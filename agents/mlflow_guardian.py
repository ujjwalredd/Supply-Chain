"""
MLflowGuardianAgent
Model: Claude Haiku (tool_use for decisions only)
Interval: 300s (5min)

What it does:
1. Queries MLflow REST API for latest model metrics
   (experiment: supply_chain_delay_prediction, model: supply_chain_delay_model)
2. Compares against stored baseline (Redis key mlflow:baseline)
3. If roc_auc drops >5% OR no model trained in >24h → triggers retraining
   via Dagster incremental job (runs gold_delay_model step)
4. After retraining: compares new metrics vs old → auto-promotes if better
5. All promotion/rollback decisions via Claude tool_use — no free text

Anti-hallucination:
  - Promotion decisions use tool_use with exact metric comparison schema
  - Never promotes if new roc_auc < 0.60 (hard floor)
  - Never promotes without at least 100 training rows
"""
import os
import json
import time
import logging
from typing import Optional

import redis
import requests

from agents.base import BaseAgent, HAIKU_MODEL

logger = logging.getLogger(__name__)

MLFLOW_URL = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
DAGSTER_URL = os.getenv("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3001")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

EXPERIMENT_NAME = "supply_chain_delay_prediction"
MODEL_NAME = "supply_chain_delay_model"
ROC_AUC_DROP_THRESHOLD = 0.05   # 5% drop triggers retraining
ROC_AUC_MIN_FLOOR = 0.60        # never promote below this
STALE_HOURS = 24                # retrain if no successful run in N hours
BASELINE_KEY = "mlflow:baseline"

# ── tool schema for promotion decisions ──────────────────────────────────────
PROMOTION_TOOL = {
    "name": "model_promotion_decision",
    "description": "Decide whether to promote the new model to Production stage.",
    "input_schema": {
        "type": "object",
        "required": ["should_promote", "reasoning", "action"],
        "properties": {
            "should_promote": {"type": "boolean"},
            "reasoning": {"type": "string"},
            "action": {
                "type": "string",
                "enum": ["promote", "keep_current", "rollback", "retrain"]
            },
            "confidence": {
                "type": "number",
                "minimum": 0, "maximum": 1
            }
        }
    }
}


class MLflowGuardianAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="mlflow_guardian",
            model=HAIKU_MODEL,
            interval_seconds=300,
            description=(
                "Monitors MLflow model metrics. "
                "Detects accuracy drift, triggers retraining, "
                "auto-promotes improved models."
            )
        )
        self._redis: Optional[redis.Redis] = None
        self._last_retrain_time: float = 0.0

    def _r(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(REDIS_URL, decode_responses=True)
        return self._redis

    # ── Main check ────────────────────────────────────────────────────────────
    def check(self) -> dict:
        metrics = {}

        # 1. Get experiment + latest run
        exp = self._get_experiment(EXPERIMENT_NAME)
        if not exp:
            logger.info("[mlflow_guardian] Experiment not found — requesting initial training")
            self._trigger_retraining("No experiment found — initial training needed")
            return {"task": "no_experiment|triggered_training"}

        exp_id = exp["experiment_id"]
        latest_run = self._get_latest_successful_run(exp_id)

        if not latest_run:
            logger.info("[mlflow_guardian] No successful run — triggering training")
            self._trigger_retraining("No successful run exists")
            return {"task": "no_run|triggered_training"}

        # MLflow API returns metrics as a list [{key, value, ...}] — convert to dict
        raw_metrics = latest_run.get("data", {}).get("metrics", [])
        if isinstance(raw_metrics, list):
            run_metrics = {m["key"]: m["value"] for m in raw_metrics if isinstance(m, dict)}
        else:
            run_metrics = raw_metrics or {}
        roc_auc = float(run_metrics.get("roc_auc", 0.0))
        accuracy = float(run_metrics.get("accuracy", 0.0))
        train_rows = float(run_metrics.get("train_rows", 0))
        run_end = latest_run.get("info", {}).get("end_time", 0)

        metrics["latest_roc_auc"] = round(roc_auc, 4)
        metrics["latest_accuracy"] = round(accuracy, 4)
        metrics["train_rows"] = int(train_rows)

        # 2. Staleness check
        age_hours = (time.time() - run_end / 1000) / 3600 if run_end else 999
        metrics["model_age_hours"] = round(age_hours, 1)

        if age_hours > STALE_HOURS:
            logger.warning(f"[mlflow_guardian] Model stale ({age_hours:.1f}h) — retraining")
            self._trigger_retraining(f"Model stale: {age_hours:.1f}h > {STALE_HOURS}h threshold")
            metrics["task"] = f"stale|roc={roc_auc:.3f}|age={age_hours:.1f}h"
            return metrics

        # 3. Baseline comparison
        baseline = self._load_baseline()
        if not baseline:
            # First time — store this run as baseline
            self._store_baseline({"roc_auc": roc_auc, "accuracy": accuracy,
                                   "run_id": latest_run["info"]["run_id"]})
            logger.info(f"[mlflow_guardian] Baseline set: roc_auc={roc_auc:.4f}")
            metrics["task"] = f"baseline_set|roc={roc_auc:.3f}"
            return metrics

        baseline_roc = float(baseline.get("roc_auc", 0))
        drop = baseline_roc - roc_auc
        metrics["roc_auc_drop"] = round(drop, 4)

        if drop > ROC_AUC_DROP_THRESHOLD:
            logger.warning(f"[mlflow_guardian] roc_auc dropped {drop:.4f} — retraining")
            self.alert(
                "HIGH",
                f"Model roc_auc dropped {drop:.4f} ({baseline_roc:.4f} → {roc_auc:.4f})",
                {"baseline": baseline_roc, "current": roc_auc, "drop": drop}
            )
            self._trigger_retraining(
                f"roc_auc drift: {baseline_roc:.4f} → {roc_auc:.4f} (drop={drop:.4f})"
            )
        else:
            logger.info(f"[mlflow_guardian] Model healthy: roc_auc={roc_auc:.4f} "
                        f"(baseline={baseline_roc:.4f}, drop={drop:.4f})")

        # 4. Check for a newly trained model that needs promotion decision
        self._check_pending_promotion(exp_id, baseline_roc)

        metrics["task"] = (
            f"roc={roc_auc:.3f}|baseline={baseline_roc:.3f}|"
            f"drop={drop:.3f}|age={age_hours:.1f}h"
        )
        return metrics

    # ── Promotion check ───────────────────────────────────────────────────────
    def _check_pending_promotion(self, exp_id: str, baseline_roc: float):
        """If there's a recent run better than production, decide whether to promote."""
        runs = self._get_recent_runs(exp_id, limit=3)
        if len(runs) < 2:
            return

        def _metrics_dict(run: dict) -> dict:
            raw = run.get("data", {}).get("metrics", [])
            if isinstance(raw, list):
                return {m["key"]: float(m["value"]) for m in raw if isinstance(m, dict)}
            return {k: float(v) for k, v in (raw or {}).items()}

        latest = runs[0]
        latest_metrics = _metrics_dict(latest)
        latest_roc = latest_metrics.get("roc_auc", 0.0)
        latest_rows = latest_metrics.get("train_rows", 0)

        # Hard floors — never promote below these regardless of LLM
        if latest_roc < ROC_AUC_MIN_FLOOR:
            logger.info(f"[mlflow_guardian] Latest run roc_auc={latest_roc:.4f} below floor {ROC_AUC_MIN_FLOOR} — no promotion")
            return
        if latest_rows < 100:
            logger.info(f"[mlflow_guardian] Too few training rows ({latest_rows}) — no promotion")
            return

        prev = runs[1]
        prev_metrics = _metrics_dict(prev)
        prev_roc = prev_metrics.get("roc_auc", 0.0)

        if latest_roc <= prev_roc:
            return   # not better — skip

        # Ask Claude for promotion decision (tool_use forced)
        decision = self._promotion_decision_llm(
            new_metrics=latest_metrics,
            old_metrics=prev_metrics,
            baseline_roc=baseline_roc,
        )

        if decision and decision.get("should_promote") and decision.get("action") == "promote":
            logger.info(f"[mlflow_guardian] Promoting model: {decision.get('reasoning')}")
            self._promote_model(latest.get("info", {}).get("run_id", ""))
            self._store_baseline({
                "roc_auc": latest_roc,
                "accuracy": latest_metrics.get("accuracy", 0),
                "run_id": latest.get("info", {}).get("run_id", ""),
            })
            self.audit("MODEL_PROMOTED", decision.get("reasoning", ""), "SUCCESS",
                       {"new_roc_auc": latest_roc, "old_roc_auc": prev_roc})
        else:
            logger.info(f"[mlflow_guardian] No promotion: {decision.get('reasoning', 'LLM declined') if decision else 'LLM call failed'}")

    def _promotion_decision_llm(
        self, new_metrics: dict, old_metrics: dict, baseline_roc: float
    ) -> Optional[dict]:
        user_msg = json.dumps({
            "new_model": new_metrics,
            "current_production": old_metrics,
            "baseline_roc_auc": baseline_roc,
            "promotion_floor": ROC_AUC_MIN_FLOOR,
            "question": "Should we promote the new model to Production?"
        }, indent=2)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=(
                    "You are an ML model governance agent for a supply chain system. "
                    "You MUST call model_promotion_decision. "
                    "Promote ONLY if new model is strictly better AND roc_auc >= "
                    f"{ROC_AUC_MIN_FLOOR}."
                ),
                tools=[PROMOTION_TOOL],
                tool_choice={"type": "tool", "name": "model_promotion_decision"},
                messages=[{"role": "user", "content": user_msg}]
            )
            for block in response.content:
                if block.type == "tool_use" and block.name == "model_promotion_decision":
                    return block.input
        except Exception as e:
            logger.error(f"[mlflow_guardian] Promotion LLM call failed: {e}")
        return None

    # ── Trigger retraining ────────────────────────────────────────────────────
    def _trigger_retraining(self, reason: str):
        # Cooldown: don't retrain more than once per 30 minutes
        if time.time() - self._last_retrain_time < 1800:
            logger.info(f"[mlflow_guardian] Retraining cooldown active — skipping ({reason})")
            return
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
            run_id = (resp.json().get("data", {})
                      .get("launchRun", {}).get("run", {}).get("runId"))
            if run_id:
                self._last_retrain_time = time.time()
                logger.info(f"[mlflow_guardian] Triggered retraining: run_id={run_id}")
                self.audit("TRIGGER_RETRAINING", reason, "SUCCESS", {"run_id": run_id})
        except Exception as e:
            logger.error(f"[mlflow_guardian] Retraining trigger failed: {e}")

    # ── Promote model via MLflow REST API ────────────────────────────────────
    def _promote_model(self, run_id: str):
        if not run_id:
            return
        try:
            # Get model version for this run
            resp = requests.get(
                f"{MLFLOW_URL}/api/2.0/mlflow/model-versions/search",
                params={"filter": f"run_id='{run_id}'"},
                timeout=10
            )
            versions = resp.json().get("model_versions", [])
            if not versions:
                return
            version = versions[0]["version"]
            # Transition to Production
            requests.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/model-versions/transition-stage",
                json={
                    "name": MODEL_NAME,
                    "version": version,
                    "stage": "Production",
                    "archive_existing_versions": True,
                },
                timeout=10
            )
            logger.info(f"[mlflow_guardian] Model v{version} promoted to Production")
        except Exception as e:
            logger.warning(f"[mlflow_guardian] Promotion API call failed: {e}")

    # ── MLflow REST API helpers ───────────────────────────────────────────────
    def _get_experiment(self, name: str) -> Optional[dict]:
        try:
            resp = requests.get(
                f"{MLFLOW_URL}/api/2.0/mlflow/experiments/get-by-name",
                params={"experiment_name": name},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json().get("experiment")
        except Exception:
            pass
        return None

    def _get_latest_successful_run(self, exp_id: str) -> Optional[dict]:
        runs = self._get_recent_runs(exp_id, limit=1)
        return runs[0] if runs else None

    def _get_recent_runs(self, exp_id: str, limit: int = 3) -> list:
        try:
            resp = requests.post(
                f"{MLFLOW_URL}/api/2.0/mlflow/runs/search",
                json={
                    "experiment_ids": [exp_id],
                    "filter": "status = 'FINISHED'",
                    "order_by": ["start_time DESC"],
                    "max_results": limit,
                },
                timeout=10
            )
            return resp.json().get("runs", [])
        except Exception:
            return []

    # ── Baseline in Redis ─────────────────────────────────────────────────────
    def _load_baseline(self) -> Optional[dict]:
        try:
            raw = self._r().get(BASELINE_KEY)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def _store_baseline(self, data: dict):
        try:
            self._r().set(BASELINE_KEY, json.dumps(data))
        except Exception:
            pass

    def apply_correction(self, correction: str):
        """Act on orchestrator corrections."""
        c = correction.lower()
        if "retrain" in c or "trigger" in c:
            logger.info("[mlflow_guardian] Orchestrator correction → forcing retraining")
            self._last_retrain_time = 0.0  # reset cooldown
            self._trigger_retraining(f"Orchestrator correction: {correction}")
        elif "reset" in c and "baseline" in c:
            logger.info("[mlflow_guardian] Orchestrator correction → clearing baseline for reset")
            try:
                self._r().delete(BASELINE_KEY)
            except Exception:
                pass
        elif "promote" in c or "rollback" in c:
            logger.info(f"[mlflow_guardian] Orchestrator correction noted (promotion managed by LLM): {correction}")
        else:
            logger.info(f"[mlflow_guardian] Orchestrator correction (no action matched): {correction}")

    def heal(self, error: Exception) -> bool:
        err_str = str(error)
        if "redis" in err_str.lower() or "connection" in err_str.lower():
            logger.warning(f"[mlflow_guardian] Connection error — resetting Redis client and retrying")
            self._redis = None  # force reconnect next call
            time.sleep(15)
            return True
        logger.warning(f"[mlflow_guardian] Healing: {error}")
        time.sleep(15)
        return True
