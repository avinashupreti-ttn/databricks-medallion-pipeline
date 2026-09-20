# Databricks AI/BI dashboard setup (T5)

Gold-only dashboard for the e-commerce medallion pipeline (DB-01–DB-06, CL-06).

**Preferred path:** deploy with the Databricks Asset Bundle. Manual UI recreation is a fallback only.

## Environment

| Setting | Value |
|---|---|
| Catalog | `workspace` |
| Gold schema | `c1_gold` |
| Bundle resource key | `ecommerce_gold_dashboard` |
| Display name | `ecommerce-gold-dashboard` (dev prefix may appear after deploy) |
| Definition | `src/dashboard/ecommerce_gold_dashboard.lvdash.json` |
| Reference SQL | `src/dashboard/dashboard_queries.sql` |
| Resource YAML | `resources/ecommerce_gold_dashboard.yml` |
| SQL warehouse | `warehouse_id` variable (lookup default: `Serverless Starter Warehouse`) |

### Gold tables (exact names — query these only)

| Table | Used for |
|---|---|
| `workspace.c1_gold.gold_sales_by_product` | Top 10 products + category filter |
| `workspace.c1_gold.gold_revenue_by_customer` | Revenue distribution histogram |
| `workspace.c1_gold.gold_customer_segmentation` | Segmentation pie (all four `segment_type`s) |
| `workspace.c1_gold.gold_daily_weekly_trends` | Daily line chart (`period_grain = 'DAY'` only) |

Do not query Bronze (`c1_bronze`) or Silver (`c1_silver`) from the dashboard.

---

## Status

| Step | Status |
|---|---|
| Gold-only SQL + `.lvdash.json` + resource YAML | Done |
| Presentation refine (horizontal bars, readable buckets, legend, category filter) | Done |
| Local filter layout (beside charts; category + date range) | Done |
| `databricks bundle validate -t free` | Run locally; see agent report |
| `databricks bundle deploy` | **PENDING** (you) |
| Open dashboard and verify tiles / filter | **PENDING** (you) |
| Publish / share | **PENDING** (you) |

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

1. Pipeline has populated the four Gold tables under `workspace.c1_gold`.
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

1. Open **Dashboards** → `ecommerce-gold-dashboard` (bundle path under your user `.bundle/.../free`).
2. Confirm warehouse can read `workspace.c1_gold.*`.
3. Check four tiles + **Product category** filter.
4. Publish when ready (**PENDING** until you do it).

Sync remote UI edits back (optional):

```bash
/opt/homebrew/bin/databricks bundle generate dashboard \
  --resource ecommerce_gold_dashboard --force -t free --profile DE_C1_FREE
```

---

## Smoke checks (SQL Editor)

```sql
SELECT COUNT(*) AS product_rows
FROM `workspace`.`c1_gold`.`gold_sales_by_product`;

SELECT COUNT(*) AS customer_rows
FROM `workspace`.`c1_gold`.`gold_revenue_by_customer`;

SELECT COUNT(*) AS day_trend_rows
FROM `workspace`.`c1_gold`.`gold_daily_weekly_trends`
WHERE period_grain = 'DAY';

SELECT segment_type, customer_count
FROM `workspace`.`c1_gold`.`gold_customer_segmentation`
ORDER BY segment_type;
```

Expect non-zero product/customer/day rows; segmentation returns four `segment_type` values (Inactive may be 0).

---

## Validation checklist (**PENDING** until you complete in Databricks)

### Bundle

- [ ] `bundle validate -t free` succeeds.
- [ ] `bundle deploy -t free` succeeds (you).
- [ ] Dashboard `ecommerce_gold_dashboard` opens in the workspace.

### Visuals

- [ ] Top 10 is **horizontal**; `product_name` and `total_revenue` are readable.
- [ ] Histogram buckets use human-readable labels in ascending order.
- [ ] Pie legend shows High-Value, Repeat, One-Time, Inactive.
- [ ] Daily trend is a line on `period_grain = 'DAY'` only.
- [ ] **Top products: category** is a compact dropdown **above** Top 10 (not a full-height side panel).
- [ ] **Daily trend: date range** is a compact filter **above** the daily line.
- [ ] Charts use full half-width (two-column layout).
- [ ] Selecting a category shows top 10 products **within** that category (`ORDER BY total_revenue DESC LIMIT 10` after filter).
- [ ] Date range only affects the daily trend tile.
- [ ] No Bronze/Silver tables in datasets.

### Publish

- [ ] Published (or draft URL captured for submission).

---

## Screenshots to capture (**PENDING**)

1. Full page (four tiles + category filter).
2. Horizontal top-products bar.
3. Revenue distribution with readable buckets.
4. Segmentation pie with full legend.
5. Daily revenue trend.
6. Data tab showing Gold-only datasets.
7. Published view (if available).

---

## Out of scope

- Changing Bronze, Silver, Gold calculations or the pipeline job.
- New Gold business rules.
- Hardcoding host, tokens, or warehouse UUIDs in git.
- Claiming deploy / visual validation / publish before you finish the PENDING steps.
