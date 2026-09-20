-- Bronze setup for Databricks serverless (Unity Catalog).
-- Replace __CATALOG__ and __SCHEMA__ before running this file in a SQL
-- editor, or run src/bronze/ingest_all.py, which substitutes those tokens
-- and executes these statements.
-- The catalog must already exist. This script does not create a catalog.
-- It creates the schema and empty Bronze Delta tables. Ingestion overwrites
-- table data on each rerun. Silver and Gold DDL are added with those layers.

CREATE SCHEMA IF NOT EXISTS `__CATALOG__`.`__SCHEMA__`
COMMENT 'E-commerce medallion pipeline';

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__SCHEMA__`.`bronze_customers` (
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

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__SCHEMA__`.`bronze_orders` (
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

CREATE TABLE IF NOT EXISTS `__CATALOG__`.`__SCHEMA__`.`bronze_products` (
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
