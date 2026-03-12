"""
Ontology constraints API router.

Provides:
  GET  /ontology/constraints       — list hard constraints per entity
  POST /ontology/constraints       — create a new constraint
  POST /ontology/normalize         — map messy field names to canonical schema (Auger-style)
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import OntologyConstraint
from api.schemas import OntologyConstraintRead

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Canonical field name mapping (messy → internal) ───────────────────────────
# Maps dozens of real-world variants to the internal supply chain schema field names.
_FIELD_MAP: dict[str, str] = {
    # Order identification
    "order_number": "order_id",
    "po_number": "order_id",
    "purchase_order": "order_id",
    "po": "order_id",
    "order": "order_id",

    # Supplier
    "vendor": "supplier_id",
    "vendor_id": "supplier_id",
    "supplier": "supplier_id",
    "plant": "supplier_id",
    "plant_code": "supplier_id",
    "manufacturer": "supplier_id",
    "mfr": "supplier_id",

    # Product
    "sku": "product",
    "item": "product",
    "part_number": "product",
    "part_no": "product",
    "item_id": "product",
    "product_id": "product",
    "material": "product",

    # Region / location
    "destination": "region",
    "dest": "region",
    "dest_port": "region",
    "ship_to": "region",
    "delivery_location": "region",
    "location": "region",
    "country": "region",
    "market": "region",

    # Quantity
    "qty": "quantity",
    "units": "quantity",
    "unit_quant": "quantity",
    "pieces": "quantity",
    "count": "quantity",
    "volume": "quantity",

    # Price / value
    "price": "unit_price",
    "cost": "unit_price",
    "rate": "unit_price",
    "unit_cost": "unit_price",
    "total": "order_value",
    "total_value": "order_value",
    "amount": "order_value",
    "invoice_amount": "order_value",

    # Delivery dates
    "delivery_date": "expected_delivery",
    "due_date": "expected_delivery",
    "eta": "expected_delivery",
    "promised_date": "expected_delivery",
    "ship_date": "expected_delivery",
    "actual_delivery_date": "actual_delivery",
    "received_date": "actual_delivery",
    "delivery_actual": "actual_delivery",

    # Delay
    "days_late": "delay_days",
    "lateness": "delay_days",
    "overdue_days": "delay_days",
    "ship_late_day_count": "delay_days",

    # Status
    "state": "status",
    "order_status": "status",
    "shipment_status": "status",

    # Inventory
    "stock": "inventory_level",
    "stock_level": "inventory_level",
    "on_hand": "inventory_level",
    "available_qty": "inventory_level",
    "inventory": "inventory_level",

    # ── OpenBoxes / WMS field aliases ────────────────────────────────────────
    # Order identification
    "orderNumber": "order_id",
    "order_number": "order_id",
    "identifier": "order_id",
    "po_ref": "order_id",
    "purchase_order_no": "order_id",
    "docname": "order_id",

    # Supplier (OpenBoxes nests supplier as 'origin' — flattened to originName)
    "originName": "supplier_id",
    "originId": "supplier_id",
    "supplier_name": "supplier_id",
    "vendor_code": "supplier_id",
    "party": "supplier_id",

    # Product (OpenBoxes uses productCode inside orderItems)
    "productCode": "product",
    "productName": "product",
    "item_code": "product",
    "item_name": "product",
    "part_code": "product",
    "article_number": "product",

    # Region (OpenBoxes nests warehouse as 'destination' — flattened to destinationName)
    "destinationName": "region",
    "set_warehouse": "region",
    "warehouse": "region",
    "delivery_warehouse": "region",
    "ship_to_location": "region",

    # Order value (OpenBoxes uses totalPrice on line items)
    "totalPrice": "order_value",
    "grand_total": "order_value",
    "net_total": "order_value",
    "rounded_total": "order_value",

    # Unit price (OpenBoxes line item field)
    "unitPrice": "unit_price",
    "base_rate": "unit_price",
    "price_list_rate": "unit_price",

    # Quantity (OpenBoxes line item)
    "quantityOrdered": "quantity",
    "quantityRequested": "quantity",
    "ordered_qty": "quantity",
    "received_qty": "quantity",
    "pending_qty": "quantity",

    # Dates (OpenBoxes uses estimatedDeliveryDate / dateReceived)
    "estimatedDeliveryDate": "expected_delivery",
    "schedule_date": "expected_delivery",
    "required_date": "expected_delivery",
    "dateReceived": "actual_delivery",
    "transaction_receipt_date": "actual_delivery",
    "lr_date": "actual_delivery",

    # Delay (OpenBoxes uses daysLate)
    "daysLate": "delay_days",
    "delay_in_days": "delay_days",
    "days_overdue": "delay_days",
    "late_days": "delay_days",

    # Status
    "workflow_state": "status",
    "document_status": "status",
    "fulfillment_status": "status",

    # Inventory (OpenBoxes stock level fields)
    "currentStockLevel": "inventory_level",
    "quantityOnHand": "inventory_level",
    "actual_qty": "inventory_level",
    "projected_qty": "inventory_level",
    "in_stock_qty": "inventory_level",
}

_SEVERITY_WEIGHTS = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}

# Lowercase-keyed version of _FIELD_MAP for case-insensitive exact lookup
_FIELD_MAP_LOWER: dict[str, str] = {k.lower(): v for k, v in _FIELD_MAP.items()}


@router.get("/constraints", response_model=list[OntologyConstraintRead])
async def list_constraints(
    limit: int = Query(100, ge=1, le=500),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List ontology constraints (Glass-box hard rules per entity)."""
    from sqlalchemy import select
    q = select(OntologyConstraint).order_by(OntologyConstraint.id).limit(limit)
    if entity_type:
        q = q.where(OntologyConstraint.entity_type == entity_type)
    if entity_id:
        q = q.where(OntologyConstraint.entity_id == entity_id)
    result = await db.execute(q)
    constraints = result.scalars().all()
    return [OntologyConstraintRead.model_validate(c) for c in constraints]


