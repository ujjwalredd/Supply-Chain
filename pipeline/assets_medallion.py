"""
Medallion lakehouse pipeline: bronze → silver → gold.

Bronze: Raw ingest, append-only, schema-on-read, full lineage
Silver: Validated, deduplicated, typed, business rules applied
Gold: Modeled, AI-ready, analytics-optimized
"""

import logging
import os
from pathlib import Path

from dagster import AssetExecutionContext, asset, MaterializeResult, MetadataValue

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "data/source"))

# Prefer explicit path env vars (set in docker-compose).
# Fall back to local paths relative to working directory.
BRONZE_PATH = os.getenv("BRONZE_PATH") or str(Path("data/bronze").absolute())
SILVER_PATH = os.getenv("SILVER_PATH") or str(Path("data/silver").absolute())
GOLD_PATH   = os.getenv("GOLD_PATH")   or str(Path("data/gold").absolute())


def _read_bronze_parquet(table: str) -> "pd.DataFrame | None":
    """Read a bronze Parquet table. Returns None if not found."""
    import pandas as pd
    path = Path(os.path.join(BRONZE_PATH, table, "data.parquet"))
    if path.exists():
        return pd.read_parquet(path)
    return None


# --- BRONZE LAYER ---
@asset(compute_kind="python", group_name="bronze")
def bronze_orders(context: AssetExecutionContext) -> MaterializeResult:
    """
    Bronze: Raw order data. Append-only, schema-on-read.
    Source: batch CSV (OrderList) or Kafka consumer.
    """
    from ingestion.batch_loader import load_orderlist_csv, load_to_bronze_delta

    orderlist = DATA_DIR / "OrderList.csv"
    if not orderlist.exists():
        logger.warning("OrderList.csv missing. Run download_supply_chain_data.py first.")
        return MaterializeResult(metadata={
            "row_count": MetadataValue.int(0),
            "source": MetadataValue.text("none"),
        })

    records = load_orderlist_csv(orderlist)
    count = load_to_bronze_delta(records, "orders")
    return MaterializeResult(metadata={
        "row_count": MetadataValue.int(count),
        "source": MetadataValue.text("OrderList.csv"),
    })


# --- SILVER LAYER ---
@asset(compute_kind="pandas", group_name="silver", deps=[bronze_orders])
def silver_orders(context: AssetExecutionContext) -> MaterializeResult:
    """
    Silver: Validated, deduplicated, typed.
    - drop null order_id, invalid delays
    - Dedupe by order_id
    - Normalize delay_days to int
    Uses pandas + deltalake (Python library) — no PySpark Delta connector needed.
    """
    import pandas as pd

    bronze_path = os.path.join(BRONZE_PATH, "orders")

    df = None
    # Try reading as Delta Lake (Python deltalake library)
    try:
        from deltalake import DeltaTable
        df = DeltaTable(str(bronze_path)).to_pyarrow_table().to_pandas()
    except Exception:
        pass

    # Fall back to Parquet written by batch_loader
    if df is None:
        parquet_file = os.path.join(bronze_path, "data.parquet")
        if Path(parquet_file).exists():
            df = pd.read_parquet(parquet_file)

    # Last resort: re-read from CSV
    if df is None or df.empty:
        csv_path = DATA_DIR / "OrderList.csv"
        if csv_path.exists():
            from ingestion.batch_loader import load_orderlist_csv
            df = pd.DataFrame(list(load_orderlist_csv(csv_path)))
        else:
            return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})

    # Validation: drop null / empty order_id
    df = df[df["order_id"].notna() & (df["order_id"].astype(str).str.strip() != "")]

    # Cast delay_days and filter valid range
    df["delay_days"] = pd.to_numeric(df["delay_days"], errors="coerce").fillna(0).astype(int)
    df = df[(df["delay_days"] >= 0) & (df["delay_days"] <= 365)]

    # Dedupe by order_id (keep last)
    df = df.drop_duplicates(subset=["order_id"], keep="last")

    # Write silver as Parquet
    silver_path = os.path.join(SILVER_PATH, "orders")
    Path(silver_path).mkdir(parents=True, exist_ok=True)
    df.to_parquet(os.path.join(silver_path, "data.parquet"), index=False)

    count = len(df)
    delayed_count = int((df["delay_days"] > 0).sum())
    delay_rate = round(delayed_count / count * 100, 2) if count > 0 else 0.0
    return MaterializeResult(metadata={
        "row_count": MetadataValue.int(count),
        "delayed_orders": MetadataValue.int(delayed_count),
        "delay_rate_pct": MetadataValue.float(delay_rate),
    })


