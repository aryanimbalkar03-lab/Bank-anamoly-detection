-- Bank DQ Platform: Run Rules Procedure

CREATE OR REPLACE PROCEDURE dq.run_all_rules() LANGUAGE plpgsql AS $$
DECLARE 
    r RECORD; 
    failed bigint; 
    total bigint;
BEGIN
    SELECT count(*) INTO total FROM dw.fact_transactions;
    
    FOR r IN SELECT * FROM dq.rule_catalog WHERE active LOOP
        EXECUTE format(
            'INSERT INTO dq.exceptions (rule_id, txn_id)
             SELECT %s, t.txn_id FROM (%s) t ON CONFLICT DO NOTHING', r.rule_id, r.rule_sql);
        
        GET DIAGNOSTICS failed = ROW_COUNT;
        
        INSERT INTO dq.rule_run_log (rule_id, records_checked, records_failed)
        VALUES (r.rule_id, total, failed);
    END LOOP;
END $$;

-- Validate detection against injected defects
/*
SELECT d.defect_type,
       COUNT(*) AS injected,
       COUNT(e.txn_id) AS caught,
       ROUND(100.0*COUNT(e.txn_id)/COUNT(*),1) AS recall_pct
FROM qa.injected_defects d
LEFT JOIN dq.exceptions e ON e.txn_id = d.txn_id
GROUP BY d.defect_type
ORDER BY d.defect_type;
*/
