# Project Context (Cursor)

Shared context for Cursor during implementation of the Databricks medallion pipeline assessment. Prefer this file for orientation; pull detail from the reference documents below—do not invent schemas, DQ rules, or acceptance criteria.

---

## Project Goal

Build a complete **Bronze → Silver → Gold → Dashboard** pipeline for synthetic e-commerce CSVs (`customers`, `orders`, `products`) on Databricks. Demonstrate AI-assisted data engineering: sample data with intentional quality issues, raw ingest, Silver validation + quality report, four Gold aggregations, and a Gold-backed SQL dashboard—plus required lifecycle artifacts.

This is an assessment exercise, not a production platform. Prefer simple, readable, testable code over frameworks and infrastructure.

---

## Technology Stack

| Area | Choice |
|---|---|
| Platform | Databricks (serverless Spark / notebooks) |
| Languages | Python, PySpark, Spark SQL |
| Tables | Delta where supported; Unity Catalog catalog/schema |
| Sources | Synthetic CSVs in `data/`; land via configurable Volume/DBFS path |
| Tests | `pytest` (light unit tests); Spark/table checks on serverless |
| BI | Databricks SQL Dashboard |

Config (catalog, schema, landing paths) must be easy to change. No hardcoded secrets or real PII.

---

## Architecture

```text
data/*.csv → landing → Bronze (raw Delta)
                     → Silver (validate, flag, DQ report)
                     → Gold (SQL aggregations)
                     → SQL Dashboard (Gold only)
```

| Concern | Layer | Location |
|---|---|---|
| Ingestion | Bronze | `src/bronze/` |
| Validation | Silver | `src/silver/` |
| Aggregation | Gold | `src/gold/` |
| Presentation | Dashboard | `src/dashboard/` |

Stages are independently rerunnable (overwrite/replace per stage). No DQ in Bronze; no new validation logic in Gold.

---

## Key Decisions

- **snake_case** column names end-to-end (CSV → Gold).
- Exact sample volumes: **10,000 / 100,000 / 500** rows, with PRD intentional defects.
- Silver **retains** bad rows; set `quality_check_result` / `failed_checks`.
- **Core Silver checks:** completeness, uniqueness, type validation, referential integrity. Business logic (`05_…`) is **stretch**.
- **Gold:** four tables including daily/weekly trends; **PASS-only** inputs (failed and duplicate-key rows excluded).
- **Dashboard:** queries **Gold only**.
- Segmentation: behavior segments from order value; High-Value uses **90th percentile** of customer revenue on the generated dataset (details in design notes).
- Fail fast on missing config/files; keep error handling assessment-simple.

---

## Testing Approach

| Tier | Where | Focus |
|---|---|---|
| Unit | Local `pytest` | Generator defect counts; small DQ helpers (no local Spark required) |
| Integration | Databricks serverless | Bronze → Silver → Gold counts, DQ detection, Gold excludes FAIL/duplicates |
| E2E | One serverless run | Documented in README / debugging notes |

Only claim tests that have actually been executed (TS-08). Map TS-01–TS-07 in `requirements-analysis.md` / `design-notes.md`.

---

## Scope Boundaries

**In scope:** Sample generator, Bronze/Silver/Gold, DQ report, ≥3 dashboard tiles, schema/setup, README, lifecycle + prompt artifacts, lightweight tests.

**Out of scope / deferred:** Streaming, SCD/MERGE, production orchestration/CI, heavy frameworks, local Spark cluster, real customer data, over-engineered error/rollback design.

Do not expand pipeline complexity at the expense of artifacts and documentation.

---

## Reference Documents

Consult the right doc; do not duplicate large sections into prompts or new files.

| Document | When to consult |
|---|---|
| `requirement-analysis.md` | Requirement IDs (DG/BR/SV/GD/DB/TS/ART), acceptance criteria, resolved clarifications (CL-*) |
| `data-model.md` | Column types, PK/FK, Bronze/Silver/Gold table shapes, quality-status fields |
| `data-quality-strategy.md` | Check definitions, fail handling, metrics report shape, intentional defect expectations |
| `design-notes.md` | How to implement layers, PASS-only Gold, segmentation approach, rerun/testing/debug trade-offs |
| `ai-prompts/requirements-and-design.md` | Prior Cursor decisions on planning artifacts (avoid re-litigating closed CLs) |

**Default workflow for Cursor:** read this context → open the relevant reference doc for detail → implement against PRD repo structure → keep changes minimal and consistent with existing decisions.
