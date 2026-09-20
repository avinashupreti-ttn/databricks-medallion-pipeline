#!/usr/bin/env python3
"""Ingest all three landing CSVs into Bronze Delta tables.

Databricks serverless example. The Unity Catalog catalog must already exist.
Stage customers.csv, orders.csv, and products.csv into the landing directory
first (Volume or dbfs: path).

    python src/bronze/ingest_all.py \\
        --catalog workspace \\
        --bronze-schema c1_bronze \\
        --silver-schema c1_silver \\
        --landing-path /Volumes/workspace/c1_landing/landing

A rerun overwrites bronze_customers, bronze_orders, and bronze_products.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path


def _repository_root() -> Path:
    """Repo root from __file__, or the caller's compiled co_filename."""
    frame = inspect.currentframe()
    if frame is None:
        raise RuntimeError("Unable to resolve repository root: no stack frame.")
    try:
        caller = frame.f_back
        if caller is None:
            raise RuntimeError("Unable to resolve repository root: no caller frame.")
        module_file = caller.f_globals.get("__file__")
        if module_file:
            script = Path(str(module_file)).resolve()
        else:
            filename = caller.f_code.co_filename
            if not filename or filename.startswith("<"):
                raise RuntimeError(
                    "Unable to resolve repository root from compiled filename: "
                    f"{filename!r}."
                )
            script = Path(filename).resolve()
        return script.parents[2]
    finally:
        del frame


REPO_ROOT = _repository_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.bronze.ingest import run_main


def main() -> int:
    return run_main(None)


def finish(status: int) -> None:
    """End a script run without SystemExit(0).

    Databricks spark_python_task uses an IPython context; raising
    SystemExit(0) surfaces an IPython exit warning after a successful run.
    Nonzero status still raises SystemExit so local CLI and failed tasks
    keep a failing exit code.
    """
    if status:
        raise SystemExit(status)


if __name__ == "__main__":
    finish(main())
