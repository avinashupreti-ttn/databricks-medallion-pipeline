# Reflection

## What I Built

A complete synthetic e-commerce Medallion pipeline on Databricks serverless:
seeded sample data, Bronze ingest, Silver with four core DQ checks and metrics,
four PASS-only Gold aggregations, a Gold-only AI/BI dashboard, Asset Bundle
job + dashboard resources, local pytest, and a serverless validation notebook.

## How I Used AI (Across the Lifecycle)

Cursor for requirement gap analysis, design notes, layer implementation,
tests, bundle wiring, dashboard definition, and tracker/evidence closure.
Each stage used the engineering contracts as the prompt boundary.

## What AI Helped With Most

- Turning resolved CL-* decisions into concrete schemas, SQL, and assertions.
- Scaffolding fail-fast config and overwrite-oriented stage scripts quickly.
- Keeping docs, tests, and task checkboxes aligned during iteration.

## What AI Got Wrong

Refinements from `ai-prompts/` where Cursor drafts needed correction:

- **Workflow docs and rules** — over-scoped context (load every engineering doc), mixed sequencing into the spec, put schema/setup too early in T0, and conflated test evidence with `debugging-notes.md`. Refined to task-scoped docs, a lightweight tracker, and short execution summaries beside the tests.
- **Sample data and local tests** — invented a random ~15% null `payment_date` on Completed orders; planned TS-01 instead of implementing; briefly had a self-tautological `verify_output()` check. Corrected to status-tied payment dates, hardcoded contract pytest expectations, and stop-planning / implement-now discipline.
- **Bronze / serverless safety** — first ingest used `cache`/`persist` and JVM/`SparkContext` file checks; local helpers hit a Python 3.9 `newline=` issue; explicit `pytest -m databricks` could still skip cleanly. Refined to DataFrame-only checks, fixed helpers, and fail-loud Databricks markers.
- **Silver and job entry points** — applied `schema.sql` before Bronze existence (empty `bronze_*` could mask missing ingest); serverless tasks broke on missing `__file__` and on `SystemExit(0)` under IPython after a successful run. Fixed ordering, frame-based path resolution, and nonzero-only exits.
- **Gold and dashboard presentation** — segmentation omitted zero-count segment rows; dashboard needed horizontal top-10 bars, human-readable buckets, compact chart-scoped filters (category before `LIMIT 10`, date on daily trend only), and a missing parameter `displayName` after deploy validation failed. Design notes were also trimmed after the first draft duplicated schema/DQ detail.

## How I Validated AI Output

- Local pytest with self-contained HTML reports.
- Databricks job run evidence for E2E (TS-07).
- Spark notebook assertions for TS-02–TS-05 on populated UC tables.
- Manual review of dashboard tiles/filters against DB-01–DB-06.

## What I Would Improve Next

## What I Would Improve Next

- Deeper commit narrative for each accept/reject cycle.
- Create reusable scripts

## Reusable Workflow

Contract docs → Cursor rules → scoped task → implement → execute tests →
short evidence file → only then mark the tracker. Keep secrets out of the repo
and treat skips as non-passes.
