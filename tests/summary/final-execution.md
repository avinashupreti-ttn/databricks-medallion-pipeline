# Final local pytest execution (T6 / TS-06 / TS-08)

Date: 2026-09-21

Vehicle: full local suite only. Does **not** rerun the Databricks job or the
serverless validation notebook. Serverless evidence remains in
`tests/summary/ts-02-execution.md`, `tests/summary/ts-03-ts-04-execution.md`,
`tests/summary/ts-05-execution.md`, and `tests/summary/ts-07-execution.md`.

## Command

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ --ignore=tests/databricks \
  --html=tests/reports/full-local-suite.html --self-contained-html -q
```

`--ignore=tests/databricks` keeps the Databricks notebook source out of the
local collection (it is not a pytest module).

## Result

**72 passed, 12 skipped** in 51.28s. Exit code 0.

| Status | Count | Meaning |
|---|---|---|
| passed | 72 | Local generator, config, Bronze/Silver/Gold unit & contract checks |
| skipped | 12 | `@pytest.mark.databricks` Spark/table checks (5 TS-02 + 4 TS-03/04 + 3 TS-05) |
| failed | 0 | — |

A skip is **not** a pass. Those 12 contracts were validated on serverless via
`tests/databricks/ts_02_05_serverless_validation.py` (see per-TS summaries).

## HTML report

`tests/reports/full-local-suite.html` (self-contained).

## Related evidence

| File | Coverage |
|---|---|
| `tests/summary/ts-01-execution.md` | Local TS-01 |
| `tests/summary/ts-02-execution.md` | Local + serverless TS-02 |
| `tests/summary/ts-03-ts-04-execution.md` | Local + serverless TS-03 / TS-04 |
| `tests/summary/ts-05-execution.md` | Local + serverless TS-05 |
| `tests/summary/ts-07-execution.md` | Serverless Bronze → Silver → Gold job run |
