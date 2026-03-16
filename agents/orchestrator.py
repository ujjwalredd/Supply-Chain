"""
Main Orchestrator Agent — deepagents edition
Model: Claude Sonnet 4.6
Interval: 300s (5min) for routine collection
         Immediate on CRITICAL alerts via Redis

Architecture:
- Uses deepagents `create_deep_agent()` with structured Pydantic output
- 3 specialist sub-agents: kafka_investigator, dagster_investigator, ml_investigator
- 6 LangChain tools: get_heartbeats, get_audit_log, get_kafka_lag, get_dagster_runs,
                     get_mlflow_status, issue_correction, trigger_pipeline
- Persistent memory: agents/memories/incident_patterns.md
- Skills: supply-chain-ops, kafka-diagnosis, dagster-diagnosis, mlflow-governance
- Fallback to legacy Anthropic SDK if deepagents is unavailable
"""
import os
import json
import time
import logging
import threading
import redis
import requests

from agents.base import BaseAgent, SONNET_MODEL, HAIKU_MODEL, _global_shutdown
from agents import state, communication

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DAGSTER_URL = os.getenv("DAGSTER_WEBSERVER_URL", "http://dagster-webserver:3000")

# ── Path helpers ──────────────────────────────────────────────────────────────
_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MEMORIES_DIR = os.path.join(_AGENTS_DIR, "memories")
_SKILLS_DIR = os.path.join(_AGENTS_DIR, "skills")

_INCIDENT_MEMORY_FILE = os.path.join(_MEMORIES_DIR, "incident_patterns.md")

_SKILL_FILES = [
    os.path.join(_SKILLS_DIR, "supply-chain-ops", "SKILL.md"),
    os.path.join(_SKILLS_DIR, "kafka-diagnosis", "SKILL.md"),
    os.path.join(_SKILLS_DIR, "dagster-diagnosis", "SKILL.md"),
    os.path.join(_SKILLS_DIR, "mlflow-governance", "SKILL.md"),
]


