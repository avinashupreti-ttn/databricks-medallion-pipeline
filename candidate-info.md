# Candidate Information

**Name:** Avinash Upreti
**Role:** ATL
**Primary Technology Stack:** Python / PySpark, SQL, Databricks
**Primary AI Tool Used:** Cursor
**Project Option Selected:** Data Pipeline (Medallion Architecture)
**Assessment Start Date:** 12th September 2026
**Submission Date:** 21st September 2026

## Tools & Environment

- Databricks: Free Edition serverless (Unity Catalog)
- Languages: Python, PySpark, Spark SQL
- Libraries / platform: Delta Lake, Databricks Asset Bundles, AI/BI dashboards
- AI Tool: Cursor (Composer agent + project rules)
- Local tests: pytest + pytest-html

## Setup Summary

1. Land `data/*.csv` on the configured Volume path (regenerate with
   `python -m src.data_generation.generate_sample_data` if missing).
2. `databricks bundle deploy -t free --profile <profile>` then
   `databricks bundle run ecommerce_medallion_pipeline`.
3. Open the Gold AI/BI dashboard; optionally run
   `tests/databricks/ts_02_05_serverless_validation.py` for TS-02–TS-05.
4. Full runbook: `README.md`. Bundle details: `docs/bundle-deployment.md`.

### Key markdown references

| File | What it covers |
|---|---|
| `README.md` | End-to-end clone → deploy → run → validate runbook |
| `docs/bundle-deployment.md` | CLI profile, `bundle validate` / `deploy` / `run`, variables |
| `src/dashboard/DASHBOARD_GUIDE.md` | Dashboard tiles, scoped filters, deploy/open steps |
| `src/data_generation/DATA_GENERATION_NOTES.md` | How sample CSVs and intentional defects are produced |
| `requirement-analysis.md` | Agreed requirements contract and CL-* decisions |
| `data-model.md` | Source, Bronze, Silver, and Gold schemas |
| `data-quality-strategy.md` | DQ check rules, fail handling, expected defect counts |
| `design-notes.md` | Layer design, PASS-only Gold, segmentation, trade-offs |
| `tool-workflow.md` | Part A — AI workflow foundation |
| `debugging-notes.md` | Meaningful issues and fixes during implementation |
| `reflection.md` | What was built, AI use, refinements, next steps |
| `final-ai-usage-summary.md` | Compact AI usage summary for submission |
| `ai-prompts/` | Prompt history by activity (accept / modify / reject) |
| `tool-specific/cursor-workflow/` | Cursor context, `spec.md`, `task-breakdown.md` |
| `tests/summary/` | Executed test evidence (TS-01…TS-07 + final) |
