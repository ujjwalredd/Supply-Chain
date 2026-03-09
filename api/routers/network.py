"""Feature 6: Supply chain network graph router — Plant → Port → Supplier topology."""

import csv
import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

DATA_DIR = Path(os.getenv("DATA_DIR", "data/source"))

# Module-level cache: CSVs rarely change, cache for 10 minutes
_NETWORK_CACHE: dict | None = None
_NETWORK_CACHE_AT: float = 0.0
_NETWORK_CACHE_TTL: float = 600.0


def _load_plant_ports() -> list[dict]:
    path = DATA_DIR / "PlantPorts.csv"
    if not path.exists():
        return []
    rows = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({k.strip(): v.strip() for k, v in row.items()})
    except Exception as exc:
        logger.warning("Could not read PlantPorts.csv: %s", exc)
    return rows


def _load_products_per_plant() -> list[dict]:
    path = DATA_DIR / "ProductsPerPlant.csv"
    if not path.exists():
        return []
    rows = []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({k.strip(): v.strip() for k, v in row.items()})
    except Exception as exc:
        logger.warning("Could not read ProductsPerPlant.csv: %s", exc)
    return rows


def _build_graph() -> dict:
    """Build the network graph from CSVs. Result is cached at call site."""
    plant_ports = _load_plant_ports()
    products_per_plant = _load_products_per_plant()

    nodes: dict[str, dict] = {}
    edge_keys: set[tuple[str, str]] = set()
    edges: list[dict] = []

    for row in plant_ports:
        plant = row.get("Plant_Code") or row.get("Plant Code") or row.get("plant_code") or row.get("Plant") or ""
        port = row.get("Ports") or row.get("Shipping Port") or row.get("port") or row.get("Port") or ""
        if not plant or not port:
            continue
        plant_id = f"plant:{plant}"
        port_id = f"port:{port}"
        if plant_id not in nodes:
            nodes[plant_id] = {"id": plant_id, "label": plant, "type": "plant"}
        if port_id not in nodes:
            nodes[port_id] = {"id": port_id, "label": port, "type": "port"}
        edge_key = (plant_id, port_id)
        if edge_key not in edge_keys:
            edge_keys.add(edge_key)
            edges.append({"source": plant_id, "target": port_id, "label": "ships_via"})

    # Build plant→products mapping in a single pass
    plant_products: dict[str, list[str]] = {}
    for row in products_per_plant:
        plant = row.get("Plant Code") or row.get("plant_code") or row.get("Plant") or ""
        product = row.get("Product ID") or row.get("product_id") or row.get("Product") or ""
        if plant and product:
            plant_products.setdefault(f"plant:{plant}", []).append(product)

    for plant_id, products in plant_products.items():
        if plant_id in nodes:
            nodes[plant_id]["products"] = products[:10]

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "plant_count": sum(1 for n in nodes.values() if n["type"] == "plant"),
            "port_count": sum(1 for n in nodes.values() if n["type"] == "port"),
            "edge_count": len(edges),
        },
    }


@router.get("")
async def get_network_graph():
    """
    Feature 6: Return Plant → Port supply chain topology as nodes + edges.

    Nodes: plants, ports
    Edges: plant→port (from PlantPorts.csv)
    """
    global _NETWORK_CACHE, _NETWORK_CACHE_AT
    if _NETWORK_CACHE and (time.monotonic() - _NETWORK_CACHE_AT) < _NETWORK_CACHE_TTL:
        return _NETWORK_CACHE
    _NETWORK_CACHE = _build_graph()
    _NETWORK_CACHE_AT = time.monotonic()
    return _NETWORK_CACHE
