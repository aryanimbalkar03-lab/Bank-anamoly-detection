"""
exception_summary.py - Generate daily DQ exception summaries using Claude API.

Reads aggregated rule scorecard data and generates a plain-language summary
for non-technical stakeholders. Only aggregates go to the model (no raw data).

Design: SQL computes every number, the LLM only narrates.
Fallback: If no API key, generates a template-based summary.

Data source: PaySim (SYNTHETIC data for portfolio demonstration only)
"""
import os
import pandas as pd
from sqlalchemy import create_engine, text
import logging
from datetime import date

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:pw@localhost:5432/bankdq")

def get_scorecard_data(engine):
    """Fetch top failing rules from the latest run."""
    try:
        return pd.read_sql(text("""
            SELECT rule_code, dimension, severity, records_failed, pass_rate_pct
            FROM mart.v_rule_scorecard
            WHERE run_date = (SELECT MAX(run_ts::date) FROM dq.rule_run_log)
            ORDER BY records_failed DESC
            LIMIT 10
        """), engine.connect())
    except Exception as e:
        logger.error(f"Error fetching scorecard data: {e}")
        return pd.DataFrame()

def generate_llm_summary(rows_df):
    """Generate summary using Claude API."""
    try:
        import anthropic
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        
        prompt = (
            "You are a data operations analyst at a bank. Using ONLY the numbers below, "
            "write a 5-line executive summary for a non-technical manager covering: "
            "what failed, severity level, likely root cause, and recommended next action. "
            "Do not invent numbers. Be concise.\n\n"
            + rows_df.to_json(orient='records')
        )
        
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        logger.warning(f"LLM summary failed: {e}. Falling back to template.")
        return generate_template_summary(rows_df)

def generate_template_summary(rows_df):
    """Template-based fallback summary (no API dependency)."""
    if rows_df.empty:
        return "No rule failures detected in the latest run. All checks passed."
    
    lines = [f"Daily DQ Report - {date.today()}"]
    total_failed = rows_df['records_failed'].sum()
    high_sev = rows_df[rows_df['severity'] == 'HIGH']
    
    lines.append(f"Total exceptions across top rules: {total_failed:,}")
    
    if not high_sev.empty:
        lines.append(f"HIGH severity rules failing: {', '.join(high_sev['rule_code'].tolist())}")
    
    worst = rows_df.iloc[0]
    lines.append(f"Worst performing rule: {worst['rule_code']} "
                 f"({worst['dimension']}) with {worst['records_failed']:,} failures "
                 f"(pass rate: {worst['pass_rate_pct']}%)")
    
    lines.append("Recommended: Review HIGH-severity exceptions first, "
                 "investigate root cause in source data, and update remediation plan.")
    
    return "\n".join(lines)

def save_summary(engine, summary_text):
    """Save summary to mart.exception_summaries."""
    try:
        df = pd.DataFrame([{
            "run_date": date.today(),
            "summary": summary_text
        }])
        df.to_sql("exception_summaries", engine, schema="mart",
                  if_exists="append", index=False)
        logger.info("Summary saved to mart.exception_summaries")
    except Exception as e:
        logger.error(f"Error saving summary: {e}")

def main():
    engine = create_engine(DB_URL)
    
    logger.info("Fetching scorecard data...")
    rows = get_scorecard_data(engine)
    
    if os.getenv("ANTHROPIC_API_KEY"):
        logger.info("Generating LLM summary...")
        summary = generate_llm_summary(rows)
    else:
        logger.info("No API key found. Using template summary.")
        summary = generate_template_summary(rows)
    
    print("\n" + "="*60)
    print(summary)
    print("="*60 + "\n")
    
    save_summary(engine, summary)

if __name__ == '__main__':
    main()
