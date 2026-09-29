# Power BI Dashboard

The Power BI dashboard connects to the PostgreSQL database and visualizes the DQ metrics.

## Setup

1. Install the [Npgsql provider](https://github.com/npgsql/npgsql) if prompted
2. Connect to PostgreSQL: `localhost:5432/bankdq`
3. Import only `mart.*` views (not the 6M-row fact table)

## Dashboard Pages

| Page | Contents |
|------|----------|
| 1. Control Summary | KPI cards (pass rate, open exceptions, HIGH-severity, SLA breaches), trend line, exceptions by dimension |
| 2. Rule Drill-down | Rule × date matrix, severity slicer, drill-through to transaction-level |
| 3. Anomaly View | Score distribution, top 50 anomalies, split by transaction type |
| 4. AI Summary | Card showing latest `mart.exception_summaries` text |

## Key DAX Measures

```dax
Pass Rate % = 1 - DIVIDE(SUM(v_rule_scorecard[records_failed]), SUM(v_rule_scorecard[records_checked]))

Open HIGH = CALCULATE(SUM(v_exception_ageing[open_exceptions]), v_exception_ageing[severity] = "HIGH")

SLA Met % = DIVIDE(
    COUNTROWS(FILTER(v_daily_control_report, v_daily_control_report[sla_met] = TRUE())),
    COUNTROWS(v_daily_control_report)
)
```

> **Note**: Power BI Desktop is Windows-only. On Mac, use a Windows VM or export mart views as CSV for Tableau Public.
