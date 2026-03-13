#!/usr/bin/env python3
"""
Kafka producer for supply chain order events.

Simulates 50+ supplier order events per minute with intentional anomalies
(delays, stockouts, value spikes) for deviation detection testing.

Usage:
    python ingestion/producer.py
    # Or with env overrides:
    KAFKA_BOOTSTRAP_SERVERS=localhost:9093 python ingestion/producer.py
"""

import json
import logging
import os
import random
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import NoReturn

from kafka import KafkaProducer
from kafka.errors import KafkaError
from pydantic import ValidationError

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from faker import Faker
except ImportError:
    Faker = None  # type: ignore

from ingestion.schemas import DemandEvent, OrderEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("supply-chain-producer")

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "supply-chain-events")
EVENTS_PER_MINUTE = int(os.getenv("EVENTS_PER_MINUTE", "55"))
ANOMALY_RATE = float(os.getenv("ANOMALY_RATE", "0.12"))

# ── JSON Schema definitions for outbound event validation ───────────────────
_EVENT_SCHEMAS = {
    "ORDER": {
        "type": "object",
        "required": ["order_id", "supplier_id", "product", "region", "quantity",
                     "unit_price", "order_value", "expected_delivery", "delay_days",
                     "status", "inventory_level"],
        "properties": {
            "order_id": {"type": "string", "minLength": 1},
            "supplier_id": {"type": "string", "minLength": 1},
            "quantity": {"type": "integer", "minimum": 1},
            "unit_price": {"type": "number", "minimum": 0},
            "order_value": {"type": "number", "minimum": 0},
            "delay_days": {"type": "integer", "minimum": 0},
            "status": {"type": "string", "enum": ["PENDING", "IN_TRANSIT", "DELIVERED", "DELAYED", "CANCELLED"]},
            "inventory_level": {"type": "number", "minimum": 0, "maximum": 100},
        },
        "additionalProperties": True,
    },
    "DEMAND_SPIKE": {
        "type": "object",
        "required": ["event_type", "product", "region", "forecast_delta_pct"],
        "properties": {
            "product": {"type": "string", "minLength": 1},
            "region": {"type": "string", "minLength": 1},
            "forecast_delta_pct": {"type": "number"},
            "current_inventory_days": {"type": "number", "minimum": 0},
        },
        "additionalProperties": True,
    },
}


def _validate_event(event_dict: dict) -> tuple[bool, str]:
    """Validate an event dict against its JSON Schema. Returns (valid, error_message)."""
    try:
        import jsonschema
        event_type = event_dict.get("event_type", "ORDER")
        schema = _EVENT_SCHEMAS.get(event_type)
        if schema is None:
            return True, ""  # unknown type — allow through
        jsonschema.validate(instance=event_dict, schema=schema)
        return True, ""
    except ImportError:
        return True, ""  # jsonschema not installed — skip validation
    except Exception as e:
        return False, str(e)


# Product and supplier catalogs
PRODUCTS = [
    "WIDGET-A", "WIDGET-B", "GADGET-X", "GADGET-Y", "COMPONENT-101",
    "COMPONENT-102", "RAW-MATERIAL-1", "RAW-MATERIAL-2", "SUPPLY-KIT-A",
    "SUPPLY-KIT-B", "BULK-UNIT-1", "BULK-UNIT-2", "PART-ALPHA", "PART-BETA",
]
REGIONS = ["NA", "EMEA", "APAC", "LATAM"]
SUPPLIERS = [f"SUP-{i:03d}" for i in range(1, 26)]
STATUSES = ["PENDING", "IN_TRANSIT", "DELIVERED", "DELAYED", "CANCELLED"]

# Faker for realistic data
fake = Faker() if Faker else None
_order_counter = 0

# ── Supplier state machine ──────────────────────────────────────────────────
# Tracks health state per supplier: NORMAL → DEGRADING → CRITICAL → NORMAL
# Drives causality: a DELAY nudges the supplier toward CRITICAL, which then
# raises the probability of downstream STOCKOUT events.
_supplier_state: dict[str, str] = {}            # SUP-XXX → NORMAL|DEGRADING|CRITICAL
_supplier_anomaly_count: dict[str, int] = {}    # rolling anomaly hit counter
_MAX_SUPPLIER_STATE_ENTRIES = 500               # prevent unbounded growth
# Pending causality events: list of (fire_at_tick, event_dict)
_causality_queue: list[tuple[int, dict]] = []
_tick: int = 0                                  # incremented on every event send


