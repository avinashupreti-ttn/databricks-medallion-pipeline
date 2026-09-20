# TS-02 execution

## Local pytest (not the serverless acceptance run)

Date: 2026-09-20

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/test_bronze_ingestion.py --html=tests/reports/ts-02-report.html --self-contained-html
```

**22 passed, 5 skipped** in 0.76s.

- **22 passed** — local checks only (config, fail-fast inputs, schema contract, explicit-databricks guard). No Spark session.
- **5 skipped** — Databricks markers; a skip is not a pass. Those contracts were later executed via the serverless notebook (below), not via `pytest -m databricks`.

## Serverless table validation (**TS-02 complete**)

Date: 2026-09-20

Vehicle: `tests/databricks/ts_02_05_serverless_validation.py` (Spark assertions on already-populated tables; pipeline not rerun).


Target: `workspace.c1_bronze` (landing compared for row counts)

| Check | Result |
|---|---|
| TS-02.1 Bronze row counts match landing CSVs and targets | PASS |
| TS-02.2 Bronze preserves intentional customer defects | PASS |
| TS-02.3 Bronze preserves intentional order defects | PASS |
| TS-02.4 Bronze products intact (500 distinct, no null PKs) | PASS |
| TS-02.5 Bronze metadata columns populated | PASS |

Overall notebook summary: **12 PASS / 0 FAIL** (TS-02 through TS-05). This is **not** a local pytest result.
