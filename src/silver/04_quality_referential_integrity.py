"""Referential integrity check for Silver orders.

A non-NULL customer_id must exist in the customer key set.
A non-NULL product_id must exist in the product key set.
NULL foreign keys are not failures here. Parent keys include ids on rows
that fail other checks. The parent sets are distinct so duplicate parent
rows cannot multiply orders.
"""

from __future__ import annotations

from src.silver.values import normalize_key

CATEGORY = "referential_integrity"
ENTITIES = ("orders",)


def parent_keys(rows, key: str) -> set:
    found = set()
    for row in rows:
        token = normalize_key(row.get(key))
        if token is not None:
            found.add(token)
    return found


def row_failed(row: dict, customer_ids: set, product_ids: set) -> bool:
    customer_id = normalize_key(row.get("customer_id"))
    product_id = normalize_key(row.get("product_id"))
    if customer_id is not None and customer_id not in customer_ids:
        return True
    if product_id is not None and product_id not in product_ids:
        return True
    return False


def _distinct_ids(frame, key: str) -> list:
    from pyspark.sql import functions as F

    rows = (
        frame.select(F.col(key).alias(key))
        .where(F.col(key).isNotNull())
        .distinct()
        .collect()
    )
    return [row[key] for row in rows]


def _missing(column: str, keys: list):
    from pyspark.sql import functions as F

    present = F.col(column).isNotNull()
    if not keys:
        return present
    return present & ~F.col(column).isin(keys)


def spark_attach(orders, customers, products):
    """Add _dq_fail_referential_integrity. Does not join, so row counts stay put."""
    from pyspark.sql import functions as F

    customer_ids = _distinct_ids(customers, "customer_id")
    product_ids = _distinct_ids(products, "product_id")
    failed = _missing("customer_id", customer_ids) | _missing("product_id", product_ids)
    return orders.withColumn("_dq_fail_referential_integrity", failed)
