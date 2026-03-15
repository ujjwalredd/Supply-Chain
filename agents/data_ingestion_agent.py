"""
DataIngestionAgent — deepagents edition
Model: Claude Haiku (schema inference + multi-step validation loop)
Interval: 60s

What it does:
- Watches /data/source/ for files it has NOT seen before
- For each new file: reads a 10-row sample, calls Claude with tool_use to infer
  the exact schema and produce a validated Python loader function
- deepagents path: iterative validation loop — up to 3 fix attempts with full
  error context fed back each time (not just 1 retry)
- Legacy fallback: 1 retry using direct Anthropic SDK tool_use
- Validates the generated loader by running it on the sample (CodeExecutor gate)
- If valid: writes loader to /data/source/_loaders/<name>.py and triggers
  medallion_full_pipeline via Dagster GraphQL
- Tracks seen files in Redis SET "ingestion:known_files"

Anti-hallucination:
  - ALL schema decisions via tool_use (structured JSON, no free text)
  - Generated loader is syntax-checked (gate 1) then run on sample (gate 2)
  - Only triggers pipeline after both gates pass
"""
import os
import csv
import json
import time
import logging
import textwrap
from pathlib import Path
from typing import Optional

import redis
import requests

from agents.base import BaseAgent, HAIKU_MODEL, SONNET_MODEL
from agents.tools.code_executor import CodeExecutor

logger = logging.getLogger(__name__)

DATA_SOURCE_DIR = os.getenv("DATA_SOURCE_DIR", "/data/source")
DAGSTER_URL = os.getenv("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3000")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
KNOWN_FILES_KEY = "ingestion:known_files"

# Files that ship with the repo — already handled by the pipeline
BUILTIN_FILES = {
    "orderlist.csv", "freightrates.csv", "whcapacities.csv",
    "plantports.csv", "productsperplant.csv", "supplifySupplychain.csv",
    "vmicustomers.csv", "whcosts.csv", "manifest.txt",
}

# Maximum loader-fix attempts (deepagents iterative loop)
MAX_FIX_ATTEMPTS = 3

# ── tool_use schema for schema inference (used in both paths) ─────────────────
SCHEMA_TOOL = {
    "name": "infer_csv_schema",
    "description": (
        "Infer schema of a CSV file from sample rows and generate a Python "
        "loader function named load_csv(path: Path) -> Iterator[dict]."
    ),
    "input_schema": {
        "type": "object",
        "required": ["table_name", "columns", "loader_code"],
        "properties": {
            "table_name": {
                "type": "string",
                "description": "Snake_case table name derived from filename"
            },
            "columns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "dtype"],
                    "properties": {
                        "name": {"type": "string"},
                        "dtype": {
                            "type": "string",
                            "enum": ["str", "float", "int", "datetime", "bool"]
                        },
                        "nullable": {"type": "boolean"}
                    }
                }
            },
            "loader_code": {
                "type": "string",
                "description": (
                    "Complete Python function: "
                    "def load_csv(path: Path) -> Iterator[dict]: ... "
                    "Must import csv, datetime, pathlib.Path at top of function. "
                    "Must handle missing/empty values gracefully."
                )
            },
            "primary_key_hint": {"type": "string"}
        }
    }
}


# ── deepagents availability check ─────────────────────────────────────────────
def _deepagents_available() -> bool:
    try:
        import deepagents  # noqa: F401
        from langchain_anthropic import ChatAnthropic  # noqa: F401
        from langchain_core.tools import tool  # noqa: F401
        from pydantic import BaseModel  # noqa: F401
        return True
    except ImportError:
        return False


# ── Pydantic result schema ─────────────────────────────────────────────────────
def _build_ingestion_result_model():
    from pydantic import BaseModel, Field
    from typing import List

    class ColumnSchema(BaseModel):
        name: str
        dtype: str
        nullable: bool = True

    class IngestionResult(BaseModel):
        table_name: str = Field(description="Snake_case table name")
        columns: List[ColumnSchema] = Field(description="Column schema list")
        loader_code: str = Field(description="Complete Python load_csv function")
        primary_key_hint: str = Field(default="", description="Suggested primary key column")
        validation_passed: bool = Field(default=False, description="Whether loader passed all validation gates")
        attempts: int = Field(default=1, description="Number of fix attempts made")
        error_reason: str = Field(default="", description="Why validation failed if not passed")

    return IngestionResult


