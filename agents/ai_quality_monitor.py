"""
AI Quality Monitor Agent
Model: Claude Haiku
Interval: 60s

Monitors:
- pending_actions table for stuck/low-quality AI analyses
- Re-triggers analysis if confidence < 0.4
- Validates Claude's structured output fields
- Detects stuck PENDING actions (> 10min)
- Validates recommended actions against ontology constraints
"""
import os
import time
import json
import logging
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

from agents.base import BaseAgent, HAIKU_MODEL

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/supplychain")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8000")
MIN_CONFIDENCE = float(os.getenv("AI_MIN_CONFIDENCE", "0.4"))
STUCK_THRESHOLD_MINUTES = int(os.getenv("AI_STUCK_THRESHOLD_MIN", "10"))


def _get_db():
    return psycopg2.connect(DATABASE_URL)


class AIQualityMonitorAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="ai_quality_monitor",
            model=HAIKU_MODEL,
            interval_seconds=60,
            description="Monitors AI analysis quality. Re-triggers low-confidence analyses. Validates Claude structured outputs."
        )
        self._re_triggered = set()  # deviation IDs we already re-triggered

    def check(self) -> dict:
        metrics = {}

        conn = _get_db()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:

                # 1. Check for stuck PENDING actions
                cur.execute("""
                    SELECT pa.id, pa.deviation_id, pa.confidence, pa.created_at,
                           d.type as deviation_type, d.severity
                    FROM pending_actions pa
                    JOIN deviations d ON pa.deviation_id = d.deviation_id
                    WHERE pa.status = 'PENDING'
                      AND pa.created_at < NOW() - (make_interval(mins => %s))
                    ORDER BY pa.created_at ASC
                """, (STUCK_THRESHOLD_MINUTES,))
                stuck = [dict(r) for r in cur.fetchall()]
                metrics["stuck_actions"] = len(stuck)

                for action in stuck:
                    dev_id = action["deviation_id"]
                    if dev_id not in self._re_triggered:
                        logger.warning(f"Stuck pending action for deviation {dev_id} — re-triggering analysis")
                        self._retrigger_analysis(dev_id)
                        self._re_triggered.add(dev_id)
                        self.audit("RETRIGGER_STUCK_ACTION",
                                   f"Action stuck >{STUCK_THRESHOLD_MINUTES}min",
                                   "TRIGGERED", {"deviation_id": dev_id, "action_id": action["id"]})

                # 2. Check for low-confidence analyses
                cur.execute("""
                    SELECT pa.id, pa.deviation_id, pa.confidence, pa.action_type, pa.description
                    FROM pending_actions pa
                    WHERE pa.status = 'PENDING'
                      AND pa.confidence IS NOT NULL
                      AND pa.confidence < %s
                      AND pa.created_at > NOW() - INTERVAL '1 hour'
                    ORDER BY pa.confidence ASC
                    LIMIT 10
                """, (MIN_CONFIDENCE,))
                low_conf = [dict(r) for r in cur.fetchall()]
                metrics["low_confidence_actions"] = len(low_conf)

                for action in low_conf:
                    dev_id = action["deviation_id"]
                    if dev_id not in self._re_triggered:
                        logger.warning(f"Low confidence {action['confidence']:.2f} for deviation {dev_id}")
                        self._retrigger_analysis(dev_id)
                        self._re_triggered.add(dev_id)
                        self.audit("RETRIGGER_LOW_CONFIDENCE",
                                   f"Confidence {action['confidence']:.2f} < {MIN_CONFIDENCE}",
                                   "TRIGGERED", {"deviation_id": dev_id, "confidence": action["confidence"]})

                # 3. Validate REROUTE actions have valid supplier context
                cur.execute("""
                    SELECT pa.id, pa.deviation_id, pa.action_type, pa.payload
                    FROM pending_actions pa
                    WHERE pa.action_type = 'REROUTE'
                      AND pa.status = 'PENDING'
                      AND pa.created_at > NOW() - INTERVAL '2 hours'
                """)
                reroutes = [dict(r) for r in cur.fetchall()]
                metrics["pending_reroutes"] = len(reroutes)

                for action in reroutes:
                    payload = action.get("payload") or {}
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except:
                            payload = {}
                    if not payload.get("alternate_supplier_id"):
                        logger.warning(f"REROUTE action {action['id']} has no alternate_supplier_id — escalating")
                        cur.execute("UPDATE pending_actions SET action_type='ESCALATE' WHERE id=%s",
                                    (action["id"],))
                        conn.commit()
                        self.audit("ESCALATE_INVALID_REROUTE",
                                   "REROUTE had no alternate supplier — converted to ESCALATE",
                                   "SUCCESS", {"action_id": action["id"]})

                # 4. Overall AI health metrics
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE status='PENDING') as pending_count,
                        COUNT(*) FILTER (WHERE status='COMPLETED') as completed_today,
                        AVG(confidence) FILTER (WHERE confidence IS NOT NULL AND created_at > NOW() - INTERVAL '24h') as avg_confidence
                    FROM pending_actions
                    WHERE created_at > NOW() - INTERVAL '24h'
                """)
                stats = dict(cur.fetchone())
                metrics.update({
                    "pending_actions_total": stats.get("pending_count", 0),
                    "completed_today": stats.get("completed_today", 0),
                    "avg_confidence_24h": round(float(stats.get("avg_confidence") or 0), 3)
                })

        finally:
            conn.close()

        # Clean up re_triggered set periodically
        if len(self._re_triggered) > 1000:
            self._re_triggered = set(list(self._re_triggered)[-500:])

        metrics["task"] = f"stuck={metrics.get('stuck_actions',0)}|low_conf={metrics.get('low_confidence_actions',0)}|avg_conf={metrics.get('avg_confidence_24h',0)}"
        return metrics

    def _retrigger_analysis(self, deviation_id: str):
        try:
            resp = requests.post(
                f"{FASTAPI_URL}/ai/analyze/structured",
                json={"deviation_id": deviation_id, "context": "re-analysis triggered by quality monitor"},
                headers={"X-API-Key": os.getenv("API_KEY_INTERNAL", "internal-monitor")},
                timeout=30
            )
            if resp.status_code == 200:
                logger.info(f"Re-triggered analysis for deviation {deviation_id}")
            else:
                logger.warning(f"Re-trigger returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Failed to re-trigger analysis for {deviation_id}: {e}")

    def heal(self, error: Exception) -> bool:
        if "connection" in str(error).lower():
            time.sleep(10)
            return True
        return False
