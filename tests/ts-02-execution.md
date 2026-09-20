# TS-02 execution

Local checks only. The five Databricks table checks were skipped. That is not a pass, and TS-02 serverless acceptance is not complete.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Run

```bash
.venv/bin/python -m pytest tests/test_bronze_ingestion.py --html=tests/reports/ts-02-report.html --self-contained-html
```

## Open the report

Open `tests/reports/ts-02-report.html` in a browser. It is self-contained; no extra asset files are required. The report lists Passed and Skipped separately.

## Result

Date: 2026-09-20

**22 passed, 5 skipped** in 0.73s.

- **22 passed** — local checks only: configuration, missing / empty / unreadable inputs, schema contract, and the guard that `pytest -m databricks` fails instead of skipping when this machine is not Databricks. No Spark session was started.
- **5 skipped** — not executed, not a pass:
  - `test_bronze_row_counts_match_source_and_targets`
  - `test_bronze_preserves_customer_defects`
  - `test_bronze_preserves_order_defects`
  - `test_bronze_preserves_products`
  - `test_bronze_metadata_columns_are_populated`

## Still pending

On Databricks serverless, after the three CSVs are on the configured landing path:

1. Run `src/bronze/ingest_all.py`.
2. Run `pytest -m databricks tests/test_bronze_ingestion.py`.

Do not record those five checks as passed until that run exists.
