"""
OpenBoxes Connector — polls OpenBoxes Purchase Orders and Stock Movements,
normalizes field names via the ontology layer, and publishes canonical ORDER
events to Kafka.

OpenBoxes is a free, open-source supply chain management system with a REST
API. Use the public demo or a self-hosted Docker instance.

Demo (no account needed):
    OPENBOXES_URL=https://demo.openboxes.com/openboxes
    OPENBOXES_USERNAME=admin
    OPENBOXES_PASSWORD=password

Self-hosted:
    docker run -p 8080:8080 openboxes/openboxes:latest
    OPENBOXES_URL=http://localhost:8080/openboxes

Modes
-----
OPENBOXES_MOCK=true  (default, no server needed)
    Generates realistic OpenBoxes-formatted payloads locally.

OPENBOXES_MOCK=false
    Polls a real OpenBoxes instance and fetches live Purchase Orders and
    Stock Movements.

Flow
----
OpenBoxes PO/Shipment (messy nested JSON)
  └─► flatten()                 — extract flat dict with OpenBoxes field names
  └─► normalize_fields()        — POST /ontology/normalize → canonical names
  └─► build_order_event()       — map to OrderEvent schema + status mapping
  └─► publish_to_kafka()        — supply-chain-events topic
"""

import json
import logging
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("openboxes-connector")

# ── Configuration ─────────────────────────────────────────────────────────────

OPENBOXES_URL = os.getenv("OPENBOXES_URL", "https://demo.openboxes.com/openboxes")
OPENBOXES_USERNAME = os.getenv("OPENBOXES_USERNAME", "admin")
OPENBOXES_PASSWORD = os.getenv("OPENBOXES_PASSWORD", "password")
OPENBOXES_MOCK = os.getenv("OPENBOXES_MOCK", "true").lower() == "true"

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "supply-chain-events")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")

POLL_INTERVAL = int(os.getenv("OPENBOXES_POLL_INTERVAL", "30"))
BATCH_SIZE = int(os.getenv("OPENBOXES_BATCH_SIZE", "25"))

# ── OpenBoxes status → canonical status ──────────────────────────────────────

_STATUS_MAP: dict[str, str] = {
    "PENDING": "PENDING",
    "PLACED": "PENDING",
    "PARTIALLY_RECEIVED": "IN_TRANSIT",
    "RECEIVED": "DELIVERED",
    "SHIPPED": "IN_TRANSIT",
    "COMPLETED": "DELIVERED",
    "CANCELLED": "CANCELLED",
    "REJECTED": "CANCELLED",
    "ROLLBACK": "CANCELLED",
    "CHECKING": "IN_TRANSIT",
    "DELIVERING": "IN_TRANSIT",
}

# ── Mock data ─────────────────────────────────────────────────────────────────

_MOCK_SUPPLIERS = [
    ("SUP-001", "Apex Medical Supplies"),
    ("SUP-002", "Global Health Partners"),
    ("SUP-003", "Pacific Distribution Ltd"),
    ("SUP-004", "Nordic Logistics AG"),
    ("SUP-005", "Delta Medical Corp"),
]
_MOCK_PRODUCTS = [
    {"productCode": "OB-SENS-001", "name": "Temperature Sensor Pack"},
    {"productCode": "OB-PUMP-002", "name": "Infusion Pump Unit"},
    {"productCode": "OB-GLOVE-L", "name": "Latex Gloves (Large, 100ct)"},
    {"productCode": "OB-MASK-N95", "name": "N95 Respirator Mask"},
    {"productCode": "OB-SYRN-5ML", "name": "5mL Syringe Box"},
    {"productCode": "OB-BAND-STD", "name": "Standard Bandage Roll"},
]
_MOCK_LOCATIONS = ["Boston - Main", "APAC - Regional DC", "NYC - Port WH", "LA - Distribution", "Chicago - HUB"]
_MOCK_STATUSES = list(_STATUS_MAP.keys())

_mock_counter = 0


