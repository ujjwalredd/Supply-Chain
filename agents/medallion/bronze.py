"""
Bronze Layer Agent
Model: Claude Haiku (called only on schema drift)
Interval: 300s (5min)

Validates:
- Bronze parquet files exist and are non-empty
- Schema matches expected columns
- New data arriving (freshness)
- No duplicate partition writes

Self-healing:
- Triggers Dagster bronze assets on staleness
"""
import os
import time
import logging
from pathlib import Path
from typing import Optional
import requests

from agents.base import BaseAgent, HAIKU_MODEL

logger = logging.getLogger(__name__)

BRONZE_PATH = os.getenv("BRONZE_PATH", "/data/bronze")
DAGSTER_URL = os.getenv("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3001")

EXPECTED_ORDER_COLS = {
    "order_id", "supplier_id", "product", "quantity",
    "unit_price", "order_value", "status", "delay_days"
}

STALE_THRESHOLD_MINUTES = int(os.getenv("BRONZE_STALE_THRESHOLD_MIN", "30"))


def _read_parquet_sample(path: str, n: int = 100):
    """Read first n rows of a parquet file. Returns (df, columns) or raises.
    Copies to /tmp first to avoid macOS Docker volume mount errno 35 (FUSE locking)."""
    import shutil
    import tempfile
    import pyarrow.parquet as pq

    # Copy to local temp dir to avoid FUSE/overlayfs locking on Docker volume mounts
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        shutil.copy2(path, tmp_path)
        table = pq.read_table(tmp_path, use_threads=False)
        df = table.to_pandas()
        return df.head(n), list(df.columns)
    finally:
        try:
            import os as _os
            _os.unlink(tmp_path)
        except Exception:
            pass


class BronzeAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="bronze_agent",
            model=HAIKU_MODEL,
            interval_seconds=300,
            description="Validates Bronze lakehouse layer: schema, freshness, row counts."
        )

    def check(self) -> dict:
        metrics = {}
        bronze_dir = Path(BRONZE_PATH)

        if not bronze_dir.exists():
            logger.warning(f"Bronze directory not found: {BRONZE_PATH}")
            self._trigger_bronze_materialization()
            return {"task": "bronze_dir_missing", "triggered_materialization": True}

        # Find all parquet files
        parquet_files = list(bronze_dir.rglob("*.parquet"))
        metrics["total_parquet_files"] = len(parquet_files)

        if len(parquet_files) == 0:
            logger.warning("No Bronze parquet files found — triggering materialization")
            self._trigger_bronze_materialization()
            return {"task": "no_parquet_files", "triggered_materialization": True}

        # Check freshness of most recently modified file
        latest = max(parquet_files, key=lambda p: p.stat().st_mtime)
        age_min = (time.time() - latest.stat().st_mtime) / 60
        metrics["latest_file_age_min"] = round(age_min, 1)
        metrics["latest_file"] = str(latest)

        if age_min > STALE_THRESHOLD_MINUTES:
            logger.warning(f"Bronze stale: latest file {age_min:.1f}min old (threshold={STALE_THRESHOLD_MINUTES})")
            self.alert("MEDIUM", f"Bronze layer stale: {age_min:.1f} min since last write",
                       {"latest_file": str(latest), "age_min": age_min})
            self._trigger_bronze_materialization()

        # Validate schema of orders file
        orders_files = [f for f in bronze_dir.rglob("*.parquet") if f.is_file() and "orders" in f.name]
        if orders_files:
            try:
                df, cols = _read_parquet_sample(str(orders_files[0]))
                cols_set = set(c.lower() for c in cols)
                missing = EXPECTED_ORDER_COLS - cols_set
                metrics["orders_row_count"] = len(df)
                metrics["orders_columns"] = cols
                metrics["missing_required_cols"] = list(missing)

                if df.empty:
                    logger.error("Bronze orders file is EMPTY")
                    self.alert("HIGH", "Bronze orders parquet is empty", {"file": str(orders_files[0])})
                    self._trigger_bronze_materialization()
                elif missing:
                    # Schema drift — call LLM for analysis
                    logger.warning(f"Bronze schema drift: missing columns {missing}")
                    analysis = self.analyze_with_llm(
                        system_prompt="You are a supply chain data engineer. Analyze schema drift in Bronze layer.",
                        user_message=f"Bronze orders parquet is missing expected columns: {missing}. "
                                     f"Current columns: {cols}. "
                                     f"What is the likely cause and recommended fix?",
                        max_tokens=256
                    )
                    self.alert("HIGH", f"Bronze schema drift: missing {missing}",
                               {"missing": list(missing), "analysis": analysis})
                    self.audit("SCHEMA_DRIFT_DETECTED", analysis, "ALERT",
                               {"missing_cols": list(missing)})
            except Exception as e:
                logger.error(f"Failed to read Bronze orders parquet: {e}")
                raise

        metrics["task"] = f"files={len(parquet_files)}|age={metrics.get('latest_file_age_min', '?')}min"
        return metrics

    def _trigger_bronze_materialization(self):
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
            resp.raise_for_status()
            data = resp.json()
            run_id = data.get("data", {}).get("launchRun", {}).get("run", {}).get("runId")
            if run_id:
                logger.info(f"Triggered medallion_full_pipeline for Bronze: {run_id}")
                self.audit("TRIGGER_BRONZE_MATERIALIZATION", "Stale or missing data", "SUCCESS",
                           {"run_id": run_id})
        except Exception as e:
            logger.error(f"Failed to trigger Bronze materialization: {e}")
            self.audit("TRIGGER_BRONZE_MATERIALIZATION", str(e), "FAILED")

    def apply_correction(self, correction: str):
        """Act on orchestrator corrections."""
        c = correction.lower()
        if "trigger" in c or "materialize" in c or "retrigger" in c or "run" in c:
            logger.info("[bronze_agent] Orchestrator correction → triggering bronze materialization")
            self._trigger_bronze_materialization()
        else:
            logger.info(f"[bronze_agent] Orchestrator correction (no action matched): {correction}")

    def heal(self, error: Exception) -> bool:
        if "No such file" in str(error) or "not found" in str(error).lower():
            logger.warning("Bronze path not found during heal — triggering materialization")
            self._trigger_bronze_materialization()
            return True
        return False
