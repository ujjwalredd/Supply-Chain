"""Dagster job definitions."""

from dagster import define_asset_job

# Full pipeline: all assets, hourly
hourly_pipeline_job = define_asset_job(
    name="hourly_supply_chain_pipeline",
    selection="*",
)

# Stream processing: raw + cleaned + deviation detection, every 5 min
stream_processing_job = define_asset_job(
    name="stream_processing",
    selection=["raw_orders", "cleaned_orders", "deviation_detection"],
)
