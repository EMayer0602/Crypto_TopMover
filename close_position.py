#!/usr/bin/env python3
"""
Manuelles Schließen von Positionen
Nutzung: python close_position.py SYMBOL SIDE
Beispiel: python close_position.py BROCCOLI714USDT SHORT
"""

import sys
from testnet_trader import BinanceTestnetTrader

def main():
    if len(sys.argv) < 3:
        print("Nutzung: python close_position.py SYMBOL SIDE")
        print("Beispiel: python close_position.py BROCCOLI714USDT SHORT")
        print("\nVerfügbare Positionen:")
        trader = BinanceTestnetTrader()
        trader.show_status()
        return

    symbol = sys.argv[1].upper()
    side = sys.argv[2].upper()

    if not symbol.endswith("USDT"):
        symbol += "USDT"

    trader = BinanceTestnetTrader()

    print(f"\n🔄 Schließe {side} Position für {symbol}...")

    if side == "SHORT":
        result = trader.futures_close_short(symbol)
    elif side == "LONG":
        result = trader.futures_close_long(symbol)
    else:
        print(f"❌ Ungültige Seite: {side}. Nutze LONG oder SHORT.")
        return

    if result:
        print("✅ Position erfolgreich geschlossen!")
    else:
        print("❌ Konnte Position nicht schließen. Prüfe die Logs oben.")

    print("\n📊 Aktueller Status:")
    trader.show_status()


if __name__ == "__main__":
    main()
