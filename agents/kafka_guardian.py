"""
Kafka Guardian Agent
Model: Claude Haiku (called only on anomaly)
Interval: 30s

Monitors:
- Consumer lag on supply-chain-events
- DLQ message count (supply-chain-dlq)
- Producer heartbeat (last event written to pg)
- Partition balance

Self-healing:
- Restarts pg-writer container on consumer lag
- Restarts producer container on silence
- Publishes DLQ alerts to orchestrator
"""
import os
import time
import logging
import subprocess
from datetime import datetime, timezone
from typing import Optional

import psycopg2

from agents.base import BaseAgent, HAIKU_MODEL
from agents.communication import publish_alert

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/supplychain")

# Thresholds — pure numbers, no LLM needed
LAG_WARN = int(os.getenv("KAFKA_LAG_WARN", "500"))
LAG_CRITICAL = int(os.getenv("KAFKA_LAG_CRITICAL", "2000"))
DLQ_SPIKE_THRESHOLD = int(os.getenv("DLQ_SPIKE_THRESHOLD", "10"))
PRODUCER_SILENCE_SECONDS = int(os.getenv("PRODUCER_SILENCE_SECONDS", "120"))


def _get_consumer_lag() -> dict:
    """Get consumer group lag using kafka-python admin client."""
    try:
        from kafka import KafkaAdminClient, KafkaConsumer
        from kafka.structs import TopicPartition

        admin = KafkaAdminClient(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            request_timeout_ms=10000,
            api_version_auto_timeout_ms=5000
        )

        # Get all consumer groups
        groups = admin.list_consumer_groups()
        group_ids = [g[0] for g in groups]

        lag_info = {}
        for group_id in group_ids:
            # Bug 9/32: use try/finally to guarantee consumer.close() even if
            # end_offsets() or iteration throws. The phantom group
            # _admin_lag_check_<group_id> is an unavoidable side-effect of using
            # KafkaConsumer for offset fetching; the proper long-term fix is to
            # use AdminClient.list_consumer_group_offsets + end_offsets via the
            # admin protocol so no new consumer group is registered at all.
            consumer = None
            try:
                offsets = admin.list_consumer_group_offsets(group_id)
                if not offsets:
                    continue

                consumer = KafkaConsumer(
                    bootstrap_servers=KAFKA_BOOTSTRAP,
                    group_id=f"_admin_lag_check_{group_id}",
                    auto_offset_reset="latest",
                    enable_auto_commit=False,
                    request_timeout_ms=10000
                )

                total_lag = 0
                for tp, offset_meta in offsets.items():
                    end_offsets = consumer.end_offsets([tp])
                    end = end_offsets.get(tp, offset_meta.offset)
                    lag = max(0, end - offset_meta.offset)
                    total_lag += lag

                lag_info[group_id] = total_lag
            except Exception:
                pass
            finally:
                if consumer:
                    consumer.close()

        admin.close()
        return lag_info

    except Exception as e:
        logger.warning(f"Consumer lag check failed: {e}")
        return {}


def _get_dlq_count() -> int:
    """Count messages in DLQ topic."""
    try:
        from kafka import KafkaConsumer, TopicPartition
        consumer = KafkaConsumer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            request_timeout_ms=10000
        )
        tp = TopicPartition("supply-chain-dlq", 0)
        consumer.assign([tp])
        consumer.seek_to_beginning(tp)
        beginning = consumer.position(tp)
        consumer.seek_to_end(tp)
        end = consumer.position(tp)
        consumer.close()
        return max(0, end - beginning)
    except Exception as e:
        logger.warning(f"DLQ count check failed: {e}")
        return -1


def _get_last_event_age_seconds() -> int:
    """Check how many seconds ago the last event was written to PostgreSQL.

    Bug 10: Each call opens a fresh psycopg2 connection (every 30 s). This
    bypasses the shared agent pool and can trip DatabaseHealthAgent's connection
    count alarms. The long-term fix is to refactor this to use a shared
    connection pool. For now, the connection is guarded with try/finally so it
    is always closed even if the query raises.
    """
    conn = None  # Bug 10: initialize before try so finally can safely guard on it
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) FROM orders WHERE created_at IS NOT NULL")
        row = cur.fetchone()
        cur.close()
        return int(row[0]) if row and row[0] else 9999
    except Exception as e:
        logger.warning(f"Last event age check failed: {e}")
        return -1
    finally:
        if conn:  # Bug 10: guarantee close even if the query throws
            conn.close()


