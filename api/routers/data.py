"""
Data upload router — customer CSV onboarding endpoint.
Accepts CSV files, drops them into /data/source/ for DataIngestionAgent to auto-process.
"""
import os
import shutil
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])

DATA_SOURCE_DIR = os.getenv("DATA_DIR", os.getenv("DATA_SOURCE_DIR", "/app/data/source"))
MAX_FILE_SIZE_MB = 100


@router.post("/upload")
async def upload_customer_data(file: UploadFile = File(...)):
    """
    Upload a CSV file for autonomous ingestion.

    The DataIngestionAgent will detect it within 60 seconds, infer the schema,
    generate a validated loader, and trigger the full medallion pipeline automatically.

    Supported formats: .csv, .tsv, .txt
    Max size: 100 MB
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".tsv", ".txt"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Must be .csv, .tsv, or .txt"
        )

    source_dir = Path(DATA_SOURCE_DIR)
    if not source_dir.exists():
        raise HTTPException(status_code=503, detail="Data source directory not available")

    dest_path = source_dir / file.filename

    # Stream to disk checking size limit
    size_bytes = 0
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    try:
        with open(dest_path, "wb") as out:
            while chunk := await file.read(65536):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    out.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {MAX_FILE_SIZE_MB} MB limit"
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

    logger.info(f"[data/upload] Received {file.filename} ({size_bytes/1024:.1f} KB)")

    return JSONResponse(status_code=202, content={
        "status": "accepted",
        "file": file.filename,
        "size_kb": round(size_bytes / 1024, 1),
        "message": "DataIngestionAgent will auto-process within 60 seconds. "
                   "Schema will be inferred, loader validated, and pipeline triggered automatically.",
        "next_steps": {
            "check_status": "GET /data/status",
            "view_pipeline": "http://<host>:3001 (Dagster UI)",
            "view_audit": "GET /data/audit"
        }
    })


@router.get("/status")
async def ingestion_status():
    """
    Check the status of recently ingested files.
    Returns list of files processed by DataIngestionAgent.
    """
    try:
        import redis
        r = redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
            socket_connect_timeout=3
        )
        known_files = r.smembers("ingestion:known_files")
        builtin = {
            "orderlist.csv", "freightrates.csv", "whcapacities.csv",
            "plantports.csv", "productsperplant.csv", "supplifySupplychain.csv",
            "vmicustomers.csv", "whcosts.csv", "manifest.txt",
        }
        customer_files = sorted(known_files - builtin)

        # Check for generated loaders
        loaders_dir = Path(DATA_SOURCE_DIR) / "_loaders"
        loaders = {}
        if loaders_dir.exists():
            for jf in loaders_dir.glob("*.json"):
                import json
                try:
                    meta = json.loads(jf.read_text())
                    loaders[meta.get("source_file", "")] = {
                        "table": meta.get("table_name"),
                        "columns": len(meta.get("columns", [])),
                        "generated_at": meta.get("generated_at"),
                    }
                except Exception:
                    pass

        return {
            "customer_files_ingested": len(customer_files),
            "files": [
                {
                    "filename": f,
                    "loader": loaders.get(f, loaders.get(f.lower())),
                    "pipeline_triggered": f in loaders or f.lower() in loaders,
                }
                for f in customer_files
            ]
        }
    except Exception as e:
        logger.warning(f"Status check failed: {e}")
        return {"customer_files_ingested": 0, "files": [], "error": "status check failed"}


@router.get("/audit")
async def ingestion_audit():
    """
    Show recent DataIngestionAgent audit log entries.
    """
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv(
            "DATABASE_URL",
            "postgresql://supplychain:supplychain@postgres:5432/supply_chain_db"
        ))
        cur = conn.cursor()
        cur.execute("""
            SELECT action, reasoning, outcome, details, created_at
            FROM agent_audit_log
            WHERE agent_id = 'data_ingestion'
            ORDER BY created_at DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "entries": [
                {
                    "action": r[0],
                    "reasoning": r[1],
                    "outcome": r[2],
                    "details": r[3],
                    "timestamp": r[4].isoformat() if r[4] else None,
                }
                for r in rows
            ]
        }
    except Exception as e:
        return {"entries": [], "error": "audit log unavailable"}
