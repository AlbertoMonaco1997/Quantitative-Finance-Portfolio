"""
This script analyzes and compares two financial strategies for obtaining liquidity
for a mortgage down payment, given an existing investment portfolio:

1.  Loan (Leverage): Keep the portfolio invested and open a line of credit
    secured by the assets. Interest is paid on the debt.

2.  Liquidation: Sell a portion of the portfolio to obtain the necessary
    liquidity, paying capital gains taxes.

The analysis generates multiple interactive plots to explore the results:
- A 3D plot varying loan interest rate and portfolio return.
- A 2D plot showing sensitivity to portfolio return at different fixed interest rates.
- A 3D plot varying the monthly investment (PAC) and the loan interest rate.
"""

import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import webbrowser
import os

# --- MODULE 1: PURE FINANCIAL FUNCTIONS ---

def calculate_loan_repayment_months(loan_amount: float, monthly_pac: float, annual_rate: float) -> float:
    """
    Calculates the number of months required to repay a loan.
    This is the explicit formula for the NPER function.
    """
    if monthly_pac <= 0 or loan_amount <= 0:
        return 0
    if annual_rate <= 0:
        return loan_amount / monthly_pac if monthly_pac > 0 else float('inf')
    
    monthly_rate = annual_rate / 12 # different from (annual_rate + 1)**(1/12)
    
    # Argument for the logarithm. If it's non-positive, the loan is never paid off.
    argument = 1 - (loan_amount * monthly_rate / monthly_pac)
    if argument <= 0:
        return float('inf')
        
    return -np.log(argument) / np.log(1 + monthly_rate)

def calculate_pic_future_value(principal: float, annual_rate: float, months: float) -> float:
    """Calculates the future value of a principal with compound interest."""
    if months <= 0 or principal <= 0:
        return principal
    monthly_growth_factor = (1 + annual_rate)**(1/12) # not -1 
    return principal * (monthly_growth_factor)**months

def calculate_future_value_severance(loan_needed: float, annual_rate: float, loan_months: int, monthly_pac: float, months_pre_mortgage: int, capital_pre_loan: float, capital_gain_tax_rate: float = 0.26) -> float:
    """Calculates the future value of an investment composed by two separate phases: 
        1) A systemic investment plan with a duration equal to months_pre_mortgage
        2) for liquidity reason it is required to sell a fraction of a portfolio equal to loan_needed (in currency) + tax on the overperformance
        3) continuation of the PAC after the liquidation for a number of months equal to loan_months   
    """
    
    ratio_gain = 1 - (months_pre_mortgage*monthly_pac)/capital_pre_loan
    eff_tax = ratio_gain * capital_gain_tax_rate
    withdrawal = loan_needed/ (1 - eff_tax)
    capital_after_liquidation = capital_pre_loan - withdrawal
    
    return calculate_pic_future_value(capital_after_liquidation, annual_rate, loan_months) + calculate_pac_future_value(monthly_pac, annual_rate, loan_months)
    

def calculate_pac_future_value(monthly_pac: float, annual_return: float, months: int) -> float:
    """Calculates the future value of a Systematic Investment Plan (annuity due)."""
    if months <= 0 or monthly_pac <= 0:
        return 0
    monthly_growth_factor = (1 + annual_return)**(1/12)
    
    monthly_growth_factor = (1 + annual_return)**(1/12)
    if monthly_growth_factor == 1:
        return monthly_pac * months
    return monthly_pac * (((monthly_growth_factor)**(months+1) - monthly_growth_factor) / (monthly_growth_factor - 1))

# --- MODULE 2: SCENARIO ANALYSIS CLASS ---

