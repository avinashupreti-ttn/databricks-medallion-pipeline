"""TS-02 checks for Bronze ingestion.

Local tests cover configuration, input failures, and schema.sql.
They do not start Spark. Tests marked databricks compare landing CSVs
to Bronze Delta tables. Those skip unless run on Databricks serverless.
A skip is not a pass.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.bronze.ingest import (
    CUSTOMER_FIELDS,
    ENTITIES,
    METADATA_FIELDS,
    ORDER_FIELDS,
    PRODUCT_FIELDS,
    SCHEMA_PATH,
    assert_local_csv_ready,
    is_remote_path,
    join_landing_path,
    render_schema_statements,
    run_main,
)
from src.config import resolve_config

REPO_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = REPO_ROOT / "src" / "bronze"
INGEST_SOURCE = BRONZE_DIR / "ingest.py"

CUSTOMER_HEADER = (
    "customer_id,customer_name,email,country,signup_date,customer_segment,lifetime_value"
)
CUSTOMER_ROW = "1,Customer,a@example.test,India,2020-01-01,Basic,1.00"

# Contract literals from data-model.md / DATA_GENERATION_NOTES.md. Not imported
# from the generator.
DUPLICATE_CUSTOMER_IDS = (51, 53, 55, 57, 59)
ABSENT_CUSTOMER_IDS = (52, 54, 56, 58, 60)
DUPLICATE_ORDER_IDS = (381, 383, 385, 387, 389, 391, 393, 395, 397, 399)
SQL_TYPE = {
    "int": "INT",
    "string": "STRING",
    "date": "DATE",
    "decimal": "DECIMAL(18, 2)",
    "timestamp": "TIMESTAMP",
}

# Literals from data-model.md. Not taken from the ingestion module.
CONTRACT_CUSTOMERS = (
    ("customer_id", "int", False),
    ("customer_name", "string", False),
    ("email", "string", True),
    ("country", "string", False),
    ("signup_date", "date", False),
    ("customer_segment", "string", False),
    ("lifetime_value", "decimal", False),
)
CONTRACT_ORDERS = (
    ("order_id", "int", False),
    ("customer_id", "int", True),
    ("order_date", "date", False),
    ("product_id", "int", True),
    ("quantity", "int", False),
    ("unit_price", "decimal", False),
    ("total_amount", "decimal", False),
    ("order_status", "string", False),
    ("payment_date", "date", True),
)
CONTRACT_PRODUCTS = (
    ("product_id", "int", False),
    ("product_name", "string", False),
    ("category", "string", False),
    ("price", "decimal", False),
    ("cost", "decimal", False),
    ("stock_quantity", "int", False),
    ("reorder_level", "int", False),
)
CONTRACT_METADATA = (
    ("_ingested_at", "timestamp", False),
    ("_source_file", "string", False),
    ("_ingestion_batch_id", "string", False),
)
CONTRACT_TABLES = (
    ("customers.csv", "bronze_customers", 10000),
    ("orders.csv", "bronze_orders", 100000),
    ("products.csv", "bronze_products", 500),
)


def _customer_csv(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_missing_config_names_every_setting(monkeypatch):
    for name in ("PIPELINE_CATALOG", "PIPELINE_SCHEMA", "PIPELINE_LANDING_PATH"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="Missing required configuration: catalog, schema, landing_path"):
        resolve_config()


def test_env_fills_settings_and_args_win(monkeypatch):
    monkeypatch.setenv("PIPELINE_CATALOG", "from_env")
    monkeypatch.setenv("PIPELINE_SCHEMA", "ecommerce")
    monkeypatch.setenv("PIPELINE_LANDING_PATH", "/Volumes/main/ecommerce/landing")
    config = resolve_config()
    assert config.catalog == "from_env"
    overridden = resolve_config("main", None, None)
    assert overridden.catalog == "main"
    assert overridden.schema == "ecommerce"
    assert overridden.landing_path == "/Volumes/main/ecommerce/landing"


def test_invalid_catalog_rejected():
    with pytest.raises(ValueError, match="Invalid catalog"):
        resolve_config("main;drop", "ecommerce", "/Volumes/main/ecommerce/landing")


def test_join_landing_path_keeps_volume_and_dbfs_forms():
    assert (
        join_landing_path("/Volumes/main/ecommerce/landing/", "customers.csv")
        == "/Volumes/main/ecommerce/landing/customers.csv"
    )
    assert join_landing_path("dbfs:/landing", "orders.csv") == "dbfs:/landing/orders.csv"
    with pytest.raises(ValueError, match="Invalid landing path"):
        join_landing_path("/", "products.csv")


def test_remote_path_detection():
    assert is_remote_path("dbfs:/landing/customers.csv")
    assert is_remote_path("s3://bucket/orders.csv")
    assert not is_remote_path("/Volumes/main/ecommerce/landing/products.csv")


def test_local_csv_ready_accepts_one_data_row(tmp_path):
    path = tmp_path / "customers.csv"
    _customer_csv(path, CUSTOMER_HEADER + "\n" + CUSTOMER_ROW + "\n")
    assert_local_csv_ready(str(path), CUSTOMER_FIELDS)


def test_missing_csv_names_the_file(tmp_path):
    path = tmp_path / "customers.csv"
    with pytest.raises(FileNotFoundError, match=f"Source file not found: {path}"):
        assert_local_csv_ready(str(path), CUSTOMER_FIELDS)


def test_empty_csv_names_the_file(tmp_path):
    path = tmp_path / "customers.csv"
    path.write_bytes(b"")
    with pytest.raises(ValueError, match=f"Source file is empty: {path}"):
        assert_local_csv_ready(str(path), CUSTOMER_FIELDS)


def test_header_only_csv_names_the_file(tmp_path):
    path = tmp_path / "customers.csv"
    _customer_csv(path, CUSTOMER_HEADER + "\n")
    with pytest.raises(ValueError, match=f"Source file has no data rows: {path}"):
        assert_local_csv_ready(str(path), CUSTOMER_FIELDS)


def test_wrong_columns_names_the_file(tmp_path):
    path = tmp_path / "customers.csv"
    _customer_csv(path, "id,name\n1,Ada\n")
    with pytest.raises(ValueError, match=f"Source file columns do not match the contract: {path}"):
        assert_local_csv_ready(str(path), CUSTOMER_FIELDS)


def test_directory_is_not_a_readable_file(tmp_path):
    with pytest.raises(ValueError, match=f"Source path is not a readable file: {tmp_path}"):
        assert_local_csv_ready(str(tmp_path), CUSTOMER_FIELDS)


def test_unreadable_csv_names_the_file(tmp_path):
    path = tmp_path / "customers.csv"
    _customer_csv(path, CUSTOMER_HEADER + "\n" + CUSTOMER_ROW + "\n")
    path.chmod(0)
    try:
        with pytest.raises(PermissionError, match=f"Source file is not readable: {path}"):
            assert_local_csv_ready(str(path), CUSTOMER_FIELDS)
    finally:
        path.chmod(0o644)


def test_unsafe_batch_id_fails_before_spark(capsys):
    code = run_main(
        "customers",
        [
            "--catalog",
            "main",
            "--schema",
            "ecommerce",
            "--landing-path",
            "/Volumes/main/ecommerce/landing",
            "--batch-id",
            "bad;id",
        ],
    )
    assert code == 1
    assert "Invalid batch id" in capsys.readouterr().err


@pytest.mark.parametrize(
    "script_name",
    [
        "01_ingest_customers.py",
        "02_ingest_orders.py",
        "03_ingest_products.py",
        "ingest_all.py",
    ],
)
def test_scripts_fail_fast_without_config(script_name):
    env = os.environ.copy()
    for name in ("PIPELINE_CATALOG", "PIPELINE_SCHEMA", "PIPELINE_LANDING_PATH"):
        env.pop(name, None)
    completed = subprocess.run(
        [sys.executable, str(BRONZE_DIR / script_name)],
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
            str(BRONZE_DIR / "ingest_all.py"),
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
    assert "Run Bronze ingestion on Databricks serverless." in completed.stderr


def test_entity_order_and_filenames():
    assert tuple(ENTITIES) == ("customers", "orders", "products")
    assert ENTITIES["customers"]["filename"] == "customers.csv"
    assert ENTITIES["orders"]["table"] == "bronze_orders"
    assert ENTITIES["products"]["table"] == "bronze_products"


def test_ingest_source_overwrites_and_does_not_drop_rows():
    source = INGEST_SOURCE.read_text(encoding="utf-8")
    config_source = (REPO_ROOT / "src" / "config.py").read_text(encoding="utf-8")
    assert '.mode("overwrite")' in source
    assert "overwriteSchema" in source
    forbidden = (
        "dropDuplicates",
        "dropna",
        ".filter(",
        ".where(",
        "distinct(",
        ".cache(",
        ".persist(",
        ".unpersist(",
        "_jvm",
        "_jsc",
        "SparkContext",
    )
    for token in forbidden:
        assert token not in source
        assert token not in config_source


def test_explicit_databricks_request_does_not_skip():
    env = os.environ.copy()
    env.pop("DATABRICKS_RUNTIME_VERSION", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_bronze_ingestion.py",
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


def test_schema_sql_matches_bronze_contract():
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "CREATE CATALOG" not in sql
    assert "CREATE SCHEMA IF NOT EXISTS `__CATALOG__`.`__SCHEMA__`" in sql
    assert CUSTOMER_FIELDS == CONTRACT_CUSTOMERS
    assert ORDER_FIELDS == CONTRACT_ORDERS
    assert PRODUCT_FIELDS == CONTRACT_PRODUCTS
    assert METADATA_FIELDS == CONTRACT_METADATA
    expected = {
        "bronze_customers": CONTRACT_CUSTOMERS + CONTRACT_METADATA,
        "bronze_orders": CONTRACT_ORDERS + CONTRACT_METADATA,
        "bronze_products": CONTRACT_PRODUCTS + CONTRACT_METADATA,
    }
    for table, fields in expected.items():
        parsed = _table_columns(sql, table)
        contract = [
            (name, SQL_TYPE[kind], nullable) for name, kind, nullable in fields
        ]
        assert parsed == contract
    statements = render_schema_statements("main", "ecommerce")
    rendered = "\n".join(statements)
    assert len(statements) == 4
    assert "__CATALOG__" not in rendered
    assert "`main`.`ecommerce`.`bronze_customers`" in rendered
    assert "`main`.`ecommerce`.`bronze_orders`" in rendered
    assert "`main`.`ecommerce`.`bronze_products`" in rendered
    assert rendered.count("USING DELTA") == 3
    with pytest.raises(ValueError, match="Invalid catalog"):
        render_schema_statements("bad name", "ecommerce")


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
                "TS-02 was explicitly requested but DATABRICKS_RUNTIME_VERSION is not set. "
                "These checks must run on Databricks serverless. This is not a pass."
            )
        pytest.skip(
            "Not executed: TS-02 Spark/table checks run on Databricks serverless only."
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
def test_bronze_row_counts_match_source_and_targets(request):
    spark, config = _skip_unless_databricks(request)
    for filename, table_name, target in CONTRACT_TABLES:
        path = join_landing_path(config.landing_path, filename)
        source_count = (
            spark.read.option("header", "true").option("inferSchema", "false").csv(path).count()
        )
        table = _table(config, table_name)
        bronze_count = _count_where(spark, table)
        assert source_count == target
        assert bronze_count == source_count


@pytest.mark.databricks
def test_bronze_preserves_customer_defects(request):
    spark, config = _skip_unless_databricks(request)
    table = _table(config, "bronze_customers")
    assert _count_where(spark, table, "email IS NULL") == 50
    assert _count_where(spark, table, "customer_id IS NULL") == 0
    absent = ", ".join(str(value) for value in ABSENT_CUSTOMER_IDS)
    assert _count_where(spark, table, f"customer_id IN ({absent})") == 0
    rows = spark.sql(
        f"""
        SELECT customer_id, COUNT(*) AS row_count
        FROM {table}
        GROUP BY customer_id
        HAVING COUNT(*) > 1
        ORDER BY customer_id
        """
    ).collect()
    assert [(int(row["customer_id"]), int(row["row_count"])) for row in rows] == [
        (value, 2) for value in DUPLICATE_CUSTOMER_IDS
    ]


@pytest.mark.databricks
def test_bronze_preserves_order_defects(request):
    spark, config = _skip_unless_databricks(request)
    table = _table(config, "bronze_orders")
    assert _count_where(spark, table, "customer_id IS NULL") == 100
    assert _count_where(spark, table, "product_id IS NULL") == 200
    assert _count_where(spark, table, "customer_id IS NULL AND product_id IS NULL") == 0
    assert _count_where(spark, table, "customer_id BETWEEN 2000001 AND 2000050") == 50
    assert _count_where(spark, table, "product_id BETWEEN 3000001 AND 3000030") == 30
    rows = spark.sql(
        f"""
        SELECT order_id, COUNT(*) AS row_count
        FROM {table}
        GROUP BY order_id
        HAVING COUNT(*) > 1
        ORDER BY order_id
        """
    ).collect()
    assert [(int(row["order_id"]), int(row["row_count"])) for row in rows] == [
        (value, 2) for value in DUPLICATE_ORDER_IDS
    ]


@pytest.mark.databricks
def test_bronze_preserves_products(request):
    spark, config = _skip_unless_databricks(request)
    table = _table(config, "bronze_products")
    row = spark.sql(
        f"""
        SELECT
          COUNT(*) AS n,
          COUNT(DISTINCT product_id) AS distinct_ids,
          SUM(CASE WHEN product_id IS NULL THEN 1 ELSE 0 END) AS null_ids
        FROM {table}
        """
    ).collect()[0]
    assert int(row["n"]) == 500
    assert int(row["distinct_ids"]) == 500
    assert int(row["null_ids"]) == 0


@pytest.mark.databricks
def test_bronze_metadata_columns_are_populated(request):
    spark, config = _skip_unless_databricks(request)
    for filename, table_name, _target in CONTRACT_TABLES:
        table = _table(config, table_name)
        row = spark.sql(
            f"""
            SELECT
              SUM(
                CASE
                  WHEN _ingested_at IS NULL
                    OR _source_file IS NULL
                    OR _ingestion_batch_id IS NULL
                  THEN 1 ELSE 0
                END
              ) AS null_meta,
              COUNT(DISTINCT _ingestion_batch_id) AS batches
            FROM {table}
            """
        ).collect()[0]
        assert int(row["null_meta"]) == 0
        assert int(row["batches"]) == 1
        files = [
            record["_source_file"]
            for record in spark.sql(f"SELECT DISTINCT _source_file FROM {table}").collect()
        ]
        assert files == [join_landing_path(config.landing_path, filename)]
