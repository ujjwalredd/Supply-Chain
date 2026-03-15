"""
DataIngestionAgent
Model: Claude Haiku (schema inference only — tool_use forced, no free text)
Interval: 60s

What it does:
- Watches /data/source/ for files it has NOT seen before
- For each new file: reads a 10-row sample, calls Claude with tool_use to infer
  the exact schema and produce a validated Python loader function
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
import hashlib
import textwrap
from pathlib import Path
from typing import Optional

import redis
import requests

from agents.base import BaseAgent, HAIKU_MODEL
from agents.tools.code_executor import CodeExecutor, CodeExecutionError

logger = logging.getLogger(__name__)

DATA_SOURCE_DIR = os.getenv("DATA_SOURCE_DIR", "/data/source")
DAGSTER_URL = os.getenv("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3001")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
KNOWN_FILES_KEY = "ingestion:known_files"

# Files that ship with the repo — already handled by the pipeline
BUILTIN_FILES = {
    "orderlist.csv", "freightrates.csv", "whcapacities.csv",
    "plantports.csv", "productsperplant.csv", "supplifySupplychain.csv",
    "vmicustomers.csv", "whcosts.csv", "manifest.txt",
}

# ── tool_use schema for schema inference ──────────────────────────────────────
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
                    "def load_csv(path: Path) -> Iterator[dict]: ..."
                    " Must import csv, datetime, pathlib.Path at top of function. "
                    "Must handle missing/empty values gracefully."
                )
            },
            "primary_key_hint": {"type": "string"}
        }
    }
}


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

        logger.info(f"[data_ingestion] Inferring schema for {path.name} "
                    f"({len(sample_rows)} sample rows, {len(header)} columns)")

        # Call Claude with tool_use — forced, no free text
        schema = self._infer_schema_with_llm(path.name, header, sample_rows)
        if not schema:
            logger.error(f"[data_ingestion] Schema inference failed for {path.name}")
            return False

        loader_code = schema.get("loader_code", "")
        table_name = schema.get("table_name", path.stem.lower().replace("-", "_"))
        columns = schema.get("columns", [])
        expected_keys = [c["name"] for c in columns]

        # Gate 2 — run loader on sample, validate output
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
            # Ask Claude to fix it
            schema = self._fix_loader(path.name, loader_code, str(err), header, sample_rows)
            if not schema:
                return False
            loader_code = schema.get("loader_code", "")
            # Re-validate
            validation = self._executor.validate_loader_code(
                loader_code=loader_code,
                sample_path=str(path),
                expected_keys=expected_keys,
                max_rows=10,
            )
            if not validation.get("ok"):
                logger.error(f"[data_ingestion] Second validation also failed for {path.name}")
                return False

        logger.info(f"[data_ingestion] Loader validated for {path.name}: "
                    f"{validation.get('rows', '?')} rows, "
                    f"keys={validation.get('first_keys', [])}")

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
        logger.info(f"[data_ingestion] ✓ {path.name} → table={table_name}, "
                    f"columns={expected_keys}")
        return True

    # ── Claude schema inference (tool_use forced) ─────────────────────────────
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
        meta_file.write_text(json.dumps({
            "table_name": table_name,
            "source_file": path.name,
            "columns": schema.get("columns", []),
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
        time.sleep(10)
        return True
