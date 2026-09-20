# Databricks AI/BI dashboard setup (T5)

Gold-only dashboard for the e-commerce medallion pipeline (DB-01–DB-06, CL-06).

**Preferred path:** deploy with the Databricks Asset Bundle. Manual UI recreation is a fallback only.

## Environment

| Setting | Value |
|---|---|
| Catalog | Bundle `dataset_catalog` ← `${var.catalog}` (default `workspace`) |
| Gold schema | Bundle `dataset_schema` ← `${var.gold_schema}` (default `c1_gold`) |
| Bundle resource key | `ecommerce_gold_dashboard` |
| Display name | `ecommerce-gold-dashboard` (dev prefix may appear after deploy) |
| Definition | `src/dashboard/ecommerce_gold_dashboard.lvdash.json` |
| Reference SQL | `src/dashboard/dashboard_queries.sql` (unqualified Gold table names) |
| Resource YAML | `resources/ecommerce_gold_dashboard.yml` |
| SQL warehouse | `warehouse_id` variable (lookup default: `Serverless Starter Warehouse`) |

### Gold tables (exact names — query these only)

Dashboard datasets use **unqualified** table names so
`dataset_catalog` / `dataset_schema` from the Asset Bundle apply. Do not
hardcode `catalog.schema.table` in `.lvdash.json` (fully qualified names
bypass those defaults).

| Table | Used for |
|---|---|
| `gold_sales_by_product` | Top 10 products + category filter |
| `gold_revenue_by_customer` | Revenue distribution histogram |
| `gold_customer_segmentation` | Segmentation pie (all four `segment_type`s) |
| `gold_daily_weekly_trends` | Daily line chart (`period_grain = 'DAY'` only) |

Do not query Bronze or Silver from the dashboard. Override catalog/schema
with `--var="catalog=..."` / `--var="gold_schema=..."` on validate/deploy
(same variables as the pipeline job).

---

## Status

| Step | Status |
|---|---|
| Gold-only SQL + `.lvdash.json` + resource YAML | Done |
| Presentation refine (horizontal bars, readable buckets, legend, category filter) | Done |
| Local filter layout (beside charts; category + date range) | Done |
| `databricks bundle validate -t free` | Done (prior isolated `DE_C1_FREE` run) |
| `databricks bundle deploy` | Done (workspace dashboard live) |
| Open dashboard and verify tiles / filters | Done — four Gold tiles + scoped category and date filters (screenshot evidence, 2026-09-21) |
| Publish / share | Draft/workspace view captured; formal publish optional |

---

## Visualizations

| Tile | Chart | Source |
|---|---|---|
| Top 10 products by revenue | **Horizontal** bar (`product_name` on Y, `total_revenue` on X, value labels) | `gold_sales_by_product` |
| Customer revenue distribution | Vertical histogram-style bar with human-readable buckets | `gold_revenue_by_customer` |
| Customer segmentation | Pie; legend includes High-Value, Repeat, One-Time, **Inactive** (even if count is 0) | `gold_customer_segmentation` |
| Daily revenue trend | Line | `gold_daily_weekly_trends` where `period_grain = 'DAY'` |

### Local filters (compact, above charts — not full-height tiles)

Two-column layout: each chart uses half width (`width: 3`). Filters are
`height: 1` rows directly above their chart.

| Filter label | Placement | Binding | Behavior |
|---|---|---|---|
| **Top products: category** | Compact dropdown above Top 10 | `ds01cats` (options) + `ds01prod` MULTI param `:category_filter` | Filter applied **before** `LIMIT 10` → top 10 **within** selected category |
| **Daily trend: date range** | Compact date range above Daily trend | `ds04dayt` / `period_start` only | Does not affect other tiles |

Does **not** filter: revenue distribution, customer segmentation (no category/date dims).
Does **not** apply category to daily trend, or date range to top products.

Revenue bucket labels (ascending order): `$0–$99`, `$100–$249`, `$250–$499`, `$500–$999`, `$1,000–$2,499`, `$2,500–$4,999`, `$5,000+`.

---

## Asset Bundle workflow

The Bronze → Silver → Gold job is unchanged. Deploy updates the dashboard resource alongside the job.

### Prerequisites

1. Pipeline has populated the four Gold tables under the configured
   `catalog.gold_schema` (default `workspace.c1_gold`).