class ScenarioAnalyzer:
    """
    Orchestrates the analysis by comparing the two strategies across a grid of parameters.
    """
    def __init__(self, months_pre_mortgage: int, loan_needed: float, capital_gain_tax_rate: float):
        self.months_pre_mortgage = months_pre_mortgage
        self.loan_needed = loan_needed
        #self.monthly_pac = monthly_pac
        self.capital_gain_tax_rate = capital_gain_tax_rate
        # self.annual_return = annual_return

    def _calculate_single_point_difference(self, interest_rate: float, portfolio_return: float, monthly_payment: float):
            """Helper function to calculate wealth difference for a single scenario."""

            
            # 1. Calculate the initial state dynamically based on the portfolio's actual return
            capital_at_mortgage_time = calculate_pac_future_value(
            monthly_payment, portfolio_return, self.months_pre_mortgage
        	)
        	
            if capital_at_mortgage_time < self.loan_needed:
                # If the portfolio is not large enough, the strategies are not viable
                return -float('inf')
    
            # 2. Calculate the time horizon based on the loan repayment
            months_to_repay = calculate_loan_repayment_months(self.loan_needed, monthly_payment, interest_rate)
            
            if months_to_repay == float('inf'):
                return -float('inf')
    
            # 3. SCENARIO A: LOAN (FIDO)
            final_wealth_loan = calculate_pic_future_value(capital_at_mortgage_time, portfolio_return, months_to_repay)
    
            # 4. SCENARIO B: LIQUIDATION + REINVESTMENT
            final_wealth_liquidation = calculate_future_value_severance(self.loan_needed, portfolio_return, months_to_repay, monthly_payment, self.months_pre_mortgage, capital_at_mortgage_time)
            
            return final_wealth_loan - final_wealth_liquidation
    
    
    
    
    def run_analysis_rate_vs_return(self, rate_range: np.ndarray, return_range: np.ndarray, fixed_pac: float):
            """Analyzes varying rate and return for a fixed monthly PAC."""
            R_grid, Y_grid = np.meshgrid(rate_range, return_range)
            Z_diff_grid = np.zeros_like(R_grid)
    
            for i, j in np.ndindex(R_grid.shape):
                Z_diff_grid[i, j] = self._calculate_single_point_difference(
                    interest_rate=R_grid[i, j], 
                    portfolio_return=Y_grid[i, j], 
                    monthly_payment=fixed_pac
                )
            return R_grid, Y_grid, Z_diff_grid
    
    def run_analysis_pac_vs_rate(self, pac_range: np.ndarray, rate_range: np.ndarray, fixed_return: float):
            """Analyzes varying PAC and rate for a fixed portfolio return."""
            P_grid, R_grid = np.meshgrid(pac_range, rate_range)
            Z_diff_grid = np.zeros_like(P_grid)
    
            for i, j in np.ndindex(P_grid.shape):
                Z_diff_grid[i, j] = self._calculate_single_point_difference(
                    interest_rate=R_grid[i, j], 
                    portfolio_return=fixed_return, 
                    monthly_payment=P_grid[i, j]
                )
            return P_grid, R_grid, Z_diff_grid


# --- MODULE 3: PLOTTING CLASS ---

class Plotter:
    """Class dedicated to visualizing the results using Plotly."""
    
    @staticmethod
    def _save_and_open(fig, filename: str):
        """Saves a Plotly figure to HTML and opens it."""
        fig.write_html(filename)
        print(f"\nInteractive plot saved as '{filename}'. Opening in your default browser...")
        try:
            webbrowser.open('file://' + os.path.realpath(filename))
        except Exception as e:
            print(f"Could not automatically open the browser. Please open '{filename}' manually. Error: {e}")

    @staticmethod
    def plot_3d_surface(X, Y, Z, title, x_label, y_label, z_label, filename):
        """Creates an advanced, interactive 3D surface plot."""
        Z[Z == -np.inf] = np.nan
        max_abs_val = np.nanmax(np.abs(Z)) if not np.all(np.isnan(Z)) else 1

        surface_trace = go.Surface(
            x=X, y=Y, z=Z, colorscale='RdBu', cmin=-max_abs_val, cmax=max_abs_val,
            colorbar=dict(title='Wealth Diff. (€)', tickformat="€,")
        )
        zero_plane_trace = go.Surface(
            x=X[0, :], y=Y[:, 0], z=np.zeros_like(Z), opacity=0.5, showscale=False,
            colorscale=[[0, 'grey'], [1, 'grey']]
        )
        fig = go.Figure(data=[surface_trace, zero_plane_trace])
        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=20)),
            scene=dict(xaxis_title=x_label, yaxis_title=y_label, zaxis_title=z_label),
            margin=dict(l=0, r=0, b=0, t=40)
        )
        Plotter._save_and_open(fig, filename)

    @staticmethod
    def plot_2d_lines(x_data, y_data_dict, title, x_label, y_label, filename):
        """Creates an interactive 2D line plot for sensitivity analysis."""
        fig = go.Figure()
        for name, y_data in y_data_dict.items():
            fig.add_trace(go.Scatter(x=x_data * 100, y=y_data, mode='lines', name=name))
        
        fig.add_hline(y=0, line_width=2, line_dash="dash", line_color="grey")
        
        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=20)),
            xaxis_title=x_label, yaxis_title=y_label,
            xaxis=dict(ticksuffix='%'), yaxis=dict(tickprefix='€', tickformat=','),
            legend_title_text='Loan Interest Rate'
        )
        Plotter._save_and_open(fig, filename)