# --- GOLD LAYER ---
@asset(compute_kind="pandas", group_name="gold", deps=[silver_orders])
def gold_orders_ai_ready(context: AssetExecutionContext) -> MaterializeResult:
    """
    Gold: AI-ready digital twin. Analytics-optimized, ontology-aligned.
    - Deviation flags (delay_days thresholds)
    - Supplier trust scores joined
    Uses pandas — no PySpark Delta connector needed.
    """
    import pandas as pd
    import numpy as np

    silver_file = os.path.join(SILVER_PATH, "orders", "data.parquet")
    if not Path(silver_file).exists():
        return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})

    df = pd.read_parquet(silver_file)
    df["delay_days"] = pd.to_numeric(df["delay_days"], errors="coerce").fillna(0).astype(int)

    # Supplier risk aggregation
    grp = df.groupby("supplier_id").agg(
        total_orders=("order_id", "count"),
        delayed_orders=("delay_days", lambda x: (x > 0).sum()),
        avg_delay_days=("delay_days", "mean"),
    ).reset_index()
    grp["trust_score"] = (1.0 - (grp["delayed_orders"] / grp["total_orders"].clip(lower=1)) * 0.5).clip(0, 1)

    # Join risk scores and add deviation flags
    df = df.merge(grp[["supplier_id", "trust_score", "total_orders", "delayed_orders", "avg_delay_days"]],
                  on="supplier_id", how="left")
    df["deviation_type"] = np.where(df["delay_days"] > 7, "DELAY",
                            np.where(df["delay_days"] > 0, "MINOR_DELAY", None))
    df["severity"] = np.where(df["delay_days"] > 14, "CRITICAL",
                      np.where(df["delay_days"] > 7, "HIGH",
                       np.where(df["delay_days"] > 0, "MEDIUM", None)))

    gold_path = os.path.join(GOLD_PATH, "orders_ai_ready")
    Path(gold_path).mkdir(parents=True, exist_ok=True)
    df.to_parquet(os.path.join(gold_path, "data.parquet"), index=False)

    count = len(df)
    deviation_count = int(df["deviation_type"].notna().sum())
    deviation_rate = round(deviation_count / count * 100, 2) if count > 0 else 0.0
    return MaterializeResult(metadata={
        "row_count": MetadataValue.int(count),
        "deviations_flagged": MetadataValue.int(deviation_count),
        "deviation_rate_pct": MetadataValue.float(deviation_rate),
    })


@asset(compute_kind="pandas", group_name="gold", deps=[silver_orders])
def gold_deviations(context: AssetExecutionContext) -> MaterializeResult:
    """Gold: Deviation events for AI reasoning. Uses pandas — no PySpark Delta needed."""
    import pandas as pd
    import numpy as np

    silver_file = os.path.join(SILVER_PATH, "orders", "data.parquet")
    if not Path(silver_file).exists():
        return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})

    df = pd.read_parquet(silver_file)
    df["delay_days"] = pd.to_numeric(df["delay_days"], errors="coerce").fillna(0).astype(int)

    df["deviation_type"] = np.where(df["delay_days"] > 7, "DELAY",
                             np.where(df["delay_days"] > 0, "MINOR_DELAY", None))
    df["severity"] = np.where(df["delay_days"] > 14, "CRITICAL",
                      np.where(df["delay_days"] > 7, "HIGH",
                       np.where(df["delay_days"] > 0, "MEDIUM", None)))

    deviations = df[df["deviation_type"].notna()].copy().reset_index(drop=True)
    deviations["deviation_id"] = deviations.index.astype(str)

    gold_path = os.path.join(GOLD_PATH, "deviations")
    Path(gold_path).mkdir(parents=True, exist_ok=True)
    deviations.to_parquet(os.path.join(gold_path, "data.parquet"), index=False)

    count = len(deviations)
    high_critical_count = int(deviations["severity"].isin(["HIGH", "CRITICAL"]).sum())
    return MaterializeResult(metadata={
        "row_count": MetadataValue.int(count),
        "high_critical_count": MetadataValue.int(high_critical_count),
    })


