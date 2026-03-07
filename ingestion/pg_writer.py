#!/usr/bin/env python3
"""
Kafka → PostgreSQL writer with deviation detection and Redis pub/sub.

Consumes supply-chain-events from Kafka, writes orders + suppliers to Postgres,
detects deviations (DELAY / STOCKOUT / ANOMALY), writes them to Postgres, and
publishes via Redis so the FastAPI WebSocket endpoint can broadcast in real-time.

This replaces the Delta Lake consumer for the operational (dashboard) data path.
The Delta Lake consumer still runs for the analytics/lakehouse path.

Usage:
    python ingestion/pg_writer.py
"""

import json
import logging
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Kafka imports are lazy (inside run()) so the module can be imported without
# kafka-python installed (e.g. in unit tests that only use _detect_deviations).
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from ingestion.schemas import OrderEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pg-writer")

# ── Configuration ──────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "supply-chain-events")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://supplychain:supplychain_secret@localhost:5432/supply_chain_db",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_CHANNEL = "deviations"
BATCH_SIZE = int(os.getenv("PG_WRITER_BATCH_SIZE", "10"))
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Deviation thresholds (match pipeline/assets.py logic)
DELAY_HIGH_THRESHOLD = 7     # > 7 days = HIGH
DELAY_CRITICAL_THRESHOLD = 14  # > 14 days = CRITICAL
STOCKOUT_HIGH_THRESHOLD = 5  # < 5 units = HIGH
STOCKOUT_THRESHOLD = 10      # < 10 units = MEDIUM
ANOMALY_VALUE_THRESHOLD = 100_000  # order_value > $100k = ANOMALY


def _get_engine():
    return create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
    )


def _get_redis():
    """Return a Redis client, or None if redis is not available."""
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        logger.warning("Redis unavailable, real-time broadcast disabled: %s", e)
        return None


def _detect_deviations(event: OrderEvent) -> list[dict[str, Any]]:
    """Apply business rules to detect deviations from a single order event."""
    deviations = []
    now = datetime.now(timezone.utc).isoformat()

    if event.delay_days > DELAY_CRITICAL_THRESHOLD:
        severity = "CRITICAL"
    elif event.delay_days > DELAY_HIGH_THRESHOLD:
        severity = "HIGH"
    elif event.delay_days > 0:
        severity = "MEDIUM"
    else:
        severity = None

    if severity:
        deviations.append({
            "deviation_id": f"DEV-{uuid.uuid4().hex[:12].upper()}",
            "order_id": event.order_id,
            "type": "DELAY",
            "severity": severity,
            "detected_at": now,
            "recommended_action": (
                f"Escalate to supplier {event.supplier_id}: "
                f"order delayed {event.delay_days} days"
            ),
            "executed": False,
        })

    if event.inventory_level < STOCKOUT_HIGH_THRESHOLD:
        deviations.append({
            "deviation_id": f"DEV-{uuid.uuid4().hex[:12].upper()}",
            "order_id": event.order_id,
            "type": "STOCKOUT",
            "severity": "HIGH",
            "detected_at": now,
            "recommended_action": (
                f"Emergency restock for {event.product} — "
                f"inventory at {event.inventory_level:.1f}%"
            ),
            "executed": False,
        })
    elif event.inventory_level < STOCKOUT_THRESHOLD:
        deviations.append({
            "deviation_id": f"DEV-{uuid.uuid4().hex[:12].upper()}",
            "order_id": event.order_id,
            "type": "STOCKOUT",
            "severity": "MEDIUM",
            "detected_at": now,
            "recommended_action": (
                f"Schedule restock for {event.product} — "
                f"inventory at {event.inventory_level:.1f}%"
            ),
            "executed": False,
        })

    if event.order_value > ANOMALY_VALUE_THRESHOLD:
        deviations.append({
            "deviation_id": f"DEV-{uuid.uuid4().hex[:12].upper()}",
            "order_id": event.order_id,
            "type": "ANOMALY",
            "severity": "MEDIUM",
            "detected_at": now,
            "recommended_action": (
                f"Review unusually high order value ${event.order_value:,.2f} "
                f"from {event.supplier_id}"
            ),
            "executed": False,
        })

    return deviations


