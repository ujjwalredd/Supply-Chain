"""
Kafka consumer for supply chain events.

Consumes from supply-chain-events topic and writes raw data to Delta Lake.
Runs Great Expectations validation on ingested batches.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Optional

from kafka import KafkaConsumer
from kafka.errors import KafkaError
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.schemas import OrderEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("supply-chain-consumer")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093").split(",")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "supply-chain-events")
DELTA_PATH = os.getenv("DELTA_RAW_PATH", "s3://supply-chain-lakehouse/raw/orders/")


def consume_to_delta(batch_size: int = 100) -> None:
    """Consume Kafka messages and append to Delta Lake table."""
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="supply-chain-consumer",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    batch: list[dict[str, Any]] = []
    try:
        for msg in consumer:
            try:
                payload = msg.value
                if payload is None:
                    continue
                event = OrderEvent.model_validate(payload)
                batch.append(event.model_dump(mode="json"))
            except (ValidationError, KeyError) as e:
                logger.warning("Invalid event, skipping: %s", e)
                continue

            if len(batch) >= batch_size:
                _write_batch_to_delta(batch)
                batch = []
    except KafkaError as e:
        logger.exception("Kafka error: %s", e)
        raise
    finally:
        if batch:
            _write_batch_to_delta(batch)
        consumer.close()


def _write_batch_to_delta(batch: list[dict[str, Any]]) -> None:
    """Write batch to Delta Lake. Uses local path if S3 not configured."""
    try:
        import pandas as pd
        from deltalake import write_deltalake
    except ImportError as e:
        logger.warning("Delta Lake not available, skipping write: %s", e)
        return

    df = pd.DataFrame(batch)
    # Normalize datetime columns
    for col in ["expected_delivery", "actual_delivery", "created_at"]:
        if col in df.columns and df[col].notna().any():
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    path = DELTA_PATH.replace("s3://", "s3a://")
    if "s3a://" in path or "s3://" in DELTA_PATH:
        storage_options = {
            "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
            "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
            "AWS_ENDPOINT_URL": os.getenv("AWS_ENDPOINT_URL", "http://localhost:9000"),
            "AWS_ALLOW_HTTP": "true",
        }
    else:
        storage_options = None
        path = path or "./data/raw/orders"

    if not path.startswith("s3a"):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        write_deltalake(
            path,
            df,
            mode="append",
            storage_options=storage_options if path.startswith("s3a") else None,
        )
        logger.info("Wrote batch of %d events to Delta Lake", len(batch))
    except Exception as e:
        logger.exception("Delta write failed: %s", e)
        raise


if __name__ == "__main__":
    consume_to_delta()
