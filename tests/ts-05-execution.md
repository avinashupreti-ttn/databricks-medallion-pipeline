# TS-05 / T4 execution

Local checks only. The three Databricks Gold table checks were skipped. That is not a pass, and TS-05 serverless acceptance is not complete.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Run

```bash
.venv/bin/python -m pytest tests/test_gold_aggregations.py --html=tests/reports/ts-05-report.html --self-contained-html
```

## Open the report

Open `tests/reports/ts-05-report.html` in a browser. It is self-contained; no extra asset files are required. The report lists Passed and Skipped separately.

## Result

Date: 2026-09-20

**13 passed, 3 skipped** in 21.70s.

- **13 passed** — local checks only: PASS-only SQL filters, segment assignment rules, in-memory GD-01–GD-04 mirrors on annotated sample CSVs (FAIL/duplicate exclusion, revenue reconciliation, DAY/WEEK grains, all four segment rows), Gold DDL under `__GOLD_SCHEMA__`, fail-fast missing config / missing `gold_schema` / missing PySpark (when applicable), and the guard that `pytest -m databricks` fails instead of skipping when this machine is not Databricks. No Spark session was started.
- **3 skipped** — not executed, not a pass:
  - `test_gold_tables_populated`
  - `test_gold_excludes_fail_and_duplicate_keys`
  - `test_gold_revenue_reconciles_to_pass_silver`

## Still pending

On Databricks serverless, after Silver tables exist for the configured catalog / silver_schema (e.g. `workspace.c1_silver`) and Gold has been built into `c1_gold`:

1. Deploy/run the renamed job `ecommerce_medallion_pipeline` (Bronze → Silver → Gold), or run `src/gold/create_gold_tables.py` with `--catalog workspace --bronze-schema c1_bronze --silver-schema c1_silver --gold-schema c1_gold --landing-path /Volumes/workspace/c1_landing/landing`.
2. Run `pytest -m databricks tests/test_gold_aggregations.py`.

Do not record those three checks as passed until that run exists.
