#!/usr/bin/env python3
"""
Sync gold layer (Delta Lake) to PostgreSQL for API and dashboard.

Runs after medallion pipeline. Loads gold/orders_ai_ready and gold/deviations
into operational DB. If gold is missing (no Dagster run yet), falls back to
bronze/orders so the dashboard has data after download + batch_loader.

Idempotent: uses INSERT ... ON CONFLICT DO NOTHING — safe to re-run any time.
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

GOLD_PATH = Path(os.getenv("GOLD_PATH", "data/gold"))
BRONZE_PATH = Path(os.getenv("BRONZE_PATH", "data/bronze"))
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://supplychain:supplychain_secret@localhost:5432/supply_chain_db",
)


def _upsert_df(df, table: str, pk: str, engine) -> int:
    """
    Upsert a DataFrame into a Postgres table using ON CONFLICT DO NOTHING.
    Returns the number of rows actually inserted (skips duplicates silently).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy import MetaData, Table

    if df.empty:
        return 0

    meta = MetaData()
    meta.reflect(bind=engine, only=[table])
    tbl = Table(table, meta)

    import pandas as pd

    # Replace NaT / NaN with None so psycopg2 serialises them as SQL NULL
    df = df.where(df.notna(), other=None)

    records = df.to_dict(orient="records")
    # Convert any remaining pandas/numpy scalars to Python natives
    clean = []
    for row in records:
        clean.append({
            k: (None if (v is pd.NaT or (isinstance(v, float) and v != v)) else v)
            for k, v in row.items()
        })

    inserted = 0
    with engine.begin() as conn:
        for chunk_start in range(0, len(clean), 500):
            chunk = clean[chunk_start : chunk_start + 500]
            stmt = pg_insert(tbl).values(chunk).on_conflict_do_nothing(index_elements=[pk])
            result = conn.execute(stmt)
            inserted += result.rowcount
    return inserted


def _build_orders_df(df) -> "pd.DataFrame":
    """Normalise a raw DataFrame into the orders table schema."""
    import pandas as pd

    cols = [
        "order_id", "supplier_id", "product", "region",
        "quantity", "order_value", "delay_days", "status", "inventory_level",
    ]
    df_out = df[[c for c in cols if c in df.columns]].copy()

    # Derive missing columns
    df_out["expected_delivery"] = pd.to_datetime(
        df.get("expected_delivery", pd.NaT), errors="coerce"
    )
    df_out["actual_delivery"] = pd.NaT
    qty = df["quantity"].replace(0, 1) if "quantity" in df.columns else 1
    df_out["unit_price"] = (df["order_value"] / qty) if "order_value" in df.columns else 10.0
    df_out["created_at"] = pd.Timestamp.now("UTC")

    df_out = df_out.dropna(subset=["order_id"])
    df_out["order_id"] = df_out["order_id"].astype(str)

    # Fill null expected_delivery so NOT NULL is satisfied
    default_ts = pd.Timestamp.now("UTC")
    df_out["expected_delivery"] = df_out["expected_delivery"].fillna(default_ts)

    # Ensure timezone-aware datetimes for TIMESTAMP WITH TIME ZONE columns
    for col in ["expected_delivery", "actual_delivery", "created_at"]:
        if col not in df_out.columns:
            continue
        if not pd.api.types.is_datetime64_any_dtype(df_out[col]):
            continue
        try:
            if df_out[col].dt.tz is None:
                df_out[col] = df_out[col].dt.tz_localize("UTC", ambiguous="NaT")
            else:
                df_out[col] = df_out[col].dt.tz_convert("UTC")
        except Exception:
            pass

    # Fill defaults for required integer/float columns
    for col, default in [("quantity", 1), ("delay_days", 0), ("inventory_level", 0.0)]:
        if col in df_out.columns:
            df_out[col] = df_out[col].fillna(default)

    df_out["status"] = df_out.get("status", "UNKNOWN").fillna("UNKNOWN") if "status" in df_out.columns else "UNKNOWN"

    return df_out


