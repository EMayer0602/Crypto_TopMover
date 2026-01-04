# Crypto TopMover

Scannt Binance nach Top Gainern/Losern und ermöglicht Paper Trading mit automatischem Take Profit und Stop Loss.

## Features

- Top Gainer/Loser Scanner (24h Veränderung)
- Paper Trading ohne echtes Geld
- Automatisches Take Profit / Stop Loss
- Trade History und Statistiken
- Persistenter Zustand (überlebt Neustarts)

## Installation

```bash
# Repository klonen
git clone https://github.com/EMayer0602/Crypto_TopMover.git
cd Crypto_TopMover

# Dependencies installieren
pip install -r requirements.txt

# .env Datei erstellen
cp .env.example .env
# Dann .env bearbeiten und API Keys eintragen
```

## Konfiguration

Bearbeite `.env` mit deinen Binance API Keys:

```
BINANCE_API_KEY=dein_api_key
BINANCE_API_SECRET=dein_api_secret
```

Einstellungen in `config.py`:

| Einstellung | Default | Beschreibung |
|-------------|---------|--------------|
| PAPER_TRADING_CAPITAL | 1000 | Startkapital in USDT |
| MAX_POSITION_SIZE | 100 | Max. pro Trade |
| TAKE_PROFIT_PERCENT | 5.0 | Verkauf bei +5% |
| STOP_LOSS_PERCENT | 3.0 | Verkauf bei -3% |
| TOP_N_MOVERS | 10 | Anzahl Top Coins |

## Verwendung

```bash
python run.py
```

### Menü

1. **Top Movers anzeigen** - Zeigt Gainer und Loser
2. **Position kaufen** - Wähle einen Top Gainer zum Kaufen
3. **Position verkaufen** - Manueller Verkauf
4. **Offene Positionen** - Übersicht mit aktuellem PnL
5. **Trading Statistiken** - Win-Rate, Gesamt-PnL etc.
6. **Auto-Trading** - Überwacht TP/SL automatisch

## Projektstruktur

```
Crypto_TopMover/
├── config.py        # Einstellungen
├── data_fetcher.py  # Binance API Scanner
├── paper_trader.py  # Paper Trading Bot
├── run.py           # Haupteinstieg
├── requirements.txt # Dependencies
├── .env             # API Keys (nicht im Git!)
├── logs/            # Trade Logs
└── ohlcv_cache/     # Daten Cache
```

## Hinweis

Dies ist ein Paper Trading Bot - es wird kein echtes Geld verwendet. Perfekt zum Testen von Strategien!
