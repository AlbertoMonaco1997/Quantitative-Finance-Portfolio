import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS


def calculate_weighted_returns(master_df, col_names, lookbacks_and_weights={3: 1/3, 6: 1/3, 12: 1/3}, ignore_last_month = True, price_prefix = "price_", metric_suffix = "_USD" ):
    
    """
    Calculate weighted (as expressed in "lookbacks_and_weights") annualized returns'  averages for all columns in "col_names".
    Choose if the last month has to be included or not. 
    Normalizing returns to monthly equivalent to compare different lookbacks fairly
    """
    relevant_cols = [f"{price_prefix}{col}{metric_suffix}" for col in col_names]
    existing_cols = [c for c in relevant_cols if c in master_df.columns]
    
    if not existing_cols:
        return pd.DataFrame()

    monthly_prices = master_df[existing_cols].resample('ME').last()
    monthly_prices.columns = [    c.removeprefix(price_prefix).removesuffix(metric_suffix) for c in monthly_prices.columns]
    
    shifter = 1 if ignore_last_month else 0
    return_score = pd.DataFrame(0.0, index=monthly_prices.index, columns=monthly_prices.columns)
    for l, weight in lookbacks_and_weights.items():
        l = int(l) 
        aux_returns = monthly_prices.pct_change(periods=l-shifter).shift(shifter)
        aux_returns = ((1 + aux_returns)**(1/(l-shifter)) - 1) 
        if not aux_returns.empty:
                return_score = return_score.add(aux_returns * weight, fill_value=0)
        
    return_score.columns = col_names
        
    return return_score


def calculate_pure_momentum_signal(master_df, config):
        
    """
    Calculates a composite momentum signal based on a
    dictionary of lookback periods (in months) and their corresponding weights.
    Sets to nan the whole day if at least a value is missing.
    """
    
    satellite_candidates = config.get_satellite_candidates()
    if not satellite_candidates: return pd.DataFrame()
    
    return_score = calculate_weighted_returns(
        master_df, 
        satellite_candidates, 
        config.signals['lookbacks_and_weights'],
        price_prefix=config.strategy_params['price_prefix']
    )
    momentum_ranks = return_score.rank(axis=1, ascending=False, method='average')
    # set to nan the whole day if at least a value is missing
    incomplete_rows_mask = momentum_ranks.isnull().any(axis=1)
    momentum_ranks[incomplete_rows_mask] = np.nan
    
    return momentum_ranks

def calculate_sharpe_momentum_signal(master_df, config):
    """
    Calculates the risk-adjusted momentum signal.
    Default choice: ((12M Return + 6M Return + 3M Return) / 6M Volatility).
    Returns a DataFrame with the ranks.
    Sets to nan the whole day if at least a value is missing.
    """
    
    satellite_candidates = config.get_satellite_candidates()
    if not satellite_candidates: return pd.DataFrame()

    return_score = calculate_weighted_returns(
        master_df, 
        satellite_candidates, 
        config.signals['lookbacks_and_weights'],
        price_prefix=config.strategy_params['price_prefix']
    )
    
    # Get volatility data dynamically
    vola_cols = [f"{factor}_VOLA_180D" for factor in satellite_candidates]
    existing_vola = [c for c in vola_cols if c in master_df.columns]
    
    if not existing_vola:
        return pd.DataFrame() # No vola, no signal

    monthly_vola_180d = master_df[existing_vola].resample('ME').last()
    monthly_vola_180d.columns = [c.replace("_VOLA_180D", "") for c in monthly_vola_180d.columns]
    
    return_score, monthly_vola_180d = return_score.align(monthly_vola_180d, axis=1, join='inner')    
    composite_sharpe_score = return_score.div(monthly_vola_180d)
        
    sharpe_momentum_ranks = composite_sharpe_score.rank(axis=1, ascending=False, method='average')
    # set to nan the whole day if at least a value is missing
    incomplete_rows_mask = sharpe_momentum_ranks.isnull().any(axis=1)
    sharpe_momentum_ranks[incomplete_rows_mask] = np.nan
    
    return sharpe_momentum_ranks

