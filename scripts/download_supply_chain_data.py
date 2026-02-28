#!/usr/bin/env python3
"""
Download messy supply chain data from public internet sources.

Sources:
1. LogisticsDataset (Brunel University via GitHub) - orders, freight, plants, warehouses
2. Supplyify supply-chain-data.csv - product/sales data
"""

import logging
import os
import sys
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Data sources - raw URLs for direct download (no auth)
LOGISTICS_BASE = "https://raw.githubusercontent.com/jaredbach/LogisticsDataset/main"
SOURCES = {
    "OrderList": f"{LOGISTICS_BASE}/CSVs/OrderList.csv",
    "FreightRates": f"{LOGISTICS_BASE}/CSVs/FreightRates.csv",
    "PlantPorts": f"{LOGISTICS_BASE}/CSVs/PlantPorts.csv",
    "ProductsPerPlant": f"{LOGISTICS_BASE}/CSVs/ProductsPerPlant.csv",
    "VmiCustomers": f"{LOGISTICS_BASE}/CSVs/VmiCustomers.csv",
    "WhCapacities": f"{LOGISTICS_BASE}/CSVs/WhCapacities.csv",
    "WhCosts": f"{LOGISTICS_BASE}/CSVs/WhCosts.csv",
}

# Fallback Supplyify dataset
SUPPLYIFY = "https://raw.githubusercontent.com/Supplyify/supply-chain-visualization/main/supply-chain-data.csv"

DATA_DIR = Path(os.getenv("DATA_DIR", "data/source"))
INJECT_MESSINESS = os.getenv("INJECT_MESSINESS", "true").lower() == "true"


def download(url: str, dest: Path) -> bool:
    """Download file from URL to dest. Returns True on success."""
    try:
        r = requests.get(url, timeout=60, stream=True)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info("Downloaded %s -> %s (%d bytes)", url, dest, dest.stat().st_size)
        return True
    except Exception as e:
        logger.error("Failed to download %s: %s", url, e)
        return False


def inject_messiness(path: Path) -> None:
    """
    Inject realistic messiness: nulls, duplicates, bad dates, invalid values.
    Simulates production data quality issues.
    """
    import random

    if not path.exists() or path.suffix != ".csv":
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 2:
        return

    header = lines[0]
    rows = lines[1:]
    out = [header]

    # 2% nulls in random cells
    null_rate = 0.02
    # 1% duplicates
    dup_rate = 0.01
    # 0.5% bad dates (invalid format)
    bad_date_rate = 0.005

    for i, row in enumerate(rows):
        if random.random() < dup_rate and len(out) > 1:
            out.append(out[-1])  # duplicate previous row
        cells = row.split(",")
        for j in range(len(cells)):
            if random.random() < null_rate and cells[j] and not cells[j].startswith('"'):
                cells[j] = ""
            # Bad date in Order_Date (col 1) or similar
            if "Order" in header and j == 1 and random.random() < bad_date_rate:
                cells[j] = "invalid-date" if random.random() > 0.5 else "99/99/99"
        out.append(",".join(cells))

    path.write_text("\n".join(out), encoding="utf-8")
    logger.info("Injected messiness into %s", path.name)


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    for name, url in SOURCES.items():
        dest = DATA_DIR / f"{name}.csv"
        if download(url, dest):
            manifest.append((name, str(dest), dest.stat().st_size))
            if INJECT_MESSINESS:
                inject_messiness(dest)

    # Try Supplyify as supplemental
    supplyify_dest = DATA_DIR / "SupplyifySupplyChain.csv"
    if download(SUPPLYIFY, supplyify_dest):
        manifest.append(("SupplyifySupplyChain", str(supplyify_dest), supplyify_dest.stat().st_size))

    manifest_path = DATA_DIR / "manifest.txt"
    manifest_path.write_text(
        "\n".join(f"{n}\t{p}\t{s}" for n, p, s in manifest),
        encoding="utf-8",
    )
    logger.info("Wrote manifest to %s", manifest_path)
    return 0 if manifest else 1


if __name__ == "__main__":
    sys.exit(main())
