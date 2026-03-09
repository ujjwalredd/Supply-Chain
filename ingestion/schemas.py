"""Pydantic schemas for supply chain events."""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class OrderEvent(BaseModel):
    """Schema for supplier order events streamed to Kafka."""

    order_id: str = Field(..., description="Unique order identifier")
    supplier_id: str = Field(..., description="Supplier identifier")
    product: str = Field(..., description="Product SKU or name")
    region: str = Field(..., description="Delivery region")
    quantity: int = Field(..., ge=1, description="Order quantity")
    unit_price: float = Field(..., ge=0, description="Unit price")
    order_value: float = Field(..., ge=0, description="Total order value")
    expected_delivery: str = Field(..., description="ISO date of expected delivery")
    actual_delivery: Optional[str] = Field(None, description="ISO date of actual delivery")
    delay_days: int = Field(0, ge=0, description="Days delayed (0 if on time)")
    status: str = Field(
        ...,
        description="Order status",
    )
    inventory_level: float = Field(..., ge=0, le=100, description="Inventory level %")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Event timestamp",
    )
    event_type: str = Field(
        default="ORDER",
        description="Event type for routing",
    )
    # Causality chain enrichment (set by producer when a DELAY triggers a downstream STOCKOUT)
    causality_chain: Optional[str] = Field(None, description="e.g. 'DELAY→STOCKOUT (supplier SUP-001)'")
    # Supplier health state from producer state machine: NORMAL | DEGRADING | CRITICAL
    supplier_health: Optional[str] = Field(None, description="Supplier state: NORMAL | DEGRADING | CRITICAL")

    model_config = {"extra": "ignore"}


class DemandEvent(BaseModel):
    """Schema for upstream demand signal events (preemptive deviation detection)."""

    event_type: str = Field(default="DEMAND_SPIKE", description="Event type for routing")
    product: str = Field(..., description="Product SKU")
    region: str = Field(..., description="Affected region")
    forecast_delta_pct: float = Field(
        ..., description="% change in demand forecast vs baseline (positive = spike)"
    )
    current_inventory_days: float = Field(
        default=14.0, description="Days of inventory cover at current stock"
    )
    signal_source: str = Field(
        default="PRODUCER_SIM",
        description="Signal origin: POS | WEATHER | MACRO | PRODUCER_SIM",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Event timestamp",
    )

    model_config = {"extra": "ignore"}


class DeviationEvent(BaseModel):
    """Schema for detected deviation events."""

    deviation_id: str = Field(..., description="Unique deviation identifier")
    order_id: str = Field(..., description="Related order ID")
    type: str = Field(..., description="DELAY | STOCKOUT | ANOMALY")
    severity: str = Field(..., description="LOW | MEDIUM | HIGH | CRITICAL")
    detected_at: str = Field(..., description="ISO timestamp")
    message: Optional[str] = Field(None, description="Human-readable description")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)
