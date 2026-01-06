"""
Auto-Optimizer für Crypto TopMover
==================================
Führt automatisch den Breakout-Optimizer aus und
aktualisiert config.py mit den besten Parametern.
"""

import sys
import re
from backtester import BreakoutBacktester
from datetime import datetime, timedelta
import config

def run_auto_optimize(days_back: int = 180, start_trading: bool = False):
    """
    Automatischer Ablauf:
    1. Breakout-Optimizer laufen lassen
    2. Beste Parameter finden
    3. config.py automatisch aktualisieren
    4. Optional: Testnet-Trading starten
    """
    print("\n" + "="*70)
    print("  🚀 AUTO-OPTIMIZER")
    print("="*70)
    print(f"  Zeitraum: {days_back} Tage")
    print(f"  Auto-Start Trading: {'Ja' if start_trading else 'Nein'}")
    print("="*70 + "\n")

    # 1. Optimizer laufen lassen
    bb = BreakoutBacktester()

    print("Lade Daten...")
    symbols = bb.get_top_symbols(20)
    start_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)

    symbol_data = {}
    for i, symbol in enumerate(symbols):
        print(f"  [{i+1}/{len(symbols)}] {symbol}", end="\r")
        klines = bb.get_klines(symbol, "1d", start_time)
        if len(klines) >= 20:
            symbol_data[symbol] = klines

    print(f"\n  {len(symbol_data)} Coins geladen.\n")

    # Parameter-Ranges
    lookbacks = [3, 5, 7, 10]
    tps = [4, 6, 8, 10, 12]
    sls = [2, 3, 4, 5]
    breakout_mins = [1.0, 2.0, 3.0]

    results = []
    total = len(lookbacks) * len(tps) * len(sls) * len(breakout_mins)
    current = 0

    print(f"Teste {total} Kombinationen...\n")

    for lb in lookbacks:
        for tp in tps:
            for sl in sls:
                for bm in breakout_mins:
                    current += 1
                    print(f"  [{current}/{total}] LB={lb} TP={tp}% SL={sl}% BM={bm}%", end="\r")

                    # Temporär BREAKOUT_MIN_PERCENT ändern für Test
                    orig_bm = config.BREAKOUT_MIN_PERCENT
                    config.BREAKOUT_MIN_PERCENT = bm

                    trades = []
                    for symbol, klines in symbol_data.items():
                        for j in range(lb, len(klines) - 5):
                            breakout = bb.detect_breakout(klines, j, lb)
                            if breakout != "NONE":
                                future = klines[j+1:j+6]
                                direction = "LONG" if breakout == "UP" else "SHORT"
                                trade = bb.simulate_breakout_trade(
                                    symbol, klines[j], future, direction, tp, sl
                                )
                                trades.append(trade)

                    config.BREAKOUT_MIN_PERCENT = orig_bm

                    if trades:
                        wins = len([t for t in trades if t.pnl_percent > 0])
                        total_pnl = sum(t.pnl_usdt for t in trades)
                        results.append({
                            "lookback": lb,
                            "tp": tp,
                            "sl": sl,
                            "breakout_min": bm,
                            "trades": len(trades),
                            "win_rate": wins / len(trades) * 100,
                            "total_pnl": total_pnl,
                            "avg_pnl": total_pnl / len(trades),
                        })

    # Beste Ergebnisse
    sorted_results = sorted(results, key=lambda x: x["total_pnl"], reverse=True)

    print(f"\n\n{'='*90}")
    print("  TOP 10 PARAMETER-KOMBINATIONEN")
    print(f"{'='*90}")
    print(f"{'#':<3} {'LB':>4} {'TP':>5} {'SL':>5} {'BM':>5} {'Trades':>7} {'Win%':>7} {'PnL':>12} {'Avg':>10}")
    print("-" * 90)

    for i, r in enumerate(sorted_results[:10], 1):
        print(f"{i:<3} {r['lookback']:>4} {r['tp']:>4}% {r['sl']:>4}% {r['breakout_min']:>4}% "
              f"{r['trades']:>7} {r['win_rate']:>6.1f}% ${r['total_pnl']:>10,.0f} ${r['avg_pnl']:>9.2f}")

    print(f"{'='*90}\n")

    if not sorted_results:
        print("❌ Keine Ergebnisse gefunden!")
        return

    best = sorted_results[0]

    print(f"  🏆 BESTE PARAMETER:")
    print(f"  Lookback: {best['lookback']} Tage")
    print(f"  Take Profit: +{best['tp']}%")
    print(f"  Stop Loss: -{best['sl']}%")
    print(f"  Breakout Min: {best['breakout_min']}%")
    print(f"  → {best['win_rate']:.1f}% Win Rate | ${best['total_pnl']:+,.0f} Total PnL\n")

    # 2. Config aktualisieren
    print("="*70)
    print("  📝 Aktualisiere config.py...")
    print("="*70)

    update_config(
        lookback=best['lookback'],
        tp=best['tp'],
        sl=best['sl'],
        breakout_min=best['breakout_min']
    )

    print("  ✅ config.py aktualisiert!\n")

    # 3. Optional: Trading starten
    if start_trading:
        print("="*70)
        print("  🤖 Starte Testnet Trading...")
        print("="*70 + "\n")
        from testnet_trader import run_testnet_auto_trading
        run_testnet_auto_trading()


def update_config(lookback: int, tp: float, sl: float, breakout_min: float):
    """Aktualisiert config.py mit neuen Parametern"""

    config_path = "config.py"

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parameter ersetzen
    replacements = [
        (r"BREAKOUT_LOOKBACK_DAYS\s*=\s*\d+", f"BREAKOUT_LOOKBACK_DAYS = {lookback}"),
        (r"TAKE_PROFIT_PERCENT\s*=\s*[\d.]+", f"TAKE_PROFIT_PERCENT = {tp}"),
        (r"STOP_LOSS_PERCENT\s*=\s*[\d.]+", f"STOP_LOSS_PERCENT = {sl}"),
        (r"BREAKOUT_MIN_PERCENT\s*=\s*[\d.]+", f"BREAKOUT_MIN_PERCENT = {breakout_min}"),
    ]

    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
        print(f"    {replacement}")

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    # Standard: 180 Tage, kein Auto-Start
    days = 180
    auto_start = False

    # Kommandozeilen-Argumente
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except:
            pass

    if "--start" in sys.argv or "-s" in sys.argv:
        auto_start = True

    run_auto_optimize(days_back=days, start_trading=auto_start)
