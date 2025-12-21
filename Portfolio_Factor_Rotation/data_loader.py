import pandas as pd
import os
import numpy as np
import pandas_datareader.data as web

def get_fred_data(ticker, start_date, end_date, data_dir="data", metric_name="Data"):
    """
    Save datas from FRED and save them on a CSV.
    """
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{ticker}.csv")
    
    # 1. Cache
    if os.path.exists(file_path):
        try:
            data = pd.read_csv(file_path, index_col=0, parse_dates=True)
            return data
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
                print(f"      [Cache] Error reading {file_path}, redownloading...")

    # 2. Web Download
    try:
        data = web.DataReader(ticker, 'fred', start_date, end_date)
        data.to_csv(file_path)
        return data
    except Exception as e:
        print(f"      WARNING: Could not download {metric_name} ({ticker}): {e}")
        return pd.DataFrame()
    
    
def winsorize_columns(df, column_list, quantile):
    """
    Helper function to apply winsorizing to a list of columns in a DataFrame.
    """
    df_copy = df.copy()
    for col in column_list:
        if col in df_copy.columns:
            lower_bound = df_copy[col].quantile(1 - quantile)
            upper_bound = df_copy[col].quantile(quantile)
            df_copy[col] = df_copy[col].clip(lower=lower_bound, upper=upper_bound)
    return df_copy

def clean_data(df, price_cols_prefix, winsorize_quantile):
    """
    Cleans the master DataFrame by handling negative values and
    winsorizing all relevant signal-driving metrics.
    """
    cleaned_df = df.copy()
    
    # 1. Handle illogical negative values in valuation metrics
    signal_cols = [col for col in cleaned_df.columns if not col.startswith(price_cols_prefix)]
    # HARDCODED: Filter logic specific to current dataset naming convention
    cols_no_negative = [c for c in signal_cols if "Price_to" in c or "VOLA" in c]
    for col in cols_no_negative:
        cleaned_df[col] = cleaned_df[col].apply(lambda x: x if x > 0 else np.nan)
        
    # 2. Winsorize signal metrics (Monthly basis)
    if signal_cols:
        monthly_metrics = cleaned_df[signal_cols].resample('ME').last()
        winsorized_monthly = winsorize_columns(monthly_metrics, signal_cols, winsorize_quantile)
        cleaned_df.update(winsorized_monthly)

    cleaned_df.ffill(inplace=True)
    
    return cleaned_df

def process_info_sheet(file_path, sheet_name, metric_suffix, column_mapping):
    """Reads one sheet from the extra_info file genericly."""
    try:
        df_sheet = pd.read_excel(file_path, sheet_name=sheet_name)
        all_factor_series = []
        
        for i in range(0, len(df_sheet.columns), 2):
            if i+1 >= len(df_sheet.columns): break
            date_col = df_sheet.iloc[:, i]
            value_col = df_sheet.iloc[:, i+1]
            factor_full_name = value_col.name
            
            if factor_full_name in column_mapping:
                short_name = column_mapping[factor_full_name]
                factor_df = pd.DataFrame({'Date': date_col, 'Value': value_col}).dropna().set_index('Date')
                factor_df.rename(columns={'Value': f"{short_name}_{metric_suffix}"}, inplace=True)
                all_factor_series.append(factor_df)

        if all_factor_series:
            return pd.concat(all_factor_series, axis=1)
    except Exception:
        pass
    return pd.DataFrame()

def load_all_data(config):
    """
    Main function to load, merge, and clean all data sources.
    Completely Asset-Agnostic.
    """
    data_dir = config.paths['data_dir']
    
    # Load Price Data  ---
    price_file_path = os.path.join(data_dir, config.files['price_file'])
    try:
        price_data = pd.read_excel(price_file_path, index_col='Date', parse_dates=True, sheet_name='Performance Data')
        
        excel_map = config.mappings.get('excel_column_map', {})
        valid_cols = [c for c in price_data.columns if c in excel_map]
        
        price_data = price_data[valid_cols].rename(columns=excel_map)
        price_data = price_data.add_prefix(config.strategy_params['price_prefix'])
        price_data = price_data.add_suffix(f"_{config.strategy_params['calculation_currency']}")
    except Exception as e:
        print(f"   CRITICAL ERROR: Could not load price data. {e}")
        return None

    # Load Extra Info Data  ---
    print("\n2. Loading Extra Info Data (Dynamic)...")
    extra_info_file_path = os.path.join(data_dir, config.files['extra_info_file'])
    extra_data_frames = []
    
    
    sheet_map = config.mappings.get('sheet_names', {})
    for metric_key, sheet_name in sheet_map.items():
        
        df_metric = process_info_sheet(extra_info_file_path, sheet_name, metric_key, excel_map)
        if not df_metric.empty:
            extra_data_frames.append(df_metric)

    # Download Tickers from FRED  ---
    print("\n3. Downloading External Tickers (FRED)...")
    start_date = price_data.index.min()
    end_date = price_data.index.max()
    macro_frames = []
    
    tickers_map = config.tickers # es. {"cpi": "CPIAUCSL", "risk_free": "TB3MS"}
    
    for key, ticker in tickers_map.items():
        print(f"   -> Getting {key} ({ticker})...")
        data = get_fred_data(ticker, start_date, end_date, data_dir, key)
        # Specific transformation rules for macro indicators
        if not data.empty:
            
            if key.lower() == 'cpi':
                data = data.pct_change(12) * 100
                data.columns = ['CPI_YoY']
            
            # change in monthly
            elif key.lower() == 'risk_free_rate':
                data = (data / 100) / 12
                
            
            macro_frames.append(data)

    # Merge Everything ---
    print("\n4. Merging all data sources...")
    
    dfs_to_merge = extra_data_frames + macro_frames
    final_df = price_data.join(dfs_to_merge, how='left')
    
    # Forward fill 
    final_df.ffill(inplace=True)
    
    # Clean ---
    final_df = clean_data(final_df, config.strategy_params['price_prefix'], config.cleaning['winsorize_quantile'])
    
    return final_df