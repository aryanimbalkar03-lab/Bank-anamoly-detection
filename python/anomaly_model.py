"""
anomaly_model.py - Isolation Forest anomaly detection for bank transactions.

Trains an Isolation Forest model on transaction features and writes
scores back to dw.txn_anomaly_score for the DQ rule engine.

Data source: PaySim (SYNTHETIC data for portfolio demonstration only)
"""
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:pw@localhost:5432/bankdq")

def load_data(engine):
    """Load transaction data from the data warehouse."""
    logger.info("Loading transaction data from dw.fact_transactions...")
    try:
        df = pd.read_sql(text("""
            SELECT txn_id, type, amount, oldbalance_org, newbalance_orig,
                   oldbalance_dest, newbalance_dest, is_fraud
            FROM dw.fact_transactions
        """), engine.connect())
        logger.info(f"Loaded {len(df):,} transactions")
        return df
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise

def engineer_features(df):
    """Create features for anomaly detection."""
    df = df.dropna(subset=["amount"]).copy()
    df["amount"] = df["amount"].clip(lower=0)
    df = df.fillna(0)
    
    # Engineered features
    df["err_orig"] = df.oldbalance_org - df.newbalance_orig - df.amount
    df["err_dest"] = df.newbalance_dest - df.oldbalance_dest - df.amount
    df["log_amt"] = np.log1p(df.amount)
    df["bal_ratio_orig"] = np.where(df.oldbalance_org > 0,
                                     df.amount / df.oldbalance_org, 0)
    df["bal_ratio_orig"] = df["bal_ratio_orig"].clip(-10, 10)
    
    return df

def train_model(df):
    """Train Isolation Forest and compute anomaly scores."""
    if df.empty:
        logger.warning("Empty dataframe, cannot train model.")
        return df, None

    feature_cols = ["log_amt", "err_orig", "err_dest", "oldbalance_org", 
                    "oldbalance_dest", "bal_ratio_orig"]
    
    X = pd.get_dummies(df[["type"] + feature_cols], columns=["type"])
    
    logger.info(f"Training Isolation Forest on {X.shape[0]:,} rows, {X.shape[1]} features...")
    model = IsolationForest(
        n_estimators=200,
        contamination=0.005,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X)
    
    df["score"] = -model.score_samples(X)
    df["is_anomaly"] = model.predict(X) == -1
    
    logger.info(f"Anomalies flagged: {df.is_anomaly.sum():,} ({df.is_anomaly.mean()*100:.2f}%)")
    return df, model

def evaluate(df):
    """Evaluate anomaly detection against PaySim's fraud labels."""
    if df.empty or "score" not in df.columns:
        return {}

    k = max(1, int(len(df) * 0.005))
    top = df.nlargest(k, "score")
    
    precision = round(top.is_fraud.mean(), 4)
    recall = round(top.is_fraud.sum() / max(df.is_fraud.sum(), 1), 4)
    
    logger.info(f"precision@0.5%: {precision}")
    logger.info(f"recall@0.5%:    {recall}")
    logger.info(f"Total fraud in data: {df.is_fraud.sum():,}")
    logger.info(f"Fraud in top-k: {int(top.is_fraud.sum()):,}")
    
    return {"precision_at_0.5pct": precision, "recall_at_0.5pct": recall}

def save_scores(df, engine):
    """Write anomaly scores to dw.txn_anomaly_score."""
    if df.empty or "score" not in df.columns:
        return

    logger.info("Writing anomaly scores to dw.txn_anomaly_score...")
    try:
        result = df[["txn_id", "score", "is_anomaly"]].copy()
        result.to_sql(
            "txn_anomaly_score", engine, schema="dw",
            if_exists="replace", index=False, chunksize=50000
        )
        logger.info("Done writing scores.")
    except Exception as e:
        logger.error(f"Error saving scores: {e}")
        raise

def insert_anomaly_exceptions(engine):
    """Insert Isolation Forest anomalies into dq.exceptions."""
    logger.info("Inserting anomaly exceptions...")
    try:
        with engine.connect() as conn:
            # First activate the ANOMALY_IFOREST rule
            conn.execute(text("UPDATE dq.rule_catalog SET active = true WHERE rule_code = 'ANOMALY_IFOREST'"))
            
            # Insert exceptions
            conn.execute(text("""
                INSERT INTO dq.exceptions (rule_id, txn_id)
                SELECT rc.rule_id, a.txn_id
                FROM dw.txn_anomaly_score a
                CROSS JOIN dq.rule_catalog rc
                WHERE rc.rule_code = 'ANOMALY_IFOREST'
                  AND a.is_anomaly = true
                ON CONFLICT DO NOTHING
            """))
            conn.commit()
        logger.info("Anomaly exceptions inserted.")
    except Exception as e:
        logger.error(f"Error inserting exceptions: {e}")
        raise

def main():
    engine = create_engine(DB_URL)
    
    df = load_data(engine)
    df = engineer_features(df)
    df, model = train_model(df)
    metrics = evaluate(df)
    save_scores(df, engine)
    insert_anomaly_exceptions(engine)
    
    return metrics

if __name__ == '__main__':
    main()
