# Databricks Medallion Pipeline

A synthetic e-commerce data pipeline built on Databricks serverless. It ingests customer, order, and product CSVs; retains and assesses their quality; produces analytics tables; and presents the results in an AI/BI dashboard.

```text
CSV files → Bronze Delta tables → Silver Delta tables + quality report
          → Gold aggregations → Databricks AI/BI dashboard
```

The project is an AI-assisted data engineering exercise. Alongside the pipeline, the repository includes requirements, design decisions, prompt history, test evidence, and a reflection on the workflow. Start with `requirement-analysis.md` for the agreed implementation contract.

## What is implemented


| Component     | Implementation                                                                                                                                                                                                                                 |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Sample data   | A deterministic Python generator creates 10,000 customers, 100,000 orders, and 500 products with intentional missing values, duplicate keys, and orphan references.                                                                            |
| Bronze        | PySpark reads the three landing CSVs into Delta tables and adds ingestion time, source path, and batch ID. It does not deduplicate or apply business quality rules.                                                                            |
| Silver        | Four checks assess completeness, uniqueness, types/domains, and referential integrity. Every ingested row is retained with `quality_check_result` and `failed_checks`. A `dq_metrics_report` records pass and fail counts by check and entity. |
| Gold          | Four SQL tables summarize product sales, customer revenue, daily and weekly trends, and behavior-based customer segments. Only Silver `PASS` rows contribute.                                                                                  |
| Dashboard     | A Databricks AI/BI dashboard displays top products, customer revenue distribution, customer segments, and a daily trend. Its datasets query Gold tables only.                                                                                  |
| Orchestration | A Databricks Asset Bundle defines a serverless job with Bronze → Silver → Gold task dependencies and deploys the dashboard.                                                                                                                    |


The generated sample's itemized quality issues affect **460 distinct rows**: 60 customers and 400 orders. The original PRD also says “~700 problematic rows”; the itemized counts and this implementation's documented interpretation total 460. See `data-quality-strategy.md` for the exact breakdown.

### How the layers work

**Bronze** reads `customers.csv`, `orders.csv`, and `products.csv` from a configurable landing directory, writes `bronze_customers`, `bronze_orders`, and `bronze_products`, and logs row counts. Source files must have the expected headers. Each run overwrites the corresponding Bronze tables, so this is a full refresh rather than an incremental pipeline.

**Silver** reads the Bronze tables and writes `silver_customers`, `silver_orders`, and `silver_products`. A failed row stays in its Silver table and records one or more failed check categories. Duplicate customer and order keys are all flagged. Non-null foreign keys are checked against the customer and product key sets; null foreign keys are handled by completeness. The quality report is written to `dq_metrics_report` in the Silver schema.

**Gold** reads quality-passing Silver data. The current SQL includes **Completed and Pending** orders in Gold order and value metrics and excludes **Cancelled** orders. Pending value is therefore included in the existing `total_revenue` measures; it can be read as projected value rather than collected revenue. The four outputs are:

- `gold_sales_by_product`: order count, total value, and average order value by product.
- `gold_revenue_by_customer`: order count, total value, average order value, and `lifetime_value_actual` by customer.
- `gold_daily_weekly_trends`: daily and ISO Monday-start weekly order/value totals.
- `gold_customer_segmentation`: High-Value, Repeat, One-Time, and Inactive groups. High-Value uses the 90th percentile of value among customers with qualifying orders.

The Gold SQL files and their local Python aggregation helpers contain the precise calculation rules. Gold tables are overwritten on rerun.

## Repository structure

```text
databricks-medallion-pipeline/
├── README.md                         # Repository runbook
├── prd.md                            # Original assessment brief
├── requirement-analysis.md           # Agreed requirements and decisions
├── design-notes.md                   # Architecture and trade-offs
├── data-model.md                     # Source and output schemas
├── data-quality-strategy.md          # Validation rules and defect counts
├── candidate-info.md                # Submission metadata
├── tool-workflow.md                  # AI workflow foundation
├── debugging-notes.md               # Investigated failures and fixes
├── reflection.md
├── final-ai-usage-summary.md
├── databricks.yml                    # Asset Bundle configuration
├── requirements-dev.txt             # Local test dependencies
├── data/                            # Generated CSVs, when present locally
│   ├── customers.csv
│   ├── orders.csv
│   └── products.csv
├── database/schema.sql              # Unity Catalog schemas/table setup
├── resources/                       # Job and dashboard Bundle resources
├── src/
│   ├── config.py                     # Runtime setting resolution
│   ├── data_generation/             # Generator and generation notes
│   ├── bronze/                      # Entity scripts and shared ingestion
│   ├── silver/                      # Four checks and Silver/report builder
│   ├── gold/                        # Four SQL aggregations and runner
│   └── dashboard/                   # SQL, dashboard JSON, setup guide
├── tests/
│   ├── test_*.py                    # Local unit and contract tests
│   ├── databricks/                  # Serverless table-validation notebook
│   ├── summary/                     # Recorded execution summaries
│   └── reports/                     # HTML pytest reports
├── docs/                            # Deployment guide and visual evidence
├── ai-prompts/                      # Prompt and decision history
└── tool-specific/cursor-workflow/   # Cursor context and task plan
```

