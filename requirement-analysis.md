# Requirement Analysis

## Problem Statement

An e-commerce company receives daily sales data from three separate source systems — a
customer database, an order system, and a product catalog — delivered as CSV files. The
data arrives unvalidated: it contains missing values, duplicate primary keys, and orders
referencing customers or products that do not exist.

The business needs the data landed, validated, and aggregated into analytics-ready tables
that answer questions about product performance, customer revenue, and customer
segmentation (behavior-based segments, distinct from source `customer_segment` values).

The objective is to build an AI-assisted pipeline on Databricks using Medallion Architecture:

**CSV sources → Bronze → Silver → Gold → Dashboard**

The implementation should be simple, readable, testable, and complete enough to demonstrate
sound engineering decisions and the required lifecycle artifacts — not a production platform.

**Conventions:** Column and field names use **snake_case** everywhere (CSV headers through Gold), as defined in `data-model.md`. Silver requirements (SV-*) refer to those same names (e.g. `customer_id`, not alternate spellings).

---

## Functional Requirements

*PRD-mandated items are listed by ID. Column definitions and Gold table shapes are in
`data-model.md`. Check rules and business-logic detail are in `data-quality-strategy.md`.
Segmentation thresholds derived from sample data are documented in `design-notes.md`.*

### 1. Sample Data Generation

| ID | Requirement |
|---|---|
| DG-01 | Generate `customers.csv`, `orders.csv`, and `products.csv` using synthetic data only. |
| DG-02 | Generate exactly **10,000** customer rows, **100,000** order rows, and **500** product rows (see `data-model.md`). |
| DG-03 | Include all PRD source columns and value domains (see `data-model.md`). |
| DG-04 | Introduce the intentional data quality issues specified in the PRD so Silver validations can be demonstrated. |
| DG-05 | Document how sample data and intentional defects are generated (`DATA_GENERATION_NOTES.md` or equivalent). |

#### Required Intentional Defects (drives testing)

**Customers**

| Defect | Expected Count | Validation Type |
|---|---:|---|
| NULL `email` | 50 | Completeness |
| Duplicate `customer_id` | 10 affected rows (5 pairs) | Uniqueness |

**Orders**

| Defect | Expected Count | Validation Type |
|---|---:|---|
| NULL `customer_id` | 100 | Completeness |
| NULL `product_id` | 200 | Completeness |
| Unknown `customer_id` | 50 | Referential integrity |
| Unknown `product_id` | 30 | Referential integrity |
| Duplicate `order_id` | 20 affected rows (10 pairs) | Uniqueness |

Uniqueness applies per entity: duplicate `customer_id` in customers; duplicate `order_id` in orders. Duplicate rows must be flagged in Silver and excluded from Gold (see **CL-05**).

---

### 2. Bronze Layer

| ID | Requirement |
|---|---|
| BR-01 | Read all three source CSVs from the configured landing location (S3/DBFS or agreed equivalent) into Databricks Bronze tables. |
| BR-02 | Preserve source records without cleansing, deduplication, or business transformations. |
| BR-03 | Apply schema inference and appropriate data types on ingest per the source contract (`data-model.md`). |
| BR-04 | Log ingestion metadata (e.g. row counts, ingestion timestamp). |
| BR-05 | Validate required inputs and fail with useful errors when source files are missing or unreadable. |

---

### 3. Silver Layer

| ID | Requirement |
|---|---|
| SV-01 | **Completeness** (`01_quality_completeness.py`): No NULLs in `email` (`customers`), `customer_id` and `product_id` (`orders`). |
| SV-02 | **Uniqueness** (`02_quality_uniqueness.py`): No duplicate `customer_id` (`customers`) or `order_id` (`orders`). Duplicates are recorded in validation output and fail the row. |
| SV-03 | **Referential integrity** (`04_quality_referential_integrity.py`): `orders.customer_id` and `orders.product_id` must exist in parent customer/product data when non-NULL. |
| SV-04 | **Type validation** (`03_quality_type_validation.py`): Values conform to expected types and source contract (`data-model.md`). |
| SV-05 | **Supplementary business logic** (`05_quality_business_logic.py`): Optional defensible rules on order facts; specifics in `data-quality-strategy.md`. |
| SV-06 | Flag bad rows; do not delete them. Set `quality_check_result` and `failed_checks` per `data-model.md`. |
| SV-07 | Produce a **data quality report** with pass/fail or % passed for each validation category. |
| SV-08 | Quality checks must detect the intentional defects in the sample data. |

