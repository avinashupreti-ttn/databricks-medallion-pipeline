-- GD-04: Behavior segments from PASS customers and PASS order revenue.
-- High-Value threshold = 90th percentile of total_revenue among customers with orders.
-- Assignment (first match): Inactive → High-Value → Repeat → One-Time.
-- Always emit all four segment_type rows (counts may be zero).
-- See design-notes.md (CL-03).

CREATE OR REPLACE TABLE `__CATALOG__`.`__GOLD_SCHEMA__`.`gold_customer_segmentation` AS
WITH pass_customers AS (
  SELECT customer_id
  FROM `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_customers`
  WHERE quality_check_result = 'PASS'
),
pass_orders AS (
  SELECT customer_id, total_amount
  FROM `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_orders`
  WHERE quality_check_result = 'PASS'
),
customer_metrics AS (
  SELECT
    c.customer_id,
    CAST(COUNT(o.customer_id) AS BIGINT) AS order_count,
    CAST(COALESCE(SUM(o.total_amount), 0) AS DECIMAL(18, 2)) AS total_revenue
  FROM pass_customers c
  LEFT JOIN pass_orders o
    ON c.customer_id = o.customer_id
  GROUP BY c.customer_id
),
threshold AS (
  SELECT CAST(percentile(total_revenue, 0.9) AS DECIMAL(18, 2)) AS high_value_threshold
  FROM customer_metrics
  WHERE order_count > 0
),
assigned AS (
  SELECT
    m.customer_id,
    m.order_count,
    m.total_revenue,
    CASE
      WHEN m.order_count = 0 THEN 'Inactive'
      WHEN m.total_revenue >= t.high_value_threshold THEN 'High-Value'
      WHEN m.order_count >= 2 THEN 'Repeat'
      ELSE 'One-Time'
    END AS segment_type
  FROM customer_metrics m
  CROSS JOIN threshold t
),
segment_dim AS (
  SELECT explode(
    array('High-Value', 'Repeat', 'One-Time', 'Inactive')
  ) AS segment_type
)
SELECT
  d.segment_type,
  CAST(COUNT(a.customer_id) AS BIGINT) AS customer_count,
  CAST(COALESCE(AVG(a.total_revenue), 0) AS DECIMAL(18, 2)) AS avg_revenue,
  CAST(COALESCE(SUM(a.total_revenue), 0) AS DECIMAL(18, 2)) AS total_revenue
FROM segment_dim d
LEFT JOIN assigned a
  ON d.segment_type = a.segment_type
GROUP BY d.segment_type
;
