# Databricks notebook source
# MAGIC %md
# MAGIC # TS-02 / TS-03 / TS-04 / TS-05 — serverless table validation
# MAGIC
# MAGIC Validates **already-populated** Unity Catalog tables with Spark SQL assertions.
# MAGIC Contracts match `tests/test_bronze_ingestion.py`, `tests/test_silver_validation.py`,
# MAGIC `tests/test_gold_aggregations.py`, and `data-quality-strategy.md`.
# MAGIC
# MAGIC **Does not** modify data, rerun the pipeline, or invoke pytest.
# MAGIC
# MAGIC ## Repo path
# MAGIC `tests/databricks/ts_02_05_serverless_validation.py`
# MAGIC
# MAGIC ## How to run (assessor) — after `databricks bundle deploy`
# MAGIC This notebook is the **only** `tests/` file synced by the Asset Bundle
# MAGIC (`sync.include` plus `tests/**` exclude with a `!` exception in
# MAGIC `databricks.yml`). Other pytest modules, scripts, reports, and evidence
# MAGIC stay local.
# MAGIC
# MAGIC 1. Deploy the bundle (you run deploy; this notebook does not deploy itself).
# MAGIC 2. Open the synced notebook under the bundle **files** root:
# MAGIC    `/Workspace/Users/<your-user>/.bundle/databricks-medallion-pipeline/<target>/files/tests/databricks/ts_02_05_serverless_validation`
# MAGIC    For the default `free` target in development mode, `<target>` is typically
# MAGIC    `dev` or `free` — use Workspace browser → `.bundle` → this bundle → `files`.
# MAGIC 3. Attach **serverless** compute.
# MAGIC 4. Optionally set widgets (defaults: `workspace` / `c1_bronze` / `c1_silver` /
# MAGIC    `c1_gold` / `/Volumes/workspace/c1_landing/landing`).
# MAGIC 5. **Run All**. Capture the PASS/FAIL summary cell output.
# MAGIC
# MAGIC The notebook raises at the end if any check failed.

# COMMAND ----------

# Widgets — override only if your catalog / schemas / landing path differ.
dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bronze_schema", "c1_bronze")
dbutils.widgets.text("silver_schema", "c1_silver")
dbutils.widgets.text("gold_schema", "c1_gold")
dbutils.widgets.text("landing_path", "/Volumes/workspace/c1_landing/landing")

CATALOG = dbutils.widgets.get("catalog").strip()
BRONZE_SCHEMA = dbutils.widgets.get("bronze_schema").strip()
SILVER_SCHEMA = dbutils.widgets.get("silver_schema").strip()
GOLD_SCHEMA = dbutils.widgets.get("gold_schema").strip()
LANDING_PATH = dbutils.widgets.get("landing_path").strip().rstrip("/")

print(
    f"Target: {CATALOG}.{{{BRONZE_SCHEMA},{SILVER_SCHEMA},{GOLD_SCHEMA}}} "
    f"landing={LANDING_PATH}"
)

# COMMAND ----------

# Contract literals from data-model.md / data-quality-strategy.md /
# DATA_GENERATION_NOTES.md (same values as the pytest databricks markers).

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
ABSENT_CUSTOMER_IDS = (52, 54, 56, 58, 60)
DUPLICATE_ORDER_IDS = (381, 383, 385, 387, 389, 391, 393, 395, 397, 399)

GOLD_TABLES = (
    "gold_sales_by_product",
    "gold_revenue_by_customer",
    "gold_daily_weekly_trends",
    "gold_customer_segmentation",
)
SEGMENT_TYPES = ("High-Value", "Repeat", "One-Time", "Inactive")
DQ_METRICS_TABLE = "dq_metrics_report"

CONTRACT_TABLES = (
    ("customers.csv", "bronze_customers", CUSTOMER_ROWS),
    ("orders.csv", "bronze_orders", ORDER_ROWS),
    ("products.csv", "bronze_products", PRODUCT_ROWS),
)

RESULTS = []  # list of dicts: test_id, status, detail


