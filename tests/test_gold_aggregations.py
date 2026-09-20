"""TS-05 checks for Gold aggregations.

Local tests annotate sample CSVs with Silver rules, then mirror Gold math
in memory. They do not start Spark. Tests marked databricks compare Gold
Delta tables to PASS Silver. Those skip unless run on Databricks serverless.
A skip is not a pass.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from src.config import resolve_config
from src.gold.create_gold_tables import (
    GOLD_SQL_DIR,
    GOLD_SQL_FILES,
    GOLD_TABLES,
    SCHEMA_PATH,
    SEGMENT_TYPES,
    aggregate_customer_segmentation,
    aggregate_daily_weekly_trends,
    aggregate_revenue_by_customer,
    aggregate_sales_by_product,
    assign_segment,
    percentile_nearest_rank,
    render_gold_sql,
    render_schema_statements,
    _money,
    _require_gold_schema,
)
from src.silver.create_silver_tables import annotate_entities

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DUPLICATE_CUSTOMER_IDS = (51, 53, 55, 57, 59)
DUPLICATE_ORDER_IDS = (381, 383, 385, 387, 389, 391, 393, 395, 397, 399)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def annotated_rows():
    customers = _read_csv(DATA_DIR / "customers.csv")
    orders = _read_csv(DATA_DIR / "orders.csv")
    products = _read_csv(DATA_DIR / "products.csv")
    return annotate_entities(customers, orders, products)


def test_gold_sql_files_use_pass_only_filters():
    for name in GOLD_SQL_FILES:
        text = (GOLD_SQL_DIR / name).read_text(encoding="utf-8")
        assert "quality_check_result = 'PASS'" in text
        assert "order_status <> 'Cancelled'" in text
        assert "__GOLD_SCHEMA__" in text
        assert "__SILVER_SCHEMA__" in text
        statements = render_gold_sql(
            text, "workspace", "c1_silver", "c1_gold"
        )
        assert statements
        joined = "\n".join(statements)
        assert "__GOLD_SCHEMA__" not in joined
        assert "c1_gold" in joined
        assert "quality_check_result = 'PASS'" in joined
        assert "order_status <> 'Cancelled'" in joined


def test_assign_segment_rules():
    threshold = Decimal("100.00")
    assert assign_segment(0, Decimal("0.00"), threshold) == "Inactive"
    assert assign_segment(5, Decimal("100.00"), threshold) == "High-Value"
    assert assign_segment(5, Decimal("99.99"), threshold) == "Repeat"
    assert assign_segment(1, Decimal("50.00"), threshold) == "One-Time"
    assert assign_segment(1, Decimal("150.00"), threshold) == "High-Value"


def test_percentile_nearest_rank_basic():
    values = [Decimal(str(n)) for n in range(1, 11)]
    assert percentile_nearest_rank(values, 0.9) == Decimal("10")


def test_sales_by_product_excludes_fail_and_matches_pass_sum(annotated_rows):
    orders = annotated_rows["orders"]
    products = annotated_rows["products"]
    gold = aggregate_sales_by_product(orders, products)
    assert gold
    pass_products = {
        int(row["product_id"])
        for row in products
        if row["quality_check_result"] == "PASS"
    }
    gold_product_ids = {row["product_id"] for row in gold}
    assert gold_product_ids.issubset(pass_products)

    expected = Decimal("0.00")
    for order in orders:
        if order["quality_check_result"] != "PASS":
            continue
        if order.get("order_status") == "Cancelled":
            continue
        if order.get("product_id") in ("", None):
            continue
        product_id = int(order["product_id"])
        if product_id not in pass_products:
            continue
        expected += _money(order["total_amount"])
    actual = sum((row["total_revenue"] for row in gold), Decimal("0.00"))
    assert actual == expected
    for row in gold:
        assert row["avg_order_value"] == _money(
            row["total_revenue"] / row["total_orders"]
        )


def test_cancelled_orders_contribute_no_revenue(annotated_rows):
    orders = annotated_rows["orders"]
    products = annotated_rows["products"]
    customers = annotated_rows["customers"]
    cancelled_pass = [
        row
        for row in orders
        if row["quality_check_result"] == "PASS"
        and row.get("order_status") == "Cancelled"
    ]
    assert cancelled_pass, "fixture must include PASS Cancelled orders"
    cancelled_amount = sum(
        (_money(row["total_amount"]) for row in cancelled_pass), Decimal("0.00")
    )
    assert cancelled_amount > 0

    with_cancelled = Decimal("0.00")
    without_cancelled = Decimal("0.00")
    pass_products = {
        int(row["product_id"])
        for row in products
        if row["quality_check_result"] == "PASS"
    }
    for order in orders:
        if order["quality_check_result"] != "PASS":
            continue
        if order.get("product_id") in ("", None):
            continue
        if int(order["product_id"]) not in pass_products:
            continue
        amount = _money(order["total_amount"])
        with_cancelled += amount
        if order.get("order_status") != "Cancelled":
            without_cancelled += amount
    gold = aggregate_sales_by_product(orders, products)
    actual = sum((row["total_revenue"] for row in gold), Decimal("0.00"))
    assert actual == without_cancelled
    assert actual == with_cancelled - cancelled_amount

    trends = aggregate_daily_weekly_trends(orders)
    day_orders = sum(
        row["total_orders"] for row in trends if row["period_grain"] == "DAY"
    )
    qualifying = sum(
        1
        for row in orders
        if row["quality_check_result"] == "PASS"
        and row.get("order_status") != "Cancelled"
    )
    assert day_orders == qualifying
    # Segmentation revenue also excludes Cancelled.
    segments = aggregate_customer_segmentation(orders, customers)
    assert sum(row["total_revenue"] for row in segments) == sum(
        (
            row["total_revenue"]
            for row in aggregate_revenue_by_customer(orders, customers)
        ),
        Decimal("0.00"),
    )


def test_dashboard_queries_are_catalog_schema_agnostic():
    sql = (REPO_ROOT / "src/dashboard/dashboard_queries.sql").read_text(
        encoding="utf-8"
    )
    lvdash = (
        REPO_ROOT / "src/dashboard/ecommerce_gold_dashboard.lvdash.json"
    ).read_text(encoding="utf-8")
    resource = (
        REPO_ROOT / "resources/ecommerce_gold_dashboard.yml"
    ).read_text(encoding="utf-8")
    for text in (sql, lvdash):
        assert "`workspace`.`c1_gold`" not in text
        assert "workspace.c1_gold" not in text
        for table in GOLD_TABLES:
            assert table in text
    assert "dataset_catalog: ${var.catalog}" in resource
    assert "dataset_schema: ${var.gold_schema}" in resource


def test_revenue_by_customer_excludes_duplicates_and_sets_ltv(annotated_rows):
    customers = annotated_rows["customers"]
    orders = annotated_rows["orders"]
    gold = aggregate_revenue_by_customer(orders, customers)
    assert gold
    gold_ids = {row["customer_id"] for row in gold}
    for dup_id in DUPLICATE_CUSTOMER_IDS:
        assert dup_id not in gold_ids
    for row in gold:
        assert row["lifetime_value_actual"] == row["total_revenue"]
        assert row["avg_order_value"] == _money(
            row["total_revenue"] / row["total_orders"]
        )
    fail_order_ids = {
        int(row["order_id"])
        for row in orders
        if row["quality_check_result"] == "FAIL" and row.get("order_id") not in ("", None)
    }
    # Duplicate order keys are FAIL; their amounts must not enter customer totals
    # beyond the PASS-only filter already applied in the helper.
    assert fail_order_ids.issuperset(DUPLICATE_ORDER_IDS)


def test_daily_weekly_trends_grains(annotated_rows):
    trends = aggregate_daily_weekly_trends(annotated_rows["orders"])
    grains = {row["period_grain"] for row in trends}
    assert grains == {"DAY", "WEEK"}
    day_orders = sum(
        row["total_orders"] for row in trends if row["period_grain"] == "DAY"
    )
    week_orders = sum(
        row["total_orders"] for row in trends if row["period_grain"] == "WEEK"
    )
    pass_order_count = sum(
        1
        for row in annotated_rows["orders"]
        if row["quality_check_result"] == "PASS"
        and row.get("order_status") != "Cancelled"
    )
    assert day_orders == pass_order_count
    assert week_orders == pass_order_count
    for row in trends:
        if row["period_grain"] == "WEEK":
            assert row["period_start"].weekday() == 0


def test_customer_segmentation_covers_all_pass_customers(annotated_rows):
    segments = aggregate_customer_segmentation(
        annotated_rows["orders"], annotated_rows["customers"]
    )
    by_type = {row["segment_type"]: row for row in segments}
    assert set(by_type) == set(SEGMENT_TYPES)
    pass_customer_count = sum(
        1
        for row in annotated_rows["customers"]
        if row["quality_check_result"] == "PASS"
    )
    assert sum(row["customer_count"] for row in segments) == pass_customer_count
    assert by_type["High-Value"]["customer_count"] > 0
    assert by_type["Repeat"]["customer_count"] > 0
    assert by_type["One-Time"]["customer_count"] > 0
    # Inactive may be zero when every PASS customer has at least one PASS order.
    assert by_type["Inactive"]["customer_count"] >= 0
    for row in segments:
        if row["customer_count"]:
            assert row["avg_revenue"] == _money(
                row["total_revenue"] / row["customer_count"]
            )


def test_schema_sql_includes_gold_contract():
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS `__CATALOG__`.`__GOLD_SCHEMA__`" in sql
    expected = {
        "gold_sales_by_product": [
            ("product_id", "INT", False),
            ("product_name", "STRING", False),
            ("category", "STRING", False),
            ("total_orders", "BIGINT", False),
            ("total_revenue", "DECIMAL(18, 2)", False),
            ("avg_order_value", "DECIMAL(18, 2)", False),
        ],
        "gold_revenue_by_customer": [
            ("customer_id", "INT", False),
            ("customer_name", "STRING", False),
            ("customer_segment", "STRING", False),
            ("total_orders", "BIGINT", False),
            ("total_revenue", "DECIMAL(18, 2)", False),
            ("avg_order_value", "DECIMAL(18, 2)", False),
            ("lifetime_value_actual", "DECIMAL(18, 2)", False),
        ],
        "gold_daily_weekly_trends": [
            ("period_start", "DATE", False),
            ("period_grain", "STRING", False),
            ("total_orders", "BIGINT", False),
            ("total_revenue", "DECIMAL(18, 2)", False),
        ],
        "gold_customer_segmentation": [
            ("segment_type", "STRING", False),
            ("customer_count", "BIGINT", False),
            ("avg_revenue", "DECIMAL(18, 2)", False),
            ("total_revenue", "DECIMAL(18, 2)", False),
        ],
    }
    for table, columns in expected.items():
        assert _table_columns(sql, table) == columns
    without_gold = render_schema_statements("workspace", "c1_bronze", "c1_silver")
    assert len(without_gold) == 9
    assert all("__GOLD_SCHEMA__" not in statement for statement in without_gold)
    with_gold = render_schema_statements(
        "workspace", "c1_bronze", "c1_silver", "c1_gold"
    )
    assert len(with_gold) == 14
    rendered = "\n".join(with_gold)
    for table in GOLD_TABLES:
        assert f"`workspace`.`c1_gold`.`{table}`" in rendered


def _table_columns(sql: str, table: str):
    marker = (
        f"CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__GOLD_SCHEMA__`.`{table}` ("
    )
    start = sql.find(marker)
    assert start != -1, table
    body_start = start + len(marker)
    body_end = sql.find(")\nUSING DELTA", body_start)
    assert body_end != -1, table
    columns = []
    for raw_line in sql[body_start:body_end].splitlines():
        line = raw_line.strip().rstrip(",")
        if not line:
            continue
        name, rest = line.split(None, 1)
        not_null = rest.endswith("NOT NULL")
        sql_type = rest[: -len(" NOT NULL")].strip() if not_null else rest
        columns.append((name, sql_type, not not_null))
    return columns


def test_script_fails_fast_without_config():
    env = os.environ.copy()
    for name in (
        "PIPELINE_CATALOG",
        "PIPELINE_BRONZE_SCHEMA",
        "PIPELINE_SILVER_SCHEMA",
        "PIPELINE_GOLD_SCHEMA",
        "PIPELINE_LANDING_PATH",
    ):
        env.pop(name, None)
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "src" / "gold" / "create_gold_tables.py")],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert (
        "Missing required configuration: catalog, bronze_schema, "
        "silver_schema, landing_path"
    ) in completed.stderr


def test_script_reports_missing_gold_schema(tmp_path):
    env = os.environ.copy()
    for name in (
        "PIPELINE_CATALOG",
        "PIPELINE_BRONZE_SCHEMA",
        "PIPELINE_SILVER_SCHEMA",
        "PIPELINE_GOLD_SCHEMA",
        "PIPELINE_LANDING_PATH",
    ):
        env.pop(name, None)
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "src" / "gold" / "create_gold_tables.py"),
            "--catalog",
            "workspace",
            "--bronze-schema",
            "c1_bronze",
            "--silver-schema",
            "c1_silver",
            "--landing-path",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "gold_schema" in completed.stderr


def test_script_reports_missing_pyspark(tmp_path):
    try:
        import pyspark  # noqa: F401
    except ImportError:
        pyspark = None
    if pyspark is not None:
        pytest.skip("PySpark is installed; missing-runtime check is not applicable.")
    env = os.environ.copy()
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "src" / "gold" / "create_gold_tables.py"),
            "--catalog",
            "workspace",
            "--bronze-schema",
            "c1_bronze",
            "--silver-schema",
            "c1_silver",
            "--gold-schema",
            "c1_gold",
            "--landing-path",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "Run Gold aggregations on Databricks serverless." in completed.stderr


def test_missing_gold_schema_helper():
    with pytest.raises(ValueError, match="gold_schema"):
        _require_gold_schema(None)
    with pytest.raises(ValueError, match="gold_schema"):
        _require_gold_schema("  ")


def test_explicit_databricks_request_does_not_skip():
    env = os.environ.copy()
    env.pop("DATABRICKS_RUNTIME_VERSION", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_gold_aggregations.py",
            "-m",
            "databricks",
            "-q",
            "--override-ini",
            "addopts=",
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "This is not a pass." in output
    assert "skipped" not in output


def _databricks_marker_requested(request) -> bool:
    expression = (request.config.getoption("markexpr") or "").strip()
    if not expression:
        return False
    from _pytest.mark.expression import Expression

    return bool(Expression.compile(expression).evaluate(lambda mark: mark == "databricks"))


def _node_explicitly_requested(request) -> bool:
    node_name = request.node.name
    keyword = (request.config.getoption("keyword") or "").strip()
    if keyword and node_name in keyword:
        return True
    for arg in request.config.args:
        if "::" in str(arg) and node_name in str(arg):
            return True
    return False


def _skip_unless_databricks(request):
    on_databricks = bool(os.environ.get("DATABRICKS_RUNTIME_VERSION", "").strip())
    explicit = _databricks_marker_requested(request) or _node_explicitly_requested(request)
    if not on_databricks:
        if explicit:
            pytest.fail(
                "TS-05 was explicitly requested but DATABRICKS_RUNTIME_VERSION "
                "is not set. These checks must run on Databricks serverless. "
                "This is not a pass."
            )
        pytest.skip(
            "Not executed: TS-05 Spark/table checks run on Databricks serverless only."
        )
    from pyspark.sql import SparkSession

    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    try:
        config = resolve_config()
    except ValueError as exc:
        pytest.fail(str(exc))
    if not config.gold_schema:
        pytest.fail(
            "Missing gold_schema for TS-05. Set PIPELINE_GOLD_SCHEMA or the "
            "gold_schema widget."
        )
    return spark, config


def _silver_table(config, table: str) -> str:
    return f"`{config.catalog}`.`{config.silver_schema}`.`{table}`"


def _gold_table(config, table: str) -> str:
    return f"`{config.catalog}`.`{config.gold_schema}`.`{table}`"


def _count_where(spark, table: str, predicate: str = "1 = 1") -> int:
    row = spark.sql(f"SELECT COUNT(*) AS n FROM {table} WHERE {predicate}").collect()[0]
    return int(row["n"])


def _sum_decimal(spark, table: str, column: str, predicate: str = "1 = 1") -> Decimal:
    row = spark.sql(
        f"SELECT CAST(COALESCE(SUM({column}), 0) AS DECIMAL(18,2)) AS total "
        f"FROM {table} WHERE {predicate}"
    ).collect()[0]
    return Decimal(str(row["total"]))


@pytest.mark.databricks
def test_gold_tables_populated(request):
    spark, config = _skip_unless_databricks(request)
    for table in GOLD_TABLES:
        assert _count_where(spark, _gold_table(config, table)) > 0
    segments = {
        row["segment_type"]
        for row in spark.table(
            f"{config.catalog}.{config.gold_schema}.gold_customer_segmentation"
        ).collect()
    }
    assert segments == set(SEGMENT_TYPES)
    grains = {
        row["period_grain"]
        for row in spark.table(
            f"{config.catalog}.{config.gold_schema}.gold_daily_weekly_trends"
        ).collect()
    }
    assert grains == {"DAY", "WEEK"}


@pytest.mark.databricks
def test_gold_excludes_fail_and_duplicate_keys(request):
    spark, config = _skip_unless_databricks(request)
    customers = _gold_table(config, "gold_revenue_by_customer")
    products = _gold_table(config, "gold_sales_by_product")
    dup_customers = ", ".join(str(value) for value in DUPLICATE_CUSTOMER_IDS)
    assert _count_where(spark, customers, f"customer_id IN ({dup_customers})") == 0
    fail_customers = spark.sql(
        f"""
        SELECT COUNT(*) AS n
        FROM {customers} g
        INNER JOIN {_silver_table(config, 'silver_customers')} s
          ON g.customer_id = s.customer_id
        WHERE s.quality_check_result = 'FAIL'
        """
    ).collect()[0]["n"]
    assert int(fail_customers) == 0
    fail_products = spark.sql(
        f"""
        SELECT COUNT(*) AS n
        FROM {products} g
        INNER JOIN {_silver_table(config, 'silver_products')} s
          ON g.product_id = s.product_id
        WHERE s.quality_check_result = 'FAIL'
        """
    ).collect()[0]["n"]
    assert int(fail_products) == 0


@pytest.mark.databricks
def test_gold_revenue_reconciles_to_pass_silver(request):
    spark, config = _skip_unless_databricks(request)
    orders = _silver_table(config, "silver_orders")
    products = _silver_table(config, "silver_products")
    customers = _silver_table(config, "silver_customers")
    gold_products = _gold_table(config, "gold_sales_by_product")
    gold_customers = _gold_table(config, "gold_revenue_by_customer")
    gold_trends = _gold_table(config, "gold_daily_weekly_trends")

    expected_product_revenue = spark.sql(
        f"""
        SELECT CAST(COALESCE(SUM(o.total_amount), 0) AS DECIMAL(18,2)) AS total
        FROM {orders} o
        INNER JOIN {products} p ON o.product_id = p.product_id
        WHERE o.quality_check_result = 'PASS'
          AND o.order_status <> 'Cancelled'
          AND p.quality_check_result = 'PASS'
        """
    ).collect()[0]["total"]
    actual_product_revenue = _sum_decimal(spark, gold_products, "total_revenue")
    assert Decimal(str(expected_product_revenue)) == actual_product_revenue

    expected_customer_revenue = spark.sql(
        f"""
        SELECT CAST(COALESCE(SUM(o.total_amount), 0) AS DECIMAL(18,2)) AS total
        FROM {orders} o
        INNER JOIN {customers} c ON o.customer_id = c.customer_id
        WHERE o.quality_check_result = 'PASS'
          AND o.order_status <> 'Cancelled'
          AND c.quality_check_result = 'PASS'
        """
    ).collect()[0]["total"]
    actual_customer_revenue = _sum_decimal(spark, gold_customers, "total_revenue")
    assert Decimal(str(expected_customer_revenue)) == actual_customer_revenue

    pass_order_count = _count_where(
        spark,
        orders,
        "quality_check_result = 'PASS' AND order_status <> 'Cancelled'",
    )
    day_orders = _count_where(spark, gold_trends, "period_grain = 'DAY'")
    # day grain row count is periods, not orders — compare summed orders
    day_order_sum = spark.sql(
        f"""
        SELECT CAST(SUM(total_orders) AS BIGINT) AS n
        FROM {gold_trends}
        WHERE period_grain = 'DAY'
        """
    ).collect()[0]["n"]
    week_order_sum = spark.sql(
        f"""
        SELECT CAST(SUM(total_orders) AS BIGINT) AS n
        FROM {gold_trends}
        WHERE period_grain = 'WEEK'
        """
    ).collect()[0]["n"]
    assert int(day_order_sum) == pass_order_count
    assert int(week_order_sum) == pass_order_count
    assert day_orders > 0
