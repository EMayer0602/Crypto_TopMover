"""
Configuration file for Crypto Top Mover Paper Trading Bot
Contains thresholds, capital settings, and API configuration
"""

# Trading Capital Settings
INITIAL_CAPITAL = 10000  # Starting capital in USD
POSITION_SIZE_PERCENT = 0.1  # Use 10% of capital per trade

# Top Loser Strategy Settings (Best Strategy!)
# Key Finding: Top Loser kaufen = Beste Strategie! (-10% → +4% avg, 79-93% Win Rate)
LOSER_BUY_THRESHOLD = -10.0  # Buy when price drops by this % in 24h
LOSER_TARGET_PROFIT = 4.0  # Target profit % for top loser trades
LOSER_STOP_LOSS = -5.0  # Stop loss % for top loser trades

# Bear Market Loser Strategy Settings
# Key Finding: Bärenmarkt Loser noch besser (-15% → +7.23%)
BEAR_MARKET_LOSER_THRESHOLD = -15.0  # Buy when price drops by this % in bear market
BEAR_MARKET_TARGET_PROFIT = 7.23  # Target profit % for bear market loser trades
BEAR_MARKET_MODE = False  # Set to True to use bear market strategy

# Top Gainer Short Strategy Settings
# Key Finding: Top Gainer shorten bei +30% (-2.79% avg)
GAINER_SHORT_THRESHOLD = 30.0  # Short when price rises by this % in 24h
GAINER_TARGET_PROFIT = 2.79  # Target profit % for top gainer shorts
GAINER_STOP_LOSS = -5.0  # Stop loss % for top gainer shorts

# Market Scanner Settings
TOP_MOVERS_COUNT = 10  # Number of top movers to scan
SCAN_INTERVAL = 300  # Scan interval in seconds (5 minutes)
MIN_VOLUME_USD = 100000  # Minimum 24h volume in USD

# API Settings (CoinGecko - no API key needed for basic usage)
API_BASE_URL = "https://api.coingecko.com/api/v3"
API_TIMEOUT = 30  # API request timeout in seconds
RATE_LIMIT_DELAY = 2  # Delay between API calls in seconds

# Cache Settings
OHLCV_CACHE_DIR = "ohlcv_cache"
CACHE_EXPIRY_HOURS = 1  # Cache expiry time in hours

# Logging Settings
LOG_DIR = "logs"
LOG_FILE = "trades.log"
LOG_LEVEL = "INFO"

# Trading Rules
MAX_OPEN_POSITIONS = 5  # Maximum number of open positions
ALLOW_LONG_POSITIONS = True  # Allow buying (long positions)
ALLOW_SHORT_POSITIONS = True  # Allow shorting (short positions)
