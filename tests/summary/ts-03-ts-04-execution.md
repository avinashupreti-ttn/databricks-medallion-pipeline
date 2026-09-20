# TS-03 / TS-04 execution

## Local pytest (not the serverless acceptance run)

Date: 2026-09-20

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/test_silver_validation.py --html=tests/reports/ts-03-ts-04-report.html --self-contained-html
```

**17 passed, 4 skipped** in 21.31s.

- **17 passed** — local checks only (DQ helpers, in-memory 460-row contract, DDL, fail-fast, explicit-databricks guard). No Spark session.
- **4 skipped** — Databricks markers; a skip is not a pass. Those contracts were later executed via the serverless notebook (below), not via `pytest -m databricks`.

## Serverless table validation (**TS-03 / TS-04 complete**)

Date: 2026-09-20

Vehicle: `tests/databricks/ts_02_05_serverless_validation.py` (Spark assertions on already-populated tables; pipeline not rerun).


Target: `workspace.c1_bronze` / `workspace.c1_silver`

| Check | Result |
|---|---|
| TS-03.1 Silver row counts match Bronze (all rows retained) | PASS |
| TS-03.2 Silver detects intentional defect counts (DQ strategy) | PASS |
| TS-03.3 dq_metrics_report matches strategy expectations | PASS |
| TS-04.1 Known-good Silver rows remain PASS | PASS |

Overall notebook summary: **12 PASS / 0 FAIL** (TS-02 through TS-05). This is **not** a local pytest result.
