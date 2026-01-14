"""
Backtest Script für Crypto Trading Strategien
=============================================
Testet verschiedene Filter und Verbesserungen auf historischen Daten.
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import config

class Backtester:
    """Backtester für Trading Strategien"""

    def __init__(self):
        self.session = requests.Session()
        self.results = {}

    def get_historical_klines(self, symbol: str, interval: str = "1h",
                               days: int = 30) -> List[dict]:
        """Holt historische Klines von Binance"""
        url = "https://api.binance.com/api/v3/klines"
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        all_klines = []
        current_start = start_time

        while current_start < end_time:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_time,
                "limit": 1000
            }

            response = self.session.get(url, params=params)
            if response.status_code != 200:
                break

            klines = response.json()
            if not klines:
                break

            for k in klines:
                all_klines.append({
                    "timestamp": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                    "quote_volume": float(k[7]),
                })

            current_start = klines[-1][0] + 1
            time.sleep(0.1)  # Rate limit

        return all_klines

    def calculate_rsi(self, closes: List[float], period: int = 14) -> List[float]:
        """Berechnet RSI"""
        if len(closes) < period + 1:
            return [50.0] * len(closes)

        rsi_values = [50.0] * period
        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))

        for i in range(period, len(closes)):
            avg_gain = sum(gains[i-period:i]) / period
            avg_loss = sum(losses[i-period:i]) / period

            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))

            rsi_values.append(rsi)

        return rsi_values

    def calculate_supertrend(self, klines: List[dict], period: int = 10,
                             multiplier: float = 3.0) -> List[str]:
        """Berechnet Supertrend Direction"""
        if len(klines) < period + 2:
            return ["NEUTRAL"] * len(klines)

        # ATR berechnen
        atr_values = [0.0] * len(klines)
        tr_values = []

        for i in range(1, len(klines)):
            high = klines[i]["high"]
            low = klines[i]["low"]
            prev_close = klines[i-1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

            if i >= period:
                atr_values[i] = sum(tr_values[i-period:i]) / period

        # Supertrend
        directions = ["NEUTRAL"] * len(klines)
        supertrend_up = [0.0] * len(klines)
        supertrend_down = [0.0] * len(klines)
        direction = 1

        for i in range(period, len(klines)):
            atr = atr_values[i]
            hl2 = (klines[i]["high"] + klines[i]["low"]) / 2

            basic_upper = hl2 + (multiplier * atr)
            basic_lower = hl2 - (multiplier * atr)

            # Final bands
            if i > period:
                if basic_upper < supertrend_up[i-1] or klines[i-1]["close"] > supertrend_up[i-1]:
                    supertrend_up[i] = basic_upper
                else:
                    supertrend_up[i] = supertrend_up[i-1]

                if basic_lower > supertrend_down[i-1] or klines[i-1]["close"] < supertrend_down[i-1]:
                    supertrend_down[i] = basic_lower
                else:
                    supertrend_down[i] = supertrend_down[i-1]
            else:
                supertrend_up[i] = basic_upper
                supertrend_down[i] = basic_lower

            # Direction
            if direction == 1:
                if klines[i]["close"] < supertrend_down[i]:
                    direction = -1
            else:
                if klines[i]["close"] > supertrend_up[i]:
                    direction = 1

            directions[i] = "BULLISH" if direction == 1 else "BEARISH"

        return directions

    def calculate_volume_sma(self, klines: List[dict], period: int = 20) -> List[float]:
        """Berechnet Volume SMA"""
        volumes = [k["quote_volume"] for k in klines]
        sma = [0.0] * len(volumes)

        for i in range(period, len(volumes)):
            sma[i] = sum(volumes[i-period:i]) / period

        return sma

    def simulate_strategy(self, klines: List[dict], btc_klines: List[dict],
                          use_rsi: bool = False, rsi_oversold: int = 30,
                          use_volume_spike: bool = False, volume_mult: float = 1.5,
                          use_time_filter: bool = False,
                          use_supertrend: bool = True,
                          tp_percent: float = 4.0, sl_percent: float = 5.0,
                          trailing_stop: bool = True, ts_activation: float = 2.0,
                          ts_distance: float = 1.5) -> dict:
        """
        Simuliert eine Trading-Strategie auf historischen Daten.
        """
        if len(klines) < 50 or len(btc_klines) < 50:
            return {"error": "Nicht genug Daten"}

        # Indikatoren berechnen
        closes = [k["close"] for k in klines]
        rsi_values = self.calculate_rsi(closes, 14)
        btc_supertrend = self.calculate_supertrend(btc_klines, 10, 3.0)
        volume_sma = self.calculate_volume_sma(klines, 20)

        # Trading Simulation
        trades = []
        position = None
        peak_price = 0.0

        for i in range(50, len(klines)):
            current = klines[i]
            price = current["close"]
            timestamp = current["timestamp"]
            hour = datetime.fromtimestamp(timestamp / 1000).hour

            # BTC Supertrend Filter
            btc_dir = btc_supertrend[min(i, len(btc_supertrend)-1)]

            # Position Management
            if position:
                if position["side"] == "LONG":
                    pnl = (price - position["entry"]) / position["entry"] * 100

                    # Trailing Stop
                    if trailing_stop and pnl >= ts_activation:
                        if price > peak_price:
                            peak_price = price
                        ts_level = peak_price * (1 - ts_distance / 100)
                        if price <= ts_level:
                            trades.append({
                                "side": "LONG",
                                "entry": position["entry"],
                                "exit": price,
                                "pnl": pnl,
                                "exit_reason": "TRAILING_STOP"
                            })
                            position = None
                            peak_price = 0.0
                            continue

                    # TP/SL
                    if pnl >= tp_percent:
                        trades.append({
                            "side": "LONG",
                            "entry": position["entry"],
                            "exit": price,
                            "pnl": pnl,
                            "exit_reason": "TP"
                        })
                        position = None
                        peak_price = 0.0
                    elif pnl <= -sl_percent:
                        trades.append({
                            "side": "LONG",
                            "entry": position["entry"],
                            "exit": price,
                            "pnl": pnl,
                            "exit_reason": "SL"
                        })
                        position = None
                        peak_price = 0.0

                continue

            # Entry Logic (nur wenn keine Position)
            if position:
                continue

            # Zeit-Filter (keine Trades 0-4 Uhr UTC)
            if use_time_filter and (hour >= 0 and hour < 4):
                continue

            # 24h Change simulieren
            if i >= 24:
                change_24h = (price - klines[i-24]["close"]) / klines[i-24]["close"] * 100
            else:
                continue

            # LONG Entry: Coin stark gefallen
            if change_24h <= -8:  # Gefallen
                # Supertrend Filter
                if use_supertrend and btc_dir == "BEARISH":
                    continue

                # RSI Filter
                if use_rsi and rsi_values[i] > rsi_oversold:
                    continue

                # Volume Spike Filter
                if use_volume_spike:
                    if volume_sma[i] > 0 and current["quote_volume"] < volume_sma[i] * volume_mult:
                        continue

                position = {"side": "LONG", "entry": price}
                peak_price = price

        # Statistiken berechnen
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "avg_pnl": 0,
                "profit_factor": 0,
                "max_drawdown": 0,
                "trades": []
            }

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]

        total_pnl = sum(t["pnl"] for t in trades)
        total_wins = sum(t["pnl"] for t in wins)
        total_losses = abs(sum(t["pnl"] for t in losses))

        # Max Drawdown
        equity_curve = []
        cumulative = 0
        peak_equity = 0
        max_dd = 0

        for t in trades:
            cumulative += t["pnl"]
            equity_curve.append(cumulative)
            if cumulative > peak_equity:
                peak_equity = cumulative
            dd = peak_equity - cumulative
            if dd > max_dd:
                max_dd = dd

        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trades) * 100 if trades else 0,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(trades) if trades else 0,
            "profit_factor": total_wins / total_losses if total_losses > 0 else 999,
            "max_drawdown": max_dd,
            "equity_curve": equity_curve,
            "trades": trades
        }

    def run_backtest(self, symbols: List[str] = None, days: int = 30):
        """Führt Backtest für mehrere Strategien durch"""

        if symbols is None:
            symbols = ["SOLUSDT", "AVAXUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT"]

        print(f"\n{'='*70}")
        print(f"  BACKTEST - {days} Tage historische Daten")
        print(f"{'='*70}")

        # BTC Daten holen
        print("\n📥 Lade BTC Daten...")
        btc_klines = self.get_historical_klines("BTCUSDT", "1h", days)
        print(f"   {len(btc_klines)} Kerzen geladen")

        # Test-Konfigurationen
        configs = {
            "Baseline (Aktuell)": {
                "use_rsi": False,
                "use_volume_spike": False,
                "use_time_filter": False,
                "use_supertrend": True,
                "trailing_stop": True
            },
            "+ RSI Filter (<30)": {
                "use_rsi": True,
                "rsi_oversold": 30,
                "use_volume_spike": False,
                "use_time_filter": False,
                "use_supertrend": True,
                "trailing_stop": True
            },
            "+ RSI Filter (<35)": {
                "use_rsi": True,
                "rsi_oversold": 35,
                "use_volume_spike": False,
                "use_time_filter": False,
                "use_supertrend": True,
                "trailing_stop": True
            },
            "+ Volume Spike (1.5x)": {
                "use_rsi": False,
                "use_volume_spike": True,
                "volume_mult": 1.5,
                "use_time_filter": False,
                "use_supertrend": True,
                "trailing_stop": True
            },
            "+ Volume Spike (2x)": {
                "use_rsi": False,
                "use_volume_spike": True,
                "volume_mult": 2.0,
                "use_time_filter": False,
                "use_supertrend": True,
                "trailing_stop": True
            },
            "+ Zeit-Filter (no 0-4h)": {
                "use_rsi": False,
                "use_volume_spike": False,
                "use_time_filter": True,
                "use_supertrend": True,
                "trailing_stop": True
            },
            "Ohne Trailing Stop": {
                "use_rsi": False,
                "use_volume_spike": False,
                "use_time_filter": False,
                "use_supertrend": True,
                "trailing_stop": False
            },
            "RSI + Volume": {
                "use_rsi": True,
                "rsi_oversold": 35,
                "use_volume_spike": True,
                "volume_mult": 1.5,
                "use_time_filter": False,
                "use_supertrend": True,
                "trailing_stop": True
            },
            "RSI + Zeit": {
                "use_rsi": True,
                "rsi_oversold": 35,
                "use_volume_spike": False,
                "use_time_filter": True,
                "use_supertrend": True,
                "trailing_stop": True
            },
            "Alle Filter": {
                "use_rsi": True,
                "rsi_oversold": 35,
                "use_volume_spike": True,
                "volume_mult": 1.5,
                "use_time_filter": True,
                "use_supertrend": True,
                "trailing_stop": True
            }
        }

        # Ergebnisse sammeln
        all_results = {}

        for config_name, params in configs.items():
            print(f"\n🔬 Teste: {config_name}")
            combined_trades = []

            for symbol in symbols:
                print(f"   📥 {symbol}...", end=" ")
                klines = self.get_historical_klines(symbol, "1h", days)
                print(f"{len(klines)} Kerzen")

                if len(klines) < 100:
                    continue

                result = self.simulate_strategy(
                    klines, btc_klines,
                    use_rsi=params.get("use_rsi", False),
                    rsi_oversold=params.get("rsi_oversold", 30),
                    use_volume_spike=params.get("use_volume_spike", False),
                    volume_mult=params.get("volume_mult", 1.5),
                    use_time_filter=params.get("use_time_filter", False),
                    use_supertrend=params.get("use_supertrend", True),
                    trailing_stop=params.get("trailing_stop", True)
                )

                combined_trades.extend(result.get("trades", []))

            # Kombinierte Statistiken
            if combined_trades:
                wins = [t for t in combined_trades if t["pnl"] > 0]
                losses = [t for t in combined_trades if t["pnl"] <= 0]
                total_pnl = sum(t["pnl"] for t in combined_trades)
                total_wins = sum(t["pnl"] for t in wins)
                total_losses = abs(sum(t["pnl"] for t in losses))

                all_results[config_name] = {
                    "trades": len(combined_trades),
                    "wins": len(wins),
                    "losses": len(losses),
                    "win_rate": len(wins) / len(combined_trades) * 100,
                    "total_pnl": total_pnl,
                    "avg_pnl": total_pnl / len(combined_trades),
                    "profit_factor": total_wins / total_losses if total_losses > 0 else 999
                }
            else:
                all_results[config_name] = {
                    "trades": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                    "profit_factor": 0
                }

        # Ergebnisse anzeigen
        print(f"\n{'='*70}")
        print(f"  BACKTEST ERGEBNISSE")
        print(f"{'='*70}")
        print(f"\n{'Strategie':<25} {'Trades':>7} {'Win%':>7} {'PnL%':>8} {'AvgPnL':>8} {'PF':>6}")
        print("-" * 70)

        # Nach Total PnL sortieren
        sorted_results = sorted(all_results.items(), key=lambda x: x[1]["total_pnl"], reverse=True)

        baseline_pnl = all_results.get("Baseline (Aktuell)", {}).get("total_pnl", 0)

        for name, stats in sorted_results:
            diff = stats["total_pnl"] - baseline_pnl
            diff_str = f"({diff:+.1f})" if name != "Baseline (Aktuell)" else ""

            emoji = "🏆" if stats["total_pnl"] == sorted_results[0][1]["total_pnl"] else "  "

            print(f"{emoji}{name:<23} {stats['trades']:>7} {stats['win_rate']:>6.1f}% "
                  f"{stats['total_pnl']:>+7.1f}% {stats['avg_pnl']:>+7.2f}% "
                  f"{stats['profit_factor']:>5.2f} {diff_str}")

        print("-" * 70)

        # Empfehlungen
        print(f"\n📊 EMPFEHLUNGEN:")

        best_name, best_stats = sorted_results[0]
        if best_name != "Baseline (Aktuell)" and best_stats["total_pnl"] > baseline_pnl:
            improvement = best_stats["total_pnl"] - baseline_pnl
            print(f"   ✅ Beste Strategie: {best_name}")
            print(f"   ✅ Verbesserung: +{improvement:.1f}% PnL vs Baseline")
            print(f"   ✅ Win-Rate: {best_stats['win_rate']:.1f}%")
            print(f"   ✅ Profit Factor: {best_stats['profit_factor']:.2f}")
        else:
            print(f"   ⚠️  Aktuelle Strategie ist bereits optimal")

        return sorted_results


if __name__ == "__main__":
    bt = Backtester()
    results = bt.run_backtest(days=30)
