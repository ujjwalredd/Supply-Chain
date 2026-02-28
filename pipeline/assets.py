"""
Dagster software-defined assets for supply chain pipeline.

Asset flow: raw_orders -> cleaned_orders -> modeled_orders -> deviation_detection -> supplier_risk_scores
"""

import json
import logging
import os
from typing import Any, Optional

from dagster import AssetExecutionContext, asset, MaterializeResult
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv("S3_STORAGE_BUCKET", "supply-chain-lakehouse")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT_URL", "http://localhost:9000")


def _get_spark() -> SparkSession:
    """Get or create Spark session with Delta Lake and S3 support."""
    return (
        SparkSession.builder.appName("supply-chain-pipeline")
        .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.access.key", os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"))
        .config("spark.hadoop.fs.s3a.secret.key", os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"))
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


@asset(compute_kind="pyspark", group_name="raw")
def raw_orders(context: AssetExecutionContext) -> MaterializeResult:
    """
    Ensure raw Delta Lake table exists. Kafka events are ingested by consumer.py
    which writes to this path. This asset creates the table if missing.
    """
    spark = _get_spark()
    path = f"s3a://{S3_BUCKET}/raw/orders"
    try:
        df = spark.read.format("delta").load(path)
        count = df.count()
        return MaterializeResult(metadata={"rows": str(count)})
    except Exception:
        logger.info("Raw Delta table not found, creating empty schema")
        _raw_orders_batch_fallback(context)
        return MaterializeResult(metadata={"rows": "0"})


def _raw_orders_batch_fallback(_context: AssetExecutionContext) -> None:
    """Fallback: create empty Delta table if Kafka streaming unavailable."""
    spark = _get_spark()
    schema = (
        StructType()
        .add("order_id", StringType())
        .add("supplier_id", StringType())
        .add("product", StringType())
        .add("region", StringType())
        .add("quantity", IntegerType())
        .add("unit_price", DoubleType())
        .add("order_value", DoubleType())
        .add("expected_delivery", StringType())
        .add("actual_delivery", StringType())
        .add("delay_days", IntegerType())
        .add("status", StringType())
        .add("inventory_level", DoubleType())
        .add("created_at", StringType())
    )
    df = spark.createDataFrame([], schema)
    path = f"s3a://{S3_BUCKET}/raw/orders"
    df.write.format("delta").mode("overwrite").save(path)
    logger.info("Created empty raw_orders Delta table at %s", path)


@asset(compute_kind="pyspark", group_name="cleaned", deps=[raw_orders])
def cleaned_orders(context: AssetExecutionContext) -> MaterializeResult:
    """Run Great Expectations validation, drop bad rows, write cleaned Delta table."""
    spark = _get_spark()
    raw_path = f"s3a://{S3_BUCKET}/raw/orders"
    clean_path = f"s3a://{S3_BUCKET}/cleaned/orders"

    try:
        df = spark.read.format("delta").load(raw_path)
    except Exception:
        df = spark.createDataFrame(
        [],
        "order_id STRING, supplier_id STRING, product STRING, region STRING, quantity INT, unit_price DOUBLE, order_value DOUBLE, expected_delivery STRING, actual_delivery STRING, delay_days INT, status STRING, inventory_level DOUBLE, created_at STRING",
    )

    # Great Expectations-style validation: drop nulls, invalid ranges
    from pyspark.sql.functions import col

    validated = (
        df.filter(col("order_id").isNotNull())
        .filter(col("order_id") != "")
        .filter(col("delay_days") >= 0)
        .filter(col("delay_days") <= 365)
        .filter(col("status").isin("PENDING", "IN_TRANSIT", "DELIVERED", "DELAYED", "CANCELLED"))
    )
    validated.write.format("delta").mode("overwrite").save(clean_path)
    count = validated.count()
    return MaterializeResult(metadata={"rows": str(count)})


@asset(compute_kind="dbt", group_name="modeled", deps=[cleaned_orders])
def modeled_orders(context: AssetExecutionContext) -> MaterializeResult:
    """Run dbt transformations to produce modeled layer."""
    import subprocess
    dbt_dir = os.path.join(os.path.dirname(__file__), "..", "transforms")
    result = subprocess.run(
        ["dbt", "run", "--profiles-dir", dbt_dir],
        cwd=dbt_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "DBT_PROFILES_DIR": dbt_dir},
    )
    if result.returncode != 0:
        logger.warning("dbt run failed: %s", result.stderr)
    return MaterializeResult(metadata={"dbt_exit": str(result.returncode)})


@asset(compute_kind="pyspark", group_name="analytics", deps=[modeled_orders])
def deviation_detection(context: AssetExecutionContext) -> MaterializeResult:
    """Flag anomalies using business rules: delays, stockouts, value spikes."""
    spark = _get_spark()
    clean_path = f"s3a://{S3_BUCKET}/cleaned/orders"
    try:
        df = spark.read.format("delta").load(clean_path)
    except Exception:
        return MaterializeResult(metadata={"rows": "0"})

    from pyspark.sql.functions import col, when, lit

    deviations = (
        df.withColumn(
            "deviation_type",
            when(col("delay_days") > 7, lit("DELAY"))
            .when(col("inventory_level") < 10, lit("STOCKOUT"))
            .when(col("order_value") > 100000, lit("ANOMALY"))
            .otherwise(lit(None)),
        )
        .withColumn(
            "severity",
            when(col("delay_days") > 14, lit("CRITICAL"))
            .when(col("delay_days") > 7, lit("HIGH"))
            .when(col("inventory_level") < 5, lit("HIGH"))
            .when(col("deviation_type").isNotNull(), lit("MEDIUM"))
            .otherwise(lit(None)),
        )
        .filter(col("deviation_type").isNotNull())
    )
    dev_path = f"s3a://{S3_BUCKET}/analytics/deviations"
    deviations.write.format("delta").mode("overwrite").save(dev_path)
    count = deviations.count()
    return MaterializeResult(metadata={"rows": str(count)})


@asset(compute_kind="pyspark", group_name="analytics", deps=[cleaned_orders])
def supplier_risk_scores(context: AssetExecutionContext) -> MaterializeResult:
    """Aggregate trust scores and delay rates per supplier."""
    spark = _get_spark()
    clean_path = f"s3a://{S3_BUCKET}/cleaned/orders"
    try:
        df = spark.read.format("delta").load(clean_path)
    except Exception:
        return MaterializeResult(metadata={"rows": "0"})

    from pyspark.sql.functions import col, count, sum as spark_sum, avg

    agg = (
        df.groupBy("supplier_id")
        .agg(
            count("*").alias("total_orders"),
            spark_sum(when(col("delay_days") > 0, 1).otherwise(0)).alias("delayed_orders"),
            avg(col("delay_days")).alias("avg_delay_days"),
        )
        .withColumn(
            "trust_score",
            when(col("total_orders") == 0, lit(1.0))
            .otherwise(1.0 - (col("delayed_orders") / col("total_orders")) * 0.5),
        )
    )
    risk_path = f"s3a://{S3_BUCKET}/analytics/supplier_risk"
    agg.write.format("delta").mode("overwrite").save(risk_path)
    count = agg.count()
    return MaterializeResult(metadata={"rows": str(count)})