def _restart_container(name: str) -> bool:
    """Restart a Docker Compose service."""
    try:
        result = subprocess.run(
            ["docker", "restart", name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            logger.info(f"Restarted container: {name}")
            return True
        else:
            logger.error(f"Restart failed for {name}: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Container restart error for {name}: {e}")
        return False


class KafkaGuardianAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            agent_id="kafka_guardian",
            model=HAIKU_MODEL,
            interval_seconds=30,
            description="Monitors Kafka consumer lag, DLQ, producer heartbeat. Self-heals by restarting containers."
        )
        self._prev_dlq_count = 0
        self._restart_cooldown = {}  # container -> last restart timestamp

    def _can_restart(self, container: str, cooldown_sec: int = 120) -> bool:
        last = self._restart_cooldown.get(container, 0)
        return (time.time() - last) > cooldown_sec

    def check(self) -> dict:
        metrics = {}

        # 1. Check producer heartbeat (age of last event)
        age = _get_last_event_age_seconds()
        metrics["last_event_age_sec"] = age

        if age > PRODUCER_SILENCE_SECONDS and age != -1:
            logger.warning(f"Producer silence detected: last event {age}s ago")
            if self._can_restart("supply-chain-os-producer-1"):
                restarted = _restart_container("supply-chain-os-producer-1")
                self.audit("RESTART_PRODUCER",
                           f"Last event was {age}s ago (threshold={PRODUCER_SILENCE_SECONDS}s)",
                           "SUCCESS" if restarted else "FAILED",
                           {"last_event_age": age})
                if restarted:
                    self._restart_cooldown["supply-chain-os-producer-1"] = time.time()
                else:
                    self.alert("HIGH", f"Producer silent for {age}s, restart failed")
            else:
                logger.info("Producer restart on cooldown, skipping")

        # 2. Check consumer lag
        lag_info = _get_consumer_lag()
        metrics["consumer_lag"] = lag_info
        for group, lag in lag_info.items():
            if lag > LAG_CRITICAL:
                logger.error(f"CRITICAL consumer lag: group={group} lag={lag}")
                if self._can_restart("supply-chain-os-pg-writer-1"):
                    restarted = _restart_container("supply-chain-os-pg-writer-1")
                    self.audit("RESTART_PG_WRITER",
                               f"Consumer lag {lag} > {LAG_CRITICAL} for group {group}",
                               "SUCCESS" if restarted else "FAILED",
                               {"group": group, "lag": lag})
                    if restarted:
                        self._restart_cooldown["supply-chain-os-pg-writer-1"] = time.time()
                    else:
                        self.alert("CRITICAL", f"pg-writer restart failed, lag={lag}", {"group": group, "lag": lag})
                else:
                    self.alert("HIGH", f"Consumer lag {lag} for {group}, restart on cooldown")
            elif lag > LAG_WARN:
                logger.warning(f"High consumer lag: group={group} lag={lag}")
                self.alert("MEDIUM", f"Consumer lag {lag} for group {group}", {"lag": lag})

        # 3. Check DLQ
        dlq = _get_dlq_count()
        metrics["dlq_count"] = dlq
        if dlq != -1 and dlq > self._prev_dlq_count + DLQ_SPIKE_THRESHOLD:
            spike = dlq - self._prev_dlq_count
            logger.warning(f"DLQ spike: +{spike} new messages (total={dlq})")
            self.alert("HIGH", f"DLQ spike: {spike} new failed messages",
                       {"total_dlq": dlq, "new_messages": spike})
            self.audit("DLQ_SPIKE_DETECTED", f"+{spike} messages in DLQ", "ALERT",
                       {"total": dlq, "spike": spike})
        self._prev_dlq_count = max(dlq, 0)

        metrics["task"] = f"lag_check|dlq={dlq}|age={age}s"
        return metrics

    def heal(self, error: Exception) -> bool:
        logger.warning(f"[kafka_guardian] Healing: {error}")
        # If Kafka is unreachable, wait for it to come back — don't crash
        if "NoBrokersAvailable" in str(error) or "Connection refused" in str(error):
            logger.warning("Kafka not reachable. Waiting 30s for broker to recover.")
            time.sleep(30)
            return True
        return False
