"""TS-03 / TS-04 checks for Silver validation.

Local tests apply the four core checks to the sample CSVs in memory.
They do not start Spark. Tests marked databricks compare Bronze to Silver
Delta tables and the dq_metrics_report. Those skip unless run on Databricks
serverless. A skip is not a pass.
"""

from __future__ import annotations

import csv
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.config import resolve_config
from src.silver import create_silver_tables as silver_mod
from src.silver.create_silver_tables import (
    BUSINESS_COLUMNS,
    CHECK_ORDER,
    DQ_METRICS_TABLE,
    METADATA_COLUMNS,
    QUALITY_COLUMNS,
    SCHEMA_PATH,
    SILVER_TABLES,
    annotate_entities,
    category_fail_count,
    render_schema_statements,
    run_main,
)
from src.silver.values import is_blank, is_date_value, is_decimal_value, is_int_value

completeness = importlib.import_module("src.silver.01_quality_completeness")
uniqueness = importlib.import_module("src.silver.02_quality_uniqueness")
type_validation = importlib.import_module("src.silver.03_quality_type_validation")
referential_integrity = importlib.import_module("src.silver.04_quality_referential_integrity")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
SILVER_DIR = REPO_ROOT / "src" / "silver"
CREATE_SOURCE = SILVER_DIR / "create_silver_tables.py"

# Literals from data-quality-strategy.md / DATA_GENERATION_NOTES.md.
CUSTOMER_ROWS = 10000
ORDER_ROWS = 100000
PRODUCT_ROWS = 500
NULL_EMAILS = 50
CUSTOMER_UNIQUENESS_FAILS = 10
NULL_ORDER_CUSTOMER_IDS = 100
NULL_ORDER_PRODUCT_IDS = 200
UNKNOWN_CUSTOMER_IDS = 50
UNKNOWN_PRODUCT_IDS = 30
ORDER_UNIQUENESS_FAILS = 20
CUSTOMER_FAIL_ROWS = 60
ORDER_FAIL_ROWS = 400
DISTINCT_DEFECT_ROWS = 460
DUPLICATE_CUSTOMER_IDS = (51, 53, 55, 57, 59)
DUPLICATE_ORDER_IDS = (381, 383, 385, 387, 389, 391, 393, 395, 397, 399)
ABSENT_CUSTOMER_IDS = (52, 54, 56, 58, 60)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def sample_rows():
    customers = _read_csv(DATA_DIR / "customers.csv")
    orders = _read_csv(DATA_DIR / "orders.csv")
    products = _read_csv(DATA_DIR / "products.csv")
    return annotate_entities(customers, orders, products)


def test_check_order_matches_strategy():
    assert CHECK_ORDER == (
        "completeness",
        "type_validation",
        "uniqueness",
        "referential_integrity",
    )


def test_value_helpers():
    assert is_blank(None)
    assert is_blank("")
    assert is_blank("  ")
    assert not is_blank("a@example.test")
    assert is_int_value("12")
    assert not is_int_value("12.5")
    assert is_decimal_value("12.50")
    assert is_date_value("2024-01-02")
    assert not is_date_value("2024-1-2")


def test_completeness_rules():
    assert completeness.row_failed("customers", {"email": None})
    assert completeness.row_failed("customers", {"email": "  "})
    assert not completeness.row_failed("customers", {"email": "a@example.test"})
    assert completeness.row_failed("orders", {"customer_id": None, "product_id": 1})
    assert completeness.row_failed("orders", {"customer_id": 1, "product_id": ""})
    assert not completeness.row_failed("orders", {"customer_id": 1, "product_id": 2})


def test_uniqueness_marks_every_duplicate_row():
    rows = [{"customer_id": "1"}, {"customer_id": "1"}, {"customer_id": "2"}]
    dups = uniqueness.duplicate_key_set(rows, "customer_id")
    assert dups == {1}
    assert uniqueness.row_failed("1", dups)
    assert not uniqueness.row_failed("2", dups)


