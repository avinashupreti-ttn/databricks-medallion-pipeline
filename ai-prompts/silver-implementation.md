# AI Prompts — T3 Silver Implementation and Testing

Factual log of Cursor interactions in this conversation for Silver validation and TS-03 / TS-04.

**Scope:** `src/silver/` (`01_quality_completeness.py`, `02_quality_uniqueness.py`, `03_quality_type_validation.py`, `04_quality_referential_integrity.py`, `create_silver_tables.py`, `values.py`), `database/schema.sql` (Silver DDL), `tests/test_silver_validation.py`, `tests/ts-03-ts-04-execution.md`, `tests/reports/ts-03-ts-04-report.html`. Related: Bronze schema-count assertion in `tests/test_bronze_ingestion.py`, T3 checkboxes in `tool-specific/cursor-workflow/task-breakdown.md`.  
**Not covered:** Bronze ingest work, Gold or later layers, optional `05_quality_business_logic.py`. The request to write this file is not an entry below.

**Format:** initial creation uses Prompt / Request → Cursor Output → Review / Decision.  
Refinements use Reason → Changes Requested → Cursor Implementation → Review / Decision.  
**Attribution:** constraints you specified are under Request / Changes Requested. Cursor’s file split, helper modules, and test mechanics are under Output / Implementation.

---

## 1. Implement Silver validation and TS-03 / TS-04

**Prompt / Request**  
Start T3 — Silver Validation. Implement the four core DQ checks under `src/silver/`: `01_quality_completeness.py`, `02_quality_uniqueness.py`, `03_quality_type_validation.py`, `04_quality_referential_integrity.py`, and `create_silver_tables.py`. Read all Bronze records into Silver, preserve row counts, flag failures, and produce the agreed DQ metrics report. Follow the documented 460-defective-row contract; Gold will consume PASS-only records later. Add TS-03 / TS-04 tests, a self-contained HTML pytest report, and a brief execution summary. Run feasible local tests; leave Databricks-dependent validation pending until actually executed. Reuse existing configuration, directory structure, and conventions. No optional business-logic check or unrelated changes. Proceed directly—no extended planning or revisiting settled decisions. Report files changed, actual test results, and remaining serverless validation. Context: `task-breakdown.md`, `data-quality-strategy.md`, `data-model.md`, and Bronze `ingest.py` patterns.

**Cursor Output**  
Added the four numbered check modules plus `src/silver/values.py` and `src/silver/create_silver_tables.py`. You named the four checks and the orchestrator; `values.py` was Cursor’s addition for shared blank/int/date/decimal helpers used by local tests and check logic.

Checks follow `data-quality-strategy.md`: completeness (customer `email`; order `customer_id` / `product_id`); uniqueness (every row in a duplicate `customer_id` / `order_id` group fails); type validation against `data-model.md` domains (no intentional type defects in the sample set); referential integrity for non-NULL order FKs against distinct parent key sets. NULL FKs are completeness-only. Check order in the orchestrator: completeness → type_validation → uniqueness → referential_integrity. Numbered modules are loaded with `importlib` because digit-prefixed names are not normal Python imports.

`create_silver_tables.py` resolves catalog/schema via existing `src.config`, requires Bronze tables, applies `database/schema.sql`, builds Silver frames with `quality_check_result` / `failed_checks` (ARRAY&lt;STRING&gt;) / `_silver_processed_at`, overwrites `silver_*` with `overwriteSchema`, and writes `dq_metrics_report` (category, entity, evaluated/passed/failed, `pass_pct`, `reported_at`). A pure-Python `annotate_entities` path supports local CSV annotation without Spark. Rerun behavior matches Bronze: overwrite Delta tables; no business-logic (`05_…`) script.

`database/schema.sql` was extended with `silver_customers`, `silver_orders`, `silver_products`, and `dq_metrics_report` (Bronze DDL kept). Header comments now mention Silver. Bronze’s schema test statement counts were updated (8 statements, 7 `USING DELTA`) so the shared DDL file still passes TS-02 local schema checks.

