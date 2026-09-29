-- Bank DQ Platform: Data Warehouse

-- 1. Dim Customer
CREATE TABLE IF NOT EXISTS dw.dim_customer AS
SELECT DISTINCT ON (account_id)
    account_id,
    segment,
    kyc_status,
    country,
    opened_date
FROM stg.customer_master
ORDER BY account_id;

ALTER TABLE dw.dim_customer ADD PRIMARY KEY (account_id);

-- 2. Dim Txn Type
CREATE TABLE IF NOT EXISTS dw.dim_txn_type (
    type_id serial PRIMARY KEY,
    type text UNIQUE,
    direction text
);

INSERT INTO dw.dim_txn_type (type, direction) VALUES
('CASH_IN', 'CREDIT'),
('CASH_OUT', 'DEBIT'),
('DEBIT', 'DEBIT'),
('PAYMENT', 'DEBIT'),
('TRANSFER', 'DEBIT')
ON CONFLICT DO NOTHING;

-- 3. Dim Time
CREATE TABLE IF NOT EXISTS dw.dim_time AS
SELECT DISTINCT
    step AS time_key,
    TIMESTAMP '2026-01-01' + step * INTERVAL '1 hour' AS txn_ts,
    EXTRACT(hour FROM (TIMESTAMP '2026-01-01' + step * INTERVAL '1 hour')) AS hour_of_day,
    EXTRACT(dow FROM (TIMESTAMP '2026-01-01' + step * INTERVAL '1 hour')) AS day_of_week,
    EXTRACT(week FROM (TIMESTAMP '2026-01-01' + step * INTERVAL '1 hour')) AS week_num,
    EXTRACT(month FROM (TIMESTAMP '2026-01-01' + step * INTERVAL '1 hour')) AS month_num
FROM stg.transactions;

ALTER TABLE dw.dim_time ADD PRIMARY KEY (time_key);

-- 4. Fact Transactions
CREATE TABLE IF NOT EXISTS dw.fact_transactions AS
SELECT
    txn_id,
    step,
    TIMESTAMP '2026-01-01' + step * INTERVAL '1 hour' AS txn_ts,
    type,
    amount,
    name_orig,
    oldbalance_org,
    newbalance_orig,
    name_dest,
    oldbalance_dest,
    newbalance_dest,
    is_fraud,
    is_flagged_fraud
FROM stg.transactions;

ALTER TABLE dw.fact_transactions ADD PRIMARY KEY (txn_id);
