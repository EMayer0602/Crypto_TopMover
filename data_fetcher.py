"""
Binance Top Gainer/Loser Scanner
================================
Scannt Binance nach den Top Gewinnern und Verlierern.
"""

import requests
import json
import os
from typing import List, Dict, Optional
from datetime import datetime
import config


class ScannerHistory:
    """Speichert Historie der Top Movers"""

    def __init__(self, history_file: str = "scanner_history.json"):
        self.history_file = history_file
        self.history = self._load_history()

    def _load_history(self) -> List[Dict]:
        """Lädt gespeicherte Historie"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_history(self):
        """Speichert Historie"""
        with open(self.history_file, "w") as f:
            json.dump(self.history, f, indent=2)

    def add_scan(self, movers: Dict[str, List[Dict]]):
        """Fügt einen Scan zur Historie hinzu"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "gainers": [{"symbol": c["symbol"], "base": c["base"],
                        "price": c["price"], "change_percent": c["change_percent"]}
                       for c in movers.get("gainers", [])[:5]],
            "losers": [{"symbol": c["symbol"], "base": c["base"],
                       "price": c["price"], "change_percent": c["change_percent"]}
                      for c in movers.get("losers", [])[:5]]
        }
        self.history.append(entry)
        # Behalte nur die letzten 100 Scans
        self.history = self.history[-100:]
        self._save_history()

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Gibt die letzten X Scans zurück"""
        return self.history[-limit:][::-1]  # Neueste zuerst

    def print_history(self, limit: int = 10):
        """Zeigt Historie formatiert an"""
        history = self.get_history(limit)

        if not history:
            print("\n📭 Keine Historie vorhanden.\n")
            return

        print(f"\n{'='*70}")
        print(f"  SCANNER HISTORIE (letzte {len(history)} Scans)")
        print(f"{'='*70}")

        for entry in history:
            ts = datetime.fromisoformat(entry["timestamp"]).strftime("%d.%m.%Y %H:%M")
            print(f"\n📅 {ts}")
            print("-" * 40)

            # Top 3 Gainer
            gainers = entry.get("gainers", [])[:3]
            if gainers:
                gainer_str = " | ".join([f"{g['base']} {g['change_percent']:+.1f}%" for g in gainers])
                print(f"  🚀 {gainer_str}")

            # Top 3 Loser
            losers = entry.get("losers", [])[:3]
            if losers:
                loser_str = " | ".join([f"{l['base']} {l['change_percent']:+.1f}%" for l in losers])
                print(f"  📉 {loser_str}")

        print(f"\n{'='*70}\n")


class BinanceScanner:
    """Scanner für Binance Top Movers"""

    BASE_URL = "https://api.binance.com/api/v3"

    def __init__(self):
        self.session = requests.Session()

    def get_all_tickers(self) -> List[Dict]:
        """Holt alle 24h Ticker Daten von Binance"""
        url = f"{self.BASE_URL}/ticker/24hr"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_usdt_pairs(self, tickers: List[Dict]) -> List[Dict]:
        """Filtert nur USDT Paare mit ausreichend Volumen"""
        usdt_pairs = []
        for ticker in tickers:
            symbol = ticker.get("symbol", "")
            if not symbol.endswith(config.QUOTE_CURRENCY):
                continue

            # Volumen Filter
            quote_volume = float(ticker.get("quoteVolume", 0))
            if quote_volume < config.MIN_VOLUME_USDT:
                continue

            # Stablecoins ausschließen
            base = symbol.replace(config.QUOTE_CURRENCY, "")
            if base in ["USDC", "BUSD", "DAI", "TUSD", "USDP", "FDUSD"]:
                continue

            usdt_pairs.append({
                "symbol": symbol,
                "base": base,
                "price": float(ticker.get("lastPrice", 0)),
                "change_percent": float(ticker.get("priceChangePercent", 0)),
                "volume_usdt": quote_volume,
                "high_24h": float(ticker.get("highPrice", 0)),
                "low_24h": float(ticker.get("lowPrice", 0)),
            })

        return usdt_pairs

    def get_top_gainers(self, limit: int = None) -> List[Dict]:
        """Holt die Top Gainer (mind. MIN_GAINER_PERCENT Veränderung)"""
        if limit is None:
            limit = config.TOP_N_MOVERS

        tickers = self.get_all_tickers()
        usdt_pairs = self.get_usdt_pairs(tickers)

        # Nur Coins mit mind. X% Gewinn (default: 10%)
        gainers = [p for p in usdt_pairs if p["change_percent"] >= config.MIN_GAINER_PERCENT]

        # Nach Gewinn sortieren (absteigend)
        sorted_pairs = sorted(gainers, key=lambda x: x["change_percent"], reverse=True)
        return sorted_pairs[:limit]

    def get_top_losers(self, limit: int = None) -> List[Dict]:
        """Holt die Top Loser (höchste negative Veränderung)"""
        if limit is None:
            limit = config.TOP_N_MOVERS

        tickers = self.get_all_tickers()
        usdt_pairs = self.get_usdt_pairs(tickers)

        # Nach Verlust sortieren (aufsteigend)
        sorted_pairs = sorted(usdt_pairs, key=lambda x: x["change_percent"])
        return sorted_pairs[:limit]

    def get_top_movers(self, limit: int = None) -> Dict[str, List[Dict]]:
        """Holt sowohl Top Gainer als auch Top Loser"""
        if limit is None:
            limit = config.TOP_N_MOVERS

        tickers = self.get_all_tickers()
        usdt_pairs = self.get_usdt_pairs(tickers)

        # Nur Gainer mit mind. X% (default: 10%)
        gainers = [p for p in usdt_pairs if p["change_percent"] >= config.MIN_GAINER_PERCENT]
        gainers_sorted = sorted(gainers, key=lambda x: x["change_percent"], reverse=True)

        # Loser (alle negativen)
        losers = [p for p in usdt_pairs if p["change_percent"] < 0]
        losers_sorted = sorted(losers, key=lambda x: x["change_percent"])

        return {
            "gainers": gainers_sorted[:limit],
            "losers": losers_sorted[:limit]
        }

    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Holt aktuellen Preis für ein Symbol"""
        url = f"{self.BASE_URL}/ticker/price"
        response = self.session.get(url, params={"symbol": symbol})
        if response.status_code == 200:
            return float(response.json().get("price", 0))
        return None


