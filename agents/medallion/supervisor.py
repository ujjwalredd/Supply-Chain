"""
Medallion Supervisor
Model: Claude Haiku
Interval: 180s (3min)

Coordinates the Bronze -> Silver -> Gold pipeline agents.
Enforces data contract: Silver cannot run if Bronze is unhealthy.
Gold cannot run if Silver is unhealthy.
Reports combined medallion status to orchestrator.
"""
import os
import logging
import time
import threading

from agents.base import BaseAgent, HAIKU_MODEL
from agents.medallion.bronze import BronzeAgent
from agents.medallion.silver import SilverAgent
from agents.medallion.gold import GoldAgent
from agents import state

logger = logging.getLogger(__name__)


class MedallionSupervisor(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="medallion_supervisor",
            model=HAIKU_MODEL,
            interval_seconds=180,
            description="Coordinates Bronze/Silver/Gold agents. Enforces data contracts."
        )
        self._layer_status = {"bronze": "UNKNOWN", "silver": "UNKNOWN", "gold": "UNKNOWN"}

    def check(self) -> dict:
        """Collect status from all layer agents and enforce contracts."""
        heartbeats = state.get_all_heartbeats()
        hb_map = {h["agent_id"]: h for h in (heartbeats or [])}

        bronze_hb = hb_map.get("bronze_agent", {})
        silver_hb = hb_map.get("silver_agent", {})
        gold_hb = hb_map.get("gold_agent", {})

        bronze_status = bronze_hb.get("status", "UNKNOWN")
        silver_status = silver_hb.get("status", "UNKNOWN")
        gold_status = gold_hb.get("status", "UNKNOWN")

        self._layer_status = {
            "bronze": bronze_status,
            "silver": silver_status,
            "gold": gold_status
        }

        # Data contract enforcement
        issues = []

        if bronze_status == "CRITICAL" and silver_status in ("HEALTHY", "DEGRADED"):
            issues.append("Bronze is CRITICAL but Silver is running — data contract violation risk")
            self.alert("HIGH", "Medallion contract violation: Bronze CRITICAL, Silver still active",
                       self._layer_status)

        if silver_status == "CRITICAL" and gold_status in ("HEALTHY", "DEGRADED"):
            issues.append("Silver is CRITICAL but Gold is running — financial data may be corrupted")
            self.alert("CRITICAL", "Medallion contract violation: Silver CRITICAL, Gold still active",
                       self._layer_status)

        # Check for offline agents
        for layer, hb in [("bronze", bronze_hb), ("silver", silver_hb), ("gold", gold_hb)]:
            last_seen = hb.get("last_seen")
            agent_id = f"{layer}_agent"
            if not last_seen:
                issues.append(f"{layer} agent has never reported — may not be running")
                # Bug 28: include agent_id in the alert payload (it was built but unused)
                self.alert("HIGH", f"{agent_id} has no heartbeat", {"layer": layer, "agent_id": agent_id})

        if issues:
            logger.warning(f"Medallion supervisor issues: {issues}")
            self.audit("MEDALLION_CONTRACT_CHECK", str(issues), "ALERT",
                       {"layer_status": self._layer_status})

        return {
            "layer_status": self._layer_status,
            "issues": len(issues),
            "task": f"bronze={bronze_status}|silver={silver_status}|gold={gold_status}"
        }

    def heal(self, error: Exception) -> bool:
        return True  # Supervisor itself should always stay up
