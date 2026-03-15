"""
Main Orchestrator Agent
Model: Claude Sonnet 4.6 (triggered only on anomaly — not constant polling)
Interval: 300s (5min) for routine collection
         Immediate on CRITICAL alerts via Redis

Responsibilities:
1. Collect all agent heartbeats every 5min
2. Detect drift (agent investigating wrong thing)
3. Detect correlated failures across multiple agents
4. Issue corrections to misdirected agents
5. Use Sonnet ONLY when drift detected or CRITICAL escalation received
"""
import os
import json
import time
import logging
import threading
import redis

from agents.base import BaseAgent, SONNET_MODEL, _global_shutdown
from agents import state, communication

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class OrchestratorAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="orchestrator",
            model=SONNET_MODEL,
            interval_seconds=300,
            description="Main orchestrator. Collects all agent status, detects drift, issues corrections using Claude Sonnet."
        )
        self._alert_queue = []
        self._alert_lock = threading.Lock()
        self._start_alert_listener()

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
                                with self._alert_lock:
                                    self._alert_queue.append(data)
                                    if data.get("severity") == "CRITICAL":
                                        logger.warning(f"[orchestrator] CRITICAL alert from {data.get('agent_id')}: {data.get('message')}")
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
                    from datetime import datetime, timezone
                    if last_seen_str.endswith("+00:00"):
                        last_seen_str = last_seen_str[:-6]
                    last_seen = datetime.fromisoformat(last_seen_str.replace("T", " ").split(".")[0])
                    age_sec = (datetime.utcnow() - last_seen).total_seconds()
                    if age_sec > 300 and hb.get("status") not in ("OFFLINE",):
                        offline_agents.append({"agent": agent_id, "age_sec": age_sec})
                except Exception:
                    pass

        metrics["offline_agents"] = len(offline_agents)

        # Detect correlated failures
        degraded = [aid for aid, h in hb_map.items() if h.get("status") in ("DEGRADED", "CRITICAL")]
        metrics["degraded_agents"] = len(degraded)

        # Only call Sonnet if there's something that needs reasoning
        needs_reasoning = (
            len(pending_alerts) > 0 or
            len(offline_agents) > 0 or
            len(degraded) >= 3 or
            any(a.get("severity") == "CRITICAL" for a in pending_alerts)
        )

        if needs_reasoning:
            self._orchestrate_with_llm(heartbeats, pending_alerts, offline_agents, degraded)

        metrics["task"] = f"agents={len(hb_map)}|alerts={len(pending_alerts)}|degraded={len(degraded)}|offline={len(offline_agents)}"
        return metrics

    def _orchestrate_with_llm(self, heartbeats, alerts, offline_agents, degraded_agents):
        """Use Claude Sonnet to analyze cross-agent patterns and issue corrections."""
        try:
            # Summarize system state compactly for LLM
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

            system_prompt = """You are the main orchestrator of an autonomous supply chain AI system.
You manage these specialized agents:
- kafka_guardian: monitors Kafka consumer lag, DLQ, producer heartbeat
- bronze_agent: validates Bronze parquet layer
- silver_agent: validates Silver parquet layer (dedup, nulls, constraints)
- gold_agent: validates Gold layer financial formulas and ML outputs
- medallion_supervisor: coordinates Bronze/Silver/Gold agents
- dagster_guardian: monitors Dagster pipeline runs and schedules
- ai_quality_monitor: validates Claude AI output quality in pending_actions
- database_health: monitors PostgreSQL health

Your job:
1. Identify if any agent is investigating the wrong thing (drift)
2. Identify correlated failures that suggest a single root cause
3. Issue specific corrections to misdirected agents
4. Determine if human intervention is needed

You must respond with a JSON object with this schema:
{
  "root_cause_analysis": "string — what is likely causing the issues",
  "correlations": ["list of correlated agent failures"],
  "corrections": [{"agent_id": "...", "correction": "specific instruction"}],
  "human_intervention_needed": false,
  "summary": "one line summary"
}"""

            user_message = f"""System state:
AGENT HEARTBEATS: {json.dumps(hb_summary, indent=2)}
RECENT ALERTS: {json.dumps(alerts_summary, indent=2)}
OFFLINE AGENTS: {offline_agents}
DEGRADED AGENTS: {degraded_agents}

Analyze and respond with corrections."""

            result_text = self.analyze_with_llm(
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=1024
            )

            # Parse and apply corrections
            try:
                # Extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())

                    corrections = result.get("corrections", [])
                    for corr in corrections:
                        agent_id = corr.get("agent_id")
                        message = corr.get("correction", "")
                        if agent_id and message:
                            state.write_correction("orchestrator", agent_id, message)
                            communication.publish_correction(agent_id, message)
                            logger.info(f"[orchestrator] Correction issued to {agent_id}: {message}")

                    summary = result.get("summary", "")
                    logger.info(f"[orchestrator] Analysis: {summary}")
                    logger.info(f"[orchestrator] Root cause: {result.get('root_cause_analysis', '')[:200]}")

                    if result.get("human_intervention_needed"):
                        logger.critical("[orchestrator] HUMAN INTERVENTION REQUIRED — see audit log")

                    self.audit("ORCHESTRATION_CYCLE",
                               result.get("root_cause_analysis", ""),
                               "SUCCESS",
                               {"corrections_issued": len(corrections),
                                "summary": summary,
                                "human_needed": result.get("human_intervention_needed", False)})
            except json.JSONDecodeError:
                logger.warning(f"Orchestrator LLM response was not valid JSON: {result_text[:200]}")
                self.audit("ORCHESTRATION_CYCLE", result_text[:500], "PARTIAL")

        except Exception as e:
            logger.error(f"[orchestrator] LLM orchestration failed: {e}")
            self.audit("ORCHESTRATION_CYCLE", str(e), "FAILED")

    def heal(self, error: Exception) -> bool:
        # Orchestrator must never die — always heal
        logger.warning(f"[orchestrator] Healing error: {error}")
        time.sleep(10)
        return True
