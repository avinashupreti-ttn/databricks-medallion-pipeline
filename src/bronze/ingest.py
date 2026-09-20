"""Land CSV extracts into Bronze Delta tables.

Preserve every source row, including intentional defects. Do not cleanse,
deduplicate, or apply data-quality checks. Reruns overwrite the Bronze table.

Explicit column types come from data-model.md. Spark inferSchema is not used:
it would widen integers and decimals away from the Bronze DDL.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.config import resolve_config, validate_batch_id, validate_identifier

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "database" / "schema.sql"

# (name, logical type, nullable). Nullable True means empty CSV fields may be null.
CUSTOMER_FIELDS = (
    ("customer_id", "int", False),
    ("customer_name", "string", False),
    ("email", "string", True),
    ("country", "string", False),
    ("signup_date", "date", False),
    ("customer_segment", "string", False),
    ("lifetime_value", "decimal", False),
)
ORDER_FIELDS = (
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
PRODUCT_FIELDS = (
    ("product_id", "int", False),
    ("product_name", "string", False),
    ("category", "string", False),
    ("price", "decimal", False),
    ("cost", "decimal", False),
    ("stock_quantity", "int", False),
    ("reorder_level", "int", False),
)
METADATA_FIELDS = (
    ("_ingested_at", "timestamp", False),
    ("_source_file", "string", False),
    ("_ingestion_batch_id", "string", False),
)

ENTITIES = {
    "customers": {
        "filename": "customers.csv",
        "table": "bronze_customers",
        "fields": CUSTOMER_FIELDS,
    },
    "orders": {
        "filename": "orders.csv",
        "table": "bronze_orders",
        "fields": ORDER_FIELDS,
    },
    "products": {
        "filename": "products.csv",
        "table": "bronze_products",
        "fields": PRODUCT_FIELDS,
    },
}

REMOTE_PREFIXES = (
    "dbfs:",
    "s3:",
    "s3a:",
    "s3n:",
    "abfss:",
    "abfs:",
    "gs:",
    "wasbs:",
    "wasb:",
    "hdfs:",
)

HANDLED_ERRORS = (
    ValueError,
    FileNotFoundError,
    PermissionError,
    RuntimeError,
    OSError,
)


def new_batch_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def is_remote_path(path: str) -> bool:
    normalized = path.strip().lower()
    if "://" in normalized:
        return True
    return normalized.startswith(REMOTE_PREFIXES)


def join_landing_path(landing_path: str, filename: str) -> str:
    if landing_path is None or not str(landing_path).strip():
        raise ValueError(
            "Missing required configuration: landing_path. "
            "Set --landing-path, PIPELINE_LANDING_PATH, or the landing_path widget."
        )
    base = str(landing_path).strip().rstrip("/")
    if not base or base.endswith(":"):
        raise ValueError(
            f"Invalid landing path: {landing_path!r}. "
            "Use a Volume directory (/Volumes/...) or a dbfs: directory "
            "containing customers.csv, orders.csv, and products.csv."
        )
    return f"{base}/{filename}"


def _expected_header(fields: tuple) -> tuple[str, ...]:
    return tuple(name for name, _kind, _nullable in fields)


def _reject_header(path: str, header: tuple[str, ...], expected: tuple[str, ...]) -> None:
    if header != expected:
        raise ValueError(
            f"Source file columns do not match the contract: {path}. "
            f"Expected {list(expected)} but found {list(header)}."
        )


def assert_local_csv_ready(path: str, fields: tuple) -> None:
    """Fail fast for a driver-visible CSV. Does not drop or rewrite rows."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    if not file_path.is_file():
        raise ValueError(f"Source path is not a readable file: {path}")
    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"Source file is not readable: {path}")
    if file_path.stat().st_size == 0:
        raise ValueError(f"Source file is empty: {path}")
    expected = _expected_header(fields)
    try:
        with file_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = tuple(next(reader))
            except StopIteration as exc:
                raise ValueError(f"Source file is empty: {path}") from exc
            _reject_header(path, header, expected)
            try:
                next(reader)
            except StopIteration as exc:
                raise ValueError(f"Source file has no data rows: {path}") from exc
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"Source file is unreadable: {path}") from exc
    except PermissionError as exc:
        raise PermissionError(f"Source file is not readable: {path}") from exc
    except OSError as exc:
        raise PermissionError(f"Source file is not readable: {path}") from exc


