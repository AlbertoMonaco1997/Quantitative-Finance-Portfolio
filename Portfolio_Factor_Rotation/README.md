# Core-Satellite Portfolio Strategy

## Executive Summary
A quantitative portfolio/index builder based on a factor `Core-Satellite` investment strategy. The framework includes capital gains tax rate and transaction costs for realistic results.
The portfolio is based on a `static fiscal-efficient core structure` which gets rebalanced by periodic cash injections (PAC), purchasing assets to restore original target weights without incurring tax drag.
The `satellite structure` contains an index selected from the satellite candidates list; it periodically rotates based on a combination of `quantitative signals` such as momentum, z-score valuation, inflationary regime, rolling market Vasicek beta, and rolling alpha generation.
The basic information regarding the built portfolio is stored in the strategy report, which saves standard valuation metrics such as CAGR, geometric Sharpe ratio, maximum drawdown, annual returns, and personalized benchmark comparison.
In the second section of the strategy report, advanced analytics can be found, such as Lopez de Prado Probabilistic Information Ratio, MinTRL, and Rolling/Full-window Non-Centered and Centered Bootstrap Reality Checks, used to validate and evaluate strategy effectiveness.

## Architecture
The project is fully modular to facilitate extension and extraction of single features, and it is designed to be *Asset Agnostic*.

- **`config.json`**: Contains all information regarding portfolio structure (core, satellite candidates, signal composition, time horizon), benchmark, data to load, and output settings.
- **`config_loader.py`**: Loads config.json parameters.
- **`data_loader.py`**: Loads data from Excel and automatically downloads from the FRED website; it then checks, cleans invalid data, and prepares the starting dataframe.
- **`signal_engine.py`**: Calculates every required signal, combines them via holistic aggregation, and builds the decision dataframe.
- **`backtest_engine.py`**: Computes portfolio value, purchases, rebalancing events, weights, and prices.
- **`performance_analyzer.py`**: Computes standard evaluation metrics and plots.
- **`strategy_validator.py`**: Statistical validation suite (Bootstrap Reality Check, Probabilistic Information Ratio, MinTRL).

## Key Features
- **Factor Investing:** In the standard setup, we perform a dynamic factor rotation of Momentum, Value, Size, and Quality factors.
- **Advanced Stats:** Basic metrics are not sufficient to statistically validate the strategy; for this reason, it is necessary to compute advanced metrics to deeply analyze strategy behavior:
  - *Probabilistic Sharpe Ratio* (Skewness/Kurtosis adjustment).
  - *Bootstrap Reality Check* (Centered vs Non-Centered) to validate the true skill of the strategy versus the luck inherent in the selection of underlying products (factors).

## Installation & Usage
1. **Clone the repository**
   Since this project is located in a subfolder, clone the main repository and navigate to the directory:
   ```bash
   git clone [https://github.com/AlbertoMonaco1997/Quantitative-Finance-Portfolio.git](https://github.com/AlbertoMonaco1997/Quantitative-Finance-Portfolio.git)
   cd Quantitative-Finance-Portfolio/Portfolio_Factor_Rotation`
   
2. **Install dependencies**
	```bash
	pip install -r requirements.txt

3. **Run the Pipeline**
	```bash
	python main.py
	
The strategy report will be generated in reports/STRATEGY_REPORT.md

# System Requirements

## Python Version
This project is developed and tested on **Python 3.11.13**.
Compatibility is expected with Python 3.9+, but performance optimizations in 3.11 are recommended for the Bootstrap simulations.

## Disclaimer
This project is for educational and research purposes only.