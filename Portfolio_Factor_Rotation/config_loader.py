import json
import os

class Config:
    """
    Handles loading and accessing configuration parameters from a JSON file.
    Now supports flexible universe definitions for asset-agnostic backtesting.
    """
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self._config = self._load_config()
        
        self.paths = self._config.get('paths', {})
        self.files = self._config.get('files', {})
        self.strategy_params = self._config.get('strategy_params', {})
        self.universe = self._config.get('universe_definition', {}) # NUOVO
        self.mappings = self._config.get('mappings', {})
        self.tickers = self._config.get('tickers', {})
        self.signals = self._config.get('signals', {})
        self.cleaning = self._config.get('cleaning', {})
        self.reporting = self._config.get('reporting', {})
        
        # convert keys from str to int
        self.signals['lookbacks_and_weights'] = {
            int(key): value for key, value in self.signals['lookbacks_and_weights'].items()
        }
    
    def _load_config(self):
        """Loads the JSON configuration file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found at: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON config: {e}")
    
    def get_all_tickers(self):
        """
        Returns a list of ALL unique tickers defined in the mapping.
        These are the internal names (e.g., 'WORLD', 'BTC').
        """
        return list(self.mappings.get('excel_column_map', {}).values())

    def get_benchmark_ticker(self):
        """Returns the internal ticker for the benchmark."""
        return self.universe.get('benchmark_ticker', 'WORLD')

    def get_core_allocation(self):
        """
        Returns the dictionary of {Ticker: Weight} for the Core portfolio.
        """
        return self.universe.get('core_allocation', {})

    def get_satellite_candidates(self):
        """
        Returns the list of tickers that are candidates for the Satellite rotation.
        """
        return self.universe.get('satellite_candidates', [])

    def get_factor_names(self, include_world=False):
        """
        Legacy helper for compatibility. Returns a list of relevant factors.
        Ideally, use get_satellite_candidates() or get_core_allocation() instead.
        """
        factors = self.get_satellite_candidates()
        
        if include_world:
            bench = self.get_benchmark_ticker()
            if bench not in factors:
                factors.append(bench)
                
        return factors