def bronze(table: str) -> str:
    return f"`{CATALOG}`.`{BRONZE_SCHEMA}`.`{table}`"


def silver(table: str) -> str:
    return f"`{CATALOG}`.`{SILVER_SCHEMA}`.`{table}`"


def gold(table: str) -> str:
    return f"`{CATALOG}`.`{GOLD_SCHEMA}`.`{table}`"


def join_landing(filename: str) -> str:
    return f"{LANDING_PATH}/{filename}"


def count_where(table: str, predicate: str = "1 = 1") -> int:
    row = spark.sql(f"SELECT COUNT(*) AS n FROM {table} WHERE {predicate}").collect()[0]
    return int(row["n"])


def sum_decimal(table: str, column: str, predicate: str = "1 = 1"):
    from decimal import Decimal

    row = spark.sql(
        f"SELECT CAST(COALESCE(SUM({column}), 0) AS DECIMAL(18,2)) AS total "
        f"FROM {table} WHERE {predicate}"
    ).collect()[0]
    return Decimal(str(row["total"]))


def check(test_id: str, description: str, fn):
    """Run one assertion block; record PASS/FAIL without stopping early."""
    try:
        fn()
        RESULTS.append({"test_id": test_id, "status": "PASS", "detail": description})
        print(f"PASS  {test_id} — {description}")
    except Exception as exc:  # noqa: BLE001 — collect all failures for the summary
        RESULTS.append(
            {
                "test_id": test_id,
                "status": "FAIL",
                "detail": f"{description} | {type(exc).__name__}: {exc}",
            }
        )
        print(f"FAIL  {test_id} — {description}")
        print(f"      {type(exc).__name__}: {exc}")


