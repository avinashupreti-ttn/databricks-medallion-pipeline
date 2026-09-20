-- GD-02: Revenue by customer from PASS Silver orders joined to PASS customers.
-- lifetime_value_actual = sum of qualifying order total_amount (same as total_revenue).

CREATE OR REPLACE TABLE `__CATALOG__`.`__GOLD_SCHEMA__`.`gold_revenue_by_customer` AS
SELECT
  c.customer_id,
  c.customer_name,
  c.customer_segment,
  CAST(COUNT(*) AS BIGINT) AS total_orders,
  CAST(SUM(o.total_amount) AS DECIMAL(18, 2)) AS total_revenue,
  CAST(SUM(o.total_amount) / COUNT(*) AS DECIMAL(18, 2)) AS avg_order_value,
  CAST(SUM(o.total_amount) AS DECIMAL(18, 2)) AS lifetime_value_actual
FROM `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_orders` o
INNER JOIN `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_customers` c
  ON o.customer_id = c.customer_id
WHERE o.quality_check_result = 'PASS'
  AND c.quality_check_result = 'PASS'
GROUP BY c.customer_id, c.customer_name, c.customer_segment
;