def _cleanup_supplier_state() -> None:
    """Prune supplier state dicts when they exceed the max entry limit.
    Keeps NORMAL suppliers (already recovered) first since they're safe to remove.
    """
    if len(_supplier_state) <= _MAX_SUPPLIER_STATE_ENTRIES:
        return
    # Remove NORMAL entries first (fully recovered, no active risk)
    normal_keys = [k for k, v in _supplier_state.items() if v == "NORMAL"]
    for k in normal_keys:
        _supplier_state.pop(k, None)
        _supplier_anomaly_count.pop(k, None)
    # If still over limit, evict oldest DEGRADING entries (lower risk than CRITICAL)
    if len(_supplier_state) > _MAX_SUPPLIER_STATE_ENTRIES:
        degrading_keys = [k for k, v in _supplier_state.items() if v == "DEGRADING"]
        overflow = len(_supplier_state) - _MAX_SUPPLIER_STATE_ENTRIES
        for k in degrading_keys[:overflow]:
            _supplier_state.pop(k, None)
            _supplier_anomaly_count.pop(k, None)
    # Last resort: evict oldest CRITICAL entries by insertion order
    overflow = len(_supplier_state) - _MAX_SUPPLIER_STATE_ENTRIES
    if overflow > 0:
        for k in list(_supplier_state.keys())[:overflow]:
            _supplier_state.pop(k, None)
            _supplier_anomaly_count.pop(k, None)
    logger.debug("Pruned supplier state to %d entries", len(_supplier_state))


def _get_supplier_state(supplier_id: str) -> str:
    return _supplier_state.get(supplier_id, "NORMAL")


def _record_supplier_anomaly(supplier_id: str) -> None:
    """Increment anomaly count and advance state machine."""
    _supplier_anomaly_count[supplier_id] = _supplier_anomaly_count.get(supplier_id, 0) + 1
    count = _supplier_anomaly_count[supplier_id]
    current = _get_supplier_state(supplier_id)
    if current == "NORMAL" and count >= 2:
        _supplier_state[supplier_id] = "DEGRADING"
        logger.info("Supplier %s → DEGRADING (anomaly_count=%d)", supplier_id, count)
    elif current == "DEGRADING" and count >= 5:
        _supplier_state[supplier_id] = "CRITICAL"
        logger.warning("Supplier %s → CRITICAL (anomaly_count=%d)", supplier_id, count)
    # Gradual recovery: reset count after 20 clean events (handled in generate_event)


def _maybe_recover_supplier(supplier_id: str) -> None:
    """On a clean event, slowly decrement anomaly count and allow recovery."""
    count = _supplier_anomaly_count.get(supplier_id, 0)
    if count > 0:
        _supplier_anomaly_count[supplier_id] = count - 1
    # State downgrade when count falls below threshold
    current = _get_supplier_state(supplier_id)
    new_count = _supplier_anomaly_count.get(supplier_id, 0)
    if current == "CRITICAL" and new_count < 3:
        _supplier_state[supplier_id] = "DEGRADING"
        logger.info("Supplier %s → DEGRADING (recovering)", supplier_id)
    elif current == "DEGRADING" and new_count == 0:
        _supplier_state[supplier_id] = "NORMAL"
        logger.info("Supplier %s → NORMAL (recovered)", supplier_id)


def _queue_causality_stockout(supplier_id: str, region: str, product: str) -> None:
    """Schedule a downstream STOCKOUT from the same supplier in 1-2 ticks."""
    if len(_causality_queue) >= _CAUSALITY_QUEUE_MAX:
        # Drop oldest entry to keep queue bounded
        _causality_queue.pop(0)
        logger.debug("Causality queue full, dropped oldest entry")
    fire_at = _tick + random.randint(1, 2)
    payload = {
        "_causality_trigger": "DELAY",
        "supplier_id": supplier_id,
        "region": region,
        "product": product,
    }
    _causality_queue.append((fire_at, payload))
    logger.debug("Queued causality STOCKOUT for %s at tick %d", supplier_id, fire_at)


