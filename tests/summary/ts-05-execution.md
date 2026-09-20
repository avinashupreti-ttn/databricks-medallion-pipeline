# TS-05 / T4 execution

## Local pytest (not the serverless acceptance run)

Date: 2026-09-20

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/test_gold_aggregations.py --html=tests/reports/ts-05-report.html --self-contained-html
```

**13 passed, 3 skipped** in 21.70s.

- **13 passed** — local checks only (PASS-only SQL, segment rules, in-memory Gold mirrors, DDL, fail-fast, explicit-databricks guard). No Spark session.
- **3 skipped** — Databricks markers; a skip is not a pass. Those contracts were later executed via the serverless notebook (below), not via `pytest -m databricks`.

## Serverless table validation (**TS-05 complete**)

Date: 2026-09-20

Vehicle: `tests/databricks/ts_02_05_serverless_validation.py` (Spark assertions on already-populated tables; pipeline not rerun).


Target: `workspace.c1_silver` / `workspace.c1_gold`

| Check | Result |
|---|---|
| TS-05.1 Gold tables populated with expected segments/grains | PASS |
| TS-05.2 Gold excludes FAIL rows and duplicate customer keys | PASS |
| TS-05.3 Gold revenue/orders reconcile to PASS Silver | PASS |

Overall notebook summary: **12 PASS / 0 FAIL** (TS-02 through TS-05). This is **not** a local pytest result.