def print_top_movers(movers: Dict[str, List[Dict]]):
    """Zeigt Top Movers formatiert an"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*60}")
    print(f"  CRYPTO TOP MOVERS - {timestamp}")
    print(f"{'='*60}")

    print(f"\n{'🚀 TOP GAINERS':^60}")
    print("-" * 60)
    print(f"{'#':<3} {'Symbol':<12} {'Preis':>12} {'24h %':>10} {'Vol (USDT)':>18}")
    print("-" * 60)

    for i, coin in enumerate(movers["gainers"], 1):
        print(f"{i:<3} {coin['base']:<12} ${coin['price']:>11.4f} "
              f"{coin['change_percent']:>+9.2f}% {coin['volume_usdt']:>17,.0f}")

    print(f"\n{'📉 TOP LOSERS':^60}")
    print("-" * 60)
    print(f"{'#':<3} {'Symbol':<12} {'Preis':>12} {'24h %':>10} {'Vol (USDT)':>18}")
    print("-" * 60)

    for i, coin in enumerate(movers["losers"], 1):
        print(f"{i:<3} {coin['base']:<12} ${coin['price']:>11.4f} "
              f"{coin['change_percent']:>+9.2f}% {coin['volume_usdt']:>17,.0f}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    # Test
    scanner = BinanceScanner()
    movers = scanner.get_top_movers()
    print_top_movers(movers)
