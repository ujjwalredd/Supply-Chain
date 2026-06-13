import json
import importlib
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


def _install_fake_dagster(monkeypatch):
    """Let helper-level tests import assets_medallion when Dagster is absent locally."""
    if importlib.util.find_spec("dagster") is not None:
        return

    fake = types.ModuleType("dagster")
    fake.__spec__ = importlib.machinery.ModuleSpec("dagster", loader=None)

    def asset(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]

        def decorator(fn):
            return fn

        return decorator

    class MaterializeResult:
        def __init__(self, metadata=None):
            self.metadata = metadata or {}

    class MetadataValue:
        @staticmethod
        def int(value):
            return value

        @staticmethod
        def float(value):
            return value

        @staticmethod
        def text(value):
            return value

    class FreshnessPolicy:
        @staticmethod
        def time_window(**kwargs):
            return kwargs

    fake.AssetExecutionContext = object
    fake.asset = asset
    fake.MaterializeResult = MaterializeResult
    fake.MetadataValue = MetadataValue
    fake.FreshnessPolicy = FreshnessPolicy
    monkeypatch.setitem(sys.modules, "dagster", fake)


@pytest.fixture
def assets_module(monkeypatch):
    _install_fake_dagster(monkeypatch)
    sys.modules.pop("pipeline.assets_medallion", None)
    module = importlib.import_module("pipeline.assets_medallion")
    yield module
    sys.modules.pop("pipeline.assets_medallion", None)


def test_run_generated_loader_returns_rows(tmp_path, assets_module):
    source = tmp_path / "customer_orders.csv"
    source.write_text(
        "OrderID,Supplier,Product,Qty,Price,Delay\n"
        "ORD-1,SUP-1,WIDGET,2,10.50,0\n"
        "ORD-2,SUP-2,GADGET,3,7.00,4\n",
        encoding="utf-8",
    )
    loader = tmp_path / "customer_orders.py"
    loader.write_text(
        """
from pathlib import Path
from typing import Iterator

def load_csv(path: Path) -> Iterator[dict]:
    import csv
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qty = int(row["Qty"])
            price = float(row["Price"])
            yield {
                "order_id": row["OrderID"],
                "supplier_id": row["Supplier"],
                "product": row["Product"],
                "quantity": qty,
                "unit_price": price,
                "order_value": qty * price,
                "status": "DELAYED" if int(row["Delay"]) else "PENDING",
                "delay_days": int(row["Delay"]),
            }
""".strip(),
        encoding="utf-8",
    )

    rows = assets_module._run_generated_loader(loader, source)

    assert len(rows) == 2
    assert rows[0]["order_id"] == "ORD-1"
    assert rows[1]["delay_days"] == 4


def test_generated_customer_loader_writes_to_bronze(tmp_path, monkeypatch, assets_module):
    import ingestion.batch_loader as bl

    data_dir = tmp_path / "source"
    loaders_dir = data_dir / "_loaders"
    bronze_dir = tmp_path / "bronze"
    loaders_dir.mkdir(parents=True)

    source = data_dir / "customer_orders.csv"
    source.write_text(
        "OrderID,Supplier,Product,Qty,Price,Delay\n"
        "ORD-10,SUP-10,WIDGET,5,11.00,0\n"
        "ORD-11,SUP-11,GADGET,1,200.00,9\n",
        encoding="utf-8",
    )
    loader = loaders_dir / "customer_orders.py"
    loader.write_text(
        """
from pathlib import Path
from typing import Iterator

def load_csv(path: Path) -> Iterator[dict]:
    import csv
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qty = int(row["Qty"])
            price = float(row["Price"])
            delay = int(row["Delay"])
            yield {
                "order_id": row["OrderID"],
                "supplier_id": row["Supplier"],
                "product": row["Product"],
                "quantity": qty,
                "unit_price": price,
                "order_value": qty * price,
                "status": "DELAYED" if delay else "PENDING",
                "delay_days": delay,
            }
""".strip(),
        encoding="utf-8",
    )
    (loaders_dir / "customer_orders.json").write_text(
        json.dumps({
            "table_name": "customer_orders",
            "source_file": "customer_orders.csv",
            "columns": [
                {"name": "order_id", "dtype": "str", "nullable": False},
                {"name": "supplier_id", "dtype": "str", "nullable": False},
            ],
            "loader_file": str(loader),
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(assets_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(assets_module, "BRONZE_PATH", str(bronze_dir))
    monkeypatch.setattr(bl, "BRONZE_PATH", str(bronze_dir))

    context = MagicMock()
    context.log = MagicMock()
    stats = assets_module._ingest_generated_loaders(context)

    assert stats["loader_count"] == 1
    assert stats["generated_rows"] == 2
    assert stats["generated_order_rows"] == 2
    assert stats["failed_loaders"] == 0

    generic_df = pd.read_parquet(bronze_dir / "customer_orders" / "data.parquet")
    orders_df = pd.read_parquet(bronze_dir / "orders" / "data.parquet")

    assert set(generic_df["order_id"]) == {"ORD-10", "ORD-11"}
    assert set(orders_df["order_id"]) == {"ORD-10", "ORD-11"}
    assert orders_df.loc[orders_df["order_id"] == "ORD-11", "status"].iloc[0] == "DELAYED"
