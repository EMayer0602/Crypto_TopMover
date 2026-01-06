"""
Backtester für Mean Reversion Strategie
=======================================
Testet die Strategie mit historischen Daten.
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass
import config


@dataclass
class BacktestTrade:
    """Ein simulierter Trade"""
    symbol: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    entry_change: float  # 24h Change bei Entry
    pnl_percent: float
    pnl_usdt: float
    exit_reason: str  # TP, SL, oder END
    direction: str = "LONG"  # LONG oder SHORT


class Backtester:
    """Backtester für Mean Reversion Strategie"""

    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self):
        self.session = requests.Session()
        self.trades: List[BacktestTrade] = []

    def get_klines(self, symbol: str, interval: str = "1d",
                   start_time: int = None, limit: int = 1000) -> List[Dict]:
        """Holt historische Klines von Binance"""
        url = f"{self.BASE_URL}/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time

        response = self.session.get(url, params=params)
        if response.status_code != 200:
            return []

        klines = response.json()
        return [{
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": k[6],
        } for k in klines]

    def get_top_symbols(self, limit: int = 50) -> List[str]:
        """Holt die Top Coins nach Volumen"""
        url = f"{self.BASE_URL}/ticker/24hr"
        response = self.session.get(url)
        tickers = response.json()

        # Nur USDT Paare, nach Volumen sortiert
        usdt_pairs = [
            t for t in tickers
            if t["symbol"].endswith("USDT")
            and float(t["quoteVolume"]) > config.MIN_VOLUME_USDT
            and not any(s in t["symbol"] for s in ["USDC", "BUSD", "DAI", "TUSD"])
        ]

        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x["quoteVolume"]), reverse=True)
        return [p["symbol"] for p in sorted_pairs[:limit]]

    def calculate_daily_changes(self, klines: List[Dict]) -> List[Dict]:
        """Berechnet tägliche Veränderungen"""
        changes = []
        for i in range(1, len(klines)):
            prev_close = klines[i-1]["close"]
            curr = klines[i]

            change_percent = ((curr["close"] - prev_close) / prev_close) * 100

            changes.append({
                "date": datetime.fromtimestamp(curr["open_time"] / 1000).strftime("%Y-%m-%d"),
                "open": curr["open"],
                "close": curr["close"],
                "high": curr["high"],
                "low": curr["low"],
                "change_percent": change_percent,
            })

        return changes

    def simulate_trade(self, symbol: str, entry_data: Dict,
                       future_klines: List[Dict]) -> BacktestTrade:
        """Simuliert einen Trade mit TP/SL"""
        entry_price = entry_data["close"]
        entry_date = entry_data["date"]
        position_size = config.MAX_POSITION_SIZE

        tp_price = entry_price * (1 + config.TAKE_PROFIT_PERCENT / 100)
        sl_price = entry_price * (1 - config.STOP_LOSS_PERCENT / 100)

        # Durch zukünftige Tage iterieren
        for day in future_klines:
            # TP erreicht?
            if day["high"] >= tp_price:
                pnl_percent = config.TAKE_PROFIT_PERCENT
                return BacktestTrade(
                    symbol=symbol,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=day["date"],
                    exit_price=tp_price,
                    entry_change=entry_data["change_percent"],
                    pnl_percent=pnl_percent,
                    pnl_usdt=position_size * pnl_percent / 100,
                    exit_reason="TP"
                )

            # SL erreicht?
            if day["low"] <= sl_price:
                pnl_percent = -config.STOP_LOSS_PERCENT
                return BacktestTrade(
                    symbol=symbol,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=day["date"],
                    exit_price=sl_price,
                    entry_change=entry_data["change_percent"],
                    pnl_percent=pnl_percent,
                    pnl_usdt=position_size * pnl_percent / 100,
                    exit_reason="SL"
                )

        # Trade noch offen am Ende
        last_day = future_klines[-1] if future_klines else entry_data
        pnl_percent = ((last_day["close"] - entry_price) / entry_price) * 100
        return BacktestTrade(
            symbol=symbol,
            entry_date=entry_date,
            entry_price=entry_price,
            exit_date=last_day["date"],
            exit_price=last_day["close"],
            entry_change=entry_data["change_percent"],
            pnl_percent=pnl_percent,
            pnl_usdt=position_size * pnl_percent / 100,
            exit_reason="END"
        )

    def simulate_short_trade(self, symbol: str, entry_data: Dict,
                             future_klines: List[Dict], tp_percent: float = None,
                             sl_percent: float = None) -> BacktestTrade:
        """Simuliert einen SHORT Trade (Futures)"""
        entry_price = entry_data["close"]
        entry_date = entry_data["date"]
        position_size = config.MAX_POSITION_SIZE

        tp = tp_percent if tp_percent else config.TAKE_PROFIT_PERCENT
        sl = sl_percent if sl_percent else config.STOP_LOSS_PERCENT

        # Bei SHORT: TP wenn Preis FÄLLT, SL wenn Preis STEIGT
        tp_price = entry_price * (1 - tp / 100)  # Preis muss fallen
        sl_price = entry_price * (1 + sl / 100)  # Stop wenn Preis steigt

        for day in future_klines:
            # TP erreicht? (Preis fällt unter TP)
            if day["low"] <= tp_price:
                pnl_percent = tp
                return BacktestTrade(
                    symbol=symbol,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=day["date"],
                    exit_price=tp_price,
                    entry_change=entry_data["change_percent"],
                    pnl_percent=pnl_percent,
                    pnl_usdt=position_size * pnl_percent / 100,
                    exit_reason="TP",
                    direction="SHORT"
                )

            # SL erreicht? (Preis steigt über SL)
            if day["high"] >= sl_price:
                pnl_percent = -sl
                return BacktestTrade(
                    symbol=symbol,
                    entry_date=entry_date,
                    entry_price=entry_price,
                    exit_date=day["date"],
                    exit_price=sl_price,
                    entry_change=entry_data["change_percent"],
                    pnl_percent=pnl_percent,
                    pnl_usdt=position_size * pnl_percent / 100,
                    exit_reason="SL",
                    direction="SHORT"
                )

        # Trade noch offen
        last_day = future_klines[-1] if future_klines else entry_data
        # Bei SHORT: Gewinn wenn Preis gefallen, Verlust wenn gestiegen
        pnl_percent = ((entry_price - last_day["close"]) / entry_price) * 100
        return BacktestTrade(
            symbol=symbol,
            entry_date=entry_date,
            entry_price=entry_price,
            exit_date=last_day["date"],
            exit_price=last_day["close"],
            entry_change=entry_data["change_percent"],
            pnl_percent=pnl_percent,
            pnl_usdt=position_size * pnl_percent / 100,
            exit_reason="END",
            direction="SHORT"
        )

    def run_backtest(self, days_back: int = 365, symbols: List[str] = None,
                     buy_threshold: float = None) -> Dict:
        """Führt Backtest durch"""
        if buy_threshold is None:
            buy_threshold = config.BUY_LOSER_THRESHOLD

        if symbols is None:
            print("Lade Top Coins...")
            symbols = self.get_top_symbols(30)

        print(f"\nBacktest: {len(symbols)} Coins, {days_back} Tage")
        print(f"Buy Threshold: {buy_threshold}%")
        print(f"TP: +{config.TAKE_PROFIT_PERCENT}% | SL: -{config.STOP_LOSS_PERCENT}%\n")

        self.trades = []
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)

        for i, symbol in enumerate(symbols):
            print(f"[{i+1}/{len(symbols)}] Analysiere {symbol}...", end="\r")

            klines = self.get_klines(symbol, "1d", start_time)
            if len(klines) < 10:
                continue

            changes = self.calculate_daily_changes(klines)

            # Durch jeden Tag iterieren
            for j, day in enumerate(changes[:-5]):  # Letzten 5 Tage für Exit behalten
                # Signal: Coin ist stark gefallen
                if day["change_percent"] <= buy_threshold:
                    future_days = changes[j+1:j+6]  # Nächsten 5 Tage
                    if future_days:
                        trade = self.simulate_trade(symbol, day, future_days)
                        self.trades.append(trade)

            time.sleep(0.1)  # Rate limiting

        print(f"\n\nBacktest abgeschlossen: {len(self.trades)} Trades")
        return self.get_statistics()

    def get_statistics(self) -> Dict:
        """Berechnet Performance-Statistiken"""
        if not self.trades:
            return {"error": "Keine Trades"}

        wins = [t for t in self.trades if t.pnl_percent > 0]
        losses = [t for t in self.trades if t.pnl_percent < 0]
        tp_exits = [t for t in self.trades if t.exit_reason == "TP"]
        sl_exits = [t for t in self.trades if t.exit_reason == "SL"]

        total_pnl = sum(t.pnl_usdt for t in self.trades)
        avg_pnl = total_pnl / len(self.trades)
        win_rate = len(wins) / len(self.trades) * 100

        avg_win = sum(t.pnl_percent for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl_percent for t in losses) / len(losses) if losses else 0

        return {
            "total_trades": len(self.trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl_usdt": total_pnl,
            "avg_pnl_usdt": avg_pnl,
            "avg_win_percent": avg_win,
            "avg_loss_percent": avg_loss,
            "tp_exits": len(tp_exits),
            "sl_exits": len(sl_exits),
        }

    def print_results(self, stats: Dict):
        """Zeigt Ergebnisse formatiert an"""
        print(f"\n{'='*60}")
        print(f"  BACKTEST ERGEBNISSE")
        print(f"{'='*60}")
        print(f"  Total Trades:     {stats['total_trades']}")
        print(f"  Gewinner:         {stats['wins']} ({stats['win_rate']:.1f}%)")
        print(f"  Verlierer:        {stats['losses']}")
        print(f"  TP Exits:         {stats['tp_exits']}")
        print(f"  SL Exits:         {stats['sl_exits']}")
        print(f"{'='*60}")
        print(f"  Avg Win:          +{stats['avg_win_percent']:.2f}%")
        print(f"  Avg Loss:         {stats['avg_loss_percent']:.2f}%")
        print(f"  Total PnL:        ${stats['total_pnl_usdt']:+,.2f}")
        print(f"  Avg PnL/Trade:    ${stats['avg_pnl_usdt']:+.2f}")
        print(f"{'='*60}")

        # Profit Factor
        gross_profit = sum(t.pnl_usdt for t in self.trades if t.pnl_usdt > 0)
        gross_loss = abs(sum(t.pnl_usdt for t in self.trades if t.pnl_usdt < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        print(f"  Profit Factor:    {profit_factor:.2f}")
        print(f"{'='*60}\n")

    def print_sample_trades(self, limit: int = 10):
        """Zeigt Beispiel-Trades"""
        print(f"\n{'='*80}")
        print(f"  BEISPIEL TRADES (letzte {limit})")
        print(f"{'='*80}")
        print(f"{'Symbol':<10} {'Entry':<12} {'Entry%':>8} {'Exit':>8} {'PnL%':>8} {'Reason':<6}")
        print("-" * 80)

        for trade in self.trades[-limit:]:
            symbol = trade.symbol.replace("USDT", "")
            print(f"{symbol:<10} {trade.entry_date:<12} {trade.entry_change:>+7.1f}% "
                  f"${trade.exit_price:>7.4f} {trade.pnl_percent:>+7.2f}% {trade.exit_reason:<6}")

        print(f"{'='*80}\n")

    def get_equity_curve(self, starting_capital: float = 1000) -> List[Dict]:
        """Berechnet die Kapitalkurve"""
        if not self.trades:
            return []

        # Trades nach Datum sortieren
        sorted_trades = sorted(self.trades, key=lambda x: x.exit_date)

        equity = starting_capital
        curve = [{"date": "Start", "equity": equity, "trade": None}]

        for trade in sorted_trades:
            equity += trade.pnl_usdt
            curve.append({
                "date": trade.exit_date,
                "equity": equity,
                "trade": trade.symbol.replace("USDT", ""),
                "pnl": trade.pnl_usdt
            })

        return curve

    def print_equity_curve(self, starting_capital: float = 1000):
        """Zeigt Kapitalkurve als ASCII-Chart"""
        curve = self.get_equity_curve(starting_capital)
        if not curve:
            print("Keine Trades für Kapitalkurve.")
            return

        print(f"\n{'='*70}")
        print(f"  KAPITALKURVE (Start: ${starting_capital:,.0f})")
        print(f"{'='*70}")

        # Min/Max für Skalierung
        equities = [c["equity"] for c in curve]
        min_eq = min(equities)
        max_eq = max(equities)
        range_eq = max_eq - min_eq if max_eq > min_eq else 1

        # ASCII Chart (40 Zeichen breit)
        chart_width = 40

        for i, point in enumerate(curve):
            if i == 0:
                continue  # Skip Start

            # Position berechnen
            pos = int((point["equity"] - min_eq) / range_eq * chart_width)
            pos = max(0, min(chart_width - 1, pos))

            # Zeile bauen
            bar = "─" * pos + "●"
            emoji = "🟢" if point.get("pnl", 0) >= 0 else "🔴"

            if i <= 20 or i >= len(curve) - 5:  # Erste 20 und letzte 5 zeigen
                print(f"  {emoji} ${point['equity']:>8,.0f} │{bar}")
            elif i == 21:
                print(f"  ... ({len(curve) - 25} weitere Trades) ...")

        print(f"{'='*70}")

        # Statistiken
        final_equity = curve[-1]["equity"]
        total_return = ((final_equity - starting_capital) / starting_capital) * 100
        max_drawdown = self._calculate_max_drawdown(curve)

        print(f"  Start:        ${starting_capital:,.0f}")
        print(f"  Ende:         ${final_equity:,.0f}")
        print(f"  Rendite:      {total_return:+.1f}%")
        print(f"  Max Drawdown: {max_drawdown:.1f}%")
        print(f"{'='*70}\n")

    def _calculate_max_drawdown(self, curve: List[Dict]) -> float:
        """Berechnet Maximum Drawdown"""
        if not curve:
            return 0

        peak = curve[0]["equity"]
        max_dd = 0

        for point in curve:
            if point["equity"] > peak:
                peak = point["equity"]
            dd = (peak - point["equity"]) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def export_trades_csv(self, filename: str = "backtest_trades.csv"):
        """Exportiert Trades als CSV"""
        if not self.trades:
            print("Keine Trades zum Exportieren.")
            return

        import csv
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Symbol", "Direction", "Entry Date", "Entry Price",
                           "Exit Date", "Exit Price", "Entry Change %",
                           "PnL %", "PnL USDT", "Exit Reason"])

            for t in self.trades:
                writer.writerow([
                    t.symbol, t.direction, t.entry_date, t.entry_price,
                    t.exit_date, t.exit_price, t.entry_change,
                    t.pnl_percent, t.pnl_usdt, t.exit_reason
                ])

        print(f"✅ {len(self.trades)} Trades exportiert nach: {filename}")


class ParameterOptimizer:
    """Optimiert Parameter für die Strategie"""

    def __init__(self):
        self.results = []

    def optimize(self, days_back: int = 365):
        """Testet verschiedene Parameter-Kombinationen"""
        print("\n" + "="*70)
        print("  PARAMETER OPTIMIZER")
        print("="*70)
        print(f"  Teste verschiedene Kombinationen über {days_back} Tage...")
        print("="*70 + "\n")

        # Parameter-Ranges
        buy_thresholds = [-5, -8, -10, -12, -15, -20]  # Long: Kaufe bei X% Verlust
        tp_values = [2, 3, 4, 5, 8, 10]  # Take Profit %
        sl_values = [2, 3, 5, 8, 10]  # Stop Loss %

        # Originale Config-Werte speichern
        orig_tp = config.TAKE_PROFIT_PERCENT
        orig_sl = config.STOP_LOSS_PERCENT

        backtester = Backtester()

        # Symbols einmal laden
        print("Lade Top Coins...")
        symbols = backtester.get_top_symbols(20)

        # Historische Daten einmal laden
        print("Lade historische Daten...")
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        symbol_data = {}

        for i, symbol in enumerate(symbols):
            print(f"  [{i+1}/{len(symbols)}] {symbol}", end="\r")
            klines = backtester.get_klines(symbol, "1d", start_time)
            if len(klines) >= 10:
                symbol_data[symbol] = backtester.calculate_daily_changes(klines)
            time.sleep(0.05)

        print(f"\n  {len(symbol_data)} Coins mit Daten geladen.\n")

        total_tests = len(buy_thresholds) * len(tp_values) * len(sl_values)
        current_test = 0

        for buy_thresh in buy_thresholds:
            for tp in tp_values:
                for sl in sl_values:
                    current_test += 1
                    print(f"  [{current_test}/{total_tests}] Buy: {buy_thresh}% | TP: +{tp}% | SL: -{sl}%", end="\r")

                    # Config temporär ändern
                    config.TAKE_PROFIT_PERCENT = tp
                    config.STOP_LOSS_PERCENT = sl

                    # Trades simulieren
                    trades = []
                    for symbol, changes in symbol_data.items():
                        for j, day in enumerate(changes[:-5]):
                            if day["change_percent"] <= buy_thresh:
                                future_days = changes[j+1:j+6]
                                if future_days:
                                    trade = backtester.simulate_trade(symbol, day, future_days)
                                    trades.append(trade)

                    if trades:
                        wins = len([t for t in trades if t.pnl_percent > 0])
                        total_pnl = sum(t.pnl_usdt for t in trades)
                        win_rate = wins / len(trades) * 100
                        avg_pnl = total_pnl / len(trades)

                        self.results.append({
                            "buy_threshold": buy_thresh,
                            "take_profit": tp,
                            "stop_loss": sl,
                            "trades": len(trades),
                            "win_rate": win_rate,
                            "total_pnl": total_pnl,
                            "avg_pnl": avg_pnl,
                        })

        # Original Config wiederherstellen
        config.TAKE_PROFIT_PERCENT = orig_tp
        config.STOP_LOSS_PERCENT = orig_sl

        print("\n\n" + "="*70)
        print("  OPTIMIERUNG ABGESCHLOSSEN")
        print("="*70)

        return self.results

    def print_best_results(self, top_n: int = 15):
        """Zeigt die besten Parameter-Kombinationen"""
        if not self.results:
            print("Keine Ergebnisse vorhanden.")
            return

        # Nach Profit sortieren
        sorted_by_profit = sorted(self.results, key=lambda x: x["total_pnl"], reverse=True)

        print(f"\n{'='*80}")
        print(f"  TOP {top_n} PARAMETER-KOMBINATIONEN (nach Profit)")
        print(f"{'='*80}")
        print(f"{'#':<3} {'Buy%':>6} {'TP%':>5} {'SL%':>5} {'Trades':>7} {'WinRate':>8} {'TotalPnL':>12} {'AvgPnL':>10}")
        print("-" * 80)

        for i, r in enumerate(sorted_by_profit[:top_n], 1):
            print(f"{i:<3} {r['buy_threshold']:>5}% {r['take_profit']:>4}% {r['stop_loss']:>4}% "
                  f"{r['trades']:>7} {r['win_rate']:>7.1f}% ${r['total_pnl']:>10,.0f} ${r['avg_pnl']:>9.2f}")

        print(f"{'='*80}")

        # Beste nach Win Rate
        sorted_by_winrate = sorted([r for r in self.results if r["trades"] >= 50],
                                   key=lambda x: x["win_rate"], reverse=True)

        if sorted_by_winrate:
            print(f"\n  TOP {min(5, len(sorted_by_winrate))} nach WIN RATE (min. 50 Trades):")
            print("-" * 60)
            for r in sorted_by_winrate[:5]:
                print(f"  Buy: {r['buy_threshold']}% | TP: +{r['take_profit']}% | SL: -{r['stop_loss']}% "
                      f"→ {r['win_rate']:.1f}% Win Rate")

        print()


class FullOptimizer:
    """Optimiert sowohl LONG als auch SHORT Parameter"""

    def __init__(self):
        self.long_results = []
        self.short_results = []

    def optimize(self, days_back: int = 365):
        """Testet LONG und SHORT Strategien"""
        print("\n" + "="*70)
        print("  FULL OPTIMIZER (LONG + SHORT)")
        print("="*70)

        backtester = Backtester()

        # Symbols laden
        print("Lade Top Coins...")
        symbols = backtester.get_top_symbols(25)

        # Daten laden
        print("Lade historische Daten...")
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
        symbol_data = {}

        for i, symbol in enumerate(symbols):
            print(f"  [{i+1}/{len(symbols)}] {symbol}", end="\r")
            klines = backtester.get_klines(symbol, "1d", start_time)
            if len(klines) >= 10:
                symbol_data[symbol] = backtester.calculate_daily_changes(klines)
            time.sleep(0.05)

        print(f"\n  {len(symbol_data)} Coins geladen.\n")

        # === LONG OPTIMIZATION ===
        print("="*70)
        print("  LONG STRATEGIE (Buy the Dip)")
        print("="*70)

        long_thresholds = [-5, -8, -10, -12, -15, -20]
        tp_values = [2, 3, 4, 5, 8, 10]
        sl_values = [2, 3, 5, 8, 10]

        total = len(long_thresholds) * len(tp_values) * len(sl_values)
        current = 0

        for thresh in long_thresholds:
            for tp in tp_values:
                for sl in sl_values:
                    current += 1
                    print(f"  LONG [{current}/{total}] Entry: {thresh}% | TP: +{tp}% | SL: -{sl}%", end="\r")

                    config.TAKE_PROFIT_PERCENT = tp
                    config.STOP_LOSS_PERCENT = sl

                    trades = []
                    for symbol, changes in symbol_data.items():
                        for j, day in enumerate(changes[:-5]):
                            if day["change_percent"] <= thresh:
                                future = changes[j+1:j+6]
                                if future:
                                    trade = backtester.simulate_trade(symbol, day, future)
                                    trades.append(trade)

                    if trades:
                        wins = len([t for t in trades if t.pnl_percent > 0])
                        total_pnl = sum(t.pnl_usdt for t in trades)
                        self.long_results.append({
                            "direction": "LONG",
                            "entry_threshold": thresh,
                            "take_profit": tp,
                            "stop_loss": sl,
                            "trades": len(trades),
                            "win_rate": wins / len(trades) * 100,
                            "total_pnl": total_pnl,
                            "avg_pnl": total_pnl / len(trades),
                        })

        print("\n")

        # === SHORT OPTIMIZATION ===
        print("="*70)
        print("  SHORT STRATEGIE (Fade the Pump)")
        print("="*70)

        short_thresholds = [10, 15, 20, 25, 30, 40]  # Short bei +X%

        total = len(short_thresholds) * len(tp_values) * len(sl_values)
        current = 0

        for thresh in short_thresholds:
            for tp in tp_values:
                for sl in sl_values:
                    current += 1
                    print(f"  SHORT [{current}/{total}] Entry: +{thresh}% | TP: +{tp}% | SL: -{sl}%", end="\r")

                    trades = []
                    for symbol, changes in symbol_data.items():
                        for j, day in enumerate(changes[:-5]):
                            if day["change_percent"] >= thresh:  # Coin stark gestiegen
                                future = changes[j+1:j+6]
                                if future:
                                    trade = backtester.simulate_short_trade(
                                        symbol, day, future, tp_percent=tp, sl_percent=sl
                                    )
                                    trades.append(trade)

                    if trades:
                        wins = len([t for t in trades if t.pnl_percent > 0])
                        total_pnl = sum(t.pnl_usdt for t in trades)
                        self.short_results.append({
                            "direction": "SHORT",
                            "entry_threshold": thresh,
                            "take_profit": tp,
                            "stop_loss": sl,
                            "trades": len(trades),
                            "win_rate": wins / len(trades) * 100,
                            "total_pnl": total_pnl,
                            "avg_pnl": total_pnl / len(trades),
                        })

        print("\n\n" + "="*70)
        print("  OPTIMIERUNG ABGESCHLOSSEN")
        print("="*70)

    def print_results(self, top_n: int = 10):
        """Zeigt die besten Ergebnisse für LONG und SHORT"""

        # LONG Results
        if self.long_results:
            sorted_long = sorted(self.long_results, key=lambda x: x["total_pnl"], reverse=True)

            print(f"\n{'='*85}")
            print(f"  TOP {top_n} LONG STRATEGIEN (Buy the Dip)")
            print(f"{'='*85}")
            print(f"{'#':<3} {'Entry':>7} {'TP':>5} {'SL':>5} {'Trades':>7} {'Win%':>7} {'TotalPnL':>12} {'Avg':>10}")
            print("-" * 85)

            for i, r in enumerate(sorted_long[:top_n], 1):
                print(f"{i:<3} {r['entry_threshold']:>6}% {r['take_profit']:>4}% {r['stop_loss']:>4}% "
                      f"{r['trades']:>7} {r['win_rate']:>6.1f}% ${r['total_pnl']:>10,.0f} ${r['avg_pnl']:>9.2f}")

        # SHORT Results
        if self.short_results:
            sorted_short = sorted(self.short_results, key=lambda x: x["total_pnl"], reverse=True)

            print(f"\n{'='*85}")
            print(f"  TOP {top_n} SHORT STRATEGIEN (Fade the Pump)")
            print(f"{'='*85}")
            print(f"{'#':<3} {'Entry':>7} {'TP':>5} {'SL':>5} {'Trades':>7} {'Win%':>7} {'TotalPnL':>12} {'Avg':>10}")
            print("-" * 85)

            for i, r in enumerate(sorted_short[:top_n], 1):
                print(f"{i:<3} +{r['entry_threshold']:>5}% {r['take_profit']:>4}% {r['stop_loss']:>4}% "
                      f"{r['trades']:>7} {r['win_rate']:>6.1f}% ${r['total_pnl']:>10,.0f} ${r['avg_pnl']:>9.2f}")

        # Beste Kombinationen
        print(f"\n{'='*85}")
        print("  EMPFOHLENE PARAMETER")
        print(f"{'='*85}")

        if self.long_results:
            best_long = max(self.long_results, key=lambda x: x["total_pnl"])
            print(f"  LONG:  Entry: {best_long['entry_threshold']}% | TP: +{best_long['take_profit']}% | "
                  f"SL: -{best_long['stop_loss']}% → {best_long['win_rate']:.1f}% Win Rate")

        if self.short_results:
            best_short = max(self.short_results, key=lambda x: x["total_pnl"])
            print(f"  SHORT: Entry: +{best_short['entry_threshold']}% | TP: +{best_short['take_profit']}% | "
                  f"SL: -{best_short['stop_loss']}% → {best_short['win_rate']:.1f}% Win Rate")

        print(f"{'='*85}\n")


class BreakoutBacktester:
    """Backtester für Breakout-Strategie"""

    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self):
        self.session = requests.Session()
        self.trades: List[BacktestTrade] = []

    def get_klines(self, symbol: str, interval: str = "1d",
                   start_time: int = None, limit: int = 1000) -> List[Dict]:
        """Holt historische Klines"""
        url = f"{self.BASE_URL}/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time:
            params["startTime"] = start_time

        response = self.session.get(url, params=params)
        if response.status_code != 200:
            return []

        return [{
            "date": datetime.fromtimestamp(k[0] / 1000).strftime("%Y-%m-%d"),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        } for k in response.json()]

    def get_top_symbols(self, limit: int = 30) -> List[str]:
        """Holt Top Coins nach Volumen"""
        url = f"{self.BASE_URL}/ticker/24hr"
        response = self.session.get(url)
        if response.status_code != 200:
            return []

        tickers = response.json()
        usdt_pairs = [
            t for t in tickers
            if t["symbol"].endswith("USDT")
            and float(t["quoteVolume"]) > config.MIN_VOLUME_USDT
            and not any(s in t["symbol"] for s in ["USDC", "BUSD", "DAI", "TUSD", "FDUSD"])
        ]
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x["quoteVolume"]), reverse=True)
        return [p["symbol"] for p in sorted_pairs[:limit]]

    def detect_breakout(self, klines: List[Dict], idx: int, lookback: int = 5) -> str:
        """
        Prüft ob an Position idx ein Breakout stattfindet.
        Returns: "UP", "DOWN", oder "NONE"
        """
        if idx < lookback:
            return "NONE"

        current = klines[idx]
        previous = klines[idx - lookback:idx]

        highest_high = max(k["high"] for k in previous)
        lowest_low = min(k["low"] for k in previous)

        breakout_up = highest_high * (1 + config.BREAKOUT_MIN_PERCENT / 100)
        breakout_down = lowest_low * (1 - config.BREAKOUT_MIN_PERCENT / 100)

        if current["close"] >= breakout_up:
            return "UP"
        elif current["close"] <= breakout_down:
            return "DOWN"
        return "NONE"

    def simulate_breakout_trade(self, symbol: str, entry_data: Dict,
                                future_klines: List[Dict], direction: str,
                                tp_percent: float, sl_percent: float) -> BacktestTrade:
        """Simuliert einen Breakout-Trade"""
        entry_price = entry_data["close"]
        entry_date = entry_data["date"]
        position_size = config.MAX_POSITION_SIZE

        if direction == "LONG":
            tp_price = entry_price * (1 + tp_percent / 100)
            sl_price = entry_price * (1 - sl_percent / 100)

            for day in future_klines:
                if day["high"] >= tp_price:
                    return BacktestTrade(
                        symbol=symbol, entry_date=entry_date, entry_price=entry_price,
                        exit_date=day["date"], exit_price=tp_price,
                        entry_change=0, pnl_percent=tp_percent,
                        pnl_usdt=position_size * tp_percent / 100,
                        exit_reason="TP", direction="LONG"
                    )
                if day["low"] <= sl_price:
                    return BacktestTrade(
                        symbol=symbol, entry_date=entry_date, entry_price=entry_price,
                        exit_date=day["date"], exit_price=sl_price,
                        entry_change=0, pnl_percent=-sl_percent,
                        pnl_usdt=position_size * -sl_percent / 100,
                        exit_reason="SL", direction="LONG"
                    )
        else:  # SHORT
            tp_price = entry_price * (1 - tp_percent / 100)
            sl_price = entry_price * (1 + sl_percent / 100)

            for day in future_klines:
                if day["low"] <= tp_price:
                    return BacktestTrade(
                        symbol=symbol, entry_date=entry_date, entry_price=entry_price,
                        exit_date=day["date"], exit_price=tp_price,
                        entry_change=0, pnl_percent=tp_percent,
                        pnl_usdt=position_size * tp_percent / 100,
                        exit_reason="TP", direction="SHORT"
                    )
                if day["high"] >= sl_price:
                    return BacktestTrade(
                        symbol=symbol, entry_date=entry_date, entry_price=entry_price,
                        exit_date=day["date"], exit_price=sl_price,
                        entry_change=0, pnl_percent=-sl_percent,
                        pnl_usdt=position_size * -sl_percent / 100,
                        exit_reason="SL", direction="SHORT"
                    )

        # Trade noch offen
        last = future_klines[-1] if future_klines else entry_data
        if direction == "LONG":
            pnl = ((last["close"] - entry_price) / entry_price) * 100
        else:
            pnl = ((entry_price - last["close"]) / entry_price) * 100

        return BacktestTrade(
            symbol=symbol, entry_date=entry_date, entry_price=entry_price,
            exit_date=last["date"], exit_price=last["close"],
            entry_change=0, pnl_percent=pnl,
            pnl_usdt=position_size * pnl / 100,
            exit_reason="END", direction=direction
        )

    def run_backtest(self, days_back: int = 180, lookback: int = 5,
                     tp_percent: float = 6.0, sl_percent: float = 3.0) -> Dict:
        """Führt Breakout-Backtest durch"""
        print(f"\n{'='*70}")
        print("  BREAKOUT BACKTEST")
        print(f"{'='*70}")
        print(f"  Lookback: {lookback} Tage | TP: +{tp_percent}% | SL: -{sl_percent}%")
        print(f"  Breakout Min: {config.BREAKOUT_MIN_PERCENT}%")
        print(f"{'='*70}\n")

        symbols = self.get_top_symbols(25)
        print(f"Teste {len(symbols)} Coins über {days_back} Tage...\n")

        self.trades = []
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)

        for i, symbol in enumerate(symbols):
            print(f"  [{i+1}/{len(symbols)}] {symbol}...", end="\r")

            klines = self.get_klines(symbol, "1d", start_time)
            if len(klines) < lookback + 10:
                continue

            for j in range(lookback, len(klines) - 5):
                breakout = self.detect_breakout(klines, j, lookback)

                if breakout == "UP":
                    future = klines[j+1:j+6]
                    trade = self.simulate_breakout_trade(
                        symbol, klines[j], future, "LONG", tp_percent, sl_percent
                    )
                    self.trades.append(trade)

                elif breakout == "DOWN":
                    future = klines[j+1:j+6]
                    trade = self.simulate_breakout_trade(
                        symbol, klines[j], future, "SHORT", tp_percent, sl_percent
                    )
                    self.trades.append(trade)

            time.sleep(0.05)

        return self.get_statistics()

    def get_statistics(self) -> Dict:
        """Berechnet Statistiken"""
        if not self.trades:
            return {"error": "Keine Trades"}

        long_trades = [t for t in self.trades if t.direction == "LONG"]
        short_trades = [t for t in self.trades if t.direction == "SHORT"]
        wins = [t for t in self.trades if t.pnl_percent > 0]
        losses = [t for t in self.trades if t.pnl_percent < 0]

        total_pnl = sum(t.pnl_usdt for t in self.trades)

        return {
            "total_trades": len(self.trades),
            "long_trades": len(long_trades),
            "short_trades": len(short_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self.trades) * 100 if self.trades else 0,
            "total_pnl_usdt": total_pnl,
            "avg_pnl_usdt": total_pnl / len(self.trades) if self.trades else 0,
            "long_pnl": sum(t.pnl_usdt for t in long_trades),
            "short_pnl": sum(t.pnl_usdt for t in short_trades),
        }

    def print_results(self, stats: Dict):
        """Zeigt Ergebnisse"""
        print(f"\n{'='*60}")
        print("  BREAKOUT BACKTEST ERGEBNISSE")
        print(f"{'='*60}")
        print(f"  Total Trades:   {stats['total_trades']}")
        print(f"    LONG:         {stats['long_trades']} (PnL: ${stats['long_pnl']:+,.0f})")
        print(f"    SHORT:        {stats['short_trades']} (PnL: ${stats['short_pnl']:+,.0f})")
        print(f"  Win Rate:       {stats['win_rate']:.1f}%")
        print(f"{'='*60}")
        print(f"  Total PnL:      ${stats['total_pnl_usdt']:+,.0f}")
        print(f"  Avg PnL/Trade:  ${stats['avg_pnl_usdt']:+.2f}")
        print(f"{'='*60}\n")

    def optimize(self, days_back: int = 180):
        """Optimiert Breakout-Parameter"""
        print(f"\n{'='*70}")
        print("  BREAKOUT PARAMETER OPTIMIZER")
        print(f"{'='*70}\n")

        symbols = self.get_top_symbols(20)
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)

        # Daten laden
        print("Lade Daten...")
        symbol_data = {}
        for i, symbol in enumerate(symbols):
            print(f"  [{i+1}/{len(symbols)}] {symbol}", end="\r")
            klines = self.get_klines(symbol, "1d", start_time)
            if len(klines) >= 20:
                symbol_data[symbol] = klines
            time.sleep(0.03)

        print(f"\n  {len(symbol_data)} Coins geladen.\n")

        # Parameter-Ranges
        lookbacks = [3, 5, 7, 10]
        tps = [4, 6, 8, 10]
        sls = [2, 3, 4, 5]

        results = []
        total = len(lookbacks) * len(tps) * len(sls)
        current = 0

        for lb in lookbacks:
            for tp in tps:
                for sl in sls:
                    current += 1
                    print(f"  [{current}/{total}] Lookback={lb} TP={tp}% SL={sl}%", end="\r")

                    trades = []
                    for symbol, klines in symbol_data.items():
                        for j in range(lb, len(klines) - 5):
                            breakout = self.detect_breakout(klines, j, lb)
                            if breakout != "NONE":
                                future = klines[j+1:j+6]
                                direction = "LONG" if breakout == "UP" else "SHORT"
                                trade = self.simulate_breakout_trade(
                                    symbol, klines[j], future, direction, tp, sl
                                )
                                trades.append(trade)

                    if trades:
                        wins = len([t for t in trades if t.pnl_percent > 0])
                        total_pnl = sum(t.pnl_usdt for t in trades)
                        results.append({
                            "lookback": lb,
                            "tp": tp,
                            "sl": sl,
                            "trades": len(trades),
                            "win_rate": wins / len(trades) * 100,
                            "total_pnl": total_pnl,
                            "avg_pnl": total_pnl / len(trades),
                        })

        # Beste Ergebnisse
        sorted_results = sorted(results, key=lambda x: x["total_pnl"], reverse=True)

        print(f"\n\n{'='*80}")
        print("  TOP 10 BREAKOUT PARAMETER")
        print(f"{'='*80}")
        print(f"{'#':<3} {'LB':>4} {'TP':>5} {'SL':>5} {'Trades':>7} {'Win%':>7} {'PnL':>12} {'Avg':>10}")
        print("-" * 80)

        for i, r in enumerate(sorted_results[:10], 1):
            print(f"{i:<3} {r['lookback']:>4} {r['tp']:>4}% {r['sl']:>4}% "
                  f"{r['trades']:>7} {r['win_rate']:>6.1f}% ${r['total_pnl']:>10,.0f} ${r['avg_pnl']:>9.2f}")

        print(f"{'='*80}\n")

        if sorted_results:
            best = sorted_results[0]
            print(f"  BESTE PARAMETER:")
            print(f"  Lookback: {best['lookback']} Tage | TP: +{best['tp']}% | SL: -{best['sl']}%")
            print(f"  → {best['win_rate']:.1f}% Win Rate | ${best['total_pnl']:+,.0f} Total PnL\n")


def run_interactive_backtest():
    """Interaktiver Backtest"""
    print("\n" + "="*50)
    print("  BACKTEST KONFIGURATION")
    print("="*50)
    print("  1. Mean Reversion Backtest (LONG)")
    print("  2. Mean Reversion Optimizer (LONG)")
    print("  3. Mean Reversion FULL (LONG + SHORT)")
    print("  4. BREAKOUT Backtest")
    print("  5. BREAKOUT Optimizer")
    print("="*50)

    mode = input("  Auswahl [4]: ").strip() or "4"

    if mode == "5":
        # Breakout Optimizer
        days = input(f"  Tage zurück [180]: ").strip()
        days = int(days) if days else 180

        bb = BreakoutBacktester()
        bb.optimize(days_back=days)
        return None

    if mode == "4":
        # Breakout Backtest
        days = input(f"  Tage zurück [180]: ").strip()
        days = int(days) if days else 180

        lookback = input(f"  Lookback Tage [{config.BREAKOUT_LOOKBACK_DAYS}]: ").strip()
        lookback = int(lookback) if lookback else config.BREAKOUT_LOOKBACK_DAYS

        tp = input(f"  Take Profit % [6]: ").strip()
        tp = float(tp) if tp else 6.0

        sl = input(f"  Stop Loss % [3]: ").strip()
        sl = float(sl) if sl else 3.0

        bb = BreakoutBacktester()
        stats = bb.run_backtest(days_back=days, lookback=lookback, tp_percent=tp, sl_percent=sl)
        bb.print_results(stats)
        return stats

    if mode == "3":
        # Full Optimizer
        days = input(f"  Tage zurück [180]: ").strip()
        days = int(days) if days else 180

        optimizer = FullOptimizer()
        optimizer.optimize(days_back=days)
        optimizer.print_results()
        return None

    if mode == "2":
        # Long Optimizer
        days = input(f"  Tage zurück [180]: ").strip()
        days = int(days) if days else 180

        optimizer = ParameterOptimizer()
        optimizer.optimize(days_back=days)
        optimizer.print_best_results()
        return None

    # Einzelner Backtest (mode == "1")
    backtester = Backtester()
    days = input(f"  Tage zurück [365]: ").strip()
    days = int(days) if days else 365

    threshold = input(f"  Buy Threshold [{config.BUY_LOSER_THRESHOLD}%]: ").strip()
    threshold = float(threshold) if threshold else config.BUY_LOSER_THRESHOLD

    print("\nStarte Backtest...")
    stats = backtester.run_backtest(days_back=days, buy_threshold=threshold)

    backtester.print_results(stats)
    backtester.print_sample_trades()
    backtester.print_equity_curve()

    # CSV Export anbieten
    export = input("  Trades als CSV exportieren? (j/n) [n]: ").strip().lower()
    if export == "j":
        backtester.export_trades_csv()

    return stats


if __name__ == "__main__":
    run_interactive_backtest()
