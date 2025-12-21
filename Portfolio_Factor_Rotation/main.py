import os
import warnings
import traceback 

# Custom modules
from config_loader import Config
from data_loader import load_all_data
from signal_engine import generate_holistic_ranks
from backtest_engine import Backtester
from performance_analyzer import PerformanceAnalyzer
from strategy_validator import StrategyValidator

# Clean output for presentation
warnings.filterwarnings('ignore')

def run_pipeline():

    # ---------------------------------------------------------
    # 1. SETUP & CONFIGURATION
    # ---------------------------------------------------------
    print("\n[1] Loading Configuration & Data...")
    
    config_path = 'config.json'
    if not os.path.exists(config_path):
        print(f"ERROR: {config_path} not found.")
        return

    config_strat = Config(config_path)
    
    # Load Data (Asset Agnostic)
    master_df = load_all_data(config_strat)
    
    if master_df is None or master_df.empty:
        print("CRITICAL ERROR: Failed to load data. Exiting pipeline.")
        return

    # ---------------------------------------------------------
    # 2. SIGNAL GENERATION
    # ---------------------------------------------------------
    print("\n[2] Generating Proprietary Signals...")
    holistic_score, final_decision = generate_holistic_ranks(master_df, config_strat)
    
    print(f"    > Signals generated from {holistic_score.index[0].date()} to {holistic_score.index[-1].date()}")

    # ---------------------------------------------------------
    # 3. BACKTESTING (STRATEGY vs BENCHMARK)
    # ---------------------------------------------------------
    print("\n[3] Running Backtest Engines...")
    
    # A. Active Strategy
    print("    > Executing Active Strategy...")
    backtester_strat = Backtester(
        config=config_strat,
        master_df=master_df,
        signals_df=final_decision
    )
    ledger_strat, _ = backtester_strat.run()
    
    # B. Benchmark (100% MSCI World)
    print("    > Executing Benchmark (Passive MSCI World)...")
    config_bench = Config(config_path) 
    # Align Benchmark params with Strategy
    config_bench.strategy_params.update({
        'core_target_weight': 1.0, # 100% Core
    })
    # Force Benchmark Allocation
    config_bench.universe['core_allocation'] = { 
        "VALUE": 0.0, "MOMENTUM": 0.0, "QUALITY": 0.0, "SIZE": 0.0, "WORLD": 1.0
    }
    
    backtester_bench = Backtester(
        config=config_bench,
        master_df=master_df,
        signals_df=final_decision # Passed but ignored by core_target_weight=1.0
    )
    ledger_bench, _ = backtester_bench.run()

    # ---------------------------------------------------------
    # 4. PERFORMANCE ANALYSIS
    # ---------------------------------------------------------
    print("\n[4] Analyzing Performance...")
    
    analyzer = PerformanceAnalyzer(
        portfolio_ledger=ledger_strat,
        benchmark_ledger=ledger_bench,
        config=config_strat,
        satellite_history=backtester_strat.satellite_history
    )
       
    # Generate static report and plots
    analyzer.finalize_report()

    # ---------------------------------------------------------
    # 5. ADVANCED STATISTICAL VALIDATION (Bootstrap)
    # ---------------------------------------------------------
    print("\n" + "="*60)
    print("   ADVANCED STATISTICAL VALIDATION")
    print("="*60)

    try:
        validator = StrategyValidator(
            config_strategy=config_strat, 
            config_benchmark=config_bench, 
            master_df=master_df, 
            performance_analyzer=analyzer
        )
        
        validator.finalize_validation()
        
    except Exception:
        print("CRITICAL ERROR in Strategy Validator:")
        traceback.print_exc()

    print("\n" + "="*60)
    print("   PIPELINE COMPLETE. CHECK 'reports/STRATEGY_REPORT.md'")
    print("="*60)

if __name__ == '__main__':
    # Ensure reports directory exists
    os.makedirs('reports', exist_ok=True)
    os.makedirs('reports/plots', exist_ok=True)
    
    run_pipeline()