NULL foreign keys (completeness) and unknown non-NULL foreign keys (referential integrity) must remain distinguishable.

---

### 4. Gold Layer

| ID | Requirement |
|---|---|
| GD-01 | **Sales by Product** (`01_sales_by_product.sql`). |
| GD-02 | **Revenue by Customer** (`02_revenue_by_customer.sql`), including `lifetime_value_actual` per `data-model.md`. |
| GD-03 | **Daily/Weekly Trends** (`03_daily_weekly_trends.sql`). |
| GD-04 | **Customer Segmentation** (`04_customer_segmentation.sql`): segment types High-Value, Repeat, One-Time, Inactive. |
| GD-05 | Use **only** Silver rows with `quality_check_result` = `PASS`. Any row that fails Silver validation must not contribute to Gold (**CL-04**). Duplicate-key rows must not appear in Gold (**CL-05**). |
| GD-06 | Assign behavior segments from **order value** (and related order facts) on the sample dataset; document cutoffs/rules in `design-notes.md` (**CL-03**). |
| GD-07 | Aggregation calculations (count, sum, average) must be verifiable via tests or documented checks. |

---

### 5. Dashboard

| ID | Requirement |
|---|---|
| DB-01 | Create a **Databricks SQL Dashboard** with at least three tiles. |
| DB-02 | **Top 10 products by revenue** (bar chart). |
| DB-03 | **Customer revenue distribution** (histogram). |
| DB-04 | **Customer segmentation** (pie chart). |
| DB-05 | Provide SQL queries (`dashboard_queries.sql` or equivalent) and setup guidance (`DASHBOARD_GUIDE.md`). |
| DB-06 | Dashboard queries read **Gold tables only** (**CL-06**). |

---

### 6. Database and Project Setup

| ID | Requirement |
|---|---|
| SET-01 | Provide database/schema setup SQL or equivalent (`database/schema.sql`). |
| SET-02 | Commit generated sample CSVs under `data/`. |
| SET-03 | Provide README with working end-to-end setup and run instructions. |
| SET-04 | Include input validation and error handling in pipeline code. |
| SET-05 | Follow the PRD repository structure as closely as practical. |

---

### 7. Testing and Validation

| ID | Requirement |
|---|---|
| TS-01 | Verify the data generator produces the intended quality defects. |
| TS-02 | Verify Bronze ingestion preserves expected source content and row counts (10,000 / 100,000 / 500). |
| TS-03 | Verify Silver detects the explicit intentional defect counts defined in `data-quality-strategy.md`, including 460 distinct defective rows in the standard non-overlapping dataset. |
| TS-04 | Verify clearly valid records are not incorrectly failed by main checks. |
| TS-05 | Validate important Gold aggregation results; confirm failed/duplicate Silver rows are absent from Gold. |
| TS-06 | Provide at least one meaningful test tier (data quality tests, pipeline tests, or equivalent). |
| TS-07 | Perform at least one basic end-to-end pipeline validation. |
| TS-08 | Do not document a test as passing unless it has been executed. |

Testing stays lightweight; a large framework or local Spark cluster is not required for this exercise.

---

### 8. Submission Artifacts and AI Workflow

| ID | Requirement |
|---|---|
| ART-01 | `requirement-analysis.md`, `design-notes.md`, `data-model.md`, `data-quality-strategy.md`. |
| ART-02 | `candidate-info.md` per PRD template. |
| ART-03 | `tool-workflow.md` (Part A: AI workflow foundation). |
| ART-04 | `debugging-notes.md`, `reflection.md`, `final-ai-usage-summary.md`. |
| ART-05 | **Full prompt history (CRITICAL):** `ai-prompts/` grouped by major activity, with prompts, evaluation, and accept/modify/reject rationale. |
| ART-06 | Cursor users: `tool-specific/cursor-workflow/` (`project-context.md`, `spec.md`, rules/instructions, `task-breakdown.md`). |
| AI-01 | Use AI for implementation support; validate generated code and logic before accepting it. |
| AI-02 | Demonstrate iteration — not unchecked copy/paste of generated code. |

---

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | **Readability:** Code and SQL are easy to review; PRD expects readable, **commented**, documented code. |
| NFR-02 | **Maintainability:** Separate Bronze, Silver, Gold, and dashboard concerns. |
| NFR-03 | **Testability:** Core validation and aggregation logic can be checked independently where practical. |
| NFR-04 | **Traceability:** Invalid records and quality failures remain explainable. |
| NFR-05 | **Observability:** Ingestion and quality metrics support debugging and validation. |
| NFR-06 | **Error handling:** Missing inputs and bad configuration produce useful errors. |
| NFR-07 | **Scope discipline:** No heavy frameworks or production infrastructure beyond the assessment. |
| NFR-08 | **Responsible AI:** Synthetic data only; no real PII or credentials in prompts or repo. |

