"""
run_pipeline.py - End-to-end pipeline orchestrator for Bank DQ Platform.

Executes the full pipeline:
1. Create schemas (01_schemas.sql)
2. Create and populate staging tables (02_staging.sql) 
3. Inject defects (03_inject_defects.sql)
4. Build warehouse star schema (04_warehouse.sql)
5. Load rule catalog (05_rule_catalog.sql)
6. Create rule runner procedure (06_run_rules.sql)
7. Create mart views (07_marts.sql)
8. Create indexes (08_indexes.sql)
9. Run all DQ rules (CALL dq.run_all_rules())
10. Run anomaly model (anomaly_model.py)
11. Generate exception summary (exception_summary.py)

Usage:
    python run_pipeline.py [--skip-load] [--skip-anomaly] [--skip-summary]

Data source: PaySim (SYNTHETIC data for portfolio demonstration only)
"""
import os
import time
import argparse
import logging
from pathlib import Path
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:pw@localhost:5432/bankdq")
SQL_DIR = Path(__file__).parent.parent / "sql"

def run_sql_file(engine, filepath):
    """Execute a SQL file against the database using a raw connection."""
    logger.info(f"Executing {filepath.name}...")
    start = time.time()
    
    sql = filepath.read_text(encoding='utf-8')
    
    try:
        # Using raw connection to execute multi-statement SQL with psycopg2 natively
        raw_conn = engine.raw_connection()
        try:
            with raw_conn.cursor() as cursor:
                cursor.execute(sql)
            raw_conn.commit()
        finally:
            raw_conn.close()
        
        elapsed = time.time() - start
        logger.info(f"  Completed {filepath.name} in {elapsed:.1f}s")
    except Exception as e:
        logger.error(f"Failed to execute {filepath.name}: {e}")
        raise

def run_procedure(engine, proc_name):
    """Call a stored procedure."""
    logger.info(f"Calling {proc_name}...")
    start = time.time()
    
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CALL {proc_name}"))
        
        elapsed = time.time() - start
        logger.info(f"  {proc_name} completed in {elapsed:.1f}s")
    except Exception as e:
        logger.error(f"Failed to execute procedure {proc_name}: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Bank DQ Platform Pipeline')
    parser.add_argument('--skip-load', action='store_true', help='Skip data loading steps')
    parser.add_argument('--skip-anomaly', action='store_true', help='Skip anomaly model')
    parser.add_argument('--skip-summary', action='store_true', help='Skip LLM summary')
    args = parser.parse_args()
    
    engine = create_engine(DB_URL)
    
    pipeline_start = time.time()
    logger.info("="*60)
    logger.info("Bank DQ Platform - Pipeline Execution")
    logger.info("="*60)
    
    # SQL pipeline
    sql_files = [
        '01_schemas.sql',
        '02_staging.sql',
        '03_inject_defects.sql',
        '04_warehouse.sql',
        '05_rule_catalog.sql',
        '06_run_rules.sql',
        '07_marts.sql',
        '08_indexes.sql',
    ]
    
    if args.skip_load:
        sql_files = [f for f in sql_files if f not in ('02_staging.sql', '03_inject_defects.sql', '04_warehouse.sql')]
    
    for f in sql_files:
        filepath = SQL_DIR / f
        if filepath.exists():
            run_sql_file(engine, filepath)
        else:
            logger.warning(f"SQL file not found: {filepath}")
    
    # Run rules
    run_procedure(engine, 'dq.run_all_rules()')
    
    # Anomaly model
    if not args.skip_anomaly:
        try:
            import anomaly_model
            anomaly_model.main()
        except Exception as e:
            logger.error(f"Anomaly model failed: {e}")
    
    # Exception summary
    if not args.skip_summary:
        try:
            import exception_summary
            exception_summary.main()
        except Exception as e:
            logger.error(f"Exception summary failed: {e}")
    
    total = time.time() - pipeline_start
    logger.info(f"\nPipeline completed in {total:.1f}s")

if __name__ == '__main__':
    main()