# --- MAIN EXECUTION BLOCK ---

if __name__ == "__main__":
    # --- FIXED SCENARIO PARAMETERS ---
    ANALYZER_PARAMS = {
        "months_pre_mortgage": 120,
        "loan_needed": 64650.0,
        "capital_gain_tax_rate": 0.26,
        
        
    }
    analyzer = ScenarioAnalyzer(**ANALYZER_PARAMS)
    
    # --- USER-DEFINED STARTING POINTS FOR ADAPTIVE GRID ---
    start_pac = 1000.0
    start_annual_return = 0.065 # Realistic 7% return
    start_loan_rate = 0.045  # Realistic 4.5% loan rate

    # --- ANALYSIS 1: 3D Plot (Rate vs Return) ---
    print("--- Running Analysis 1: Rate vs Return (3D) ---")
    loan_rate_range_1 = np.linspace(0.1 * start_loan_rate, 1.5 * start_loan_rate, 50)
    etf_return_range_1 = np.linspace(0.1 * start_annual_return, 1.5 * start_annual_return, 50)
    
    r_grid_1, y_grid_1, z_grid_1 = analyzer.run_analysis_rate_vs_return(
        loan_rate_range_1, etf_return_range_1, fixed_pac=start_pac
    )
    
    Plotter.plot_3d_surface(
        r_grid_1 * 100, y_grid_1 * 100, z_grid_1,
        f"Analysis 1: Loan vs. Liquidation (Fixed PAC = €{start_pac:.0f})",
        "Loan Interest Rate (i) [%]", "Annual Portfolio Return (r) [%]", "Additional Final Wealth (€)",
        "analysis_1_rate_vs_return.html"
    )

    # --- ANALYSIS 2: 2D Plot (Sensitivity to Return) ---
    print("\n--- Running Analysis 2: Sensitivity to Return (2D) ---")
    ratios = [0.5, 0.75, 0.9, 1, 1.1, 1.25, 1.5]
    fixed_rates_2 = [start_loan_rate * r for r in ratios]
    #fixed_rates_2 = [start_loan_rate * 0.75, start_loan_rate,  start_loan_rate * 1.5]
    etf_return_range_2 = np.linspace(0.1 * start_annual_return, 1.5* start_annual_return, 100)
    y_data_2 = {}
    for rate in fixed_rates_2:
        diffs = [analyzer._calculate_single_point_difference(rate, ret, start_pac) for ret in etf_return_range_2]
        y_data_2[f'i = {rate:.2%}'] = np.array(diffs)
    
    Plotter.plot_2d_lines(
        etf_return_range_2, y_data_2,
        f"Analysis 2: Break-Even Points (Fixed PAC = €{start_pac:.0f})",
        "Annual Portfolio Return (r)", "Additional Final Wealth (€)",
        "analysis_2_sensitivity.html"
    )

    # --- ANALYSIS 3: 3D Plot (PAC vs Rate) ---
    print("\n--- Running Analysis 3: PAC vs Rate (3D) ---")
    pac_range_3 = np.linspace(0.5 * start_pac, 1.5 * start_pac, 50)
    loan_rate_range_3 = np.linspace(0.1 * start_loan_rate, 1.5 * start_loan_rate, 50)

    p_grid_3, r_grid_3, z_grid_3 = analyzer.run_analysis_pac_vs_rate(
        pac_range_3, loan_rate_range_3, fixed_return=start_annual_return
    )
    Plotter.plot_3d_surface(
        p_grid_3, r_grid_3 * 100, z_grid_3,
        f"Analysis 3: Loan vs. Liquidation (Fixed Return = {start_annual_return:.1%})",
        "Monthly PAC Investment (€)", "Loan Interest Rate (i) [%]", "Additional Final Wealth (€)",
        "analysis_3_pac_vs_rate.html"
    )