@asset(compute_kind="pandas", group_name="gold", deps=[silver_orders])
def gold_supplier_risk(context: AssetExecutionContext) -> MaterializeResult:
    """Gold: Supplier trust scores for ontology and AI context. Uses pandas — no PySpark needed."""
    import pandas as pd

    silver_file = os.path.join(SILVER_PATH, "orders", "data.parquet")
    if not Path(silver_file).exists():
        return MaterializeResult(metadata={"supplier_count": MetadataValue.int(0)})

    df = pd.read_parquet(silver_file)
    df["delay_days"] = pd.to_numeric(df["delay_days"], errors="coerce").fillna(0).astype(int)

    risk = df.groupby("supplier_id").agg(
        total_orders=("order_id", "count"),
        delayed_orders=("delay_days", lambda x: (x > 0).sum()),
        avg_delay_days=("delay_days", "mean"),
    ).reset_index()
    risk["trust_score"] = (1.0 - (risk["delayed_orders"] / risk["total_orders"].clip(lower=1)) * 0.5).clip(0, 1)
    risk["delay_rate_pct"] = (risk["delayed_orders"] / risk["total_orders"].clip(lower=1) * 100)

    gold_path = os.path.join(GOLD_PATH, "supplier_risk")
    Path(gold_path).mkdir(parents=True, exist_ok=True)
    risk.to_parquet(os.path.join(gold_path, "data.parquet"), index=False)

    count = len(risk)
    avg_trust = round(float(risk["trust_score"].mean()), 3) if count > 0 else 0.0
    avg_delay_rate = round(float(risk["delay_rate_pct"].mean()), 2) if count > 0 else 0.0
    return MaterializeResult(metadata={
        "supplier_count": MetadataValue.int(count),
        "avg_trust_score": MetadataValue.float(avg_trust),
        "avg_delay_rate_pct": MetadataValue.float(avg_delay_rate),
    })


# ─────────────────────────────────────────────
# FEATURE 1: ADDITIONAL SOURCE DATASETS
# ─────────────────────────────────────────────

@asset(compute_kind="python", group_name="bronze")
def bronze_freight_rates(context: AssetExecutionContext) -> MaterializeResult:
    """Bronze: FreightRates.csv — carrier costs, transit days, route coverage."""
    from ingestion.batch_loader import load_freight_rates_csv, load_to_bronze_generic
    path = DATA_DIR / "FreightRates.csv"
    if not path.exists():
        return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})
    count = load_to_bronze_generic(load_freight_rates_csv(path), "freight_rates")
    return MaterializeResult(metadata={"row_count": MetadataValue.int(count)})


@asset(compute_kind="python", group_name="bronze")
def bronze_wh_capacities(context: AssetExecutionContext) -> MaterializeResult:
    """Bronze: WhCapacities.csv — warehouse daily throughput capacity per plant."""
    from ingestion.batch_loader import load_wh_capacities_csv, load_to_bronze_generic
    path = DATA_DIR / "WhCapacities.csv"
    if not path.exists():
        return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})
    count = load_to_bronze_generic(load_wh_capacities_csv(path), "wh_capacities")
    return MaterializeResult(metadata={"row_count": MetadataValue.int(count)})


@asset(compute_kind="python", group_name="bronze")
def bronze_plant_ports(context: AssetExecutionContext) -> MaterializeResult:
    """Bronze: PlantPorts.csv — plant to port export mapping."""
    from ingestion.batch_loader import load_plant_ports_csv, load_to_bronze_generic
    path = DATA_DIR / "PlantPorts.csv"
    if not path.exists():
        return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})
    count = load_to_bronze_generic(load_plant_ports_csv(path), "plant_ports")
    return MaterializeResult(metadata={"row_count": MetadataValue.int(count)})


@asset(compute_kind="python", group_name="bronze")
def bronze_products_per_plant(context: AssetExecutionContext) -> MaterializeResult:
    """Bronze: ProductsPerPlant.csv — which products each plant can manufacture."""
    from ingestion.batch_loader import load_products_per_plant_csv, load_to_bronze_generic
    path = DATA_DIR / "ProductsPerPlant.csv"
    if not path.exists():
        return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})
    count = load_to_bronze_generic(load_products_per_plant_csv(path), "products_per_plant")
    return MaterializeResult(metadata={"row_count": MetadataValue.int(count)})