def _sync_bronze_orders(engine) -> int:
    """Fallback: sync bronze/orders to Postgres when gold not yet built."""
    orders_path = BRONZE_PATH / "orders"
    if not orders_path.exists():
        logger.info(
            "No bronze data at %s — run download + batch_loader first",
            orders_path.resolve(),
        )
        return 0

    import pandas as pd

    df = None
    try:
        from deltalake import DeltaTable
        dt = DeltaTable(str(orders_path))
        df = dt.to_pyarrow_table().to_pandas()
    except Exception:
        pass

    if df is None:
        parquet_file = orders_path / "data.parquet"
        if parquet_file.exists():
            df = pd.read_parquet(parquet_file)
        else:
            parquet_files = list(orders_path.glob("*.parquet"))
            if parquet_files:
                df = pd.concat([pd.read_parquet(p) for p in parquet_files], ignore_index=True)

    if df is None or df.empty:
        logger.warning("Could not read bronze/orders as Delta or Parquet")
        return 0

    df_out = _build_orders_df(df)
    inserted = _upsert_df(df_out, "orders", "order_id", engine)
    skipped = len(df_out) - inserted
    logger.info(
        "Bronze sync: %d inserted, %d skipped (already exist) from %d rows",
        inserted, skipped, len(df_out),
    )
    return inserted


def sync() -> int:
    """Sync gold Delta tables to Postgres. Fully idempotent."""
    try:
        import pandas as pd
        from sqlalchemy import create_engine
    except ImportError:
        logger.error("Missing deps: pip install pandas sqlalchemy psycopg2-binary")
        return 1

    engine = create_engine(DATABASE_URL)

    orders_path = GOLD_PATH / "orders_ai_ready"
    deviations_path = GOLD_PATH / "deviations"
    supplier_risk_path = GOLD_PATH / "supplier_risk"

    total = 0

    def _read_gold(path: Path) -> "pd.DataFrame | None":
        """Read gold layer: Parquet first (new format), Delta fallback (legacy)."""
        parquet_file = path / "data.parquet"
        if parquet_file.exists():
            return pd.read_parquet(parquet_file)
        # Delta fallback
        try:
            from deltalake import DeltaTable
            return DeltaTable(str(path)).to_pyarrow_table().to_pandas()
        except Exception:
            return None

    # --- Orders ---
    if orders_path.exists():
        try:
            df = _read_gold(orders_path)
            if df is not None and not df.empty:
                df_out = _build_orders_df(df)
                inserted = _upsert_df(df_out, "orders", "order_id", engine)
                skipped = len(df_out) - inserted
                logger.info("Orders: %d inserted, %d skipped (already exist)", inserted, skipped)
                total += inserted
        except Exception as e:
            logger.warning("Could not sync gold/orders_ai_ready: %s", e)

    # --- Deviations ---
    if deviations_path.exists():
        try:
            df = _read_gold(deviations_path)
            if df is not None and not df.empty:
                cols = ["deviation_id", "order_id", "severity"]
                df_out = df[[c for c in cols if c in df.columns]].copy()
                df_out["type"] = df["deviation_type"] if "deviation_type" in df.columns else "DELAY"
                df_out["detected_at"] = pd.Timestamp.now("UTC")
                df_out["executed"] = False
                df_out["created_at"] = pd.Timestamp.now("UTC")
                for col in ["detected_at", "created_at"]:
                    if df_out[col].dt.tz is None:
                        df_out[col] = df_out[col].dt.tz_localize("UTC")
                inserted = _upsert_df(df_out, "deviations", "deviation_id", engine)
                skipped = len(df_out) - inserted
                logger.info("Deviations: %d inserted, %d skipped", inserted, skipped)
                total += inserted
        except Exception as e:
            logger.warning("Could not sync gold/deviations: %s", e)

    # --- Supplier risk ---
    if supplier_risk_path.exists():
        try:
            df = _read_gold(supplier_risk_path)
            if df is not None and not df.empty:
                df["name"] = df.get("supplier_id", "")
                df["region"] = "NA"
                df["contract_terms"] = None
                df["capacity_limits"] = None
                df["created_at"] = pd.Timestamp.now("UTC")
                df["updated_at"] = pd.Timestamp.now("UTC")
                keep = [
                    "supplier_id", "name", "region", "trust_score",
                    "total_orders", "delayed_orders", "avg_delay_days",
                    "contract_terms", "capacity_limits", "created_at", "updated_at",
                ]
                df_out = df[[c for c in keep if c in df.columns]].copy()
                inserted = _upsert_df(df_out, "suppliers", "supplier_id", engine)
                skipped = len(df_out) - inserted
                logger.info("Suppliers: %d inserted, %d skipped", inserted, skipped)
        except Exception as e:
            logger.warning("Could not sync gold/supplier_risk: %s", e)

    # --- Bronze fallback ---
    if total == 0 and not orders_path.exists():
        total = _sync_bronze_orders(engine)

    logger.info("Sync complete. Total new rows inserted: %d", total)
    return 0


if __name__ == "__main__":
    sys.exit(sync())
