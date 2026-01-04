"""
Data Fetcher for scanning top gainers and losers in the crypto market
Uses CoinGecko API to fetch market data
"""

import requests
import time
import json
import os
from datetime import datetime, timedelta
import config


class DataFetcher:
    """Fetches crypto market data and identifies top gainers and losers"""
    
    def __init__(self):
        self.api_base = config.API_BASE_URL
        self.timeout = config.API_TIMEOUT
        self.cache_dir = config.OHLCV_CACHE_DIR
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def _rate_limit_delay(self):
        """Apply rate limiting delay"""
        time.sleep(config.RATE_LIMIT_DELAY)
    
    def fetch_market_data(self):
        """
        Fetch market data for all coins from CoinGecko
        Returns list of coins with price change data
        """
        try:
            url = f"{self.api_base}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'volume_desc',
                'per_page': 250,  # Fetch top 250 by volume
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '24h'
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            self._rate_limit_delay()
            
            # Filter by minimum volume
            filtered_data = [
                coin for coin in data 
                if coin.get('total_volume', 0) >= config.MIN_VOLUME_USD
            ]
            
            return filtered_data
            
        except Exception as e:
            print(f"Error fetching market data: {e}")
            return []
    
    def get_top_losers(self, market_data=None, count=None):
        """
        Get top losing coins by 24h price change percentage
        
        Args:
            market_data: Pre-fetched market data (optional)
            count: Number of top losers to return
            
        Returns:
            List of top losing coins sorted by price change (most negative first)
        """
        if market_data is None:
            market_data = self.fetch_market_data()
        
        if count is None:
            count = config.TOP_MOVERS_COUNT
        
        # Filter coins with valid price change data
        valid_coins = [
            coin for coin in market_data 
            if coin.get('price_change_percentage_24h') is not None
        ]
        
        # Sort by price change (ascending - most negative first)
        sorted_losers = sorted(
            valid_coins,
            key=lambda x: x.get('price_change_percentage_24h', 0)
        )
        
        return sorted_losers[:count]
    
    def get_top_gainers(self, market_data=None, count=None):
        """
        Get top gaining coins by 24h price change percentage
        
        Args:
            market_data: Pre-fetched market data (optional)
            count: Number of top gainers to return
            
        Returns:
            List of top gaining coins sorted by price change (most positive first)
        """
        if market_data is None:
            market_data = self.fetch_market_data()
        
        if count is None:
            count = config.TOP_MOVERS_COUNT
        
        # Filter coins with valid price change data
        valid_coins = [
            coin for coin in market_data 
            if coin.get('price_change_percentage_24h') is not None
        ]
        
        # Sort by price change (descending - most positive first)
        sorted_gainers = sorted(
            valid_coins,
            key=lambda x: x.get('price_change_percentage_24h', 0),
            reverse=True
        )
        
        return sorted_gainers[:count]
    
    def get_trading_signals(self):
        """
        Scan market and generate trading signals based on configured thresholds
        
        Returns:
            dict with 'buy_signals' and 'short_signals' lists
        """
        market_data = self.fetch_market_data()
        
        buy_signals = []
        short_signals = []
        
        # Determine which loser threshold to use
        if config.BEAR_MARKET_MODE:
            loser_threshold = config.BEAR_MARKET_LOSER_THRESHOLD
            target_profit = config.BEAR_MARKET_TARGET_PROFIT
        else:
            loser_threshold = config.LOSER_BUY_THRESHOLD
            target_profit = config.LOSER_TARGET_PROFIT
        
        # Scan for buy signals (top losers)
        for coin in market_data:
            price_change = coin.get('price_change_percentage_24h')
            if price_change is not None and price_change <= loser_threshold:
                buy_signals.append({
                    'symbol': coin['symbol'].upper(),
                    'name': coin['name'],
                    'current_price': coin['current_price'],
                    'price_change_24h': price_change,
                    'volume': coin['total_volume'],
                    'signal_type': 'LOSER_BUY',
                    'target_profit': target_profit,
                    'stop_loss': config.LOSER_STOP_LOSS
                })
        
        # Scan for short signals (top gainers)
        for coin in market_data:
            price_change = coin.get('price_change_percentage_24h')
            if price_change is not None and price_change >= config.GAINER_SHORT_THRESHOLD:
                short_signals.append({
                    'symbol': coin['symbol'].upper(),
                    'name': coin['name'],
                    'current_price': coin['current_price'],
                    'price_change_24h': price_change,
                    'volume': coin['total_volume'],
                    'signal_type': 'GAINER_SHORT',
                    'target_profit': config.GAINER_TARGET_PROFIT,
                    'stop_loss': config.GAINER_STOP_LOSS
                })
        
        return {
            'buy_signals': buy_signals,
            'short_signals': short_signals,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_current_price(self, symbol):
        """
        Get current price for a specific coin
        
        Args:
            symbol: Coin symbol (e.g., 'BTC', 'ETH')
            
        Returns:
            Current price in USD or None if not found
        """
        try:
            market_data = self.fetch_market_data()
            for coin in market_data:
                if coin['symbol'].upper() == symbol.upper():
                    return coin['current_price']
            return None
        except Exception as e:
            print(f"Error getting current price for {symbol}: {e}")
            return None


if __name__ == "__main__":
    # Test the data fetcher
    fetcher = DataFetcher()
    
    print("Fetching market data...")
    market_data = fetcher.fetch_market_data()
    print(f"Fetched data for {len(market_data)} coins")
    
    print("\nTop 5 Losers (24h):")
    losers = fetcher.get_top_losers(market_data, 5)
    for coin in losers:
        print(f"  {coin['symbol'].upper()}: {coin['price_change_percentage_24h']:.2f}%")
    
    print("\nTop 5 Gainers (24h):")
    gainers = fetcher.get_top_gainers(market_data, 5)
    for coin in gainers:
        print(f"  {coin['symbol'].upper()}: {coin['price_change_percentage_24h']:.2f}%")
    
    print("\nScanning for trading signals...")
    signals = fetcher.get_trading_signals()
    print(f"  Buy signals: {len(signals['buy_signals'])}")
    print(f"  Short signals: {len(signals['short_signals'])}")
