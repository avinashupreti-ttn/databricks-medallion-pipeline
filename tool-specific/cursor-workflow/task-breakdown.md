# Task Breakdown

Dependency-driven implementation plan. Detail lives in `spec.md`, `project-context.md`, and engineering docs—use this file for **sequence and gates** only.

**Workflow per task:** implement → write tests → **execute** tests → review results.  
**Do not** mark validation complete unless tests were actually run (TS-08).  
**pytest** locally where practical; **Databricks serverless** for Spark/table integration.

**Evidence:** short execution summaries under `tests/summary/` (what ran, pass/fail)—not full logs, not README, not `debugging-notes.md`.  
**debugging-notes.md:** meaningful issues and fixes only.

Commits and AI prompt history are managed separately (outside this tracker).

```text
T0 Setup ──► T1 Data gen ──► T2 Bronze ──► T3 Silver ──► T4 Gold ──► T5 Dashboard
                                                                      │
                                                                      ▼
                                                              T6 Final validation
```

---

## T0 — Project setup

**Depends on:** none  

**Files**
- `src/config.py` — injectable catalog / bronze_schema / silver_schema / gold_schema / landing_path
- `src/` package layout: `data_generation/`, `bronze/`, `silver/`, `gold/`, `dashboard/`

**Implement**
- [x] Lightweight config so later stages inject paths (CLI → env → widgets; fail-fast on missing required settings) — SET-04
- [x] Confirm package folders under `src/` match expected Medallion layout

**Validate / review**
- [x] Write tests: N/A
- [x] Execute: N/A
- [x] Review: structure and injectable config sufficient for T1+ without separate Databricks schema bootstrap beyond `database/schema.sql`

**Acceptance**
- [x] Repo layout ready for generator and later layers; config is injectable (SET-04)

---

## T1 — Sample data generation

**Depends on:** T0 (optional; can start in parallel)

**Files**
- `src/data_generation/generate_sample_data.py`
- `src/data_generation/DATA_GENERATION_NOTES.md`
- `data/customers.csv`, `data/orders.csv`, `data/products.csv`
- `tests/` for generator assertions

**Implement**
- [x] Generator with seed, exact volumes, intentional defects (see DQ strategy / requirements)
- [x] Write CSVs under `data/`
- [x] Document generation and defects in notes

**Validate / review**
- [x] Write tests: pytest for row counts, intentional defect counts, and **source schema/columns vs `data-model.md`** (**TS-01**)
- [x] Execute: run pytest locally — **8 passed** (`tests/summary/ts-01-execution.md`)
- [x] Review: results match targets; schema columns/domains present; no claimed pass without run

**Acceptance**
- [x] DG-01–DG-05 / SET-02 satisfied; **TS-01** executed green (volumes + defects + source schema)

---

## T2 — Bronze ingest

**Depends on:** T1 (CSVs available); T0 (config placeholders)

**Files**
- `database/schema.sql`
- `src/bronze/01_ingest_customers.py`, `02_ingest_orders.py`, `03_ingest_products.py`, `ingest_all.py`

**Implement**
- [x] Create catalog/schema/table setup (`database/schema.sql`) needed for Bronze+
- [x] Land three CSVs to bronze Delta tables with metadata; fail fast on missing files
- [x] Stage CSVs to configured landing path on Databricks (evidenced by TS-02.1 landing vs Bronze)

**Validate / review**
- [x] Write tests: serverless checks for row counts / raw preservation (**TS-02**); mark `databricks` so local pytest can skip
- [x] Execute: Bronze tables validated on serverless via `tests/databricks/ts_02_05_serverless_validation.py` (**TS-02.1–02.5 PASS**) — see `tests/summary/ts-02-execution.md`
- [x] Review: counts match 10k / 100k / 500; defective rows still present

**Acceptance**
- [x] SET-01 and BR-01–BR-05 met; **TS-02** executed on serverless

---

## T3 — Silver validation

**Depends on:** T2

**Files**
- Core: `01_quality_completeness.py`, `02_quality_uniqueness.py`, `03_quality_type_validation.py`, `04_quality_referential_integrity.py`, `create_silver_tables.py`
- DQ metrics output (table or export per DQ strategy)

**Implement**
- [x] Wire core four checks; retain rows; set `quality_check_result` / `failed_checks`
- [x] Produce quality metrics report

**Validate / review**
- [x] Write tests: serverless assertions for intentional defect detection and known-good PASS (**TS-03**, **TS-04**); optional unit tests for pure helpers via pytest
- [x] Execute: Silver tables + `dq_metrics_report` validated on serverless via `tests/databricks/ts_02_05_serverless_validation.py` (**TS-03.1–03.3**, **TS-04.1 PASS**) — see `tests/summary/ts-03-ts-04-execution.md`
- [x] Review: metrics and FAIL rates align with DQ strategy; log only real issues in `debugging-notes.md`

