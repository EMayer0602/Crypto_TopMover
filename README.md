# Crypto TopMover

Automatisierter Crypto Trading Bot für Binance Futures (Testnet) mit Fear & Greed basierter Position-Allokation.

## Features

- **Futures Trading** auf Binance Testnet (kein echtes Geld)
- **Fear & Greed Index** basierte Position-Verteilung
- **Mean Reversion Strategie** (Buy the Dip, Short the Pump)
- **Supertrend Entry Filter** (verhindert Chasing nach Pumps)
- **RSI Filter** für besseres Entry-Timing
- **Trailing Stop** zur Gewinnabsicherung
- **Live Dashboard** mit Equity Curve
- **Close All Positions** Button

---

## Installation

```bash
# Repository klonen
git clone https://github.com/EMayer0602/Crypto_TopMover.git
cd Crypto_TopMover

# Dependencies installieren
pip install -r requirements.txt

# .env Datei erstellen
cp .env.example .env
# API Keys eintragen (Testnet Keys von testnet.binancefuture.com)
```

---

## Verwendung

### Live Trading starten
```bash
python testnet_trader.py
```

### Backtest ausführen
```bash
python testnet_trader.py backtest
```

### Peak/Trough Analyse
```bash
python testnet_trader.py analyze
```

### Hilfe anzeigen
```bash
python testnet_trader.py help
```

### Dashboard öffnen
```bash
# Terminal 1: Trader starten
python testnet_trader.py

# Terminal 2: HTTP Server starten
python -m http.server 8080

# Browser: http://localhost:8080/dashboard.html
```

### Alle Positionen schließen
```bash
python close_all.py
```

---

## Konfiguration (config.py)

### Trading Einstellungen

| Einstellung | Default | Beschreibung |
|-------------|---------|--------------|
| `MAX_POSITION_SIZE` | 500 | Max. USD pro Trade |
| `MAX_OPEN_POSITIONS` | 10 | Max. gleichzeitige Positionen |
| `TAKE_PROFIT_PERCENT` | 4.0 | TP bei +4% |
| `STOP_LOSS_PERCENT` | 5.0 | SL bei -5% |

### Fear & Greed Allocation

```python
USE_FEAR_GREED_ALLOCATION = True   # Aktivieren
FEAR_GREED_MODE = "MOMENTUM"       # oder "CONTRARIAN"
```

**MOMENTUM Modus** (empfohlen):
| F&G Index | Klassifikation | Max Longs | Max Shorts |
|-----------|----------------|-----------|------------|
| 90-100 | Extreme Greed | 9 | 1 |
| 70-90 | Greed | 7-8 | 2-3 |
| 30-70 | Neutral | 5 | 5 |
| 10-30 | Fear | 2-3 | 7-8 |
| 0-10 | Extreme Fear | 1 | 9 |

**CONTRARIAN Modus** (Gegenteil):
- Fear = Mehr Longs (Kaufgelegenheit)
- Greed = Mehr Shorts (Überkauft)

### Entry Filter

```python
# RSI Filter
USE_RSI_FILTER = True
RSI_OVERSOLD = 45                  # Long wenn RSI < 45
RSI_OVERBOUGHT = 55                # Short wenn RSI > 55

# Supertrend Entry Filter (verhindert Chasing)
USE_SUPERTREND_ENTRY_FILTER = True
ENTRY_MAX_ATR_DISTANCE = 2.0       # Max 2x ATR vom Supertrend
```

### Trailing Stop

```python
USE_TRAILING_STOP = True
TRAILING_STOP_ACTIVATION = 2.0    # Aktiviert ab +2%
TRAILING_STOP_DISTANCE = 1.5      # Folgt mit 1.5% Abstand
```

### Mean Reversion Schwellen

```python
BUY_LOSER_THRESHOLD = -7.0        # Long bei Coins mit -7% oder mehr
SHORT_GAINER_THRESHOLD = 15.0     # Short bei Coins mit +15% oder mehr
```

---

## Strategien

### 1. Mean Reversion (Standard)
- **Long**: Kaufe Coins die stark gefallen sind (-7% oder mehr)
- **Short**: Shorte Coins die stark gestiegen sind (+15% oder mehr)
- Erwartet Rückkehr zum Mittelwert

### 2. Breakout Detection
```python
USE_BREAKOUT_DETECTION = True
```
- Erkennt Ausbrüche über/unter 5-Tage High/Low
- Long bei Breakout Up, Short bei Breakout Down

### 3. Trend Following
```python
USE_TREND_FILTER = True
```
- Prüft 3-Tage Trend-Konsistenz
- Vermeidet Trades gegen den Trend

---

## Dashboard Features

- **Equity Curve** (USD oder %)
- **Live PnL** in USD
- **Win Rate** und Profit Factor
- **Offene Positionen** mit Trailing Stop Status
- **Trade History**
- **Close All Button**
- **BTC Supertrend Status**

---

## Projektstruktur

```
Crypto_TopMover/
├── testnet_trader.py      # Haupt-Trading-Bot
├── config.py              # Alle Einstellungen
├── dashboard.html         # Live Dashboard
├── close_all.py           # Alle Positionen schließen
├── backtest_supertrend.py # Backtest Script
├── analyze_peaks.py       # Peak/Trough Analyse
├── HELP.md                # Ausführliche Hilfe
├── .env                   # API Keys (nicht im Git!)
└── dashboard_data.json    # Dashboard Daten (auto-generiert)
```

---

## API Keys einrichten

1. Gehe zu https://testnet.binancefuture.com
2. Registriere dich / Logge ein
3. Erstelle API Keys unter "API Management"
4. Trage sie in `.env` ein:

```env
BINANCE_API_KEY_TEST=dein_testnet_api_key
BINANCE_API_SECRET_TEST=dein_testnet_api_secret
```

---

## Tipps

1. **Starte mit Testnet** - Kein echtes Geld riskieren
2. **Beobachte die ersten Trades** - Passe Filter bei Bedarf an
3. **Nutze das Dashboard** - Behalte Überblick über Performance
4. **Fear & Greed beachten** - MOMENTUM folgt dem Markt-Sentiment
5. **Backtest vor Änderungen** - Teste neue Einstellungen zuerst

---

## Warnung

Dies ist ein **experimenteller Trading Bot** für Bildungszwecke.
- Verwende nur das **Testnet** zum Lernen
- Keine Garantie für Gewinne
- Crypto-Trading ist hochriskant

---

## Lizenz

MIT License
