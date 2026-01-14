#!/usr/bin/env python3
"""
Manuelles Schließen von LONG Positionen
Nutzung: python close_position.py SYMBOL
Beispiel: python close_position.py BTCUSDT
"""

import sys
from testnet_trader import BinanceTestnetTrader

def main():
    if len(sys.argv) < 2:
        print("Nutzung: python close_position.py SYMBOL")
        print("Beispiel: python close_position.py BTCUSDT")
        print("\nVerfügbare Positionen:")
        trader = BinanceTestnetTrader()
        trader.show_status()
        return

    symbol = sys.argv[1].upper()

    if not symbol.endswith("USDT"):
        symbol += "USDT"

    trader = BinanceTestnetTrader()

    print(f"\n🔄 Schließe LONG Position für {symbol}...")
    result = trader.futures_close_long(symbol)

    if result:
        print("✅ Position erfolgreich geschlossen!")
    else:
        print("❌ Konnte Position nicht schließen. Prüfe die Logs oben.")

    print("\n📊 Aktueller Status:")
    trader.show_status()


if __name__ == "__main__":
    main()
