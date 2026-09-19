# Task Breakdown

Dependency-driven implementation plan. Detail lives in `spec.md`, `project-context.md`, and engineering docs—use this file for **sequence and gates** only.

**Workflow per task:** implement → write tests → **execute** tests → review results.  
**Do not** mark validation complete unless tests were actually run (TS-08).  
**pytest** locally where practical; **Databricks serverless** for Spark/table integration.

**Evidence:** keep a short execution summary alongside the tests (what ran, pass/fail)—not full logs, not README, not `debugging-notes.md`.  
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
- Minimal shared config for catalog / schema / landing path (placeholders OK)
- Confirm `src/` package layout exists

**Implement**
- [ ] Lightweight config placeholders so later stages can inject paths
- [ ] Confirm package folders under `src/` match expected layout

**Validate / review**
- [ ] Write tests: N/A (or smoke import of config if present)
- [ ] Execute: N/A
- [ ] Review: enough structure to start T1 without Databricks schema setup

**Acceptance**
- [ ] Repo layout ready for generator and later layers; config is injectable (SET-04)

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
- [x] Execute: run pytest locally
- [x] Review: results match targets; schema columns/domains present; no claimed pass without run

**Acceptance**
- [ ] DG-01–DG-05 / SET-02 satisfied; **TS-01** executed green (volumes + defects + source schema)

---

## T2 — Bronze ingest

**Depends on:** T1 (CSVs available); T0 (config placeholders)

**Files**
- `database/schema.sql`
- `src/bronze/01_ingest_customers.py`, `02_ingest_orders.py`, `03_ingest_products.py`, `ingest_all.py`

**Implement**
- [ ] Create catalog/schema/table setup (`database/schema.sql`) needed for Bronze+
- [ ] Land three CSVs to bronze Delta tables with metadata; fail fast on missing files
- [ ] Stage CSVs to configured landing path on Databricks

**Validate / review**
- [ ] Write tests: serverless checks for row counts / raw preservation (**TS-02**); mark `databricks` so local pytest can skip
- [ ] Execute: run Bronze on serverless; run/skip-marked tests as designed
- [ ] Review: counts match 10k / 100k / 500; defective rows still present

**Acceptance**
- [ ] SET-01 and BR-01–BR-05 met; **TS-02** executed on serverless

---

## T3 — Silver validation

**Depends on:** T2

**Files**
- Core: `01_quality_completeness.py`, `02_quality_uniqueness.py`, `03_quality_type_validation.py`, `04_quality_referential_integrity.py`, `create_silver_tables.py`
- Stretch (optional): `05_quality_business_logic.py`
- DQ metrics output (table or export per DQ strategy)

**Implement**
- [ ] Wire core four checks; retain rows; set `quality_check_result` / `failed_checks`
- [ ] Produce quality metrics report
- [ ] Optional: business-logic check if time remains

**Validate / review**
- [ ] Write tests: serverless assertions for intentional defect detection and known-good PASS (**TS-03**, **TS-04**); optional unit tests for pure helpers via pytest
- [ ] Execute: Silver on serverless + pytest (local helpers / skip Databricks markers)
- [ ] Review: metrics and FAIL rates align with DQ strategy; log only real issues in `debugging-notes.md`

**Acceptance**
- [ ] SV-01–SV-04, SV-06–SV-08 met; **TS-03** / **TS-04** executed
- [ ] **Bronze vs Silver row-count reconciliation:** each `silver_*` row count equals matching `bronze_*` (all rows retained)
- [ ] Stretch SV-05 only if implemented and validated

---

## T4 — Gold aggregations

**Depends on:** T3

**Files**
- `01_sales_by_product.sql`, `02_revenue_by_customer.sql`, `03_daily_weekly_trends.sql`, `04_customer_segmentation.sql`, `create_gold_tables.py`

**Implement**
- [ ] Four Gold tables; PASS-only inputs (facts + dimension joins)
- [ ] Segmentation / trends per design-notes (no re-spec here)

**Validate / review**
- [ ] Write tests: serverless checks for aggregate sanity and absence of FAIL/duplicate keys in Gold (**TS-05**)
- [ ] Execute: Gold on serverless; run integration checks
- [ ] Review: spot-check sums/counts against PASS Silver

**Acceptance**
- [ ] GD-01–GD-07 met; **TS-05** executed

---

## T5 — Dashboard

**Depends on:** T4

**Files**
- `src/dashboard/dashboard_queries.sql`
- `src/dashboard/DASHBOARD_GUIDE.md`

**Implement**
- [ ] Gold-only SQL for required visualizations
- [ ] Create **Databricks SQL Dashboard** with 3+ tiles (bar / histogram / pie)
- [ ] Document recreate steps and filters in the guide

**Validate / review**
- [ ] Write tests: N/A beyond query smoke (manual/SQL warehouse)
- [ ] Execute: run queries against Gold; open dashboard and confirm 3+ visualizations render
- [ ] Review: tiles match DB-01–DB-06; guide is usable

**Acceptance**
- [ ] Dashboard exists with 3+ visualizations; queries + guide in repo

---

## T6 — Final validation and wrap-up

**Depends on:** T1–T5

**Files**
- README end-to-end instructions
- Short test-execution summary alongside tests for E2E / final runs
- Remaining AI workflow and submission artifacts per `spec.md` §8

**Implement**
- [ ] Complete README runbook (land → Bronze → Silver → Gold → dashboard) (SET-03)
- [ ] Complete remaining AI workflow and submission artifacts listed in `spec.md` §8
- [ ] Confirm repo structure vs PRD / SET-05

**Validate / review**
- [ ] Write tests: ensure pytest suite remains the meaningful local tier (**TS-06**)
- [ ] Execute: one full serverless Bronze → Silver → Gold path (**TS-07**); re-run local pytest
- [ ] Review: short pass/fail summary with the tests (**TS-08**); fix or note failures honestly

**Acceptance**
- [ ] E2E path works; README usable; no unexecuted “green” claims
- [ ] Artifacts in `spec.md` §8 complete enough for assessment

---

## Progress tracker

| Task | Implement | Tests written | Tests executed | Reviewed |
|---|---|---|---|---|
| T0 Setup | [ ] | [ ] | [ ] | [ ] |
| T1 Data gen | [x] | [x] | [x] | [x] |
| T2 Bronze | [ ] | [ ] | [ ] | [ ] |
| T3 Silver | [ ] | [ ] | [ ] | [ ] |
| T4 Gold | [ ] | [ ] | [ ] | [ ] |
| T5 Dashboard | [ ] | [ ] | [ ] | [ ] |
| T6 Final | [ ] | [ ] | [ ] | [ ] |
