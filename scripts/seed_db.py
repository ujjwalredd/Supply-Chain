#!/usr/bin/env python3
"""Seed database with sample orders, suppliers, deviations, and ontology constraints."""

import os
import sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.models import Base, Order, Supplier, Deviation, OntologyConstraint

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://supplychain:supplychain_secret@localhost:5432/supply_chain_db",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def seed() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        suppliers_data = [
            ("SUP-001", "Alpha Components", "NA", 0.92, 100, 8, 1.2),
            ("SUP-002", "Beta Manufacturing", "EMEA", 0.88, 150, 18, 2.1),
            ("SUP-003", "Gamma Logistics", "APAC", 0.95, 80, 4, 0.5),
            ("SUP-004", "Delta Supplies", "LATAM", 0.75, 120, 30, 3.5),
            ("SUP-005", "Epsilon Parts", "NA", 0.82, 90, 16, 2.0),
        ]

        # Use merge (upsert) so re-runs are idempotent
        for sid, name, region, trust, total, delayed, avg_d in suppliers_data:
            db.merge(
                Supplier(
                    supplier_id=sid,
                    name=name,
                    region=region,
                    trust_score=trust,
                    total_orders=total,
                    delayed_orders=delayed,
                    avg_delay_days=avg_d,
                )
            )

        base = datetime.utcnow()
        orders_added = 0
        for i in range(50):
            order_id = f"ORD-{base.strftime('%Y%m%d')}-{i+1:06d}"
            if db.get(Order, order_id):
                continue
            exp = base + timedelta(days=5 + i % 10)
            delay = i % 5 == 2 and 3 or (i % 7 == 3 and 8 or 0)
            actual = exp + timedelta(days=delay) if delay else None
            status = "DELAYED" if delay > 0 else ("DELIVERED" if i < 25 else "IN_TRANSIT")
            o = Order(
                order_id=order_id,
                supplier_id=suppliers_data[i % 5][0],
                product=f"WIDGET-{chr(65 + i % 5)}",
                region=suppliers_data[i % 5][2],
                quantity=100 + i * 10,
                unit_price=25.0 + i * 0.5,
                order_value=(100 + i * 10) * (25.0 + i * 0.5),
                expected_delivery=exp,
                actual_delivery=actual,
                delay_days=delay,
                status=status,
                inventory_level=30.0 + i % 50,
            )
            db.add(o)
            orders_added += 1

        deviations_added = 0
        for i in range(10):
            dev_id = f"DEV-{i+1:04d}"
            if db.get(Deviation, dev_id):
                continue
            order_id = f"ORD-{base.strftime('%Y%m%d')}-{(i * 5 + 2):06d}"
            db.add(
                Deviation(
                    deviation_id=dev_id,
                    order_id=order_id,
                    type="DELAY" if i % 2 == 0 else "STOCKOUT",
                    severity="HIGH" if i % 3 == 0 else "MEDIUM",
                    detected_at=base - timedelta(hours=i),
                    recommended_action="Escalate to supplier" if i % 2 == 0 else "Replenish inventory",
                    executed=i >= 5,
                )
            )
            deviations_added += 1

        # Ontology constraints: merge so re-runs are safe
        db.merge(OntologyConstraint(
            id=1,
            entity_id="*",
            entity_type="GLOBAL",
            constraint_type="max_delay_days",
            value=7,
            hard_limit=True,
        ))
        db.merge(OntologyConstraint(
            id=2,
            entity_id="*",
            entity_type="GLOBAL",
            constraint_type="min_inventory_level",
            value=20,
            hard_limit=True,
        ))
        db.merge(OntologyConstraint(
            id=3,
            entity_id="SUP-004",
            entity_type="SUPPLIER",
            constraint_type="max_delay_rate_pct",
            value=15,
            hard_limit=True,
        ))

        db.commit()
        if orders_added == 0 and deviations_added == 0:
            print("Database already fully seeded. Skipping.")
        else:
            print(f"Seeded: {orders_added} orders, {deviations_added} deviations, suppliers (merged), ontology constraints (merged).")


if __name__ == "__main__":
    seed()