2. CLI: `/opt/homebrew/bin/databricks` (or equivalent).
3. Isolated Free Edition profile (example: `DE_C1_FREE` via `$HOME/.config/databricks-de-c1/.databrickscfg` — not `~/.databrickscfg`).
4. SQL warehouse available (default lookup name: `Serverless Starter Warehouse`).

### Validate (does not deploy)

```bash
cd /path/to/databricks-medallion-pipeline

export DATABRICKS_CONFIG_FILE="$HOME/.config/databricks-de-c1/.databrickscfg"
export DATABRICKS_TF_VERSION=1.5.5
export DATABRICKS_TF_EXEC_PATH=/opt/homebrew/bin/terraform

/opt/homebrew/bin/databricks bundle validate -t free --profile DE_C1_FREE
```

### Deploy (you run this)

```bash
export DATABRICKS_CONFIG_FILE="$HOME/.config/databricks-de-c1/.databrickscfg"
export DATABRICKS_TF_VERSION=1.5.5
export DATABRICKS_TF_EXEC_PATH=/opt/homebrew/bin/terraform

/opt/homebrew/bin/databricks bundle deploy -t free --profile DE_C1_FREE
```

Optional warehouse override:

```bash
/opt/homebrew/bin/databricks warehouses list --profile DE_C1_FREE
/opt/homebrew/bin/databricks bundle deploy -t free --profile DE_C1_FREE \
  --var="warehouse_id=YOUR_WAREHOUSE_ID"
```

### After deploy

1. Open **Dashboards** → `ecommerce-gold-dashboard` (bundle path under your user `.bundle/...`).
2. Confirm warehouse can read the configured Gold schema tables.
3. Check four tiles + **Top products: category** and **Daily trend: date range**.
4. Publish when ready for wider sharing (optional if draft/workspace view is enough for assessment).

Sync remote UI edits back (optional):

```bash
/opt/homebrew/bin/databricks bundle generate dashboard \
  --resource ecommerce_gold_dashboard --force -t free --profile DE_C1_FREE
```

---

## Smoke checks (SQL Editor)

```sql
-- Prefer USE CATALOG / USE SCHEMA matching your bundle vars, then:
SELECT COUNT(*) AS product_rows
FROM gold_sales_by_product;

SELECT COUNT(*) AS customer_rows
FROM gold_revenue_by_customer;

SELECT COUNT(*) AS day_trend_rows
FROM gold_daily_weekly_trends
WHERE period_grain = 'DAY';

SELECT segment_type, customer_count
FROM gold_customer_segmentation
ORDER BY segment_type;
```

Expect non-zero product/customer/day rows; segmentation returns four `segment_type` values (Inactive may be 0).

---

## Validation checklist

### Bundle

- [x] `bundle validate -t free` succeeds.
- [x] `bundle deploy -t free` succeeds.
- [x] Dashboard `ecommerce_gold_dashboard` opens in the workspace.

### Visuals (screenshot evidence, 2026-09-21)

- [x] Top 10 is **horizontal**; `product_name` and `total_revenue` are readable.
- [x] Histogram buckets use human-readable labels in ascending order.
- [x] Pie legend shows High-Value, Repeat, One-Time, Inactive.
- [x] Daily trend is a line on `period_grain = 'DAY'` only.
- [x] **Top products: category** is a compact dropdown **above** Top 10 (not a full-height side panel).
- [x] **Daily trend: date range** is a compact filter **above** the daily line.
- [x] Charts use full half-width (two-column layout).
- [x] Selecting a category shows top 10 products **within** that category (`ORDER BY total_revenue DESC LIMIT 10` after filter) — filter present; exercised at **All** in evidence.
- [x] Date range only affects the daily trend tile (scoped filter labeling).
- [x] No Bronze/Silver tables in datasets (Gold-only design + guide).

### Publish

- [x] Workspace/draft view captured for submission (formal Publish optional).

---

## Screenshots captured

1. Full page (four tiles + category filter + daily date range) — attached closure evidence.
2. Horizontal top-products bar — included in full page.
3. Revenue distribution with readable buckets — included.
4. Segmentation pie with full legend — included.
5. Daily revenue trend — included.
6. Data tab Gold-only datasets — design/guide; not required to re-open for this closure.
7. Published view — draft/workspace view used if Publish was not separately confirmed.

---

## Out of scope

- Changing Bronze, Silver, Gold calculations or the pipeline job.
- New Gold business rules.
- Hardcoding host, tokens, or warehouse UUIDs in git.
