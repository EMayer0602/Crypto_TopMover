#!/usr/bin/env python3
"""
HTF Optimizer - Findet optimale Indicator-Settings pro Symbol
=============================================================
Testet verschiedene Timeframes und Parameter für:
- Supertrend
- KAMA
- JMA

Speichert optimale Settings in symbol_settings.json
"""

import requests
import json
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import config


@dataclass
class TradeResult:
    """Ein simulierter Trade"""
    entry_price: float
    exit_price: float
    side: str  # LONG oder SHORT
    pnl_percent: float
    entry_time: str
    exit_time: str


class HTFOptimizer:
    """Optimiert Indicator-Settings pro Symbol"""

    def __init__(self):
        self.session = requests.Session()
        self.cache_dir = "ohlcv_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        # Zu testende Parameter
        self.timeframes = ["5m", "15m", "1h", "4h"]
        self.supertrend_periods = [7, 10, 14]
        self.supertrend_multipliers = [2.0, 3.0, 4.0]
        self.kama_periods = [5, 10, 20]
        self.jma_periods = [5, 7, 10]

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[dict]:
        """Holt historische Klines von Binance"""
        cache_file = f"{self.cache_dir}/{symbol}_{interval}_{limit}.json"

        # Cache prüfen (max 1 Stunde alt)
        if os.path.exists(cache_file):
            mtime = os.path.getmtime(cache_file)
            if time.time() - mtime < 3600:  # 1 Stunde
                with open(cache_file, "r") as f:
                    return json.load(f)

        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                print(f"  API Error: {response.status_code}")
                return []

            klines = response.json()
            result = [{
                "open_time": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "close_time": k[6],
            } for k in klines]

            # Cache speichern
            with open(cache_file, "w") as f:
                json.dump(result, f)

            return result

        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            return []

    def calculate_atr(self, klines: List[dict], period: int = 10) -> List[float]:
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

        atr_values = [None] * (period - 1)
        atr = sum(tr_values[:period]) / period
        atr_values.append(atr)

        for i in range(period, len(tr_values)):
            atr = (atr * (period - 1) + tr_values[i]) / period
            atr_values.append(atr)

        return atr_values

    def calculate_supertrend(self, klines: List[dict], period: int = 10, multiplier: float = 3.0) -> List[dict]:
        """Berechnet Supertrend für alle Kerzen"""
        atr_values = self.calculate_atr(klines, period)
        if not atr_values:
            return []

        results = []
        supertrend = []
        direction = []

        for i in range(len(klines)):
            # ATR hat einen Offset von 1 (braucht prev close)
            atr_idx = i - 1
            if i < period or atr_idx < 0 or atr_idx >= len(atr_values) or atr_values[atr_idx] is None:
                results.append({"value": None, "direction": "NEUTRAL"})
                supertrend.append(None)
                direction.append(0)
                continue

            hl2 = (klines[i]["high"] + klines[i]["low"]) / 2
            atr = atr_values[atr_idx]

            basic_upper = hl2 + multiplier * atr
            basic_lower = hl2 - multiplier * atr

            prev_upper = supertrend[i-1] if supertrend[i-1] is not None else basic_upper
            prev_lower = supertrend[i-1] if supertrend[i-1] is not None else basic_lower

            # Final bands
            if basic_upper < prev_upper or klines[i-1]["close"] > prev_upper:
                final_upper = basic_upper
            else:
                final_upper = prev_upper

            if basic_lower > prev_lower or klines[i-1]["close"] < prev_lower:
                final_lower = basic_lower
            else:
                final_lower = prev_lower

            # Direction
            close = klines[i]["close"]
            prev_st = supertrend[i-1] if supertrend[i-1] is not None else final_lower
            prev_dir = direction[i-1]

            if prev_st == prev_upper:
                if close > final_upper:
                    st_value = final_lower
                    st_dir = 1  # UP
                else:
                    st_value = final_upper
                    st_dir = -1  # DOWN
            else:
                if close < final_lower:
                    st_value = final_upper
                    st_dir = -1  # DOWN
                else:
                    st_value = final_lower
                    st_dir = 1  # UP

            supertrend.append(st_value)
            direction.append(st_dir)
            results.append({
                "value": st_value,
                "direction": "UP" if st_dir == 1 else "DOWN"
            })

        return results

    def calculate_kama(self, klines: List[dict], period: int = 10) -> List[dict]:
        """Berechnet KAMA für alle Kerzen"""
        if len(klines) < period + 1:
            return []

        closes = [k["close"] for k in klines]
        results = []
        kama_values = []

        fast_sc = 2 / (2 + 1)
        slow_sc = 2 / (30 + 1)

        for i in range(len(klines)):
            if i < period:
                results.append({"value": None, "trend": "NEUTRAL"})
                kama_values.append(closes[i] if i == period - 1 else None)
                continue

            # Efficiency Ratio
            change = abs(closes[i] - closes[i - period])
            volatility = sum(abs(closes[j] - closes[j-1]) for j in range(i - period + 1, i + 1))

            if volatility == 0:
                er = 0
            else:
                er = change / volatility

            # Smoothing Constant
            sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

            # KAMA
            prev_kama = kama_values[i-1] if kama_values[i-1] is not None else closes[i-1]
            kama = prev_kama + sc * (closes[i] - prev_kama)
            kama_values.append(kama)

            # Trend
            if closes[i] > kama * 1.001:
                trend = "UP"
            elif closes[i] < kama * 0.999:
                trend = "DOWN"
            else:
                trend = "NEUTRAL"

            results.append({"value": kama, "trend": trend})

        return results

    def calculate_jma(self, klines: List[dict], period: int = 7) -> List[dict]:
        """Berechnet JMA (vereinfacht) für alle Kerzen"""
        if len(klines) < period + 1:
            return []

        closes = [k["close"] for k in klines]
        results = []

        # EMA als Basis
        alpha = 2 / (period + 1)
        ema1 = [closes[0]]
        ema2 = [closes[0]]

        for i in range(1, len(klines)):
            e1 = alpha * closes[i] + (1 - alpha) * ema1[-1]
            e2 = alpha * e1 + (1 - alpha) * ema2[-1]
            ema1.append(e1)
            ema2.append(e2)

            jma = 2 * e1 - e2

            if i < period:
                results.append({"value": None, "trend": "NEUTRAL"})
            else:
                prev_jma = results[-1]["value"] if results and results[-1]["value"] else jma
                if jma > prev_jma * 1.0005:
                    trend = "UP"
                elif jma < prev_jma * 0.9995:
                    trend = "DOWN"
                else:
                    trend = "NEUTRAL"
                results.append({"value": jma, "trend": trend})

        return results

    def backtest_settings(
        self,
        symbol: str,
        klines: List[dict],
        st_period: int,
        st_mult: float,
        kama_period: int,
        jma_period: int,
        tp_percent: float = 4.0,
        sl_percent: float = 2.0
    ) -> Dict:
        """
        Simuliert Trades mit gegebenen Settings.
        Returns: Performance-Metriken
        """
        # Berechne Indikatoren
        st_results = self.calculate_supertrend(klines, st_period, st_mult)
        kama_results = self.calculate_kama(klines, kama_period)
        jma_results = self.calculate_jma(klines, jma_period)

        if not st_results or not kama_results or not jma_results:
            return {"trades": 0, "win_rate": 0, "total_pnl": 0}

        trades = []
        position = None  # {"side": "LONG/SHORT", "entry_price": x, "entry_idx": i}

        # Minimale Länge aller Arrays
        min_len = min(len(st_results), len(kama_results), len(jma_results), len(klines))
        start_idx = max(st_period, kama_period, jma_period) + 1

        # Simuliere Trades
        for i in range(start_idx, min_len):
            close = klines[i]["close"]

            # Bounds check
            if i >= len(st_results) or i >= len(kama_results) or i >= len(jma_results):
                continue

            st = st_results[i]
            kama = kama_results[i]
            jma = jma_results[i]

            # Skip wenn Indikatoren nicht verfügbar
            if st is None or kama is None or jma is None:
                continue
            if st.get("direction") == "NEUTRAL" or kama.get("trend") == "NEUTRAL":
                continue

            # Position Management
            if position:
                entry = position["entry_price"]

                if position["side"] == "LONG":
                    pnl = (close - entry) / entry * 100
                    # TP oder SL
                    if pnl >= tp_percent or pnl <= -sl_percent:
                        trades.append(TradeResult(
                            entry_price=entry,
                            exit_price=close,
                            side="LONG",
                            pnl_percent=pnl,
                            entry_time=str(klines[position["entry_idx"]]["open_time"]),
                            exit_time=str(klines[i]["open_time"])
                        ))
                        position = None

                elif position["side"] == "SHORT":
                    pnl = (entry - close) / entry * 100
                    if pnl >= tp_percent or pnl <= -sl_percent:
                        trades.append(TradeResult(
                            entry_price=entry,
                            exit_price=close,
                            side="SHORT",
                            pnl_percent=pnl,
                            entry_time=str(klines[position["entry_idx"]]["open_time"]),
                            exit_time=str(klines[i]["open_time"])
                        ))
                        position = None

            # Entry Signale (nur wenn keine Position)
            if not position:
                st_dir = st.get("direction", "NEUTRAL")
                kama_trend = kama.get("trend", "NEUTRAL")
                jma_trend = jma.get("trend", "NEUTRAL")

                # LONG: ST UP + KAMA UP + JMA nicht DOWN
                if st_dir == "UP" and kama_trend == "UP" and jma_trend != "DOWN":
                    position = {"side": "LONG", "entry_price": close, "entry_idx": i}

                # SHORT: ST DOWN + KAMA DOWN + JMA nicht UP
                elif st_dir == "DOWN" and kama_trend == "DOWN" and jma_trend != "UP":
                    position = {"side": "SHORT", "entry_price": close, "entry_idx": i}

        # Berechne Metriken
        if not trades:
            return {"trades": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl": 0}

        wins = sum(1 for t in trades if t.pnl_percent > 0)
        total_pnl = sum(t.pnl_percent for t in trades)

        return {
            "trades": len(trades),
            "wins": wins,
            "losses": len(trades) - wins,
            "win_rate": wins / len(trades) * 100,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(trades)
        }

    def optimize_symbol(self, symbol: str, timeframe: str = "1h") -> Dict:
        """
        Findet optimale Settings für ein Symbol.
        Returns: Beste Settings + Performance
        """
        print(f"\n{'='*50}")
        print(f"  Optimiere {symbol} auf {timeframe}")
        print(f"{'='*50}")

        # Lade Daten
        klines = self.get_klines(symbol, timeframe, 500)
        if len(klines) < 100:
            print(f"  Nicht genug Daten ({len(klines)} Kerzen)")
            return {}

        print(f"  {len(klines)} Kerzen geladen")

        best_result = None
        best_settings = None
        total_tests = (len(self.supertrend_periods) *
                      len(self.supertrend_multipliers) *
                      len(self.kama_periods) *
                      len(self.jma_periods))

        test_count = 0

        for st_period in self.supertrend_periods:
            for st_mult in self.supertrend_multipliers:
                for kama_period in self.kama_periods:
                    for jma_period in self.jma_periods:
                        test_count += 1

                        result = self.backtest_settings(
                            symbol, klines,
                            st_period, st_mult,
                            kama_period, jma_period
                        )

                        # Bewertung: Win Rate * Anzahl Trades (mindestens 10 Trades)
                        if result["trades"] >= 10:
                            score = result["win_rate"] * (1 + result["avg_pnl"] / 10)

                            if best_result is None or score > best_result.get("score", 0):
                                best_result = {**result, "score": score}
                                best_settings = {
                                    "supertrend_period": st_period,
                                    "supertrend_multiplier": st_mult,
                                    "kama_period": kama_period,
                                    "jma_period": jma_period,
                                    "timeframe": timeframe
                                }

        if best_result and best_settings:
            print(f"\n  Beste Settings für {symbol}:")
            print(f"    Supertrend: Period={best_settings['supertrend_period']}, Mult={best_settings['supertrend_multiplier']}")
            print(f"    KAMA: Period={best_settings['kama_period']}")
            print(f"    JMA: Period={best_settings['jma_period']}")
            print(f"    ---")
            print(f"    Trades: {best_result['trades']}")
            print(f"    Win Rate: {best_result['win_rate']:.1f}%")
            print(f"    Total PnL: {best_result['total_pnl']:.1f}%")
            print(f"    Avg PnL: {best_result['avg_pnl']:.2f}%")

            return {
                "symbol": symbol,
                "settings": best_settings,
                "performance": best_result
            }
        else:
            print(f"  Keine validen Settings gefunden (zu wenig Trades)")
            return {}

    def optimize_multiple(self, symbols: List[str], timeframe: str = "1h") -> Dict:
        """Optimiert mehrere Symbole"""
        results = {}

        for symbol in symbols:
            result = self.optimize_symbol(symbol, timeframe)
            if result:
                results[symbol] = result
            time.sleep(0.5)  # Rate limiting

        return results

    def save_settings(self, results: Dict, filename: str = "symbol_settings.json"):
        """Speichert optimale Settings"""
        # Nur Settings speichern (nicht Performance)
        settings_only = {}
        for symbol, data in results.items():
            if "settings" in data:
                settings_only[symbol] = data["settings"]

        with open(filename, "w") as f:
            json.dump(settings_only, f, indent=2)

        print(f"\n{'='*50}")
        print(f"  Settings gespeichert in {filename}")
        print(f"  {len(settings_only)} Symbole optimiert")
        print(f"{'='*50}")


def get_active_symbols() -> List[str]:
    """Holt aktive Trading-Symbole von Binance"""
    url = "https://api.binance.com/api/v3/ticker/24hr"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return []

        tickers = response.json()

        # Filter: USDT Paare mit gutem Volume
        symbols = []
        for t in tickers:
            symbol = t["symbol"]
            if not symbol.endswith("USDT"):
                continue

            volume = float(t.get("quoteVolume", 0))
            if volume < 10000000:  # Min 10M USDT Volume
                continue

            # Keine Stablecoins
            base = symbol.replace("USDT", "")
            if base in ["USDC", "BUSD", "DAI", "TUSD", "FDUSD"]:
                continue

            symbols.append(symbol)

        return symbols[:30]  # Top 30

    except Exception as e:
        print(f"Error: {e}")
        return []


def analyze_filters():
    """
    Analysiert Filter-Performance aus filter_stats.json
    und empfiehlt welche Filter deaktiviert werden sollten.
    """
    print("\n" + "="*60)
    print("  FILTER ANALYSE")
    print("  Analysiert welche Filter helfen oder schaden")
    print("="*60)

    stats_file = "filter_stats.json"
    if not os.path.exists(stats_file):
        print(f"\n  ❌ {stats_file} nicht gefunden!")
        print("  Starte erst den Trader, damit Statistiken gesammelt werden.")
        return

    with open(stats_file, "r") as f:
        data = json.load(f)

    filter_counts = data.get("filter_counts", {})
    passed_trades = data.get("passed_trades", {})

    print("\n  📊 FILTER PERFORMANCE")
    print("  " + "-"*56)

    recommendations = []

    for filter_name, counts in filter_counts.items():
        blocked = counts.get("blocked", 0)
        would_win = counts.get("would_win", 0)
        would_lose = counts.get("would_lose", 0)
        checked = would_win + would_lose

        if blocked == 0:
            continue

        print(f"\n  {filter_name.upper().replace('_', ' ')}")
        print(f"    Geblockt: {blocked}")

        if checked > 0:
            win_rate = would_win / checked * 100
            print(f"    Davon geprüft: {checked}")
            print(f"    Wären Gewinner: {would_win} ({win_rate:.1f}%)")
            print(f"    Wären Verlierer: {would_lose} ({100-win_rate:.1f}%)")

            # Empfehlung
            if win_rate > 50:
                print(f"    ⚠️  EMPFEHLUNG: DEAKTIVIEREN - blockt zu viele Gewinner!")
                recommendations.append({
                    "filter": filter_name,
                    "action": "DISABLE",
                    "reason": f"blockt {win_rate:.0f}% Gewinner",
                    "config_key": f"USE_{filter_name.upper()}_FILTER" if filter_name != "supertrend_entry" else "USE_SUPERTREND_ENTRY_FILTER"
                })
            elif win_rate > 35:
                print(f"    ⚡ NEUTRAL - Filter ist grenzwertig")
                recommendations.append({
                    "filter": filter_name,
                    "action": "WATCH",
                    "reason": f"blockt {win_rate:.0f}% Gewinner - beobachten",
                    "config_key": f"USE_{filter_name.upper()}_FILTER" if filter_name != "supertrend_entry" else "USE_SUPERTREND_ENTRY_FILTER"
                })
            else:
                print(f"    ✅ GUT - Filter spart Verluste!")
        else:
            print(f"    ⏳ Noch keine Outcome-Daten (braucht 4h)")

    # Zusammenfassung der durchgelassenen Trades
    print("\n  " + "-"*56)
    print("  DURCHGELASSENE TRADES")
    total = passed_trades.get("total", 0)
    wins = passed_trades.get("wins", 0)
    if total > 0:
        win_rate = wins / total * 100
        print(f"    Total: {total}")
        print(f"    Gewinner: {wins} ({win_rate:.1f}%)")
        print(f"    Verlierer: {total - wins} ({100-win_rate:.1f}%)")
    else:
        print("    Noch keine abgeschlossenen Trades")

    # Empfehlungen ausgeben
    if recommendations:
        print("\n" + "="*60)
        print("  EMPFEHLUNGEN FÜR config.py")
        print("="*60)

        disable_count = 0
        for rec in recommendations:
            if rec["action"] == "DISABLE":
                disable_count += 1
                print(f"\n  ❌ {rec['config_key']} = False")
                print(f"     Grund: {rec['reason']}")

        if disable_count == 0:
            print("\n  ✅ Alle Filter sind nützlich - keine Änderungen nötig!")

        # Auto-Fix Option
        print("\n" + "-"*60)
        print("  Willst du die Änderungen automatisch anwenden?")
        print("  Führe aus: python optimize_htf.py autofix")

    print("")


def autofix_filters():
    """
    Deaktiviert automatisch Filter die zu viele Gewinner blocken.
    Ändert config.py direkt.
    """
    print("\n" + "="*60)
    print("  AUTOFIX - Filter automatisch anpassen")
    print("="*60)

    stats_file = "filter_stats.json"
    if not os.path.exists(stats_file):
        print(f"\n  ❌ {stats_file} nicht gefunden!")
        return

    with open(stats_file, "r") as f:
        data = json.load(f)

    filter_counts = data.get("filter_counts", {})

    # Finde Filter die deaktiviert werden sollten
    to_disable = []
    for filter_name, counts in filter_counts.items():
        blocked = counts.get("blocked", 0)
        would_win = counts.get("would_win", 0)
        would_lose = counts.get("would_lose", 0)
        checked = would_win + would_lose

        if blocked > 0 and checked > 5:  # Mindestens 5 geprüfte Trades
            win_rate = would_win / checked * 100
            if win_rate > 50:  # Blockt mehr als 50% Gewinner
                config_key = f"USE_{filter_name.upper()}_FILTER"
                if filter_name == "supertrend_entry":
                    config_key = "USE_SUPERTREND_ENTRY_FILTER"
                to_disable.append({
                    "filter": filter_name,
                    "config_key": config_key,
                    "win_rate": win_rate
                })

    if not to_disable:
        print("\n  ✅ Alle Filter sind nützlich - keine Änderungen nötig!")
        return

    print(f"\n  {len(to_disable)} Filter werden deaktiviert:")
    for f in to_disable:
        print(f"    - {f['filter']} (blockt {f['win_rate']:.0f}% Gewinner)")

    # config.py lesen und ändern
    config_file = "config.py"
    if not os.path.exists(config_file):
        print(f"\n  ❌ {config_file} nicht gefunden!")
        return

    with open(config_file, "r") as f:
        config_content = f.read()

    changes_made = 0
    for f in to_disable:
        key = f["config_key"]
        # Suche nach "KEY = True" und ersetze mit "KEY = False"
        old_pattern = f"{key} = True"
        new_pattern = f"{key} = False  # AUTO-DISABLED: blockt {f['win_rate']:.0f}% Gewinner"

        if old_pattern in config_content:
            config_content = config_content.replace(old_pattern, new_pattern)
            changes_made += 1
            print(f"    ✓ {key} = False")

    if changes_made > 0:
        with open(config_file, "w") as f:
            f.write(config_content)
        print(f"\n  ✅ {changes_made} Filter in config.py deaktiviert!")
    else:
        print("\n  ⚠️ Keine Änderungen nötig (bereits deaktiviert)")


if __name__ == "__main__":
    import sys

    optimizer = HTFOptimizer()

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()

        if arg == "analyze":
            # Filter-Analyse
            analyze_filters()

        elif arg == "autofix":
            # Automatisch schlechte Filter deaktivieren
            autofix_filters()

        elif arg == "all":
            # ALLE Symbole optimieren
            print("\n" + "="*60)
            print("  HTF OPTIMIZER - ALLE SYMBOLE")
            print("="*60)

            symbols = get_active_symbols()
            if not symbols:
                print("  Konnte keine Symbole laden!")
                sys.exit(1)

            print(f"  {len(symbols)} Symbole werden optimiert...")

            all_results = {}
            for tf in ["15m", "1h"]:
                print(f"\n{'#'*60}")
                print(f"  TIMEFRAME: {tf}")
                print(f"{'#'*60}")

                results = optimizer.optimize_multiple(symbols, tf)  # ALLE Symbole
                all_results.update(results)
                optimizer.save_settings(results, f"symbol_settings_{tf}.json")

            # Kombinierte Settings speichern
            optimizer.save_settings(all_results, "symbol_settings.json")
            print(f"\n  Gesamt: {len(all_results)} Symbole optimiert")

        else:
            # Einzelnes Symbol optimieren
            symbol = arg.upper()
            if not symbol.endswith("USDT"):
                symbol += "USDT"

            timeframe = sys.argv[2] if len(sys.argv) > 2 else "1h"

            result = optimizer.optimize_symbol(symbol, timeframe)
            if result:
                optimizer.save_settings({symbol: result})
    else:
        # Standard: Top 10 Symbole
        print("\n" + "="*60)
        print("  HTF OPTIMIZER")
        print("  Findet optimale Indicator-Settings pro Symbol")
        print("="*60)
        print("\n  Verwendung:")
        print("    python optimize_htf.py           → Top 10 Symbole")
        print("    python optimize_htf.py all       → ALLE Symbole")
        print("    python optimize_htf.py BTCUSDT   → Einzelnes Symbol")
        print("    python optimize_htf.py analyze   → Filter-Analyse")
        print("")

        print("\n  Lade aktive Symbole...")
        symbols = get_active_symbols()

        if not symbols:
            print("  Konnte keine Symbole laden!")
            sys.exit(1)

        print(f"  {len(symbols)} Symbole gefunden")
        print(f"  Symbole: {', '.join(symbols[:10])}...")

        # Verschiedene Timeframes testen
        for tf in ["15m", "1h"]:
            print(f"\n\n{'#'*60}")
            print(f"  TIMEFRAME: {tf}")
            print(f"{'#'*60}")

            results = optimizer.optimize_multiple(symbols[:10], tf)  # Top 10
            optimizer.save_settings(results, f"symbol_settings_{tf}.json")

        print("\n\n  FERTIG!")
        print("  Nutze die Settings mit: python testnet_trader.py")
