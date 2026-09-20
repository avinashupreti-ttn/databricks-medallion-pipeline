"""Uniqueness check for Silver.

Customers: at most one row per customer_id.
Orders: at most one row per order_id.
Every row in a duplicate-key group fails. No survivor is kept for Gold.
"""

from __future__ import annotations

from src.silver.values import normalize_key

CATEGORY = "uniqueness"
ENTITIES = ("customers", "orders")

KEYS = {
    "customers": "customer_id",
    "orders": "order_id",
}


def duplicate_key_set(rows, key: str) -> set:
    """Keys that appear on more than one row. Missing keys are included."""
    counts: dict = {}
    for row in rows:
        token = normalize_key(row.get(key))
        counts[token] = counts.get(token, 0) + 1
    return {token for token, count in counts.items() if count > 1}


def row_failed(value, duplicates: set) -> bool:
    return normalize_key(value) in duplicates


def spark_attach(frame, key: str):
    """Add _dq_fail_uniqueness without dropping rows."""
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    window = Window.partitionBy(key)
    counted = frame.withColumn("_dq_key_rows", F.count(F.lit(1)).over(window))
    return counted.withColumn(
        "_dq_fail_uniqueness",
        F.col("_dq_key_rows") > F.lit(1),
    ).drop("_dq_key_rows")