**Acceptance**
- [x] SV-01–SV-04, SV-06–SV-08 met; **TS-03** / **TS-04** executed
- [x] **Bronze vs Silver row-count reconciliation:** each `silver_*` row count equals matching `bronze_*` (all rows retained) — **TS-03.1 PASS**

---

## T4 — Gold aggregations

**Depends on:** T3

**Files**
- `01_sales_by_product.sql`, `02_revenue_by_customer.sql`, `03_daily_weekly_trends.sql`, `04_customer_segmentation.sql`, `create_gold_tables.py`

**Implement**
- [x] Four Gold tables; PASS-only inputs (facts + dimension joins)
- [x] Segmentation / trends per design-notes (no re-spec here)

**Validate / review**
- [x] Write tests: serverless checks for aggregate sanity and absence of FAIL/duplicate keys in Gold (**TS-05**)
- [x] Execute: Gold tables validated on serverless via `tests/databricks/ts_02_05_serverless_validation.py` (**TS-05.1–05.3 PASS**) — see `tests/summary/ts-05-execution.md`
- [x] Review: spot-check sums/counts against PASS Silver

**Acceptance**
- [x] GD-01–GD-07 met; **TS-05** executed

---

## T5 — Dashboard

**Depends on:** T4

**Files**
- `src/dashboard/dashboard_queries.sql`
- `src/dashboard/DASHBOARD_GUIDE.md`
- `src/dashboard/ecommerce_gold_dashboard.lvdash.json`
- `resources/ecommerce_gold_dashboard.yml`

**Implement**
- [x] Gold-only SQL for required visualizations
- [x] Bundle-deployable AI/BI dashboard definition (`.lvdash.json` + resource YAML)
- [x] Deploy / open dashboard in workspace with 4 tiles (screenshot evidence, 2026-09-21)
- [x] Document recreate and bundle deploy steps in the guide

**Validate / review**
- [x] Write tests: N/A beyond query smoke / `bundle validate` — checklist in `DASHBOARD_GUIDE.md`
- [x] Execute: dashboard deployed; four Gold visualizations render with scoped **Top products: category** and **Daily trend: date range** filters
- [x] Review: tiles match DB-01–DB-06; guide usable; stale PENDING text removed from guide status/checklist

**Acceptance**
- [x] Dashboard exists with 3+ visualizations (four Gold tiles evidenced); queries + guide + bundle definition in repo

---

## T6 — Final validation and wrap-up

**Depends on:** T1–T5

**Files**
- `README.md` end-to-end runbook
- `tests/summary/` (per-TS summaries + `final-execution.md`)
- Submission / AI artifacts per `spec.md` §8

**Implement**
- [x] Complete README runbook (land → Bronze → Silver → Gold → dashboard) (SET-03)
- [x] Complete remaining AI workflow and submission artifacts listed in `spec.md` §8 (`tool-workflow.md`, `candidate-info.md`, `debugging-notes.md`, `reflection.md`, `final-ai-usage-summary.md`, `ai-prompts/`, `tool-specific/cursor-workflow/`)
- [x] Confirm repo structure vs PRD / SET-05 (practical match; stretch `05_quality_business_logic.py` intentionally omitted)

**Validate / review**
- [x] Write tests: pytest suite remains the meaningful local tier (**TS-06**)
- [x] Execute: one full serverless Bronze → Silver → Gold path (**TS-07**) — run ID `820602453234839`, Sep 20, 2026; see `tests/summary/ts-07-execution.md`
- [x] Re-run local pytest (T6 / TS-06) — **72 passed, 12 skipped** (`tests/summary/final-execution.md`)
- [x] Review: short pass/fail summary with the tests (**TS-08**); skips documented as non-passes; serverless contracts evidenced separately

**Acceptance**
- [x] E2E path works; README usable; no unexecuted “green” claims
- [x] Artifacts in `spec.md` §8 present for assessment — **blocker:** fill remaining personal fields in `candidate-info.md` (Role, Assessment Start Date, Submission Date)

---

## Progress tracker

| Task | Implement | Tests written | Tests executed | Reviewed |
|---|---|---|---|---|
| T0 Setup | [x] | N/A | N/A | [x] |
| T1 Data gen | [x] | [x] | [x] | [x] |
| T2 Bronze | [x] | [x] | [x] | [x] |
| T3 Silver | [x] | [x] | [x] | [x] |
| T4 Gold | [x] | [x] | [x] | [x] |
| T5 Dashboard | [x] | [x] | [x] | [x] |
| T6 Final | [x] | [x] | [x] | [x] |