_CAUSALITY_QUEUE_MAX = 50  # prevent unbounded growth


def _next_order_id() -> str:
    global _order_counter
    _order_counter += 1
    return f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{_order_counter:06d}"


def _generate_base_order(supplier_id: str | None = None) -> dict:
    """Generate a normal order event."""
    now = datetime.now(timezone.utc)
    expected = now + timedelta(days=random.randint(3, 14))
    quantity = random.randint(10, 500)
    unit_price = round(random.uniform(5.0, 250.0), 2)
    order_value = round(quantity * unit_price, 2)
    inventory = round(random.uniform(15.0, 85.0), 1)

    return {
        "order_id": _next_order_id(),
        "supplier_id": supplier_id or random.choice(SUPPLIERS),
        "product": random.choice(PRODUCTS),
        "region": random.choice(REGIONS),
        "quantity": quantity,
        "unit_price": unit_price,
        "order_value": order_value,
        "expected_delivery": expected.date().isoformat(),
        "actual_delivery": None,
        "delay_days": 0,
        "status": random.choice(["PENDING", "IN_TRANSIT"]),
        "inventory_level": inventory,
        "created_at": now.isoformat(),
        "event_type": "ORDER",
    }


def _inject_anomaly(base: dict, force_type: str | None = None) -> dict:
    """Inject an anomaly: delay, stockout, value spike, or quantity anomaly.

    If force_type is set (causality path), inject that specific type.
    CRITICAL suppliers get higher weights on severe anomaly types.
    """
    state = _get_supplier_state(base["supplier_id"])

    if force_type:
        anomaly_type = force_type
    elif state == "CRITICAL":
        # Critical suppliers more likely to have compounding delays + stockouts
        anomaly_type = random.choices(
            ["DELAY", "STOCKOUT", "VALUE_SPIKE", "QUANTITY_ANOMALY"],
            weights=[0.55, 0.35, 0.06, 0.04],
            k=1,
        )[0]
    elif state == "DEGRADING":
        anomaly_type = random.choices(
            ["DELAY", "STOCKOUT", "VALUE_SPIKE", "QUANTITY_ANOMALY"],
            weights=[0.55, 0.30, 0.10, 0.05],
            k=1,
        )[0]
    else:
        anomaly_type = random.choices(
            ["DELAY", "STOCKOUT", "VALUE_SPIKE", "QUANTITY_ANOMALY"],
            weights=[0.5, 0.25, 0.15, 0.1],
            k=1,
        )[0]

    if anomaly_type == "DELAY":
        delay_days = random.randint(1, 14)
        expected = datetime.fromisoformat(base["expected_delivery"].replace("Z", ""))
        actual = expected + timedelta(days=delay_days)
        base["actual_delivery"] = actual.date().isoformat()
        base["delay_days"] = delay_days
        base["status"] = "DELAYED"
        # ── Causality: 30% chance of downstream STOCKOUT in next 1-2 ticks ──
        if random.random() < 0.30:
            _queue_causality_stockout(base["supplier_id"], base["region"], base["product"])

    elif anomaly_type == "STOCKOUT":
        base["inventory_level"] = round(random.uniform(0.0, 8.0), 1)
        base["status"] = random.choice(["PENDING", "IN_TRANSIT"])

    elif anomaly_type == "VALUE_SPIKE":
        base["unit_price"] = round(base["unit_price"] * random.uniform(2.0, 4.0), 2)
        base["order_value"] = round(base["quantity"] * base["unit_price"], 2)

    elif anomaly_type == "QUANTITY_ANOMALY":
        base["quantity"] = base["quantity"] * random.randint(3, 10)
        base["order_value"] = round(base["quantity"] * base["unit_price"], 2)

    _record_supplier_anomaly(base["supplier_id"])
    base["supplier_health"] = _get_supplier_state(base["supplier_id"])
    return base


