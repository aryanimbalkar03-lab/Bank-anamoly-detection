-- Bank DQ Platform: Performance Indexes
-- Run this AFTER warehouse and rule catalog are populated.

-- ============================================================
-- Fact table indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_fact_dest_step ON dw.fact_transactions (name_dest, step);
CREATE INDEX IF NOT EXISTS idx_fact_type      ON dw.fact_transactions (type);
CREATE INDEX IF NOT EXISTS idx_fact_orig      ON dw.fact_transactions (name_orig);
CREATE INDEX IF NOT EXISTS idx_fact_fraud     ON dw.fact_transactions (is_fraud) WHERE is_fraud = 1;  -- partial index
CREATE INDEX IF NOT EXISTS idx_fact_step      ON dw.fact_transactions (step);

-- ============================================================
-- Exception table indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_exc_open    ON dq.exceptions (rule_id) WHERE status = 'OPEN';  -- partial index
CREATE INDEX IF NOT EXISTS idx_exc_txn     ON dq.exceptions (txn_id);
CREATE INDEX IF NOT EXISTS idx_exc_status  ON dq.exceptions (status);

-- ============================================================
-- Supporting table indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_stg_settlements_txn ON stg.settlements (txn_id);
CREATE INDEX IF NOT EXISTS idx_dim_customer_acct   ON dw.dim_customer (account_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_txn         ON dw.txn_anomaly_score (txn_id);

-- Update planner statistics
ANALYZE dw.fact_transactions;
ANALYZE dq.exceptions;
ANALYZE dq.rule_run_log;
ANALYZE stg.settlements;
ANALYZE dw.dim_customer;

-- ============================================================
-- EXPLAIN ANALYZE: Before/After Comparison
-- ============================================================
-- Run these queries BEFORE creating indexes, screenshot the plan,
-- then run AFTER indexes + ANALYZE and screenshot again.
-- Save screenshots to /docs/explain_before.png and /docs/explain_after.png
--
-- Query 1: Destination lookup with step range filter
/*
EXPLAIN (ANALYZE, BUFFERS)
SELECT type, COUNT(*) FROM dw.fact_transactions
WHERE name_dest = 'C1234567890' AND step BETWEEN 100 AND 200
GROUP BY type;
*/
--
-- Query 2: Rule execution timing
/*
EXPLAIN (ANALYZE, BUFFERS)
SELECT txn_id FROM dw.fact_transactions
WHERE amount IS NOT NULL
  AND ABS(newbalance_orig -
    CASE WHEN type='CASH_IN' THEN oldbalance_org+amount
         ELSE oldbalance_org-amount END) > 0.01;
*/
--
-- Before indexes: expect Seq Scan on fact_transactions
-- After indexes:  expect Index Scan / Bitmap Heap Scan, reduced execution time
--
-- Also time the rule runner:
-- \timing on
-- CALL dq.run_all_rules();
-- Report actual before/after times in README.
