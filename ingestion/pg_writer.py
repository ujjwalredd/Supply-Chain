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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Kafka imports are lazy (inside run()) so the module can be imported without
# kafka-python installed (e.g. in unit tests that only use _detect_deviations).
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from ingestion.schemas import DemandEvent, OrderEvent

# Background thread pool for AI analysis (max 2 concurrent Claude calls)
_AI_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ai-analyzer")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("pg-writer")

# ── Configuration ──────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "supply-chain-events")
DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "supply-chain-dlq")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    _pg_user = os.getenv("POSTGRES_USER", "supplychain")
    _pg_pass = os.getenv("POSTGRES_PASSWORD", "")
    _pg_host = os.getenv("POSTGRES_HOST", "localhost")
    _pg_port = os.getenv("POSTGRES_PORT", "5432")
    _pg_db = os.getenv("POSTGRES_DB", "supply_chain_db")
    if not _pg_pass:
        raise RuntimeError(
            "pg_writer: database credentials not configured. "
            "Set DATABASE_URL or POSTGRES_PASSWORD in environment."
        )
    try:
        _pg_port_int = int(_pg_port)
    except ValueError as exc:
        raise RuntimeError(
            f"pg_writer: invalid POSTGRES_PORT '{_pg_port}'. Must be an integer."
        ) from exc

    # Use SQLAlchemy URL builder so special chars in credentials are safely encoded.
    DATABASE_URL = URL.create(
        drivername="postgresql",
        username=_pg_user,
        password=_pg_pass,
        host=_pg_host,
        port=_pg_port_int,
        database=_pg_db,
    ).render_as_string(hide_password=False)
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


def _get_producer():
    """Return a Kafka producer for DLQ publishing."""
    try:
        from kafka import KafkaProducer
        return KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            retries=3,
            acks="all",
        )
    except Exception as e:
        logger.warning("DLQ producer unavailable: %s", e)
        return None


