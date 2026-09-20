"""Completeness check for Silver.

Customers: email must not be NULL or blank after trim.
Orders: customer_id and product_id must not be NULL.
NULL foreign keys are completeness failures, not referential-integrity failures.
"""

from __future__ import annotations

from src.silver.values import is_blank

CATEGORY = "completeness"
ENTITIES = ("customers", "orders")

CUSTOMER_COLUMNS = ("email",)
ORDER_COLUMNS = ("customer_id", "product_id")


def row_failed(entity: str, row: dict) -> bool:
    if entity == "customers":
        return any(is_blank(row.get(column)) for column in CUSTOMER_COLUMNS)
    if entity == "orders":
        return any(is_blank(row.get(column)) for column in ORDER_COLUMNS)
    raise ValueError(f"Completeness does not apply to {entity}")


def spark_failed_column(entity: str):
    """Boolean column: True when this row fails completeness."""
    from pyspark.sql import functions as F

    if entity == "customers":
        email = F.col("email")
        return email.isNull() | (F.trim(email) == F.lit(""))
    if entity == "orders":
        return F.col("customer_id").isNull() | F.col("product_id").isNull()
    raise ValueError(f"Completeness does not apply to {entity}")