def _raise_remote_access_error(path: str, exc: Exception) -> None:
    message = str(exc).lower()
    missing = (
        "does not exist",
        "path_not_found",
        "filenotfound",
        "no such file",
    )
    if any(token in message for token in missing):
        raise FileNotFoundError(f"Source file not found: {path}") from exc
    raise PermissionError(f"Source file is not readable: {path}") from exc


def assert_remote_csv_ready(spark, path: str, fields: tuple) -> None:
    """Fail fast for dbfs:/ and cloud URIs using DataFrame reads only."""
    try:
        listed = (
            spark.read.format("binaryFile")
            .load(path)
            .select("length")
            .limit(2)
            .collect()
        )
    except Exception as exc:
        _raise_remote_access_error(path, exc)
    if len(listed) > 1:
        raise ValueError(f"Source path is not a readable file: {path}")
    if len(listed) == 1 and int(listed[0]["length"]) == 0:
        raise ValueError(f"Source file is empty: {path}")
    try:
        preview = spark.read.format("text").load(path).limit(2).collect()
    except Exception as exc:
        _raise_remote_access_error(path, exc)
    if not preview or preview[0][0] is None:
        raise ValueError(f"Source file is empty: {path}")
    header = tuple(next(csv.reader([str(preview[0][0]).rstrip("\r")])))
    _reject_header(path, header, _expected_header(fields))
    if len(preview) < 2:
        raise ValueError(f"Source file has no data rows: {path}")


def assert_source_ready(path: str, fields: tuple, spark=None) -> None:
    if is_remote_path(path):
        if spark is None:
            raise ValueError(f"Spark session is required to validate source file: {path}")
        assert_remote_csv_ready(spark, path, fields)
        return
    assert_local_csv_ready(path, fields)


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


def render_schema_statements(catalog: str, schema_name: str) -> list[str]:
    validate_identifier(catalog, "catalog")
    validate_identifier(schema_name, "schema")
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
    rendered = (
        SCHEMA_PATH.read_text(encoding="utf-8")
        .replace("__CATALOG__", catalog)
        .replace("__SCHEMA__", schema_name)
    )
    if "__CATALOG__" in rendered or "__SCHEMA__" in rendered:
        raise RuntimeError("database/schema.sql has unsubstituted placeholders.")
    statements = split_sql(rendered)
    if not statements:
        raise RuntimeError(f"Schema file has no statements: {SCHEMA_PATH}")
    return statements


def apply_schema(spark, catalog: str, schema_name: str) -> None:
    statements = render_schema_statements(catalog, schema_name)
    for statement in statements:
        try:
            spark.sql(statement)
        except Exception as exc:
            raise RuntimeError(
                "Failed to apply database/schema.sql for "
                f"{catalog}.{schema_name}: {exc}"
            ) from exc


def _spark_schema(fields: tuple):
    from pyspark.sql.types import (
        DateType,
        DecimalType,
        IntegerType,
        StringType,
        StructField,
        StructType,
    )

    type_map = {
        "int": IntegerType(),
        "string": StringType(),
        "date": DateType(),
        "decimal": DecimalType(18, 2),
    }
    return StructType(
        [
            StructField(name, type_map[kind], nullable)
            for name, kind, nullable in fields
        ]
    )


def read_landing_csv(spark, path: str, fields: tuple):
    """Read with the contract schema. Empty fields become null. No row drops."""
    reader = (
        spark.read.format("csv")
        .option("header", "true")
        .option("mode", "FAILFAST")
        .option("nullValue", "")
        .option("dateFormat", "yyyy-MM-dd")
        .option("encoding", "UTF-8")
        .option("enforceSchema", "true")
        .option("ignoreLeadingWhiteSpace", "false")
        .option("ignoreTrailingWhiteSpace", "false")
        .schema(_spark_schema(fields))
    )
    try:
        return reader.load(path)
    except Exception as exc:
        raise RuntimeError(f"Source file is unreadable: {path}") from exc


