-- GD-03: Daily and weekly order trends from PASS Silver orders only.
-- DAY grain uses order_date. WEEK grain uses ISO Monday via date_trunc('WEEK', ...).

CREATE OR REPLACE TABLE `__CATALOG__`.`__GOLD_SCHEMA__`.`gold_daily_weekly_trends` AS
SELECT
  CAST(order_date AS DATE) AS period_start,
  CAST('DAY' AS STRING) AS period_grain,
  CAST(COUNT(*) AS BIGINT) AS total_orders,
  CAST(SUM(total_amount) AS DECIMAL(18, 2)) AS total_revenue
FROM `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_orders`
WHERE quality_check_result = 'PASS'
GROUP BY CAST(order_date AS DATE)

UNION ALL

SELECT
  CAST(date_trunc('WEEK', order_date) AS DATE) AS period_start,
  CAST('WEEK' AS STRING) AS period_grain,
  CAST(COUNT(*) AS BIGINT) AS total_orders,
  CAST(SUM(total_amount) AS DECIMAL(18, 2)) AS total_revenue
FROM `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_orders`
WHERE quality_check_result = 'PASS'
GROUP BY CAST(date_trunc('WEEK', order_date) AS DATE)
;
