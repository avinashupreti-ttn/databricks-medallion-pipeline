"""Type and domain check for Silver.

Rules follow the source contract in data-model.md. Required fields must be
present. customer_segment and order_status must be in their domains.
Nullable fields fail only when a present value has the wrong type.
The standard sample set injects no type defects.
"""

from __future__ import annotations

from src.silver.values import is_blank, is_date_value, is_decimal_value, is_int_value

CATEGORY = "type_validation"
ENTITIES = ("customers", "orders", "products")

CUSTOMER_SEGMENTS = ("Premium", "Standard", "Basic")
ORDER_STATUSES = ("Pending", "Completed", "Cancelled")

# required_*: missing or wrong type fails.
# optional_*: missing is allowed; a present value of the wrong type fails.
# domains: blank or a value outside the set fails.
SPECS = {
    "customers": {
        "required_strings": ("customer_name", "country"),
        "required_ints": ("customer_id",),
        "optional_ints": (),
        "required_dates": ("signup_date",),
        "optional_dates": (),
        "required_decimals": ("lifetime_value",),
        "domains": {"customer_segment": CUSTOMER_SEGMENTS},
    },
    "orders": {
        "required_strings": (),
        "required_ints": ("order_id", "quantity"),
        "optional_ints": ("customer_id", "product_id"),
        "required_dates": ("order_date",),
        "optional_dates": ("payment_date",),
        "required_decimals": ("unit_price", "total_amount"),
        "domains": {"order_status": ORDER_STATUSES},
    },
    "products": {
        "required_strings": ("product_name", "category"),
        "required_ints": ("product_id", "stock_quantity", "reorder_level"),
        "optional_ints": (),
        "required_dates": (),
        "optional_dates": (),
        "required_decimals": ("price", "cost"),
        "domains": {},
    },
}


def _domain_failed(value, allowed: tuple[str, ...]) -> bool:
    if is_blank(value) or not isinstance(value, str):
        return True
    return value.strip() not in allowed


def row_failed(entity: str, row: dict) -> bool:
    spec = SPECS[entity]
    for column in spec["required_strings"]:
        value = row.get(column)
        if not isinstance(value, str) or value.strip() == "":
            return True
    for column in spec["required_ints"]:
        if not is_int_value(row.get(column)):
            return True
    for column in spec["optional_ints"]:
        value = row.get(column)
        if not is_blank(value) and not is_int_value(value):
            return True
    for column in spec["required_dates"]:
        if not is_date_value(row.get(column)):
            return True
    for column in spec["optional_dates"]:
        value = row.get(column)
        if not is_blank(value) and not is_date_value(value):
            return True
    for column in spec["required_decimals"]:
        if not is_decimal_value(row.get(column)):
            return True
    for column, allowed in spec["domains"].items():
        if _domain_failed(row.get(column), allowed):
            return True
    return False


def spark_failed_column(entity: str):
    """Boolean column: True when this row fails type validation.

    Bronze already stores canonical types, so cast failures arrive as null.
    This flags null required fields, blank required strings, and domain violations.
    """
    from pyspark.sql import functions as F

    spec = SPECS[entity]
    checks = []
    for column in spec["required_strings"]:
        trimmed = F.trim(F.col(column))
        checks.append(F.col(column).isNull() | trimmed.isNull() | (trimmed == F.lit("")))
    for column in spec["required_ints"]:
        checks.append(F.col(column).isNull())
    for column in spec["required_dates"]:
        checks.append(F.col(column).isNull())
    for column in spec["required_decimals"]:
        checks.append(F.col(column).isNull())
    for column, allowed in spec["domains"].items():
        trimmed = F.trim(F.col(column))
        checks.append(
            F.col(column).isNull()
            | trimmed.isNull()
            | (trimmed == F.lit(""))
            | ~trimmed.isin(*allowed)
        )
    if not checks:
        return F.lit(False)
    failed = checks[0]
    for check in checks[1:]:
        failed = failed | check
    return F.coalesce(failed, F.lit(False))