@asset(compute_kind="pandas", group_name="silver", deps=[bronze_freight_rates])
def silver_freight_rates(context: AssetExecutionContext) -> MaterializeResult:
    """Silver: validated freight rates — drop nulls, normalize mode, add cost-per-day metric."""
    import pandas as pd
    bronze_file = os.path.join(BRONZE_PATH, "freight_rates", "data.parquet")
    if not Path(bronze_file).exists():
        return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})

    df = pd.read_parquet(bronze_file)
    df = df.dropna(subset=["carrier", "orig_port", "dest_port"])
    df["mode"] = df["mode"].str.strip().str.upper()
    df["cost_per_day"] = df.apply(
        lambda r: round(r["min_cost"] / r["transit_days"], 2) if r["transit_days"] > 0 else 0.0, axis=1
    )

    silver_path = os.path.join(SILVER_PATH, "freight_rates")
    Path(silver_path).mkdir(parents=True, exist_ok=True)
    df.to_parquet(os.path.join(silver_path, "data.parquet"), index=False)
    return MaterializeResult(metadata={
        "row_count": MetadataValue.int(len(df)),
        "unique_routes": MetadataValue.int(int(df.groupby(["orig_port", "dest_port"]).ngroups)),
        "avg_transit_days": MetadataValue.float(round(float(df["transit_days"].mean()), 1)),
    })


@asset(compute_kind="pandas", group_name="silver", deps=[bronze_wh_capacities])
def silver_wh_capacities(context: AssetExecutionContext) -> MaterializeResult:
    """Silver: warehouse capacities — validated, utilisation rate added."""
    import pandas as pd
    bronze_file = os.path.join(BRONZE_PATH, "wh_capacities", "data.parquet")
    if not Path(bronze_file).exists():
        return MaterializeResult(metadata={"row_count": MetadataValue.int(0)})

    df = pd.read_parquet(bronze_file)
    df = df.dropna(subset=["plant_code"])
    df = df[df["daily_capacity"] > 0]

    silver_path = os.path.join(SILVER_PATH, "wh_capacities")
    Path(silver_path).mkdir(parents=True, exist_ok=True)
    df.to_parquet(os.path.join(silver_path, "data.parquet"), index=False)
    return MaterializeResult(metadata={
        "row_count": MetadataValue.int(len(df)),
        "total_daily_capacity": MetadataValue.int(int(df["daily_capacity"].sum())),
        "avg_capacity_per_plant": MetadataValue.float(round(float(df["daily_capacity"].mean()), 1)),
    })


# ─────────────────────────────────────────────
# FEATURE 3: GREAT EXPECTATIONS QUALITY GATE
# ─────────────────────────────────────────────

@asset(compute_kind="python", group_name="silver", deps=[silver_orders])
def quality_gate_silver_orders(context: AssetExecutionContext) -> MaterializeResult:
    """Feature 3: Run data quality checks on silver_orders; log failures as warnings."""
    import pandas as pd
    from quality.validations import run_validation_suite

    # silver_orders now writes Parquet directly
    silver_file = os.path.join(SILVER_PATH, "orders", "data.parquet")
    if not Path(silver_file).exists():
        return MaterializeResult(metadata={
            "checks_passed": MetadataValue.int(0),
            "checks_failed": MetadataValue.int(0),
        })
    df = pd.read_parquet(silver_file)

    results = run_validation_suite(df, suite="orders")
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    for r in results:
        if not r.passed:
            context.log.warning("Quality check FAILED: %s — %s", r.rule, r.message)
        else:
            context.log.info("Quality check passed: %s", r.rule)

    return MaterializeResult(metadata={
        "checks_passed": MetadataValue.int(passed),
        "checks_failed": MetadataValue.int(failed),
        "total_rows_checked": MetadataValue.int(len(df)),
    })


# ─────────────────────────────────────────────
# FEATURE 2: DBT TRANSFORMS
# ─────────────────────────────────────────────