def _send_to_dlq(producer, raw_message: str, error: str, context: dict) -> None:
    """Send a failed message to the dead letter queue topic."""
    if producer is None:
        logger.warning("DLQ producer not available, dropping failed message: %s", error)
        return
    try:
        dlq_record = {
            "original_message": raw_message,
            "error": str(error),
            "context": context,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        producer.send(DLQ_TOPIC, dlq_record)
        producer.flush(timeout=5)
        logger.warning("Sent failed message to DLQ: %s", error)
    except Exception as e:
        logger.error("Failed to send to DLQ: %s", e)


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
    """Upsert order events into the orders table. Returns count of records processed (inserted or updated)."""
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


def _count_recent_critical(session, supplier_id: str, order_id: str) -> int:
    """Count CRITICAL deviations for a supplier in the last 24 hours."""
    from datetime import timedelta
    from api.models import Deviation, Order
    from sqlalchemy import select as sa_select, func as sa_func
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    row = session.execute(
        sa_select(sa_func.count())
        .select_from(Deviation)
        .join(Order, Deviation.order_id == Order.order_id)
        .where(Order.supplier_id == supplier_id)
        .where(Deviation.severity == "CRITICAL")
        .where(Deviation.detected_at >= cutoff)
    ).scalar()
    return int(row or 0)


def _insert_deviations(session, deviations: list[dict]) -> list[dict]:
    """Insert detected deviations using savepoints so failures don't roll back the batch.

    Alert fatigue suppression: if the same supplier already has 5+ CRITICAL deviations
    in the last 24 hours, skip inserting additional CRITICAL ones and log a warning.
    """
    from api.models import Deviation, Order
    from sqlalchemy import select as sa_select

    # Pre-resolve order_id -> supplier_id for suppression check
    order_ids = {d["order_id"] for d in deviations if d.get("severity") == "CRITICAL"}
    supplier_by_order: dict[str, str] = {}
    if order_ids:
        rows = session.execute(
            sa_select(Order.order_id, Order.supplier_id).where(Order.order_id.in_(order_ids))
        ).all()
        for r in rows:
            supplier_by_order[r.order_id] = r.supplier_id

    # Cache suppression decisions per supplier to avoid repeated DB queries in one batch
    suppression_cache: dict[str, bool] = {}

    inserted = []
    skipped = 0
    for d in deviations:
        # Alert fatigue check for CRITICAL deviations
        if d.get("severity") == "CRITICAL":
            sid = supplier_by_order.get(d["order_id"])
            if sid:
                if sid not in suppression_cache:
                    count = _count_recent_critical(session, sid, d["order_id"])
                    suppression_cache[sid] = count >= 5
                    if suppression_cache[sid]:
                        logger.warning(
                            "Alert fatigue suppression: supplier %s has %d CRITICAL alerts in 24h, skipping",
                            sid, count,
                        )
                if suppression_cache[sid]:
                    skipped += 1
                    continue

        savepoint = session.begin_nested()
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
            savepoint.commit()
            inserted.append(d)
        except Exception as e:
            savepoint.rollback()
            skipped += 1
            logger.debug("Deviation insert skipped (%s): %s", d["deviation_id"], e)
    if skipped:
        logger.info("Skipped %d duplicate/suppressed deviations in batch", skipped)
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


def _detect_demand_deviations(event: DemandEvent) -> list[dict]:
    """Detect preemptive STOCKOUT risk from upstream demand signal."""
    deviations = []
    now = datetime.now(timezone.utc).isoformat()
    # Spike > 25% with < 7 days inventory cover = preemptive HIGH alert
    if event.forecast_delta_pct >= 25.0 and event.current_inventory_days < 7.0:
        deviations.append({
            "deviation_id": f"DEV-{uuid.uuid4().hex[:12].upper()}",
            "order_id": f"DEMAND-{event.region}-{event.product[:8]}",
            "type": "STOCKOUT",
            "severity": "HIGH" if event.forecast_delta_pct >= 40 else "MEDIUM",
            "detected_at": now,
            "recommended_action": (
                f"Preemptive restock: demand for {event.product} in {event.region} "
                f"spiked +{event.forecast_delta_pct:.0f}% "
                f"(signal: {event.signal_source}, cover: {event.current_inventory_days:.0f}d)"
            ),
            "executed": False,
        })
    return deviations


def _trigger_ai_background(deviation: dict, engine_factory) -> None:
    """
    Background task: run AI analysis on a CRITICAL deviation, then auto-execute
    or create an ESCALATE action depending on autonomous_executable flag.

    Runs in _AI_EXECUTOR thread pool — never blocks the main batch loop.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        return
    try:
        from api.models import Deviation, Order, PendingAction, Supplier
        from integrations.action_executor import ActionExecutor
        from reasoning.engine import analyze_structured, compute_financial_impact
        from sqlalchemy import select
        from sqlalchemy.orm import sessionmaker

        engine = engine_factory()
        Session = sessionmaker(bind=engine)

        with Session() as session:
            # Fetch order + supplier context
            dev = session.execute(
                select(Deviation).where(Deviation.deviation_id == deviation["deviation_id"])
            ).scalar_one_or_none()

            order_data: dict = {}
            supplier_data: dict = {}
            if dev:
                order = session.execute(
                    select(Order).where(Order.order_id == dev.order_id)
                ).scalar_one_or_none()
                if order:
                    order_data = {
                        "order_id": order.order_id,
                        "supplier_id": order.supplier_id,
                        "product": order.product,
                        "order_value": order.order_value,
                        "delay_days": order.delay_days,
                        "region": order.region,
                    }
                    sup = session.execute(
                        select(Supplier).where(Supplier.supplier_id == order.supplier_id)
                    ).scalar_one_or_none()
                    if sup:
                        supplier_data = {
                            "supplier_id": sup.supplier_id,
                            "trust_score": sup.trust_score,
                            "delayed_orders": sup.delayed_orders,
                            "total_orders": sup.total_orders,
                        }

            fi = compute_financial_impact(deviation, order_data)
            analysis = analyze_structured(
                deviation, order_data, supplier_data,
                financial_impact=fi,
            )

            max_confidence = max(
                (o.confidence for o in analysis.options), default=0.0
            )
            action_type = "REROUTE" if analysis.autonomous_executable else "ESCALATE"
            action = PendingAction(
                deviation_id=deviation["deviation_id"],
                action_type=action_type,
                description=analysis.recommendation,
                payload={
                    "ai_analysis": {
                        "root_cause": analysis.root_cause,
                        "recommendation": analysis.recommendation,
                        "autonomous_executable": analysis.autonomous_executable,
                    },
                    "financial_impact_usd": fi["usd"],
                    "confidence": round(max_confidence, 3),
                    "execution_confidence": round(analysis.execution_confidence, 3),
                    "trigger": "auto",
                    "severity": deviation.get("severity"),
                    "deviation_type": deviation.get("type"),
                },
                status="PENDING",
            )
            session.add(action)
            session.flush()

            if analysis.autonomous_executable:
                executor = ActionExecutor(session)
                executor.execute(action)

            session.commit()
            logger.info(
                "AI auto-action: deviation=%s type=%s impact=$%.0f autonomous=%s",
                deviation["deviation_id"], action_type,
                fi["usd"], analysis.autonomous_executable,
            )
    except Exception as e:
        logger.warning("Background AI analysis failed for %s: %s", deviation.get("deviation_id"), e)
        # Guarantee an ESCALATE action is always created even when AI is unavailable,
        # so operators are notified and no CRITICAL deviation falls through silently.
        # Open a FRESH session — `session` may be undefined (import/engine failure) or
        # already closed/rolled-back (exception inside the with-block above).
        try:
            from api.models import PendingAction as _PendingAction
            from sqlalchemy.orm import sessionmaker as _sessionmaker
            _engine = engine_factory()
            _FallbackSession = _sessionmaker(bind=_engine)
            with _FallbackSession() as fallback_session:
                fallback = _PendingAction(
                    deviation_id=deviation["deviation_id"],
                    action_type="ESCALATE",
                    description=(
                        f"[AI unavailable — human review required] "
                        f"CRITICAL deviation detected: {deviation.get('type', 'UNKNOWN')} "
                        f"severity={deviation.get('severity', 'CRITICAL')}"
                    ),
                    payload={
                        "trigger": "auto_fallback",
                        "severity": deviation.get("severity"),
                        "deviation_type": deviation.get("type"),
                        "ai_error": str(e),
                    },
                    status="PENDING",
                )
                fallback_session.add(fallback)
                fallback_session.commit()
            logger.info("Fallback ESCALATE action created for deviation %s", deviation.get("deviation_id"))
        except Exception as fallback_err:
            logger.error("Failed to create fallback action for deviation %s: %s", deviation.get("deviation_id"), fallback_err)


def process_batch(
    session,
    redis_client,
    events: list[OrderEvent],
) -> tuple[int, int]:
    """
    Process a batch of events: upsert orders/suppliers, detect deviations,
    publish to Redis, and trigger background AI for CRITICAL deviations.
    Returns (orders_upserted, deviations_detected).
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

        # Trigger background AI analysis for CRITICAL deviations
        for dev in inserted_devs:
            if dev.get("severity") == "CRITICAL":
                _AI_EXECUTOR.submit(_trigger_ai_background, dev, _get_engine)

        return orders_count, len(inserted_devs)
    except Exception as e:
        logger.exception("Batch processing failed: %s", e)
        session.rollback()
        return 0, 0


def process_demand_event(session, redis_client, event: DemandEvent) -> int:
    """Process a demand signal event — detect preemptive deviations."""
    deviations = _detect_demand_deviations(event)
    if not deviations:
        return 0
    # Use a fake Order stub for demand events (order_id = DEMAND-...)
    # We insert deviations directly without an orders FK to keep it lightweight
    inserted = []
    for d in deviations:
        savepoint = session.begin_nested()
        try:
            from api.models import Deviation
            detected_at = datetime.fromisoformat(d["detected_at"].replace("Z", "+00:00"))
            # Find a real order for this product/region to attach to, or skip FK
            from sqlalchemy import select
            from api.models import Order
            anchor = session.execute(
                select(Order)
                .where(Order.product == event.product)
                .where(Order.region == event.region)
                .where(Order.status.notin_(["DELIVERED", "CANCELLED"]))
                .order_by(Order.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if not anchor:
                savepoint.rollback()
                continue
            dev = Deviation(
                deviation_id=d["deviation_id"],
                order_id=anchor.order_id,
                type=d["type"],
                severity=d["severity"],
                detected_at=detected_at,
                recommended_action=d.get("recommended_action"),
                executed=False,
            )
            session.add(dev)
            session.flush()
            savepoint.commit()
            inserted.append(d)
        except Exception as e:
            savepoint.rollback()
            logger.debug("Demand deviation insert skipped: %s", e)
    if inserted:
        session.commit()
        _publish_deviations(redis_client, inserted)
        logger.info("Demand signal: %d preemptive deviations for %s/%s",
                    len(inserted), event.product, event.region)
    return len(inserted)


def run() -> None:
    """Main consumer loop."""
    # Lazy Kafka imports - not needed for unit tests that only use _detect_deviations
    from kafka import KafkaConsumer  # type: ignore
    from kafka.errors import KafkaError  # type: ignore
    engine = _get_engine()
    Session = sessionmaker(bind=engine)
    redis_client = _get_redis()
    dlq_producer = _get_producer()

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
                event_type = payload.get("event_type", "ORDER")

                # Route demand spike events to their own handler
                if event_type == "DEMAND_SPIKE":
                    try:
                        demand = DemandEvent.model_validate(payload)
                    except (ValidationError, json.JSONDecodeError) as e:
                        raw = json.dumps(payload) if payload else ""
                        _send_to_dlq(
                            dlq_producer, raw, str(e),
                            {"event_type": "DEMAND_SPIKE", "topic": KAFKA_TOPIC,
                             "partition": msg.partition, "offset": msg.offset},
                        )
                        continue
                    with Session() as session:
                        process_demand_event(session, redis_client, demand)
                    continue

                try:
                    event = OrderEvent.model_validate(payload)
                except (ValidationError, json.JSONDecodeError) as e:
                    raw = json.dumps(payload) if payload else ""
                    _send_to_dlq(
                        dlq_producer, raw, str(e),
                        {"event_type": event_type, "topic": KAFKA_TOPIC,
                         "partition": msg.partition, "offset": msg.offset},
                    )
                    continue
                batch.append(event)
            except (KeyError,) as e:
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
        _AI_EXECUTOR.shutdown(wait=False)
        consumer.close()


if __name__ == "__main__":
    run()
