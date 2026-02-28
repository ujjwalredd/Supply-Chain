"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class OrderBase(BaseModel):
    order_id: str
    supplier_id: str
    product: str
    region: str
    quantity: int
    unit_price: float
    order_value: float
    expected_delivery: datetime
    actual_delivery: Optional[datetime] = None
    delay_days: int = 0
    status: str
    inventory_level: float


class OrderRead(OrderBase):
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierBase(BaseModel):
    supplier_id: str
    name: str
    region: str
    trust_score: float = 1.0
    total_orders: int = 0
    delayed_orders: int = 0
    avg_delay_days: float = 0.0
    contract_terms: Optional[dict[str, Any]] = None
    capacity_limits: Optional[dict[str, Any]] = None


class SupplierRead(SupplierBase):
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierRisk(BaseModel):
    supplier_id: str
    name: str
    region: str
    trust_score: float
    total_orders: int
    delayed_orders: int
    delay_rate_pct: float


class DeviationBase(BaseModel):
    deviation_id: str
    order_id: str
    type: str
    severity: str
    detected_at: datetime
    ai_analysis: Optional[dict[str, Any]] = None
    recommended_action: Optional[str] = None
    executed: bool = False


class DeviationRead(DeviationBase):
    created_at: datetime

    model_config = {"from_attributes": True}


class OntologyConstraintBase(BaseModel):
    entity_id: str
    entity_type: str
    constraint_type: str
    value: float
    hard_limit: bool = True


class OntologyConstraintRead(OntologyConstraintBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAnalysisRequest(BaseModel):
    deviation_id: str
    order_id: Optional[str] = None
    deviation_type: str = "DELAY"
    severity: str = "MEDIUM"
    context: Optional[dict[str, Any]] = None


class AIAnalysisStructured(BaseModel):
    root_cause: str
    financial_impact: str
    options: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: str
    autonomous_executable: bool = False


class PendingActionCreate(BaseModel):
    deviation_id: str
    action_type: str
    description: str
    payload: Optional[dict[str, Any]] = None


class PendingActionRead(BaseModel):
    id: int
    deviation_id: str
    action_type: str
    description: str
    payload: Optional[dict[str, Any]] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ForecastedRisk(BaseModel):
    order_id: str
    supplier_id: str
    days_to_delivery: float
    risk_reason: str
    alt_carrier: Optional[str] = None
    alt_min_cost: Optional[float] = None
    alt_transit_days: Optional[float] = None


class NetworkNode(BaseModel):
    id: str
    label: str
    type: str  # plant | port | supplier


class NetworkEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None


class NetworkGraph(BaseModel):
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]