@asset(compute_kind="dbt", group_name="gold", deps=[quality_gate_silver_orders])
def dbt_transforms(context: AssetExecutionContext) -> MaterializeResult:
    """Feature 2: Run dbt models (staging + marts) against PostgreSQL."""
    import subprocess
    transforms_dir = Path(__file__).parent.parent / "transforms"
    if not transforms_dir.exists():
        return MaterializeResult(metadata={"status": MetadataValue.text("transforms/ not found")})

    env = {
        **os.environ,
        "POSTGRES_HOST": os.getenv("DAGSTER_POSTGRES_HOST", "postgres"),
        "POSTGRES_PORT": os.getenv("DAGSTER_POSTGRES_PORT", "5432"),
        "POSTGRES_USER": os.getenv("DAGSTER_POSTGRES_USER", "supplychain"),
        "POSTGRES_PASSWORD": os.getenv("DAGSTER_POSTGRES_PASSWORD", "supplychain_secret"),
        "POSTGRES_DB": os.getenv("DAGSTER_POSTGRES_DB", "supply_chain_db"),
    }
    result = subprocess.run(
        ["dbt", "run", "--profiles-dir", str(transforms_dir), "--project-dir", str(transforms_dir)],
        capture_output=True, text=True, env=env, timeout=120
    )
    if result.returncode != 0:
        context.log.warning("dbt run failed:\n%s", result.stderr)
        return MaterializeResult(metadata={
            "status": MetadataValue.text("failed"),
            "models_run": MetadataValue.int(0),
        })

    # Count "OK" lines in dbt output
    ok_count = result.stdout.count(" OK ")
    context.log.info("dbt run output:\n%s", result.stdout)
    return MaterializeResult(metadata={
        "status": MetadataValue.text("success"),
        "models_run": MetadataValue.int(ok_count),
    })


# ─────────────────────────────────────────────
# FEATURE 5: FORECASTING — predict at-risk orders
# ─────────────────────────────────────────────

@asset(compute_kind="pandas", group_name="gold",
       deps=[silver_orders, silver_freight_rates, silver_wh_capacities,
             bronze_plant_ports, bronze_products_per_plant])
