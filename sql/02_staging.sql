-- Bank DQ Platform: Staging Layer

-- 1. Raw Tables (All Text)
CREATE TABLE IF NOT EXISTS raw.transactions (
    step text,
    type text,
    amount text,
    name_orig text,
    oldbalance_org text,
    newbalance_orig text,
    name_dest text,
    oldbalance_dest text,
    newbalance_dest text,
    is_fraud text,
    is_flagged_fraud text
);

CREATE TABLE IF NOT EXISTS raw.customer_master (
    account_id text,
    segment text,
    kyc_status text,
    country text,
    opened_date text
);

CREATE TABLE IF NOT EXISTS raw.settlements (
    settlement_ref text,
    txn_id text,
    settled_amount text,
    settlement_date text
);

-- 2. Staging Tables (Typed)
CREATE TABLE IF NOT EXISTS stg.transactions (
    txn_id bigserial PRIMARY KEY,
    step int,
    type text,
    amount numeric(18,2),
    name_orig text,
    oldbalance_org numeric(18,2),
    newbalance_orig numeric(18,2),
    name_dest text,
    oldbalance_dest numeric(18,2),
    newbalance_dest numeric(18,2),
    is_fraud smallint,
    is_flagged_fraud smallint
);

CREATE TABLE IF NOT EXISTS stg.customer_master (
    account_id text,
    segment text,
    kyc_status text,
    country text,
    opened_date date
);

CREATE TABLE IF NOT EXISTS stg.settlements (
    settlement_ref text,
    txn_id bigint,
    settled_amount numeric(18,2),
    settlement_date date
);

-- 3. Populate Staging from Raw
INSERT INTO stg.transactions (
    step, type, amount, name_orig, oldbalance_org, newbalance_orig, 
    name_dest, oldbalance_dest, newbalance_dest, is_fraud, is_flagged_fraud
)
SELECT
    NULLIF(step, '')::int,
    NULLIF(type, ''),
    NULLIF(amount, '')::numeric(18,2),
    NULLIF(name_orig, ''),
    NULLIF(oldbalance_org, '')::numeric(18,2),
    NULLIF(newbalance_orig, '')::numeric(18,2),
    NULLIF(name_dest, ''),
    NULLIF(oldbalance_dest, '')::numeric(18,2),
    NULLIF(newbalance_dest, '')::numeric(18,2),
    NULLIF(is_fraud, '')::smallint,
    NULLIF(is_flagged_fraud, '')::smallint
FROM raw.transactions;

INSERT INTO stg.customer_master (account_id, segment, kyc_status, country, opened_date)
SELECT
    NULLIF(account_id, ''),
    NULLIF(segment, ''),
    NULLIF(kyc_status, ''),
    NULLIF(country, ''),
    NULLIF(opened_date, '')::date
FROM raw.customer_master;

INSERT INTO stg.settlements (settlement_ref, txn_id, settled_amount, settlement_date)
SELECT
    NULLIF(settlement_ref, ''),
    NULLIF(txn_id, '')::bigint,
    NULLIF(settled_amount, '')::numeric(18,2),
    NULLIF(settlement_date, '')::date
FROM raw.settlements;
