import numpy as np
import pandas as pd
from scipy.stats import norm
import copy
from performance_analyzer import PerformanceAnalyzer
import statsmodels.api as sm 
import warnings
from typing import List, Optional
from config_loader import Config
from joblib import Parallel, delayed
import os
from signal_engine import generate_holistic_ranks
from backtest_engine import Backtester
import seaborn as sns
import matplotlib.pyplot as plt

class StrategyValidator:
    """
    Performs advanced validation tests on a backtest result.
    
    This class implements:
    1. Probabilistic metrics (PIR, MinTRL) using Lopez de Prado's
       consistent variance formulation.
    2. Bootstrap-based metrics (HAC t-stat, BRC, Rolling BRC) to correct for 
       autocorrelation and selection bias.
    """
    
    def __init__(self, 
                 config_strategy: Config,
                 config_benchmark: Config,
                 master_df: pd.DataFrame, 
                 performance_analyzer: PerformanceAnalyzer):
        """
        Initializes the validator with all necessary tools and data.
        """
        print("Initializing Strategy Validator (Phase 2)...")
        
        self.config_strategy = config_strategy
        self.config_benchmark = config_benchmark
        self.reporting_config = config_strategy.reporting
        
        self.master_df_full = master_df.copy()
        self.T_full = len(self.master_df_full)
        self.full_index = self.master_df_full.index
        
        price_prefix = config_strategy.strategy_params['price_prefix']
        price_cols = [c for c in self.master_df_full.columns if c.startswith(price_prefix)]
        non_price_cols = [c for c in self.master_df_full.columns if not c.startswith(price_prefix)]
        
        self.original_start_prices = self.master_df_full[price_cols].iloc[0]
        self.original_returns_df_full = self.master_df_full[price_cols].pct_change().fillna(0.0)
        self.original_demeaned_returns_df_full = self.original_returns_df_full - self.original_returns_df_full.mean()
        self.original_non_price_df_full = self.master_df_full[non_price_cols]
        self.original_column_order = self.master_df_full.columns
        
        self.pa = performance_analyzer
        self.d_t_original = self.pa.excess_returns.dropna() 
        self.T_test = len(self.d_t_original)
        self.relevant_index = self.d_t_original.index

        if self.T_test < 30:
            warnings.warn(f"Warning: Test sample size is {self.T_test}. CLT assumption may not hold.")

        self.mean_daily = self.d_t_original.mean()
        self.std_daily = self.d_t_original.std()
        self.ir_daily = self.mean_daily / self.std_daily if self.std_daily != 0 else 0.0
        
        self.skew_active = self.pa.metrics.get('Skewness_Active', 0.0) 
        self.kurt_excess = self.pa.metrics.get('Kurtosis_Active', 0.0) 
        g4_minus_1 = self.kurt_excess + 2.0
        # Lopez de Prado 
        self.var_term_LDP = 1 - (self.skew_active * self.ir_daily) + (g4_minus_1 / 4) * (self.ir_daily**2)
        if self.var_term_LDP <= 0:
            warnings.warn("SR variance term is non-positive. PIR/MinTRL will be 0 or Inf.")
            self.var_term_LDP = 0.0

        self.t_stat_obs_non_centered = self._get_hac_tstat(self.d_t_original)
        self.t_stat_obs_centered = None # Lazy loading

        self.validation_results = {}
        self.rolling_results = pd.DataFrame()
        print(f"...Validator Initialized. Full History T={self.T_full}, Test T={self.T_test}.")
        print(f"   Observed HAC t-stat (Non-Centered): {self.t_stat_obs_non_centered:.3f}")


    # --- 1. PROBABILISTIC METRICS ---
    def calculate_pir(self, benchmark_ir_daily: float = 0.0) -> float:
        """Calculates Probabilistic Information Ratio (PIR)."""
        if self.T_test == 0 or self.var_term_LDP == 0: return 0.0
        numerator = (self.ir_daily - benchmark_ir_daily) * np.sqrt(self.T_test - 1)
        denominator = np.sqrt(self.var_term_LDP)
        z_score = numerator / denominator
        pir = norm.cdf(z_score)
        return pir
    
    def calculate_min_trl(self, target_annual_ir: float = 0., confidence_level: float = 0.95) -> float:
        """Calculates Minimum Track Record Length (MinTRL)."""
        target_ir_daily = target_annual_ir / np.sqrt(252)
        z_alpha = norm.ppf(confidence_level)
        diff = self.ir_daily - target_ir_daily
        if diff <= 0 or self.var_term_LDP == 0: return np.inf            
        numerator_term = z_alpha / diff        
        min_trl = 1 + self.var_term_LDP * (numerator_term**2)
        return min_trl/252.0

    def get_probabilistic_report(self):
        """Prints Phase 2a Report."""
        print("\n--- Probabilistic Validation Report (Phase 2a: Analytic) ---")
        pir_0 = self.calculate_pir(benchmark_ir_daily=0.0)
        min_trl_days = self.calculate_min_trl(target_annual_ir=0.0, confidence_level=0.95)
        min_trl_years = min_trl_days / 252.0 if min_trl_days != np.inf else np.inf
        
        print(f"{'Observed Annual IR':<35}: {self.pa.metrics.get('Information_Ratio', 0.0):,.3f}")
        print(f"{'Observed HAC t-stat':<35}: {self.t_stat_obs_non_centered:,.3f}")
        print("-" * 65)
        print(f"{'Probabilistic IR (P[IR>0])':<35}: {pir_0:,.2%}")
        print(f"{'Min. Track Record (Years) at 95%':<35}: {min_trl_years:,.2f}")
        print("=================================================================")
    
    def _get_hac_tstat(self, d_t_series: pd.Series) -> float:
        """
        Calculates the Newey-West HAC-consistent t-statistic for the mean.
        Core of BRC/DIR tests.
        """
        d = d_t_series.dropna().to_numpy()
        T = len(d)
        if T < 2: return 0.0
        
        max_lags = int(4 * (len(d) / 100) ** (2/9))
        X = np.ones((T, 1))
        try:
            model = sm.OLS(d, X).fit(cov_type='HAC', cov_kwds={'maxlags': max_lags})
            t_stat = float(model.tvalues[0])
        except Exception:
            return 0.0
            
        return t_stat

    def _get_avg_block_length(self, t_obs: Optional[int] = None, heuristic_power: Optional[float] = 3.0) -> float:
        """Calculates optimal average block length (ell)."""
        if t_obs is None:
            t_obs = self.T_full
        if t_obs == 0: return 1.0
        return np.floor(t_obs**(1.0 / heuristic_power))

    def _stationary_bootstrap_indices(self, t_obs: int, n_replications: int, avg_block_length: float) -> List[np.ndarray]:
        """Generates indices for Stationary Bootstrap (Vectorized)."""
        if avg_block_length <= 0: avg_block_length = 1.0
        p_stop = 1.0 / avg_block_length
        start_indices = np.random.randint(0, t_obs, size=(n_replications, t_obs))
        stop_rolls = np.random.rand(n_replications, t_obs) < p_stop
        bootstrap_indices = start_indices.copy()
        
        for i in range(1, t_obs):
            keep_index_mask = ~stop_rolls[:, i]
            bootstrap_indices[keep_index_mask, i] = (bootstrap_indices[keep_index_mask, i-1] + 1) % t_obs
            
        return [bootstrap_indices[b] for b in range(n_replications)]

    def _create_bootstrap_world(self, indices, demean, target_index=None):
        """Creates R* (Bootstrapped Master DF)."""
        src_ret = self.original_demeaned_returns_df_full if demean else self.original_returns_df_full
        
        boot_ret = src_ret.iloc[indices].values
        boot_macro = self.original_non_price_df_full.iloc[indices].values
        
        boot_prices = 100 * (1 + pd.DataFrame(boot_ret, columns=src_ret.columns)).cumprod(axis=0)
        
        R_star = pd.concat([boot_prices, pd.DataFrame(boot_macro, columns=self.original_non_price_df_full.columns)], axis=1)
        
        if target_index is not None:
            if len(R_star) > len(target_index): R_star = R_star.iloc[:len(target_index)]
            R_star.index = target_index
        else:
            R_star.index = self.full_index[:len(R_star)]
            
        return R_star[self.original_column_order]
    
    
    def _run_single_path_backtest(self, indices, demean, target_index=None, cfg_s=None, cfg_b=None):
        """Unified worker for both Global and Rolling tests."""
        cfg_s = cfg_s or copy.deepcopy(self.config_strategy)
        cfg_b = cfg_b or copy.deepcopy(self.config_benchmark)
        
        R_star = self._create_bootstrap_world(indices, demean, target_index)
        
        rf_col = cfg_s.tickers.get('risk_free_rate')
        rf_ser = R_star[rf_col] if rf_col in R_star.columns else None
        
        _, dec = generate_holistic_ranks(R_star, cfg_s)
        l_s, _ = Backtester(cfg_s, R_star, dec).run()
        l_b, _ = Backtester(cfg_b, R_star, dec).run()
        
        an = PerformanceAnalyzer(l_s, l_b, cfg_s, risk_free_series=rf_ser)
        an.portfolio_returns = an._calculate_twr_returns(an.portfolio_ledger, an.cash_flows)
        an.benchmark_returns = an._calculate_twr_returns(an.benchmark_ledger, an.cash_flows)
        d_t = (an.portfolio_returns - an.benchmark_returns).fillna(0.0).dropna()
        
        if len(d_t) < 10: return np.nan
        return self._get_hac_tstat(d_t)
        
    def _get_observed_tstat(self, demean):
        """Calculates t_obs. If demean=True, runs a single backtest on demeaned history."""
        if not demean:
            return self.t_stat_obs_non_centered
        
        # Calculate Centered Observed t-stat on demand
        print("   Calculating Centered Observed t-stat (on Flat Market)...")
        indices = np.arange(self.T_full)
        t_stat = self._run_single_path_backtest(indices, demean=True)
        return t_stat if not np.isnan(t_stat) else 0.0
            
            
    def run_brc(self, n_replications: int = 2000, demean = False) -> dict:
        """Runs BRC Centered or Non-Centered depending on demean variable"""
        label = "Centered" if demean else "Non_Centered"
        print(f"\n--- Running BRC {label} ({n_replications} sims) ---")
        
        t_obs = self._get_observed_tstat(demean)
        avg_block = self._get_avg_block_length(self.T_full)
        indices = self._stationary_bootstrap_indices(self.T_full, n_replications, avg_block)
        
        print(f"Running simulations...")
        t_stars = Parallel(n_jobs=-1, verbose=0)(delayed(self._run_single_path_backtest)(idx, demean) for idx in indices)
        t_stars = np.array([t for t in t_stars if not np.isnan(t)])
        
        p_val = np.mean(t_stars >= t_obs) if len(t_stars) > 0 else np.nan
        
        report = {'t_obs': t_obs, 'p_value': p_val, 'n': len(t_stars), 't_stars': t_stars}
        self.validation_results[label] = report
        
        print(f"   [{label}] t_obs: {t_obs:.3f} | p-value: {p_val:.4f}")
        return report

    def run_brc_rolling_test(self, window_years=5, step_months=12, n_replications=500):
            """Runs Phase 8: Rolling BRC (Local Bootstrap via Shifting)."""
            print(f"\n--- Running Rolling BRC (Win: {window_years}Y, Step: {step_months}M) ---")
            window_days = int(window_years * 252)
            step_days = int(step_months * 21)
            
            avg_block = self._get_avg_block_length(window_days)
            master_patterns = self._stationary_bootstrap_indices(window_days, n_replications, avg_block)
            
            results = []
            cfg_s, cfg_b = copy.deepcopy(self.config_strategy), copy.deepcopy(self.config_benchmark)
    
            for start_idx in range(0, self.T_full - window_days + 1, step_days):
                end_idx = start_idx + window_days
                win_dates = self.full_index[start_idx:end_idx]
                
                d_t_loc = self.d_t_original.loc[win_dates[0]:win_dates[-1]]
                if len(d_t_loc) < 30: continue
                t_obs_loc = self._get_hac_tstat(d_t_loc)
                
                for c in [cfg_s, cfg_b]: 
                    c.strategy_params['start_date'] = win_dates[0]
                    c.strategy_params['end_date'] = win_dates[-1]
    
                # Shift Indices: Local Bootstrap Logic
                abs_indices = [pat + start_idx for pat in master_patterns]
                
                t_stars = Parallel(n_jobs=-1, verbose=0)(
                    delayed(self._run_single_path_backtest)(
                        idx, False, win_dates, cfg_s, cfg_b
                    ) for idx in abs_indices
                )
                t_stars = [t for t in t_stars if not np.isnan(t)]
                
                if t_stars:
                    p_val = np.mean(np.array(t_stars) >= t_obs_loc)
                    results.append({'end_date': win_dates[-1], 't_obs': t_obs_loc, 'p_value': p_val})
                    print(f"   Win End: {win_dates[-1].date()} | t_obs: {t_obs_loc:5.2f} | p-val: {p_val:.3f}")
    
            self.rolling_results = pd.DataFrame(results).set_index('end_date')
    
    
    # --- 4. REPORTING ---

    def save_validation_plots(self, output_dir):
        """Generates plots for the markdown report (Non-Centered AND Centered)."""
        os.makedirs(output_dir, exist_ok=True)
        sns.set_theme(style="whitegrid")
        
        if 'Non_Centered' in self.validation_results:
            res = self.validation_results['Non_Centered']
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.histplot(res['t_stars'], kde=True, color='gray', stat='density', label='Random Paths', ax=ax)
            ax.axvline(res['t_obs'], color='red', linestyle='--', linewidth=2, label=f'Strategy (t={res["t_obs"]:.2f})')
            ax.set_title(f"Bootstrap Reality Check (Non-Centered)\nHypothesis: Excess Return > 0 (p-value: {res['p_value']:.4f})")
            ax.legend()
            fig.savefig(f"{output_dir}/bootstrap_distribution.png", bbox_inches='tight')
            plt.close(fig)

        if 'Centered' in self.validation_results:
            res = self.validation_results['Centered']
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.histplot(res['t_stars'], kde=True, color='orange', stat='density', label='Random Timing', ax=ax)
            ax.axvline(res['t_obs'], color='blue', linestyle='--', linewidth=2, label=f'Strategy (t={res["t_obs"]:.2f})')
            ax.set_title(f"Centered BRC (Skill vs Luck)\nHypothesis: Timing Ability > Random (p-value: {res['p_value']:.4f})")
            ax.legend()
            fig.savefig(f"{output_dir}/bootstrap_centered_distribution.png", bbox_inches='tight')
            plt.close(fig)

        if not self.rolling_results.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            self.rolling_results['p_value'].plot(ax=ax, color='purple', marker='o', linewidth=1)
            ax.axhline(0.05, color='green', linestyle='--', label='High Significance (5%)')
            ax.axhline(0.10, color='orange', linestyle=':', label='Moderate Significance (10%)')
            ax.set_title("Rolling Bootstrap P-Value (Time Robustness)")
            ax.set_ylabel("P-Value (Prob. of Luck)")
            ax.set_xlabel("Window End Date")
            ax.legend()
            fig.savefig(f"{output_dir}/rolling_pvalue.png", bbox_inches='tight')
            plt.close(fig)

    def append_to_markdown(self, md_path):
        """Appends validation section to existing report."""
        pir = self.calculate_pir(0.0)
        min_trl_years = self.calculate_min_trl(0.0) # Ora è già in anni
        brc_nc = self.validation_results.get('Non_Centered', {})
        brc_c = self.validation_results.get('Centered', {})
        
        try:
            with open(md_path, "a", encoding="utf-8") as f:
                f.write("\n\n# 7. Advanced Statistical Validation\n")
                
                f.write("## 7.1 Probabilistic Metrics (Lopez de Prado)\n")
                f.write(f"- **Probabilistic IR (P[IR>0]):** {pir:.2%}\n")
                
                if min_trl_years > 100:
                    trl_str = "> 100 Years (Not Significant)" 
                else:
                    trl_str = f"{min_trl_years:.1f} Years"
                f.write(f"- **Min Track Record (95% Conf.):** {trl_str}\n\n")
                
                if brc_nc:
                    f.write("## 7.2 Bootstrap Reality Check (Non-Centered)\n")
                    f.write(f"- **Observed t-stat:** {brc_nc.get('t_obs',0):.3f}\n")
                    f.write(f"- **Bootstrap p-value:** {brc_nc.get('p_value',1.0):.4f}\n")
                    f.write("![Bootstrap Dist](plots/bootstrap_distribution.png)\n\n")
                
                if brc_c:
                    f.write("## 7.3 BRC Centered (Skill vs Luck)\n")
                    f.write(f"- **Centered t-stat:** {brc_c.get('t_obs',0):.3f}\n")
                    f.write(f"- **Centered p-value:** {brc_c.get('p_value',1.0):.4f}\n")
                    f.write("![Bootstrap Centered](plots/bootstrap_centered_distribution.png)\n\n")

                if not self.rolling_results.empty:
                    f.write("## 7.4 Rolling Time Robustness\n")
                    f.write("![Rolling P-Value](plots/rolling_pvalue.png)\n")
        except Exception as e:
            print(f"Error appending to MD: {e}")

    def finalize_validation(self):
        # 1. Run Tests
        self.run_brc(n_replications=5000, demean=False)
        self.run_brc(n_replications=5000, demean=True)
        self.run_brc_rolling_test(window_years=10, n_replications=2000)
        
        # 2. Reporting
        out_dir = self.reporting_config.get('output_path', 'reports')
        self.save_validation_plots(os.path.join(out_dir, 'plots'))
        self.append_to_markdown(os.path.join(out_dir, 'STRATEGY_REPORT.md'))
        print(f"--- Validation Complete. Report Updated. ---")