"""
Binance Top Gainer/Loser Scanner
================================
Scannt Binance nach den Top Gewinnern und Verlierern.
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime
import config


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
        """Holt die Top Gainer (höchste positive Veränderung)"""
        if limit is None:
            limit = config.TOP_N_MOVERS

        tickers = self.get_all_tickers()
        usdt_pairs = self.get_usdt_pairs(tickers)

        # Nach Gewinn sortieren (absteigend)
        sorted_pairs = sorted(usdt_pairs, key=lambda x: x["change_percent"], reverse=True)
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

        # Sortieren
        sorted_by_change = sorted(usdt_pairs, key=lambda x: x["change_percent"], reverse=True)

        return {
            "gainers": sorted_by_change[:limit],
            "losers": sorted_by_change[-limit:][::-1]  # Umkehren für größten Verlust zuerst
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
