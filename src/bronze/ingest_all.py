#!/usr/bin/env python3
"""Ingest all three landing CSVs into Bronze Delta tables.

Databricks serverless example. The Unity Catalog catalog must already exist.
Stage customers.csv, orders.csv, and products.csv into the landing directory
first (Volume or dbfs: path).

    python src/bronze/ingest_all.py \\
        --catalog main \\
        --schema ecommerce \\
        --landing-path /Volumes/main/ecommerce/landing

A rerun overwrites bronze_customers, bronze_orders, and bronze_products.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bronze.ingest import run_main


def main() -> int:
    return run_main(None)


if __name__ == "__main__":
    raise SystemExit(main())
