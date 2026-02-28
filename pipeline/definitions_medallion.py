"""Dagster Definitions - Medallion pipeline (bronze → silver → gold)."""

from dagster import Definitions, ScheduleDefinition

from pipeline.assets_medallion import (
    bronze_orders,
    silver_orders,
    gold_orders_ai_ready,
    gold_deviations,
    gold_supplier_risk,
    # Feature 1: additional source datasets
    bronze_freight_rates,
    bronze_wh_capacities,
    bronze_plant_ports,
    bronze_products_per_plant,
    silver_freight_rates,
    silver_wh_capacities,
    # Feature 2: dbt transforms
    dbt_transforms,
    # Feature 3: quality gate
    quality_gate_silver_orders,
    # Feature 5: forecasting
    gold_forecasted_risks,
)
from pipeline.jobs_medallion import medallion_full_job, medallion_incremental_job

all_assets = [
    bronze_orders,
    silver_orders,
    gold_orders_ai_ready,
    gold_deviations,
    gold_supplier_risk,
    bronze_freight_rates,
    bronze_wh_capacities,
    bronze_plant_ports,
    bronze_products_per_plant,
    silver_freight_rates,
    silver_wh_capacities,
    quality_gate_silver_orders,
    dbt_transforms,
    gold_forecasted_risks,
]

defs = Definitions(
    assets=all_assets,
    jobs=[medallion_full_job, medallion_incremental_job],
    schedules=[
        ScheduleDefinition(
            job=medallion_full_job,
            cron_schedule="0 */6 * * *",  # Every 6 hours
            name="medallion_full_schedule",
        ),
    ],
)