---

## Assumptions

**Environment and sources**

- Databricks Community Edition (or equivalent), Python/PySpark, Spark SQL; Delta tables where the environment supports them.
- PRD cites S3/DBFS; if DBFS is restricted, land CSVs via a configurable path (e.g. Unity Catalog Volume) documented in README/setup notes.
- Repo `data/` CSVs are the source extracts; ingestion reads from the configured landing path.

**Design choices (documented in companion artifacts)**

- Fixed random seed (or equivalent) so intentional defect counts remain reproducible alongside DG-02 row counts.
- `quality_check_result` = `PASS` / `FAIL`; `failed_checks` lists categories such as `completeness`, `uniqueness`, `referential_integrity`, `type_validation`, `business_logic`.
- Gold eligibility: Silver `PASS` only; no failed or duplicate-key rows in Gold (resolved **CL-04**, **CL-05**).
- `lifetime_value_actual` computed from qualifying order revenue (`data-model.md`, `design-notes.md`).
- Customer behavior segments use **order value** (total/average revenue from qualifying orders) calibrated on the generated sample data (**CL-03**); cutoffs in `design-notes.md`.
- Bronze reruns and isolated defect groups are development conveniences, not extra PRD scope.

---

## Edge Cases

- Missing, empty, or unreadable source files; unexpected columns.
- Values that do not parse to expected types (caught by type validation).
- Duplicate PKs in multiple groups; duplicates that also fail other checks — all such rows remain in Silver as `FAIL` and out of Gold.
- NULL vs orphan foreign keys; orders pointing at invalid parent rows.
- Invalid or inconsistent `quantity`, `unit_price`, `total_amount`; NULL `payment_date` where allowed.
- No qualifying orders for a customer/product; averages with zero rows.
- Re-running pipeline stages; defect overlap affecting distinct failure counts.
- Spark CSV null/parsing behavior differing from the generator.

Implement only edge handling needed for required behavior within the planned implementation window.

---

## Resolved Clarifications

Decisions below drive implementation; they supersede earlier open questions.

| ID | Decision |
|---|---|
| **CL-01** | **Four** Gold aggregation tables: Sales by Product, Revenue by Customer, **Daily/Weekly Trends** (`gold_daily_weekly_trends`), Customer Segmentation. |
| **CL-02** | Silver implements four core validation areas: completeness, uniqueness, type validation, and referential integrity. `05_quality_business_logic.py` is supplementary/stretch. |
| **CL-03** | Behavior segments (High-Value / Repeat / One-Time / Inactive) are assigned using **order value** and order facts from the sample data; numeric cutoffs documented in `design-notes.md`. |
| **CL-04** | Rows that fail Silver validation (`quality_check_result` = `FAIL`) **must not** be loaded into Gold. |
| **CL-05** | Duplicate `customer_id` / `order_id` rows are **flagged** in uniqueness checks (`failed_checks` includes `uniqueness`) and **excluded from Gold** (no duplicate survives into analytics). |
| **CL-06** | Dashboard SQL queries use **Gold tables only**. |

---

## High-Level Acceptance Criteria

The submission is complete when:

1. Three source CSVs exist at 10,000 / 100,000 / 500 rows with PRD intentional quality issues; generator behavior is documented.
2. Bronze ingests all three sources as raw data with ingestion metadata and sensible input errors.
3. Silver runs all four core validation areas (CL-02), flags bad rows, and delivers a quality report with % or pass/fail by category. Business-logic validation is supplementary/stretch.
4. Tests show intentional defects are caught; failed and duplicate rows do not appear in Gold.
5. Gold delivers **four** aggregation tables (CL-01) with verifiable calculations.
6. Databricks SQL Dashboard has ≥3 tiles; queries read from Gold only (CL-06); setup guide is in repo.
7. Schema/setup, seed data, and README support end-to-end execution.
8. Mandatory artifacts are present: `tool-workflow.md`, `candidate-info.md`, design/data-model/DQ docs, debugging and reflection notes, and **full** `ai-prompts/` history.
9. Code is readable, commented, and appropriately scoped — no unnecessary production complexity.
