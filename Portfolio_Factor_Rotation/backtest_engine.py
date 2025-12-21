import pandas as pd
from collections import namedtuple, defaultdict

Lot = namedtuple('Lot', ['quantity', 'purchase_price', 'purchase_date'])

class Portfolio:
    """
    Represents the state of the investment portfolio at any given time.
    It holds cash, positions (as lots), and a history of its value.
    It does not contain any strategy logic.
    """
    def __init__(self, initial_capital, start_date, asset_tickers, config):
        
        self.config = config
        
        # --- Core Attributes ---
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.asset_tickers = asset_tickers
        # --- Position Tracking ---
        # A dictionary to hold the lots for each asset.
        # Example: {'VALUE': [Lot(10, 95.5, '2020-01-01'), Lot(5, 98.0, '2020-02-01')]}
        self.positions = defaultdict(lambda: {'core': [], 'satellite': []})
        
        # --- Tax Management (Italian "Zainetto Fiscale") ---
        self.tax_loss_carryforward = 0.0
        self.tax_rate = self.config.strategy_params.get('capital_gains_tax_rate')
        self.transaction_cost_pct = self.config.strategy_params.get('transaction_cost_pct')
        # --- Historical Logging (The "Ledger") ---
        # A DataFrame to store the state of the portfolio over time.
        ledger_columns = ['total_value', 'cash', 'market_value']
        for ticker in asset_tickers:
            ledger_columns.extend([f'value_{ticker}', f'quantity_{ticker}', f'weight_{ticker}'])
        self.ledger = pd.DataFrame(columns=ledger_columns)
        
        # Record the initial state at T-1
        initial_state = {
            'total_value': self.initial_capital,
            'cash': self.cash,
            'market_value': 0.0
        }
        # The ledger starts one day before the simulation for correct return calculation
        self.ledger.loc[pd.to_datetime(start_date) - pd.DateOffset(days=1)] = initial_state
        
    def _get_total_quantity(self, ticker):
        """Helper to get total quantity for a ticker across core and satellite."""
        core_qty = sum(lot.quantity for lot in self.positions[ticker]['core'])
        sat_qty = sum(lot.quantity for lot in self.positions[ticker]['satellite'])
        return core_qty + sat_qty

    def update_market_value(self, current_prices):
        """Calculates total market value summing core and satellite holdings."""
        market_value = 0.0
        price_prefix = self.config.strategy_params['price_prefix']
        currency = self.config.strategy_params['calculation_currency']
        
        for ticker in self.asset_tickers: # Iterate through all possible tickers
            total_quantity = self._get_total_quantity(ticker)
            if total_quantity > 0:
                full_price_col_name = f"{price_prefix}{ticker}_{currency}"
                price = current_prices.get(full_price_col_name, 0)
                market_value += total_quantity * price
                
        return market_value

    def record_daily_state(self, date, current_prices):
        """Calculates and records the detailed daily state, summing core/satellite."""
        market_value = self.update_market_value(current_prices)
        total_value = self.cash + market_value
        
        new_row_data = {
            'total_value': total_value,
            'cash': self.cash,
            'market_value': market_value
        }

        price_prefix = self.config.strategy_params['price_prefix']
        currency = self.config.strategy_params['calculation_currency']

        for ticker in self.asset_tickers:
            full_price_col_name = f"{price_prefix}{ticker}_{currency}"
            quantity = self._get_total_quantity(ticker) 
            value = quantity * current_prices.get(full_price_col_name, 0)
            weight = value / total_value if total_value > 0 else 0
            
            new_row_data[f'value_{ticker}'] = value
            new_row_data[f'quantity_{ticker}'] = quantity
            new_row_data[f'weight_{ticker}'] = weight
            
        self.ledger.loc[date] = new_row_data


    def transact_shares(self, date, ticker, quantity, price, allocation_type):
        """
        Executes a trade (buy or sell) and updates the portfolio state,
        including FIFO accounting and tax calculation for sales.
        """

        trade_value = abs(quantity) * price
        cost = trade_value * self.transaction_cost_pct

        # --- Purchase
        if quantity > 0:
            if self.cash < trade_value + cost:
                if self.cash + 1e-10 < trade_value + cost:
                    # print(f"WARNING {date}: Insufficient cash for BUY {quantity} {ticker}. Trade skipped.")
                    return False
                else:
                    quantity = (self.cash-1e-10)/(1+self.transaction_cost_pct)/price
                    trade_value = abs(quantity) * price
                    cost = trade_value * self.transaction_cost_pct

            self.cash -= (trade_value + cost)
            new_lot = Lot(quantity=quantity, purchase_price=price, purchase_date=date)
            self.positions[ticker][allocation_type].append(new_lot)
            return True 

        # --- Sell
        elif quantity < 0:
            quantity_to_sell = abs(quantity)
            
            satellite_lots = self.positions[ticker]['satellite']
            total_quantity_held = sum(lot.quantity for lot in satellite_lots)
            if total_quantity_held + 1e-8 < quantity_to_sell:
                if total_quantity_held < quantity_to_sell:                
                    # print(f"WARNING {date}: Insufficient shares for SELL {quantity_to_sell} {ticker} (Satellite). Skipped.")
                    return False
                else:
                    quantity_to_sell = total_quantity_held

            # 2. FIFO Logic
            realized_gain_loss = 0.0
            lots_to_remove = []
            
            for i, lot in enumerate(satellite_lots):
                if quantity_to_sell < 1e-8:
                    break

                sell_from_this_lot = min(quantity_to_sell, lot.quantity)
                
                realized_gain_loss += (price - lot.purchase_price) * sell_from_this_lot
                
                # update lot quantity
                if sell_from_this_lot < lot.quantity:
                    self.positions[ticker][i] = lot._replace(quantity=lot.quantity - sell_from_this_lot)
                else:
                    lots_to_remove.append(i)
                
                quantity_to_sell -= sell_from_this_lot
            
            
            for i in sorted(lots_to_remove, reverse=True):
                del self.positions[ticker]['satellite'][i]

            # 3.Update zainetto fiscale and calculate taxes
            tax_due = 0.0
            if realized_gain_loss > 0:
                
                usable_loss = min(realized_gain_loss, self.tax_loss_carryforward)
                taxable_gain = realized_gain_loss - usable_loss
                self.tax_loss_carryforward -= usable_loss
                
                tax_due = taxable_gain * self.tax_rate
            else: 
                self.tax_loss_carryforward += abs(realized_gain_loss)

            self.cash += (trade_value - cost - tax_due)
            
            return True 

    def get_total_value(self, current_prices):
        """
        Returns the total equity of the portfolio (cash + market value of positions).
        """
        market_value = self.update_market_value(current_prices)
        return self.cash + market_value

    def get_current_weights(self, current_prices):
        """Calculates total weights (cash + assets), summing core/satellite."""
        total_value = self.get_total_value(current_prices)
        if total_value == 0: return {'CASH': 1.0}

        weights = {'CASH': self.cash / total_value}
        price_prefix = self.config.strategy_params['price_prefix']
        currency = self.config.strategy_params['calculation_currency']
        
        for ticker in self.asset_tickers:
            full_price_col_name = f"{price_prefix}{ticker}_{currency}"
            total_quantity = self._get_total_quantity(ticker) 
            market_value = total_quantity * current_prices.get(full_price_col_name, 0)
            weights[ticker] = market_value / total_value
            
        return weights 
    
    def get_internal_core_weights(self, current_prices):
        """
        Calculates the weights of assets ONLY within the Core allocation.
        """
        core_market_values = {}
        total_core_value = 0.0
        price_prefix = self.config.strategy_params['price_prefix']
        currency = self.config.strategy_params['calculation_currency']

        for ticker in self.asset_tickers:
            core_lots = self.positions[ticker]['core']
            if core_lots:
                quantity = sum(lot.quantity for lot in core_lots)
                price_col = f"{price_prefix}{ticker}_{currency}"
                price = current_prices.get(price_col, 0)
                value = quantity * price
                core_market_values[ticker] = value
                total_core_value += value
        
        internal_weights = {}
        if total_core_value > 0:
            for ticker, value in core_market_values.items():
                internal_weights[ticker] = value / total_core_value
        
        return internal_weights
    

