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
MAX_OPEN_POSITIONS = 10       # Max. gleichzeitige Positionen (erhöht von 5)

# Top Mover Einstellungen
TIMEFRAMES = ["1h", "4h", "24h"]  # Verfügbare Timeframes
DEFAULT_TIMEFRAME = "1h"          # Standard Timeframe
MIN_VOLUME_USDT = 1000000         # Mindestvolumen in USDT (Filter für kleine Coins)
TOP_N_MOVERS = 10                 # Anzahl Top Gainer/Loser anzeigen
MIN_GAINER_PERCENT = 10.0         # Nur Coins mit mind. +10% als Top Gainer

# Take Profit / Stop Loss (in Prozent)
TAKE_PROFIT_PERCENT = 4.0   # Verkaufen bei +4% (Mean Reversion Target)
STOP_LOSS_PERCENT = 5.0     # Verkaufen bei -5%

# Trailing Stop (aktiviert sich nach Mindestgewinn)
USE_TRAILING_STOP = True         # Trailing Stop aktivieren
TRAILING_STOP_ACTIVATION = 2.0   # Ab +2% Gewinn wird Trailing Stop aktiv
TRAILING_STOP_DISTANCE = 1.5     # Trailing Stop folgt mit 1.5% Abstand

# RSI Filter (verbessert Entry-Timing)
USE_RSI_FILTER = True            # RSI Filter aktivieren
RSI_PERIOD = 14                  # RSI Periode
RSI_OVERSOLD = 45                # Für Longs: RSI unter 45 (gelockert von 35)
RSI_OVERBOUGHT = 55              # Für Shorts: RSI über 55 (gelockert von 65)

# Supertrend Entry Filter (verhindert Einstieg nach Pump)
USE_SUPERTREND_ENTRY_FILTER = True    # Supertrend als Entry-Filter aktivieren
ENTRY_SUPERTREND_TIMEFRAME = "5m"     # Timeframe für Entry-Check (5min Kerzen)
ENTRY_SUPERTREND_PERIOD = 10          # ATR Periode
ENTRY_SUPERTREND_MULTIPLIER = 3.0     # ATR Multiplikator
ENTRY_MAX_ATR_DISTANCE = 2.0          # Max. Abstand in ATR (gelockert von 1.5)

# KAMA Entry Filter (Kaufman Adaptive Moving Average)
USE_KAMA_FILTER = True                # KAMA als Entry-Filter aktivieren
KAMA_TIMEFRAME = "15m"                # Timeframe für KAMA
KAMA_PERIOD = 10                      # Effizienz-Periode
KAMA_FAST = 2                         # Schnelle EMA Periode
KAMA_SLOW = 30                        # Langsame EMA Periode

# JMA Entry Filter (Jurik Moving Average)
USE_JMA_FILTER = True                 # JMA als Entry-Filter aktivieren
JMA_TIMEFRAME = "15m"                 # Timeframe für JMA
JMA_PERIOD = 7                        # Glättungsperiode
JMA_PHASE = 50                        # Phase (-100 bis +100)

# Volume Filter (bestätigt echte Bewegungen)
USE_VOLUME_FILTER = True              # Volume Filter aktivieren
VOLUME_MIN_RATIO = 1.5                # Min. Volume Ratio (1.5 = 50% über Durchschnitt)
VOLUME_LOOKBACK = 20                  # Anzahl Kerzen für Durchschnitts-Berechnung

# Partial Take Profit (sichert Gewinne früher)
USE_PARTIAL_TP = True                 # Partial TP aktivieren
PARTIAL_TP_PERCENT = 2.0              # Erster TP bei +2%
PARTIAL_TP_CLOSE_RATIO = 0.5          # 50% der Position schließen

# Funding Rate Filter (Contrarian bei extremer Funding)
USE_FUNDING_RATE_FILTER = True        # Funding Rate Filter aktivieren
FUNDING_RATE_THRESHOLD = 0.01         # Ab 0.01% (1% annualisiert) als extrem

# Mean Reversion Strategie (automatisch)
AUTO_BUY_ENABLED = True           # Automatisch kaufen
BUY_LOSER_THRESHOLD = -7.0        # Kaufe Coins ab -7% (gelockert von -10%)
MIN_LOSER_VOLUME = 5000000        # Mindestvolumen für Auto-Buy (5M USDT)

# SHORT Strategie (Futures)
SHORT_GAINER_THRESHOLD = 15.0     # Shorte Coins ab +15% (gelockert von +25%)
SHORT_TAKE_PROFIT = 5.0           # TP für Shorts
SHORT_STOP_LOSS = 8.0             # SL für Shorts

# Trend-Filter Einstellungen
TREND_CHECK_DAYS = 3              # Anzahl Tage für Trend-Check
TREND_MAX_PULLBACK = 2.0          # Max. erlaubte Gegenbewegung in % (sonst = choppy)
TREND_MIN_MOVE = 5.0              # Min. Gesamtbewegung über 3 Tage für Trend
USE_TREND_FILTER = True           # Trend-Filter aktivieren

# Breakout Detection
BREAKOUT_LOOKBACK_DAYS = 5        # Wie viele Tage zurück schauen für High/Low
BREAKOUT_MIN_PERCENT = 2.0        # Min. Breakout über High/Low in %
USE_BREAKOUT_DETECTION = True     # Breakout-Modus statt fester Trend

# BTC Markt-Filter (verhindert Trades gegen den Gesamtmarkt)
USE_BTC_MARKET_FILTER = False     # Einfacher 24h-Change Filter (veraltet)
BTC_TREND_THRESHOLD = 3.0         # Ab +/-3% 24h gilt BTC als trending
BTC_TREND_TIMEFRAME = "24h"       # Timeframe für BTC-Check (1h, 4h, 24h)

# HTF Supertrend Filter (BTC als Markt-Indikator)
USE_HTF_SUPERTREND = False        # DEAKTIVIERT - Trade ohne Markt-Filter
HTF_TIMEFRAME = "4h"              # Timeframe für Supertrend (1h, 4h, 1d)
SUPERTREND_PERIOD = 10            # ATR Periode
SUPERTREND_MULTIPLIER = 3.0       # ATR Multiplikator

# Fear & Greed Position Allocation
USE_FEAR_GREED_ALLOCATION = True  # Dynamische Position-Verteilung aktivieren
FEAR_GREED_MODE = "MOMENTUM"      # "MOMENTUM" = Greed→Longs, Fear→Shorts
                                  # "CONTRARIAN" = Fear→Longs, Greed→Shorts

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
