#!/usr/bin/env python3
"""
Backtest für Supertrend Entry Filter
Testet das Muster: Entry nur wenn Preis nah am Supertrend ist
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import json

# Konfiguration
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT"]
TIMEFRAME = "5m"
LOOKBACK_DAYS = 7
POSITION_SIZE = 500  # USD

# Strategy Settings
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0
MAX_ATR_DISTANCE = 2.0  # Max Abstand in ATR
TAKE_PROFIT = 4.0  # %
STOP_LOSS = 5.0  # %

# API
BASE_URL = "https://api.binance.com"


def get_klines(symbol: str, interval: str, limit: int = 500) -> List[dict]:
    """Holt historische Klines von Binance"""
    url = f"{BASE_URL}/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"API Error: {response.status_code}")
            return []

        data = response.json()
        klines = []
        for k in data:
            klines.append({
                "timestamp": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })
        return klines
    except Exception as e:
        print(f"Error fetching klines: {e}")
        return []


def calculate_atr(klines: List[dict], period: int = 14) -> List[float]:
    """Berechnet ATR"""
    if len(klines) < period + 1:
        return []

    tr_values = []
    for i in range(1, len(klines)):
        high = klines[i]["high"]
        low = klines[i]["low"]
        prev_close = klines[i-1]["close"]

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        tr_values.append(tr)

    atr_values = [None] * period
    for i in range(period, len(tr_values) + 1):
        atr = sum(tr_values[i-period:i]) / period
        atr_values.append(atr)

    return atr_values


def calculate_supertrend(klines: List[dict], period: int = 10, multiplier: float = 3.0) -> List[dict]:
    """Berechnet Supertrend für alle Kerzen"""
    if len(klines) < period + 2:
        return []

    atr_values = calculate_atr(klines, period)
    if not atr_values:
        return []

    results = []
    supertrend_up = [None] * len(klines)
    supertrend_down = [None] * len(klines)
    supertrend = [None] * len(klines)
    direction = [1] * len(klines)

    for i in range(len(klines)):
        if i < period or atr_values[i] is None:
            results.append({"direction": "NEUTRAL", "value": 0, "atr": 0})
            continue

        atr = atr_values[i]
        hl2 = (klines[i]["high"] + klines[i]["low"]) / 2

        basic_upper = hl2 + (multiplier * atr)
        basic_lower = hl2 - (multiplier * atr)

        prev_upper = supertrend_up[i-1] if supertrend_up[i-1] is not None else basic_upper
        if basic_upper < prev_upper or klines[i-1]["close"] > prev_upper:
            final_upper = basic_upper
        else:
            final_upper = prev_upper

        prev_lower = supertrend_down[i-1] if supertrend_down[i-1] is not None else basic_lower
        if basic_lower > prev_lower or klines[i-1]["close"] < prev_lower:
            final_lower = basic_lower
        else:
            final_lower = prev_lower

        supertrend_up[i] = final_upper
        supertrend_down[i] = final_lower

        prev_dir = direction[i-1]

        if prev_dir == 1:
            if klines[i]["close"] < final_lower:
                direction[i] = -1
                supertrend[i] = final_upper
            else:
                direction[i] = 1
                supertrend[i] = final_lower
        else:
            if klines[i]["close"] > final_upper:
                direction[i] = 1
                supertrend[i] = final_lower
            else:
                direction[i] = -1
                supertrend[i] = final_upper

        results.append({
            "direction": "BULLISH" if direction[i] == 1 else "BEARISH",
            "value": supertrend[i],
            "atr": atr
        })

    return results


def check_entry_allowed(price: float, st_value: float, atr: float, side: str, max_atr_dist: float) -> Tuple[bool, float]:
    """Prüft ob Entry erlaubt ist basierend auf ATR-Distanz"""
    if st_value == 0 or atr == 0:
        return True, 0

    distance = (price - st_value) / atr

    if side == "LONG":
        return distance <= max_atr_dist, distance
    else:  # SHORT
        return distance >= -max_atr_dist, distance


def simulate_trade(klines: List[dict], entry_idx: int, side: str, entry_price: float,
                   tp_pct: float, sl_pct: float) -> dict:
    """Simuliert einen Trade und findet Exit"""

    for i in range(entry_idx + 1, len(klines)):
        high = klines[i]["high"]
        low = klines[i]["low"]

        if side == "LONG":
            # Check TP
            tp_price = entry_price * (1 + tp_pct/100)
            if high >= tp_price:
                pnl_pct = tp_pct
                return {
                    "exit_idx": i,
                    "exit_price": tp_price,
                    "pnl_pct": pnl_pct,
                    "exit_reason": "TP"
                }

            # Check SL
            sl_price = entry_price * (1 - sl_pct/100)
            if low <= sl_price:
                pnl_pct = -sl_pct
                return {
                    "exit_idx": i,
                    "exit_price": sl_price,
                    "pnl_pct": pnl_pct,
                    "exit_reason": "SL"
                }

        else:  # SHORT
            # Check TP
            tp_price = entry_price * (1 - tp_pct/100)
            if low <= tp_price:
                pnl_pct = tp_pct
                return {
                    "exit_idx": i,
                    "exit_price": tp_price,
                    "pnl_pct": pnl_pct,
                    "exit_reason": "TP"
                }

            # Check SL
            sl_price = entry_price * (1 + sl_pct/100)
            if high >= sl_price:
                pnl_pct = -sl_pct
                return {
                    "exit_idx": i,
                    "exit_price": sl_price,
                    "pnl_pct": pnl_pct,
                    "exit_reason": "SL"
                }

    # Still open
    last_price = klines[-1]["close"]
    if side == "LONG":
        pnl_pct = (last_price - entry_price) / entry_price * 100
    else:
        pnl_pct = (entry_price - last_price) / entry_price * 100

    return {
        "exit_idx": len(klines) - 1,
        "exit_price": last_price,
        "pnl_pct": pnl_pct,
        "exit_reason": "OPEN"
    }


def backtest_symbol(symbol: str, use_filter: bool = True) -> dict:
    """Backtest für ein Symbol"""
    print(f"\n{'='*50}")
    print(f"  Backtest: {symbol} ({'MIT' if use_filter else 'OHNE'} Filter)")
    print(f"{'='*50}")

    # Hole Daten
    limit = LOOKBACK_DAYS * 24 * 12  # 5min = 12 per hour
    klines = get_klines(symbol, TIMEFRAME, min(limit, 1000))

    if len(klines) < 100:
        print(f"  Nicht genug Daten: {len(klines)} Kerzen")
        return {"trades": 0, "win_rate": 0, "total_pnl": 0}

    print(f"  Daten: {len(klines)} Kerzen ({LOOKBACK_DAYS} Tage)")

    # Berechne Supertrend
    st_data = calculate_supertrend(klines, SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER)

    trades = []
    i = SUPERTREND_PERIOD + 10

    while i < len(klines) - 10:
        price = klines[i]["close"]
        st = st_data[i]

        if st["direction"] == "NEUTRAL":
            i += 1
            continue

        # Entry Signal: Preis nahe am Supertrend
        if use_filter:
            # Mit Filter: Nur wenn nah am ST
            allowed, distance = check_entry_allowed(
                price, st["value"], st["atr"],
                "LONG" if st["direction"] == "BULLISH" else "SHORT",
                MAX_ATR_DISTANCE
            )
            if not allowed:
                i += 1
                continue

        # Bestimme Trade-Richtung basierend auf ST
        if st["direction"] == "BULLISH":
            side = "LONG"
        else:
            side = "SHORT"

        # Simuliere Trade
        result = simulate_trade(klines, i, side, price, TAKE_PROFIT, STOP_LOSS)

        trades.append({
            "entry_idx": i,
            "entry_price": price,
            "side": side,
            "st_value": st["value"],
            "atr_distance": (price - st["value"]) / st["atr"] if st["atr"] > 0 else 0,
            **result
        })

        # Skip bis nach Exit
        i = result["exit_idx"] + 1

    # Statistiken
    if not trades:
        print("  Keine Trades!")
        return {"trades": 0, "win_rate": 0, "total_pnl": 0, "wins": 0, "losses": 0}

    wins = len([t for t in trades if t["pnl_pct"] > 0])
    losses = len([t for t in trades if t["pnl_pct"] <= 0])
    total_pnl = sum(t["pnl_pct"] for t in trades)
    win_rate = wins / len(trades) * 100 if trades else 0

    avg_win = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0) / wins if wins > 0 else 0
    avg_loss = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0) / losses if losses > 0 else 0

    print(f"\n  Ergebnis:")
    print(f"  Trades: {len(trades)} ({wins}W / {losses}L)")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total PnL: {total_pnl:+.2f}%")
    print(f"  Avg Win: +{avg_win:.2f}% | Avg Loss: {avg_loss:.2f}%")

    # USD Berechnung
    total_usd = POSITION_SIZE * total_pnl / 100
    print(f"  USD (bei ${POSITION_SIZE}): {'+' if total_usd >= 0 else ''}{total_usd:.2f}")

    return {
        "symbol": symbol,
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "total_usd": total_usd,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "trade_list": trades
    }


def run_comparison_backtest():
    """Vergleicht Ergebnisse MIT und OHNE Filter"""
    print("\n" + "="*60)
    print("  BACKTEST: Supertrend Entry Filter")
    print("  Vergleich: MIT Filter vs. OHNE Filter")
    print("="*60)
    print(f"\n  Settings:")
    print(f"  - Timeframe: {TIMEFRAME}")
    print(f"  - Lookback: {LOOKBACK_DAYS} Tage")
    print(f"  - Max ATR Distance: {MAX_ATR_DISTANCE}")
    print(f"  - TP: {TAKE_PROFIT}% | SL: {STOP_LOSS}%")

    results_with_filter = []
    results_without_filter = []

    for symbol in SYMBOLS:
        # Mit Filter
        result_with = backtest_symbol(symbol, use_filter=True)
        results_with_filter.append(result_with)
        time.sleep(0.5)

        # Ohne Filter
        result_without = backtest_symbol(symbol, use_filter=False)
        results_without_filter.append(result_without)
        time.sleep(0.5)

    # Gesamtergebnis
    print("\n" + "="*60)
    print("  GESAMTERGEBNIS")
    print("="*60)

    def summarize(results, label):
        total_trades = sum(r["trades"] for r in results)
        total_wins = sum(r["wins"] for r in results)
        total_losses = sum(r["losses"] for r in results)
        total_pnl = sum(r["total_pnl"] for r in results)
        total_usd = sum(r["total_usd"] for r in results)
        win_rate = total_wins / total_trades * 100 if total_trades > 0 else 0

        print(f"\n  {label}:")
        print(f"  Trades: {total_trades} ({total_wins}W / {total_losses}L)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Total PnL: {total_pnl:+.2f}%")
        print(f"  Total USD: ${total_usd:+.2f}")

        return {"trades": total_trades, "win_rate": win_rate, "pnl": total_pnl, "usd": total_usd}

    with_stats = summarize(results_with_filter, "MIT Supertrend Entry Filter")
    without_stats = summarize(results_without_filter, "OHNE Filter")

    # Vergleich
    print("\n" + "-"*60)
    print("  VERGLEICH:")
    pnl_diff = with_stats["pnl"] - without_stats["pnl"]
    usd_diff = with_stats["usd"] - without_stats["usd"]
    wr_diff = with_stats["win_rate"] - without_stats["win_rate"]

    print(f"  Filter-Vorteil PnL: {pnl_diff:+.2f}%")
    print(f"  Filter-Vorteil USD: ${usd_diff:+.2f}")
    print(f"  Filter-Vorteil WinRate: {wr_diff:+.1f}%")

    if pnl_diff > 0:
        print("\n  ✅ FILTER VERBESSERT PERFORMANCE!")
    else:
        print("\n  ❌ Filter verschlechtert Performance")

    print("="*60)

    return {
        "with_filter": results_with_filter,
        "without_filter": results_without_filter,
        "comparison": {
            "pnl_diff": pnl_diff,
            "usd_diff": usd_diff,
            "wr_diff": wr_diff
        }
    }


if __name__ == "__main__":
    results = run_comparison_backtest()
