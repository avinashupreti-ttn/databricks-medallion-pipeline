-- Medallion setup for Databricks serverless (Unity Catalog).
-- Replace __CATALOG__, __BRONZE_SCHEMA__, __SILVER_SCHEMA__, and
-- __GOLD_SCHEMA__ before running this file in a SQL editor, or run
-- src/bronze/ingest_all.py / src/silver/create_silver_tables.py /
-- src/gold/create_gold_tables.py, which substitute those tokens and
-- execute these statements.
-- The catalog must already exist. This script does not create a catalog.
-- It creates the Bronze, Silver, and Gold schemas and empty Delta tables.
-- Pipeline stages overwrite table data on each rerun.
-- Bronze/Silver apply Gold DDL only when gold_schema is configured.
--
-- Free Edition example:
--   catalog=workspace, bronze=c1_bronze, silver=c1_silver, gold=c1_gold
--   landing=/Volumes/workspace/c1_landing/landing

CREATE SCHEMA IF NOT EXISTS `__CATALOG__`.`__BRONZE_SCHEMA__`
COMMENT 'E-commerce medallion Bronze (raw ingest)';

CREATE SCHEMA IF NOT EXISTS `__CATALOG__`.`__SILVER_SCHEMA__`
COMMENT 'E-commerce medallion Silver (validated + DQ metrics)';

CREATE SCHEMA IF NOT EXISTS `__CATALOG__`.`__GOLD_SCHEMA__`
COMMENT 'E-commerce medallion Gold (PASS-only aggregations)';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__BRONZE_SCHEMA__`.`bronze_customers` (
  customer_id INT NOT NULL,
  customer_name STRING NOT NULL,
  email STRING,
  country STRING NOT NULL,
  signup_date DATE NOT NULL,
  customer_segment STRING NOT NULL,
  lifetime_value DECIMAL(18, 2) NOT NULL,
  _ingested_at TIMESTAMP NOT NULL,
  _source_file STRING NOT NULL,
  _ingestion_batch_id STRING NOT NULL
)
USING DELTA
COMMENT 'Raw customers plus ingestion metadata. No cleansing or deduplication.';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__BRONZE_SCHEMA__`.`bronze_orders` (
  order_id INT NOT NULL,
  customer_id INT,
  order_date DATE NOT NULL,
  product_id INT,
  quantity INT NOT NULL,
  unit_price DECIMAL(18, 2) NOT NULL,
  total_amount DECIMAL(18, 2) NOT NULL,
  order_status STRING NOT NULL,
  payment_date DATE,
  _ingested_at TIMESTAMP NOT NULL,
  _source_file STRING NOT NULL,
  _ingestion_batch_id STRING NOT NULL
)
USING DELTA
COMMENT 'Raw orders plus ingestion metadata. No cleansing or deduplication.';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__BRONZE_SCHEMA__`.`bronze_products` (
  product_id INT NOT NULL,
  product_name STRING NOT NULL,
  category STRING NOT NULL,
  price DECIMAL(18, 2) NOT NULL,
  cost DECIMAL(18, 2) NOT NULL,
  stock_quantity INT NOT NULL,
  reorder_level INT NOT NULL,
  _ingested_at TIMESTAMP NOT NULL,
  _source_file STRING NOT NULL,
  _ingestion_batch_id STRING NOT NULL
)
USING DELTA
COMMENT 'Raw products plus ingestion metadata. No cleansing or deduplication.';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_customers` (
  customer_id INT NOT NULL,
  customer_name STRING NOT NULL,
  email STRING,
  country STRING NOT NULL,
  signup_date DATE NOT NULL,
  customer_segment STRING NOT NULL,
  lifetime_value DECIMAL(18, 2) NOT NULL,
  _ingested_at TIMESTAMP NOT NULL,
  _source_file STRING NOT NULL,
  _ingestion_batch_id STRING NOT NULL,
  quality_check_result STRING NOT NULL,
  failed_checks ARRAY<STRING> NOT NULL,
  _silver_processed_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Validated customers. All Bronze rows retained with quality flags.';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_orders` (
  order_id INT NOT NULL,
  customer_id INT,
  order_date DATE NOT NULL,
  product_id INT,
  quantity INT NOT NULL,
  unit_price DECIMAL(18, 2) NOT NULL,
  total_amount DECIMAL(18, 2) NOT NULL,
  order_status STRING NOT NULL,
  payment_date DATE,
  _ingested_at TIMESTAMP NOT NULL,
  _source_file STRING NOT NULL,
  _ingestion_batch_id STRING NOT NULL,
  quality_check_result STRING NOT NULL,
  failed_checks ARRAY<STRING> NOT NULL,
  _silver_processed_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Validated orders. All Bronze rows retained with quality flags.';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__SILVER_SCHEMA__`.`silver_products` (
  product_id INT NOT NULL,
  product_name STRING NOT NULL,
  category STRING NOT NULL,
  price DECIMAL(18, 2) NOT NULL,
  cost DECIMAL(18, 2) NOT NULL,
  stock_quantity INT NOT NULL,
  reorder_level INT NOT NULL,
  _ingested_at TIMESTAMP NOT NULL,
  _source_file STRING NOT NULL,
  _ingestion_batch_id STRING NOT NULL,
  quality_check_result STRING NOT NULL,
  failed_checks ARRAY<STRING> NOT NULL,
  _silver_processed_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Validated products. All Bronze rows retained with quality flags.';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__SILVER_SCHEMA__`.`dq_metrics_report` (
  check_category STRING NOT NULL,
  entity STRING NOT NULL,
  rows_evaluated BIGINT NOT NULL,
  rows_passed BIGINT NOT NULL,
  rows_failed BIGINT NOT NULL,
  pass_pct DOUBLE NOT NULL,
  reported_at TIMESTAMP NOT NULL
)
USING DELTA
COMMENT 'Pass/fail counts and pass_pct per Silver validation category.';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__GOLD_SCHEMA__`.`gold_sales_by_product` (
  product_id INT NOT NULL,
  product_name STRING NOT NULL,
  category STRING NOT NULL,
  total_orders BIGINT NOT NULL,
  total_revenue DECIMAL(18, 2) NOT NULL,
  avg_order_value DECIMAL(18, 2) NOT NULL
)
USING DELTA
COMMENT 'PASS-only sales aggregated by product (GD-01).';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__GOLD_SCHEMA__`.`gold_revenue_by_customer` (
  customer_id INT NOT NULL,
  customer_name STRING NOT NULL,
  customer_segment STRING NOT NULL,
  total_orders BIGINT NOT NULL,
  total_revenue DECIMAL(18, 2) NOT NULL,
  avg_order_value DECIMAL(18, 2) NOT NULL,
  lifetime_value_actual DECIMAL(18, 2) NOT NULL
)
USING DELTA
COMMENT 'PASS-only revenue aggregated by customer (GD-02).';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__GOLD_SCHEMA__`.`gold_daily_weekly_trends` (
  period_start DATE NOT NULL,
  period_grain STRING NOT NULL,
  total_orders BIGINT NOT NULL,
  total_revenue DECIMAL(18, 2) NOT NULL
)
USING DELTA
COMMENT 'PASS-only order trends at DAY and WEEK grains (GD-03).';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__GOLD_SCHEMA__`.`gold_customer_segmentation` (
  segment_type STRING NOT NULL,
  customer_count BIGINT NOT NULL,
  avg_revenue DECIMAL(18, 2) NOT NULL,
  total_revenue DECIMAL(18, 2) NOT NULL
)
USING DELTA
COMMENT 'PASS-only behavior segments High-Value / Repeat / One-Time / Inactive (GD-04).';
