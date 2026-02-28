"""Pydantic schemas for supply chain events."""

from datetime import datetime
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
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="Event timestamp",
    )
    event_type: str = Field(
        default="ORDER",
        description="Event type for routing",
    )

    model_config = {"extra": "forbid"}


class DeviationEvent(BaseModel):
    """Schema for detected deviation events."""

    deviation_id: str = Field(..., description="Unique deviation identifier")
    order_id: str = Field(..., description="Related order ID")
    type: str = Field(..., description="DELAY | STOCKOUT | ANOMALY")
    severity: str = Field(..., description="LOW | MEDIUM | HIGH | CRITICAL")
    detected_at: str = Field(..., description="ISO timestamp")
    message: Optional[str] = Field(None, description="Human-readable description")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)