@router.post("/constraints", response_model=OntologyConstraintRead, status_code=201)
async def create_constraint(
    entity_id: str = Body(...),
    entity_type: str = Body(..., description="SUPPLIER | PRODUCT | REGION"),
    constraint_type: str = Body(..., description="e.g. MAX_DELAY_DAYS, MIN_TRUST_SCORE, MAX_SPEND_USD"),
    value: float = Body(...),
    hard_limit: bool = Body(True),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new ontology constraint (Auger-style hard business rule).

    Examples:
      - MAX_DELAY_DAYS on supplier SUP-001, value=7.0  → auto-escalate if >7d late
      - MIN_TRUST_SCORE on supplier SUP-002, value=0.75 → block auto-execute if trust drops below
      - MAX_SPEND_USD on region APAC, value=500000     → require approval if order_value > 500k
    """
    _VALID_TYPES = {"SUPPLIER", "PRODUCT", "REGION"}
    if entity_type not in _VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"entity_type must be one of {_VALID_TYPES}")

    constraint = OntologyConstraint(
        entity_id=entity_id,
        entity_type=entity_type,
        constraint_type=constraint_type.upper(),
        value=value,
        hard_limit=hard_limit,
    )
    db.add(constraint)
    await db.commit()
    await db.refresh(constraint)
    return OntologyConstraintRead.model_validate(constraint)


@router.post("/normalize")
async def normalize_fields(
    fields: dict[str, Any] = Body(
        ...,
        examples=[{
            "po_number": "ORD-001",
            "vendor": "SUP-007",
            "sku": "SENSOR-PACK-A",
            "qty": 500,
            "eta": "2026-04-15",
            "ship_late_day_count": 3,
        }],
    ),
) -> dict[str, Any]:
    """
    Auger-style schema normalization: map messy / legacy field names to canonical
    internal schema fields.

    Returns:
      - normalized: dict with canonical field names
      - unmapped: fields that had no mapping (passed through as-is)
      - mapping_applied: list of (original → canonical) substitutions made
    """
    normalized: dict[str, Any] = {}
    unmapped: dict[str, Any] = {}
    mapping_applied: list[dict[str, str]] = []

    for raw_key, value in fields.items():
        lower = raw_key.lower().strip()
        canonical = _FIELD_MAP_LOWER.get(lower)
        if canonical:
            normalized[canonical] = value
            mapping_applied.append({"from": raw_key, "to": canonical})
        else:
            # Try partial match — e.g. "order_no" → contains "order" → "order_id"
            partial_match = next(
                (canon for alias, canon in _FIELD_MAP_LOWER.items() if alias in lower or lower in alias),
                None,
            )
            if partial_match:
                normalized[partial_match] = value
                mapping_applied.append({"from": raw_key, "to": partial_match, "match": "partial"})
            else:
                unmapped[raw_key] = value

    return {
        "normalized": normalized,
        "unmapped": unmapped,
        "mapping_applied": mapping_applied,
        "canonical_fields": sorted(set(_FIELD_MAP.values())),
    }