def test_type_validation_domains_and_required_fields():
    good_customer = {
        "customer_id": "1",
        "customer_name": "Ada",
        "country": "India",
        "signup_date": "2020-01-01",
        "customer_segment": "Basic",
        "lifetime_value": "1.00",
    }
    assert not type_validation.row_failed("customers", good_customer)
    bad = dict(good_customer)
    bad["customer_segment"] = "Gold"
    assert type_validation.row_failed("customers", bad)
    bad_order = {
        "order_id": "1",
        "customer_id": "",
        "order_date": "2023-01-01",
        "product_id": "",
        "quantity": "1",
        "unit_price": "1.00",
        "total_amount": "1.00",
        "order_status": "Pending",
        "payment_date": "",
    }
    assert not type_validation.row_failed("orders", bad_order)


def test_referential_integrity_ignores_null_fks():
    parents_c = {1}
    parents_p = {10}
    assert not referential_integrity.row_failed(
        {"customer_id": "", "product_id": "10"}, parents_c, parents_p
    )
    assert referential_integrity.row_failed(
        {"customer_id": "9", "product_id": "10"}, parents_c, parents_p
    )
    assert referential_integrity.row_failed(
        {"customer_id": "1", "product_id": "99"}, parents_c, parents_p
    )


def test_local_row_counts_preserved(sample_rows):
    assert len(sample_rows["customers"]) == CUSTOMER_ROWS
    assert len(sample_rows["orders"]) == ORDER_ROWS
    assert len(sample_rows["products"]) == PRODUCT_ROWS


def test_ts03_detects_intentional_defect_counts(sample_rows):
    customers = sample_rows["customers"]
    orders = sample_rows["orders"]
    products = sample_rows["products"]

    assert category_fail_count(customers, "completeness") == NULL_EMAILS
    assert category_fail_count(customers, "uniqueness") == CUSTOMER_UNIQUENESS_FAILS
    assert category_fail_count(customers, "type_validation") == 0
    assert category_fail_count(customers, "referential_integrity") == 0

    assert category_fail_count(orders, "completeness") == (
        NULL_ORDER_CUSTOMER_IDS + NULL_ORDER_PRODUCT_IDS
    )
    assert category_fail_count(orders, "uniqueness") == ORDER_UNIQUENESS_FAILS
    assert category_fail_count(orders, "referential_integrity") == (
        UNKNOWN_CUSTOMER_IDS + UNKNOWN_PRODUCT_IDS
    )
    assert category_fail_count(orders, "type_validation") == 0

    assert category_fail_count(products, "completeness") == 0
    assert category_fail_count(products, "uniqueness") == 0
    assert category_fail_count(products, "type_validation") == 0
    assert category_fail_count(products, "referential_integrity") == 0

    customer_fails = sum(1 for row in customers if row["quality_check_result"] == "FAIL")
    order_fails = sum(1 for row in orders if row["quality_check_result"] == "FAIL")
    product_fails = sum(1 for row in products if row["quality_check_result"] == "FAIL")
    assert customer_fails == CUSTOMER_FAIL_ROWS
    assert order_fails == ORDER_FAIL_ROWS
    assert product_fails == 0
    assert customer_fails + order_fails + product_fails == DISTINCT_DEFECT_ROWS


def test_ts03_duplicate_keys_match_generator(sample_rows):
    customers = sample_rows["customers"]
    orders = sample_rows["orders"]
    customer_dup_ids = sorted(
        {
            int(row["customer_id"])
            for row in customers
            if "uniqueness" in row["failed_checks"]
        }
    )
    order_dup_ids = sorted(
        {
            int(row["order_id"])
            for row in orders
            if "uniqueness" in row["failed_checks"]
        }
    )
    assert customer_dup_ids == list(DUPLICATE_CUSTOMER_IDS)
    assert order_dup_ids == list(DUPLICATE_ORDER_IDS)
    for absent in ABSENT_CUSTOMER_IDS:
        assert all(int(row["customer_id"]) != absent for row in customers)


