# Crypto TopMover - Hilfe & Verwendung

## Schnellstart

```bash
# Testnet Trading starten (empfohlen)
python testnet_trader.py

# Automatische Optimierung + Trading
python auto_optimize.py --start

# Backtest durchführen
python backtester.py
```

---

## Trading Modi

### 1. Breakout-Detection (Standard)
Erkennt wenn Coins aus ihrer Range ausbrechen.

**Wann wird getradet:**
- **LONG:** Preis bricht über das N-Tage-High hinaus
- **SHORT:** Preis fällt unter das N-Tage-Low

**Config:**
```python
USE_BREAKOUT_DETECTION = True
BREAKOUT_LOOKBACK_DAYS = 5    # Tage zurückschauen
BREAKOUT_MIN_PERCENT = 2.0    # Min. Breakout über High/Low
```

### 2. Trend-Following (Fallback)
Handelt mit etablierten Trends.

**Wann wird getradet:**
- **LONG:** 3+ Tage konsistent UP ohne große Pullbacks
- **SHORT:** 3+ Tage konsistent DOWN ohne große Rallyes

**Config:**
```python
USE_TREND_FILTER = True
TREND_CHECK_DAYS = 3
TREND_MIN_MOVE = 5.0          # Min. Gesamtbewegung
TREND_MAX_PULLBACK = 2.0      # Max. Gegenbewegung
```

### 3. Mean Reversion (Letzter Fallback)
Klassische "Buy the Dip / Fade the Pump" Strategie.

**Wann wird getradet:**
- **LONG:** Coin fällt stark (-10% oder mehr)
- **SHORT:** Coin pumpt stark (+25% oder mehr)

**Config:**
```python
BUY_LOSER_THRESHOLD = -10.0
SHORT_GAINER_THRESHOLD = 25.0
```

---

## HTF Supertrend Filter (Empfohlen)

Nutzt den **Supertrend Indikator** auf BTC 4h als Markt-Richtungsfilter.
Robuster als einfacher 24h-Change, da Supertrend Volatilität berücksichtigt.

**Logik:**
```
BTC Preis > Supertrend  → BULLISH  → Nur Longs erlaubt
BTC Preis < Supertrend  → BEARISH  → Nur Shorts erlaubt
```

**Config:**
```python
USE_HTF_SUPERTREND = True       # Supertrend Filter aktivieren
HTF_TIMEFRAME = "4h"            # Timeframe (1h, 4h, 1d)
SUPERTREND_PERIOD = 10          # ATR Periode
SUPERTREND_MULTIPLIER = 3.0     # ATR Multiplikator
```

**Vorteile gegenüber 24h-Change:**
- Reagiert auf echte Trendwechsel, nicht nur auf Volatilität
- Weniger Fehlsignale bei seitwärts-bewegenden Märkten
- Berücksichtigt Average True Range (ATR) für Volatilität

---

## BTC/ETH 24h-Filter (Legacy)

Einfacher Filter basierend auf 24h-Preisänderung.

**Config:**
```python
USE_BTC_MARKET_FILTER = True    # (Nur wenn USE_HTF_SUPERTREND = False)
BTC_TREND_THRESHOLD = 3.0       # Ab +/-3% gilt als trending
```

| BTC 24h | ETH 24h | Markt-Status | Longs | Shorts |
|---------|---------|--------------|-------|--------|
| -5%     | -4%     | BEARISH      | ❌    | ✅     |
| +4%     | +3%     | BULLISH      | ✅    | ❌     |
| +1%     | -1%     | NEUTRAL      | ✅    | ✅     |

---

## Auto-Optimizer

Findet automatisch die besten Parameter.

```bash
# Standard (180 Tage Daten)
python auto_optimize.py

# Mit mehr Daten
python auto_optimize.py 365

# Optimieren + sofort Trading starten
python auto_optimize.py --start
python auto_optimize.py 365 --start
```

**Was passiert:**
1. Lädt OHLCV-Daten der Top 20 Coins
2. Testet 240 Parameter-Kombinationen
3. Zeigt Top 10 Ergebnisse
4. Schreibt beste Parameter in config.py
5. Startet Trading (wenn --start angegeben)

---

## Backtest

```bash
python backtester.py
```

**Menü:**
1. Mean Reversion Backtest
2. Optimierung (Parameter Sweep)
3. Batch-Test (alle Top Coins)
4. Breakout Backtest
5. Breakout Optimierung

---

## Prioritäts-Reihenfolge

Der Bot prüft in dieser Reihenfolge:

1. **HTF Supertrend:** BTC über/unter Supertrend? → Bestimmt erlaubte Richtung
2. **Breakout:** Gibt es frische Breakouts?
3. **Trend:** Gibt es etablierte Trends?
4. **Mean Reversion:** Extreme Moves zum Faden?

---

## Config Übersicht

| Einstellung | Default | Beschreibung |
|-------------|---------|--------------|
| `MAX_POSITION_SIZE` | 500 | USDT pro Trade |
| `TAKE_PROFIT_PERCENT` | 4.0 | TP für Longs |
| `STOP_LOSS_PERCENT` | 5.0 | SL für Longs |
| `SHORT_TAKE_PROFIT` | 5.0 | TP für Shorts |
| `SHORT_STOP_LOSS` | 8.0 | SL für Shorts |
| `USE_BREAKOUT_DETECTION` | True | Breakout-Modus |
| `USE_TREND_FILTER` | True | Trend-Following |
| `USE_HTF_SUPERTREND` | True | BTC Supertrend Filter |
| `HTF_TIMEFRAME` | "4h" | Supertrend Timeframe |
| `SUPERTREND_PERIOD` | 10 | ATR Periode |
| `SUPERTREND_MULTIPLIER` | 3.0 | ATR Multiplikator |

---

## Tipps

1. **BTC unter Supertrend?**
   → Nur Shorts werden geöffnet, keine neuen Longs

2. **BTC über Supertrend?**
   → Nur Longs werden geöffnet, keine neuen Shorts

3. **Viele Breakouts?**
   → Bot tradet mit dem Momentum

4. **Seitwärtsmarkt?**
   → Mean Reversion funktioniert am besten

5. **Performance schlecht?**
   → `python auto_optimize.py` laufen lassen

6. **Supertrend zu sensibel?**
   → SUPERTREND_MULTIPLIER erhöhen (z.B. 3.5 oder 4.0)
