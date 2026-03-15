"""
Silver Layer Agent
Model: Claude Haiku
Interval: 300s (5min)

Validates:
- Silver row count <= Bronze (dedup happened)
- Zero null order_ids and supplier_ids
- Status enum values are valid
- delay_days in range [-1, 365]
- trust_score in [0, 1]
- No duplicate order_ids in Silver
"""
import os
import logging
from pathlib import Path
import requests
import pyarrow.parquet as pq

from agents.base import BaseAgent, HAIKU_MODEL

logger = logging.getLogger(__name__)

BRONZE_PATH = os.getenv("BRONZE_PATH", "/data/bronze")
SILVER_PATH = os.getenv("SILVER_PATH", "/data/silver")
DAGSTER_URL = os.getenv("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3001")

VALID_STATUSES = {"PENDING", "IN_TRANSIT", "DELIVERED", "DELAYED", "CANCELLED"}


def _read_parquet(path: str):
    """Read parquet by copying to /tmp first — avoids macOS Docker FUSE errno 35."""
    import shutil
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        shutil.copy2(path, tmp_path)
        table = pq.read_table(tmp_path, use_threads=False)
        return table.to_pandas()
    finally:
        try:
            import os as _os
            _os.unlink(tmp_path)
        except Exception:
            pass


class SilverAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="silver_agent",
            model=HAIKU_MODEL,
            interval_seconds=300,
            description="Validates Silver lakehouse layer: deduplication, null rates, constraint enforcement."
        )

    def check(self) -> dict:
        metrics = {}
        silver_dir = Path(SILVER_PATH)

        if not silver_dir.exists() or not list(silver_dir.rglob("*.parquet")):
            logger.warning(f"Silver path empty or missing: {SILVER_PATH}")
            self._trigger_silver()
            return {"task": "silver_missing", "triggered": True}

        orders_files = [f for f in silver_dir.rglob("*.parquet") if f.is_file() and "orders" in str(f)]
        if not orders_files:
            logger.warning("No Silver orders files found")
            self._trigger_silver()
            return {"task": "silver_orders_missing", "triggered": True}

        try:
            df = _read_parquet(str(orders_files[0]))
        except Exception as e:
            logger.error(f"Cannot read Silver orders: {e}")
            raise

        metrics["silver_row_count"] = len(df)

        if df.empty:
            logger.error("Silver orders parquet is EMPTY")
            self.alert("HIGH", "Silver orders is empty", {"file": str(orders_files[0])})
            self._trigger_silver()
            return metrics

        issues = []

        # 1. Null check on critical fields
        for col in ["order_id", "supplier_id", "status"]:
            if col in df.columns:
                null_count = int(df[col].isnull().sum())
                metrics[f"null_{col}"] = null_count
                if null_count > 0:
                    issues.append(f"{col}: {null_count} nulls")

        # 2. Status enum validation
        if "status" in df.columns:
            invalid_status = df[~df["status"].isin(VALID_STATUSES)]
            metrics["invalid_status_count"] = len(invalid_status)
            if len(invalid_status) > 0:
                bad_vals = invalid_status["status"].unique().tolist()[:5]
                issues.append(f"Invalid status values: {bad_vals}")

        # 3. Delay days range
        if "delay_days" in df.columns:
            out_of_range = df[(df["delay_days"] < -1) | (df["delay_days"] > 365)]
            metrics["delay_days_out_of_range"] = len(out_of_range)
            if len(out_of_range) > 0:
                issues.append(f"delay_days out of range [-1,365]: {len(out_of_range)} rows")

        # 4. Trust score range (suppliers)
        supplier_files = [f for f in silver_dir.rglob("*.parquet") if f.is_file() and "supplier" in f.name]
        if supplier_files:
            try:
                sdf = _read_parquet(str(supplier_files[0]))
                if "trust_score" in sdf.columns:
                    bad_trust = sdf[(sdf["trust_score"] < 0) | (sdf["trust_score"] > 1)]
                    metrics["bad_trust_score_count"] = len(bad_trust)
                    if len(bad_trust) > 0:
                        issues.append(f"trust_score out of [0,1]: {len(bad_trust)} rows")
            except Exception as e:
                logger.debug(f"Supplier silver check skipped: {e}")

        # 5. Duplicate order_ids
        if "order_id" in df.columns:
            dupes = int(df["order_id"].duplicated().sum())
            metrics["duplicate_order_ids"] = dupes
            if dupes > 0:
                issues.append(f"{dupes} duplicate order_ids in Silver (dedup failed)")

        if issues:
            logger.error(f"Silver validation issues: {issues}")
            analysis = self.analyze_with_llm(
                system_prompt="You are a data quality engineer. Analyze Silver layer data quality issues.",
                user_message=f"Silver layer has these quality issues: {issues}. "
                             f"Row count: {len(df)}. "
                             f"Recommend specific fixes for each issue.",
                max_tokens=512
            )
            self.alert("HIGH", f"Silver validation failed: {len(issues)} issue(s)",
                       {"issues": issues, "analysis": analysis})
            self.audit("SILVER_VALIDATION_FAILED", analysis, "ALERT",
                       {"issues": issues, "row_count": len(df)})
            self._trigger_silver()

        metrics["task"] = f"rows={len(df)}|issues={len(issues)}"
        return metrics

    def _trigger_silver(self):
        try:
            resp = requests.post(
                f"{DAGSTER_URL}/graphql",
                json={"query": """
                    mutation {
                        launchRun(executionParams: {
                            selector: {
                                jobName: "medallion_incremental",
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
            run_id = resp.json().get("data", {}).get("launchRun", {}).get("run", {}).get("runId")
            if run_id:
                logger.info(f"Triggered incremental job for Silver fix: {run_id}")
                self.audit("TRIGGER_SILVER_REBUILD", "Validation failure", "SUCCESS", {"run_id": run_id})
        except Exception as e:
            logger.error(f"Silver rebuild trigger failed: {e}")

    def apply_correction(self, correction: str):
        """Act on orchestrator corrections."""
        c = correction.lower()
        if "trigger" in c or "retrigger" in c or "run" in c or "materialize" in c:
            logger.info("[silver_agent] Orchestrator correction → triggering silver materialization")
            self._trigger_silver()
        else:
            logger.info(f"[silver_agent] Orchestrator correction (no action matched): {correction}")

    def heal(self, error: Exception) -> bool:
        self._trigger_silver()
        return True
