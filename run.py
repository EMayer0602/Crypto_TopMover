#!/usr/bin/env python3
"""
Crypto TopMover - Haupteinstieg
===============================
Scannt Binance nach Top Gainern/Losern und ermöglicht Paper Trading.
"""

import time
import sys
from data_fetcher import BinanceScanner, print_top_movers
from paper_trader import PaperTrader
import config


def show_menu():
    """Zeigt das Hauptmenü"""
    print(f"\n{'='*50}")
    print("  🚀 CRYPTO TOPMOVER - PAPER TRADING BOT")
    print(f"{'='*50}")
    print("  1. Top Movers anzeigen (Gainer & Loser)")
    print("  2. Top Gainer anzeigen")
    print("  3. Top Loser anzeigen")
    print("  4. Position kaufen")
    print("  5. Position verkaufen")
    print("  6. Offene Positionen anzeigen")
    print("  7. Trading Statistiken")
    print("  8. Auto-Trading starten (TP/SL Überwachung)")
    print("  9. Paper Trader zurücksetzen")
    print("  0. Beenden")
    print(f"{'='*50}")
    print(f"  Balance: ${trader.balance:,.2f} | Positionen: {len(trader.positions)}")
    print(f"{'='*50}")
    return input("\n  Auswahl: ").strip()


def buy_menu():
    """Menü zum Kaufen"""
    print("\n--- TOP GAINER ---")
    gainers = scanner.get_top_gainers(5)
    for i, coin in enumerate(gainers, 1):
        print(f"  {i}. {coin['base']:<8} {coin['change_percent']:>+6.2f}% @ ${coin['price']:.4f}")

    print(f"\n  Verfügbare Balance: ${trader.balance:.2f}")
    symbol_input = input("  Symbol eingeben (z.B. BTCUSDT) oder # wählen: ").strip().upper()

    if symbol_input.isdigit():
        idx = int(symbol_input) - 1
        if 0 <= idx < len(gainers):
            symbol = gainers[idx]["symbol"]
        else:
            print("❌ Ungültige Auswahl!")
            return
    else:
        symbol = symbol_input if symbol_input.endswith("USDT") else symbol_input + "USDT"

    amount = input(f"  Betrag in USDT [{config.MAX_POSITION_SIZE}]: ").strip()
    amount = float(amount) if amount else config.MAX_POSITION_SIZE

    trader.buy(symbol, amount)


def sell_menu():
    """Menü zum Verkaufen"""
    if not trader.positions:
        print("\n📭 Keine offenen Positionen zum Verkaufen.")
        return

    print("\n--- OFFENE POSITIONEN ---")
    positions_list = list(trader.positions.keys())
    for i, symbol in enumerate(positions_list, 1):
        pos = trader.positions[symbol]
        current_price = scanner.get_ticker_price(symbol) or pos.entry_price
        pnl = pos.pnl_percent(current_price)
        print(f"  {i}. {pos.base:<8} {pnl:>+6.2f}%")

    choice = input("  Position wählen (#) oder Symbol: ").strip().upper()

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(positions_list):
            symbol = positions_list[idx]
        else:
            print("❌ Ungültige Auswahl!")
            return
    else:
        symbol = choice if choice.endswith("USDT") else choice + "USDT"

    trader.sell(symbol)


def auto_trading():
    """Auto-Trading mit TP/SL Überwachung"""
    print(f"\n🤖 Auto-Trading gestartet!")
    print(f"   Take Profit: +{config.TAKE_PROFIT_PERCENT}%")
    print(f"   Stop Loss:   -{config.STOP_LOSS_PERCENT}%")
    print(f"   Interval:    {config.SCAN_INTERVAL_SECONDS}s")
    print("   [Strg+C zum Beenden]\n")

    try:
        while True:
            # Positionen prüfen
            trader.check_positions()

            # Status anzeigen
            if trader.positions:
                print(f"[{time.strftime('%H:%M:%S')}] Überwache {len(trader.positions)} Position(en)...")
                for symbol, pos in trader.positions.items():
                    price = scanner.get_ticker_price(symbol) or pos.entry_price
                    pnl = pos.pnl_percent(price)
                    print(f"   {pos.base}: {pnl:+.2f}%")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Keine Positionen offen.")

            time.sleep(config.SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n\n⏹️  Auto-Trading beendet.")


def main():
    """Hauptschleife"""
    while True:
        try:
            choice = show_menu()

            if choice == "1":
                movers = scanner.get_top_movers()
                print_top_movers(movers)

            elif choice == "2":
                gainers = scanner.get_top_gainers()
                print_top_movers({"gainers": gainers, "losers": []})

            elif choice == "3":
                losers = scanner.get_top_losers()
                print_top_movers({"gainers": [], "losers": losers})

            elif choice == "4":
                buy_menu()

            elif choice == "5":
                sell_menu()

            elif choice == "6":
                trader.show_positions()

            elif choice == "7":
                trader.show_stats()

            elif choice == "8":
                auto_trading()

            elif choice == "9":
                confirm = input("  Wirklich zurücksetzen? (j/n): ").lower()
                if confirm == "j":
                    trader.reset()

            elif choice == "0":
                print("\n👋 Auf Wiedersehen!\n")
                sys.exit(0)

            else:
                print("❌ Ungültige Auswahl!")

        except KeyboardInterrupt:
            print("\n\n👋 Auf Wiedersehen!\n")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Fehler: {e}\n")


if __name__ == "__main__":
    print("\n🔄 Initialisiere...")
    scanner = BinanceScanner()
    trader = PaperTrader()
    main()
