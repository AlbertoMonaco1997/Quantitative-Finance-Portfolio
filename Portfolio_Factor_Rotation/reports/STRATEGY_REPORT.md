# Strategy Report
**Date:** 2025-12-25 21:40

## 1. Executive Strategy Profile
### 1.1 Mandate & Parameters
- **Simulation Period:** 2000-01-03 to 2025-08-31
- **Initial Capital:** 10,000.00 USD
- **Recurring Inv. (PAC):** 1,000.00 USD (BMS)
- **Rebalancing:** QS
- **Benchmark:** WORLD
### 1.2 Strategic Asset Allocation
- **Core Weight:** 76.0% (Strategic/Static)
- **Satellite Weight:** 24.0% (Tactical/Dynamic)
### 1.3 Universe Composition
**Core Constituents (Policy Weights):**
| Ticker | Weight |
| :--- | :--- |
| VALUE | 25.0% |
| QUALITY | 25.0% |
| MOMENTUM | 25.0% |
| SIZE | 25.0% |


**Satellite Candidates (Dynamic Universe):**
_VALUE, QUALITY, MOMENTUM, SIZE, WORLD_

### 1.4 Signal Engine Configuration
| Signal Factor | Influence Weight |
| :--- | :--- |
| pure_momentum | 20% |
| alpha | 40% |
| valuation | 40% |


## 2. Key Performance Indicators
| Metric | Portfolio | Benchmark |
| :--- | :--- | :--- |
| **CAGR** | 7.80% | 5.91% |
| **Vol (Daily)** | 15.79% | 16.03% |
| **Sharpe** | 0.41 | 0.29 |
| **Sortino** | 0.64 | 0.45 |
| **Max DD** | -57.89% | -57.76% |
| **Calmar** | 0.13 | 0.10 |
| **Skew** | -0.45 | -0.38 |


## 3. Relative Performance
| Metric | Value |
| :--- | :--- |
| **Alpha (Ann)** | 1.94% |
| **Beta** | 0.96 |
| **Info Ratio** | 0.50 |
| **Track Err** | 3.36% |


## 4. Periodic Returns
|                 | Portfolio   | Benchmark   |
|:----------------|:------------|:------------|
| YTD             | 14.97%      | 13.78%      |
| 1 Month         | 2.29%       | 1.54%       |
| 3 Months        | 7.57%       | 8.93%       |
| 1 Year          | 15.64%      | 16.65%      |
| 3 Years         | 16.46%      | 17.51%      |
| 5 Years         | 11.37%      | 12.89%      |
| Since Inception | 635.36%     | 359.89%     |


## 5. Annual Returns
|   Date | Portfolio   | Benchmark   |
|-------:|:------------|:------------|
|   2000 | -10.98%     | -13.80%     |
|   2001 | -7.79%      | -16.93%     |
|   2002 | -14.65%     | -19.90%     |
|   2003 | 46.56%      | 32.85%      |
|   2004 | 22.76%      | 14.60%      |
|   2005 | 16.73%      | 9.44%       |
|   2006 | 23.70%      | 20.03%      |
|   2007 | 10.79%      | 9.02%       |
|   2008 | -40.58%     | -40.68%     |
|   2009 | 31.19%      | 30.00%      |
|   2010 | 16.44%      | 11.69%      |
|   2011 | -5.45%      | -5.51%      |
|   2012 | 14.39%      | 15.80%      |
|   2013 | 29.89%      | 26.66%      |
|   2014 | 4.24%       | 4.95%       |
|   2015 | -0.03%      | -0.88%      |
|   2016 | 5.78%       | 7.50%       |
|   2017 | 26.57%      | 22.39%      |
|   2018 | -8.23%      | -8.71%      |
|   2019 | 25.29%      | 27.67%      |
|   2020 | 15.98%      | 15.90%      |
|   2021 | 17.36%      | 21.80%      |
|   2022 | -17.35%     | -18.15%     |
|   2023 | 19.80%      | 23.78%      |
|   2024 | 15.06%      | 18.67%      |
|   2025 | 14.97%      | 13.78%      |


## 6. Visual Analysis
### Growth & Risk
![Equity Curve Log](plots/equity_curve_log.png)
![Drawdowns](plots/drawdowns.png)
### Rolling Analysis (Dynamic)
![Rolling CAGR 5Y](plots/rolling_cagr_5y.png)
![Rolling Volatility 3Y](plots/rolling_volatility_3y.png)
![Rolling Correlation 3Y](plots/rolling_correlation_3y.png)
![Returns Distribution](plots/returns_distribution.png)
### Allocation & Seasonality
![Heatmap](plots/monthly_heatmap.png)

# 7. Advanced Statistical Validation
## 7.1 Probabilistic Metrics (Lopez de Prado)
- **Probabilistic IR (P[IR>0]):** 99.60%
- **Min Track Record (95% Conf.):** 10.3 Years

## 7.2 Bootstrap Reality Check (Non-Centered - Robustness)
- **Observed t-stat:** 2.627
- **Prob(t* > 0):** **99.70%**
- **Interpretation:** **STRUCTURAL EDGE CONFIRMED:** The strategy (or its underlyings) generates positive returns in >95% of random scenarios. The engine is robust.
![Bootstrap Dist](plots/bootstrap_distribution.png)

## 7.3 BRC Centered (Skill vs Luck)
- **Centered t-stat:** 0.006
- **Prob(t* > 0) [Skill Mass]:** **57.31%**
- **Interpretation:**  **NO TIMING SKILL:** Value comes from index selection, not Timing.
![Bootstrap Centered](plots/bootstrap_centered_distribution.png)

## 7.4 Rolling Time Robustness
### Rolling Probability of Positive Return
![Rolling Prob](plots/rolling_prob_gt_0.png)
### Rolling P-Value (Outlier Check)
![Rolling P-Value](plots/rolling_pvalue.png)