`tests/test_silver_validation.py` hardcodes the 460-row contract literals (60 customer / 400 order / 0 product FAILs). Local tests cover helpers, each DQ rule, in-memory sample CSV annotation (TS-03 defect counts + TS-04 known-good PASS), Silver DDL shape, fail-fast config / missing PySpark, and the guard that explicit `pytest -m databricks` fails instead of skipping off-cluster. Four tests are marked `databricks` (Bronze↔Silver row counts, defect detection, PASS rows, metrics report) and skip when `DATABRICKS_RUNTIME_VERSION` is unset. Cursor also wrote `tests/ts-03-ts-04-execution.md` and generated `tests/reports/ts-03-ts-04-report.html`. T3 implement and “tests written” were checked in `task-breakdown.md`; execute / review / acceptance stayed open. No business-logic stretch work.

Executed:

`.venv/bin/python -m pytest tests/test_silver_validation.py -q --html=tests/reports/ts-03-ts-04-report.html --self-contained-html` → **16 passed, 4 skipped** in **21.28s**.

The four `databricks` checks were not run. Serverless Silver acceptance was not marked complete.

**Review / Decision**  
No separate review of this drop. The next message kept Silver behavior and schemas and corrected Bronze prerequisite ordering (§2).

---

## 2. Check Bronze exists before applying schema.sql

**Reason for Refinement**  
`create_silver_tables()` applied `schema.sql` before verifying Bronze prerequisites. Because `schema.sql` also creates empty `bronze_*` tables, that order can mask a missing Bronze ingestion.

**Changes Requested**  
Check that all three Bronze tables exist before applying `schema.sql`. Keep the existing TS-03 row-count checks to catch empty or incomplete Bronze data during serverless validation. Make only this ordering fix and add a focused test if needed. Preserve existing Silver behavior and schemas. Run local pytest, regenerate the HTML report, and update the execution summary with actual results. No broader refactoring or planning.

**Cursor Implementation**  
In `create_silver_tables()`, `_require_bronze()` now runs before `apply_schema()`, with a short comment that applying schema first would CREATE empty bronze tables and hide missing ingest.

Added `test_missing_bronze_fails_before_schema_apply`: when `tableExists` is false for Bronze, `FileNotFoundError` is raised and `apply_schema` is never called; when `_require_bronze` is stubbed to succeed, call order is `require_bronze` then `apply_schema`. No Silver check logic, DDL shapes, or metrics semantics were changed.

Executed:

`.venv/bin/python -m pytest tests/test_silver_validation.py -q --html=tests/reports/ts-03-ts-04-report.html --self-contained-html` → **17 passed, 4 skipped** in **22.11s**.

`tests/ts-03-ts-04-execution.md` was updated to that 17/4 split and still lists the four skipped Databricks tests as not executed. First full-suite run in that turn had a transient failure on the new test (`NameError` on `create_silver_tables`); isolated re-run and the subsequent full suite both passed with the counts above. No serverless Silver run was performed.

**Review / Decision**  
No review of this correction is recorded after the run.

---

## Summary

| Item | Outcome in this conversation |
|---|---|
| Core Silver checks + orchestrator | Written. Rows retained; FAIL flags + `dq_metrics_report`; no SV-05 business-logic script |
| Extra file Cursor added | `src/silver/values.py` |
| Schema | Silver entity tables + `dq_metrics_report` added to shared `database/schema.sql` |
| Ordering correction | Bronze `tableExists` check before `apply_schema` so empty Bronze DDL cannot mask missing ingest |
| Local pytest | Initial drop: 16 passed, 4 skipped (21.28s). After ordering fix: 17 passed, 4 skipped (22.11s) |
| Report | `tests/reports/ts-03-ts-04-report.html`; summary is `tests/ts-03-ts-04-execution.md` |
| Left open | Four `databricks` tests not executed. T3 serverless execute / review / acceptance not checked |
