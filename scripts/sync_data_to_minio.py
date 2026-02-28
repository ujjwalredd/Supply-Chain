#!/usr/bin/env python3
"""
Upload local bronze/silver/gold data lake files to MinIO.

Makes the MinIO Console show the real medallion lake structure so you can
browse Parquet files, check file sizes, and verify pipeline outputs.

Usage:
    docker compose exec fastapi python scripts/sync_data_to_minio.py
"""

import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET = os.getenv("S3_STORAGE_BUCKET", "supply-chain-lakehouse")

DATA_ROOT = Path(os.getenv("DATA_ROOT", "/app/data"))
LAYERS = {
    "bronze": Path(os.getenv("BRONZE_PATH", str(DATA_ROOT / "bronze"))),
    "silver": Path(os.getenv("SILVER_PATH", str(DATA_ROOT / "silver"))),
    "gold":   Path(os.getenv("GOLD_PATH",   str(DATA_ROOT / "gold"))),
}


def get_s3_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name="us-east-1",  # MinIO ignores this but boto3 requires it
    )


def ensure_bucket(s3):
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception:
        s3.create_bucket(Bucket=BUCKET)
        logger.info("Created bucket: %s", BUCKET)


def upload_layer(s3, layer_name: str, layer_path: Path) -> int:
    if not layer_path.exists():
        logger.info("Skipping %s — path does not exist: %s", layer_name, layer_path)
        return 0

    extensions = {".parquet", ".json", ".crc", ".last_checkpoint"}
    files = [f for f in layer_path.rglob("*") if f.is_file() and f.suffix in extensions]

    if not files:
        logger.info("Skipping %s — no Parquet/Delta files found in %s", layer_name, layer_path)
        return 0

    uploaded = 0
    for local_path in files:
        # Build S3 key: layer_name/dataset/file.parquet
        relative = local_path.relative_to(layer_path)
        s3_key = f"{layer_name}/{relative}"

        try:
            s3.upload_file(
                str(local_path),
                BUCKET,
                s3_key,
                ExtraArgs={"ContentType": "application/octet-stream"},
            )
            size_kb = local_path.stat().st_size // 1024
            logger.info("  ✓ %s (%d KB)", s3_key, size_kb)
            uploaded += 1
        except Exception as exc:
            logger.warning("  ✗ Failed %s: %s", s3_key, exc)

    return uploaded


def main() -> int:
    try:
        import boto3
    except ImportError:
        logger.error("boto3 not installed. Run: pip install boto3")
        return 1

    logger.info("Connecting to MinIO at %s …", MINIO_ENDPOINT)
    s3 = get_s3_client()

    # Verify connection
    try:
        s3.list_buckets()
    except Exception as exc:
        logger.error("Cannot connect to MinIO: %s", exc)
        logger.error("Is MinIO running? Try: docker compose up -d minio")
        return 1

    ensure_bucket(s3)
    logger.info("Bucket: %s", BUCKET)

    total = 0
    for layer_name, layer_path in LAYERS.items():
        logger.info("Uploading %s layer from %s …", layer_name.upper(), layer_path)
        n = upload_layer(s3, layer_name, layer_path)
        logger.info("%s: %d files uploaded", layer_name.upper(), n)
        total += n

    logger.info("")
    logger.info("Done. %d files uploaded to MinIO.", total)
    logger.info("Open MinIO Console → http://localhost:9001")
    logger.info("Bucket: %s | Login: minioadmin / minioadmin", BUCKET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
