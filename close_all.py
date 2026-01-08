#!/usr/bin/env python3
"""
Close All Positions - Schnelles Schließen aller Positionen

Dieses Skript erstellt ein Signal-File, das vom laufenden Trader
erkannt wird und alle Positionen sofort schließt.

Verwendung:
    python close_all.py         # Sendet Signal an laufenden Trader
    python close_all.py --now   # Schließt direkt (wenn Trader nicht läuft)
"""

import sys
import os

# Signal-File Pfad
SIGNAL_FILE = "close_all.signal"


def send_signal():
    """Erstellt Signal-File für den laufenden Trader"""
    try:
        with open(SIGNAL_FILE, "w") as f:
            f.write("CLOSE_ALL")
        print("\n" + "=" * 50)
        print("  🚨 CLOSE ALL SIGNAL GESENDET!")
        print("=" * 50)
        print("\n  Der Trader wird alle Positionen schließen")
        print("  sobald der nächste Scan-Zyklus startet.")
        print("\n  (Max. Wartezeit: 60 Sekunden)")
        print("=" * 50 + "\n")
        return True
    except Exception as e:
        print(f"❌ Fehler beim Erstellen des Signals: {e}")
        return False


def close_now():
    """Schließt Positionen direkt (wenn Trader nicht läuft)"""
    try:
        from testnet_trader import BinanceTestnetTrader
        trader = BinanceTestnetTrader()

        if not trader.positions:
            print("\n  Keine offenen Positionen vorhanden.\n")
            return

        result = trader.close_all_positions()
        print(f"\n  Ergebnis: {result}")

    except Exception as e:
        print(f"❌ Fehler: {e}")
        print("\n  Tipp: Starte den Trader und verwende dann:")
        print("        python close_all.py")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  ⚠️  CLOSE ALL POSITIONS")
    print("=" * 50)

    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        print("\n  Modus: Direktes Schließen")
        close_now()
    else:
        print("\n  Modus: Signal an laufenden Trader senden")
        send_signal()