def assert_eq(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


# COMMAND ----------

# MAGIC %md
# MAGIC ## TS-02 — Bronze ingestion

# COMMAND ----------


def ts02_row_counts():
    for filename, table_name, target in CONTRACT_TABLES:
        path = join_landing(filename)
        source_count = (
            spark.read.option("header", "true")
            .option("inferSchema", "false")
            .csv(path)
            .count()
        )
        bronze_count = count_where(bronze(table_name))
        assert_eq(source_count, target, f"{filename} landing rows")
        assert_eq(bronze_count, source_count, f"{table_name} vs landing")


def ts02_customer_defects():
    table = bronze("bronze_customers")
    assert_eq(count_where(table, "email IS NULL"), NULL_EMAILS, "null emails")
    assert_eq(count_where(table, "customer_id IS NULL"), 0, "null customer_id")
    absent = ", ".join(str(v) for v in ABSENT_CUSTOMER_IDS)
    assert_eq(
        count_where(table, f"customer_id IN ({absent})"),
        0,
        "absent customer_ids present",
    )
    rows = spark.sql(
        f"""
        SELECT customer_id, COUNT(*) AS row_count
        FROM {table}
        GROUP BY customer_id
        HAVING COUNT(*) > 1
        ORDER BY customer_id
        """
    ).collect()
    actual = [(int(r["customer_id"]), int(r["row_count"])) for r in rows]
    expected = [(v, 2) for v in DUPLICATE_CUSTOMER_IDS]
    assert_eq(actual, expected, "duplicate customer_id pairs")


def ts02_order_defects():
    table = bronze("bronze_orders")
    assert_eq(
        count_where(table, "customer_id IS NULL"),
        NULL_ORDER_CUSTOMER_IDS,
        "null order customer_id",
    )
    assert_eq(
        count_where(table, "product_id IS NULL"),
        NULL_ORDER_PRODUCT_IDS,
        "null order product_id",
    )
    assert_eq(
        count_where(table, "customer_id IS NULL AND product_id IS NULL"),
        0,
        "both FKs null",
    )
    assert_eq(
        count_where(table, "customer_id BETWEEN 2000001 AND 2000050"),
        UNKNOWN_CUSTOMER_IDS,
        "unknown customer_id band",
    )
    assert_eq(
        count_where(table, "product_id BETWEEN 3000001 AND 3000030"),
        UNKNOWN_PRODUCT_IDS,
        "unknown product_id band",
    )
    rows = spark.sql(
        f"""
        SELECT order_id, COUNT(*) AS row_count
        FROM {table}
        GROUP BY order_id
        HAVING COUNT(*) > 1
        ORDER BY order_id
        """
    ).collect()
    actual = [(int(r["order_id"]), int(r["row_count"])) for r in rows]
    expected = [(v, 2) for v in DUPLICATE_ORDER_IDS]
    assert_eq(actual, expected, "duplicate order_id pairs")


def ts02_products():
    table = bronze("bronze_products")
    row = spark.sql(
        f"""
        SELECT
          COUNT(*) AS n,
          COUNT(DISTINCT product_id) AS distinct_ids,
          SUM(CASE WHEN product_id IS NULL THEN 1 ELSE 0 END) AS null_ids
        FROM {table}
        """
    ).collect()[0]
    assert_eq(int(row["n"]), PRODUCT_ROWS, "product rows")
    assert_eq(int(row["distinct_ids"]), PRODUCT_ROWS, "distinct product_id")
    assert_eq(int(row["null_ids"]), 0, "null product_id")


def ts02_metadata():
    for filename, table_name, _target in CONTRACT_TABLES:
        table = bronze(table_name)
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
        assert_eq(int(row["null_meta"]), 0, f"{table_name} null metadata")
        assert_eq(int(row["batches"]), 1, f"{table_name} batch count")
        files = [
            r["_source_file"]
            for r in spark.sql(f"SELECT DISTINCT _source_file FROM {table}").collect()
        ]
        assert_eq(files, [join_landing(filename)], f"{table_name} _source_file")


check("TS-02.1", "Bronze row counts match landing CSVs and targets", ts02_row_counts)
check("TS-02.2", "Bronze preserves intentional customer defects", ts02_customer_defects)
check("TS-02.3", "Bronze preserves intentional order defects", ts02_order_defects)
check("TS-02.4", "Bronze products intact (500 distinct, no null PKs)", ts02_products)
check("TS-02.5", "Bronze metadata columns populated", ts02_metadata)

# COMMAND ----------

# MAGIC %md
# MAGIC ## TS-03 / TS-04 — Silver validation + known-good PASS

# COMMAND ----------


def ts03_row_counts_match_bronze():
    pairs = (
        ("bronze_customers", "silver_customers", CUSTOMER_ROWS),
        ("bronze_orders", "silver_orders", ORDER_ROWS),
        ("bronze_products", "silver_products", PRODUCT_ROWS),
    )
    for bronze_name, silver_name, target in pairs:
        b = count_where(bronze(bronze_name))
        s = count_where(silver(silver_name))
        assert_eq(b, target, f"{bronze_name} target")
        assert_eq(s, b, f"{silver_name} vs {bronze_name}")


def ts03_intentional_defects():
    customers = silver("silver_customers")
    orders = silver("silver_orders")
    products = silver("silver_products")

    assert_eq(
        count_where(customers, "array_contains(failed_checks, 'completeness')"),
        NULL_EMAILS,
        "customer completeness fails",
    )
    assert_eq(
        count_where(customers, "array_contains(failed_checks, 'uniqueness')"),
        CUSTOMER_UNIQUENESS_FAILS,
        "customer uniqueness fails",
    )
    assert_eq(
        count_where(customers, "array_contains(failed_checks, 'type_validation')"),
        0,
        "customer type_validation fails",
    )
    assert_eq(
        count_where(customers, "quality_check_result = 'FAIL'"),
        CUSTOMER_FAIL_ROWS,
        "customer FAIL rows",
    )

    assert_eq(
        count_where(orders, "array_contains(failed_checks, 'completeness')"),
        NULL_ORDER_CUSTOMER_IDS + NULL_ORDER_PRODUCT_IDS,
        "order completeness fails",
    )
    assert_eq(
        count_where(orders, "array_contains(failed_checks, 'uniqueness')"),
        ORDER_UNIQUENESS_FAILS,
        "order uniqueness fails",
    )
    assert_eq(
        count_where(orders, "array_contains(failed_checks, 'referential_integrity')"),
        UNKNOWN_CUSTOMER_IDS + UNKNOWN_PRODUCT_IDS,
        "order RI fails",
    )
    assert_eq(
        count_where(orders, "array_contains(failed_checks, 'type_validation')"),
        0,
        "order type_validation fails",
    )
    assert_eq(
        count_where(orders, "quality_check_result = 'FAIL'"),
        ORDER_FAIL_ROWS,
        "order FAIL rows",
    )

    assert_eq(
        count_where(products, "quality_check_result = 'FAIL'"),
        0,
        "product FAIL rows",
    )
    total_fail = (
        count_where(customers, "quality_check_result = 'FAIL'")
        + count_where(orders, "quality_check_result = 'FAIL'")
        + count_where(products, "quality_check_result = 'FAIL'")
    )
    assert_eq(total_fail, DISTINCT_DEFECT_ROWS, "distinct defective rows")


def ts03_dq_metrics():
    rows = {
        (row["check_category"], row["entity"]): row
        for row in spark.table(f"{CATALOG}.{SILVER_SCHEMA}.{DQ_METRICS_TABLE}").collect()
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
    assert_eq(set(rows), set(expected), "dq_metrics keys")
    for key, (evaluated, failed) in expected.items():
        row = rows[key]
        assert_eq(int(row["rows_evaluated"]), evaluated, f"{key} evaluated")
        assert_eq(int(row["rows_failed"]), failed, f"{key} failed")
        assert_eq(int(row["rows_passed"]), evaluated - failed, f"{key} passed")
        expected_pct = round(((evaluated - failed) / evaluated) * 100, 2)
        assert_eq(float(row["pass_pct"]), expected_pct, f"{key} pass_pct")
    assert_eq(
        count_where(silver(DQ_METRICS_TABLE)),
        len(expected),
        "dq_metrics row count",
    )


def ts04_known_good_pass():
    customers = silver("silver_customers")
    orders = silver("silver_orders")
    products = silver("silver_products")
    assert_eq(
        count_where(customers, "quality_check_result = 'PASS'"),
        CUSTOMER_ROWS - CUSTOMER_FAIL_ROWS,
        "customer PASS rows",
    )
    assert_eq(
        count_where(orders, "quality_check_result = 'PASS'"),
        ORDER_ROWS - ORDER_FAIL_ROWS,
        "order PASS rows",
    )
    assert_eq(
        count_where(products, "quality_check_result = 'PASS'"),
        PRODUCT_ROWS,
        "product PASS rows",
    )
    assert_eq(
        count_where(products, "size(failed_checks) = 0"),
        PRODUCT_ROWS,
        "product empty failed_checks",
    )


check("TS-03.1", "Silver row counts match Bronze (all rows retained)", ts03_row_counts_match_bronze)
check("TS-03.2", "Silver detects intentional defect counts (DQ strategy)", ts03_intentional_defects)
check("TS-03.3", "dq_metrics_report matches strategy expectations", ts03_dq_metrics)
check("TS-04.1", "Known-good Silver rows remain PASS", ts04_known_good_pass)

# COMMAND ----------

# MAGIC %md
# MAGIC ## TS-05 — Gold aggregations

# COMMAND ----------


def ts05_tables_populated():
    for table in GOLD_TABLES:
        n = count_where(gold(table))
        if n <= 0:
            raise AssertionError(f"{table} is empty")
    segments = {
        row["segment_type"]
        for row in spark.table(
            f"{CATALOG}.{GOLD_SCHEMA}.gold_customer_segmentation"
        ).collect()
    }
    assert_eq(segments, set(SEGMENT_TYPES), "segment_type set")
    grains = {
        row["period_grain"]
        for row in spark.table(
            f"{CATALOG}.{GOLD_SCHEMA}.gold_daily_weekly_trends"
        ).collect()
    }
    assert_eq(grains, {"DAY", "WEEK"}, "period_grain set")


def ts05_excludes_fail_and_duplicates():
    customers = gold("gold_revenue_by_customer")
    products = gold("gold_sales_by_product")
    dup_customers = ", ".join(str(v) for v in DUPLICATE_CUSTOMER_IDS)
    assert_eq(
        count_where(customers, f"customer_id IN ({dup_customers})"),
        0,
        "duplicate customer_ids in Gold",
    )
    fail_customers = spark.sql(
        f"""
        SELECT COUNT(*) AS n
        FROM {customers} g
        INNER JOIN {silver('silver_customers')} s
          ON g.customer_id = s.customer_id
        WHERE s.quality_check_result = 'FAIL'
        """
    ).collect()[0]["n"]
    assert_eq(int(fail_customers), 0, "FAIL customers in Gold")
    fail_products = spark.sql(
        f"""
        SELECT COUNT(*) AS n
        FROM {products} g
        INNER JOIN {silver('silver_products')} s
          ON g.product_id = s.product_id
        WHERE s.quality_check_result = 'FAIL'
        """
    ).collect()[0]["n"]
    assert_eq(int(fail_products), 0, "FAIL products in Gold")


def ts05_revenue_reconciles():
    from decimal import Decimal

    orders = silver("silver_orders")
    products = silver("silver_products")
    customers = silver("silver_customers")
    gold_products = gold("gold_sales_by_product")
    gold_customers = gold("gold_revenue_by_customer")
    gold_trends = gold("gold_daily_weekly_trends")

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
    assert_eq(
        Decimal(str(expected_product_revenue)),
        sum_decimal(gold_products, "total_revenue"),
        "product revenue vs PASS Silver",
    )

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
    assert_eq(
        Decimal(str(expected_customer_revenue)),
        sum_decimal(gold_customers, "total_revenue"),
        "customer revenue vs PASS Silver",
    )

    pass_order_count = count_where(
        orders, "quality_check_result = 'PASS' AND order_status <> 'Cancelled'"
    )
    day_orders = count_where(gold_trends, "period_grain = 'DAY'")
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
    assert_eq(int(day_order_sum), pass_order_count, "DAY grain order sum")
    assert_eq(int(week_order_sum), pass_order_count, "WEEK grain order sum")
    if day_orders <= 0:
        raise AssertionError("DAY grain has no periods")


check("TS-05.1", "Gold tables populated with expected segments/grains", ts05_tables_populated)
check("TS-05.2", "Gold excludes FAIL rows and duplicate customer keys", ts05_excludes_fail_and_duplicates)
check("TS-05.3", "Gold revenue/orders reconcile to PASS Silver", ts05_revenue_reconciles)

# COMMAND ----------

# MAGIC %md
# MAGIC ## PASS / FAIL summary
# MAGIC
# MAGIC Copy this output as evidence. Notebook fails if any check failed.
# MAGIC This cell does **not** mark TS-02–TS-05 complete in the task tracker.

# COMMAND ----------

from pyspark.sql import Row

summary_rows = [Row(test_id=r["test_id"], status=r["status"], detail=r["detail"]) for r in RESULTS]
display(spark.createDataFrame(summary_rows))

passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
total = len(RESULTS)

print("=" * 72)
print("TS-02 / TS-03 / TS-04 / TS-05 serverless validation summary")
print(f"Catalog/schemas: {CATALOG}.{BRONZE_SCHEMA} / {SILVER_SCHEMA} / {GOLD_SCHEMA}")
print(f"Total: {total}  PASS: {passed}  FAIL: {failed}")
print("-" * 72)
for r in RESULTS:
    print(f"{r['status']:4}  {r['test_id']:8}  {r['detail']}")
print("=" * 72)

if failed:
    failed_ids = [r["test_id"] for r in RESULTS if r["status"] == "FAIL"]
    raise AssertionError(
        f"{failed} of {total} checks failed: {', '.join(failed_ids)}. "
        "See summary above. Pipeline was not modified by this notebook."
    )

print("ALL CHECKS PASSED — record this output as serverless execution evidence.")
print("Do not treat this notebook run as a local pytest result.")
