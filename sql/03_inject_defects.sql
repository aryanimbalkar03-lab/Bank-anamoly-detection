-- Bank DQ Platform: Inject Defects for QA

SELECT setseed(0.42);

CREATE TABLE IF NOT EXISTS qa.injected_defects (
    txn_id bigint,
    defect_type text
);

TRUNCATE TABLE qa.injected_defects;

WITH d1 AS (
    UPDATE stg.transactions 
    SET amount = NULL 
    WHERE random() < 0.002 
    RETURNING txn_id, 'NULL_AMOUNT' AS defect_type
),
d2 AS (
    UPDATE stg.transactions 
    SET amount = -amount 
    WHERE random() < 0.002 AND amount > 0 AND txn_id NOT IN (SELECT txn_id FROM d1)
    RETURNING txn_id, 'NEG_AMOUNT' AS defect_type
),
d3 AS (
    INSERT INTO stg.transactions (
        step, type, amount, name_orig, oldbalance_org, newbalance_orig, 
        name_dest, oldbalance_dest, newbalance_dest, is_fraud, is_flagged_fraud
    )
    SELECT 
        step, type, amount, name_orig, oldbalance_org, newbalance_orig, 
        name_dest, oldbalance_dest, newbalance_dest, is_fraud, is_flagged_fraud
    FROM stg.transactions 
    WHERE random() < 0.002 
    RETURNING txn_id, 'DUP_TXN' AS defect_type
),
d4 AS (
    UPDATE stg.transactions 
    SET name_orig = 'INVALID_' || txn_id 
    WHERE random() < 0.001 AND txn_id NOT IN (SELECT txn_id FROM d1 UNION ALL SELECT txn_id FROM d2)
    RETURNING txn_id, 'BAD_ACCT_FORMAT' AS defect_type
),
d5 AS (
    UPDATE stg.transactions 
    SET type = 'WIRE' 
    WHERE random() < 0.001 AND txn_id NOT IN (SELECT txn_id FROM d1 UNION ALL SELECT txn_id FROM d2 UNION ALL SELECT txn_id FROM d4)
    RETURNING txn_id, 'INVALID_TYPE' AS defect_type
),
d6 AS (
    UPDATE stg.transactions 
    SET newbalance_orig = newbalance_orig * 1.5 
    WHERE random() < 0.002 AND txn_id NOT IN (SELECT txn_id FROM d1 UNION ALL SELECT txn_id FROM d2 UNION ALL SELECT txn_id FROM d4 UNION ALL SELECT txn_id FROM d5)
    RETURNING txn_id, 'BAL_TAMPERING' AS defect_type
),
d7 AS (
    UPDATE stg.transactions 
    SET step = -1 
    WHERE random() < 0.001 AND txn_id NOT IN (SELECT txn_id FROM d1 UNION ALL SELECT txn_id FROM d2 UNION ALL SELECT txn_id FROM d4 UNION ALL SELECT txn_id FROM d5 UNION ALL SELECT txn_id FROM d6)
    RETURNING txn_id, 'STEP_OUT_OF_RANGE' AS defect_type
),
d8 AS (
    UPDATE stg.transactions 
    SET amount = 0 
    WHERE random() < 0.001 AND amount > 0 AND txn_id NOT IN (SELECT txn_id FROM d1 UNION ALL SELECT txn_id FROM d2 UNION ALL SELECT txn_id FROM d4 UNION ALL SELECT txn_id FROM d5 UNION ALL SELECT txn_id FROM d6 UNION ALL SELECT txn_id FROM d7)
    RETURNING txn_id, 'ZERO_AMOUNT' AS defect_type
)
INSERT INTO qa.injected_defects (txn_id, defect_type)
SELECT txn_id, defect_type FROM d1
UNION ALL SELECT txn_id, defect_type FROM d2
UNION ALL SELECT txn_id, defect_type FROM d3
UNION ALL SELECT txn_id, defect_type FROM d4
UNION ALL SELECT txn_id, defect_type FROM d5
UNION ALL SELECT txn_id, defect_type FROM d6
UNION ALL SELECT txn_id, defect_type FROM d7
UNION ALL SELECT txn_id, defect_type FROM d8;
