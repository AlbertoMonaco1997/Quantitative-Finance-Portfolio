# Project EX-04: Python Implementation of a UCITS Pre-Compliance Check

## Objective

This project translates the logical design from `EX-01` into a functional and robust Python script. The core of this module is a function, `check_ucits_compliance()`, that simulates a real-world pre-trade compliance check for a UCITS fund against key regulatory concentration limits.

## Scenario Context

A Risk Manager receives a request from a Portfolio Manager to execute a new trade. Before the order can be sent to the market, it must be checked to ensure it does not breach the fund's investment limits. This function automates that verification process.

## Key Skills Demonstrated

-   **Python for Risk Management:**
    -   Designing a modular and reusable function with clear inputs and outputs.
    -   Using `pandas` for advanced data manipulation, including creating hypothetical post-trade portfolio states, merging dataframes, and performing complex `groupby` aggregations.
    -   Implementing robust control flow to handle different scenarios (e.g., adding to an existing position vs. creating a new one).
    -   Error handling and validation of inputs.
-   **Financial & Regulatory Logic:**
    -   Translating complex UCITS rules (10% issuer limit, 20% group limit, 40% "bucket" rule) into a sequential algorithm.
    -   Demonstrating a "fail-fast" approach, where checks are performed in a logical order of priority.
-   **Software Design:**
    -   Creating a clear and informative output (a list of all breached rules) instead of just a binary pass/fail, which provides more value to the end-user (the PM).

## How It Works

The `check_ucits_compliance()` function performs the following steps:
1.  **Validates Inputs:** Checks if the asset to be added is UCITS eligible and exists in the master data.
2.  **Calculates Post-Trade State:** Creates a hypothetical version of the portfolio as it would look *after* the proposed trade, calculating the new NAV and new market values.
3.  **Performs Sequential Checks:** It systematically verifies the post-trade portfolio against:
    -   The 10% limit for any single issuer.
    -   The 20% limit for any single issuer group.
    -   The 40% limit for the sum of all issuers that individually exceed 5% of the NAV.
4.  **Returns a Clear Result:** The function returns a tuple containing a boolean for the overall outcome and a list of detailed messages, either confirming approval or specifying all the rules that would be breached.