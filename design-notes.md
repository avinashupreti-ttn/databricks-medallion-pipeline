# Design Notes

Pipeline implementation on **Databricks serverless** compute.  
**Schemas:** `data-model.md` · **DQ rules & metrics:** `data-quality-strategy.md` · **Requirements:** `requirement-analysis.md`

---

## Architecture Overview

```text
data/*.csv  →  landing (Volume/DBFS)  →  Bronze (Delta)
                                        →  Silver (Delta + DQ flags + report)
                                        →  Gold (Delta, SQL)
                                        →  SQL Dashboard (Gold queries only)
```

| Layer | Role | Code |
|---|---|---|
| Landing | CSV extracts | `data/`, configurable path |
| Bronze | Raw ingest | `src/bronze/`, `ingest_all.py` |
| Silver | Validate & flag | `src/silver/`, `create_silver_tables.py` |
| Gold | Aggregations | `src/gold/*.sql`, `create_gold_tables.py` |
| Dashboard | BI tiles | `src/dashboard/` |

**Compute:** Python/notebooks on **serverless** Spark; Unity Catalog names from `database/schema.sql`.

**Separation:** ingestion (Bronze) → validation (Silver) → aggregation (Gold). No DQ in Bronze; no new validation in Gold.

**Orchestration:** Bronze → Silver → Gold, documented in README. Stages can be rerun independently during development.

---

## Bronze Layer Design

Land all three CSVs to Delta `bronze_*` tables with ingest metadata (`data-model.md`). Preserve every row; no cleansing (BR-02). Validate inputs exist before read; clear error if a file is missing (SET-04). Log row counts for **TS-02**.

One script per entity plus `ingest_all.py`.

---

## Silver Layer Design

Apply PRD/core checks via `01`–`04` (`data-quality-strategy.md`). `create_silver_tables.py` reads Bronze, runs checks, writes `silver_*` and the DQ metrics report (SV-07).

**Required:** completeness, uniqueness, type validation, referential integrity.  
**Stretch:** `05_quality_business_logic.py` — implement if time permits; not required for core acceptance.

Retain all rows; set `quality_check_result` / `failed_checks` per `data-model.md`. Do not re-document check rules or intentional defect counts here.

---

## Gold Layer Design

**Four** Gold tables (stricter PRD / CL-01): sales by product, revenue by customer, **daily/weekly trends**, customer segmentation. Shapes and columns: `data-model.md`.

**Design decision — PASS-only Gold (CL-04, CL-05):** Every Gold query uses only Silver rows with `quality_check_result` = `PASS`, including dimension joins. Failed and duplicate-key rows stay in Silver for audit but never feed metrics.

**Segmentation (CL-03):** Behavior `segment_type` is assigned from PASS Silver customers and their PASS order facts (order count and sum of `total_amount`). Rules in `04_customer_segmentation.sql`:

1. Per PASS customer: `order_count` and `total_revenue` from PASS orders only (no orders → both 0).
2. **High-Value threshold:** 90th percentile of `total_revenue` among PASS customers with `order_count` > 0 (recomputed each run).
3. Mutually exclusive assignment (first match wins):
   - **Inactive** — `order_count` = 0
   - **High-Value** — `total_revenue` ≥ P90 threshold
   - **Repeat** — `order_count` ≥ 2
   - **One-Time** — `order_count` = 1
4. Gold table is one row per `segment_type` with `customer_count`, `avg_revenue`, `total_revenue`.

**Trends (CL-01 / GD-03):** `period_grain` is `DAY` (`order_date`) or `WEEK`. Week start is **ISO Monday** via Spark `date_trunc('WEEK', order_date)`.

Revenue fields use qualifying order `total_amount`; `lifetime_value_actual` is the sum of those amounts for the customer (`data-model.md`).

`create_gold_tables.py` runs Gold SQL in repo order and overwrites Gold tables (see rerun).

---

## Dashboard Design

**Gold only** (CL-06): top products (bar), customer revenue distribution (histogram), segmentation (pie). Queries in `dashboard_queries.sql`; setup in `DASHBOARD_GUIDE.md`. Trends tile may use `gold_daily_weekly_trends` as a fourth visualization when built.

---

## Error Handling

Keep errors obvious and local to the exercise:

- **Config / paths:** Fail early with a short message if catalog, schema, or landing path is missing.
- **Bronze:** Raise if a source CSV is missing or empty; include file name in the message.
- **Silver / Gold:** Let Spark/SQL surface failures; fix and rerun the stage.

No partial-state orchestration, rollback design, or dashboard runtime error handling beyond SQL editor debugging.

---

## Rerun Approach

Overwrite/replace Delta tables per stage (`overwrite` or `CREATE OR REPLACE`) when re-running the same sample files. Full Silver refresh from Bronze; full Gold refresh from current Silver. No incremental merges for this assessment.

---

## Testing & Validation Approach

Architecture unchanged: **pytest** for light unit tests; **Databricks serverless** for table-level integration.

| ID | Approach |
|---|---|
| **TS-01** | `pytest` on `generate_sample_data.py` — intended defect counts per `data-quality-strategy.md`. |
| **TS-02** | Serverless: Bronze row counts vs 10,000 / 100,000 / 500. |
| **TS-03** | Serverless: Silver detects the explicit defect counts and 460 distinct intentionally defective rows defined in the DQ strategy. |
| **TS-04** | Serverless or unit tests: sample known-good rows remain `PASS` on core checks. |
| **TS-05** | Serverless: Gold aggregates sane; no `FAIL` / duplicate-key rows in Gold outputs. |
| **TS-06** | Meaningful test tier provided through pytest-based data quality/unit tests, with Databricks integration validation for the pipeline. |
| **TS-07** | One serverless run Bronze → Silver → Gold (notebook or sequential scripts). |
| **TS-08** | Record only executed tests in repo notes; no claimed passes without a run. |

Use `pytest -m "not databricks"` (or similar) to skip integration markers locally. Keep concise test execution summaries alongside the tests.
Use `debugging-notes.md` for meaningful failures and fixes.

---

## Debugging Approach

- **Bronze:** `count(*)`, sample rows, compare to CSV.
- **Silver:** Filter `FAIL` by `failed_checks`; compare to `data-quality-strategy.md` expectations.
- **Gold:** Run one SQL file; reconcile to PASS-only Silver.
- **Dashboard:** Execute `dashboard_queries.sql` in SQL warehouse.

Track fixes in `debugging-notes.md`.

---

## Key Decisions / Trade-offs

| Decision | Notes |
|---|---|
| **Serverless compute** | Target platform; integration tests run in Databricks. |
| **PASS-only Gold** | Explicit design choice (CL-04): analytics trust boundary at Silver `PASS`. |
| **Flag in Silver, filter in Gold** | PRD requires keeping bad rows; Gold stays clean. |
| **Four Gold tables incl. trends** | Implemented to satisfy the stricter PRD/repository interpretation (CL-01). |
| **Core Silver = four checks** | Business logic (`05_…`) optional stretch. |
| **Duplicate PK rows all fail** | CL-05; simpler tests than dedupe-to-survivor. |
| **90th percentile High-Value** | Tied to generated sample revenue (CL-03), recomputed when data changes. |
| **Delta overwrite per run** | Simple reruns vs production incremental patterns. |
| **pytest + serverless** | TS-06/TS-07 without a local Spark cluster. |
| **Volume vs DBFS landing** | Environment-driven; paths in README. |

**Deferred:** streaming, SCD/MERGE, automated job orchestration, production monitoring.
