# AI Prompts — T4 Gold Aggregates and Test Implementation

Factual log of Cursor interactions in this conversation for Gold aggregations and TS-05.

**Scope:** `src/gold/` (`01_sales_by_product.sql`, `02_revenue_by_customer.sql`, `03_daily_weekly_trends.sql`, `04_customer_segmentation.sql`, `create_gold_tables.py`), `database/schema.sql` (Gold DDL), `src/config.py` / Bronze–Silver schema apply for optional `__GOLD_SCHEMA__`, job rename and Bronze → Silver → Gold wiring (`resources/ecommerce_medallion_pipeline_job.yml`, `databricks.yml`, `docs/bundle-deployment.md`), CL-03 / week rules in `design-notes.md`, `tests/test_gold_aggregations.py`, `tests/ts-05-execution.md`, `tests/reports/ts-05-report.html`, entry-point coverage for Gold in `tests/test_entry_path_resolution.py`, T4 checkboxes in `tool-specific/cursor-workflow/task-breakdown.md`.  
**Not covered:** Dashboard (T5), notebook conversion, `bundle deploy` / `bundle run`, or the request to write this file.  
**Format:** initial creation uses Prompt / Request → Cursor Output → Review / Decision.  
**Attribution:** constraints you specified are under Request. Cursor’s file mechanics, mid-run test fixes, and helpers are under Output.

---

## 1. Implement Gold aggregations, job rename, and TS-05

**Prompt / Request**  
Start T4 — Gold aggregations. Environment: Databricks Free Edition serverless; catalog `workspace`; Silver `c1_silver`; Gold `c1_gold`; Bronze and Silver already successful in Databricks. Implement the four Gold aggregations exactly as in the attached task and design docs; Silver PASS rows only; do not invent new business rules or redefine revenue, segmentation, or grain. Extend existing config and `schema.sql` only as needed; reuse the Python-script approach and serverless bundle job. Rename `resources/bronze_silver_job.yml` → `resources/ecommerce_medallion_pipeline_job.yml`; Databricks job name `ecommerce-medallion-pipeline`; update resource key and deployment-guide commands consistently; job flow Bronze → Silver → Gold with Gold only after Silver succeeds. Add focused Gold tests, a self-contained pytest HTML report, and a short T4 execution summary; record actual local results; Databricks Gold execution remains pending. Keep Bronze/Silver behavior unchanged. No notebook conversion, dashboard, architecture redesign, or unrelated edits. Implement directly; report changed files, tests, and remaining Databricks validation; do not deploy or run the job. Context: `task-breakdown.md`, `data-quality-strategy.md`, `data-model.md`, `database/schema.sql`, `spec.md`.

**Cursor Output**  
Added four Gold SQL scripts and `src/gold/create_gold_tables.py` (PASS-only filters; overwrite Gold; require `gold_schema` and existing `silver_*`; apply shared `schema.sql`; run SQL in repo order). Local pure-Python mirrors of GD-01–GD-04 support pytest without Spark.

`database/schema.sql` gained `__GOLD_SCHEMA__` schema plus empty DDL for the four `gold_*` tables. Bronze/Silver/Gold `render_schema_statements` replace `__GOLD_SCHEMA__` when configured and drop Gold statements when `gold_schema` is absent so Bronze/Silver statement counts stay unchanged. Config docstring updated; job and `databricks.yml` gained `gold_schema` (default `c1_gold`).

Job file renamed; resource key `ecommerce_medallion_pipeline`; display name `ecommerce-medallion-pipeline`; third task `gold_aggregate` depends on `silver_validate`. `docs/bundle-deployment.md` updated for the new key/commands and Gold variable. `design-notes.md` documented concrete CL-03 rules (Inactive → High-Value at P90 → Repeat ≥2 → One-Time) and ISO Monday weeks via `date_trunc('WEEK', …)`.

`tests/test_gold_aggregations.py`: local PASS-filter / math / FAIL-exclusion / segment / DDL / fail-fast checks; three `@pytest.mark.databricks` checks (populated tables, no FAIL/duplicate keys in Gold, revenue reconcile to PASS Silver) skip off-cluster with an explicit-request fail guard. Entry-point tests include `create_gold_tables.py`. Wrote `tests/ts-05-execution.md` and generated `tests/reports/ts-05-report.html`. T4 implement and “tests written” checked in `task-breakdown.md`; serverless execute / review / acceptance left open.

Mid-implementation fixes after local pytest failures (same turn, not a separate user request):

- Sample data has no Inactive PASS customers; SQL updated to always emit all four `segment_type` rows (including zero counts); assertion relaxed accordingly.
- Gold `render_schema_statements` made `gold_schema` optional like Bronze/Silver so “without gold” DDL tests work.

Executed:

- `.venv/bin/python -m pytest tests/test_gold_aggregations.py --html=tests/reports/ts-05-report.html --self-contained-html` → **13 passed, 3 skipped** in **21.70s**
- Broader local suite (Bronze / Silver / Gold / entry-path): **64 passed, 12 skipped** in **42.48s**

The three `databricks` Gold checks were not run. No deploy or job run. Serverless TS-05 acceptance was not marked complete.

**Review / Decision**  
No separate review of this drop is recorded in the conversation after the implementation report.

---

## Summary

| Item | Outcome in this conversation |
|---|---|
| Four Gold SQL + orchestrator | Written; PASS-only; overwrite; `gold_schema` required for Gold |
| Schema / config | Gold DDL + optional `__GOLD_SCHEMA__` apply; `c1_gold` in bundle vars |
| Job | Renamed to `ecommerce-medallion-pipeline`; Bronze → Silver → Gold |
| Segmentation / trends | P90 High-Value + order-count rules; ISO Monday weeks (documented in `design-notes.md`) |
| Local pytest | Gold file: 13 passed, 3 skipped (21.70s). Combined local suite: 64 passed, 12 skipped |
| Report | `tests/reports/ts-05-report.html`; summary `tests/ts-05-execution.md` |
| Left open | Three `databricks` TS-05 tests; deploy/run of `ecommerce_medallion_pipeline`; T4 serverless execute / review / acceptance |