def _upsert_orders(session, events: list[OrderEvent]) -> int:
    """Upsert order events into the orders table. Returns rows inserted."""
    from api.models import Order

    records = []
    for e in events:
        try:
            expected = datetime.fromisoformat(
                e.expected_delivery.replace("Z", "+00:00")
            )
        except Exception:
            expected = datetime.now(timezone.utc)

        actual = None
        if e.actual_delivery:
            try:
                actual = datetime.fromisoformat(
                    e.actual_delivery.replace("Z", "+00:00")
                )
            except Exception:
                pass

        records.append({
            "order_id": e.order_id,
            "supplier_id": e.supplier_id,
            "product": e.product,
            "region": e.region,
            "quantity": e.quantity,
            "unit_price": e.unit_price,
            "order_value": e.order_value,
            "expected_delivery": expected,
            "actual_delivery": actual,
            "delay_days": e.delay_days,
            "status": e.status,
            "inventory_level": e.inventory_level,
            "created_at": datetime.now(timezone.utc),
        })

    if not records:
        return 0

    stmt = (
        pg_insert(Order.__table__)
        .values(records)
        .on_conflict_do_update(
            index_elements=["order_id"],
            set_={
                "status": pg_insert(Order.__table__).excluded.status,
                "delay_days": pg_insert(Order.__table__).excluded.delay_days,
                "actual_delivery": pg_insert(Order.__table__).excluded.actual_delivery,
                "inventory_level": pg_insert(Order.__table__).excluded.inventory_level,
            },
        )
    )
    session.execute(stmt)
    return len(records)


def _upsert_suppliers(session, events: list[OrderEvent]) -> None:
    """Create supplier stubs for any new supplier_ids seen in this batch."""
    from api.models import Supplier

    seen: dict[str, OrderEvent] = {}
    for e in events:
        seen[e.supplier_id] = e

    for sid, e in seen.items():
        stmt = (
            pg_insert(Supplier.__table__)
            .values(
                supplier_id=sid,
                name=sid,
                region=e.region,
                trust_score=1.0,
                total_orders=0,
                delayed_orders=0,
                avg_delay_days=0.0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=["supplier_id"])
        )
        session.execute(stmt)


def _insert_deviations(session, deviations: list[dict]) -> list[dict]:
    """Insert detected deviations. Returns the ones actually inserted."""
    from api.models import Deviation

    inserted = []
    for d in deviations:
        try:
            detected_at = datetime.fromisoformat(d["detected_at"].replace("Z", "+00:00"))
            dev = Deviation(
                deviation_id=d["deviation_id"],
                order_id=d["order_id"],
                type=d["type"],
                severity=d["severity"],
                detected_at=detected_at,
                recommended_action=d.get("recommended_action"),
                executed=False,
            )
            session.add(dev)
            session.flush()
            inserted.append(d)
        except Exception as e:
            logger.debug("Deviation insert skipped (%s): %s", d["deviation_id"], e)
            session.rollback()
    return inserted


