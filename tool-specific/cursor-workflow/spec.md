# Implementation Spec

Implementation specification for Cursor on **Databricks serverless**. Read `project-context.md` first. Sequencing lives in `task-breakdown.md`.

**Conventions:** snake_case columns; configurable catalog/schema/landing path; Delta overwrite per stage; no real PII.

### Reference documents

| Document | Use for |
|---|---|
| `requirement-analysis.md` | Requirements, acceptance criteria, resolved clarifications (CL-*), requirement IDs |
| `data-model.md` | Schemas, table shapes, quality-status fields |
| `data-quality-strategy.md` | DQ check rules, fail handling, metrics, defect expectations |
| `design-notes.md` | Layer approach, PASS-only Gold, segmentation, rerun/testing trade-offs |
| `project-context.md` | Stack, architecture summary, scope boundaries |

---

## 1. Sample Data Generation

| | |
|---|---|
| **Files** | `src/data_generation/generate_sample_data.py`, `DATA_GENERATION_NOTES.md` |
| **Inputs** | Fixed seed (or equivalent); volumes and domains from `data-model.md` |
| **Outputs** | `data/customers.csv`, `data/orders.csv`, `data/products.csv` |

**Behavior**
- Synthetic only; exact **10,000 / 100,000 / 500** rows (DG-01, DG-02, DG-03).
- Inject intentional defects at counts in `requirement-analysis.md` / `data-quality-strategy.md` (DG-04). Prefer isolated defect groups where practical.
- Document generation method and defect injection (DG-05).

**Acceptance**
- [ ] CSVs committed under `data/` (SET-02).
- [ ] Row counts and defect counts match targets (supports **TS-01**).
- [ ] Notes explain how defects were created.

---

## 2. Bronze Layer

| | |
|---|---|
| **Files** | `src/bronze/01_ingest_customers.py`, `02_ingest_orders.py`, `03_ingest_products.py`, `ingest_all.py` |
| **Inputs** | Landing CSVs (Volume/DBFS path from config) |
| **Outputs** | `bronze_customers`, `bronze_orders`, `bronze_products` (+ ingest metadata per `data-model.md`) |

**Behavior**
- Raw land only: no cleanse, dedupe, or business transforms (BR-01, BR-02).
- Apply types/schema per contract (BR-03); log row counts and `_ingested_at` (BR-04).
- Fail fast if file missing/empty/unreadable (BR-05, SET-04).
- Rerun: overwrite/replace bronze tables for the same files (`design-notes.md`).

**Acceptance**
- [ ] All three tables load successfully.
- [ ] Row counts match source targets (**TS-02**).
- [ ] Invalid rows from the generator are still present (unchanged).

---

## 3. Silver Layer

| | |
|---|---|
| **Files (core)** | `01_quality_completeness.py`, `02_quality_uniqueness.py`, `03_quality_type_validation.py`, `04_quality_referential_integrity.py`, `create_silver_tables.py` |
| **Files (stretch)** | `05_quality_business_logic.py` (optional; SV-05) |
| **Inputs** | Bronze tables |
| **Outputs** | `silver_customers`, `silver_orders`, `silver_products`; DQ metrics report |

**Behavior**
- Run core checks SV-01–SV-04 per `data-quality-strategy.md`; orchestrate in `create_silver_tables.py`.
- Retain all rows; set `quality_check_result` and `failed_checks` (SV-06). Accumulate multiple failures on one row.
- NULL FKs → completeness; non-NULL orphans → referential integrity.
- Produce pass/fail or % by category (SV-07); must catch intentional defects (SV-08).
- Do not restate check logic here—follow `data-quality-strategy.md`.

**Acceptance**
- [ ] Core four checks implemented and wired.
- [ ] Failed rows retained with correct flags.
- [ ] Metrics report exists and reflects intentional issues (**TS-03**, **TS-04**).
- [ ] Stretch business-logic script only if time permits.

---

## 4. Gold Layer