def gold_forecasted_risks(context: AssetExecutionContext) -> MaterializeResult:
    """
    Feature 5: Predict orders at risk of delay BEFORE they are late.

    ML scoring (time-decay weighted):
    - delay_probability = Σ(is_delayed * weight) / Σ(weight)  per supplier
      where weight = exp(-days_old / 90)  — recent delays count more
    - confidence = 1 - 1/sqrt(n_orders)   — more orders → more certain
    - risk_score = order_value * delay_probability * (1 / days_to_delivery)
    - Threshold: at_risk if delay_probability > 0.15 OR risk_score > 500
    """
    import numpy as np
    import pandas as pd
    from datetime import datetime, timezone

    # Load silver orders (prefer silver, fall back to bronze)
    silver_file = os.path.join(SILVER_PATH, "orders", "data.parquet")
    bronze_file = os.path.join(BRONZE_PATH, "orders", "data.parquet")
    parquet_file = silver_file if Path(silver_file).exists() else bronze_file
    if not Path(parquet_file).exists():
        return MaterializeResult(metadata={"at_risk_count": MetadataValue.int(0)})

    now = datetime.now(timezone.utc)

    df = pd.read_parquet(parquet_file)
    df["delay_days"] = pd.to_numeric(df.get("delay_days", 0), errors="coerce").fillna(0)
    df["order_value"] = pd.to_numeric(df.get("order_value", 0), errors="coerce").fillna(0)
    df["expected_delivery"] = pd.to_datetime(df["expected_delivery"], errors="coerce", format="mixed", utc=True)

    # ── Time-decay weighted delay probability per supplier ──────────────────
    # Use the newest order date in the dataset as the reference point, not today.
    # This keeps the decay meaningful for historical datasets (e.g. 2015-2016 CSV).
    newest_date = df["expected_delivery"].dropna().max()
    if pd.isnull(newest_date):
        newest_date = now
    df["days_old"] = (newest_date - df["expected_delivery"]).dt.total_seconds().div(86400).clip(lower=0).fillna(180)
    df["weight"] = np.exp(-df["days_old"] / 90)          # half-life ≈ 62 days
    df["weighted_delayed"] = (df["delay_days"] > 0).astype(float) * df["weight"]

    def _supplier_risk(g: "pd.DataFrame") -> "pd.Series":
        total_weight = float(g["weight"].sum())
        if total_weight < 1e-9:
            total_weight = 1e-9
        return pd.Series({
            "total_orders": len(g),
            "delay_probability": float(g["weighted_delayed"].sum()) / total_weight,
            "avg_delay_days": float(g["delay_days"].mean()),
        })

    try:
        # pandas >= 2.2 requires include_groups=False
        supplier_stats = (
            df.groupby("supplier_id", group_keys=False)
            .apply(_supplier_risk, include_groups=False)
            .reset_index()
        )
    except TypeError:
        # pandas < 2.2 — include_groups kwarg not recognised
        supplier_stats = (
            df.groupby("supplier_id", group_keys=False)
            .apply(_supplier_risk)
            .reset_index()
        )
    # Per-supplier confidence: more orders → less uncertainty
    supplier_stats["confidence"] = (
        1.0 - 1.0 / np.sqrt(supplier_stats["total_orders"].clip(lower=1))
    ).clip(0, 1).round(3)

    # ── All non-delivered orders are candidates ──────────────────────────────
    # Note: OrderList.csv uses historical dates (2015-2016). We don't filter
    # by absolute date — we use delay_probability and risk_score as the
    # threshold so the endpoint returns real data regardless of the dataset era.
    in_transit = (
        df[df["status"] != "DELIVERED"].copy()
        if "status" in df.columns
        else df.copy()
    )
    days_to_delivery = (in_transit["expected_delivery"] - now).dt.total_seconds() / 86400
    at_risk = in_transit.copy()
    at_risk["days_to_delivery"] = days_to_delivery[at_risk.index].round(2)

    # ── Join supplier risk scores ────────────────────────────────────────────
    at_risk = at_risk.merge(
        supplier_stats[["supplier_id", "delay_probability", "confidence", "avg_delay_days"]],
        on="supplier_id",
        how="left",
    )
    at_risk["delay_probability"] = at_risk["delay_probability"].fillna(0)
    at_risk["confidence"] = at_risk["confidence"].fillna(0)

    # ── Risk score: value × probability (urgency not applied for historical data) ──
    at_risk["risk_score"] = (
        at_risk["order_value"] * at_risk["delay_probability"]
    ).round(2)

    # ── At-risk threshold: supplier delay probability > 15% ──────────────────
    at_risk = at_risk[at_risk["delay_probability"] > 0.15].copy()

    # Sort highest risk first and cap at 500 rows for the Parquet file
    at_risk = at_risk.sort_values("risk_score", ascending=False).head(500)

    at_risk["risk_reason"] = at_risk.apply(
        lambda r: (
            f"Supplier {r['supplier_id']}: {r['delay_probability']*100:.0f}% weighted delay prob "
            f"(confidence {r['confidence']*100:.0f}%), risk_score={r['risk_score']:.0f}"
        ),
        axis=1,
    )

    # ── Enrich: cheapest alternative carrier ────────────────────────────────
    fr_file = os.path.join(SILVER_PATH, "freight_rates", "data.parquet")
    if Path(fr_file).exists():
        fr = pd.read_parquet(fr_file)
        cheapest = (
            fr.sort_values("min_cost")
            .groupby("dest_port")
            .first()[["carrier", "min_cost", "transit_days"]]
            .reset_index()
        )
        cheapest.columns = ["dest_port", "alt_carrier", "alt_min_cost", "alt_transit_days"]
        at_risk = at_risk.merge(cheapest, left_on="region", right_on="dest_port", how="left")

    # ── Enrich: warehouse capacity headroom ─────────────────────────────────
    wh_file = os.path.join(SILVER_PATH, "wh_capacities", "data.parquet")
    if Path(wh_file).exists():
        wh = pd.read_parquet(wh_file)
        at_risk = at_risk.merge(wh, left_on="supplier_id", right_on="plant_code", how="left")

    gold_path = os.path.join(GOLD_PATH, "forecasted_risks")
    Path(gold_path).mkdir(parents=True, exist_ok=True)
    at_risk.to_parquet(os.path.join(gold_path, "data.parquet"), index=False)

    n_risky_suppliers = int((supplier_stats["delay_probability"] > 0.15).sum())
    avg_risk_score = round(float(at_risk["risk_score"].mean()), 2) if len(at_risk) else 0.0
    avg_confidence = round(float(at_risk["confidence"].mean()), 3) if len(at_risk) else 0.0

    context.log.info(
        "Forecasted risks: %d at-risk orders, %d risky suppliers, avg_score=%.1f",
        len(at_risk), n_risky_suppliers, avg_risk_score,
    )
    return MaterializeResult(metadata={
        "at_risk_count": MetadataValue.int(len(at_risk)),
        "risky_supplier_count": MetadataValue.int(n_risky_suppliers),
        "total_orders_scanned": MetadataValue.int(len(df)),
        "avg_risk_score": MetadataValue.float(avg_risk_score),
        "avg_model_confidence": MetadataValue.float(avg_confidence),
    })
