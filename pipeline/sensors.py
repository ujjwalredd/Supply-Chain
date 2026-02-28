"""Dagster sensors that trigger on new Kafka messages."""

import logging
import os
from typing import Optional

from dagster import (
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)

from pipeline.jobs import stream_processing_job

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")


@sensor(job=stream_processing_job)
def new_kafka_messages_sensor(context: SensorEvaluationContext) -> Optional[SensorResult]:
    """Trigger stream processing when new messages appear in Kafka."""
    try:
        from dagster import RunRequest

        from kafka import KafkaConsumer

        consumer = KafkaConsumer(
            os.getenv("KAFKA_TOPIC", "supply-chain-events"),
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
            consumer_timeout_ms=3000,
        )
        partitions = consumer.partitions_for_topic(os.getenv("KAFKA_TOPIC", "supply-chain-events")) or []
        consumer.close()
        if partitions:
            return SensorResult(run_requests=[RunRequest(run_key="kafka_trigger")])
        return SkipReason("Kafka topic not available")
    except Exception as e:
        logger.warning("Sensor check failed: %s", e)
        return SkipReason(str(e))
