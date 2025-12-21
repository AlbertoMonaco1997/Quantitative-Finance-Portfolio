import pandas as pd
import numpy as np
import statsmodels.api as sm
from data_loader import get_fred_data 
from scipy.stats import skew, kurtosis
import matplotlib.pyplot as plt
import seaborn as sns
import datetime as dt
import os

class PerformanceAnalyzer:
    """
    Output: Comprehensive Markdown Report + Full Suite of PNG Charts.
    """
    
    def __init__(self, portfolio_ledger, benchmark_ledger, config, satellite_history=None, risk_free_series=None):
        self.config = config
        self.reporting_config = config.reporting
        self.portfolio_ledger = portfolio_ledger
        self.benchmark_ledger = benchmark_ledger
        self.satellite_history = satellite_history
        self.metrics = {} 
        self.tables = {} 
        self.series = {} 

        # --- 1. Risk Free Rate Setup ---
        
        if risk_free_series is not None:
            self.risk_free_rate_daily_series = pd.DataFrame({'daily_rf': risk_free_series})
            approx_days_in_month = 365.25 / 12.0
            self.risk_free_rate_daily_series['daily_rf'] = (1 + self.risk_free_rate_daily_series['daily_rf'])**(1/approx_days_in_month) - 1
        else:
            rf_ticker = self.config.tickers.get('risk_free_rate', 'TB3MS')
            start_date = self.portfolio_ledger.index.min()
            end_date = self.portfolio_ledger.index.max()
            rf_annual_raw = get_fred_data(rf_ticker, start_date, end_date) #/ 100 / 12          
            self.risk_free_rate_daily_series = pd.DataFrame({})
            self.risk_free_rate_daily_series['daily_rf'] = (1 + rf_annual_raw / 100)**(1/365.25) - 1
            self.risk_free_rate_daily_series = self.risk_free_rate_daily_series.reindex(self.portfolio_ledger.index, method='ffill')
        self.risk_free_rate_daily_series['daily_rf'] = self.risk_free_rate_daily_series['daily_rf'].bfill().fillna(0.0)

        # --- 2. Returns Calculation (TWRR) ---
        pac_value = self.config.strategy_params.get('pac_value', 0)
        pac_frequency = self.config.strategy_params.get('pac_frequency')
        
        self.cash_flows = pd.Series(0.0, index=self.portfolio_ledger.index)
        if pac_value > 0 and pac_frequency:
            pac_dates = pd.date_range(start=self.portfolio_ledger.index.min(), end=self.portfolio_ledger.index.max(), freq=pac_frequency)
            actual_pac_dates_idx = self.cash_flows.index.searchsorted(pac_dates, side='left')
            valid_idx = actual_pac_dates_idx[actual_pac_dates_idx < len(self.cash_flows.index)]
            self.cash_flows.iloc[valid_idx] = pac_value
        
        self.portfolio_returns = self._calculate_twr_returns(self.portfolio_ledger, self.cash_flows)
        self.benchmark_returns = self._calculate_twr_returns(self.benchmark_ledger, self.cash_flows)

        # Excess Returns
        self.excess_returns = (self.portfolio_returns - self.benchmark_returns).fillna(0.0)
        self.portfolio_excess_vs_rf = (self.portfolio_returns - self.risk_free_rate_daily_series['daily_rf']).fillna(0.0)
        self.benchmark_excess_vs_rf = (self.benchmark_returns - self.risk_free_rate_daily_series['daily_rf']).fillna(0.0)
        
        # Monthly Series (for smooth plots & tables)
        self.portfolio_returns_monthly = self._resample_to_monthly(self.portfolio_returns)
        self.benchmark_returns_monthly = self._resample_to_monthly(self.benchmark_returns)
        self.portfolio_excess_vs_rf_monthly = self._resample_to_monthly(self.portfolio_excess_vs_rf)
        self.benchmark_excess_vs_rf_monthly = self._resample_to_monthly(self.benchmark_excess_vs_rf)

    def _calculate_twr_returns(self, ledger, cash_flows):
        prev_value = ledger['total_value'].shift(1)
        base_value = prev_value + cash_flows
        current_value = ledger['total_value']
        daily_returns = (current_value / base_value) - 1
        daily_returns = daily_returns.replace([np.inf, -np.inf], 0)
        daily_returns.iloc[0] = 0.0
        return daily_returns.fillna(0.0)
        
    def _resample_to_monthly(self, daily_returns):
        if daily_returns.empty: return pd.Series(dtype=float)
        return daily_returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)

    # --- CORE METRICS ---

    def calculate_cagr(self, returns_series):
        if returns_series.empty: return 0.0
        num_years = len(returns_series) / 252.0
        if num_years == 0: return 0.0
        total_return = (1 + returns_series).prod()
        return (total_return ** (1 / num_years)) - 1

    def calculate_annualized_volatility(self, returns_series):
        if returns_series.empty: return 0.0
        return returns_series.std() * np.sqrt(252)

    def calculate_sharpe_ratio(self, excess_returns_series, volatility):
        if volatility == 0: return 0.0
        annualized_excess_return = self.calculate_cagr(excess_returns_series)
        return annualized_excess_return / volatility

    def calculate_sortino_ratio(self, returns_series, rf_daily_series):
        if returns_series.empty: return 0.0
        annualized_return = self.calculate_cagr(returns_series)
        annualized_rf = self.calculate_cagr(rf_daily_series)
        target_return = rf_daily_series
        downside_diff = (returns_series - target_return).copy()
        downside_diff[downside_diff > 0] = 0
        downside_deviation = downside_diff.std() * np.sqrt(252)
        if downside_deviation == 0: return 0.0
        return (annualized_return - annualized_rf) / downside_deviation

    def calculate_calmar_ratio(self, cagr, max_drawdown):
        if max_drawdown == 0: return 0.0
        return cagr / abs(max_drawdown)

    def analyze_drawdown_periods(self, returns_series):
        if returns_series.empty: return 0.0, None, None, None, 0, 0, pd.Series(dtype=float)
        cumulative_returns = (1 + returns_series).cumprod()
        running_max = cumulative_returns.cummax()
        drawdown_series = (cumulative_returns / running_max) - 1
        max_drawdown = drawdown_series.min()
        if max_drawdown == 0: return 0.0, None, None, None, 0, 0, drawdown_series

        trough_date = drawdown_series.idxmin()
        peak_date = running_max.loc[:trough_date].idxmax()
        try:
            recovery_date = cumulative_returns.loc[trough_date:].loc[cumulative_returns >= cumulative_returns[peak_date]].index[0]
            recovery_days = (recovery_date - trough_date).days
        except IndexError:
            recovery_date = None 
            recovery_days = np.nan
            
        duration_days = (trough_date - peak_date).days
        return max_drawdown, peak_date, trough_date, recovery_date, duration_days, recovery_days, drawdown_series

    def calculate_information_ratio(self):
        tracking_error = self.excess_returns.std() * np.sqrt(252)
        if tracking_error == 0:
            self.metrics['Information_Ratio'] = 0.0
            self.metrics['Tracking_Error'] = 0.0
            return
        annualized_excess_return = self.calculate_cagr(self.excess_returns)
        self.metrics['Information_Ratio'] = annualized_excess_return / tracking_error
        self.metrics['Tracking_Error'] = tracking_error

    def calculate_regression_metrics(self):
        if self.portfolio_excess_vs_rf.empty or self.benchmark_excess_vs_rf.empty:
            self.metrics['Alpha'] = 0.0; self.metrics['Beta'] = 0.0
            return
        df = pd.DataFrame({'portfolio': self.portfolio_excess_vs_rf, 'benchmark': self.benchmark_excess_vs_rf}).dropna()
        X = sm.add_constant(df['benchmark'])
        model = sm.OLS(df['portfolio'], X).fit()
        self.metrics['Alpha'] = model.params.get('const', 0) * 252
        self.metrics['Beta'] = model.params.get('benchmark', 0)

    def analyze_satellite_rotation(self):
        if self.satellite_history is None or self.satellite_history.empty: return
        stats = {
            'holdings_pct': self.satellite_history.value_counts(normalize=True).to_dict(),
            'total_rotations': (self.satellite_history != self.satellite_history.shift(1)).sum()
        }
        self.metrics['Satellite_Stats'] = stats

    def _calculate_annual_returns(self, daily_returns_series):
        if daily_returns_series.empty: return pd.Series(dtype=float)
        res = daily_returns_series.resample('YE').apply(lambda x: (1 + x).prod() - 1)
        res.index = res.index.year
        return res

    def _calculate_calendar_period_returns(self, daily_returns_series):
        if daily_returns_series.empty: return pd.Series(dtype=float)
        end_date = daily_returns_series.index.max()
        periods = {
            'YTD': pd.Timestamp(year=end_date.year, month=1, day=1),
            '1 Month': end_date - pd.DateOffset(months=1),
            '3 Months': end_date - pd.DateOffset(months=3),
            '1 Year': end_date - pd.DateOffset(years=1),
            '3 Years': end_date - pd.DateOffset(years=3),
            '5 Years': end_date - pd.DateOffset(years=5),
            'Since Inception': daily_returns_series.index.min()
        }
        results = {}
        for name, start in periods.items():
            idx = daily_returns_series.index.searchsorted(start, side='left')
            if idx < len(daily_returns_series):
                ret = (1 + daily_returns_series.iloc[idx:]).prod() - 1
                if name in ['3 Years', '5 Years'] and (end_date - daily_returns_series.index[idx]).days > 365:
                    years = (end_date - daily_returns_series.index[idx]).days / 365.25
                    ret = (1 + ret)**(1/years) - 1
                results[name] = ret
            else:
                results[name] = np.nan
        return pd.Series(results)

    # --- ORCHESTRATOR ---

    def run_all_analytics(self):
        port_daily = self.portfolio_returns.dropna()
        bench_daily = self.benchmark_returns.dropna()
        daily_rf = self.risk_free_rate_daily_series['daily_rf'].dropna()

        self.metrics['CAGR_Portfolio'] = self.calculate_cagr(port_daily)
        self.metrics['Volatility_Portfolio_Daily'] = self.calculate_annualized_volatility(port_daily)
        (self.metrics['Max_Drawdown_Portfolio'], _, _, _, _, _, self.series['Drawdown_Portfolio']) = self.analyze_drawdown_periods(port_daily)
        self.metrics['Sharpe_Ratio_Portfolio'] = self.calculate_sharpe_ratio((port_daily - daily_rf), self.metrics['Volatility_Portfolio_Daily'])
        self.metrics['Sortino_Ratio_Portfolio'] = self.calculate_sortino_ratio(port_daily, daily_rf)
        self.metrics['Calmar_Ratio_Portfolio'] = self.calculate_calmar_ratio(self.metrics['CAGR_Portfolio'], self.metrics['Max_Drawdown_Portfolio'])
        self.metrics['Skewness_Portfolio'] = skew(port_daily)
        self.metrics['Kurtosis_Portfolio'] = kurtosis(port_daily)

        self.metrics['CAGR_Benchmark'] = self.calculate_cagr(bench_daily)
        self.metrics['Volatility_Benchmark_Daily'] = self.calculate_annualized_volatility(bench_daily)
        (self.metrics['Max_Drawdown_Benchmark'], _, _, _, _, _, self.series['Drawdown_Benchmark']) = self.analyze_drawdown_periods(bench_daily)
        self.metrics['Sharpe_Ratio_Benchmark'] = self.calculate_sharpe_ratio((bench_daily - daily_rf), self.metrics['Volatility_Benchmark_Daily'])
        self.metrics['Sortino_Ratio_Benchmark'] = self.calculate_sortino_ratio(bench_daily, daily_rf)
        self.metrics['Calmar_Ratio_Benchmark'] = self.calculate_calmar_ratio(self.metrics['CAGR_Benchmark'], self.metrics['Max_Drawdown_Benchmark'])
        self.metrics['Skewness_Benchmark'] = skew(bench_daily)
        self.metrics['Kurtosis_Benchmark'] = kurtosis(bench_daily)

        self.calculate_information_ratio()
        self.calculate_regression_metrics()
        self.analyze_satellite_rotation()

        self.tables['Periodic_Returns'] = pd.DataFrame({
            'Portfolio': self._calculate_calendar_period_returns(port_daily),
            'Benchmark': self._calculate_calendar_period_returns(bench_daily)
        })
        self.tables['Annual_Returns'] = pd.DataFrame({
            'Portfolio': self._calculate_annual_returns(port_daily),
            'Benchmark': self._calculate_annual_returns(bench_daily)
        })

    # --- PLOTTING ENGINE ---

    def save_plots(self, output_dir):
        """Generates and saves a complete suite of plots."""
        os.makedirs(output_dir, exist_ok=True)
        sns.set_theme(style=self.reporting_config.get('plot_theme', 'whitegrid'))
        
        # 1. Equity Curves (Linear & Log)
        fig, ax = plt.subplots(figsize=(12, 6))
        (1+self.portfolio_returns).cumprod().plot(ax=ax, label="Portfolio", linewidth=2)
        (1+self.benchmark_returns).cumprod().plot(ax=ax, label="Benchmark", linewidth=2, linestyle='--')
        ax.set_title('Portfolio Growth (Linear)'); ax.legend()
        fig.savefig(f"{output_dir}/equity_curve_linear.png", bbox_inches='tight'); plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 6))
        (1+self.portfolio_returns).cumprod().plot(ax=ax, label="Portfolio", linewidth=2)
        (1+self.benchmark_returns).cumprod().plot(ax=ax, label="Benchmark", linewidth=2, linestyle='--')
        ax.set_yscale('log'); ax.set_title('Portfolio Growth (Log Scale)'); ax.legend()
        fig.savefig(f"{output_dir}/equity_curve_log.png", bbox_inches='tight'); plt.close(fig)

        # 2. Drawdowns
        fig, ax = plt.subplots(figsize=(12, 4))
        if 'Drawdown_Portfolio' in self.series:
            (self.series['Drawdown_Portfolio']*100).plot(ax=ax, label="Portfolio DD", color='red', alpha=0.6)
            ax.fill_between(self.series['Drawdown_Portfolio'].index, (self.series['Drawdown_Portfolio']*100), 0, color='red', alpha=0.1)
        if 'Drawdown_Benchmark' in self.series:
            (self.series['Drawdown_Benchmark']*100).plot(ax=ax, label="Benchmark DD", color='gray', linestyle='--', alpha=0.5)
        ax.set_title('Drawdown Profile (%)'); ax.legend()
        fig.savefig(f"{output_dir}/drawdowns.png", bbox_inches='tight'); plt.close(fig)

        # 3. Monthly Heatmap
        monthly_ret = self.portfolio_ledger['total_value'].resample('ME').last().pct_change()
        df = pd.DataFrame({'Year': monthly_ret.index.year, 'Month': monthly_ret.index.month, 'Ret': monthly_ret})
        pivot = df.pivot(index='Year', columns='Month', values='Ret')
        pivot.columns = [dt.date(1900, m, 1).strftime('%b') for m in pivot.columns]
        fig, ax = plt.subplots(figsize=(10, len(pivot)/2 + 2))
        sns.heatmap(pivot * 100, annot=True, fmt=".1f", cmap="RdYlGn", center=0, cbar=False, ax=ax)
        ax.set_title('Monthly Returns (%)')
        fig.savefig(f"{output_dir}/monthly_heatmap.png", bbox_inches='tight'); plt.close(fig)
        
        # 4. Satellite Allocation
        if self.satellite_history is not None and not self.satellite_history.empty:
            fig, ax = plt.subplots(figsize=(12, 4))
            plot_data = self.satellite_history.dropna()
            factors = sorted(plot_data.unique())
            factor_map = {f: i for i, f in enumerate(factors)}
            ax.plot(plot_data.index, plot_data.map(factor_map), drawstyle='steps-post', color='green')
            ax.set_yticks(range(len(factors))); ax.set_yticklabels(factors)
            ax.set_title('Satellite Factor Allocation')
            fig.savefig(f"{output_dir}/satellite_allocation.png", bbox_inches='tight'); plt.close(fig)
        
        # 5. Returns Distribution (Histogram)
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.histplot(self.portfolio_returns_monthly, kde=True, label='Portfolio', color='blue', alpha=0.4, stat='density', ax=ax)
        sns.histplot(self.benchmark_returns_monthly, kde=True, label='Benchmark', color='orange', alpha=0.4, stat='density', ax=ax)
        ax.set_title('Monthly Returns Distribution'); ax.legend()
        fig.savefig(f"{output_dir}/returns_distribution.png", bbox_inches='tight'); plt.close(fig)

        # 6. Rolling Volatility (3Y)
        fig, ax = plt.subplots(figsize=(12, 5))
        roll_vol_p = self.portfolio_returns_monthly.rolling(36).std() * np.sqrt(12)
        roll_vol_b = self.benchmark_returns_monthly.rolling(36).std() * np.sqrt(12)
        roll_vol_p.plot(ax=ax, label='Portfolio Vol (3Y)', color='blue')
        roll_vol_b.plot(ax=ax, label='Benchmark Vol (3Y)', color='orange', linestyle='--')
        ax.set_title('Rolling 3-Year Volatility (Annualized)'); ax.legend()
        fig.savefig(f"{output_dir}/rolling_volatility_3y.png", bbox_inches='tight'); plt.close(fig)

        # 7. Rolling CAGR (5Y)
        fig, ax = plt.subplots(figsize=(12, 5))
        def roll_cagr(x): return (1+x).prod()**(12/len(x))-1
        roll_cagr_p = self.portfolio_returns_monthly.rolling(60).apply(roll_cagr)
        roll_cagr_b = self.benchmark_returns_monthly.rolling(60).apply(roll_cagr)
        roll_cagr_p.plot(ax=ax, label='Portfolio CAGR (5Y)', color='green')
        roll_cagr_b.plot(ax=ax, label='Benchmark CAGR (5Y)', color='gray', linestyle='--')
        ax.set_title('Rolling 5-Year CAGR'); ax.legend()
        fig.savefig(f"{output_dir}/rolling_cagr_5y.png", bbox_inches='tight'); plt.close(fig)

        # 8. Rolling Correlation (3Y)
        fig, ax = plt.subplots(figsize=(12, 5))
        roll_corr = self.portfolio_returns_monthly.rolling(36).corr(self.benchmark_returns_monthly)
        roll_corr.plot(ax=ax, label='Correlation (3Y)', color='purple')
        ax.axhline(0, color='black', linestyle=':')
        ax.set_title('Rolling 3-Year Correlation vs Benchmark'); ax.legend()
        fig.savefig(f"{output_dir}/rolling_correlation_3y.png", bbox_inches='tight'); plt.close(fig)

    # --- MARKDOWN REPORT GENERATOR ---

    def generate_markdown_report(self, output_path):
        """Generates the .md report using data in self.metrics/tables."""
        strat = self.config.strategy_params
        univ = self.config.universe
        sigs = self.config.signals
        curr = strat.get('calculation_currency', 'USD')
        
        md = []
        md.append("# Strategy Report")
        md.append(f"**Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n")
        
        # --- NEW SECTION: 1. EXECUTIVE PROFILE ---
        md.append("## 1. Executive Strategy Profile")
        
        # 1.1 Mandate & Parameters
        md.append("### 1.1 Mandate & Parameters")
        md.append(f"- **Simulation Period:** {strat.get('start_date')} to {strat.get('end_date')}")
        md.append(f"- **Initial Capital:** {strat.get('initial_capital', 0):,.2f} {curr}")
        if strat.get('pac_value', 0) > 0:
            md.append(f"- **Recurring Inv. (PAC):** {strat['pac_value']:,.2f} {curr} ({strat.get('pac_frequency', '-')})")
        md.append(f"- **Rebalancing:** {strat.get('rebalance_frequency', 'Monthly')}")
        md.append(f"- **Benchmark:** {univ.get('benchmark_ticker', 'WORLD')}")

        # 1.2 Asset Allocation
        md.append("### 1.2 Strategic Asset Allocation")
        core_w = strat.get('core_target_weight', 0.5)
        sat_w = 1.0 - core_w
        md.append(f"- **Core Weight:** {core_w:.1%} (Strategic/Static)")
        md.append(f"- **Satellite Weight:** {sat_w:.1%} (Tactical/Dynamic)")
        
        # 1.3 Universe Composition
        md.append("### 1.3 Universe Composition")
        
        core_alloc = univ.get('core_allocation', {})
        if core_alloc:
            md.append("**Core Constituents (Policy Weights):**")
            md.append("| Ticker | Weight |")
            md.append("| :--- | :--- |")
            for k, v in core_alloc.items():
                if v > 0:
                    md.append(f"| {k} | {v:.1%} |")
            md.append("\n")
            
        sat_cands = univ.get('satellite_candidates', [])
        md.append(f"**Satellite Candidates (Dynamic Universe):**")
        md.append(f"_{', '.join(sat_cands)}_\n")
        
        # 1.4 Signal Logic
        signals_used = sigs.get('signals_to_use', {})
        if signals_used:
            md.append("### 1.4 Signal Engine Configuration")
            md.append("| Signal Factor | Influence Weight |")
            md.append("| :--- | :--- |")
            for k, v in signals_used.items():
                if v > 0:
                    md.append(f"| {k} | {v:.0%} |")
            md.append("\n")
        
        def get_m(key, fmt="{:,.2%}"):
            v = self.metrics.get(key)
            return fmt.format(v) if v is not None else "-"

        # 2. KPIs
        md.append("## 2. Key Performance Indicators")
        md.append("| Metric | Portfolio | Benchmark |")
        md.append("| :--- | :--- | :--- |")
        md.append(f"| **CAGR** | {get_m('CAGR_Portfolio')} | {get_m('CAGR_Benchmark')} |")
        md.append(f"| **Vol (Daily)** | {get_m('Volatility_Portfolio_Daily')} | {get_m('Volatility_Benchmark_Daily')} |")
        md.append(f"| **Sharpe** | {get_m('Sharpe_Ratio_Portfolio', '{:,.2f}')} | {get_m('Sharpe_Ratio_Benchmark', '{:,.2f}')} |")
        md.append(f"| **Sortino** | {get_m('Sortino_Ratio_Portfolio', '{:,.2f}')} | {get_m('Sortino_Ratio_Benchmark', '{:,.2f}')} |")
        md.append(f"| **Max DD** | {get_m('Max_Drawdown_Portfolio')} | {get_m('Max_Drawdown_Benchmark')} |")
        md.append(f"| **Calmar** | {get_m('Calmar_Ratio_Portfolio', '{:,.2f}')} | {get_m('Calmar_Ratio_Benchmark', '{:,.2f}')} |")
        md.append(f"| **Skew** | {get_m('Skewness_Portfolio', '{:,.2f}')} | {get_m('Skewness_Benchmark', '{:,.2f}')} |")
        md.append("\n")

        # 3. Relative
        md.append("## 3. Relative Performance")
        md.append("| Metric | Value |")
        md.append("| :--- | :--- |")
        md.append(f"| **Alpha (Ann)** | {get_m('Alpha')} |")
        md.append(f"| **Beta** | {get_m('Beta', '{:,.2f}')} |")
        md.append(f"| **Info Ratio** | {get_m('Information_Ratio', '{:,.2f}')} |")
        md.append(f"| **Track Err** | {get_m('Tracking_Error')} |")
        md.append("\n")

        # 4. Tables
        md.append("## 4. Periodic Returns")
        if 'Periodic_Returns' in self.tables:
            order = ['YTD', '1 Month', '3 Months', '1 Year', '3 Years', '5 Years', 'Since Inception']
            df = self.tables['Periodic_Returns'].reindex(order)
            md.append(df.map(lambda x: f"{x:.2%}" if pd.notnull(x) else "-").to_markdown())
        md.append("\n")

        md.append("## 5. Annual Returns")
        if 'Annual_Returns' in self.tables:
            md.append(self.tables['Annual_Returns'].map(lambda x: f"{x:.2%}" if pd.notnull(x) else "-").to_markdown())
        md.append("\n")

        # 6. Visuals
        md.append("## 6. Visual Analysis")
        md.append("### Growth & Risk")
        md.append("![Equity Curve Log](plots/equity_curve_log.png)")
        md.append("![Drawdowns](plots/drawdowns.png)")
        
        md.append("### Rolling Analysis (Dynamic)")
        md.append("![Rolling CAGR 5Y](plots/rolling_cagr_5y.png)")
        md.append("![Rolling Volatility 3Y](plots/rolling_volatility_3y.png)")
        md.append("![Rolling Correlation 3Y](plots/rolling_correlation_3y.png)")
        md.append("![Returns Distribution](plots/returns_distribution.png)")
        
        md.append("### Allocation & Seasonality")
        md.append("![Heatmap](plots/monthly_heatmap.png)")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        print(f"Markdown report generated: {output_path}")
        

    def finalize_report(self):
        """
        Runs analytics, saves FULL PLOT SUITE, and generates the Markdown report.
        """
        output_dir = self.reporting_config.get('output_path', 'reports')
        plots_dir = os.path.join(output_dir, 'plots')
        md_path = os.path.join(output_dir, 'STRATEGY_REPORT.md')

        print(f"\n[Analyzer] Running Analytics...")
        self.run_all_analytics()
        
        print(f"[Analyzer] Saving Plots to {plots_dir}...")
        self.save_plots(plots_dir)
        
        print(f"[Analyzer] Generating Markdown Report...")
        self.generate_markdown_report(md_path)
        
        print(f"--- Full Report Complete: {md_path} ---")