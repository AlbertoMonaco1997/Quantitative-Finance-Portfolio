Of course. Here is the original text in English, formatted in Markdown.

-----

# Loan vs. Liquidation: A Financial Strategy Analyzer 📈

This project provides a Python-based tool to analyze and compare two common financial strategies for raising a significant amount of cash (e.g., for a mortgage down payment) when you have an existing investment portfolio.

The two strategies are:

  * **Loan (Leverage Strategy)**: Keep the entire portfolio invested and take out a loan secured by your assets. This allows the portfolio to continue growing but incurs interest costs.
  * **Liquidation Strategy**: Sell a portion of the portfolio to get the required cash. This avoids debt but incurs immediate capital gains taxes and reduces the capital base for future growth.

The script uses `plotly` to generate interactive 2D and 3D visualizations, helping users understand under which conditions (portfolio return, loan interest rate, monthly savings rate) one strategy outperforms the other.

-----

## How It Works ⚙️

The core of the analysis is to compare the final net worth of an investor at the end of a specific time horizon: the number of months required to pay off the loan in the "Loan" scenario.

For the comparison to be fair, in the "Liquidation" scenario, the monthly payment that would have gone towards the loan is instead reinvested back into the portfolio.

The script generates three distinct analyses:

### Analysis 1: 3D Surface - Interest Rate vs. Portfolio Return

This plot shows how the final wealth difference between the two strategies changes when varying the loan interest rate (`i`) and the annual portfolio return (`r`).

  * 🔵 **Blue Surface (Z \> 0)**: The Loan strategy is more profitable. This is typical when portfolio returns are high and interest rates are low.
  * 🔴 **Red Surface (Z \< 0)**: The Liquidation strategy is more profitable. This occurs when the cost of debt outweighs the benefits of investment growth.

### Analysis 2: 2D Plot - Break-Even Points

This plot shows the break-even points for the portfolio return (`r`) at several fixed loan interest rates (`i`). It answers the question: "What is the minimum return my portfolio needs to achieve to make the Loan strategy worthwhile?"

  * The intersection points on the zero-line show the break-even portfolio return for each interest rate.
  * The divergence of the lines at higher returns shows how sensitive the outcome is to the cost of debt when the portfolio is performing well.

### Analysis 3: 3D Surface - Monthly Savings vs. Interest Rate

This plot shows how the final wealth difference changes when varying the monthly investment amount (PAC) and the loan interest rate (`i`), assuming a fixed portfolio return.

  * This visualization highlights that a higher savings/repayment capacity makes the Loan strategy viable even at higher interest rates.

-----

## How to Use 🛠️

1.  **Configure Parameters**: Open the `liquidation_vs_loan.py` script and modify the parameters in the `if __name__ == "__main__":` block to match your personal financial scenario.
2.  You can find the results in the "plots" folder.

<!-- end list -->

```python
# --- USER-DEFINED STARTING POINTS FOR ADAPTIVE GRID ---
start_pac = 1000.0           # Your monthly savings/investment amount
start_annual_return = 0.065  # Your expected annual portfolio return (e.g., 6.5%)
start_loan_rate = 0.045      # The expected annual interest rate for the loan (e.g., 4.5%)

ANALYZER_PARAMS = {
    "months_pre_mortgage": 120, # How many months you've been investing
    "loan_needed": 50000.0,     # The amount of cash you need
    "capital_gain_tax_rate": 0.26,
}
```