## Deploy and run



### 1. Prepare the local data

You need Python 3.9+, the Databricks CLI, a Databricks workspace with Unity Catalog and serverless jobs, and access to a SQL warehouse for the dashboard. Configure a Databricks CLI profile for your own workspace; credentials are not stored in this repository.

From the repository root, generate the CSVs if they are absent:

```bash
python3 -m src.data_generation.generate_sample_data
```

The default seed is 42. Generation details and the intended defects are in `src/data_generation/DATA_GENERATION_NOTES.md`.

Create or select a Unity Catalog Volume directory and upload all three CSVs to it. The default Bundle setting expects:

```text
/Volumes/workspace/c1_landing/landing/customers.csv
/Volumes/workspace/c1_landing/landing/orders.csv
/Volumes/workspace/c1_landing/landing/products.csv
```

For example, if your profile and Volume allow CLI file copies:

```bash
databricks fs cp data/customers.csv dbfs:/Volumes/workspace/c1_landing/landing/customers.csv --profile <PROFILE>
databricks fs cp data/orders.csv dbfs:/Volumes/workspace/c1_landing/landing/orders.csv --profile <PROFILE>
databricks fs cp data/products.csv dbfs:/Volumes/workspace/c1_landing/landing/products.csv --profile <PROFILE>
```

The catalog and Volume must already exist. The pipeline's `database/schema.sql` creates the Bronze, Silver, and Gold schemas and table definitions on first run.

### 2. Configure the Bundle

The `free` target in `databricks.yml` defaults to catalog `workspace`, schemas `c1_bronze`, `c1_silver`, and `c1_gold`, and the landing directory shown above. The dashboard also needs a SQL warehouse; the Bundle looks up `Serverless Starter Warehouse` by default.

If your names differ, pass overrides when validating and deploying. Keep the same values across both commands:

```bash
databricks bundle validate -t free --profile <PROFILE> \
  --var="catalog=<CATALOG>" \
  --var="bronze_schema=<BRONZE_SCHEMA>" \
  --var="silver_schema=<SILVER_SCHEMA>" \
  --var="gold_schema=<GOLD_SCHEMA>" \
  --var="landing_path=/Volumes/<CATALOG>/<VOLUME_SCHEMA>/<VOLUME>/<DIRECTORY>" \
  --var="warehouse_id=<WAREHOUSE_ID>"
```

Use an installed Databricks CLI version that supports the dashboard resource fields in `resources/ecommerce_gold_dashboard.yml`, including `dataset_catalog` and `dataset_schema`. Those fields bind the dashboard's unqualified Gold table queries to the Bundle catalog and Gold schema. See `docs/bundle-deployment.md` and `src/dashboard/DASHBOARD_GUIDE.md` for environment-specific guidance.

### 3. Deploy, run, and inspect

```bash
databricks bundle deploy -t free --profile <PROFILE>
databricks bundle run ecommerce_medallion_pipeline -t free --profile <PROFILE>
```

The job runs `bronze_ingest`, then `silver_validate`, then `gold_aggregate`. A failed task prevents downstream tasks from starting. After a successful run, inspect the three Bronze tables, three Silver tables plus `dq_metrics_report`, and four Gold tables in your configured catalog. Then open `ecommerce-gold-dashboard` in the Databricks workspace and confirm that its SQL warehouse can read the Gold schema.

If you use overrides, deploy with the same `--var` values used at validation. Bundle variables set the job defaults. Details about job parameters and dashboard setup are in `docs/bundle-deployment.md` and `src/dashboard/DASHBOARD_GUIDE.md`.

## Test and validation evidence

Install local test dependencies and run the suite from the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ --ignore=tests/databricks -q
```

Local tests cover the generator, configuration, data quality helpers, Gold aggregation helpers, and code contracts. Tests marked for Databricks are skipped locally; a skip is not a pass. The repository's recorded full local run in `tests/summary/final-execution.md` reports **72 passed and 12 skipped** on 2026-09-21.

For live table checks, deploy the Bundle, populate the tables, then open and run `tests/databricks/ts_02_05_serverless_validation.py` on Databricks serverless. It checks source/Bronze counts, Silver defect detection and metrics, known-good rows, and Gold reconciliation. The repository also contains recorded job-run and dashboard evidence under `tests/summary/` and `docs/evidence/`; that evidence describes the runs at the time it was captured and does not replace validation after later edits.

## Scope and useful references

This exercise uses full-refresh overwrites and synthetic data. It does not implement streaming, incremental merges, or the optional fifth Silver business-logic check. The source schema, specific validation categories, segmentation threshold, and resolved PRD ambiguities are documented in `data-model.md`, `data-quality-strategy.md`, `design-notes.md`, and `requirement-analysis.md`.

For deployment troubleshooting, use `docs/bundle-deployment.md`. For dashboard recreation and visual checks, use `src/dashboard/DASHBOARD_GUIDE.md`. For the AI-assisted workflow and evidence trail, see `tool-workflow.md`, `ai-prompts/`, and `tests/summary/`.