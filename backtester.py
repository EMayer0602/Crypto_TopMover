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


def run_interactive_backtest():
    """Interaktiver Backtest"""
    backtester = Backtester()

    print("\n" + "="*50)
    print("  BACKTEST KONFIGURATION")
    print("="*50)
    print("  1. Einzelner Backtest")
    print("  2. Parameter Optimizer")
    print("="*50)

    mode = input("  Auswahl [1]: ").strip()

    if mode == "2":
        # Optimizer
        days = input(f"  Tage zurück [180]: ").strip()
        days = int(days) if days else 180

        optimizer = ParameterOptimizer()
        optimizer.optimize(days_back=days)
        optimizer.print_best_results()
        return None

    # Einzelner Backtest
    days = input(f"  Tage zurück [365]: ").strip()
    days = int(days) if days else 365

    threshold = input(f"  Buy Threshold [{config.BUY_LOSER_THRESHOLD}%]: ").strip()
    threshold = float(threshold) if threshold else config.BUY_LOSER_THRESHOLD

    print("\nStarte Backtest...")
    stats = backtester.run_backtest(days_back=days, buy_threshold=threshold)

    backtester.print_results(stats)
    backtester.print_sample_trades()

    return stats


if __name__ == "__main__":
    run_interactive_backtest()
