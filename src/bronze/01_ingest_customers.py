#!/usr/bin/env python3
"""Ingest customers.csv into bronze_customers. No cleansing."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bronze.ingest import run_main


def main() -> int:
    return run_main("customers")


if __name__ == "__main__":
    raise SystemExit(main())
