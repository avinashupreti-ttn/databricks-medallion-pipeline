# Candidate Information

**Name:** Avinash Upreti
**Role:** [fill — SE / SSE / ATL / TL / other]
**Primary Technology Stack:** Python / PySpark, SQL, Databricks
**Primary AI Tool Used:** Cursor
**Project Option Selected:** Data Pipeline (Medallion Architecture)
**Assessment Start Date:** [fill]
**Submission Date:** [fill]

## Tools & Environment

- Databricks: Free Edition serverless (Unity Catalog)
- Languages: Python, PySpark, Spark SQL
- Libraries / platform: Delta Lake, Databricks Asset Bundles, AI/BI dashboards
- AI Tool: Cursor (Composer agent + project rules)
- Local tests: pytest + pytest-html

## Setup Summary

1. Land `data/*.csv` on the configured Volume path.
2. `databricks bundle deploy -t free --profile <profile>` then
   `databricks bundle run ecommerce_medallion_pipeline`.
3. Open the Gold AI/BI dashboard; optionally run
   `tests/databricks/ts_02_05_serverless_validation.py` for TS-02–TS-05.
4. Full runbook: `README.md`. Bundle details: `docs/bundle-deployment.md`.