class Backtester:
    """
    Orchestrates the backtest simulation. It contains the strategy logic,
    manages the event loop, and instructs the Portfolio object.
    """
    def __init__(self, config, master_df, signals_df):
        """
        Initializes the Backtester with all necessary data and strategy rules.
        """
        
        self.config = config
        self.data = master_df
        self.signals = signals_df
        
        req_start = pd.to_datetime(config.strategy_params['start_date'])
        valid_idx = self.data.index
        future_dates = valid_idx[valid_idx >= req_start]
        self.start_date = future_dates[0] 
        self.end_date = pd.to_datetime(config.strategy_params['end_date'])
        
        self.mode = config.strategy_params.get('backtest_mode', 'portfolio') # 'portfolio' or 'index'
        self.pac_frequency = config.strategy_params.get('pac_frequency') # 'BMS'
        self.rebalance_frequency = config.strategy_params['rebalance_frequency'] # 'BQS-JAN'       
        # Strategy Parameters
        self.pac_value = config.strategy_params['pac_value']
        self.initial_capital = self.pac_value  if self.pac_value > 0 and config.strategy_params['initial_capital'] == 0 else config.strategy_params['initial_capital']
            
        self.core_target_weights = config.universe['core_allocation']
        self.core_target_weight = config.strategy_params['core_target_weight']
        self.satellite_target_weight = 1 - self.core_target_weight
        
        # Asset Tickers
        self.asset_tickers = config.get_factor_names(include_world=True)
        self.benchmark_ticker = 'WORLD'
        
        self.satellite_history = pd.Series(dtype=object, name="satellite_winner")
        self.pac_dates = pd.date_range(start=self.start_date, end=self.end_date, freq=self.pac_frequency) if self.pac_frequency else []
        self.rebalance_dates = pd.date_range(start=self.start_date, end=self.end_date, freq=self.rebalance_frequency)
        if self.pac_dates[0] == self.start_date and self.initial_capital > 0:
            self.pac_dates = self.pac_dates[1:]
        if self.rebalance_dates[0] == self.start_date and self.initial_capital > 0:
            self.rebalance_dates = self.rebalance_dates[1:]
        self.currency = config.strategy_params["calculation_currency"]

        # --- PORTFOLIO INITIALIZATION ---
        self.portfolio = Portfolio(
            initial_capital=self.initial_capital,
            start_date=self.start_date,
            asset_tickers=self.asset_tickers,
            config=self.config
        )
        
        # --- LOGGING INITIALIZATION ---
        self.transaction_log = [] # A list to store trade dictionaries

    def _calculate_shares_to_buy(self, budget, price):
        """
        Calculates the number of shares that can be bought with a given budget,
        accounting for transaction costs.
        """
        if price <= 0 or budget <= 0:
            return 0        
        
        denominator = price * (1 + self.portfolio.transaction_cost_pct)
        if denominator == 0:
            return 0
            
        return budget / denominator 


    def run(self):
        """"
        main function of backtester.
        Performs the strategy according to the configuration given.
        Calculates every transaction in event dates and fills remaining dates after the comptation
        """        
        
        event_dates = self.pac_dates.union(self.rebalance_dates).union([self.start_date])
        event_dates = self.data.loc[self.start_date:self.end_date].index.intersection(event_dates)
        
        # save all days for the computation
        self.all_trading_dates = self.data.loc[self.start_date:self.end_date].index
                
        self._perform_initial_investment()
        if self.start_date in self.all_trading_dates:
             self.portfolio.record_daily_state(self.start_date, self.data.loc[self.start_date])
        for date in event_dates:            
            is_pac_day = date in self.pac_dates
            is_rebalance_day = date in self.rebalance_dates
            if is_pac_day:
                self._inject_pac_capital(date)
                # only one between rebalncing and pac
            if is_rebalance_day:
                self._perform_full_rebalancing(date)
            elif is_pac_day and date != self.start_date:
                self._execute_pac_purchase(date)
    
            # record daily state
            self.portfolio.record_daily_state(date, self.data.loc[date])
        
        # fill remaining dates
        final_daily_ledger = self._expand_ledger_vectorized(self.portfolio.ledger)
        
        return final_daily_ledger, self.transaction_log
    
    def _perform_initial_investment(self):
        """
        Invests the initial capital at the beginning of the backtest.
        Called once by the run() method.
        """
        if self.initial_capital <= 0:
            return
            
        
        core_investment = self.initial_capital * self.core_target_weight
        satellite_investment = self.initial_capital * self.satellite_target_weight
        
        trades_to_execute = []        
        
        if core_investment > 0 and len(self.core_target_weights) > 0:
            
            for ticker in self.core_target_weights.keys():
                allocation_per_factor = core_investment * self.core_target_weights[ticker]
                price = self.data.loc[self.start_date, f"price_{ticker}_{self.currency}"]
                quantity = self._calculate_shares_to_buy(allocation_per_factor, price)
                trades_to_execute.append({'ticker': ticker, 'quantity': quantity, 'allocation_type': 'core'})

        if satellite_investment > 0:
            first_signal_date = self.signals.loc[self.signals.index >= self.start_date].index[0]
            winner = self.signals.loc[first_signal_date]
            self.satellite_history.loc[first_signal_date] = winner
            
            price = self.data.loc[self.start_date, f"price_{winner}_{self.currency}"]
            quantity = self._calculate_shares_to_buy(satellite_investment, price)
            trades_to_execute.append({'ticker': winner, 'quantity': quantity, 'allocation_type': 'satellite'})

        for trade in trades_to_execute:
            price = self.data.loc[self.start_date, f"price_{trade['ticker']}_{self.currency}"]
            self.portfolio.transact_shares(self.start_date, trade['ticker'], trade['quantity'], price, trade['allocation_type'])
            

    def _inject_pac_capital(self, date):
        """
        Adds the fixed PAC amount to the portfolio's cash balance.
        This method is called on PAC dates as determined by the main 'run' loop.
        """
        if self.pac_value > 0:
            # Add the amount to the portfolio's cash
            self.portfolio.cash += self.pac_value

    def _execute_pac_purchase(self, date):
        """
        Executes the periodic investment (PAC) without performing a full strategic rebalance.
        Allocates new cash to the Core's underweight assets and to the current Satellite holding.
        """
        
        cash_to_invest = self.pac_value
        if cash_to_invest <= 0:
            return

        core_investment = cash_to_invest * self.core_target_weight
        satellite_investment = cash_to_invest * self.satellite_target_weight
        current_prices = self.data.loc[date]
        trades_to_execute = []

        if satellite_investment > 0:
            current_satellite_holding = self.satellite_history.asof(date)
            
            if current_satellite_holding:
                price = current_prices.get(f"price_{current_satellite_holding}_{self.currency}", 0)
                if price > 0:
                    quantity = self._calculate_shares_to_buy(satellite_investment, price)
                    trades_to_execute.append({'ticker': current_satellite_holding, 'quantity': quantity, 'price': price, 'allocation_type': 'satellite'})
            else:
                print(f"[{date.date()}] PAC satellite purchase skipped: no satellite chosen yet.")
                
        if core_investment > 0:
        
            core_filtered_weights = {k: v for k, v in self.core_target_weights.items() if v > 0}
            num_core_factors = len(core_filtered_weights)
            
            if num_core_factors == 1:
                ticker = list(core_filtered_weights.keys())[0]
                allocation = core_investment
                price_col = f"price_{ticker}_{self.currency}"
                price = current_prices.get(price_col, 0)
                if price > 0:
                     quantity = self._calculate_shares_to_buy(allocation, price)
                     trades_to_execute.append({'ticker': ticker, 'quantity': quantity, 'price': price, 'allocation_type': 'core'})

            elif num_core_factors > 1:
                # Calculate current CORE value to determine target values
                current_core_value = 0.0
                for ticker in self.core_target_weights.keys():
                     core_lots = self.portfolio.positions[ticker]['core']
                     price = current_prices.get(f"price_{ticker}_{self.currency}", 0)
                     if pd.notna(price):
                         current_core_value += sum(l.quantity * price for l in core_lots)
                next_core_value = current_core_value + core_investment
                # 1. Calculate Value Deficit for each underweight factor
                value_deficit = {}
                total_deficit = 0.0
                for ticker, target_internal_weight in self.core_target_weights.items():
                    target_value = next_core_value * target_internal_weight # Target value based on *current* core value
                    
                    # Calculate current value ONLY for core lots
                    core_lots = self.portfolio.positions[ticker]['core']
                    price = current_prices.get(f"price_{ticker}_{self.currency}", 0)
                    current_value = sum(lot.quantity * price for lot in core_lots) if pd.notna(price) else 0
                    
                    deficit = target_value - current_value
                    if deficit > 1e-6: # Only consider factors truly underweight 
                        value_deficit[ticker] = deficit
                        total_deficit += deficit
        
                # 2. Allocate PAC cash proportionally to the deficit
                if total_deficit > 0:
                    for ticker, deficit in value_deficit.items():
                        # 3. Allocation proportional to deficit share
                        allocation = core_investment * (deficit / total_deficit)
    
                        price_col = f"price_{ticker}_{self.currency}"
                        price = current_prices.get(price_col, 0)
                        if price > 0:
                            # 4. Calculate shares to buy
                            quantity = self._calculate_shares_to_buy(allocation, price)
                            if quantity > 1e-8: # Avoid negligible trades
                                 trades_to_execute.append({
                                     'ticker': ticker, 
                                     'quantity': quantity, 
                                     'price': price,
                                     'allocation_type': 'core' 
                                 })

            for trade in trades_to_execute:
                self.portfolio.transact_shares(date, trade['ticker'], trade['quantity'], trade['price'], trade['allocation_type'])
                self.transaction_log.append({'date': date, 'ticker': trade['ticker'], 'quantity':  trade['quantity'], 'price': price, 'allocation': trade['allocation_type']})

    def _perform_full_rebalancing(self, date):
        """
        Executes the full strategic rebalance using a two-phase process:
        1. Executes all necessary strategic sales (Satellite rotation).
        2. Recalculates targets based on new cash and executes all buys.
        """
        current_prices = self.data.loc[date]

        # search satellite winner
        try:
            valid_signal_dates = self.signals.index[self.signals.index <= date]
            latest_signal_date = valid_signal_dates[-1] if not valid_signal_dates.empty else None
            current_winner = self.signals.loc[latest_signal_date] if latest_signal_date is not None else None
            if pd.isna(current_winner): current_winner = self.satellite_history.iloc[-1] if not self.satellite_history.empty else None
        except Exception:
            current_winner = self.satellite_history.iloc[-1] if not self.satellite_history.empty else None

        if pd.notna(current_winner): self.satellite_history.loc[date] = current_winner
        previous_winner = self.satellite_history.iloc[-2] if len(self.satellite_history) > 1 else None

        # sell old satellite
        if current_winner != previous_winner and previous_winner:
            sat_lots_old = self.portfolio.positions[previous_winner]['satellite']
            quantity_to_sell = sum(lot.quantity for lot in sat_lots_old)
            
            if quantity_to_sell > 1e-8: 
                price = current_prices.get(f"price_{previous_winner}_{self.currency}", 0)
                if price > 0:
                    success = self.portfolio.transact_shares(date, previous_winner, -quantity_to_sell, price, 'satellite')
                    if success:
                        self.transaction_log.append({'date': date, 'ticker': previous_winner, 'quantity': -quantity_to_sell, 'price': price, 'allocation': 'satellite_sell'})

        #calculate targets with cash available from sell and pac
        available_cash = self.portfolio.cash
        current_total_value_after_sells = self.portfolio.get_total_value(current_prices)
        
        #get targets to reach
        target_satellite_total_value = current_total_value_after_sells * self.satellite_target_weight
        target_core_total_value = current_total_value_after_sells * self.core_target_weight

        buy_orders_value = defaultdict(lambda: {'core': 0.0, 'satellite': 0.0})

        # buy new satellite first
        if current_winner:
            current_satellite_value = 0.0
            sat_lots = self.portfolio.positions[current_winner]['satellite']
            price = current_prices.get(f"price_{current_winner}_{self.currency}", 0)
            if pd.notna(price):
                current_satellite_value = sum(l.quantity * price for l in sat_lots)
            
            value_to_buy = target_satellite_total_value - current_satellite_value
            if value_to_buy > 0:
                buy_orders_value[current_winner]['satellite'] = value_to_buy

        # Core
        if target_core_total_value > 0 and len(self.core_target_weights) > 0:
            current_core_value = 0.0
            for ticker in self.core_target_weights.keys():
                core_lots = self.portfolio.positions[ticker]['core']
                price = current_prices.get(f"price_{ticker}_{self.currency}", 0)
                if pd.notna(price):
                    current_core_value += sum(l.quantity * price for l in core_lots)

            # deficit
            value_deficit = {}
            total_positive_deficit = 0.0
            for ticker, target_internal_weight in self.core_target_weights.items():
                target_value = target_core_total_value * target_internal_weight
                
                current_value = 0.0
                core_lots = self.portfolio.positions[ticker]['core']
                price = current_prices.get(f"price_{ticker}_{self.currency}", 0)
                if pd.notna(price):
                    current_value = sum(l.quantity * price for l in core_lots)
                
                deficit = target_value - current_value
                if deficit > 1e-6:
                    value_deficit[ticker] = deficit
                    total_positive_deficit += deficit
                    
            core_investment_budget = target_core_total_value - current_core_value
            
            if core_investment_budget > 0:
                if total_positive_deficit > 0:     
                    for ticker, deficit in value_deficit.items():
                        allocation = core_investment_budget * (deficit / total_positive_deficit)
                        buy_orders_value[ticker]['core'] += allocation
                else:
                    for ticker, target_weight in self.core_target_weights.items():
                         allocation = core_investment_budget * target_weight
                         buy_orders_value[ticker]['core'] += allocation
            
        
        total_buy_orders_value = sum(v['core'] + v['satellite'] for v in buy_orders_value.values())
        estimated_buy_costs = total_buy_orders_value * self.portfolio.transaction_cost_pct
        total_cash_required = total_buy_orders_value + estimated_buy_costs

        buy_scaling_factor = 1.0
        if total_cash_required > available_cash:
            # print(f"   WARNING: Insufficient cash for buys. Needed ~{total_cash_required:.2f}, have {available_cash:.2f}. Scaling buys.")
            buy_scaling_factor = available_cash / total_cash_required if total_cash_required > 0 else 0
            buy_scaling_factor = max(0, min(1, buy_scaling_factor))

        for ticker, values in buy_orders_value.items():
            for allocation_type, value_change in values.items():
                if value_change > 1e-6:
                    scaled_value_to_buy = value_change * buy_scaling_factor
                    price = current_prices.get(f"price_{ticker}_{self.currency}", 0)
                    if price > 0:
                        quantity = self._calculate_shares_to_buy(scaled_value_to_buy, price)
                        success = self.portfolio.transact_shares(date, ticker, quantity, price, allocation_type)
                        if success:
                             self.transaction_log.append({'date': date, 'ticker': ticker, 'quantity': quantity, 'price': price, 'allocation': allocation_type})
        
        

    def _expand_ledger_vectorized(self, sparse_ledger):
        """
        Expands ledger to a full daily ledger using vectorized pandas operations.
        """
        full_index = self.all_trading_dates
        daily_ledger = sparse_ledger.reindex(full_index)
        qty_cols = [col for col in daily_ledger.columns if col.startswith('quantity_')]
        daily_ledger[qty_cols] = daily_ledger[qty_cols].ffill().fillna(0)
        
        # daily_ledger[qty_cols] = daily_ledger[qty_cols]
        daily_ledger['cash'] = daily_ledger['cash'].ffill().fillna(0)

        price_prefix = self.config.strategy_params['price_prefix']
        currency = self.config.strategy_params['calculation_currency']
        
        market_value_series = pd.Series(0.0, index=full_index)

        for ticker in self.asset_tickers:
            qty_col = f'quantity_{ticker}'
            price_col = f"{price_prefix}{ticker}_{currency}"
            value_col = f'value_{ticker}'
            weight_col = f'weight_{ticker}'

            price_series = self.data[price_col]
            
            daily_ledger[value_col] = daily_ledger[qty_col] * price_series

            market_value_series = market_value_series.add(daily_ledger[value_col], fill_value=0)

        daily_ledger['market_value'] = market_value_series
        daily_ledger['total_value'] = daily_ledger['market_value'] + daily_ledger['cash']
        
        for ticker in self.asset_tickers:
            value_col = f'value_{ticker}'
            weight_col = f'weight_{ticker}'
            daily_ledger[weight_col] = daily_ledger[value_col] / daily_ledger['total_value']

        daily_ledger.fillna(0, inplace=True) 

        return daily_ledger
