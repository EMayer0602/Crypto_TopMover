#!/usr/bin/env python3
"""
Schneller API-Verbindungstest für Binance Testnet
"""

import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv

load_dotenv()

TESTNET_API_KEY = os.getenv("BINANCE_API_KEY_TEST", "")
TESTNET_API_SECRET = os.getenv("BINANCE_API_SECRET_TEST", "")
TESTNET_FUTURES_URL = "https://testnet.binancefuture.com"

def test_connection():
    print("=" * 50)
    print("  BINANCE TESTNET API TEST")
    print("=" * 50)

    # 1. Check if keys are set
    if not TESTNET_API_KEY or not TESTNET_API_SECRET:
        print("\n[FEHLER] API Keys nicht in .env gefunden!")
        print("         Bitte TESTNET_API_KEY und TESTNET_API_SECRET setzen.")
        return False

    print(f"\n[OK] API Key gefunden: {TESTNET_API_KEY[:8]}...{TESTNET_API_KEY[-4:]}")
    print(f"[OK] API Secret gefunden: {TESTNET_API_SECRET[:4]}...{TESTNET_API_SECRET[-4:]}")

    # 2. Test public endpoint (no auth needed)
    print("\n[TEST] Öffentlicher Endpoint...")
    try:
        resp = requests.get(f"{TESTNET_FUTURES_URL}/fapi/v1/time", timeout=10)
        if resp.status_code == 200:
            server_time = resp.json()["serverTime"]
            print(f"[OK] Server erreichbar (Zeit: {server_time})")
        else:
            print(f"[FEHLER] Server antwortet mit Status {resp.status_code}")
            return False
    except Exception as e:
        print(f"[FEHLER] Keine Verbindung: {e}")
        return False

    # 3. Test authenticated endpoint (account balance)
    print("\n[TEST] Authentifizierter Endpoint (Account Balance)...")
    try:
        timestamp = int(time.time() * 1000)
        query = f"timestamp={timestamp}"
        signature = hmac.new(
            TESTNET_API_SECRET.encode(),
            query.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {"X-MBX-APIKEY": TESTNET_API_KEY}
        url = f"{TESTNET_FUTURES_URL}/fapi/v2/balance?{query}&signature={signature}"

        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            balances = resp.json()
            usdt_balance = next((b for b in balances if b["asset"] == "USDT"), None)
            if usdt_balance:
                print(f"[OK] API funktioniert!")
                print(f"[OK] USDT Balance: {float(usdt_balance['balance']):,.2f} USDT")
                print(f"[OK] Verfügbar: {float(usdt_balance['availableBalance']):,.2f} USDT")
            else:
                print("[OK] API funktioniert! (kein USDT Balance)")
            return True
        else:
            error = resp.json()
            print(f"[FEHLER] API Error: {error}")
            if error.get("code") == -2015:
                print("         -> API Key ist ungültig oder nicht aktiviert")
            elif error.get("code") == -1022:
                print("         -> Signatur ist ungültig (Secret Key falsch?)")
            return False

    except Exception as e:
        print(f"[FEHLER] {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    print("\n" + "=" * 50)
    if success:
        print("  ERGEBNIS: Alles OK! Du kannst jetzt traden.")
        print("  Starte mit: python run.py -> 't' für Testnet")
    else:
        print("  ERGEBNIS: Es gibt noch Probleme.")
        print("  Prüfe deine .env Datei und API Keys.")
    print("=" * 50 + "\n")
