#!/usr/bin/env python3
"""Ingest orders.csv into bronze_orders. No cleansing."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bronze.ingest import run_main


def main() -> int:
    return run_main("orders")


if __name__ == "__main__":
    raise SystemExit(main())