def _mock_purchase_orders(batch_size: int) -> list[dict[str, Any]]:
    """
    Generate OpenBoxes-style Purchase Order dicts with realistic nested structure.
    Field names match the OpenBoxes REST API response format exactly.
    """
    global _mock_counter
    import random

    orders = []
    for _ in range(batch_size):
        _mock_counter += 1
        sup_id, sup_name = random.choice(_MOCK_SUPPLIERS)
        product = random.choice(_MOCK_PRODUCTS)
        qty = random.randint(50, 2000)
        unit_price = round(random.uniform(5.0, 250.0), 2)
        total_price = round(qty * unit_price, 2)
        delay = random.randint(0, 10)
        estimated_delivery = (datetime.now(timezone.utc) + timedelta(days=random.randint(7, 45))).date().isoformat()
        actual_delivery = None
        if random.random() < 0.35:
            actual_delivery = (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 3))).date().isoformat()
        destination = random.choice(_MOCK_LOCATIONS)
        status = random.choice(_MOCK_STATUSES)
        inventory = round(random.uniform(5.0, 95.0), 1)

        # OpenBoxes REST API field names — nested, different from our canonical schema
        orders.append({
            "id": f"OB-{uuid.uuid4().hex[:8]}",
            "orderNumber": f"OB-PO-{_mock_counter:05d}",    # not order_id
            "status": status,
            "dateOrdered": datetime.now(timezone.utc).date().isoformat(),
            "estimatedDeliveryDate": estimated_delivery,      # not expected_delivery
            "dateReceived": actual_delivery,                  # not actual_delivery
            "origin": {                                       # nested supplier
                "id": sup_id,
                "name": sup_name,
            },
            "destination": {                                  # nested region
                "id": f"LOC-{_mock_counter}",
                "name": destination,
            },
            "orderItems": [                                   # nested line items
                {
                    "id": f"ITEM-{_mock_counter}",
                    "product": {
                        "id": f"PROD-{_mock_counter}",
                        "productCode": product["productCode"],  # not product
                        "name": product["name"],
                    },
                    "quantity": qty,                           # same
                    "unitPrice": unit_price,                   # not unit_price in flat form
                    "totalPrice": total_price,                 # not order_value
                }
            ],
            "daysLate": delay,                                # not delay_days
            "currentStockLevel": inventory,                   # not inventory_level
            "sourceSystem": "OPENBOXES_MOCK",
        })
    return orders


# ── Real OpenBoxes API ────────────────────────────────────────────────────────

def _ob_auth() -> tuple[str, str]:
    return (OPENBOXES_USERNAME, OPENBOXES_PASSWORD)


def _assert_json(resp: requests.Response, endpoint: str) -> dict[str, Any]:
    """
    Raise a descriptive error if the server returned HTML instead of JSON.
    OpenBoxes redirects unauthenticated requests to an HTML login page — this
    catches that before json() blows up with a misleading parse error.
    """
    ct = resp.headers.get("Content-Type", "")
    if "text/html" in ct or resp.text.lstrip().startswith("<!"):
        raise ValueError(
            f"{endpoint} returned HTML (likely auth redirect). "
            "Check OPENBOXES_USERNAME / OPENBOXES_PASSWORD or use OPENBOXES_MOCK=true."
        )
    return resp.json()


def _fetch_purchase_orders(page: int = 0) -> list[dict[str, Any]]:
    """Fetch Purchase Orders from live OpenBoxes instance."""
    try:
        resp = requests.get(
            f"{OPENBOXES_URL}/api/generic/purchaseOrders",
            auth=_ob_auth(),
            headers={"Accept": "application/json"},
            params={"max": BATCH_SIZE, "offset": page * BATCH_SIZE, "status": "PENDING,PLACED,PARTIALLY_RECEIVED"},
            timeout=15,
        )
        resp.raise_for_status()
        data = _assert_json(resp, "purchaseOrders")
        pos = data.get("data", [])
        logger.info("Fetched %d Purchase Orders from OpenBoxes (page=%d)", len(pos), page)
        return pos
    except Exception as e:
        logger.error("OpenBoxes PO fetch error: %s", e)
        return []


def _fetch_stock_movements() -> list[dict[str, Any]]:
    """Fetch active Stock Movements (shipments) from live OpenBoxes."""
    try:
        resp = requests.get(
            f"{OPENBOXES_URL}/api/stockMovements",
            auth=_ob_auth(),
            headers={"Accept": "application/json"},
            params={"max": BATCH_SIZE, "receiptStatusCode": "SHIPPED,CHECKING,DELIVERING"},
            timeout=15,
        )
        resp.raise_for_status()
        data = _assert_json(resp, "stockMovements")
        movements = data.get("data", [])
        logger.info("Fetched %d Stock Movements from OpenBoxes", len(movements))
        return movements
    except Exception as e:
        logger.error("OpenBoxes stock movement fetch error: %s", e)
        return []


# ── Field flattening ─────────────────────────────────────────────────────────

