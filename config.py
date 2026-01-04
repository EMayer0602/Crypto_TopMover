# Crypto TopMover Configuration
# ================================

import os
from dotenv import load_dotenv

# .env Datei laden
load_dotenv()

# === MODUS ===
USE_TESTNET = True  # True = Testnet (Spielgeld), False = Live (echtes Geld!)

# Binance API Credentials (aus .env)
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Testnet API Credentials (separate Keys vom Testnet!)
TESTNET_API_KEY = os.getenv("BINANCE_API_KEY_TEST", "")
TESTNET_API_SECRET = os.getenv("BINANCE_API_SECRET_TEST", "")

# API URLs
BINANCE_SPOT_URL = "https://api.binance.com/api/v3"
BINANCE_FUTURES_URL = "https://fapi.binance.com"
TESTNET_SPOT_URL = "https://testnet.binance.vision/api/v3"
TESTNET_FUTURES_URL = "https://testnet.binancefuture.com"

# Trading Einstellungen
PAPER_TRADING_CAPITAL = 1000  # Startkapital in USDT
MAX_POSITION_SIZE = 500       # Max. Investition pro Trade in USDT (10% von $5000)
MAX_OPEN_POSITIONS = 5        # Max. gleichzeitige Positionen

# Top Mover Einstellungen
TIMEFRAMES = ["1h", "4h", "24h"]  # Verfügbare Timeframes
DEFAULT_TIMEFRAME = "1h"          # Standard Timeframe
MIN_VOLUME_USDT = 1000000         # Mindestvolumen in USDT (Filter für kleine Coins)
TOP_N_MOVERS = 10                 # Anzahl Top Gainer/Loser anzeigen
MIN_GAINER_PERCENT = 10.0         # Nur Coins mit mind. +10% als Top Gainer

# Take Profit / Stop Loss (in Prozent)
TAKE_PROFIT_PERCENT = 4.0   # Verkaufen bei +4% (Mean Reversion Target)
STOP_LOSS_PERCENT = 5.0     # Verkaufen bei -5%

# Mean Reversion Strategie (automatisch)
AUTO_BUY_ENABLED = True           # Automatisch kaufen
BUY_LOSER_THRESHOLD = -10.0       # Kaufe Coins die -10% oder mehr gefallen sind
MIN_LOSER_VOLUME = 5000000        # Mindestvolumen für Auto-Buy (5M USDT)

# SHORT Strategie (Futures)
SHORT_GAINER_THRESHOLD = 25.0     # Shorte Coins die +25% oder mehr gestiegen sind
SHORT_TAKE_PROFIT = 5.0           # TP für Shorts
SHORT_STOP_LOSS = 8.0             # SL für Shorts

# Scanner Einstellungen
SCAN_INTERVAL_SECONDS = 60  # Wie oft nach neuen Top Movern scannen
QUOTE_CURRENCY = "USDT"     # Nur Paare mit USDT handeln

# Logging
LOG_TRADES = True
LOG_DIR = "logs"
CACHE_DIR = "ohlcv_cache"


def get_api_credentials():
    """Gibt die richtigen API Credentials zurück (Testnet oder Live)"""
    if USE_TESTNET:
        return TESTNET_API_KEY, TESTNET_API_SECRET
    return BINANCE_API_KEY, BINANCE_API_SECRET


def get_api_url(futures: bool = False):
    """Gibt die richtige API URL zurück"""
    if USE_TESTNET:
        return TESTNET_FUTURES_URL if futures else TESTNET_SPOT_URL
    return BINANCE_FUTURES_URL if futures else BINANCE_SPOT_URL
