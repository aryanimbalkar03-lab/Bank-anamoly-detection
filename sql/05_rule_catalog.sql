-- Bank DQ Platform: Rule Catalog

CREATE TABLE IF NOT EXISTS dq.rule_catalog (
    rule_id serial PRIMARY KEY,
    rule_code text UNIQUE,
    dimension text,
    severity text CHECK (severity IN ('HIGH','MEDIUM','LOW')),
    description text,
    rule_sql text,
    active boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS dq.exceptions (
    exception_id bigserial PRIMARY KEY,
    rule_id int REFERENCES dq.rule_catalog(rule_id),
    txn_id bigint,
    detected_at timestamptz DEFAULT now(),
    status text DEFAULT 'OPEN',
    assigned_to text,
    resolved_at timestamptz,
    note text,
    UNIQUE (rule_id, txn_id)
);

CREATE TABLE IF NOT EXISTS dq.rule_run_log (
    run_id bigserial PRIMARY KEY,
    rule_id int REFERENCES dq.rule_catalog(rule_id),
    run_ts timestamptz DEFAULT now(),
    records_checked bigint,
    records_failed bigint
);

TRUNCATE TABLE dq.rule_catalog CASCADE;

INSERT INTO dq.rule_catalog (rule_code, dimension, severity, description, rule_sql, active) VALUES

-- Completeness (5)
('NULL_AMOUNT', 'Completeness', 'HIGH', 'Amount is NULL', 
$$SELECT txn_id FROM dw.fact_transactions WHERE amount IS NULL$$, true),

('NULL_TYPE', 'Completeness', 'HIGH', 'Type is NULL', 
$$SELECT txn_id FROM dw.fact_transactions WHERE type IS NULL$$, true),

('NULL_ORIG_ACCT', 'Completeness', 'HIGH', 'Origin account is NULL', 
$$SELECT txn_id FROM dw.fact_transactions WHERE name_orig IS NULL$$, true),

('NULL_DEST_ACCT', 'Completeness', 'HIGH', 'Destination account is NULL', 
$$SELECT txn_id FROM dw.fact_transactions WHERE name_dest IS NULL$$, true),

('NULL_BALANCE_FIELDS', 'Completeness', 'HIGH', 'Balance fields are NULL', 
$$SELECT txn_id FROM dw.fact_transactions WHERE oldbalance_org IS NULL OR newbalance_orig IS NULL OR oldbalance_dest IS NULL OR newbalance_dest IS NULL$$, true),

-- Validity (6)
('NEG_AMOUNT', 'Validity', 'HIGH', 'Amount is negative', 
$$SELECT txn_id FROM dw.fact_transactions WHERE amount < 0$$, true),

('ZERO_AMOUNT', 'Validity', 'MEDIUM', 'Amount is zero', 
$$SELECT txn_id FROM dw.fact_transactions WHERE amount = 0$$, true),

('INVALID_TYPE', 'Validity', 'HIGH', 'Invalid transaction type', 
$$SELECT txn_id FROM dw.fact_transactions WHERE type NOT IN ('CASH_IN','CASH_OUT','DEBIT','PAYMENT','TRANSFER')$$, true),

('AMOUNT_OVER_LIMIT', 'Validity', 'MEDIUM', 'Amount exceeds 10M limit', 
$$SELECT txn_id FROM dw.fact_transactions WHERE amount > 10000000$$, true),

('BAD_ACCT_FORMAT', 'Validity', 'HIGH', 'Account name format is invalid', 
$$SELECT txn_id FROM dw.fact_transactions WHERE name_orig !~ '^[CM][0-9]+$' OR name_dest !~ '^[CM][0-9]+$' $$, true),

('STEP_OUT_OF_RANGE', 'Validity', 'HIGH', 'Step out of 0-744 range', 
$$SELECT txn_id FROM dw.fact_transactions WHERE step < 0 OR step > 744$$, true),

-- Consistency (7)
('BAL_ORIG_MISMATCH', 'Consistency', 'HIGH', 'Origin balance mismatch', 
$$SELECT txn_id FROM dw.fact_transactions WHERE amount IS NOT NULL AND ABS(newbalance_orig - CASE WHEN type='CASH_IN' THEN oldbalance_org+amount ELSE oldbalance_org-amount END) > 0.01$$, true),

('BAL_DEST_MISMATCH', 'Consistency', 'HIGH', 'Destination balance mismatch for non-merchants', 
$$SELECT txn_id FROM dw.fact_transactions WHERE amount IS NOT NULL AND name_dest NOT LIKE 'M%' AND ABS(newbalance_dest - CASE WHEN type='CASH_IN' THEN oldbalance_dest-amount ELSE oldbalance_dest+amount END) > 0.01$$, true),

('ORIG_NEG_BALANCE', 'Consistency', 'MEDIUM', 'Origin negative balance', 
$$SELECT txn_id FROM dw.fact_transactions WHERE oldbalance_org < 0 OR newbalance_orig < 0$$, true),

('DEST_NEG_BALANCE', 'Consistency', 'MEDIUM', 'Destination negative balance', 
$$SELECT txn_id FROM dw.fact_transactions WHERE oldbalance_dest < 0 OR newbalance_dest < 0$$, true),

('FLAG_RULE_MISMATCH', 'Consistency', 'MEDIUM', 'Fraud flag rule mismatch', 
$$SELECT txn_id FROM dw.fact_transactions WHERE type = 'TRANSFER' AND amount > 200000 AND is_flagged_fraud = 0$$, true),

('SELF_TRANSFER', 'Consistency', 'MEDIUM', 'Origin equals destination', 
$$SELECT txn_id FROM dw.fact_transactions WHERE name_orig = name_dest$$, true),

('PAYMENT_DEST_NOT_MERCHANT', 'Consistency', 'MEDIUM', 'Payment dest not a merchant', 
$$SELECT txn_id FROM dw.fact_transactions WHERE type = 'PAYMENT' AND name_dest NOT LIKE 'M%'$$, true),

-- Uniqueness (3)
('DUP_BUSINESS_KEY', 'Uniqueness', 'MEDIUM', 'Duplicate transaction business key', 
$$SELECT txn_id FROM (SELECT txn_id, ROW_NUMBER() OVER (PARTITION BY name_orig,name_dest,amount,step,type ORDER BY txn_id) as rn FROM dw.fact_transactions) t WHERE t.rn > 1$$, true),

('DUP_CUSTOMER_MASTER', 'Uniqueness', 'MEDIUM', 'Duplicate customer master record', 
$$SELECT f.txn_id FROM dw.fact_transactions f JOIN (SELECT account_id FROM stg.customer_master GROUP BY account_id HAVING COUNT(*) > 1) d ON f.name_orig = d.account_id OR f.name_dest = d.account_id$$, true),

('DUP_SETTLEMENT_REF', 'Uniqueness', 'MEDIUM', 'Duplicate settlement reference', 
$$SELECT txn_id FROM (SELECT txn_id, ROW_NUMBER() OVER (PARTITION BY settlement_ref ORDER BY txn_id) as rn FROM stg.settlements) t WHERE t.rn > 1$$, true),

-- Integrity (4)
('ORPHAN_ORIG', 'Integrity', 'HIGH', 'Origin not in dim_customer (C-prefix only)', 
$$SELECT f.txn_id FROM dw.fact_transactions f LEFT JOIN dw.dim_customer c ON f.name_orig = c.account_id WHERE f.name_orig LIKE 'C%' AND c.account_id IS NULL$$, true),

('ORPHAN_DEST', 'Integrity', 'HIGH', 'Dest not in dim_customer (C-prefix only)', 
$$SELECT f.txn_id FROM dw.fact_transactions f LEFT JOIN dw.dim_customer c ON f.name_dest = c.account_id WHERE f.name_dest LIKE 'C%' AND c.account_id IS NULL$$, true),

('SETTLEMENT_MISSING', 'Integrity', 'HIGH', 'Settlement missing for txn_id', 
$$SELECT f.txn_id FROM dw.fact_transactions f LEFT JOIN stg.settlements s ON f.txn_id = s.txn_id WHERE s.txn_id IS NULL$$, true),

('SETTLEMENT_AMOUNT_DIFF', 'Integrity', 'HIGH', 'Settlement amount mismatch', 
$$SELECT f.txn_id FROM dw.fact_transactions f JOIN stg.settlements s ON f.txn_id = s.txn_id WHERE f.amount != s.settled_amount$$, true),

-- Timeliness (2)
('LATE_SETTLEMENT', 'Timeliness', 'MEDIUM', 'Settlement later than T+2', 
$$SELECT f.txn_id FROM dw.fact_transactions f JOIN stg.settlements s ON f.txn_id = s.txn_id WHERE s.settlement_date > (f.txn_ts::date + 2)$$, true),

('FUTURE_DATED', 'Timeliness', 'LOW', 'Future dated transaction', 
$$SELECT txn_id FROM dw.fact_transactions WHERE txn_ts > now()$$, true),

-- Anomaly (3)
('AMOUNT_ZSCORE_BY_TYPE', 'Anomaly', 'MEDIUM', 'Amount outlier (Z-Score) by type', 
$$SELECT txn_id FROM (SELECT txn_id, amount, AVG(amount) OVER (PARTITION BY type) as m, STDDEV(amount) OVER (PARTITION BY type) as s FROM dw.fact_transactions) t WHERE amount > m + 4 * s$$, true),

('DEST_VELOCITY', 'Anomaly', 'MEDIUM', 'High destination velocity', 
$$SELECT txn_id FROM (SELECT txn_id, COUNT(*) OVER (PARTITION BY name_dest ORDER BY step RANGE BETWEEN 3 PRECEDING AND CURRENT ROW) as c FROM dw.fact_transactions) t WHERE c > 10$$, true),

('ANOMALY_IFOREST', 'Anomaly', 'MEDIUM', 'Machine Learning anomaly score', 
$$SELECT txn_id FROM dw.txn_anomaly_score WHERE is_anomaly = true$$, false);
