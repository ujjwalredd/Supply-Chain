"""
Action Executor — auto-execute or escalate AI-recommended supply chain actions.

Supports four action types that mirror Auger's autonomous execution model:
  REROUTE       — switch to an alternate high-trust supplier in the same region
  EXPEDITE      — notify ops team via Slack (or log) to fast-track shipment
  SAFETY_STOCK  — publish a procurement event to Kafka to trigger replenishment
  NOTIFY        — send alert without changing operational state
  ESCALATE      — structured decision package for human review (no auto-exec)

Called by:
  - pg_writer background thread (CRITICAL deviations, autonomous_executable=True)
  - POST /actions/{id}/execute  (manual operator trigger)
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
PROCUREMENT_TOPIC = os.getenv("PROCUREMENT_TOPIC", "supply-chain-procurement")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:3000")

# Minimum confidence required for autonomous execution.
# Increase toward 1.0 for a stricter glass-box gate; lower toward 0.0 to run
# autonomously on lower-confidence recommendations.
AUTONOMY_CONFIDENCE_THRESHOLD = float(os.getenv("AUTONOMY_CONFIDENCE_THRESHOLD", "0.70"))


class ActionExecutor:
    """
    Dispatch and execute PendingActions against live operational state.

    Usage:
        executor = ActionExecutor(session)
        success = executor.execute(action)
        if success:
            session.commit()
    """

    def __init__(self, session):
        self.session = session

    def execute(self, action) -> bool:
        """Dispatch to the correct handler. Returns True on success."""
        from datetime import datetime, timezone

        handlers = {
            "REROUTE": self._handle_reroute,
            "EXPEDITE": self._handle_expedite,
            "SAFETY_STOCK": self._handle_safety_stock,
            "NOTIFY": self._handle_notify,
            "ESCALATE": self._handle_escalate,
        }
        handler = handlers.get(action.action_type)
        if not handler:
            logger.warning("No executor for action_type=%s", action.action_type)
            return False

        # Confidence gate: ESCALATE actions bypass this check (they are human-review only)
        if action.action_type != "ESCALATE":
            payload_confidence = float((action.payload or {}).get("execution_confidence", 1.0))
            if payload_confidence < AUTONOMY_CONFIDENCE_THRESHOLD:
                logger.warning(
                    "Action id=%s blocked by confidence gate: %.2f < %.2f (threshold). "
                    "Promoting to ESCALATE.",
                    action.id, payload_confidence, AUTONOMY_CONFIDENCE_THRESHOLD,
                )
                action.action_type = "ESCALATE"
                action.description = (
                    f"[Confidence gate: {payload_confidence:.0%} < {AUTONOMY_CONFIDENCE_THRESHOLD:.0%}] "
                    + action.description
                )
                handler = self._handle_escalate

        try:
            handler(action)
            action.status = "COMPLETED"
            action.completed_at = datetime.now(timezone.utc)
            logger.info(
                "Action executed: id=%s type=%s deviation=%s",
                action.id, action.action_type, action.deviation_id,
            )
            return True
        except Exception as e:
            logger.exception(
                "Action execution failed (id=%s type=%s): %s",
                action.id, action.action_type, e,
            )
            return False

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _handle_reroute(self, action) -> None:
        """Switch order to the best alternate supplier in the same region."""
        from sqlalchemy import select
        from api.models import Deviation, Order, Supplier

        dev = self.session.execute(
            select(Deviation).where(Deviation.deviation_id == action.deviation_id)
        ).scalar_one_or_none()
        if not dev:
            logger.warning("REROUTE: deviation %s not found", action.deviation_id)
            return

        order = self.session.execute(
            select(Order).where(Order.order_id == dev.order_id)
        ).scalar_one_or_none()
        if not order:
            logger.warning("REROUTE: order for deviation %s not found", action.deviation_id)
            return

        alt = self.session.execute(
            select(Supplier)
            .where(Supplier.region == order.region)
            .where(Supplier.supplier_id != order.supplier_id)
            .where(Supplier.trust_score >= 0.80)
            .order_by(Supplier.trust_score.desc())
            .limit(1)
        ).scalar_one_or_none()

        if alt:
            old_sup = order.supplier_id
            order.supplier_id = alt.supplier_id
            order.status = "IN_TRANSIT"
            action.payload = {
                **(action.payload or {}),
                "executed_reroute": {
                    "from_supplier": old_sup,
                    "to_supplier": alt.supplier_id,
                    "alt_trust_score": round(alt.trust_score, 3),
                    "region": order.region,
                },
            }
            logger.info(
                "REROUTE: order %s → supplier %s (trust=%.2f, region=%s)",
                order.order_id, alt.supplier_id, alt.trust_score, order.region,
            )
            _send_slack(
                f"AUTO-REROUTE EXECUTED\n"
                f"Order: {order.order_id}\n"
                f"From: {old_sup} → To: {alt.supplier_id} (trust {alt.trust_score:.0%})\n"
                f"Region: {order.region}"
            )
        else:
            logger.warning(
                "REROUTE: no eligible alternate supplier for order %s (region=%s)",
                order.order_id, order.region,
            )
            _send_slack(
                f"REROUTE FAILED — no alternate supplier (region={order.region})\n"
                f"Order {order.order_id} requires manual action."
            )

    def _handle_expedite(self, action) -> None:
        """Notify ops team to expedite the shipment."""
        payload = action.payload or {}
        _send_slack(
            f"EXPEDITE REQUEST\n"
            f"Deviation: {action.deviation_id}\n"
            f"Action: {action.description}\n"
            f"Severity: {payload.get('severity', 'UNKNOWN')}\n"
            f"Financial Impact: ${payload.get('financial_impact_usd', 0):,.0f}\n"
            f"Dashboard: {DASHBOARD_URL}/alerts"
        )
        logger.info("EXPEDITE: notification sent for deviation %s", action.deviation_id)

    def _handle_safety_stock(self, action) -> None:
        """Publish a procurement event to Kafka to trigger replenishment."""
        payload = action.payload or {}
        event = {
            "event_type": "SAFETY_STOCK_TRIGGER",
            "deviation_id": action.deviation_id,
            "description": action.description,
            "severity": payload.get("severity"),
            "product": payload.get("product"),
            "recommended_quantity": payload.get("recommended_quantity", 100),
            "financial_impact_usd": payload.get("financial_impact_usd", 0),
        }
        _publish_kafka(PROCUREMENT_TOPIC, event)
        logger.info(
            "SAFETY_STOCK: procurement event published for deviation %s",
            action.deviation_id,
        )

    def _handle_notify(self, action) -> None:
        """Send alert notification without changing operational state."""
        payload = action.payload or {}
        _send_slack(
            f"SUPPLY CHAIN ALERT\n"
            f"Type: {payload.get('deviation_type', 'UNKNOWN')}\n"
            f"Severity: {payload.get('severity', 'UNKNOWN')}\n"
            f"Action: {action.description}\n"
            f"Dashboard: {DASHBOARD_URL}/alerts"
        )
        logger.info("NOTIFY: sent for deviation %s", action.deviation_id)

    def _handle_escalate(self, action) -> None:
        """Log and alert escalation package — human review required, no auto-exec."""
        payload = action.payload or {}
        confidence = payload.get("confidence", 0.0)
        impact = payload.get("financial_impact_usd", 0)
        _send_slack(
            f"ESCALATION REQUIRED — Human Review Needed\n"
            f"Deviation: {action.deviation_id}\n"
            f"Confidence: {confidence:.0%}  |  Impact: ${impact:,.0f}\n"
            f"Recommendation: {action.description}\n"
            f"Review: {DASHBOARD_URL}/alerts"
        )
        logger.warning(
            "ESCALATE: human review for deviation=%s confidence=%.2f impact=$%.0f",
            action.deviation_id, confidence, impact,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _send_slack(message: str) -> None:
    """Send Slack webhook notification. Falls back to INFO log when not configured."""
    if not SLACK_WEBHOOK_URL:
        logger.info("SLACK (not configured): %s", message[:300])
        return
    try:
        import urllib.request
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.warning("Slack notification failed: %s", e)


def _publish_kafka(topic: str, event: dict) -> None:
    """Publish a single event to a Kafka topic."""
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        producer.send(topic, value=event)
        producer.flush(timeout=5)
        producer.close()
    except Exception as e:
        logger.warning("Kafka publish failed (topic=%s): %s", topic, e)
