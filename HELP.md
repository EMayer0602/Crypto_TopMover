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

## BTC/ETH Markt-Filter (NEU)

Verhindert Trades gegen den Gesamtmarkt.

**Logik:**
```
BTC + ETH beide < -3%  → BEARISH  → Nur Shorts erlaubt
BTC + ETH beide > +3%  → BULLISH  → Nur Longs erlaubt
Einer fällt stark      → WEAK_BEARISH → Keine neuen Longs
Einer steigt stark     → WEAK_BULLISH → Keine neuen Shorts
Beide neutral          → NEUTRAL  → Beide Richtungen erlaubt
```

**Config:**
```python
USE_BTC_MARKET_FILTER = True
BTC_TREND_THRESHOLD = 3.0     # Ab +/-3% gilt als trending
```

**Beispiel-Szenarien:**

| BTC 24h | ETH 24h | Markt-Status | Longs | Shorts |
|---------|---------|--------------|-------|--------|
| -5%     | -4%     | BEARISH      | ❌    | ✅     |
| +4%     | +3%     | BULLISH      | ✅    | ❌     |
| -4%     | +1%     | WEAK_BEARISH | ❌    | ✅     |
| +1%     | +5%     | WEAK_BULLISH | ✅    | ❌     |
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

1. **Markt-Filter:** BTC/ETH erlaubt diese Richtung?
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
| `USE_BTC_MARKET_FILTER` | True | BTC/ETH Filter |

---

## Tipps

1. **Markt fällt stark?**
   → Nur Shorts werden geöffnet, keine neuen Longs

2. **Viele Breakouts?**
   → Bot tradet mit dem Momentum

3. **Seitwärtsmarkt?**
   → Mean Reversion funktioniert am besten

4. **Performance schlecht?**
   → `python auto_optimize.py` laufen lassen
