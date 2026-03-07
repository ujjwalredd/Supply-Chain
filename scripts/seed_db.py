#!/usr/bin/env python3
"""
Seed database with realistic supply chain data.
Idempotent: safe to run multiple times — uses merge/upsert throughout.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models import Base, Deviation, OntologyConstraint, Order, PendingAction, Supplier

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://supplychain:supplychain_secret@localhost:5432/supply_chain_db",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Realistic supplier data
SUPPLIERS_DATA = [
    ("SUP-001", "Alpha Components Inc.",     "NA",   0.92, 245, 20,  1.2),
    ("SUP-002", "Beta Manufacturing GmbH",   "EMEA", 0.88, 310, 37,  2.1),
    ("SUP-003", "Gamma Logistics Asia",       "APAC", 0.95, 180, 9,   0.5),
    ("SUP-004", "Delta Supplies LATAM",       "LATAM",0.72, 275, 77,  4.8),
    ("SUP-005", "Epsilon Parts Co.",          "NA",   0.83, 195, 31,  2.5),
    ("SUP-006", "Zeta Electronics",           "APAC", 0.91, 220, 18,  1.4),
    ("SUP-007", "Eta Industrial Ltd.",        "EMEA", 0.78, 140, 31,  3.2),
    ("SUP-008", "Theta Materials",            "NA",   0.96, 300, 12,  0.8),
]

PRODUCTS = [
    "WIDGET-A", "WIDGET-B", "GADGET-X", "GADGET-Y",
    "COMPONENT-101", "COMPONENT-202", "RAW-STEEL-1",
    "CIRCUIT-BOARD-A", "MOTOR-UNIT-B", "SENSOR-PACK-C",
]

REGIONS_BY_SUPPLIER = {
    "NA":   "NA",
    "EMEA": "EMEA",
    "APAC": "APAC",
    "LATAM": "LATAM",
}


def seed() -> None:
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        # ── Suppliers ────────────────────────────────────────────────────────
        for sid, name, region, trust, total, delayed, avg_d in SUPPLIERS_DATA:
            db.merge(Supplier(
                supplier_id=sid,
                name=name,
                region=region,
                trust_score=trust,
                total_orders=total,
                delayed_orders=delayed,
                avg_delay_days=avg_d,
                contract_terms={
                    "max_delay_days": 7,
                    "payment_terms": "NET30",
                    "penalty_per_day": 500,
                },
                capacity_limits={"max_monthly_orders": 60, "max_order_value": 500_000},
            ))
        db.flush()

        # ── Orders ───────────────────────────────────────────────────────────
        base_ts = datetime.now(timezone.utc)
        orders_added = 0
        order_ids_for_deviations: list[str] = []

        statuses = ["PENDING", "IN_TRANSIT", "DELIVERED", "DELAYED", "CANCELLED"]

        for i in range(120):
            order_id = f"ORD-{base_ts.strftime('%Y%m%d')}-{i+1:06d}"
            if db.get(Order, order_id):
                continue

            sup = SUPPLIERS_DATA[i % len(SUPPLIERS_DATA)]
            exp = base_ts + timedelta(days=5 + (i % 15))
            delay = 0
            if i % 5 == 2:
                delay = 3
            elif i % 7 == 3:
                delay = 9
            elif i % 11 == 5:
                delay = 16

            actual = (exp + timedelta(days=delay)) if delay else None
            if delay > 0:
                status = "DELAYED"
            elif i < 60:
                status = "DELIVERED"
            elif i < 90:
                status = "IN_TRANSIT"
            else:
                status = "PENDING"

            qty = 50 + i * 5
            unit_p = 20.0 + i * 0.8
            inv = max(0.5, 80.0 - (delay * 12))

            o = Order(
                order_id=order_id,
                supplier_id=sup[0],
                product=PRODUCTS[i % len(PRODUCTS)],
                region=sup[2],
                quantity=qty,
                unit_price=round(unit_p, 2),
                order_value=round(qty * unit_p, 2),
                expected_delivery=exp,
                actual_delivery=actual,
                delay_days=delay,
                status=status,
                inventory_level=round(inv, 1),
            )
            db.add(o)
            orders_added += 1

            if delay > 0 or inv < 10:
                order_ids_for_deviations.append(order_id)

        db.flush()

        # ── Deviations (only for orders we just inserted) ───────────────────
        devs_added = 0
        for j, oid in enumerate(order_ids_for_deviations[:20]):
            dev_id = f"DEV-SEED-{j+1:04d}"
            if db.get(Deviation, dev_id):
                continue
            o = db.get(Order, oid)
            if not o:
                continue

            if o.delay_days > 14:
                sev = "CRITICAL"
                dtype = "DELAY"
                action = f"Critical: escalate {oid} to supplier {o.supplier_id} — {o.delay_days}d overdue"
            elif o.delay_days > 7:
                sev = "HIGH"
                dtype = "DELAY"
                action = f"Expedite {oid}: {o.delay_days}d delay. Contact {o.supplier_id}."
            elif o.delay_days > 0:
                sev = "MEDIUM"
                dtype = "DELAY"
                action = f"Monitor {oid}: minor delay of {o.delay_days}d from {o.supplier_id}"
            elif o.inventory_level < 5:
                sev = "HIGH"
                dtype = "STOCKOUT"
                action = f"Emergency restock {o.product} — inventory at {o.inventory_level:.1f}%"
            else:
                sev = "MEDIUM"
                dtype = "STOCKOUT"
                action = f"Schedule restock for {o.product} (inventory {o.inventory_level:.1f}%)"

            db.add(Deviation(
                deviation_id=dev_id,
                order_id=oid,
                type=dtype,
                severity=sev,
                detected_at=base_ts - timedelta(hours=j * 2),
                recommended_action=action,
                executed=(j >= 10),
            ))
            devs_added += 1

        db.flush()

        # ── PendingActions (for executed deviations) ─────────────────────────
        actions_added = 0
        for j in range(10, min(15, len(order_ids_for_deviations))):
            dev_id = f"DEV-SEED-{j+1:04d}"
            dev = db.get(Deviation, dev_id)
            if not dev:
                continue
            # Check if action already exists
            from sqlalchemy import select
            existing = db.execute(
                select(PendingAction).where(PendingAction.deviation_id == dev_id)
            ).scalar_one_or_none()
            if existing:
                continue
            db.add(PendingAction(
                deviation_id=dev_id,
                action_type="EXECUTE_RECOMMENDATION",
                description=dev.recommended_action or "AI recommendation executed",
                payload={"deviation_type": dev.type, "severity": dev.severity},
                status="COMPLETED",
                completed_at=base_ts - timedelta(hours=j),
            ))
            actions_added += 1

        # ── Ontology Constraints ─────────────────────────────────────────────
        constraints = [
            (1, "*",      "GLOBAL",    "max_delay_days",             7.0,  True),
            (2, "*",      "GLOBAL",    "min_inventory_level",        20.0, True),
            (3, "*",      "GLOBAL",    "max_single_supplier_pct",    40.0, True),
            (4, "SUP-004","SUPPLIER",  "max_delay_rate_pct",         15.0, True),
            (5, "SUP-007","SUPPLIER",  "max_delay_rate_pct",         20.0, True),
            (6, "*",      "GLOBAL",    "anomaly_value_threshold",    100000.0, False),
            (7, "LATAM",  "REGION",    "max_avg_delay_days",         5.0,  False),
        ]
        for cid, eid, etype, ctype, val, hard in constraints:
            db.merge(OntologyConstraint(
                id=cid,
                entity_id=eid,
                entity_type=etype,
                constraint_type=ctype,
                value=val,
                hard_limit=hard,
            ))

        db.commit()

        if orders_added == 0 and devs_added == 0 and actions_added == 0:
            print("Database already seeded. Skipping.")
        else:
            print(
                f"Seeded: {orders_added} orders, {devs_added} deviations, "
                f"{actions_added} actions, {len(SUPPLIERS_DATA)} suppliers (merged), "
                f"{len(constraints)} ontology constraints (merged)."
            )


if __name__ == "__main__":
    seed()
