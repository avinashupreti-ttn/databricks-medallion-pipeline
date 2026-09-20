"""Build Gold aggregations from Silver PASS rows only.

Runs the four Gold SQL scripts in order and overwrites gold_* tables.
Requires catalog, silver_schema, gold_schema, and existing silver_* tables.
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
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

from src.config import resolve_config, validate_identifier

SCHEMA_PATH = REPO_ROOT / "database" / "schema.sql"
GOLD_SQL_DIR = REPO_ROOT / "src" / "gold"

GOLD_SQL_FILES = (
    "01_sales_by_product.sql",
    "02_revenue_by_customer.sql",
    "03_daily_weekly_trends.sql",
    "04_customer_segmentation.sql",
)
GOLD_TABLES = (
    "gold_sales_by_product",
    "gold_revenue_by_customer",
    "gold_daily_weekly_trends",
    "gold_customer_segmentation",
)
SILVER_TABLES = (
    "silver_customers",
    "silver_orders",
    "silver_products",
)
SEGMENT_TYPES = ("High-Value", "Repeat", "One-Time", "Inactive")
HANDLED_ERRORS = (
    ValueError,
    FileNotFoundError,
    PermissionError,
    RuntimeError,
    OSError,
)


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _as_decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return _money(value)


def _pass_rows(rows: list) -> list:
    return [row for row in rows if row.get("quality_check_result") == "PASS"]


def percentile_nearest_rank(values: list[Decimal], pct: float) -> Decimal:
    """Inclusive nearest-rank percentile (matches Spark percentile intent for tests)."""
    if not values:
        raise ValueError("Cannot compute percentile of an empty value list.")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = max(1, int(round(pct * len(ordered) + 0.5)))
    index = min(len(ordered), rank) - 1
    return ordered[index]


def assign_segment(order_count: int, total_revenue: Decimal, high_value_threshold: Decimal) -> str:
    """CL-03 segment rules from design-notes.md."""
    if order_count == 0:
        return "Inactive"
    if total_revenue >= high_value_threshold:
        return "High-Value"
    if order_count >= 2:
        return "Repeat"
    return "One-Time"


def aggregate_sales_by_product(orders: list, products: list) -> list[dict]:
    """Local GD-01 mirror: PASS orders joined to PASS products."""
    products_by_id = {
        _as_int(row["product_id"]): row for row in _pass_rows(products)
    }
    buckets: dict[int, dict] = {}
    for order in _pass_rows(orders):
        product_id = _as_int(order.get("product_id"))
        product = products_by_id.get(product_id)
        if product is None:
            continue
        bucket = buckets.get(product_id)
        if bucket is None:
            bucket = {
                "product_id": product_id,
                "product_name": product["product_name"],
                "category": product["category"],
                "total_orders": 0,
                "total_revenue": Decimal("0.00"),
            }
            buckets[product_id] = bucket
        bucket["total_orders"] += 1
        bucket["total_revenue"] += _as_decimal(order.get("total_amount"))
    rows = []
    for bucket in buckets.values():
        total_orders = bucket["total_orders"]
        total_revenue = _money(bucket["total_revenue"])
        rows.append(
            {
                "product_id": bucket["product_id"],
                "product_name": bucket["product_name"],
                "category": bucket["category"],
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "avg_order_value": _money(total_revenue / total_orders),
            }
        )
    return rows


def aggregate_revenue_by_customer(orders: list, customers: list) -> list[dict]:
    """Local GD-02 mirror: PASS orders joined to PASS customers."""
    customers_by_id = {
        _as_int(row["customer_id"]): row for row in _pass_rows(customers)
    }
    buckets: dict[int, dict] = {}
    for order in _pass_rows(orders):
        customer_id = _as_int(order.get("customer_id"))
        customer = customers_by_id.get(customer_id)
        if customer is None:
            continue
        bucket = buckets.get(customer_id)
        if bucket is None:
            bucket = {
                "customer_id": customer_id,
                "customer_name": customer["customer_name"],
                "customer_segment": customer["customer_segment"],
                "total_orders": 0,
                "total_revenue": Decimal("0.00"),
            }
            buckets[customer_id] = bucket
        bucket["total_orders"] += 1
        bucket["total_revenue"] += _as_decimal(order.get("total_amount"))
    rows = []
    for bucket in buckets.values():
        total_orders = bucket["total_orders"]
        total_revenue = _money(bucket["total_revenue"])
        rows.append(
            {
                "customer_id": bucket["customer_id"],
                "customer_name": bucket["customer_name"],
                "customer_segment": bucket["customer_segment"],
                "total_orders": total_orders,
                "total_revenue": total_revenue,
                "avg_order_value": _money(total_revenue / total_orders),
                "lifetime_value_actual": total_revenue,
            }
        )
    return rows


def aggregate_daily_weekly_trends(orders: list) -> list[dict]:
    """Local GD-03 mirror: DAY and ISO-Monday WEEK grains from PASS orders."""
    from datetime import date, timedelta

    def iso_week_start(value: date) -> date:
        return value - timedelta(days=value.weekday())

    day_buckets: dict[date, dict] = defaultdict(
        lambda: {"total_orders": 0, "total_revenue": Decimal("0.00")}
    )
    week_buckets: dict[date, dict] = defaultdict(
        lambda: {"total_orders": 0, "total_revenue": Decimal("0.00")}
    )
    for order in _pass_rows(orders):
        raw = order.get("order_date")
        if hasattr(raw, "year"):
            order_day = raw if isinstance(raw, date) else raw.date()
        else:
            order_day = date.fromisoformat(str(raw)[:10])
        amount = _as_decimal(order.get("total_amount"))
        day_buckets[order_day]["total_orders"] += 1
        day_buckets[order_day]["total_revenue"] += amount
        week_start = iso_week_start(order_day)
        week_buckets[week_start]["total_orders"] += 1
        week_buckets[week_start]["total_revenue"] += amount
    rows = []
    for period_start, bucket in sorted(day_buckets.items()):
        rows.append(
            {
                "period_start": period_start,
                "period_grain": "DAY",
                "total_orders": bucket["total_orders"],
                "total_revenue": _money(bucket["total_revenue"]),
            }
        )
    for period_start, bucket in sorted(week_buckets.items()):
        rows.append(
            {
                "period_start": period_start,
                "period_grain": "WEEK",
                "total_orders": bucket["total_orders"],
                "total_revenue": _money(bucket["total_revenue"]),
            }
        )
    return rows


def aggregate_customer_segmentation(orders: list, customers: list) -> list[dict]:
    """Local GD-04 mirror using design-notes.md segment rules."""
    pass_customers = _pass_rows(customers)
    metrics: dict[int, dict] = {
        _as_int(row["customer_id"]): {
            "order_count": 0,
            "total_revenue": Decimal("0.00"),
        }
        for row in pass_customers
        if _as_int(row["customer_id"]) is not None
    }
    for order in _pass_rows(orders):
        customer_id = _as_int(order.get("customer_id"))
        if customer_id not in metrics:
            continue
        metrics[customer_id]["order_count"] += 1
        metrics[customer_id]["total_revenue"] += _as_decimal(order.get("total_amount"))
    active_revenues = [
        _money(values["total_revenue"])
        for values in metrics.values()
        if values["order_count"] > 0
    ]
    if not active_revenues:
        raise ValueError("No PASS customers with orders; cannot compute High-Value threshold.")
    threshold = percentile_nearest_rank(active_revenues, 0.9)
    segment_buckets: dict[str, dict] = {
        name: {"customer_count": 0, "total_revenue": Decimal("0.00")}
        for name in SEGMENT_TYPES
    }
    for values in metrics.values():
        revenue = _money(values["total_revenue"])
        segment = assign_segment(values["order_count"], revenue, threshold)
        segment_buckets[segment]["customer_count"] += 1
        segment_buckets[segment]["total_revenue"] += revenue
    rows = []
    for segment_type in SEGMENT_TYPES:
        bucket = segment_buckets[segment_type]
        count = bucket["customer_count"]
        total_revenue = _money(bucket["total_revenue"])
        avg_revenue = (
            _money(total_revenue / count) if count else Decimal("0.00")
        )
        rows.append(
            {
                "segment_type": segment_type,
                "customer_count": count,
                "avg_revenue": avg_revenue,
                "total_revenue": total_revenue,
            }
        )
    return rows


def split_sql(text: str) -> list[str]:
    kept_lines = []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        kept_lines.append(line)
    statements = []
    for chunk in "\n".join(kept_lines).split(";"):
        statement = chunk.strip()
        if statement:
            statements.append(statement)
    return statements


def render_schema_statements(
    catalog: str,
    bronze_schema: str,
    silver_schema: str,
    gold_schema: str | None = None,
) -> list[str]:
    validate_identifier(catalog, "catalog")
    validate_identifier(bronze_schema, "bronze_schema")
    validate_identifier(silver_schema, "silver_schema")
    if gold_schema:
        validate_identifier(gold_schema, "gold_schema")
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
    rendered = (
        SCHEMA_PATH.read_text(encoding="utf-8")
        .replace("__CATALOG__", catalog)
        .replace("__BRONZE_SCHEMA__", bronze_schema)
        .replace("__SILVER_SCHEMA__", silver_schema)
    )
    if gold_schema:
        rendered = rendered.replace("__GOLD_SCHEMA__", gold_schema)
    statements = split_sql(rendered)
    if not gold_schema:
        statements = [s for s in statements if "__GOLD_SCHEMA__" not in s]
    joined = "\n".join(statements)
    if (
        "__CATALOG__" in joined
        or "__BRONZE_SCHEMA__" in joined
        or "__SILVER_SCHEMA__" in joined
        or "__GOLD_SCHEMA__" in joined
    ):
        raise RuntimeError("database/schema.sql has unsubstituted placeholders.")
    if not statements:
        raise RuntimeError(f"Schema file has no statements: {SCHEMA_PATH}")
    return statements


def render_gold_sql(
    sql_text: str, catalog: str, silver_schema: str, gold_schema: str
) -> list[str]:
    validate_identifier(catalog, "catalog")
    validate_identifier(silver_schema, "silver_schema")
    validate_identifier(gold_schema, "gold_schema")
    rendered = (
        sql_text.replace("__CATALOG__", catalog)
        .replace("__SILVER_SCHEMA__", silver_schema)
        .replace("__GOLD_SCHEMA__", gold_schema)
    )
    if (
        "__CATALOG__" in rendered
        or "__SILVER_SCHEMA__" in rendered
        or "__GOLD_SCHEMA__" in rendered
        or "__BRONZE_SCHEMA__" in rendered
    ):
        raise RuntimeError("Gold SQL has unsubstituted placeholders.")
    statements = split_sql(rendered)
    if not statements:
        raise RuntimeError("Gold SQL file has no executable statements.")
    return statements


def apply_schema(
    spark,
    catalog: str,
    bronze_schema: str,
    silver_schema: str,
    gold_schema: str,
) -> None:
    for statement in render_schema_statements(
        catalog, bronze_schema, silver_schema, gold_schema
    ):
        try:
            spark.sql(statement)
        except Exception as exc:
            raise RuntimeError(
                "Failed to apply database/schema.sql for "
                f"{catalog}.{gold_schema}: {exc}"
            ) from exc


def _qualified(catalog: str, schema_name: str, table: str) -> str:
    return f"`{catalog}`.`{schema_name}`.`{table}`"


def _require_gold_schema(gold_schema: str | None) -> str:
    if not gold_schema or not str(gold_schema).strip():
        raise ValueError(
            "Missing required configuration: gold_schema. "
            "Set --gold-schema, PIPELINE_GOLD_SCHEMA, or the gold_schema widget."
        )
    return validate_identifier(gold_schema.strip(), "gold_schema")


def _require_silver(spark, catalog: str, silver_schema: str) -> None:
    missing = []
    for table in SILVER_TABLES:
        if not spark.catalog.tableExists(f"{catalog}.{silver_schema}.{table}"):
            missing.append(_qualified(catalog, silver_schema, table))
    if missing:
        names = ", ".join(missing)
        raise FileNotFoundError(
            f"Silver tables required for Gold are missing: {names}. "
            "Run Silver validation before Gold aggregations."
        )


def _gold_sql_path(name: str) -> Path:
    path = GOLD_SQL_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Gold SQL file not found: {path}")
    return path


def run_gold_sql_files(
    spark, catalog: str, silver_schema: str, gold_schema: str
) -> dict:
    counts = {}
    for sql_name, table in zip(GOLD_SQL_FILES, GOLD_TABLES):
        path = _gold_sql_path(sql_name)
        statements = render_gold_sql(
            path.read_text(encoding="utf-8"),
            catalog,
            silver_schema,
            gold_schema,
        )
        for statement in statements:
            try:
                spark.sql(statement)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed running {sql_name} into "
                    f"{_qualified(catalog, gold_schema, table)}: {exc}"
                ) from exc
        full = _qualified(catalog, gold_schema, table)
        count = spark.table(f"{catalog}.{gold_schema}.{table}").count()
        print(f"Wrote {count} rows to {full}", flush=True)
        counts[table] = int(count)
    return counts


def create_gold_tables(
    spark,
    catalog: str,
    bronze_schema: str,
    silver_schema: str,
    gold_schema: str,
) -> dict:
    gold_schema = _require_gold_schema(gold_schema)
    validate_identifier(catalog, "catalog")
    validate_identifier(bronze_schema, "bronze_schema")
    validate_identifier(silver_schema, "silver_schema")
    _require_silver(spark, catalog, silver_schema)
    apply_schema(spark, catalog, bronze_schema, silver_schema, gold_schema)
    counts = run_gold_sql_files(spark, catalog, silver_schema, gold_schema)
    summary = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(f"Gold aggregations complete: {summary}", flush=True)
    return counts


def get_spark():
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError(
            "PySpark is not available. Run Gold aggregations on Databricks serverless."
        ) from exc
    spark = SparkSession.getActiveSession()
    if spark is not None:
        return spark
    if not os.environ.get("DATABRICKS_RUNTIME_VERSION", "").strip():
        raise RuntimeError(
            "No active Spark session. Run Gold aggregations on Databricks serverless."
        )
    return SparkSession.builder.getOrCreate()


def run_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build Gold tables from Silver PASS rows only. Overwrites gold_* "
            "on each run. Requires --gold-schema."
        )
    )
    parser.add_argument("--catalog", default=None)
    parser.add_argument("--bronze-schema", default=None)
    parser.add_argument("--silver-schema", default=None)
    parser.add_argument("--gold-schema", default=None)
    parser.add_argument("--landing-path", default=None)
    args = parser.parse_args(argv)
    try:
        config = resolve_config(
            args.catalog,
            args.bronze_schema,
            args.silver_schema,
            args.landing_path,
            args.gold_schema,
        )
        gold_schema = _require_gold_schema(config.gold_schema)
        spark = get_spark()
        create_gold_tables(
            spark,
            config.catalog,
            config.bronze_schema,
            config.silver_schema,
            gold_schema,
        )
    except HANDLED_ERRORS as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    return run_main()


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
