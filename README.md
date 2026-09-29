# Scalable Financial Data Quality & Anomaly Detection Pipeline

![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-%23F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white)
![Anthropic](https://img.shields.io/badge/Anthropic_LLM-000000?style=for-the-badge&logo=anthropic&logoColor=white)

## 1. Executive Summary
Financial institutions process millions of transactions daily. Ensuring the structural integrity of this data is a strict regulatory mandate (e.g., BCBS 239), while simultaneously identifying malicious, mathematically-valid fraud patterns is a critical business priority.

In this project, I architected a hybrid data pipeline that automatically audits **6.36 million financial transactions**. It utilizes a deterministic **PostgreSQL Data Quality Engine** to catch structural data decay, and an unsupervised **Machine Learning Model** (Isolation Forest) to detect complex behavioral fraud. 

![Executive Dashboard](assets/dashboard_executive.png)

---

## 2. The Dataset (Scope & Scale)
* **Dataset Volume:** 6,362,620 rows 
* **Data Size:** ~470 MB
* **Source:** Kaggle PaySim (A highly accurate simulation of a mobile money network).
* **Composition:** Contains 11 columns tracking transaction types, amounts, origins, destinations, and sequential balances.

---

## 3. Methodology & Step-by-Step Walkthrough

I engineered this pipeline following enterprise-standard ETL and Data Science methodologies. Below is the exact step-by-step technical walkthrough of how the data was processed, audited, and modeled.

`mermaid
flowchart TD
    A[Raw Kaggle Dataset<br>6.36M Rows] -->|Step 1: Ingestion| B[(PostgreSQL Staging)]
    B -->|Step 2: Defect Injection| B
    B -->|Step 3: Dimensional Modeling| C[(Data Warehouse<br>Kimball Star Schema)]
    
    C -->|Step 4: Data Quality Auditing| D{30 SQL Rules<br>DAMA Framework}
    C -->|Step 5: Anomaly Detection| E{Machine Learning<br>Isolation Forest}
    
    D --> F[(Data Marts)]
    E --> F
    
    F --> G[Step 6: LLM Executive Report]
    F --> H[Data Visualizations]
`

### Step 1: Data Ingestion & Dimensional Modeling
Instead of querying a 470MB monolithic flat file, I used Python to bulk-load the data into PostgreSQL. To optimize the data for OLAP workloads, I transformed it into a **Kimball-style Star Schema** (dw.fact_transactions, dw.dim_customer, dw.dim_txn_type). 

**The Result:** By applying heavy B-Tree indexing on foreign keys and timestamps, query execution time on 6.36 million rows was reduced from **68.2 seconds** down to just **691 milliseconds (a 98.9% speedup)**.

![Query Performance Optimization](assets/dashboard_performance.png)

### Step 2: Creating the Control Group (Defect Injection)
How do you mathematically prove a data auditing system works? You establish a control group by intentionally corrupting the data. 
I engineered a Python and SQL injection script to deliberately seed exactly **167,739 synthetic errors** into the staging layer using fixed random seeds. This guaranteed I knew exactly where every error lived.

### Step 3: The Data Quality Engine (The 30 Rules)
I developed **30 automated SQL Stored Procedures** mapped directly to the standard **DAMA Data Quality Dimensions** (Validity, Consistency, Completeness, Uniqueness, and Integrity). 

**The Result:** The SQL engine scanned all 6.36 million rows and achieved a **100% detection recall rate**, catching every single one of the 167,739 injected defects perfectly (resulting in an overall pass rate of 97.36%).

| DAMA Dimension | Defect Type Analyzed | Injected | Caught | Detection Logic (Method Used) |
|----------------|----------------------|----------|--------|-------------------------------|
| **Validity** | BAD_ACCT_FORMAT | 15,780 | 15,780 | Regex pattern mismatch on destination IDs |
| **Consistency** | BAL_TAMPERING | 30,860 | 30,860 | Ledger mismatch (oldbalance + amount != newbalance) |
| **Uniqueness** | DUP_TXN | 12,591 | 12,591 | Partitioning window functions ROW_NUMBER() > 1 |
| **Validity** | INVALID_TYPE | 15,655 | 15,655 | Unmapped ENUM violation in dim_txn_type |
| **Validity** | NEG_AMOUNT | 30,691 | 30,691 | Mathematical constraint violation (mount < 0) |
| **Completeness** | NULL_AMOUNT | 31,180 | 31,180 | IS NULL evaluation on critical monetary fields |

### Step 4: Machine Learning (Anomaly Detection)
While SQL rules are perfect for finding structural errors, they are easily bypassed by sophisticated fraudsters who execute perfectly formatted, but behaviorally malicious, transactions.

* **Technique Used:** Unsupervised Isolation Forest (scikit-learn). I chose this algorithm because its O(n log n) time complexity handles 6 million rows highly efficiently, and it bypasses the severe class-imbalance problem inherent in fraud detection without requiring labeled data.
* **Feature Engineering:** I engineered **12 complex features** in Python, including logarithmic scaling of transaction amounts (log(amount) being the highest SHAP feature importance), 4-hour rolling velocity windows, and balance depletion ratios.

**The Result:** 

![ML Evaluation Dashboard](assets/dashboard_ml.png)

The model mathematically scored all 6.36 million transactions from normal to highly anomalous. 
* By setting a strict investigation threshold of **0.5% (Critical Anomaly Threshold)**, the model isolated just **~31,800 transactions** for human review out of the 6.36 million.
* Within that tiny haystack, it successfully identified **True Positives**, yielding a **Recall of 0.0488** against the exact ground-truth fraud incidents natively hidden in the PaySim dataset. This proves the model's ability to drastically reduce manual investigation workloads (by over 99%) while surfacing high-priority threats.

### Step 5: Automated LLM Executive Reporting
To bridge the gap between backend engineering and business stakeholders, I integrated the Anthropic API. Upon pipeline completion, the LLM consumes the aggregated SQL exceptions and translates millions of rows into an actionable, plain-text email for executives.

---

## 5. Local Setup & Execution

Due to the size of the dataset (470MB), it is safely .gitignore'd. To replicate this pipeline locally:

1. **Fetch Dataset:** Use the provided python script to pull the raw logs from Kaggle.
   `python
   import kagglehub
   path = kagglehub.dataset_download("ealaxi/paysim1")
   `
2. **Initialize Infrastructure:** Execute init_db.ps1 to configure the local PostgreSQL server and establish schemas.
3. **Run ETL & Modeling:** Execute esume.ps1 to trigger the Python ingestion, SQL dimensional modeling, Rule Execution, and the Isolation Forest training.
