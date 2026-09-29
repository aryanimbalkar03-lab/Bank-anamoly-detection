"""
test_rules.py - Unit tests for DQ rule engine.

Creates a miniature test schema, inserts rows with known defects,
runs the DQ rules, and asserts that each defect is caught.

Data: All test data is synthetic and self-contained (PaySim).
"""
import pytest
import os
from sqlalchemy import create_engine, text

DB_URL = os.getenv("TEST_DATABASE_URL", 
                   os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:pw@localhost:5432/bankdq_test"))

@pytest.fixture(scope='session')
def engine():
    eng = create_engine(DB_URL)
    yield eng
    eng.dispose()

@pytest.fixture(scope='session', autouse=True)
def setup_test_db(engine):
    """Create test schemas and tables, insert test data."""
    with engine.begin() as conn:
        # Create schemas
        for schema in ['dw', 'dq', 'stg', 'mart']:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        
        # Create minimal fact_transactions
        conn.execute(text("""
            DROP TABLE IF EXISTS dw.fact_transactions CASCADE;
            CREATE TABLE dw.fact_transactions (
                txn_id bigserial PRIMARY KEY,
                step int, type text, amount numeric(18,2),
                name_orig text, oldbalance_org numeric(18,2),
                newbalance_orig numeric(18,2),
                name_dest text, oldbalance_dest numeric(18,2),
                newbalance_dest numeric(18,2),
                is_fraud smallint, is_flagged_fraud smallint,
                txn_ts timestamp DEFAULT TIMESTAMP '2026-01-01'
            )
        """))
        
        # Insert test rows
        conn.execute(text("""
            INSERT INTO dw.fact_transactions 
            (step, type, amount, name_orig, oldbalance_org, newbalance_orig,
             name_dest, oldbalance_dest, newbalance_dest, is_fraud, is_flagged_fraud) VALUES
            -- Clean row
            (1, 'PAYMENT', 1000.00, 'C100', 5000.00, 4000.00, 'M200', 0, 1000.00, 0, 0),
            -- NULL amount
            (2, 'TRANSFER', NULL, 'C101', 3000.00, 3000.00, 'C102', 0, 0, 0, 0),
            -- Negative amount
            (3, 'CASH_OUT', -500.00, 'C103', 2000.00, 2500.00, 'C104', 0, 500.00, 0, 0),
            -- Duplicate (same business key as row 1 but different txn_id)
            (1, 'PAYMENT', 1000.00, 'C100', 5000.00, 4000.00, 'M200', 0, 1000.00, 0, 0),
            -- Bad account format
            (5, 'DEBIT', 200.00, 'INVALID_999', 1000.00, 800.00, 'C106', 0, 200.00, 0, 0),
            -- Balance mismatch origin
            (6, 'CASH_OUT', 100.00, 'C107', 1000.00, 500.00, 'C108', 0, 100.00, 0, 0),
            -- Self transfer
            (7, 'TRANSFER', 300.00, 'C109', 1000.00, 700.00, 'C109', 0, 300.00, 0, 0),
            -- Payment to non-merchant
            (8, 'PAYMENT', 400.00, 'C110', 2000.00, 1600.00, 'C111', 0, 400.00, 0, 0),
            -- Invalid type
            (9, 'WIRE', 250.00, 'C112', 1000.00, 750.00, 'C113', 0, 250.00, 0, 0),
            -- Zero amount
            (10, 'TRANSFER', 0.00, 'C114', 1000.00, 1000.00, 'C115', 0, 0, 0, 0)
        """))
        
        # Create rule catalog and exceptions tables
        conn.execute(text("""
            DROP TABLE IF EXISTS dq.exceptions CASCADE;
            DROP TABLE IF EXISTS dq.rule_run_log CASCADE;
            DROP TABLE IF EXISTS dq.rule_catalog CASCADE;
            
            CREATE TABLE dq.rule_catalog (
                rule_id serial PRIMARY KEY, rule_code text UNIQUE, dimension text,
                severity text, description text, rule_sql text, active boolean DEFAULT true);
            
            CREATE TABLE dq.exceptions (
                exception_id bigserial PRIMARY KEY, rule_id int REFERENCES dq.rule_catalog,
                txn_id bigint, detected_at timestamptz DEFAULT now(),
                status text DEFAULT 'OPEN', assigned_to text, resolved_at timestamptz, note text,
                UNIQUE (rule_id, txn_id));
            
            CREATE TABLE dq.rule_run_log (
                run_id bigserial PRIMARY KEY, rule_id int, run_ts timestamptz DEFAULT now(),
                records_checked bigint, records_failed bigint);
        """))
        
        # Insert test rules
        conn.execute(text("""
            INSERT INTO dq.rule_catalog (rule_code, dimension, severity, description, rule_sql) VALUES
            ('NULL_AMOUNT', 'Completeness', 'HIGH', 'Amount is null',
             'SELECT txn_id FROM dw.fact_transactions WHERE amount IS NULL'),
            ('NEG_AMOUNT', 'Validity', 'HIGH', 'Amount is negative',
             'SELECT txn_id FROM dw.fact_transactions WHERE amount < 0'),
            ('ZERO_AMOUNT', 'Validity', 'MEDIUM', 'Amount is zero',
             'SELECT txn_id FROM dw.fact_transactions WHERE amount = 0'),
            ('INVALID_TYPE', 'Validity', 'HIGH', 'Invalid transaction type',
             'SELECT txn_id FROM dw.fact_transactions WHERE type NOT IN (''CASH_IN'',''CASH_OUT'',''DEBIT'',''PAYMENT'',''TRANSFER'')'),
            ('BAD_ACCT_FORMAT', 'Validity', 'HIGH', 'Bad account format',
             'SELECT txn_id FROM dw.fact_transactions WHERE name_orig !~ ''^[CM][0-9]+$'' OR name_dest !~ ''^[CM][0-9]+$'''),
            ('SELF_TRANSFER', 'Consistency', 'MEDIUM', 'Self transfer',
             'SELECT txn_id FROM dw.fact_transactions WHERE name_orig = name_dest'),
            ('PAYMENT_DEST_NOT_MERCHANT', 'Consistency', 'MEDIUM', 'Payment to non-merchant',
             'SELECT txn_id FROM dw.fact_transactions WHERE type = ''PAYMENT'' AND name_dest NOT LIKE ''M%'''),
            ('DUP_BUSINESS_KEY', 'Uniqueness', 'MEDIUM', 'Duplicate business key',
             'SELECT txn_id FROM (SELECT txn_id, ROW_NUMBER() OVER (PARTITION BY name_orig,name_dest,amount,step,type ORDER BY txn_id) rn FROM dw.fact_transactions) x WHERE rn > 1')
        """))
        
        # Create and run the procedure
        conn.execute(text("""
            CREATE OR REPLACE PROCEDURE dq.run_all_rules() LANGUAGE plpgsql AS $proc$
            DECLARE r RECORD; failed bigint; total bigint;
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
            END $proc$;
        """))
        
        conn.execute(text("CALL dq.run_all_rules()"))
    
    yield
    
    # Cleanup
    with engine.begin() as conn:
        for schema in ['dq', 'dw', 'stg', 'mart']:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

def get_exception_count(engine, rule_code):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FROM dq.exceptions e
            JOIN dq.rule_catalog c ON e.rule_id = c.rule_id
            WHERE c.rule_code = :code
        """), {"code": rule_code})
        return result.scalar()

def test_null_amount_detected(engine):
    assert get_exception_count(engine, 'NULL_AMOUNT') >= 1

def test_neg_amount_detected(engine):
    assert get_exception_count(engine, 'NEG_AMOUNT') >= 1

def test_zero_amount_detected(engine):
    assert get_exception_count(engine, 'ZERO_AMOUNT') >= 1

def test_invalid_type_detected(engine):
    assert get_exception_count(engine, 'INVALID_TYPE') >= 1

def test_bad_acct_format_detected(engine):
    assert get_exception_count(engine, 'BAD_ACCT_FORMAT') >= 1

def test_self_transfer_detected(engine):
    assert get_exception_count(engine, 'SELF_TRANSFER') >= 1

def test_payment_dest_not_merchant_detected(engine):
    assert get_exception_count(engine, 'PAYMENT_DEST_NOT_MERCHANT') >= 1

def test_dup_business_key_detected(engine):
    assert get_exception_count(engine, 'DUP_BUSINESS_KEY') >= 1

def test_clean_row_not_flagged(engine):
    """The clean row (txn_id=1) should not appear in NULL_AMOUNT or NEG_AMOUNT."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FROM dq.exceptions e
            JOIN dq.rule_catalog c ON e.rule_id = c.rule_id
            WHERE e.txn_id = 1 AND c.rule_code IN ('NULL_AMOUNT', 'NEG_AMOUNT')
        """))
        assert result.scalar() == 0

def test_rule_run_log_populated(engine):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM dq.rule_run_log"))
        assert result.scalar() >= 8  # At least 8 rules were run
