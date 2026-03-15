"""
BaseAgent — foundation for all supply chain agents.

Key design:
- Infinite loop that NEVER exits (catches all exceptions)
- Exponential backoff on errors (max 60s)
- Automatic heartbeat writing to Redis + PostgreSQL
- Self-healing interface (subclasses override heal())
- LLM called only on anomaly, not every cycle
- All decisions are audited
- Signal handling in main thread only (run_all.py) — NOT in agent threads
"""
import os
import logging
import time
import threading
from abc import ABC, abstractmethod
from anthropic import Anthropic

from agents import state, communication

logger = logging.getLogger(__name__)

HAIKU_MODEL = os.getenv("AGENT_MODEL_HAIKU", "claude-haiku-4-5-20251001")
SONNET_MODEL = os.getenv("AGENT_MODEL_SONNET", "claude-sonnet-4-6")

# Global shutdown event set by run_all.py main thread signal handler
_global_shutdown = threading.Event()


def request_shutdown():
    """Called from main thread signal handler to stop all agents."""
    _global_shutdown.set()


class BaseAgent(ABC):
    """
    Base class for all supply chain agents.

    Subclasses must implement:
      - check() : performs one monitoring cycle, raises on anomaly
      - heal(error) : attempts to fix the error, returns True if healed

    Subclasses may override:
      - analyze_with_llm(context) : call LLM for complex reasoning
    """

    def __init__(self, agent_id: str, model: str, interval_seconds: int,
                 description: str = ""):
        self.agent_id = agent_id
        self.model = model
        self.interval = interval_seconds
        self.description = description
        # Bug 5: check for API key before creating client to surface a clear error early
        _api_key = os.getenv("ANTHROPIC_API_KEY")
        if not _api_key:
            raise EnvironmentError(
                f"[{agent_id}] ANTHROPIC_API_KEY environment variable is not set. "
                "Set it before starting agents."
            )
        self.client = Anthropic(api_key=_api_key)
        self.error_count = 0
        self.consecutive_failures = 0
        self.start_time = time.time()

        # Ensure agent tables exist (idempotent)
        try:
            state.ensure_tables()
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Could not ensure tables at init: {e} — will retry")

        logger.info(f"[{self.agent_id}] Initialized. Model: {self.model}. Interval: {self.interval}s")

    def uptime(self) -> int:
        return int(time.time() - self.start_time)

    def _write_heartbeat(self, status: str, task: str = None, metrics: dict = None, error: str = None):
        try:
            state.write_heartbeat(
                agent_id=self.agent_id,
                status=status,
                current_task=task,
                metrics=metrics or {},
                error_count=self.error_count,
                last_error=error,
                model=self.model,
                uptime_seconds=self.uptime()
            )
            communication.publish_heartbeat(self.agent_id, status)
        except Exception as e:
            logger.debug(f"[{self.agent_id}] Heartbeat write failed (non-fatal): {e}")

    def audit(self, action: str, reasoning: str = None, outcome: str = "SUCCESS", details: dict = None):
        try:
            state.write_audit(self.agent_id, action, reasoning, outcome, details)
        except Exception as e:
            logger.debug(f"[{self.agent_id}] Audit write failed (non-fatal): {e}")

    def alert(self, severity: str, message: str, details: dict = None):
        communication.publish_alert(self.agent_id, severity, message, details)
        self.audit(f"ALERT:{severity}", message, "ALERT", details)

    def analyze_with_llm(self, system_prompt: str, user_message: str,
                          tools: list = None, max_tokens: int = 1024) -> str:
        """
        Call LLM for complex reasoning. Returns text or tool_use JSON string.
        Only call this when threshold-based logic is insufficient.
        """
        try:
            import json
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}]
            }
            if tools:
                kwargs["tools"] = tools

            response = self.client.messages.create(**kwargs)

            for block in response.content:
                if block.type == "tool_use":
                    return json.dumps({"tool": block.name, "input": block.input})
                if block.type == "text":
                    return block.text
            return ""
        except Exception as e:
            logger.error(f"[{self.agent_id}] LLM call failed: {e}")
            raise

    def check_for_corrections(self):
        """Apply any pending corrections from the orchestrator."""
        try:
            corrections = state.get_pending_corrections(self.agent_id)
            for correction in corrections:
                logger.warning(f"[{self.agent_id}] Orchestrator correction: {correction}")
                self.apply_correction(correction)
        except Exception as e:
            logger.debug(f"[{self.agent_id}] Correction check failed: {e}")

    def apply_correction(self, correction: str):
        """Override in subclasses to handle orchestrator corrections."""
        logger.info(f"[{self.agent_id}] Correction received (default handler): {correction}")

    @abstractmethod
    def check(self) -> dict:
        """
        Perform one monitoring cycle.
        Returns metrics dict.
        Raises exception on anomaly that requires healing.
        """

    def heal(self, error: Exception) -> bool:
        """
        Attempt to self-heal after an error.
        Returns True if healed, False if escalation needed.
        Override in subclasses.
        """
        return False

    def run(self):
        """
        Main entry point. Infinite synchronous loop.
        NEVER exits unless global shutdown event is set.
        """
        logger.info(f"[{self.agent_id}] Starting. Description: {self.description}")
        self._write_heartbeat("STARTING", "Initializing")

        while not _global_shutdown.is_set():
            cycle_start = time.time()
            try:
                # Check for orchestrator corrections
                self.check_for_corrections()

                # Run the monitoring check
                metrics = self.check() or {}
                self.consecutive_failures = 0
                self._write_heartbeat("HEALTHY", task=metrics.get("task", "monitoring"),
                                      metrics=metrics)

                # Sleep for the configured interval
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.interval - elapsed)
                self._interruptible_sleep(sleep_time)

            except Exception as e:
                self.error_count += 1
                self.consecutive_failures += 1
                error_msg = str(e)

                logger.error(f"[{self.agent_id}] Error (consecutive={self.consecutive_failures}): {error_msg}")
                self._write_heartbeat("DEGRADED", task="healing", error=error_msg,
                                      metrics={"consecutive_failures": self.consecutive_failures})

                # Try to self-heal
                healed = False
                try:
                    healed = self.heal(e)
                except Exception as heal_err:
                    logger.error(f"[{self.agent_id}] Heal attempt failed: {heal_err}")

                if not healed and self.consecutive_failures >= 3:
                    self.alert("CRITICAL",
                               f"Agent {self.agent_id} has {self.consecutive_failures} consecutive failures: {error_msg}",
                               {"error": error_msg, "consecutive_failures": self.consecutive_failures})

                # Exponential backoff: 2, 4, 8, 16, 32, 60 (max)
                backoff = min(2 ** self.consecutive_failures, 60)
                logger.info(f"[{self.agent_id}] Backing off {backoff}s before retry")
                self._interruptible_sleep(backoff)

        logger.info(f"[{self.agent_id}] Shutdown complete. Total errors: {self.error_count}")
        self._write_heartbeat("OFFLINE", task="shutdown")

    def _interruptible_sleep(self, seconds: float):
        """Sleep in 1s chunks so shutdown event is checked frequently."""
        end = time.time() + seconds
        while time.time() < end and not _global_shutdown.is_set():
            time.sleep(min(1.0, end - time.time()))