def test_ts04_known_good_rows_pass(sample_rows):
    customers = sample_rows["customers"]
    orders = sample_rows["orders"]
    products = sample_rows["products"]

    assert sum(1 for row in customers if row["quality_check_result"] == "PASS") == (
        CUSTOMER_ROWS - CUSTOMER_FAIL_ROWS
    )
    assert sum(1 for row in orders if row["quality_check_result"] == "PASS") == (
        ORDER_ROWS - ORDER_FAIL_ROWS
    )
    assert all(row["quality_check_result"] == "PASS" for row in products)
    assert all(row["failed_checks"] == [] for row in products)

    # First clean customer and order after the chained defect slices.
    assert customers[60]["quality_check_result"] == "PASS"
    assert customers[60]["failed_checks"] == []
    assert not is_blank(customers[60]["email"])
    assert orders[400]["quality_check_result"] == "PASS"
    assert orders[400]["failed_checks"] == []
    assert not is_blank(orders[400]["customer_id"])
    assert not is_blank(orders[400]["product_id"])


def test_create_source_overwrites_and_retains_rows():
    source = CREATE_SOURCE.read_text(encoding="utf-8")
    assert '.mode("overwrite")' in source
    assert "overwriteSchema" in source
    assert "quality_check_result" in source
    assert "failed_checks" in source
    assert DQ_METRICS_TABLE in source
    assert "dropDuplicates" not in source
    assert "dropna" not in source
    # Metrics may count with where(); Silver writes must keep the full frame.
    write_block = source.split("def write_silver_tables", 1)[1].split(
        "def build_metrics_rows", 1
    )[0]
    assert ".filter(" not in write_block
    assert ".where(" not in write_block
    assert "dropDuplicates" not in write_block


def test_missing_bronze_fails_before_schema_apply(monkeypatch):
    """schema.sql creates bronze_* DDL; applying it first would mask missing ingest."""

    class Catalog:
        @staticmethod
        def tableExists(_name):
            return False

    class Spark:
        catalog = Catalog()

    applied = []

    def track_apply(*_args, **_kwargs):
        applied.append("apply_schema")

    monkeypatch.setattr(silver_mod, "apply_schema", track_apply)
    with pytest.raises(
        FileNotFoundError,
        match="Bronze tables required for Silver are missing",
    ):
        silver_mod.create_silver_tables(Spark(), "main", "ecommerce")
    assert applied == []

    calls = []

    def require(*_args, **_kwargs):
        calls.append("require_bronze")

    def apply_then_stop(*_args, **_kwargs):
        calls.append("apply_schema")
        raise RuntimeError("stop-after-order-check")

    monkeypatch.setattr(silver_mod, "_require_bronze", require)
    monkeypatch.setattr(silver_mod, "apply_schema", apply_then_stop)
    with pytest.raises(RuntimeError, match="stop-after-order-check"):
        silver_mod.create_silver_tables(object(), "main", "ecommerce")
    assert calls == ["require_bronze", "apply_schema"]


