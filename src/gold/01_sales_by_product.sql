-- GD-01: Sales by product from PASS Silver orders joined to PASS products.
-- Revenue = sum(total_amount). avg_order_value = total_revenue / total_orders.
-- Cancelled orders contribute no revenue and are excluded from Gold metrics.

CREATE OR REPLACE TABLE `__CATALOG__`.`__GOLD_SCHEMA__`.`gold_sales_by_product` AS
SELECT
  p.product_id,
  p.product_name,
  p.category,
  CAST(COUNT(*) AS BIGINT) AS total_orders,
  CAST(SUM(o.total_amount) AS DECIMAL(18, 2)) AS total_revenue,
  CAST(SUM(o.total_amount) / COUNT(*) AS DECIMAL(18, 2)) AS avg_order_value
FROM `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_orders` o
INNER JOIN `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_products` p
  ON o.product_id = p.product_id
WHERE o.quality_check_result = 'PASS'
  AND o.order_status <> 'Cancelled'
  AND p.quality_check_result = 'PASS'
GROUP BY p.product_id, p.product_name, p.category
;
