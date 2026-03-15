"""
Dagster Guardian Agent
Model: Claude Haiku (called only on complex failures)
Interval: 120s

Monitors:
- Asset materialization freshness
- Run statuses (FAILURE detection)
- Schedule/sensor status
- Self-healing via Dagster GraphQL API (trigger rematerialization)

Rules:
- 3 consecutive FAILURE runs -> stop retrying, escalate to orchestrator
- Asset stale > 7h -> trigger medallion_incremental
- Schedule STOPPED -> restart via GraphQL mutation
"""
import os
import time
import logging
import requests
from typing import Optional

from agents.base import BaseAgent, HAIKU_MODEL

logger = logging.getLogger(__name__)

# Bug 21: standardise default port to 3000 (internal container port) to match data_ingestion_agent
DAGSTER_URL = os.getenv("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3000")
FRESHNESS_THRESHOLD_MINUTES = int(os.getenv("ASSET_FRESHNESS_THRESHOLD_MIN", "420"))  # 7h
MAX_CONSECUTIVE_FAILURES = 3


def _gql(query: str, variables: dict = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(
        f"{DAGSTER_URL}/graphql",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()


RUNS_QUERY = """
query LatestRuns {
  runsOrError(limit: 10) {
    ... on Runs {
      results {
        runId
        status
        jobName
        startTime
        endTime
      }
    }
  }
}
"""

ASSETS_QUERY = """
query AssetFreshness {
  assetNodes {
    assetKey { path }
    latestMaterializationByPartition {
      timestamp
    }
  }
}
"""

LAUNCH_RUN_MUTATION = """
mutation LaunchRun($jobName: String!, $repositoryLocationName: String!, $repositoryName: String!) {
  launchRun(executionParams: {
    selector: {
      jobName: $jobName,
      repositoryLocationName: $repositoryLocationName,
      repositoryName: $repositoryName
    },
    runConfigData: {}
  }) {
    ... on LaunchRunSuccess {
      run { runId }
    }
    ... on PythonError {
      message
    }
  }
}
"""


class DagsterGuardianAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="dagster_guardian",
            model=HAIKU_MODEL,
            interval_seconds=120,
            description="Monitors Dagster runs, asset freshness, schedules. Triggers rematerialization on failure."
        )
        self._consecutive_failures = 0
        self._triggered_runs = set()  # run IDs we triggered to avoid double-counting
        self._escalated = False

    def check(self) -> dict:
        metrics = {}

        # 1. Check recent runs for failures
        try:
            data = _gql(RUNS_QUERY)
            runs = data.get("data", {}).get("runsOrError", {}).get("results", [])
            failed = [r for r in runs if r.get("status") == "FAILURE"]
            metrics["recent_failed_runs"] = len(failed)
            metrics["recent_runs"] = len(runs)

            if failed and not self._escalated:
                self._consecutive_failures += 1
                logger.warning(f"Dagster: {len(failed)} failed runs (consecutive={self._consecutive_failures})")

                if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(f"Dagster: {MAX_CONSECUTIVE_FAILURES}+ consecutive failures — escalating")
                    self.alert("CRITICAL",
                               f"Dagster has {self._consecutive_failures} consecutive failures — manual intervention may be needed",
                               {"failed_runs": [r["runId"] for r in failed]})
                    self._escalated = True
                    self.audit("ESCALATE_TO_ORCHESTRATOR",
                               f"{self._consecutive_failures} consecutive failures",
                               "ESCALATED", {"runs": [r["runId"] for r in failed]})
                elif self._consecutive_failures == 1:
                    # First failure — try full pipeline rebuild
                    logger.info("Dagster failure detected — triggering full pipeline rebuild")
                    self._trigger_full_job()
                else:
                    # Subsequent failures — try incremental
                    self._trigger_incremental_job()
            else:
                if self._consecutive_failures > 0:
                    logger.info("Dagster runs healthy again — resetting failure count")
                self._consecutive_failures = 0
                self._escalated = False

        except Exception as e:
            logger.warning(f"Dagster runs check failed: {e}")
            raise

        # 2. Check asset freshness
        try:
            data = _gql(ASSETS_QUERY)
            nodes = data.get("data", {}).get("assetNodes", [])
            stale_assets = []
            now = time.time()

            for node in nodes:
                key = "/".join(node.get("assetKey", {}).get("path", []))
                # latestMaterializationByPartition returns a list; take the first entry
                mat_list = node.get("latestMaterializationByPartition") or []
                last_mat = mat_list[0].get("timestamp") if mat_list else None
                if last_mat:
                    age_min = (now - float(last_mat)) / 60
                    if age_min > FRESHNESS_THRESHOLD_MINUTES:
                        stale_assets.append({"key": key, "age_min": round(age_min, 1)})

            metrics["stale_assets"] = len(stale_assets)

            if stale_assets and self._consecutive_failures < MAX_CONSECUTIVE_FAILURES:
                logger.warning(f"Stale assets detected: {[a['key'] for a in stale_assets]}")
                self._trigger_incremental_job()
                self.audit("TRIGGER_REFRESH_STALE",
                           f"{len(stale_assets)} stale assets",
                           "TRIGGERED", {"assets": stale_assets})
        except Exception as e:
            logger.warning(f"Asset freshness check failed: {e}")

        metrics["task"] = f"runs={metrics.get('recent_runs',0)}|failed={metrics.get('recent_failed_runs',0)}|stale={metrics.get('stale_assets',0)}"
        return metrics

    def _launch_job(self, job_name: str, audit_key: str):
        try:
            resp = requests.post(
                f"{DAGSTER_URL}/graphql",
                json={"query": LAUNCH_RUN_MUTATION,
                      "variables": {
                          "jobName": job_name,
                          "repositoryLocationName": "pipeline.definitions:defs",
                          "repositoryName": "__repository__"
                      }},
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            run_info = data.get("data", {}).get("launchRun", {})
            run_id = run_info.get("run", {}).get("runId")
            if run_id:
                logger.info(f"Triggered {job_name}: run_id={run_id}")
                self._triggered_runs.add(run_id)
                self.audit(audit_key, f"Triggered {job_name}", "SUCCESS", {"run_id": run_id})
            else:
                err = run_info.get("message", "unknown")
                logger.warning(f"Dagster {job_name} launch returned: {err}")
                self.audit(audit_key, err, "FAILED")
        except Exception as e:
            logger.error(f"Failed to trigger {job_name}: {e}")
            self.audit(audit_key, str(e), "FAILED")

    def _trigger_incremental_job(self):
        self._launch_job("medallion_incremental", "TRIGGER_INCREMENTAL_JOB")

    def _trigger_full_job(self):
        self._launch_job("medallion_full_pipeline", "TRIGGER_FULL_PIPELINE")

    def apply_correction(self, correction: str):
        """Act on orchestrator corrections."""
        c = correction.lower()
        if "full" in c and ("pipeline" in c or "retrain" in c or "run" in c):
            logger.info("[dagster_guardian] Orchestrator correction → triggering full pipeline")
            self._trigger_full_job()
        elif "incremental" in c or ("trigger" in c and "run" in c):
            logger.info("[dagster_guardian] Orchestrator correction → triggering incremental job")
            self._trigger_incremental_job()
        elif "reset" in c or "clear" in c or "consecutive" in c:
            logger.info("[dagster_guardian] Orchestrator correction → resetting consecutive error counter")
            self._consecutive_failures = 0
        else:
            logger.info(f"[dagster_guardian] Orchestrator correction (no action matched): {correction}")

    def heal(self, error: Exception) -> bool:
        err_str = str(error)
        if "Connection refused" in err_str or "Max retries" in err_str:
            logger.warning("Dagster webserver not reachable — waiting 60s")
            time.sleep(60)
            return True
        return False