def _send_slack_alert(deviation: dict) -> None:
    """Send a Slack webhook notification for CRITICAL deviations."""
    if not SLACK_WEBHOOK_URL:
        return
    try:
        import urllib.request
        message = (
            f":rotating_light: *CRITICAL Supply Chain Alert*\n"
            f"*Type:* {deviation['type']}\n"
            f"*Order:* {deviation['order_id']}\n"
            f"*Action:* {deviation.get('recommended_action', 'N/A')}"
        )
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(
            SLACK_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.warning("Slack alert failed: %s", e)


def _publish_deviations(redis_client, deviations: list[dict]) -> None:
    """Publish detected deviations to Redis channel for WebSocket broadcast."""
    if not deviations:
        return
    for d in deviations:
        if redis_client:
            payload = json.dumps({"type": "deviation", "data": d})
            try:
                redis_client.publish(REDIS_CHANNEL, payload)
            except Exception as e:
                logger.warning("Redis publish failed: %s", e)
        if d.get("severity") == "CRITICAL":
            _send_slack_alert(d)


def _update_supplier_stats(session, events: list[OrderEvent]) -> None:
    """Incrementally update supplier trust scores and delay counts."""
    delayed_by_supplier: dict[str, int] = {}
    total_by_supplier: dict[str, int] = {}
    delay_days_by_supplier: dict[str, list[int]] = {}

    for e in events:
        total_by_supplier[e.supplier_id] = total_by_supplier.get(e.supplier_id, 0) + 1
        if e.delay_days > 0:
            delayed_by_supplier[e.supplier_id] = delayed_by_supplier.get(e.supplier_id, 0) + 1
        delay_days_by_supplier.setdefault(e.supplier_id, []).append(e.delay_days)

    for sid in total_by_supplier:
        total_inc = total_by_supplier[sid]
        delayed_inc = delayed_by_supplier.get(sid, 0)
        avg_delay = sum(delay_days_by_supplier[sid]) / len(delay_days_by_supplier[sid])
        session.execute(
            text("""
                UPDATE suppliers
                SET
                    total_orders = total_orders + :total_inc,
                    delayed_orders = delayed_orders + :delayed_inc,
                    avg_delay_days = (
                        avg_delay_days * total_orders + :avg_delay * :total_inc
                    ) / GREATEST(1, total_orders + :total_inc),
                    trust_score = GREATEST(0.0, LEAST(1.0,
                        1.0 - ((delayed_orders + :delayed_inc)::float
                               / GREATEST(1, total_orders + :total_inc)) * 0.5
                    )),
                    updated_at = NOW()
                WHERE supplier_id = :sid
            """),
            {
                "total_inc": total_inc,
                "delayed_inc": delayed_inc,
                "avg_delay": avg_delay,
                "sid": sid,
            },
        )


def process_batch(
    session,
    redis_client,
    events: list[OrderEvent],
) -> tuple[int, int]:
    """
    Process a batch of events: upsert orders/suppliers, detect deviations,
    publish to Redis. Returns (orders_upserted, deviations_detected).
    """
    try:
        _upsert_suppliers(session, events)
        orders_count = _upsert_orders(session, events)

        all_deviations: list[dict] = []
        for e in events:
            all_deviations.extend(_detect_deviations(e))

        inserted_devs = _insert_deviations(session, all_deviations)
        _update_supplier_stats(session, events)
        session.commit()

        _publish_deviations(redis_client, inserted_devs)

        return orders_count, len(inserted_devs)
    except Exception as e:
        logger.exception("Batch processing failed: %s", e)
        session.rollback()
        return 0, 0


def run() -> None:
    """Main consumer loop."""
    # Lazy Kafka imports - not needed for unit tests that only use _detect_deviations
    from kafka import KafkaConsumer  # type: ignore
    from kafka.errors import KafkaError  # type: ignore
    engine = _get_engine()
    Session = sessionmaker(bind=engine)
    redis_client = _get_redis()

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="pg-writer",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    logger.info(
        "pg_writer started: topic=%s db=%s redis=%s batch=%d",
        KAFKA_TOPIC,
        DATABASE_URL.split("@")[-1],  # don't log credentials
        REDIS_URL,
        BATCH_SIZE,
    )

    total_orders = 0
    total_deviations = 0
    batch: list[OrderEvent] = []

    def flush(sig=None, frame=None):
        nonlocal total_orders, total_deviations, batch
        if batch:
            with Session() as session:
                o, d = process_batch(session, redis_client, batch)
                total_orders += o
                total_deviations += d
            batch = []
        logger.info("Flushed. Total: %d orders, %d deviations", total_orders, total_deviations)
        if sig:
            consumer.close()
            sys.exit(0)

    signal.signal(signal.SIGTERM, flush)
    signal.signal(signal.SIGINT, flush)

    try:
        for msg in consumer:
            try:
                payload = msg.value
                if payload is None:
                    continue
                event = OrderEvent.model_validate(payload)
                batch.append(event)
            except (ValidationError, KeyError) as e:
                logger.debug("Invalid event skipped: %s", e)
                continue

            if len(batch) >= BATCH_SIZE:
                with Session() as session:
                    o, d = process_batch(session, redis_client, batch)
                    total_orders += o
                    total_deviations += d
                logger.info(
                    "Batch flushed: +%d orders, +%d deviations | total: %d / %d",
                    o, d, total_orders, total_deviations,
                )
                batch = []
    except KafkaError as e:
        logger.exception("Kafka error: %s", e)
    finally:
        flush()
        consumer.close()


if __name__ == "__main__":
    run()
