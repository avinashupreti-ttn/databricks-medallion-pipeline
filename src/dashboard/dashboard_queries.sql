-- T5 Databricks AI/BI dashboard datasets (Gold only — DB-06 / CL-06).
-- Catalog/schema: workspace.c1_gold
-- Gold tables: gold_sales_by_product, gold_revenue_by_customer,
--              gold_customer_segmentation, gold_daily_weekly_trends
--
-- Use these SELECT statements as dashboard SQL datasets (read-only).
-- Do not run against Bronze or Silver. Do not CREATE/INSERT/DELETE here.
-- Embedded in src/dashboard/ecommerce_gold_dashboard.lvdash.json.
--
-- Dataset names:
--   1. top_10_products_by_revenue  (horizontal bar; :category_filter BEFORE LIMIT 10)
--   1b. product_categories         (DISTINCT category for filter dropdown only)
--   2. customer_revenue_distribution
--   3. customer_segmentation
--   4. daily_revenue_trend (period_grain = 'DAY' only)

-- ---------------------------------------------------------------------------
-- Dataset 1 — Top 10 products by revenue (DB-02, horizontal bar)
-- Source: workspace.c1_gold.gold_sales_by_product
-- :category_filter is applied BEFORE ORDER BY / LIMIT 10 so a selection
-- returns the top 10 products within the chosen category/categories.
-- Empty selection (size = 0) means all categories.
-- Dashboard MULTI param: keyword category_filter (ARRAY<STRING>).
-- ---------------------------------------------------------------------------
SELECT
  product_id,
  product_name,
  category,
  total_orders,
  total_revenue,
  avg_order_value
FROM `workspace`.`c1_gold`.`gold_sales_by_product`
WHERE (size(:category_filter) = 0 OR array_contains(:category_filter, category))
ORDER BY total_revenue DESC
LIMIT 10
;

-- ---------------------------------------------------------------------------
-- Dataset 1b — Product categories (filter dropdown options only)
-- ---------------------------------------------------------------------------
SELECT DISTINCT
  category
FROM `workspace`.`c1_gold`.`gold_sales_by_product`
ORDER BY category
;

-- ---------------------------------------------------------------------------
-- Dataset 2 — Customer revenue distribution (DB-03, histogram-style bar)
-- Source: workspace.c1_gold.gold_revenue_by_customer
-- Human-readable bucket labels; bucket_sort keeps ascending order.
-- Presentation-only bins; does not change Gold calculations.
-- ---------------------------------------------------------------------------
SELECT
  CASE
    WHEN total_revenue < 100 THEN '$0–$99'
    WHEN total_revenue < 250 THEN '$100–$249'
    WHEN total_revenue < 500 THEN '$250–$499'
    WHEN total_revenue < 1000 THEN '$500–$999'
    WHEN total_revenue < 2500 THEN '$1,000–$2,499'
    WHEN total_revenue < 5000 THEN '$2,500–$4,999'
    ELSE '$5,000+'
  END AS revenue_bucket,
  CASE
    WHEN total_revenue < 100 THEN 0
    WHEN total_revenue < 250 THEN 1
    WHEN total_revenue < 500 THEN 2
    WHEN total_revenue < 1000 THEN 3
    WHEN total_revenue < 2500 THEN 4
    WHEN total_revenue < 5000 THEN 5
    ELSE 6
  END AS bucket_sort,
  COUNT(*) AS customer_count,
  CAST(SUM(total_revenue) AS DECIMAL(18, 2)) AS bucket_total_revenue
FROM `workspace`.`c1_gold`.`gold_revenue_by_customer`
GROUP BY 1, 2
ORDER BY bucket_sort
;

-- ---------------------------------------------------------------------------
-- Dataset 3 — Customer segmentation (DB-04, pie chart)
-- Source: workspace.c1_gold.gold_customer_segmentation
-- Includes all four segment_type rows (Inactive may be zero-count).
-- ---------------------------------------------------------------------------
SELECT
  segment_type,
  customer_count,
  avg_revenue,
  total_revenue
FROM `workspace`.`c1_gold`.`gold_customer_segmentation`
ORDER BY
  CASE segment_type
    WHEN 'High-Value' THEN 1
    WHEN 'Repeat' THEN 2
    WHEN 'One-Time' THEN 3
    WHEN 'Inactive' THEN 4
    ELSE 5
  END
;

-- ---------------------------------------------------------------------------
-- Dataset 4 — Daily revenue trend (line chart; period_grain = 'DAY' only)
-- Source: workspace.c1_gold.gold_daily_weekly_trends
-- ---------------------------------------------------------------------------
SELECT
  period_start,
  period_grain,
  total_orders,
  total_revenue
FROM `workspace`.`c1_gold`.`gold_daily_weekly_trends`
WHERE period_grain = 'DAY'
ORDER BY period_start
;

-- ---------------------------------------------------------------------------
-- Smoke checks (SQL editor only — not dashboard datasets)
-- ---------------------------------------------------------------------------
-- SELECT COUNT(*) AS product_rows FROM `workspace`.`c1_gold`.`gold_sales_by_product`;
-- SELECT COUNT(*) AS customer_rows FROM `workspace`.`c1_gold`.`gold_revenue_by_customer`;
-- SELECT COUNT(*) AS day_trend_rows FROM `workspace`.`c1_gold`.`gold_daily_weekly_trends` WHERE period_grain = 'DAY';
-- SELECT * FROM `workspace`.`c1_gold`.`gold_customer_segmentation` ORDER BY segment_type;
