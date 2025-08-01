# Portfolio Reconciliation Script (NAV Investigation)

This project simulates the core task of a Risk or Operations Analyst: reconciling a fund's internal portfolio holdings against a report from an external Fund Administrator to identify the sources of a Net Asset Value (NAV) discrepancy.

The script is designed to be a robust, automated solution that systematically detects and classifies different types of breaks.

---
## Objective

The goal is to write a Python function that takes two portfolio dataframes (internal system vs. administrator) and returns a clean summary of all discrepancies, classified by type. This simulates a real-world scenario where a Risk Manager must quickly and accurately investigate a NAV break.

---
## Key Features & Skills Demonstrated

-   **Systematic Reconciliation Process:** The script follows a professional workflow, first checking for structural breaks (missing/extra positions) and then for quantitative breaks (price/quantity mismatches).
-   **Advanced Pandas Usage:**
    -   `pd.merge` with `how='outer'` and `indicator=True` to robustly identify structural differences between two datasets.
    -   Data cleaning and consolidation of merged dataframes using `.fillna()`.
    -   Vectorized conditional logic with `np.select` to efficiently classify discrepancies.
-   **Financial Logic:** Translating an operational risk problem (NAV break) into a structured data analysis task.
-   **Code Reusability:** The core logic is encapsulated in a Python function `reconcile_portfolios` to make it modular and testable.

---
## How It Works

1.  **Data Loading:** The script starts with two sample pandas DataFrames: `df_internal` and `df_external`, simulating the two portfolio reports.
2.  **Merge & Consolidate:** The dataframes are merged using an `outer join` on the `ISIN` to ensure no position is missed.
3.  **Calculate Diffs:** The script calculates the difference between internal and external quantities and prices.
4.  **Classify Breaks:** Using a set of logical conditions, each position is classified as:
    -   `Missing in Internal` (exists only in the external report)
    -   `Extra in Internal` (exists only in the internal report)
    -   `Quantity Mismatch`
    -   `Price Mismatch`
    -   `OK`
5.  **Generate Summary:** The final output is a filtered dataframe showing only the assets with discrepancies, making the investigation clear and actionable.