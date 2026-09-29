-- Bank DQ Platform: Marts Layer
-- Reporting views for Power BI and stakeholder dashboards

-- 1. Rule Scorecard: pass/fail rates per rule per run
CREATE OR REPLACE VIEW mart.v_rule_scorecard AS
SELECT
    c.rule_code,
    c.dimension,
    c.severity,
    l.run_ts::date AS run_date,
    l.records_checked,
    l.records_failed,
    ROUND(100.0 * (1 - l.records_failed::numeric / NULLIF(l.records_checked, 0)), 3) AS pass_rate_pct
FROM dq.rule_run_log l
JOIN dq.rule_catalog c USING (rule_id);

-- 2. Exception Ageing: open exceptions by severity and age bucket
CREATE OR REPLACE VIEW mart.v_exception_ageing AS
SELECT
    c.severity,
    CASE
        WHEN now() - e.detected_at < interval '1 day'  THEN '0-1d'
        WHEN now() - e.detected_at < interval '7 days' THEN '1-7d'
        ELSE '7d+'
    END AS age_bucket,
    COUNT(*) AS open_exceptions
FROM dq.exceptions e
JOIN dq.rule_catalog c USING (rule_id)
WHERE e.status = 'OPEN'
GROUP BY 1, 2;

-- 3. Daily Control Report: aggregated by date, dimension, severity with SLA check
CREATE OR REPLACE VIEW mart.v_daily_control_report AS
SELECT
    l.run_ts::date AS run_date,
    c.dimension,
    c.severity,
    SUM(l.records_failed) AS failed,
    ROUND(AVG(100.0 * (1 - l.records_failed::numeric / NULLIF(l.records_checked, 0))), 3) AS avg_pass_rate_pct,
    BOOL_AND(
        (1 - l.records_failed::numeric / NULLIF(l.records_checked, 0)) >= 0.99
    ) AS sla_met
FROM dq.rule_run_log l
JOIN dq.rule_catalog c USING (rule_id)
GROUP BY 1, 2, 3;

-- 4. Exception Detail: drill-through view for Power BI
CREATE OR REPLACE VIEW mart.v_exception_detail AS
SELECT
    e.exception_id,
    c.rule_code,
    c.dimension,
    c.severity,
    e.detected_at,
    e.status,
    e.assigned_to,
    e.resolved_at,
    e.note,
    f.txn_id,
    f.step,
    f.txn_ts,
    f.type,
    f.amount,
    f.name_orig,
    f.name_dest,
    f.is_fraud,
    f.is_flagged_fraud
FROM dq.exceptions e
JOIN dq.rule_catalog c USING (rule_id)
JOIN dw.fact_transactions f ON e.txn_id = f.txn_id;

-- 5. Anomaly score table (created here, populated by Python anomaly_model.py)
CREATE TABLE IF NOT EXISTS dw.txn_anomaly_score (
    txn_id bigint,
    score double precision,
    is_anomaly boolean
);

-- 6. Anomaly Overview: for Power BI anomaly dashboard page
CREATE OR REPLACE VIEW mart.v_anomaly_overview AS
SELECT
    f.txn_id,
    f.txn_ts,
    f.type,
    f.amount,
    f.name_orig,
    f.name_dest,
    f.is_fraud,
    a.score AS anomaly_score,
    a.is_anomaly
FROM dw.fact_transactions f
JOIN dw.txn_anomaly_score a ON f.txn_id = a.txn_id;

-- 7. LLM/Template exception summaries storage
CREATE TABLE IF NOT EXISTS mart.exception_summaries (
    run_date date,
    summary text
);
