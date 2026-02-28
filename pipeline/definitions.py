"""Dagster Definitions entry point.

Primary: Medallion pipeline (bronze → silver → gold) with real internet data.
Legacy: Kafka-based pipeline (raw_orders → cleaned → modeled).
"""

import os
from dagster import Definitions

# Medallion: bronze → silver → gold (real data, batch files, lakehouse)
from pipeline.definitions_medallion import defs as medallion_defs

# Use medallion as default; set DAGSTER_USE_LEGACY=true for Kafka pipeline
if os.getenv("DAGSTER_USE_LEGACY", "false").lower() == "true":
    from pipeline.definitions_legacy import defs as legacy_defs

    defs = legacy_defs
else:
    defs = medallion_defs