def generate_event() -> OrderEvent:
    """Generate a validated order event, with anomalies and causality chains."""
    global _tick
    _tick += 1
    # Periodic cleanup every 1000 ticks to prevent unbounded dict growth
    if _tick % 1000 == 0:
        _cleanup_supplier_state()

    # ── Check causality queue for due events ────────────────────────────────
    due = [(t, p) for (t, p) in _causality_queue if _tick >= t]
    if due:
        fire_at, payload = due[0]
        _causality_queue.remove((fire_at, payload))
        base = _generate_base_order(supplier_id=payload["supplier_id"])
        base["product"] = payload.get("product", base["product"])
        base["region"] = payload.get("region", base["region"])
        base["causality_chain"] = f"DELAY→STOCKOUT (supplier {payload['supplier_id']})"
        base = _inject_anomaly(base, force_type="STOCKOUT")
        return OrderEvent.model_validate(base)

    # ── Normal event generation ──────────────────────────────────────────────
    base = _generate_base_order()
    supplier_id = base["supplier_id"]
    state = _get_supplier_state(supplier_id)

    # CRITICAL/DEGRADING suppliers have elevated anomaly rates
    effective_rate = ANOMALY_RATE
    if state == "CRITICAL":
        effective_rate = min(ANOMALY_RATE * 3.0, 0.60)
    elif state == "DEGRADING":
        effective_rate = min(ANOMALY_RATE * 1.8, 0.35)

    if random.random() < effective_rate:
        base = _inject_anomaly(base)
    else:
        _maybe_recover_supplier(supplier_id)
        base["supplier_health"] = state

    return OrderEvent.model_validate(base)


def create_producer() -> KafkaProducer:
    """Create and return a Kafka producer with JSON serialization."""
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        retries=3,
        max_in_flight_requests_per_connection=1,
    )


def run_producer() -> NoReturn:
    """Run the producer loop, sending events at target rate."""
    producer = create_producer()
    interval_seconds = 60.0 / EVENTS_PER_MINUTE
    logger.info(
        "Starting producer: %s events/min, anomaly rate %.1f%%, topic=%s",
        EVENTS_PER_MINUTE,
        ANOMALY_RATE * 100,
        KAFKA_TOPIC,
    )

    def shutdown(signum: int, frame: object) -> None:
        logger.info("Shutting down producer...")
        producer.flush()
        producer.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    sent = 0
    while True:
        try:
            event = generate_event()
            payload = event.model_dump(mode="json")
            valid, err = _validate_event(payload)
            if not valid:
                logger.warning("Schema validation failed, skipping event: %s", err)
                continue
            key = event.order_id
            producer.send(KAFKA_TOPIC, value=payload, key=key)
            sent += 1

            # 3% chance: emit a preemptive DEMAND_SPIKE for this product/region
            if random.random() < 0.03:
                demand = DemandEvent(
                    product=event.product,
                    region=event.region,
                    forecast_delta_pct=round(random.uniform(25.0, 60.0), 1),
                    current_inventory_days=round(random.uniform(3.0, 21.0), 1),
                    signal_source=random.choice(["POS", "WEATHER", "MACRO", "PRODUCER_SIM"]),
                )
                demand_payload = demand.model_dump(mode="json")
                valid, err = _validate_event(demand_payload)
                if not valid:
                    logger.warning("Schema validation failed for DEMAND_SPIKE, skipping: %s", err)
                else:
                    producer.send(KAFKA_TOPIC, value=demand_payload, key=None)
                logger.debug(
                    "DEMAND_SPIKE: %s %s +%.0f%%",
                    demand.product, demand.region, demand.forecast_delta_pct,
                )

            if sent % 50 == 0:
                logger.info("Sent %d events", sent)
        except (ValidationError, KafkaError) as e:
            logger.exception("Failed to send event (skipping, pipeline continues): %s", e)
            # Do not re-raise — a single bad event must not crash the producer loop.
            # The event is logged above; downstream DLQ will handle persistent failures.

        time.sleep(interval_seconds)

    producer.flush()
    producer.close()


if __name__ == "__main__":
    run_producer()
