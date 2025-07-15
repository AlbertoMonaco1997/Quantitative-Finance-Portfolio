# Portfolio Optimization Project

This project is part of a long-term study plan to acquire practical and theoretical skills for roles such as Portfolio Analyst, Risk Analyst, or Quantitative Analyst in the finance and energy sectors.

The main goal is to implement key concepts from Modern Portfolio Theory (MPT), including portfolio construction, risk/return tradeoffs, and optimization under constraints.

## Contents

- Exploratory data analysis of market indices and etfs
- Calculation of returns, variance, covariance, and correlation
- Efficient frontier and capital allocation line (CAL)
- Monte Carlo simulations of random portfolios
- Risk-adjusted performance metrics (Sharpe ratio)
- Inflation-adjusted return analysis (planned)
- Future extensions: Value at Risk (VaR), CVaR, constraints, Black-Litterman

## Dataset

The dataset consists of daily closing prices of several market indices, downloaded using the `yfinance` Python library.
Here is the list:
    # --- Global Stock Indexes
    '^GSPC',        # **S&P 500 (USA Large Cap)
    '^DJI',          # **Dow Jones Industrial Average (USA Blue Chip)             
    '^IXIC',        # **NASDAQ Composite (USA)
    '^RUT',          # Russell 2000 (USA Small Caps)
    '^FTSE',        # **FTSE 100 (UK)
    '^GDAXI',       # **DAX (Germany)** - 
    '^STOXX50E',    # **Euro Stoxx 50 (Europe Blue Chip)** 
    '^N225',        # **Nikkei 225 (Japan)**
    '^HSI',         # **Hang Seng Index (Hong Kong)** 
    '000001.SS',    # SSE Composite Index (Cina)
    
    # ---Other Indexes ---
    '^FCHI',        # **CAC 40 (Francr)
    '^AORD',        # **All Ordinaries (Australia)
    # ---Emerging Markets---
    '^JKSE',        # **Jakarta Composite Index (Indonesia)
    '^BVSP',        # **Ibovespa (Brasile)
    '^MXX',         # **IPC (Messico)
	
	"^IRX", # US 13-Week Treasury Bill Yield.
    "^TNX", # US 10-Year Treasury Note Yield.
    "^TYX"  # US 30-Year Treasury Bond Yield.
	

## Status

Ongoing — the project is evolving alongside the theoretical study of Chapters 4–12 of *Modern Portfolio Theory and Investment Analysis* (Elton et al.).

## Requirements

- Python 3.10+
- NumPy
- Pandas
- Matplotlib / Plotly
- yfinance

## Author

This project is part of a portfolio designed to demonstrate technical and analytical skills to potential employers.