def obtain_z_score(master_df, metric_suffix, window=48, candidates=[]):
    """
    Helper function. Calculates the rolling z-score for a single metric.
    'metric' should be a string like 'Price_to_Book' or 'Price_to_Earnings'.
    Time horizon starts from a minimum of window//2 and is up to window value.
    Returns a DataFrame of raw z-scores.
    """
    
    relevant_cols = []
    clean_names = []
    # Select columns containing metric in the name
    for col in master_df.columns:
        for cand in candidates:
            if col == f"{cand}_{metric_suffix}":
                relevant_cols.append(col)
                clean_names.append(cand)
    
    if not relevant_cols:
        return pd.DataFrame()

    monthly_metric_data = master_df[relevant_cols].resample('ME').last()
    monthly_metric_data.columns = clean_names  
    # z-score calculation
    rolling_mean = monthly_metric_data.rolling(window=window, min_periods=window//2).mean()
    rolling_std = monthly_metric_data.rolling(window=window, min_periods=window//2).std()
    rolling_std = rolling_std.replace(0, np.nan) 
    
    z_score = (monthly_metric_data - rolling_mean) / rolling_std
    z_score.columns = [col.split('_')[0] for col in z_score.columns]
    
    return z_score


def calculate_valuation_signal(master_df, config):
    """
    Main function. Calculates a composite valuation signal by calling the helper
    to get z-scores, weighting them, and then ranking the final composite score.
    """
    satellite_candidates = config.get_satellite_candidates()
    composite_z_score = pd.DataFrame()
    
    # obtain z-scores
    for metric, weight in config.signals['valuation_metrics'].items():
        aux_z_score = obtain_z_score(master_df, metric, config.signals['valuation_window'], satellite_candidates)
        
        # weighting and cumulating scores
        if not aux_z_score.empty:
            if composite_z_score.empty:
                composite_z_score = aux_z_score * weight
            else:
                composite_z_score = composite_z_score.add(aux_z_score * weight, fill_value=0)
            
    # Rank based on the lowest composite z-score (lower is better)
    if composite_z_score.empty:
        return pd.DataFrame()
    valuation_ranks = composite_z_score.rank(axis=1, ascending=True, method='average')
    # set to nan the whole day if at least a value is missing
    incomplete_rows_mask = valuation_ranks.isnull().any(axis=1)
    valuation_ranks[incomplete_rows_mask] = np.nan
    
    return valuation_ranks

def adjust_beta_vasicek(raw_betas, beta_std_errors, prior_mean=1.0, use_fixed_prior=True):
    """
    Apply Vasicek adjustment to betas.
    Prior mean can be fixed due to a low number of assets in use
    """
    raw_betas_val = raw_betas.values 
    var_obs_val = (beta_std_errors.values) ** 2
    var_cross_val = raw_betas.var(axis=1).values.reshape(-1, 1)
    weight_val = var_cross_val / (var_cross_val + var_obs_val)
    
    if use_fixed_prior:
        prior_val = np.full_like(raw_betas_val, prior_mean)
    else:
        prior_val = raw_betas_val.mean(axis=1, keepdims=True)

    adj_betas_val = (weight_val * raw_betas_val) + ((1 - weight_val) * prior_val)
    
    adjusted_betas = pd.DataFrame(
        adj_betas_val, 
        index=raw_betas.index, 
        columns=raw_betas.columns
    )
    
    return adjusted_betas

def calculate_alpha_beta(master_df, config):
    """
    Calculates Rolling Alpha/Beta vs Benchmark.
    Vasicek Adjustment applied to rolling historical betas.
    Future evolution: Kalman Filter    
    """
    satellite_candidates = config.get_satellite_candidates()
    benchmark_ticker = config.get_benchmark_ticker()
    price_prefix = config.strategy_params['price_prefix']
    currency = config.strategy_params['calculation_currency']
    window = config.signals['alpha_beta_window']
    rf_col = config.tickers['risk_free_rate']
    
    cand_cols = [f"{price_prefix}{c}_{currency}" for c in satellite_candidates]
    bench_col = f"{price_prefix}{benchmark_ticker}_{currency}"
    
    available_cands = [c for c in cand_cols if c in master_df.columns]
    
    if bench_col not in master_df.columns or rf_col not in master_df.columns or not available_cands:
        return pd.DataFrame(), pd.DataFrame()

    cols_to_use = list(dict.fromkeys(available_cands + [bench_col, rf_col]))
    monthly_prices = master_df[cols_to_use].resample('ME').last()
    monthly_returns = monthly_prices.pct_change().dropna()
    
    rf = monthly_returns[rf_col]
    excess_bench = monthly_returns[bench_col].sub(rf, axis=0)
    excess_cands = monthly_returns[available_cands].sub(rf, axis=0)
    excess_bench.name = "Mkt_RF"
    
    if len(excess_cands) < window:
        return pd.DataFrame(), pd.DataFrame()

    exog = sm.add_constant(excess_bench)
    
    raw_betas_dict = {}
    bse_dict = {}

    for col in excess_cands.columns:
        if col == bench_col:
            # if benchmark and candidate index are the same, set to 1 beta and alpha to 0
            raw_betas_dict[col] = pd.Series(1.0, index=excess_cands.index)
            bse_dict[col] = pd.Series(0.0, index=excess_cands.index)
            continue
        
        endog = excess_cands[col]
        
        rols = RollingOLS(endog, exog, window=window)
        rres = rols.fit()
        
        raw_betas_dict[col] = rres.params["Mkt_RF"]
        bse_dict[col] = rres.bse["Mkt_RF"]

    raw_betas = pd.DataFrame(raw_betas_dict, index=excess_cands.index)
    beta_std_errors = pd.DataFrame(bse_dict, index=excess_cands.index)
    
    final_betas = adjust_beta_vasicek(raw_betas, beta_std_errors, prior_mean=1.0, use_fixed_prior=True)
    
    mean_y = excess_cands.rolling(window).mean()
    mean_x = excess_bench.rolling(window).mean()
    
    final_alphas = mean_y - final_betas.mul(mean_x, axis=0)
    
    clean_cols = [
        c.replace(price_prefix, "").replace(f"_{currency}", "") 
        for c in available_cands
    ]
    final_alphas.columns = clean_cols
    final_betas.columns = clean_cols
    
    return final_alphas.dropna().astype(float), final_betas.dropna().astype(float)

def calculate_alpha_signal(master_df, config):
    alphas, _ = calculate_alpha_beta(master_df, config)
    if alphas.empty: return pd.DataFrame()
    # Higher alpha is better
    rank = alphas.rank(axis=1, ascending=False, method='average')
    rank[rank.isnull().any(axis=1)] = np.nan
    return rank

def calculate_beta_signal(master_df, config):
    _, betas = calculate_alpha_beta(master_df, config)
    if betas.empty: return pd.DataFrame()
    # Lower beta is better (Betting Against Beta)
    rank = betas.rank(axis=1, ascending=True, method='average')
    rank[rank.isnull().any(axis=1)] = np.nan
    return rank
   
def calculate_macro_signal(master_df, config):
    """
    Calculates the Macro signal based on the inflation regime, with dynamic ranking
    for Quality and Size.
    Inflationary regime (True): Value > Quality > Size > Momentum
    Deflationary regime (False): Momentum > Size > Quality > Value
    """
    if 'CPI_YoY' not in master_df.columns:
        return pd.DataFrame()
        
    # check if the candidates are msci factors
    satellite_candidates = set(config.get_satellite_candidates())
    required_factors = {'VALUE', 'MOMENTUM', 'QUALITY', 'SIZE'}
    
    # if not, skip signal
    if not required_factors.issubset(satellite_candidates):
        return pd.DataFrame()

    # Standard MSCI Factors (Inflation Regime) ---
    monthly_cpi = master_df['CPI_YoY'].resample('ME').last()
    cpi_ma_3m = monthly_cpi.rolling(window=3, min_periods=3).mean()
    cpi_ma_12m = monthly_cpi.rolling(window=12, min_periods=12).mean()
    cpi_ma_36m = monthly_cpi.rolling(window=36, min_periods=36).mean()
    
    # naive analisys for inflationary regime
    is_inflationary = cpi_ma_3m > np.maximum(cpi_ma_12m, cpi_ma_36m)
    
    factor_names = list(required_factors) # Solo sui 4 noti
    macro_ranks = pd.DataFrame(index=is_inflationary.index, columns=factor_names)
    
    # Inflationary: Value > Quality > Size > Momentum
    macro_ranks.loc[is_inflationary, 'VALUE'] = 1.0
    macro_ranks.loc[is_inflationary, 'QUALITY'] = 2.0
    macro_ranks.loc[is_inflationary, 'SIZE'] = 3.0
    macro_ranks.loc[is_inflationary, 'MOMENTUM'] = 4.0
    
    # Deflationary: Momentum > Size > Quality > Value
    macro_ranks.loc[~is_inflationary, 'MOMENTUM'] = 1.0
    macro_ranks.loc[~is_inflationary, 'SIZE'] = 2.0
    macro_ranks.loc[~is_inflationary, 'QUALITY'] = 3.0
    macro_ranks.loc[~is_inflationary, 'VALUE'] = 4.0
    
    final_ranks = macro_ranks.dropna(how='any')
    final_ranks[final_ranks.isnull().any(axis=1)] = np.nan
    
    return final_ranks

def generate_holistic_ranks(master_df, config):
    """
    Generates the final holistic score and the definitive rank for factor selection.
    if a signal si nan in a specific day, it will be skipped.
    If two factors have the same rank, the previous winner will be chosen,
    if neither of those is the previous winner o the previous winner in None,
    the one with higher alpha will be the winner.
    Args:
        master_df (pd.DataFrame): The main data DataFrame.
        config (Config): The configuration object.
        previous_holdings (pd.Series, optional): A Series with the factor held in the previous period,
                                                 indexed by date. Needed for the inertia tie-breaker.

    Returns:
        pd.DataFrame: A DataFrame with the final, single rank (1=best) for each month.
    """

    signals_and_weights = config.signals['signals_to_use']
    satellite_candidates = config.get_satellite_candidates()

    signal_functions = {
        'sharpe_momentum': calculate_sharpe_momentum_signal,
        'pure_momentum': calculate_pure_momentum_signal,
        'valuation': calculate_valuation_signal,
        'alpha': calculate_alpha_signal,
        'beta': calculate_beta_signal,
        'macro': calculate_macro_signal
    }

    all_ranks_dict = {}
    total_weight = sum(signals_and_weights.values())
    if total_weight > 0:
        signals_and_weights = {k: v / total_weight for k, v in signals_and_weights.items()}
    for signal_name, weight in signals_and_weights.items():
        if weight > 0 and signal_name in signal_functions:
            ranks_df = signal_functions[signal_name](master_df, config)
            if not ranks_df.empty:
                all_ranks_dict[signal_name] = ranks_df

    master_monthly_index = master_df.resample('ME').last().index
    numerator = pd.DataFrame(0.0, index=master_monthly_index, columns=satellite_candidates)
    denominator = pd.DataFrame(0.0, index=master_monthly_index, columns=satellite_candidates)

    for signal_name, weight in signals_and_weights.items():
        if signal_name in all_ranks_dict:
            ranks_df = all_ranks_dict[signal_name].copy()
            ranks_df_aligned = ranks_df.reindex(index=master_monthly_index, columns=satellite_candidates)
            valid_mask = ranks_df_aligned.notna()
            safe_ranks = ranks_df_aligned.astype(float).fillna(0)
            
            numerator = numerator.add(safe_ranks * weight, fill_value=0)
            denominator = denominator.add(valid_mask.astype(float) * weight, fill_value=0)
            
    denominator = denominator.replace(0, np.nan)
    holistic_score = numerator.div(denominator)
    holistic_score.dropna(how='all', inplace=True)

    # --- TIE-BREAKING LOGIC ---
    final_decision = pd.Series(index=holistic_score.index, dtype=object, name="winner")
    
    aligned_alphas = None 
    
    previous_winner = None
    
    for date, row in holistic_score.iterrows():
        if row.isnull().all():
            winner = previous_winner
        else:
            min_score = row.min()
            tied_winners = row[row == min_score].index.tolist()
            
            winner = None
            if len(tied_winners) == 1:
                winner = tied_winners[0]
            else:
                # Tie Break 1: Inertia
                winner_found = False
                if previous_winner in tied_winners:
                    winner = previous_winner
                    winner_found = True
                
                # Tie Break 2: Alpha 
                if not winner_found:
                    if aligned_alphas is None:
                        try:
                            raw_alphas, _ = calculate_alpha_beta(master_df, config)
                            aligned_alphas = raw_alphas.reindex(holistic_score.index, method='ffill')
                        except Exception:
                            aligned_alphas = pd.DataFrame() # Empty df fallback


                    if not aligned_alphas.empty and date in aligned_alphas.index:
                        valid_cols = [c for c in tied_winners if c in aligned_alphas.columns]
                        if valid_cols:
                            alpha_vals = aligned_alphas.loc[date, valid_cols]
                            if not alpha_vals.isna().all():
                                winner = alpha_vals.idxmax()
                            else:
                                winner = sorted(tied_winners)[0]
                        else:
                            winner = sorted(tied_winners)[0]
                    else:
                        winner = sorted(tied_winners)[0] 
        
        final_decision[date] = winner
        if winner is not None:
            previous_winner = winner

    return holistic_score, final_decision