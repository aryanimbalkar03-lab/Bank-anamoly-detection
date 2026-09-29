"""
gen_feeds.py - Generate supplementary feeds for the Bank DQ Platform.

Generates:
1. customer_master.csv - One row per distinct C-prefixed account with deliberate defects
2. settlements.csv - Settlement records for transactions with deliberate defects

Data source: PaySim (SYNTHETIC data for portfolio demonstration only)
"""
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:pw@localhost:5432/bankdq")

def generate_customer_master(engine, seed=42):
    """Generate customer_master with ~0.5% duplicate rows and ~0.5% orphans."""
    rng = np.random.default_rng(seed)
    
    # Get all distinct C-prefixed accounts from staged transactions
    accounts = pd.read_sql(text("""
        SELECT DISTINCT account_id FROM (
            SELECT name_orig AS account_id FROM stg.transactions WHERE name_orig LIKE 'C%'
            UNION
            SELECT name_dest AS account_id FROM stg.transactions WHERE name_dest LIKE 'C%'
        ) a
    """), engine.connect())
    
    n = len(accounts)
    if n == 0:
        logger.warning("No C-prefixed accounts found in stg.transactions.")
        return pd.DataFrame()

    segments = rng.choice(['RETAIL', 'PREMIUM', 'CORPORATE', 'SME'], size=n, p=[0.5, 0.2, 0.15, 0.15])
    kyc_statuses = rng.choice(['VERIFIED', 'PENDING', 'EXPIRED', 'REJECTED'], size=n, p=[0.7, 0.15, 0.1, 0.05])
    countries = rng.choice(['US', 'UK', 'IN', 'DE', 'SG', 'AE', 'JP', 'BR'], size=n, p=[0.3, 0.15, 0.15, 0.1, 0.1, 0.08, 0.07, 0.05])
    
    # Generate random opened dates between 2020-2025
    base_date = pd.Timestamp('2020-01-01')
    days_offset = rng.integers(0, 365*5, size=n)
    opened_dates = [base_date + pd.Timedelta(days=int(d)) for d in days_offset]
    
    df = accounts.copy()
    df['segment'] = segments
    df['kyc_status'] = kyc_statuses  
    df['country'] = countries
    df['opened_date'] = opened_dates
    
    # Remove ~0.5% of accounts to create orphans
    n_remove = int(n * 0.005)
    remove_idx = rng.choice(df.index, size=n_remove, replace=False)
    df_orphaned = df.drop(remove_idx)
    
    # Add ~0.5% duplicate rows
    n_dup = int(len(df_orphaned) * 0.005)
    if n_dup > 0:
        dup_idx = rng.choice(df_orphaned.index, size=n_dup, replace=False)
        df_with_dups = pd.concat([df_orphaned, df_orphaned.loc[dup_idx]], ignore_index=True)
    else:
        df_with_dups = df_orphaned
    
    return df_with_dups

def generate_settlements(engine, seed=42):
    """Generate settlements with ~1% missing, ~0.5% amount mismatch, ~1% late."""
    rng = np.random.default_rng(seed)
    
    txns = pd.read_sql(text("""
        SELECT txn_id, amount, step,
               (TIMESTAMP '2026-01-01' + step * INTERVAL '1 hour')::date AS txn_date
        FROM stg.transactions
        WHERE amount IS NOT NULL AND amount > 0
    """), engine.connect())
    
    n = len(txns)
    if n == 0:
        logger.warning("No transactions found in stg.transactions.")
        return pd.DataFrame()

    # Remove ~1% to create missing settlements  
    keep_mask = rng.random(n) >= 0.01
    settlements = txns[keep_mask].copy()
    
    m = len(settlements)
    settlements['settlement_ref'] = ['SET' + str(i).zfill(10) for i in range(m)]
    settlements['settled_amount'] = settlements['amount']
    
    # ~0.5% amount mismatch
    mismatch_mask = rng.random(m) < 0.005
    settlements.loc[mismatch_mask, 'settled_amount'] = (
        settlements.loc[mismatch_mask, 'amount'] * rng.uniform(0.95, 1.05, mismatch_mask.sum())
    ).round(2)
    
    # Settlement date: normally txn_date + 1 day, but ~1% are 3+ days late
    settlements['settlement_date'] = pd.to_datetime(settlements['txn_date']) + pd.Timedelta(days=1)
    late_mask = rng.random(m) < 0.01
    late_days = rng.integers(3, 8, size=late_mask.sum())
    
    settlements.loc[late_mask, 'settlement_date'] = (
        pd.to_datetime(settlements.loc[late_mask, 'txn_date']) + pd.to_timedelta(late_days, unit='D')
    )
    
    return settlements[['settlement_ref', 'txn_id', 'settled_amount', 'settlement_date']]

def main():
    engine = create_engine(DB_URL)
    os.makedirs('data', exist_ok=True)
    
    logger.info("Generating customer_master...")
    customers = generate_customer_master(engine)
    if not customers.empty:
        customers.to_csv('data/customer_master.csv', index=False)
        logger.info(f"  -> {len(customers)} rows (including duplicates)")
        
        # Also load into raw schema
        customers.to_sql('customer_master', engine, schema='raw', if_exists='replace', index=False)
        logger.info("  -> Loaded into raw.customer_master")
    
    logger.info("Generating settlements...")
    settlements = generate_settlements(engine)
    if not settlements.empty:
        settlements.to_csv('data/settlements.csv', index=False)
        logger.info(f"  -> {len(settlements)} rows")
        
        # Also load into raw schema
        settlements.to_sql('settlements', engine, schema='raw', if_exists='replace', index=False)
        logger.info("  -> Loaded into raw.settlements")
    
    logger.info("Done.")

if __name__ == '__main__':
    main()