def _flatten_po(po: dict[str, Any]) -> dict[str, Any]:
    """
    Flatten a nested OpenBoxes Purchase Order dict so all fields are top-level,
    ready for the ontology normalizer.

    OpenBoxes nests supplier under 'origin', region under 'destination',
    and product/price under 'orderItems[0]'.
    """
    flat: dict[str, Any] = {}

    for k, v in po.items():
        if k not in ("origin", "destination", "orderItems"):
            flat[k] = v

    # Flatten origin (supplier)
    origin = po.get("origin") or {}
    flat["originId"] = origin.get("id", "")
    flat["originName"] = origin.get("name", "")

    # Flatten destination (region/warehouse)
    dest = po.get("destination") or {}
    flat["destinationName"] = dest.get("name", "")

    # Flatten first line item
    items = po.get("orderItems") or []
    if items:
        item = items[0]
        product = item.get("product") or {}
        flat["productCode"] = product.get("productCode", "")
        flat["productName"] = product.get("name", "")
        flat["quantityOrdered"] = item.get("quantity", 1)
        flat["unitPrice"] = item.get("unitPrice", 0.0)
        flat["totalPrice"] = item.get("totalPrice", 0.0)

    return flat


def _flatten_movement(mv: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Stock Movement dict for ontology normalization."""
    flat: dict[str, Any] = {}

    for k, v in mv.items():
        if k not in ("origin", "destination", "lineItems"):
            flat[k] = v

    origin = mv.get("origin") or {}
    flat["originName"] = origin.get("name", "")

    dest = mv.get("destination") or {}
    flat["destinationName"] = dest.get("name", "")

    items = mv.get("lineItems") or []
    if items:
        item = items[0]
        product = item.get("product") or {}
        flat["productCode"] = product.get("productCode", "")
        flat["quantityOrdered"] = item.get("quantityRequested", 1)

    return flat


# ── Ontology normalization ────────────────────────────────────────────────────

def _normalize(flat: dict[str, Any]) -> dict[str, Any]:
    """
    POST to /ontology/normalize to map OpenBoxes field names → canonical schema.
    Falls back to passthrough if the API is unavailable.
    """
    try:
        resp = requests.post(
            f"{API_BASE}/ontology/normalize",
            json=flat,
            timeout=5,
        )
        if resp.ok:
            result = resp.json()
            normalized = result.get("normalized", {})
            unmapped = result.get("unmapped", {})
            mappings_count = len(result.get("mapping_applied", []))
            logger.debug("Normalized %d fields (%d mappings applied)", len(normalized), mappings_count)
            return {**unmapped, **normalized}
    except Exception as e:
        logger.warning("Ontology normalize unavailable (%s) — using raw fields.", e)
    return flat


# ── Build OrderEvent ──────────────────────────────────────────────────────────

def _build_order_event(po: dict[str, Any], raw_status: str) -> Optional[dict[str, Any]]:
    """
    Map a normalized (canonical) flat dict to an OrderEvent-compatible payload.
    Returns None if required fields are missing.
    """
    order_id = (
        po.get("order_id")
        or po.get("orderNumber")
        or po.get("identifier")
        or f"OB-{uuid.uuid4().hex[:8]}"
    )
    supplier_id = (
        po.get("supplier_id")
        or po.get("originId")
        or po.get("originName", "UNKNOWN")
    )
    product = (
        po.get("product")
        or po.get("productCode")
        or po.get("productName", "UNKNOWN")
    )
    region_raw = (
        po.get("region")
        or po.get("destinationName")
        or "UNKNOWN"
    )
    region = region_raw.split(" - ")[0].strip()

    quantity = int(po.get("quantity") or po.get("quantityOrdered", 1))
    unit_price = float(po.get("unit_price") or po.get("unitPrice", 0.0))
    order_value = float(
        po.get("order_value")
        or po.get("totalPrice")
        or (unit_price * quantity)
    )
    expected_delivery = po.get("expected_delivery") or po.get("estimatedDeliveryDate", "")
    actual_delivery = po.get("actual_delivery") or po.get("dateReceived")
    delay_days = int(po.get("delay_days") or po.get("daysLate", 0))
    inventory_level = float(po.get("inventory_level") or po.get("currentStockLevel", 50.0))

    # Map OpenBoxes status → canonical status
    status = _STATUS_MAP.get(raw_status, "PENDING")
    if delay_days > 0 and status not in ("CANCELLED",):
        status = "DELAYED"

    if not product or not supplier_id:
        logger.warning("Skipping record %s — missing product/supplier", order_id)
        return None

    return {
        "order_id": order_id,
        "supplier_id": supplier_id,
        "product": product,
        "region": region or "UNKNOWN",
        "quantity": max(1, quantity),
        "unit_price": round(unit_price, 2),
        "order_value": round(order_value, 2),
        "expected_delivery": expected_delivery or datetime.now(timezone.utc).date().isoformat(),
        "actual_delivery": actual_delivery,
        "delay_days": max(0, delay_days),
        "status": status,
        "inventory_level": max(0.0, min(100.0, inventory_level)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event_type": "ORDER",
        "supplier_health": (
            "NORMAL" if delay_days == 0 else
            "DEGRADING" if delay_days < 7 else
            "CRITICAL"
        ),
        "causality_chain": f"OPENBOXES_IMPORT (source={po.get('sourceSystem', 'OPENBOXES')})",
    }


# ── Kafka publish ─────────────────────────────────────────────────────────────

def _get_producer(max_attempts: int = 10, backoff: float = 5.0):
    from kafka import KafkaProducer
    import time
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
            )
            logger.info("Kafka producer connected on attempt %d", attempt)
            return producer
        except Exception as e:
            last_err = e
            logger.warning(
                "Kafka not ready (attempt %d/%d): %s — retrying in %.0fs",
                attempt, max_attempts, e, backoff,
            )
            time.sleep(backoff)
    raise RuntimeError(f"Kafka unavailable after {max_attempts} attempts: {last_err}")


# ── Main loop ─────────────────────────────────────────────────────────────────

_shutdown = False


def _signal_handler(sig, frame):
    global _shutdown
    logger.info("Shutdown signal received — finishing current batch.")
    _shutdown = True


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def run() -> None:
    global OPENBOXES_MOCK  # may be updated to True on auto-fallback below
    logger.info(
        "OpenBoxes connector starting | mode=%s url=%s kafka=%s topic=%s",
        "MOCK" if OPENBOXES_MOCK else "LIVE",
        OPENBOXES_URL if not OPENBOXES_MOCK else "N/A",
        KAFKA_BOOTSTRAP_SERVERS,
        KAFKA_TOPIC,
    )

    # Verify connectivity to real OpenBoxes before starting
    if not OPENBOXES_MOCK:
        try:
            # OpenBoxes doesn't expose /api/ping on all versions; probe the
            # generic orders list endpoint with Accept: application/json.
            # A 200 JSON response means auth worked; HTML means login redirect.
            resp = requests.get(
                f"{OPENBOXES_URL}/api/generic/purchaseOrders",
                auth=_ob_auth(),
                headers={"Accept": "application/json"},
                params={"max": 1},
                timeout=10,
            )
            ct = resp.headers.get("Content-Type", "")
            if resp.ok and "text/html" not in ct and not resp.text.lstrip().startswith("<!"):
                logger.info("OpenBoxes connection verified (live mode): %s", OPENBOXES_URL)
            else:
                raise ValueError(
                    f"Server returned {'HTML login page' if 'text/html' in ct else f'HTTP {resp.status_code}'}. "
                    "Basic auth may not be accepted — falling back to mock mode. "
                    "To fix: ensure OPENBOXES_USERNAME/PASSWORD are correct, or use OPENBOXES_MOCK=true."
                )
        except Exception as e:
            logger.warning("OpenBoxes connectivity check failed (%s) — falling back to mock mode.", e)
            OPENBOXES_MOCK = True

    producer = _get_producer()
    total_published = 0

    try:
        while not _shutdown:
            records: list[dict[str, Any]] = []

            if OPENBOXES_MOCK:
                import random
                records = _mock_purchase_orders(random.randint(4, 12))
            else:
                # Fetch both Purchase Orders and Stock Movements
                pos = _fetch_purchase_orders()
                movements = _fetch_stock_movements()
                records = pos + movements

            if not records:
                logger.debug("No new records — waiting %ds", POLL_INTERVAL)
                time.sleep(POLL_INTERVAL)
                continue

            batch_count = 0
            for record in records:
                raw_status = record.get("status", "PENDING")

                # Flatten nested JSON → top-level dict
                flat = (
                    _flatten_po(record)
                    if "orderNumber" in record or "orderItems" in record
                    else _flatten_movement(record)
                )

                # Normalize field names via ontology API
                normalized = _normalize(flat)

                # Build canonical OrderEvent
                event = _build_order_event(normalized, raw_status)
                if event is None:
                    continue

                producer.send(KAFKA_TOPIC, key=event["order_id"], value=event)
                batch_count += 1

            producer.flush(timeout=10)
            total_published += batch_count
            logger.info(
                "Batch complete: published=%d | total=%d | mode=%s",
                batch_count, total_published,
                "MOCK" if OPENBOXES_MOCK else "LIVE",
            )

            time.sleep(POLL_INTERVAL)

    finally:
        producer.flush(timeout=10)
        producer.close()
        logger.info("OpenBoxes connector stopped. Total published: %d", total_published)


if __name__ == "__main__":
    run()
