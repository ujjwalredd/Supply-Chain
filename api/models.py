"""SQLAlchemy models for operational database."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


class Order(Base):
    """Orders from suppliers."""

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(String(32), index=True)
    product: Mapped[str] = mapped_column(String(128), index=True)
    region: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    order_value: Mapped[float] = mapped_column(Float)
    expected_delivery: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actual_delivery: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delay_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True)
    inventory_level: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    deviations = relationship("Deviation", back_populates="order")


class Supplier(Base):
    """Supplier metadata and trust scores."""

    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    region: Mapped[str] = mapped_column(String(32))
    trust_score: Mapped[float] = mapped_column(Float, default=1.0)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    delayed_orders: Mapped[int] = mapped_column(Integer, default=0)
    avg_delay_days: Mapped[float] = mapped_column(Float, default=0.0)
    contract_terms: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    capacity_limits: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Deviation(Base):
    """Detected deviations (delays, stockouts, anomalies)."""

    __tablename__ = "deviations"

    deviation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), ForeignKey("orders.order_id"), index=True)
    type: Mapped[str] = mapped_column(String(32))  # DELAY | STOCKOUT | ANOMALY
    severity: Mapped[str] = mapped_column(String(32))  # LOW | MEDIUM | HIGH | CRITICAL
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ai_analysis: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    order = relationship("Order", back_populates="deviations")


class OntologyConstraint(Base):
    """Auger-style ontology: hard constraints per entity."""

    __tablename__ = "ontology_constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))  # SUPPLIER | PRODUCT | REGION
    constraint_type: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float)
    hard_limit: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PendingAction(Base):
    """Feature 4: AI-recommended actions queued for execution."""

    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deviation_id: Mapped[str] = mapped_column(String(64), ForeignKey("deviations.deviation_id"), index=True)
    action_type: Mapped[str] = mapped_column(String(64))  # REROUTE | EXPEDITE | SAFETY_STOCK | NOTIFY
    description: Mapped[str] = mapped_column(Text)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")  # PENDING | COMPLETED | CANCELLED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
