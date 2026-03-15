"""
run_all.py — Start all supply chain agents.

Each agent runs in its own daemon thread.
Main thread monitors all threads and restarts any that die.
This process NEVER exits under normal circumstances.

Signal handling lives ONLY in this main thread (Python limitation).
Shutdown is propagated to all agents via the _global_shutdown event in base.py.
"""
import os
import sys
import time
import logging
import signal
import threading
from typing import Dict, Type

from agents import state
from agents.base import BaseAgent, request_shutdown, _global_shutdown
from agents.kafka_guardian import KafkaGuardianAgent
from agents.dagster_guardian import DagsterGuardianAgent
from agents.ai_quality_monitor import AIQualityMonitorAgent
from agents.database_health import DatabaseHealthAgent
from agents.orchestrator import OrchestratorAgent
from agents.medallion.bronze import BronzeAgent
from agents.medallion.silver import SilverAgent
from agents.medallion.gold import GoldAgent
from agents.medallion.supervisor import MedallionSupervisor
from agents.data_ingestion_agent import DataIngestionAgent
from agents.mlflow_guardian import MLflowGuardianAgent
from agents.feature_engineer import FeatureEngineerAgent
from agents.dashboard_agent import DashboardAgent

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("run_all")

AGENT_CLASSES: Dict[str, Type[BaseAgent]] = {
    "kafka_guardian": KafkaGuardianAgent,
    "dagster_guardian": DagsterGuardianAgent,
    "bronze_agent": BronzeAgent,
    "silver_agent": SilverAgent,
    "gold_agent": GoldAgent,
    "medallion_supervisor": MedallionSupervisor,
    "ai_quality_monitor": AIQualityMonitorAgent,
    "database_health": DatabaseHealthAgent,
    "orchestrator": OrchestratorAgent,
    # New autonomous agents — full agentic loop
    "data_ingestion": DataIngestionAgent,
    "mlflow_guardian": MLflowGuardianAgent,
    "feature_engineer": FeatureEngineerAgent,
    "dashboard_agent": DashboardAgent,
}


def _handle_signal(signum, frame):
    """Called from main thread only — propagates shutdown to all agents."""
    logger.warning(f"Signal {signum} received — requesting global shutdown")
    request_shutdown()


def run_agent(agent_id: str, agent_class: Type[BaseAgent]):
    """Run a single agent with automatic restart on crash. Never exits unless shutdown."""
    while not _global_shutdown.is_set():
        try:
            logger.info(f"[run_all] Starting agent: {agent_id}")
            agent = agent_class()
            agent.run()
        except Exception as e:
            logger.error(f"[run_all] Agent {agent_id} crashed: {e}", exc_info=True)
            if not _global_shutdown.is_set():
                logger.info(f"[run_all] Restarting {agent_id} in 15s")
                # Write RESTARTING heartbeat
                try:
                    # Bug 24: increase error truncation from 200 to 1000 chars
                    state.write_heartbeat(agent_id, "RESTARTING",
                                          current_task="crashed — auto-restarting in 15s",
                                          last_error=str(e)[:1000])
                except Exception:
                    pass
                _global_shutdown.wait(timeout=15)  # Interruptible sleep

    logger.info(f"[run_all] Agent {agent_id} thread exiting (shutdown)")


def main():
    # Signal handlers MUST be registered in the main thread
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("=" * 60)
    logger.info("Supply Chain Autonomous Agent System starting")
    logger.info(f"Agents to launch: {list(AGENT_CLASSES.keys())}")
    logger.info("=" * 60)

    # Wait for infrastructure services to be fully ready
    startup_delay = int(os.getenv("AGENT_STARTUP_DELAY", "45"))
    logger.info(f"Waiting {startup_delay}s for infra (postgres, redis, kafka, dagster)...")
    _global_shutdown.wait(timeout=startup_delay)
    if _global_shutdown.is_set():
        logger.info("Shutdown requested during startup — exiting")
        return

    # Ensure agent tables exist in PostgreSQL
    for attempt in range(10):
        try:
            state.ensure_tables()
            logger.info("Agent state tables ready")
            break
        except Exception as e:
            logger.warning(f"DB not ready yet (attempt {attempt+1}/10): {e}")
            if _global_shutdown.wait(timeout=5):
                return
    else:
        logger.error("Could not connect to DB after 10 attempts — agents will retry internally")

    # Start all agents in daemon threads (staggered 2s apart)
    threads: Dict[str, threading.Thread] = {}
    for agent_id, agent_class in AGENT_CLASSES.items():
        if _global_shutdown.is_set():
            break
        t = threading.Thread(
            target=run_agent,
            args=(agent_id, agent_class),
            name=f"agent-{agent_id}",
            daemon=True
        )
        t.start()
        threads[agent_id] = t
        logger.info(f"[run_all] Thread started for {agent_id}")
        _global_shutdown.wait(timeout=2)  # Stagger with interruptible sleep

    logger.info(f"[run_all] All {len(threads)} agent threads launched")

    # Main thread: watch for dead threads and restart them
    while not _global_shutdown.is_set():
        _global_shutdown.wait(timeout=30)  # Check every 30s

        if _global_shutdown.is_set():
            break

        for agent_id, t in list(threads.items()):
            if not t.is_alive():
                logger.error(f"[run_all] Thread for {agent_id} died — restarting immediately")
                new_t = threading.Thread(
                    target=run_agent,
                    args=(agent_id, AGENT_CLASSES[agent_id]),
                    name=f"agent-{agent_id}",
                    daemon=True
                )
                new_t.start()
                threads[agent_id] = new_t

    # Wait for all threads to finish
    logger.info("[run_all] Shutdown in progress — waiting for threads...")
    for agent_id, t in threads.items():
        t.join(timeout=10)

    logger.info("[run_all] All agents stopped. Exiting.")
    sys.exit(0)


if __name__ == "__main__":
    main()