def _qualified_table(catalog: str, schema_name: str, table: str) -> str:
    return f"`{catalog}`.`{schema_name}`.`{table}`"


def ingest_entity(
    spark,
    entity: str,
    catalog: str,
    schema_name: str,
    landing_path: str,
    batch_id: str,
    *,
    prepare: bool = True,
) -> int:
    if entity not in ENTITIES:
        raise ValueError(f"Unknown Bronze entity: {entity}")
    validate_identifier(catalog, "catalog")
    validate_identifier(schema_name, "schema")
    batch_id = validate_batch_id(batch_id)
    spec = ENTITIES[entity]
    path = join_landing_path(landing_path, spec["filename"])
    if prepare:
        assert_source_ready(path, spec["fields"], spark)
        apply_schema(spark, catalog, schema_name)
    frame = read_landing_csv(spark, path, spec["fields"])
    row_count = frame.count()
    if row_count == 0:
        raise ValueError(f"Source file has no data rows: {path}")
    ingested_at = spark.sql(
        "SELECT current_timestamp() AS ingested_at"
    ).collect()[0]["ingested_at"]
    from pyspark.sql import functions as F

    stamped = (
        frame.withColumn("_ingested_at", F.lit(ingested_at))
        .withColumn("_source_file", F.lit(path))
        .withColumn("_ingestion_batch_id", F.lit(batch_id))
    )
    table = _qualified_table(catalog, schema_name, spec["table"])
    try:
        spark.sql(f"USE CATALOG `{catalog}`")
        spark.sql(f"USE SCHEMA `{schema_name}`")
        (
            stamped.write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(spec["table"])
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to write {table} from {path}: {exc}") from exc
    print(
        f"Ingested {row_count} rows into {table} from {path} "
        f"at {ingested_at} batch {batch_id}",
        flush=True,
    )
    return int(row_count)


def ingest_all(spark, catalog: str, schema_name: str, landing_path: str, batch_id: str) -> dict:
    """Validate every source file before writing any Bronze table."""
    validate_identifier(catalog, "catalog")
    validate_identifier(schema_name, "schema")
    batch_id = validate_batch_id(batch_id)
    for spec in ENTITIES.values():
        path = join_landing_path(landing_path, spec["filename"])
        assert_source_ready(path, spec["fields"], spark)
    apply_schema(spark, catalog, schema_name)
    counts = {}
    for entity in ENTITIES:
        counts[entity] = ingest_entity(
            spark,
            entity,
            catalog,
            schema_name,
            landing_path,
            batch_id,
            prepare=False,
        )
    summary = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(f"Bronze ingestion complete: {summary}", flush=True)
    return counts


def get_spark():
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError(
            "PySpark is not available. Run Bronze ingestion on Databricks serverless."
        ) from exc
    spark = SparkSession.getActiveSession()
    if spark is not None:
        return spark
    if not os.environ.get("DATABRICKS_RUNTIME_VERSION", "").strip():
        raise RuntimeError(
            "No active Spark session. Run Bronze ingestion on Databricks serverless."
        )
    return SparkSession.builder.getOrCreate()


def run_main(entity: str | None = None, argv: list[str] | None = None) -> int:
    """CLI entry for one entity, or all three when entity is None."""
    parser = argparse.ArgumentParser(
        description=(
            "Ingest landing CSVs into Bronze Delta tables. "
            "Overwrites tables on rerun. Does not cleanse or deduplicate."
        )
    )
    parser.add_argument("--catalog", default=None)
    parser.add_argument("--schema", default=None)
    parser.add_argument("--landing-path", default=None)
    parser.add_argument("--batch-id", default=None)
    args = parser.parse_args(argv)
    try:
        config = resolve_config(args.catalog, args.schema, args.landing_path)
        batch_id = (
            validate_batch_id(args.batch_id) if args.batch_id is not None else new_batch_id()
        )
        spark = get_spark()
        if entity is None:
            ingest_all(
                spark,
                config.catalog,
                config.schema,
                config.landing_path,
                batch_id,
            )
        else:
            ingest_entity(
                spark,
                entity,
                config.catalog,
                config.schema,
                config.landing_path,
                batch_id,
            )
    except HANDLED_ERRORS as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