def _load_file_safe(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _load_skills_text() -> str:
    parts = []
    for p in _SKILL_FILES:
        content = _load_file_safe(p)
        if content:
            parts.append(f"## SKILL: {os.path.basename(os.path.dirname(p))}\n{content}")
    return "\n\n---\n\n".join(parts)


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


# ── Pydantic response schema ──────────────────────────────────────────────────
def _build_orchestration_result_model():
    from pydantic import BaseModel, Field
    from typing import List, Optional

    class CorrectionItem(BaseModel):
        agent_id: str = Field(description="Agent to correct")
        correction: str = Field(description="Exact correction instruction to send")

    class OrchestrationResult(BaseModel):
        root_cause_analysis: str = Field(description="What is causing the issues observed")
        correlations: List[str] = Field(default_factory=list, description="List of correlated failure patterns")
        corrections: List[CorrectionItem] = Field(default_factory=list, description="Corrections to issue to agents")
        human_intervention_needed: bool = Field(default=False, description="True if human must act")
        summary: str = Field(description="One-line summary of the orchestration cycle")
        confidence: str = Field(default="HIGH", description="Confidence in analysis: HIGH, MEDIUM, or LOW")

    return OrchestrationResult


# ── LangChain tools (called by deepagents) ────────────────────────────────────
def _build_tools(agent_instance: "OrchestratorAgent"):
    from langchain_core.tools import tool

    @tool
    def get_all_heartbeats() -> str:
        """Get the latest heartbeat status for every agent in the system.
        Returns a JSON array of agent heartbeats including status, error_count, and current_task."""
        try:
            heartbeats = state.get_all_heartbeats()
            if not heartbeats:
                return json.dumps({"error": "No agents reporting"})
            return json.dumps([{
                "agent_id": h.get("agent_id"),
                "status": h.get("status"),
                "error_count": h.get("error_count", 0),
                "consecutive_failures": h.get("metrics", {}).get("consecutive_failures", 0),
                "last_error": str(h.get("last_error", ""))[:150],
                "current_task": str(h.get("current_task", ""))[:100],
                "last_seen": str(h.get("last_seen", "")),
            } for h in heartbeats], indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def get_recent_audit_log(limit: int = 20) -> str:
        """Get the most recent entries from the system audit log.
        Shows actions taken by agents, outcomes (SUCCESS/FAILED/PARTIAL), and reasoning.
        Use limit to control how many entries to retrieve (default 20, max 50)."""
        try:
            limit = min(int(limit), 50)
            entries = state.get_recent_audit(limit=limit)
            return json.dumps(entries or [], indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def get_kafka_lag() -> str:
        """Get current Kafka consumer lag and DLQ status from the kafka_guardian heartbeat.
        Returns lag for supply-chain-events topic, DLQ count, and producer health."""
        try:
            heartbeats = state.get_all_heartbeats()
            for h in (heartbeats or []):
                if h.get("agent_id") == "kafka_guardian":
                    return json.dumps({
                        "status": h.get("status"),
                        "current_task": h.get("current_task", ""),
                        "metrics": h.get("metrics", {}),
                        "last_error": str(h.get("last_error", ""))[:200],
                    }, indent=2)
            return json.dumps({"error": "kafka_guardian not found in heartbeats"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def get_dagster_recent_runs(limit: int = 5) -> str:
        """Get recent Dagster pipeline run statuses.
        Shows run ID, status (SUCCESS/FAILURE/STARTED), pipeline name, and error message if failed.
        Use this to check if medallion_full_pipeline or medallion_incremental are running."""
        try:
            query = """
            {
              runsOrError(limit: %d) {
                ... on Runs {
                  results {
                    runId
                    status
                    pipelineName
                    startTime
                    endTime
                    tags { key value }
                    stats {
                      ... on RunStatsSnapshot {
                        stepsFailed
                        stepsSucceeded
                      }
                    }
                  }
                }
              }
            }
            """ % min(int(limit), 10)
            resp = requests.post(
                f"{DAGSTER_URL}/graphql",
                json={"query": query},
                timeout=10
            )
            data = resp.json().get("data", {}).get("runsOrError", {})
            return json.dumps(data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def get_mlflow_model_status() -> str:
        """Get current MLflow model status, production model metrics, and baseline comparison.
        Returns roc_auc, accuracy, train_rows for current production model vs Redis baseline."""
        try:
            r = redis.from_url(REDIS_URL, decode_responses=True)
            baseline_raw = r.get("mlflow:baseline")
            baseline = json.loads(baseline_raw) if baseline_raw else {}

            hbs = state.get_all_heartbeats()
            mlflow_hb = next((h for h in (hbs or []) if h.get("agent_id") == "mlflow_guardian"), {})

            return json.dumps({
                "redis_baseline": baseline,
                "mlflow_guardian_status": mlflow_hb.get("status"),
                "mlflow_guardian_task": mlflow_hb.get("current_task", ""),
                "mlflow_guardian_metrics": mlflow_hb.get("metrics", {}),
                "mlflow_guardian_last_error": str(mlflow_hb.get("last_error", ""))[:200],
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @tool
    def issue_correction_to_agent(agent_id: str, correction: str) -> str:
        """Issue a correction instruction to a specific agent.
        Use the exact correction patterns from the supply-chain-ops skill:
        - dagster_guardian: 'trigger incremental', 'trigger full pipeline', 'reset consecutive error counter'
        - mlflow_guardian: 'force retraining', 'reset baseline', 'trigger retraining'
        - feature_engineer: 'force regeneration', 'trigger incremental pipeline'
        - bronze_agent: 'trigger materialization'
        - silver_agent: 'trigger materialization'
        Returns confirmation of the correction being issued."""
        try:
            from agents.security import sign_correction
            state.write_correction("orchestrator", agent_id, correction, sign_correction(correction))
            communication.publish_correction(agent_id, correction)
            agent_instance.audit(
                "CORRECTION_ISSUED",
                f"deepagents orchestrator issued correction to {agent_id}: {correction}",
                "SUCCESS",
                {"target_agent": agent_id, "correction": correction}
            )
            logger.info(f"[orchestrator/deepagents] Correction → {agent_id}: {correction}")
            return json.dumps({"issued": True, "agent_id": agent_id, "correction": correction})
        except Exception as e:
            logger.error(f"[orchestrator/deepagents] Correction failed: {e}")
            return json.dumps({"issued": False, "error": str(e)})

    @tool
    def trigger_dagster_pipeline(job_name: str, reason: str) -> str:
        """Trigger a Dagster pipeline job directly.
        job_name must be exactly 'medallion_full_pipeline' or 'medallion_incremental'.
        NEVER trigger both jobs simultaneously — they share assets.
        Provide a reason string explaining why you're triggering."""
        allowed = {"medallion_full_pipeline", "medallion_incremental"}
        if job_name not in allowed:
            return json.dumps({"error": f"Invalid job_name. Must be one of: {allowed}"})
        try:
            mutation = """
            mutation LaunchRun($jobName: String!) {
              launchRun(executionParams: {
                selector: {
                  jobName: $jobName,
                  repositoryLocationName: "pipeline.definitions:defs",
                  repositoryName: "__repository__"
                },
                runConfigData: {}
              }) {
                ... on LaunchRunSuccess { run { runId status } }
                ... on PythonError { message }
                ... on InvalidSubsetError { message }
              }
            }
            """
            resp = requests.post(
                f"{DAGSTER_URL}/graphql",
                json={"query": mutation, "variables": {"jobName": job_name}},
                timeout=15
            )
            result = resp.json().get("data", {}).get("launchRun", {})
            run_id = result.get("run", {}).get("runId")
            agent_instance.audit(
                "PIPELINE_TRIGGERED",
                f"deepagents orchestrator triggered {job_name}: {reason}",
                "SUCCESS" if run_id else "FAILED",
                {"job_name": job_name, "run_id": run_id, "reason": reason}
            )
            logger.info(f"[orchestrator/deepagents] Triggered {job_name}: {run_id}")
            return json.dumps({"triggered": bool(run_id), "run_id": run_id, "job": job_name})
        except Exception as e:
            return json.dumps({"error": str(e)})

    return [
        get_all_heartbeats,
        get_recent_audit_log,
        get_kafka_lag,
        get_dagster_recent_runs,
        get_mlflow_model_status,
        issue_correction_to_agent,
        trigger_dagster_pipeline,
    ]


# ── Sub-agent definitions ─────────────────────────────────────────────────────
def _build_subagents():
    """Build specialist sub-agents for deepagents to delegate to.
    SubAgent is a TypedDict — use dict literal syntax, not keyword constructor.
    Required keys: name, description, system_prompt, model.
    """
    try:
        import deepagents  # noqa: F401
    except ImportError:
        return []

    kafka_investigator = {
        "name": "kafka_investigator",
        "description": (
            "Specialist in Kafka health. Investigates consumer lag, DLQ spikes, "
            "and producer silence. Calls get_kafka_lag and get_all_heartbeats."
        ),
        "system_prompt": (
            "You are a Kafka reliability expert for the Adopt Supply Chain AI OS. "
            "Diagnose Kafka consumer lag, DLQ growth, and producer silence. "
            "Return structured findings: dlq_count, lag, producer_age_sec, assessment, recommended_action."
        ),
        "model": HAIKU_MODEL,
    }

    dagster_investigator = {
        "name": "dagster_investigator",
        "description": (
            "Specialist in Dagster pipeline failures. Checks recent runs, "
            "identifies failed steps, recommends trigger actions."
        ),
        "system_prompt": (
            "You are a Dagster pipeline expert for the Adopt Supply Chain AI OS. "
            "Check recent runs with get_dagster_recent_runs. Identify FAILURE patterns. "
            "Never trigger both jobs simultaneously. "
            "Return: last_run_status, failed_step, error_message, recommended_action."
        ),
        "model": HAIKU_MODEL,
    }

    ml_investigator = {
        "name": "ml_investigator",
        "description": (
            "Specialist in ML model health and MLflow lifecycle. "
            "Checks model performance drift, baseline comparison, retraining status."
        ),
        "system_prompt": (
            "You are an ML model governance expert for the Adopt Supply Chain AI OS. "
            "Check MLflow status with get_mlflow_model_status. "
            "roc_auc >= 0.86 is healthy for supply chain delay prediction. "
            "A roc_auc jump after feature regeneration is EXPECTED — do not flag as anomaly. "
            "Return: current_roc_auc, baseline_roc_auc, drift_pct, assessment, recommended_action."
        ),
        "model": HAIKU_MODEL,
    }

    return [kafka_investigator, dagster_investigator, ml_investigator]


# ── Build the deepagents orchestrator ─────────────────────────────────────────
def _build_deep_agent(agent_instance: "OrchestratorAgent"):
    from deepagents import create_deep_agent  # type: ignore

    OrchestrationResult = _build_orchestration_result_model()
    tools = _build_tools(agent_instance)
    subagents = _build_subagents()

    skills_text = _load_skills_text()
    incident_memory = _load_file_safe(_INCIDENT_MEMORY_FILE)

    system_prompt = f"""You are the main orchestrator of Adopt Supply Chain AI OS — a fully autonomous 13-agent supply chain platform.

Your role:
1. Collect all agent heartbeats and identify issues
2. Detect correlated failures that suggest a single root cause (not independent problems)
3. Issue precise corrections to misdirected or stuck agents
4. Escalate to humans ONLY when systemic failure is confirmed (3+ agents cross-domain DEGRADED)

Escalation rules:
- 1 agent DEGRADED → issue correction, monitor next cycle
- 2+ agents DEGRADED (same domain) → correlated failure → investigate root cause first
- 3+ agents DEGRADED (cross-domain) → systemic → human_intervention_needed=True
- All agents offline → human_intervention_needed=True immediately

Correction patterns (use exactly):
- dagster_guardian: "trigger incremental" | "trigger full pipeline" | "reset consecutive error counter"
- mlflow_guardian: "force retraining" | "reset baseline" | "trigger retraining"
- feature_engineer: "force regeneration" | "trigger incremental pipeline"
- bronze_agent / silver_agent: "trigger materialization"

---
## DOMAIN KNOWLEDGE (Skills)
{skills_text}

---
## INCIDENT PATTERN MEMORY
{incident_memory}
"""

    # Bug 20: memory expects file content string, not a file path list.
    # Read the file and pass its content via system_prompt (already included above).
    # Pass None for memory to avoid incorrect path-string passing.
    graph = create_deep_agent(
        model=SONNET_MODEL,
        tools=tools,
        subagents=subagents if subagents else None,
        response_format=OrchestrationResult,
        memory=None,
        system_prompt=system_prompt,
    )
    return graph, OrchestrationResult


class OrchestratorAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="orchestrator",
            model=SONNET_MODEL,
            interval_seconds=300,
            description="Main orchestrator. Collects all agent status, detects drift, issues corrections."
        )
        self._alert_queue = []
        self._alert_lock = threading.Lock()
        self._start_alert_listener()

        # deepagents graph — built lazily on first use
        self._deep_graph = None
        self._OrchestrationResult = None
        self._use_deepagents = _deepagents_available()

        if self._use_deepagents:
            logger.info("[orchestrator] deepagents available — will use structured LangGraph orchestration")
        else:
            logger.warning("[orchestrator] deepagents not available — using legacy Anthropic SDK fallback")

    def _start_alert_listener(self):
        """Background thread subscribing to Redis agent:alerts channel."""
        def listen():
            while not _global_shutdown.is_set():
                try:
                    r = redis.from_url(REDIS_URL, decode_responses=True)
                    pubsub = r.pubsub()
                    pubsub.subscribe("agent:alerts")
                    logger.info("[orchestrator] Alert listener started")
                    for msg in pubsub.listen():
                        if _global_shutdown.is_set():
                            break
                        if msg["type"] == "message":
                            try:
                                data = json.loads(msg["data"])
                                # Bug 10: listener must also hold the lock when appending
                                with self._alert_lock:
                                    self._alert_queue.append(data)
                                    if data.get("severity") == "CRITICAL":
                                        logger.warning(
                                            f"[orchestrator] CRITICAL alert from "
                                            f"{data.get('agent_id')}: {data.get('message')}"
                                        )
                            except Exception:
                                pass
                except Exception as e:
                    logger.debug(f"Alert listener error: {e}")
                    time.sleep(5)

        t = threading.Thread(target=listen, daemon=True, name="orchestrator-alert-listener")
        t.start()

    def check(self) -> dict:
        metrics = {}

        # Drain alert queue
        with self._alert_lock:
            pending_alerts = list(self._alert_queue)
            self._alert_queue.clear()

        metrics["pending_alerts"] = len(pending_alerts)

        # Get all heartbeats
        heartbeats = state.get_all_heartbeats()
        if not heartbeats:
            return {"task": "no_agents_reporting", "heartbeats": 0}

        hb_map = {h["agent_id"]: h for h in heartbeats}
        metrics["agents_reporting"] = len(hb_map)

        # Detect offline agents (no heartbeat for >3min)
        offline_agents = []
        for agent_id, hb in hb_map.items():
            last_seen_str = str(hb.get("last_seen", ""))
            if last_seen_str:
                try:
                    # Bug 2: use dateutil.parser or datetime.fromisoformat with proper tz handling
                    from datetime import datetime, timezone
                    try:
                        from dateutil import parser as _dtparser
                        last_seen = _dtparser.parse(last_seen_str)
                        if last_seen.tzinfo is None:
                            last_seen = last_seen.replace(tzinfo=timezone.utc)
                        now_utc = datetime.now(timezone.utc)
                    except ImportError:
                        # fallback: strip tz suffix and use utcnow
                        _s = last_seen_str
                        for suffix in ("+00:00", "Z", "+0000"):
                            _s = _s.replace(suffix, "")
                        _s = _s.replace("T", " ").split(".")[0].strip()
                        last_seen = datetime.fromisoformat(_s)
                        now_utc = datetime.utcnow()
                    age_sec = (now_utc - last_seen.replace(tzinfo=None) if last_seen.tzinfo is None
                               else (now_utc - last_seen)).total_seconds()
                    if age_sec > 300 and hb.get("status") not in ("OFFLINE",):
                        offline_agents.append({"agent": agent_id, "age_sec": age_sec})
                except Exception:
                    pass

        metrics["offline_agents"] = len(offline_agents)

        # Detect correlated failures
        degraded = [aid for aid, h in hb_map.items() if h.get("status") in ("DEGRADED", "CRITICAL")]
        metrics["degraded_agents"] = len(degraded)

        # Only invoke LLM when there's something that needs reasoning
        needs_reasoning = (
            len(pending_alerts) > 0
            or len(offline_agents) > 0
            or len(degraded) >= 2
            or any(a.get("severity") in ("CRITICAL", "HIGH") for a in pending_alerts)
        )

        if needs_reasoning:
            if self._use_deepagents:
                self._orchestrate_with_deepagents(heartbeats, pending_alerts, offline_agents, degraded)
            else:
                self._orchestrate_with_llm(heartbeats, pending_alerts, offline_agents, degraded)

        metrics["task"] = (
            f"agents={len(hb_map)}|alerts={len(pending_alerts)}"
            f"|degraded={len(degraded)}|offline={len(offline_agents)}"
        )
        return metrics

    # ── deepagents path ────────────────────────────────────────────────────────
    def _orchestrate_with_deepagents(self, heartbeats, alerts, offline_agents, degraded_agents):
        """Use deepagents LangGraph to analyze cross-agent patterns and issue corrections."""
        try:
            # Build graph lazily
            if self._deep_graph is None:
                self._deep_graph, self._OrchestrationResult = _build_deep_agent(self)
                logger.info("[orchestrator] deepagents graph compiled")

            # Compose the input message
            hb_summary = {h["agent_id"]: {
                "status": h.get("status"),
                "error_count": h.get("error_count", 0),
                # Bug 29: increase heartbeat context truncation from 120 to 500 chars
                "last_error": str(h.get("last_error", ""))[:500],
                "current_task": str(h.get("current_task", ""))[:80],
            } for h in heartbeats}

            alerts_summary = [
                {
                    "from": a.get("agent_id"),
                    "severity": a.get("severity"),
                    "message": str(a.get("message", ""))[:150],
                }
                for a in alerts[:10]
            ]

            user_message = (
                f"SYSTEM STATE SNAPSHOT:\n"
                f"Agent heartbeats: {json.dumps(hb_summary)}\n"
                f"Recent alerts: {json.dumps(alerts_summary)}\n"
                f"Offline agents: {offline_agents}\n"
                f"Degraded agents: {degraded_agents}\n\n"
                "Analyze the system state. Use your tools to investigate further if needed. "
                "Issue corrections to any misdirected or stuck agents. "
                "Return a structured OrchestrationResult."
            )

            result = self._deep_graph.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config={"configurable": {"thread_id": "orchestrator-main"}},
            )

            # Extract structured response
            # deepagents returns the Pydantic model in the last message or as a structured output
            structured = None
            if hasattr(result, "get"):
                messages = result.get("messages", [])
                for msg in reversed(messages):
                    if hasattr(msg, "content") and isinstance(msg.content, self._OrchestrationResult):
                        structured = msg.content
                        break
                    if hasattr(msg, "additional_kwargs"):
                        tool_calls = msg.additional_kwargs.get("tool_calls", [])
                        for tc in tool_calls:
                            if tc.get("name") == "OrchestrationResult":
                                try:
                                    structured = self._OrchestrationResult(
                                        **json.loads(tc["args"])
                                    )
                                except Exception:
                                    pass
                # Fallback: look for structured_response key
                if structured is None and "structured_response" in result:
                    raw = result["structured_response"]
                    if isinstance(raw, self._OrchestrationResult):
                        structured = raw
                    elif isinstance(raw, dict):
                        try:
                            structured = self._OrchestrationResult(**raw)
                        except Exception:
                            pass

            if structured is None:
                # Try parsing from the last text message if structured extraction failed
                logger.warning("[orchestrator] deepagents structured output not found, attempting text parse")
                self._parse_and_apply_text_result(result)
                return

            # Apply corrections from structured result
            from agents.security import sign_correction as _sign
            corrections_issued = 0
            for corr in (structured.corrections or []):
                agent_id = corr.agent_id
                message = corr.correction
                if agent_id and message:
                    state.write_correction("orchestrator", agent_id, message, _sign(message))
                    communication.publish_correction(agent_id, message)
                    corrections_issued += 1
                    logger.info(f"[orchestrator/deepagents] Correction → {agent_id}: {message}")

            logger.info(f"[orchestrator/deepagents] Summary: {structured.summary}")
            logger.info(f"[orchestrator/deepagents] Root cause: {structured.root_cause_analysis[:200]}")
            logger.info(f"[orchestrator/deepagents] Confidence: {structured.confidence}")

            if structured.human_intervention_needed:
                logger.critical("[orchestrator] HUMAN INTERVENTION REQUIRED — see audit log")
                self.alert(
                    "CRITICAL",
                    f"Human intervention needed: {structured.summary}",
                    {
                        "root_cause": structured.root_cause_analysis,
                        "correlations": structured.correlations,
                    }
                )

            self.audit(
                "ORCHESTRATION_CYCLE",
                structured.root_cause_analysis,
                "SUCCESS",
                {
                    "engine": "deepagents",
                    "corrections_issued": corrections_issued,
                    "summary": structured.summary,
                    "confidence": structured.confidence,
                    "human_needed": structured.human_intervention_needed,
                    "correlations": structured.correlations,
                }
            )

        except Exception as e:
            logger.error(f"[orchestrator] deepagents orchestration failed: {e}", exc_info=True)
            # Gracefully fall back to legacy
            logger.info("[orchestrator] Falling back to legacy LLM orchestration")
            self._orchestrate_with_llm(heartbeats, alerts, offline_agents, degraded_agents)

    def _parse_and_apply_text_result(self, result):
        """Fallback: try to extract JSON from a deepagents text result."""
        try:
            import re
            text = ""
            if hasattr(result, "get"):
                messages = result.get("messages", [])
                for msg in reversed(messages):
                    content = getattr(msg, "content", "")
                    if isinstance(content, str) and len(content) > 20:
                        text = content
                        break
            if not text:
                return
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                from agents.security import sign_correction as _sign
                parsed = json.loads(json_match.group())
                for corr in parsed.get("corrections", []):
                    agent_id = corr.get("agent_id")
                    message = corr.get("correction", "")
                    if agent_id and message:
                        state.write_correction("orchestrator", agent_id, message, _sign(message))
                        communication.publish_correction(agent_id, message)
                        logger.info(f"[orchestrator/fallback] Correction → {agent_id}: {message}")
                self.audit("ORCHESTRATION_CYCLE", parsed.get("root_cause_analysis", text[:300]), "PARTIAL",
                           {"engine": "deepagents-text-fallback"})
        except Exception as e:
            logger.warning(f"[orchestrator] Text parse fallback failed: {e}")
            self.audit("ORCHESTRATION_CYCLE", "Text parse fallback failed", "PARTIAL")

    # ── Legacy Anthropic SDK path (fallback) ──────────────────────────────────
    def _orchestrate_with_llm(self, heartbeats, alerts, offline_agents, degraded_agents):
        """Legacy fallback: direct Anthropic SDK call with regex JSON parsing."""
        try:
            hb_summary = {h["agent_id"]: {
                "status": h.get("status"),
                "error_count": h.get("error_count", 0),
                "last_error": str(h.get("last_error", ""))[:100],
                "current_task": str(h.get("current_task", ""))[:80],
                "metrics": h.get("metrics", {})
            } for h in heartbeats}

            alerts_summary = [
                {"from": a.get("agent_id"), "severity": a.get("severity"),
                 "message": str(a.get("message", ""))[:150]}
                for a in alerts[:10]
            ]

            skills_text = _load_skills_text()
            incident_memory = _load_file_safe(_INCIDENT_MEMORY_FILE)

            system_prompt = f"""You are the main orchestrator of Adopt Supply Chain AI OS.
Manage 13 specialized agents and issue corrections.

{skills_text}

INCIDENT PATTERNS:
{incident_memory[:2000]}

Respond with a JSON object:
{{
  "root_cause_analysis": "...",
  "correlations": ["..."],
  "corrections": [{{"agent_id": "...", "correction": "..."}}],
  "human_intervention_needed": false,
  "summary": "..."
}}"""

            user_message = (
                f"AGENT HEARTBEATS: {json.dumps(hb_summary, indent=2)}\n"
                f"RECENT ALERTS: {json.dumps(alerts_summary, indent=2)}\n"
                f"OFFLINE AGENTS: {offline_agents}\n"
                f"DEGRADED AGENTS: {degraded_agents}\n\n"
                "Analyze and respond with corrections JSON."
            )

            result_text = self.analyze_with_llm(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=1024
            )

            import re
            from agents.security import sign_correction as _sign
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                corrections = result.get("corrections", [])
                for corr in corrections:
                    agent_id = corr.get("agent_id")
                    message = corr.get("correction", "")
                    if agent_id and message:
                        state.write_correction("orchestrator", agent_id, message, _sign(message))
                        communication.publish_correction(agent_id, message)
                        logger.info(f"[orchestrator/legacy] Correction → {agent_id}: {message}")

                summary = result.get("summary", "")
                logger.info(f"[orchestrator/legacy] Summary: {summary}")

                if result.get("human_intervention_needed"):
                    logger.critical("[orchestrator] HUMAN INTERVENTION REQUIRED")

                self.audit("ORCHESTRATION_CYCLE", result.get("root_cause_analysis", ""), "SUCCESS",
                           {"engine": "legacy-sdk",
                            "corrections_issued": len(corrections),
                            "summary": summary,
                            "human_needed": result.get("human_intervention_needed", False)})
            else:
                logger.warning(f"[orchestrator/legacy] Non-JSON LLM response: {result_text[:200]}")
                self.audit("ORCHESTRATION_CYCLE", result_text[:500], "PARTIAL", {"engine": "legacy-sdk"})

        except Exception as e:
            logger.error(f"[orchestrator] Legacy LLM orchestration failed: {e}")
            self.audit("ORCHESTRATION_CYCLE", str(e), "FAILED")

    def heal(self, error: Exception) -> bool:
        """Orchestrator must never die — always heal."""
        logger.warning(f"[orchestrator] Healing error: {error}")
        # Reset deepagents graph on failure so it's rebuilt fresh
        self._deep_graph = None
        time.sleep(10)
        return True
