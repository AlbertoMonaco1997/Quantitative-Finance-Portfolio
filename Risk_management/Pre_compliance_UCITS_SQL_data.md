# Exercise 01.1: SQL Data Extraction for UCITS Pre-Compliance

## Objective

This script is part of a larger exercise (`EX-01: UCITS Pre-Compliance Check`). The specific goal of this module is to write a robust and professional SQL query to extract current portfolio exposures, which are necessary to perform a pre-trade compliance check against UCITS concentration limits.

## Scenario Context

A Portfolio Manager intends to purchase a new security (`ticker_to_check`) for a specific fund (`fund_to_check`). The query must calculate the fund's total current exposure to the new security's issuer and issuer group *before* the trade is executed.

## Skills Demonstrated

-   **SQL (Advanced):**
    -   Use of **Common Table Expressions (CTE)** with the `WITH` clause to structure the logic into clear, readable steps.
    -   Implementation of **conditional aggregations** using `SUM(CASE WHEN ...)` to calculate multiple metrics in a single pass.
    -   Management of `JOINs` between operational tables (`positions`) and master data tables (`assets_master`).
-   **Financial Logic:**
    -   Translation of a regulatory requirement (UCITS issuer and group exposure limits) into a specific data query.
    -   Ability to design a query that correctly handles complex data structures (e.g., multiple securities from the same issuer).

## Result

The final query efficiently and correctly extracts the two necessary exposure metrics, providing the fundamental input for the pre-compliance check algorithm.

## Code

WITH
    issuer_x 
AS (Select 
        issuer_name, issuer_group 
    FROM 
        assets_master
    WHERE
        ticker = '{ticker_to_check}')
                
SELECT 
    SUM(CASE
            WHEN a.issuer_name = (SELECT issuer_name FROM issuer_x)
            THEN p.market_value_eur
            ELSE 0
            END) AS total_exposure_to_issuer_eur,
    SUM(CASE
            WHEN a.issuer_group = (SELECT issuer_group FROM issuer_x)
            THEN p.market_value_eur
            ELSE 0
            END) AS total_exposure_to_group_eur
FROM
    assets_master AS a 
JOIN 
    positions AS p ON a.ticker = p.asset_ticker

WHERE
    p.fund_id = '{fund_to_check}';