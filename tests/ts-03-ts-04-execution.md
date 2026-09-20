# TS-03 / TS-04 execution

Local checks only. The four Databricks Silver table checks were skipped. That is not a pass, and TS-03 / TS-04 serverless acceptance is not complete.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Run

```bash
.venv/bin/python -m pytest tests/test_silver_validation.py --html=tests/reports/ts-03-ts-04-report.html --self-contained-html
```

## Open the report

Open `tests/reports/ts-03-ts-04-report.html` in a browser. It is self-contained; no extra asset files are required. The report lists Passed and Skipped separately.

## Result

Date: 2026-09-20

**17 passed, 4 skipped** in 21.31s.

- **17 passed** — local checks only: value helpers, the four core DQ rules, in-memory annotation of the sample CSVs against the 460-row defect contract (TS-03), known-good PASS rows (TS-04), schema DDL for `silver_*` / `dq_metrics_report` under `__SILVER_SCHEMA__`, fail-fast multi-schema config / missing PySpark, Bronze-before-`schema.sql` ordering (`test_missing_bronze_fails_before_schema_apply`), and the guard that `pytest -m databricks` fails instead of skipping when this machine is not Databricks. No Spark session was started.
- **4 skipped** — not executed, not a pass:
  - `test_silver_row_counts_match_bronze`
  - `test_silver_detects_intentional_defects`
  - `test_silver_known_good_rows_pass`
  - `test_dq_metrics_report_matches_strategy`

## Still pending

On Databricks serverless, after Bronze tables exist for the configured catalog / bronze_schema (e.g. `workspace.c1_bronze`):

1. Run `src/silver/create_silver_tables.py` with `--catalog workspace --bronze-schema c1_bronze --silver-schema c1_silver --landing-path /Volumes/workspace/c1_landing/landing` (or matching env/widgets).
2. Run `pytest -m databricks tests/test_silver_validation.py`.

Do not record those four checks as passed until that run exists. Row-count reconciliation on serverless still catches empty or incomplete Bronze data after the tables exist.
