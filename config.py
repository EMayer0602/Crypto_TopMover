# Crypto TopMover Configuration
# ================================

import os
from dotenv import load_dotenv

# .env Datei laden
load_dotenv()

# Binance API Credentials (aus .env)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Trading Einstellungen
PAPER_TRADING_CAPITAL = 1000  # Startkapital in USDT
MAX_POSITION_SIZE = 100       # Max. Investition pro Trade in USDT
MAX_OPEN_POSITIONS = 5        # Max. gleichzeitige Positionen

# Top Mover Einstellungen
TIMEFRAMES = ["1h", "4h", "24h"]  # Verfügbare Timeframes
DEFAULT_TIMEFRAME = "1h"          # Standard Timeframe
MIN_VOLUME_USDT = 1000000         # Mindestvolumen in USDT (Filter für kleine Coins)
TOP_N_MOVERS = 10                 # Anzahl Top Gainer/Loser anzeigen

# Take Profit / Stop Loss (in Prozent)
TAKE_PROFIT_PERCENT = 5.0   # Verkaufen bei +5%
STOP_LOSS_PERCENT = 3.0     # Verkaufen bei -3%

# Scanner Einstellungen
SCAN_INTERVAL_SECONDS = 60  # Wie oft nach neuen Top Movern scannen
QUOTE_CURRENCY = "USDT"     # Nur Paare mit USDT handeln

# Logging
LOG_TRADES = True
LOG_DIR = "logs"
CACHE_DIR = "ohlcv_cache"