| | |
|---|---|
| **Files** | `01_sales_by_product.sql`, `02_revenue_by_customer.sql`, `03_daily_weekly_trends.sql`, `04_customer_segmentation.sql`, `create_gold_tables.py` |
| **Inputs** | Silver tables with `quality_check_result = 'PASS'` only |
| **Outputs** | Four Gold tables per `data-model.md` (GD-01–GD-04) |

**Behavior**
- **PASS-only** for facts and dimension joins (GD-05 / CL-04, CL-05). No FAIL or duplicate-key rows in metrics.
- Aggregations: count/sum/avg over qualifying `total_amount`; `lifetime_value_actual` from orders (GD-02, GD-07).
- Segmentation from order value; High-Value ≈ 90th percentile of customer revenue on this dataset (GD-06 / `design-notes.md`).
- Trends: day and week grains (`03_daily_weekly_trends.sql`).
- Rerun: overwrite Gold from current Silver.

**Acceptance**
- [ ] Four Gold tables populated with expected columns.
- [ ] Spot-checks of sums/counts pass (**TS-05**).
- [ ] Known FAIL/duplicate Silver keys absent from Gold.

---

## 5. Dashboard

| | |
|---|---|
| **Files** | `src/dashboard/dashboard_queries.sql`, `DASHBOARD_GUIDE.md` |
| **Inputs** | Gold tables only (DB-06) |
| **Outputs** | Databricks SQL Dashboard with ≥3 visualizations |

**Behavior**
- Required visualizations: top 10 products by revenue (bar), customer revenue distribution (histogram), segmentation (pie) (DB-01–DB-04).
- Queries and recreate steps in repo (DB-05). Optional fourth tile from daily/weekly trends.

**Acceptance**
- [ ] A Databricks SQL Dashboard exists with **3+ visualizations** configured (not queries alone).
- [ ] Queries powering the tiles read Gold only (no Bronze/Silver).
- [ ] `DASHBOARD_GUIDE.md` is sufficient to recreate tiles/filters.

---

## 6. Testing

| | |
|---|---|
| **Files** | `tests/` (pytest); optional serverless notebook or script for integration |
| **Inputs** | Generated CSVs; Bronze/Silver/Gold after a pipeline run |

**Behavior**

| ID | What to verify | Where |
|---|---|---|
| TS-01 | Generator defect counts | Local pytest |
| TS-02 | Bronze row counts / raw content | Serverless |
| TS-03 | Silver catches intentional defects | Serverless |
| TS-04 | Known-good rows stay PASS | Serverless / unit |
| TS-05 | Gold math; no FAIL/dupes in Gold | Serverless |
| TS-06 | At least one meaningful test tier | pytest satisfies |
| TS-07 | One Bronze→Silver→Gold run | Serverless |
| TS-08 | Only document executed passes | Process |

No local Spark cluster required. Mark Databricks tests so they can be skipped locally.

**Acceptance**
- [ ] pytest covers generator (and small helpers if any).
- [ ] One documented serverless E2E run.
- [ ] No claimed green tests without evidence.

---

## 7. Supporting setup (minimal)

| Item | Expectation | IDs |
|---|---|---|
| `database/schema.sql` | Catalog/schema/table stubs or create statements | SET-01 |
| README | End-to-end: land CSVs → Bronze → Silver → Gold → dashboard | SET-03 |
| Repo layout | Match PRD structure as closely as practical | SET-05 |

---

## 8. AI workflow and submission artifacts

Pipeline code alone is not complete. Maintain AI and submission evidence alongside implementation (ART-*, AI-*):

- `tool-workflow.md`, `candidate-info.md`
- Lifecycle docs already in repo (requirements, design, data model, DQ strategy)
- `debugging-notes.md`, `reflection.md`, `final-ai-usage-summary.md`
- Full prompt history organized by activity under ai-prompts/
- Cursor workflow under `tool-specific/cursor-workflow/` (`project-context.md`, this `spec.md`, rules/instructions, `task-breakdown.md`)

Validate AI-generated code before accepting it. Do not expand scope into streaming, MERGE/SCD, or production job frameworks.
