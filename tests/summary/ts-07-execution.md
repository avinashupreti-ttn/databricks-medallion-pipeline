# TS-07 / T6 execution — serverless Bronze → Silver → Gold

End-to-end job run only. This does **not** claim TS-02–TS-05 Databricks pytest markers passed, and does not re-run local pytest (TS-06).

## Evidence reviewed

1. Databricks job-run UI screenshot (`[dev avinash_upreti] ecommerce-medallion-pipeline run`)
2. Run URL (below)
3. Supporting: E-commerce Gold dashboard screenshot (four Gold visualizations populated)

## Job run

| Field | Value |
|---|---|
| Job name | `[dev avinash_upreti] ecommerce-medallion-pipeline` |
| Job ID | `89776921226898` |
| **Job run ID** | **`820602453234839`** |
| **Started** | **Sep 20, 2026, 05:49 PM** |
| Ended | Sep 20, 2026, 05:52 PM |
| Duration | 3m 19s |
| Overall status | Succeeded |
| Compute | Serverless (cluster terminated) |
| Launched | Manually |

## Task graph (all succeeded)

| Task | Script | Duration | Status |
|---|---|---|---|
| `bronze_ingest` | `bronze_ingest_all.py` | 1m 42s | Succeeded |
| `silver_validate` | `create_silver_tables.py` | 58s | Succeeded |
| `gold_aggregate` | `create_gold_tables.py` | 37s | Succeeded |

## Result

**TS-07: PASS** — one full serverless Bronze → Silver → Gold path completed successfully (run ID `820602453234839`, Sep 20, 2026).

## Explicitly not claimed

- TS-02 / TS-03 / TS-04 / TS-05 Databricks `pytest -m databricks` checks — Done Using Notebook Validation (see `ts-02-execution.md`, `ts-03-ts-04-execution.md`, `ts-05-execution.md`)
- Local pytest re-run for T6 / TS-06 — not part of this evidence