def test_script_fails_fast_without_config():
    env = os.environ.copy()
    for name in ("PIPELINE_CATALOG", "PIPELINE_SCHEMA", "PIPELINE_LANDING_PATH"):
        env.pop(name, None)
    completed = subprocess.run(
        [sys.executable, str(SILVER_DIR / "create_silver_tables.py")],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "Missing required configuration: catalog, schema, landing_path" in completed.stderr


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
            str(SILVER_DIR / "create_silver_tables.py"),
            "--catalog",
            "main",
            "--schema",
            "ecommerce",
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
    assert "Run Silver validation on Databricks serverless." in completed.stderr


def test_run_main_rejects_invalid_catalog(capsys):
    code = run_main(
        [
            "--catalog",
            "main;drop",
            "--schema",
            "ecommerce",
            "--landing-path",
            "/Volumes/main/ecommerce/landing",
        ]
    )
    assert code == 1
    assert "Invalid catalog" in capsys.readouterr().err


def _table_columns(sql: str, table: str):
    marker = f"CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__SCHEMA__`.`{table}` ("
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
        sql_type = rest[: -len("NOT NULL")].strip() if not_null else rest
        columns.append((name, sql_type, not not_null))
    return columns


def test_schema_sql_matches_silver_contract():
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    expected_quality = (
        ("quality_check_result", "STRING", False),
        ("failed_checks", "ARRAY<STRING>", False),
        ("_silver_processed_at", "TIMESTAMP", False),
    )
    expected_meta = (
        ("_ingested_at", "TIMESTAMP", False),
        ("_source_file", "STRING", False),
        ("_ingestion_batch_id", "STRING", False),
    )
    customer_business = [
        ("customer_id", "INT", False),
        ("customer_name", "STRING", False),
        ("email", "STRING", True),
        ("country", "STRING", False),
        ("signup_date", "DATE", False),
        ("customer_segment", "STRING", False),
        ("lifetime_value", "DECIMAL(18, 2)", False),
    ]
    order_business = [
        ("order_id", "INT", False),
        ("customer_id", "INT", True),
        ("order_date", "DATE", False),
        ("product_id", "INT", True),
        ("quantity", "INT", False),
        ("unit_price", "DECIMAL(18, 2)", False),
        ("total_amount", "DECIMAL(18, 2)", False),
        ("order_status", "STRING", False),
        ("payment_date", "DATE", True),
    ]
    product_business = [
        ("product_id", "INT", False),
        ("product_name", "STRING", False),
        ("category", "STRING", False),
        ("price", "DECIMAL(18, 2)", False),
        ("cost", "DECIMAL(18, 2)", False),
        ("stock_quantity", "INT", False),
        ("reorder_level", "INT", False),
    ]
    assert _table_columns(sql, "silver_customers") == (
        customer_business + list(expected_meta) + list(expected_quality)
    )
    assert _table_columns(sql, "silver_orders") == (
        order_business + list(expected_meta) + list(expected_quality)
    )
    assert _table_columns(sql, "silver_products") == (
        product_business + list(expected_meta) + list(expected_quality)
    )
    assert _table_columns(sql, DQ_METRICS_TABLE) == [
        ("check_category", "STRING", False),
        ("entity", "STRING", False),
        ("rows_evaluated", "BIGINT", False),
        ("rows_passed", "BIGINT", False),
        ("rows_failed", "BIGINT", False),
        ("pass_pct", "DOUBLE", False),
        ("reported_at", "TIMESTAMP", False),
    ]
    statements = render_schema_statements("main", "ecommerce")
    rendered = "\n".join(statements)
    assert len(statements) == 8
    assert SILVER_TABLES["customers"] in rendered
    assert DQ_METRICS_TABLE in rendered
    assert tuple(BUSINESS_COLUMNS["customers"]) == tuple(
        name for name, _type, _null in customer_business
    )
    assert METADATA_COLUMNS == ("_ingested_at", "_source_file", "_ingestion_batch_id")
    assert QUALITY_COLUMNS == (
        "quality_check_result",
        "failed_checks",
        "_silver_processed_at",
    )


def test_explicit_databricks_request_does_not_skip():
    env = os.environ.copy()
    env.pop("DATABRICKS_RUNTIME_VERSION", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_silver_validation.py",
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
                "TS-03/TS-04 were explicitly requested but DATABRICKS_RUNTIME_VERSION "
                "is not set. These checks must run on Databricks serverless. "
                "This is not a pass."
            )
        pytest.skip(
            "Not executed: TS-03/TS-04 Spark/table checks run on Databricks serverless only."
        )
    from pyspark.sql import SparkSession

    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    try:
        config = resolve_config()
    except ValueError as exc:
        pytest.fail(str(exc))
    return spark, config


def _table(config, table: str) -> str:
    return f"`{config.catalog}`.`{config.schema}`.`{table}`"


def _count_where(spark, table: str, predicate: str = "1 = 1") -> int:
    row = spark.sql(f"SELECT COUNT(*) AS n FROM {table} WHERE {predicate}").collect()[0]
    return int(row["n"])


@pytest.mark.databricks
def test_silver_row_counts_match_bronze(request):
    spark, config = _skip_unless_databricks(request)
    pairs = (
        ("bronze_customers", "silver_customers", CUSTOMER_ROWS),
        ("bronze_orders", "silver_orders", ORDER_ROWS),
        ("bronze_products", "silver_products", PRODUCT_ROWS),
    )
    for bronze_name, silver_name, target in pairs:
        bronze = _count_where(spark, _table(config, bronze_name))
        silver = _count_where(spark, _table(config, silver_name))
        assert bronze == target
        assert silver == bronze


@pytest.mark.databricks
def test_silver_detects_intentional_defects(request):
    spark, config = _skip_unless_databricks(request)
    customers = _table(config, "silver_customers")
    orders = _table(config, "silver_orders")
    products = _table(config, "silver_products")

    assert _count_where(
        spark, customers, "array_contains(failed_checks, 'completeness')"
    ) == NULL_EMAILS
    assert _count_where(
        spark, customers, "array_contains(failed_checks, 'uniqueness')"
    ) == CUSTOMER_UNIQUENESS_FAILS
    assert _count_where(
        spark, customers, "array_contains(failed_checks, 'type_validation')"
    ) == 0
    assert _count_where(spark, customers, "quality_check_result = 'FAIL'") == CUSTOMER_FAIL_ROWS

    assert _count_where(
        spark, orders, "array_contains(failed_checks, 'completeness')"
    ) == NULL_ORDER_CUSTOMER_IDS + NULL_ORDER_PRODUCT_IDS
    assert _count_where(
        spark, orders, "array_contains(failed_checks, 'uniqueness')"
    ) == ORDER_UNIQUENESS_FAILS
    assert _count_where(
        spark, orders, "array_contains(failed_checks, 'referential_integrity')"
    ) == UNKNOWN_CUSTOMER_IDS + UNKNOWN_PRODUCT_IDS
    assert _count_where(
        spark, orders, "array_contains(failed_checks, 'type_validation')"
    ) == 0
    assert _count_where(spark, orders, "quality_check_result = 'FAIL'") == ORDER_FAIL_ROWS

    assert _count_where(spark, products, "quality_check_result = 'FAIL'") == 0
    assert (
        _count_where(spark, customers, "quality_check_result = 'FAIL'")
        + _count_where(spark, orders, "quality_check_result = 'FAIL'")
        + _count_where(spark, products, "quality_check_result = 'FAIL'")
    ) == DISTINCT_DEFECT_ROWS


@pytest.mark.databricks
def test_silver_known_good_rows_pass(request):
    spark, config = _skip_unless_databricks(request)
    customers = _table(config, "silver_customers")
    orders = _table(config, "silver_orders")
    products = _table(config, "silver_products")
    assert _count_where(spark, customers, "quality_check_result = 'PASS'") == (
        CUSTOMER_ROWS - CUSTOMER_FAIL_ROWS
    )
    assert _count_where(spark, orders, "quality_check_result = 'PASS'") == (
        ORDER_ROWS - ORDER_FAIL_ROWS
    )
    assert _count_where(spark, products, "quality_check_result = 'PASS'") == PRODUCT_ROWS
    assert _count_where(spark, products, "size(failed_checks) = 0") == PRODUCT_ROWS


@pytest.mark.databricks
def test_dq_metrics_report_matches_strategy(request):
    spark, config = _skip_unless_databricks(request)
    table = _table(config, DQ_METRICS_TABLE)
    rows = {
        (row["check_category"], row["entity"]): row
        for row in spark.table(f"{config.catalog}.{config.schema}.{DQ_METRICS_TABLE}").collect()
    }
    expected = {
        ("completeness", "customers"): (CUSTOMER_ROWS, NULL_EMAILS),
        ("completeness", "orders"): (
            ORDER_ROWS,
            NULL_ORDER_CUSTOMER_IDS + NULL_ORDER_PRODUCT_IDS,
        ),
        ("uniqueness", "customers"): (CUSTOMER_ROWS, CUSTOMER_UNIQUENESS_FAILS),
        ("uniqueness", "orders"): (ORDER_ROWS, ORDER_UNIQUENESS_FAILS),
        ("type_validation", "customers"): (CUSTOMER_ROWS, 0),
        ("type_validation", "orders"): (ORDER_ROWS, 0),
        ("type_validation", "products"): (PRODUCT_ROWS, 0),
        ("referential_integrity", "orders"): (
            ORDER_ROWS,
            UNKNOWN_CUSTOMER_IDS + UNKNOWN_PRODUCT_IDS,
        ),
    }
    assert set(rows) == set(expected)
    for key, (evaluated, failed) in expected.items():
        row = rows[key]
        assert int(row["rows_evaluated"]) == evaluated
        assert int(row["rows_failed"]) == failed
        assert int(row["rows_passed"]) == evaluated - failed
        assert float(row["pass_pct"]) == round(((evaluated - failed) / evaluated) * 100, 2)
    assert _count_where(spark, table) == len(expected)
