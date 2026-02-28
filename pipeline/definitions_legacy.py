"""Legacy Kafka-based pipeline definitions."""

from dagster import Definitions, ScheduleDefinition

from pipeline.assets import (
    raw_orders,
    cleaned_orders,
    modeled_orders,
    deviation_detection,
    supplier_risk_scores,
)
from pipeline.sensors import new_kafka_messages_sensor
from pipeline.jobs import hourly_pipeline_job, stream_processing_job

all_assets = [raw_orders, cleaned_orders, modeled_orders, deviation_detection, supplier_risk_scores]

defs = Definitions(
    assets=all_assets,
    jobs=[hourly_pipeline_job, stream_processing_job],
    schedules=[
        ScheduleDefinition(job=hourly_pipeline_job, cron_schedule="0 * * * *", name="hourly_pipeline"),
        ScheduleDefinition(job=stream_processing_job, cron_schedule="*/5 * * * *", name="stream_processing"),
    ],
    sensors=[new_kafka_messages_sensor],
)