# ── LangChain tools for ingestion agent ──────────────────────────────────────
def _build_ingestion_tools(executor: CodeExecutor):
    from langchain_core.tools import tool

    @tool
    def validate_python_loader(loader_code: str, sample_csv_path: str, expected_keys: str) -> str:
        """Validate a Python CSV loader function by running it on a sample file.
        loader_code: the complete Python function definition (must be named load_csv)
        sample_csv_path: absolute path to the CSV file to test against
        expected_keys: JSON array string of column names the loader should return
        Returns JSON with ok (bool), error (str if failed), rows (int), first_keys (list)."""
        try:
            keys = json.loads(expected_keys) if expected_keys else []
        except Exception:
            keys = []
        try:
            result = executor.validate_loader_code(
                loader_code=loader_code,
                sample_path=sample_csv_path,
                expected_keys=keys,
                max_rows=10,
            )
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @tool
    def read_csv_sample(csv_path: str, n_rows: int = 10) -> str:
        """Read a CSV file and return its header and first N rows as JSON.
        csv_path: absolute path to the CSV file
        n_rows: how many data rows to read (default 10, max 20)
        Returns JSON with header (list) and rows (list of lists)."""
        n_rows = min(int(n_rows), 20)
        try:
            with open(csv_path, encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                all_rows = [r for _, r in zip(range(n_rows + 1), reader)]
            if not all_rows:
                return json.dumps({"header": [], "rows": []})
            return json.dumps({"header": all_rows[0], "rows": all_rows[1:]})
        except Exception as e:
            return json.dumps({"error": str(e)})

    return [validate_python_loader, read_csv_sample]


# ── Build the deepagents ingestion agent ─────────────────────────────────────
def _build_ingestion_agent(executor: CodeExecutor):
    from deepagents import create_deep_agent  # type: ignore

    IngestionResult = _build_ingestion_result_model()
    tools = _build_ingestion_tools(executor)

    # Load data-ingestion skill
    skill_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "skills", "data-ingestion", "SKILL.md"
    )
    skill_text = ""
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            skill_text = f.read()
    except Exception:
        pass

    system_prompt = f"""You are a supply chain data engineer for the Adopt Supply Chain AI OS.
Your task: infer the schema of a new CSV file and generate a validated Python loader.

RULES (hard constraints — never break):
1. The loader function MUST be named `load_csv`
2. Return type must be Iterator[dict] (use `yield`)
3. Must handle empty/null values without raising exceptions
4. All imports must be from Python stdlib only (no pip packages)
5. No print statements
6. Max 50 lines of loader code

VALIDATION LOOP:
- Use validate_python_loader to test your generated loader
- If it fails, read the error carefully and fix the specific issue
- You have up to {MAX_FIX_ATTEMPTS} attempts before giving up
- Always use read_csv_sample to verify your understanding of the file structure first

{skill_text}
"""

    graph = create_deep_agent(
        model=HAIKU_MODEL,
        tools=tools,
        response_format=IngestionResult,
        system_prompt=system_prompt,
    )
    return graph, IngestionResult


class DataIngestionAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="data_ingestion",
            model=HAIKU_MODEL,
            interval_seconds=60,
            description=(
                "Watches /data/source/ for new CSV files. "
                "Auto-infers schema via Claude tool_use, validates loader, "
                "triggers Dagster pipeline."
            )
        )
        self._executor = CodeExecutor()
        self._redis: Optional[redis.Redis] = None

        # deepagents graph — built lazily on first use
        self._deep_graph = None
        self._IngestionResult = None
        self._use_deepagents = _deepagents_available()

        if self._use_deepagents:
            logger.info("[data_ingestion] deepagents available — iterative validation loop enabled")
        else:
            logger.info("[data_ingestion] deepagents not available — using legacy 1-retry path")

    # ── Redis helpers ─────────────────────────────────────────────────────────
    def _r(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    def _known_files(self) -> set:
        return self._r().smembers(KNOWN_FILES_KEY)

    def _mark_known(self, filename: str):
        self._r().sadd(KNOWN_FILES_KEY, filename)

    # ── Main check loop ───────────────────────────────────────────────────────
    def check(self) -> dict:
        metrics = {"new_files_found": 0, "successfully_processed": 0, "failed": 0}
        source_dir = Path(DATA_SOURCE_DIR)

        if not source_dir.exists():
            logger.debug(f"[data_ingestion] Source dir not found: {DATA_SOURCE_DIR}")
            return metrics

        known = self._known_files()

        # Pre-register built-in files on first run
        for bf in BUILTIN_FILES:
            if bf not in known:
                self._mark_known(bf)
                known.add(bf)

        csv_files = [
            f for f in source_dir.iterdir()
            if f.is_file()
            and f.suffix.lower() in (".csv", ".tsv", ".txt")
            and f.name.lower() not in known
        ]

        metrics["new_files_found"] = len(csv_files)

        for csv_file in csv_files:
            try:
                logger.info(f"[data_ingestion] New file detected: {csv_file.name}")
                ok = self._process_new_file(csv_file)
                if ok:
                    metrics["successfully_processed"] += 1
                    self._mark_known(csv_file.name.lower())
                else:
                    metrics["failed"] += 1
            except Exception as e:
                logger.error(f"[data_ingestion] Failed to process {csv_file.name}: {e}")
                metrics["failed"] += 1

        metrics["task"] = (
            f"new={metrics['new_files_found']}|"
            f"ok={metrics['successfully_processed']}|"
            f"fail={metrics['failed']}"
        )
        return metrics

    # ── Process a single new file ─────────────────────────────────────────────
    def _process_new_file(self, path: Path) -> bool:
        # Read sample rows
        sample_rows, header = self._read_sample(path, n=10)
        if not sample_rows:
            logger.warning(f"[data_ingestion] Empty file: {path.name}")
            return False

        logger.info(
            f"[data_ingestion] Inferring schema for {path.name} "
            f"({len(sample_rows)} sample rows, {len(header)} columns)"
        )

        if self._use_deepagents:
            schema = self._infer_schema_with_deepagents(path)
        else:
            schema = self._infer_schema_with_llm(path.name, header, sample_rows)

        if not schema:
            logger.error(f"[data_ingestion] Schema inference failed for {path.name}")
            return False

        loader_code = schema.get("loader_code", "")
        table_name = schema.get("table_name", path.stem.lower().replace("-", "_"))
        columns = schema.get("columns", [])

        # Normalize columns: could be list of dicts or list of Pydantic models
        if columns and hasattr(columns[0], "name"):
            expected_keys = [c.name for c in columns]
        else:
            expected_keys = [c["name"] for c in columns if isinstance(c, dict)]

        # If deepagents already validated, skip re-validation
        already_validated = schema.get("validation_passed", False)

        if not already_validated:
            # Run validation gates
            validation = self._executor.validate_loader_code(
                loader_code=loader_code,
                sample_path=str(path),
                expected_keys=expected_keys,
                max_rows=10,
            )

            if not validation.get("ok"):
                err = validation.get("error") or validation.get("missing_keys")
                logger.error(f"[data_ingestion] Loader validation failed for {path.name}: {err}")
                self.alert(
                    "MEDIUM",
                    f"Generated loader for {path.name} failed validation: {err}",
                    {"file": path.name, "validation": validation}
                )
                # One more fix attempt via legacy path
                schema = self._fix_loader(path.name, loader_code, str(err), header, sample_rows)
                if not schema:
                    return False
                loader_code = schema.get("loader_code", "")
                validation = self._executor.validate_loader_code(
                    loader_code=loader_code,
                    sample_path=str(path),
                    expected_keys=expected_keys,
                    max_rows=10,
                )
                if not validation.get("ok"):
                    logger.error(f"[data_ingestion] Second validation failed for {path.name}")
                    return False
        else:
            logger.info(f"[data_ingestion] deepagents pre-validated loader for {path.name}")

        logger.info(f"[data_ingestion] Loader ready for {path.name}: table={table_name}")

        # Save loader to disk
        self._save_loader(path, table_name, loader_code, schema)

        # Trigger full pipeline
        self._trigger_pipeline()

        self.audit(
            "NEW_FILE_INGESTED",
            f"Auto-generated loader for {path.name}, table={table_name}",
            "SUCCESS",
            {"file": path.name, "table": table_name, "columns": expected_keys}
        )
        logger.info(f"[data_ingestion] ✓ {path.name} → table={table_name}, columns={expected_keys}")
        return True

    # ── deepagents schema inference with iterative validation ─────────────────
    def _infer_schema_with_deepagents(self, path: Path) -> Optional[dict]:
        """Use deepagents iterative loop for schema inference + validation."""
        try:
            if self._deep_graph is None:
                self._deep_graph, self._IngestionResult = _build_ingestion_agent(self._executor)
                logger.info("[data_ingestion] deepagents ingestion graph compiled")

            user_message = (
                f"New CSV file to ingest: {path.name}\n"
                f"Full path: {str(path)}\n\n"
                f"Steps:\n"
                f"1. Use read_csv_sample to read the file and understand its structure\n"
                f"2. Generate a load_csv loader function\n"
                f"3. Use validate_python_loader to test it (expected_keys from the header)\n"
                f"4. Fix any errors and re-validate until it passes or {MAX_FIX_ATTEMPTS} attempts reached\n"
                f"5. Return the final IngestionResult with validation_passed=True if all gates passed\n"
            )

            result = self._deep_graph.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config={"configurable": {"thread_id": f"ingestion-{path.name}"}},
            )

            # Extract structured result
            structured = None
            if hasattr(result, "get"):
                # Check structured_response key
                sr = result.get("structured_response")
                if isinstance(sr, self._IngestionResult):
                    structured = sr
                elif isinstance(sr, dict):
                    try:
                        structured = self._IngestionResult(**sr)
                    except Exception:
                        pass

                # Check messages
                if structured is None:
                    messages = result.get("messages", [])
                    for msg in reversed(messages):
                        content = getattr(msg, "content", "")
                        if isinstance(content, self._IngestionResult):
                            structured = content
                            break

            if structured is not None:
                logger.info(
                    f"[data_ingestion/deepagents] Schema inferred for {path.name}: "
                    f"table={structured.table_name}, "
                    f"validated={structured.validation_passed}, "
                    f"attempts={structured.attempts}"
                )
                # Convert Pydantic model to dict for downstream code
                return {
                    "table_name": structured.table_name,
                    "columns": [
                        {"name": c.name, "dtype": c.dtype, "nullable": c.nullable}
                        for c in (structured.columns or [])
                    ],
                    "loader_code": structured.loader_code,
                    "primary_key_hint": structured.primary_key_hint or "",
                    "validation_passed": structured.validation_passed,
                }

            logger.warning(f"[data_ingestion/deepagents] Structured output not found for {path.name}, falling back")
            return None

        except Exception as e:
            logger.error(f"[data_ingestion/deepagents] Ingestion agent failed for {path.name}: {e}")
            # Reset graph on error
            self._deep_graph = None
            return None

    # ── Legacy Anthropic SDK schema inference (fallback) ──────────────────────
    def _infer_schema_with_llm(
        self, filename: str, header: list, sample_rows: list
    ) -> Optional[dict]:
        sample_str = "\n".join([",".join(header)] + [",".join(r) for r in sample_rows[:5]])
        user_msg = (
            f"Filename: {filename}\n\n"
            f"CSV sample (header + 5 rows):\n```\n{sample_str}\n```\n\n"
            "Infer the schema and generate a complete Python loader function. "
            "The function MUST be named `load_csv` and return Iterator[dict]. "
            "Handle empty/null values, type coercion errors gracefully. "
            "Do not import anything outside stdlib."
        )
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=(
                    "You are a supply chain data engineer. "
                    "You MUST call the infer_csv_schema tool. No free-text responses."
                ),
                tools=[SCHEMA_TOOL],
                tool_choice={"type": "tool", "name": "infer_csv_schema"},
                messages=[{"role": "user", "content": user_msg}]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "infer_csv_schema":
                    return block.input
        except Exception as e:
            logger.error(f"[data_ingestion] LLM schema inference failed: {e}")
        return None

    def _fix_loader(
        self, filename: str, broken_code: str, error: str, header: list, sample_rows: list
    ) -> Optional[dict]:
        sample_str = "\n".join([",".join(header)] + [",".join(r) for r in sample_rows[:3]])
        user_msg = (
            f"The loader for {filename} failed with: {error}\n\n"
            f"Broken code:\n```python\n{broken_code}\n```\n\n"
            f"CSV sample:\n```\n{sample_str}\n```\n\n"
            "Fix the loader. The function MUST be named `load_csv`."
        )
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system="Fix the CSV loader. Call infer_csv_schema with corrected loader_code.",
                tools=[SCHEMA_TOOL],
                tool_choice={"type": "tool", "name": "infer_csv_schema"},
                messages=[{"role": "user", "content": user_msg}]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "infer_csv_schema":
                    return block.input
        except Exception as e:
            logger.error(f"[data_ingestion] LLM fix attempt failed: {e}")
        return None

    # ── Save loader + metadata ────────────────────────────────────────────────
    def _save_loader(self, path: Path, table_name: str, loader_code: str, schema: dict):
        loader_dir = path.parent / "_loaders"
        loader_dir.mkdir(exist_ok=True)
        loader_file = loader_dir / f"{table_name}.py"

        full_module = textwrap.dedent(f"""
# Auto-generated by DataIngestionAgent — {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}
# Source file: {path.name}
# Table: {table_name}
from pathlib import Path
from typing import Iterator

{loader_code}
""").strip()

        loader_file.write_text(full_module, encoding="utf-8")

        meta_file = loader_dir / f"{table_name}.json"
        columns = schema.get("columns", [])
        # Normalize columns for JSON serialization
        if columns and hasattr(columns[0], "name"):
            columns = [{"name": c.name, "dtype": c.dtype, "nullable": c.nullable} for c in columns]
        meta_file.write_text(json.dumps({
            "table_name": table_name,
            "source_file": path.name,
            "columns": columns,
            "primary_key_hint": schema.get("primary_key_hint", ""),
            "generated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "loader_file": str(loader_file),
        }, indent=2), encoding="utf-8")

        logger.info(f"[data_ingestion] Saved loader → {loader_file}")

    # ── Trigger Dagster pipeline ──────────────────────────────────────────────
    def _trigger_pipeline(self):
        try:
            resp = requests.post(
                f"{DAGSTER_URL}/graphql",
                json={"query": """
                    mutation {
                        launchRun(executionParams: {
                            selector: {
                                jobName: "medallion_full_pipeline",
                                repositoryLocationName: "pipeline.definitions:defs",
                                repositoryName: "__repository__"
                            },
                            runConfigData: {}
                        }) {
                            ... on LaunchRunSuccess { run { runId } }
                            ... on PythonError { message }
                        }
                    }
                """},
                timeout=15
            )
            run_id = (resp.json().get("data", {})
                      .get("launchRun", {}).get("run", {}).get("runId"))
            if run_id:
                logger.info(f"[data_ingestion] Triggered pipeline: {run_id}")
                self.audit("TRIGGER_PIPELINE", "New file ingested", "SUCCESS",
                           {"run_id": run_id})
        except Exception as e:
            logger.warning(f"[data_ingestion] Pipeline trigger failed: {e}")

    # ── CSV helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _read_sample(path: Path, n: int = 10):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = [r for _, r in zip(range(n + 1), reader)]
            if not rows:
                return [], []
            header = rows[0]
            return rows[1:], header
        except Exception as e:
            logger.error(f"[data_ingestion] CSV read failed: {e}")
            return [], []

    def heal(self, error: Exception) -> bool:
        logger.warning(f"[data_ingestion] Healing: {error}")
        # Reset deepagents graph on error
        self._deep_graph = None
        time.sleep(10)
        return True
