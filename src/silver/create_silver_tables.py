"""Build Silver tables from Bronze and write the DQ metrics report.

Reads every Bronze row, applies the four core checks, retains all rows,
and overwrites silver_* plus dq_metrics_report. Gold will use PASS only.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import os
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

from src.config import resolve_config, validate_identifier

SCHEMA_PATH = REPO_ROOT / "database" / "schema.sql"

completeness = importlib.import_module("src.silver.01_quality_completeness")
uniqueness = importlib.import_module("src.silver.02_quality_uniqueness")
type_validation = importlib.import_module("src.silver.03_quality_type_validation")
referential_integrity = importlib.import_module("src.silver.04_quality_referential_integrity")

CHECK_ORDER = (
    completeness.CATEGORY,
    type_validation.CATEGORY,
    uniqueness.CATEGORY,
    referential_integrity.CATEGORY,
)

BRONZE_TABLES = {
    "customers": "bronze_customers",
    "orders": "bronze_orders",
    "products": "bronze_products",
}
SILVER_TABLES = {
    "customers": "silver_customers",
    "orders": "silver_orders",
    "products": "silver_products",
}
BUSINESS_COLUMNS = {
    "customers": (
        "customer_id",
        "customer_name",
        "email",
        "country",
        "signup_date",
        "customer_segment",
        "lifetime_value",
    ),
    "orders": (
        "order_id",
        "customer_id",
        "order_date",
        "product_id",
        "quantity",
        "unit_price",
        "total_amount",
        "order_status",
        "payment_date",
    ),
    "products": (
        "product_id",
        "product_name",
        "category",
        "price",
        "cost",
        "stock_quantity",
        "reorder_level",
    ),
}
METADATA_COLUMNS = (
    "_ingested_at",
    "_source_file",
    "_ingestion_batch_id",
)
QUALITY_COLUMNS = (
    "quality_check_result",
    "failed_checks",
    "_silver_processed_at",
)
DQ_METRICS_TABLE = "dq_metrics_report"
METRICS_ENTITIES = {
    completeness.CATEGORY: completeness.ENTITIES,
    uniqueness.CATEGORY: uniqueness.ENTITIES,
    type_validation.CATEGORY: type_validation.ENTITIES,
    referential_integrity.CATEGORY: referential_integrity.ENTITIES,
}

HANDLED_ERRORS = (
    ValueError,
    FileNotFoundError,
    PermissionError,
    RuntimeError,
    OSError,
)


def annotate_entities(customers: list, orders: list, products: list) -> dict:
    """Apply the four core checks in memory. Used by local tests.

    Returns one annotated row list per entity. Every input row is retained.
    Check order matches data-quality-strategy.md.
    """
    customer_dups = uniqueness.duplicate_key_set(
        customers, uniqueness.KEYS["customers"]
    )
    order_dups = uniqueness.duplicate_key_set(orders, uniqueness.KEYS["orders"])
    customer_ids = referential_integrity.parent_keys(customers, "customer_id")
    product_ids = referential_integrity.parent_keys(products, "product_id")

    def annotate(entity: str, rows: list) -> list:
        annotated = []
        for row in rows:
            failed = []
            if entity in completeness.ENTITIES and completeness.row_failed(entity, row):
                failed.append(completeness.CATEGORY)
            if type_validation.row_failed(entity, row):
                failed.append(type_validation.CATEGORY)
            if entity == "customers" and uniqueness.row_failed(
                row.get(uniqueness.KEYS["customers"]), customer_dups
            ):
                failed.append(uniqueness.CATEGORY)
            if entity == "orders" and uniqueness.row_failed(
                row.get(uniqueness.KEYS["orders"]), order_dups
            ):
                failed.append(uniqueness.CATEGORY)
            if entity in referential_integrity.ENTITIES and referential_integrity.row_failed(
                row, customer_ids, product_ids
            ):
                failed.append(referential_integrity.CATEGORY)
            result = dict(row)
            result["failed_checks"] = failed
            result["quality_check_result"] = "FAIL" if failed else "PASS"
            annotated.append(result)
        return annotated

    return {
        "customers": annotate("customers", customers),
        "orders": annotate("orders", orders),
        "products": annotate("products", products),
    }


def category_fail_count(rows: list, category: str) -> int:
    return sum(1 for row in rows if category in row["failed_checks"])


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
    catalog: str, bronze_schema: str, silver_schema: str
) -> list[str]:
    validate_identifier(catalog, "catalog")
    validate_identifier(bronze_schema, "bronze_schema")
    validate_identifier(silver_schema, "silver_schema")
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
    rendered = (
        SCHEMA_PATH.read_text(encoding="utf-8")
        .replace("__CATALOG__", catalog)
        .replace("__BRONZE_SCHEMA__", bronze_schema)
        .replace("__SILVER_SCHEMA__", silver_schema)
    )
    if (
        "__CATALOG__" in rendered
        or "__BRONZE_SCHEMA__" in rendered
        or "__SILVER_SCHEMA__" in rendered
    ):
        raise RuntimeError("database/schema.sql has unsubstituted placeholders.")
    statements = split_sql(rendered)
    if not statements:
        raise RuntimeError(f"Schema file has no statements: {SCHEMA_PATH}")
    return statements


def apply_schema(spark, catalog: str, bronze_schema: str, silver_schema: str) -> None:
    for statement in render_schema_statements(catalog, bronze_schema, silver_schema):
        try:
            spark.sql(statement)
        except Exception as exc:
            raise RuntimeError(
                "Failed to apply database/schema.sql for "
                f"{catalog}.{bronze_schema} / {catalog}.{silver_schema}: {exc}"
            ) from exc


def _qualified(catalog: str, schema_name: str, table: str) -> str:
    return f"`{catalog}`.`{schema_name}`.`{table}`"


def _require_bronze(spark, catalog: str, bronze_schema: str) -> None:
    missing = []
    for entity, table in BRONZE_TABLES.items():
        full = _qualified(catalog, bronze_schema, table)
        if not spark.catalog.tableExists(f"{catalog}.{bronze_schema}.{table}"):
            missing.append(full)
    if missing:
        names = ", ".join(missing)
        raise FileNotFoundError(
            f"Bronze tables required for Silver are missing: {names}. "
            "Run Bronze ingestion before Silver validation."
        )


def _read_bronze(spark, catalog: str, bronze_schema: str, entity: str):
    table = _qualified(catalog, bronze_schema, BRONZE_TABLES[entity])
    try:
        return spark.table(f"{catalog}.{bronze_schema}.{BRONZE_TABLES[entity]}")
    except Exception as exc:
        raise RuntimeError(f"Failed to read {table}: {exc}") from exc


def _fail_flags(entity: str, bronze, parents: dict):
    from pyspark.sql import functions as F

    frame = bronze
    if entity in completeness.ENTITIES:
        frame = frame.withColumn(
            f"_dq_fail_{completeness.CATEGORY}",
            completeness.spark_failed_column(entity),
        )
    else:
        frame = frame.withColumn(f"_dq_fail_{completeness.CATEGORY}", F.lit(False))

    frame = frame.withColumn(
        f"_dq_fail_{type_validation.CATEGORY}",
        type_validation.spark_failed_column(entity),
    )

    if entity in uniqueness.ENTITIES:
        frame = uniqueness.spark_attach(frame, uniqueness.KEYS[entity])
    else:
        frame = frame.withColumn(f"_dq_fail_{uniqueness.CATEGORY}", F.lit(False))

    if entity in referential_integrity.ENTITIES:
        frame = referential_integrity.spark_attach(
            frame,
            parents["customers"],
            parents["products"],
        )
    else:
        frame = frame.withColumn(
            f"_dq_fail_{referential_integrity.CATEGORY}",
            F.lit(False),
        )
    return frame


def _attach_quality(frame):
    from pyspark.sql import functions as F

    parts = []
    any_failed = F.lit(False)
    for category in CHECK_ORDER:
        flag = F.col(f"_dq_fail_{category}")
        any_failed = any_failed | flag
        parts.append(
            F.when(flag, F.array(F.lit(category))).otherwise(F.array().cast("array<string>"))
        )
    failed_checks = parts[0]
    for part in parts[1:]:
        failed_checks = F.concat(failed_checks, part)
    stamped = (
        frame.withColumn(
            "quality_check_result",
            F.when(any_failed, F.lit("FAIL")).otherwise(F.lit("PASS")),
        )
        .withColumn("failed_checks", failed_checks)
        .withColumn("_silver_processed_at", F.current_timestamp())
    )
    drop_cols = [f"_dq_fail_{category}" for category in CHECK_ORDER]
    return stamped.drop(*drop_cols)


def _select_silver(entity: str, frame):
    columns = list(BUSINESS_COLUMNS[entity]) + list(METADATA_COLUMNS) + list(QUALITY_COLUMNS)
    return frame.select(*columns)


def build_silver_frames(spark, catalog: str, bronze_schema: str) -> dict:
    bronze = {
        entity: _read_bronze(spark, catalog, bronze_schema, entity)
        for entity in BRONZE_TABLES
    }
    parents = {
        "customers": bronze["customers"],
        "products": bronze["products"],
    }
    silver = {}
    for entity in BRONZE_TABLES:
        flagged = _fail_flags(entity, bronze[entity], parents)
        silver[entity] = _select_silver(entity, _attach_quality(flagged))
    return silver


def write_silver_tables(spark, catalog: str, silver_schema: str, silver: dict) -> dict:
    counts = {}
    spark.sql(f"USE CATALOG `{catalog}`")
    spark.sql(f"USE SCHEMA `{silver_schema}`")
    for entity, frame in silver.items():
        table = SILVER_TABLES[entity]
        full = _qualified(catalog, silver_schema, table)
        count = frame.count()
        try:
            (
                frame.write.format("delta")
                .mode("overwrite")
                .option("overwriteSchema", "true")
                .saveAsTable(table)
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to write {full}: {exc}") from exc
        print(f"Wrote {count} rows to {full}", flush=True)
        counts[entity] = int(count)
    return counts


def _contains_category(failed_checks_col, category: str):
    from pyspark.sql import functions as F

    return F.array_contains(failed_checks_col, F.lit(category))


def build_metrics_rows(spark, silver: dict, reported_at):
    from pyspark.sql import Row

    rows = []
    for category, entities in METRICS_ENTITIES.items():
        for entity in entities:
            frame = silver[entity]
            total = frame.count()
            failed = frame.where(
                _contains_category(frame["failed_checks"], category)
            ).count()
            passed = total - failed
            pass_pct = round((passed / total) * 100, 2) if total else 0.0
            rows.append(
                Row(
                    check_category=category,
                    entity=entity,
                    rows_evaluated=int(total),
                    rows_passed=int(passed),
                    rows_failed=int(failed),
                    pass_pct=float(pass_pct),
                    reported_at=reported_at,
                )
            )
    return spark.createDataFrame(rows)


def write_metrics_report(spark, catalog: str, silver_schema: str, silver: dict) -> int:
    reported_at = spark.sql(
        "SELECT current_timestamp() AS reported_at"
    ).collect()[0]["reported_at"]
    metrics = build_metrics_rows(spark, silver, reported_at)
    spark.sql(f"USE CATALOG `{catalog}`")
    spark.sql(f"USE SCHEMA `{silver_schema}`")
    full = _qualified(catalog, silver_schema, DQ_METRICS_TABLE)
    try:
        (
            metrics.write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(DQ_METRICS_TABLE)
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to write {full}: {exc}") from exc
    count = metrics.count()
    print(f"Wrote {count} rows to {full}", flush=True)
    return int(count)


def create_silver_tables(
    spark, catalog: str, bronze_schema: str, silver_schema: str
) -> dict:
    validate_identifier(catalog, "catalog")
    validate_identifier(bronze_schema, "bronze_schema")
    validate_identifier(silver_schema, "silver_schema")
    # Check Bronze before schema.sql. Applying schema first would CREATE empty
    # bronze_* tables and hide a missing ingestion.
    _require_bronze(spark, catalog, bronze_schema)
    apply_schema(spark, catalog, bronze_schema, silver_schema)
    silver = build_silver_frames(spark, catalog, bronze_schema)
    counts = write_silver_tables(spark, catalog, silver_schema, silver)
    write_metrics_report(spark, catalog, silver_schema, silver)
    summary = ", ".join(f"{name}={count}" for name, count in counts.items())
    print(f"Silver validation complete: {summary}", flush=True)
    return counts


def get_spark():
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError(
            "PySpark is not available. Run Silver validation on Databricks serverless."
        ) from exc
    spark = SparkSession.getActiveSession()
    if spark is not None:
        return spark
    if not os.environ.get("DATABRICKS_RUNTIME_VERSION", "").strip():
        raise RuntimeError(
            "No active Spark session. Run Silver validation on Databricks serverless."
        )
    return SparkSession.builder.getOrCreate()


def run_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Bronze tables into Silver. Retains every row, flags "
            "core DQ failures, and overwrites silver_* plus dq_metrics_report."
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
        spark = get_spark()
        create_silver_tables(
            spark,
            config.catalog,
            config.bronze_schema,
            config.silver_schema,
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
