"""Dagster jobs for medallion pipeline."""

from dagster import define_asset_job

medallion_full_job = define_asset_job(
    name="medallion_full_pipeline",
    selection="*",
    description="Full medallion pipeline: bronze → silver → gold",
)

medallion_incremental_job = define_asset_job(
    name="medallion_incremental",
    selection=["bronze_orders", "silver_orders", "gold_orders_ai_ready"],
    description="Incremental: bronze + silver + gold orders only",
)
