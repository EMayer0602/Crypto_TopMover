"""
Binance Testnet Trader
======================
Echte API Calls auf dem Testnet (Spielgeld).
Unterstützt LONG (Spot) und SHORT (Futures).
"""

import hmac
import hashlib
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import json
import os
import config


@dataclass
class TestnetPosition:
    """Eine offene Position"""
    symbol: str
    side: str  # LONG oder SHORT
    entry_price: float
    quantity: float
    entry_time: str
    order_id: str


class BinanceTestnetTrader:
    """Trader für Binance Testnet"""

    def __init__(self):
        self.api_key, self.api_secret = config.get_api_credentials()
        self.spot_url = config.get_api_url(futures=False)
        self.futures_url = config.get_api_url(futures=True)
        self.session = requests.Session()
        self.positions: Dict[str, TestnetPosition] = {}
        self.trade_history = []
        self.state_file = "testnet_state.json"
        self._load_state()

        # Prüfe ob Keys vorhanden
        if not self.api_key or not self.api_secret:
            print("⚠️  WARNUNG: Keine Testnet API Keys in .env!")
            print("   Hole dir Keys von: https://testnet.binancefuture.com")

    def _sign(self, params: dict) -> str:
        """Erstellt HMAC SHA256 Signatur"""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, url: str, params: dict = None,
                 signed: bool = False) -> Optional[dict]:
        """Führt API Request durch"""
        if params is None:
            params = {}

        headers = {"X-MBX-APIKEY": self.api_key}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)

        try:
            if method == "GET":
                response = self.session.get(url, params=params, headers=headers)
            elif method == "POST":
                response = self.session.post(url, params=params, headers=headers)
            elif method == "DELETE":
                response = self.session.delete(url, params=params, headers=headers)
            else:
                return None

            if response.status_code == 200:
                return response.json()
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Request Error: {e}")
            return None

    def _load_state(self):
        """Lädt gespeicherten Zustand"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    self.positions = {
                        k: TestnetPosition(**v)
                        for k, v in state.get("positions", {}).items()
                    }
                    self.trade_history = state.get("trade_history", [])
            except Exception as e:
                print(f"Fehler beim Laden: {e}")

    def _save_state(self):
        """Speichert Zustand"""
        state = {
            "positions": {k: vars(v) for k, v in self.positions.items()},
            "trade_history": self.trade_history
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    # === SPOT TRADING (LONG) ===

    def get_spot_balance(self, asset: str = "USDT") -> float:
        """Holt Spot Balance"""
        url = f"{self.spot_url}/account"
        result = self._request("GET", url, signed=True)
        if result:
            for balance in result.get("balances", []):
                if balance["asset"] == asset:
                    return float(balance["free"])
        return 0.0

    def spot_buy(self, symbol: str, quote_amount: float) -> Optional[dict]:
        """Kauft auf Spot Markt (LONG)"""
        url = f"{self.spot_url}/order"
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "MARKET",
            "quoteOrderQty": quote_amount,  # Kaufe für X USDT
        }

        result = self._request("POST", url, params, signed=True)
        if result:
            # Position speichern
            qty = float(result.get("executedQty", 0))
            price = float(result.get("cummulativeQuoteQty", 0)) / qty if qty > 0 else 0

            self.positions[symbol] = TestnetPosition(
                symbol=symbol,
                side="LONG",
                entry_price=price,
                quantity=qty,
                entry_time=datetime.now().isoformat(),
                order_id=str(result.get("orderId", ""))
            )
            self._save_state()

            print(f"✅ LONG: {qty:.6f} {symbol.replace('USDT', '')} @ ${price:.4f}")
            return result

        return None

    def spot_sell(self, symbol: str) -> Optional[dict]:
        """Verkauft auf Spot Markt"""
        if symbol not in self.positions:
            print(f"❌ Keine Position in {symbol}")
            return None

        position = self.positions[symbol]
        url = f"{self.spot_url}/order"
        params = {
            "symbol": symbol,
            "side": "SELL",
            "type": "MARKET",
            "quantity": position.quantity,
        }

        result = self._request("POST", url, params, signed=True)
        if result:
            exit_price = float(result.get("cummulativeQuoteQty", 0)) / position.quantity
            pnl = (exit_price - position.entry_price) / position.entry_price * 100

            # Trade History
            self.trade_history.append({
                "symbol": symbol,
                "side": "LONG",
                "entry_price": position.entry_price,
                "exit_price": exit_price,
                "quantity": position.quantity,
                "pnl_percent": pnl,
                "timestamp": datetime.now().isoformat()
            })

            del self.positions[symbol]
            self._save_state()

            emoji = "🟢" if pnl >= 0 else "🔴"
            print(f"{emoji} SOLD: {position.quantity:.6f} {symbol.replace('USDT', '')} "
                  f"@ ${exit_price:.4f} | PnL: {pnl:+.2f}%")
            return result

        return None

    # === FUTURES TRADING (SHORT) ===

    def get_futures_balance(self) -> float:
        """Holt Futures USDT Balance"""
        url = f"{self.futures_url}/fapi/v2/balance"
        result = self._request("GET", url, signed=True)
        if result:
            for asset in result:
                if asset["asset"] == "USDT":
                    return float(asset["availableBalance"])
        return 0.0

    def futures_short(self, symbol: str, usdt_amount: float) -> Optional[dict]:
        """Öffnet SHORT Position (Futures)"""
        # Erst Preis holen
        price = self._get_futures_price(symbol)
        if not price:
            print(f"❌ Konnte Preis für {symbol} nicht abrufen")
            return None

        quantity = usdt_amount / price

        url = f"{self.futures_url}/fapi/v1/order"
        params = {
            "symbol": symbol,
            "side": "SELL",  # SHORT = SELL to open
            "type": "MARKET",
            "quantity": round(quantity, 3),
        }

        result = self._request("POST", url, params, signed=True)
        if result:
            self.positions[f"{symbol}_SHORT"] = TestnetPosition(
                symbol=symbol,
                side="SHORT",
                entry_price=price,
                quantity=round(quantity, 3),
                entry_time=datetime.now().isoformat(),
                order_id=str(result.get("orderId", ""))
            )
            self._save_state()

            print(f"✅ SHORT: {quantity:.4f} {symbol.replace('USDT', '')} @ ${price:.4f}")
            return result

        return None

    def futures_close_short(self, symbol: str) -> Optional[dict]:
        """Schließt SHORT Position"""
        key = f"{symbol}_SHORT"
        if key not in self.positions:
            print(f"❌ Keine SHORT Position in {symbol}")
            return None

        position = self.positions[key]

        url = f"{self.futures_url}/fapi/v1/order"
        params = {
            "symbol": symbol,
            "side": "BUY",  # SHORT schließen = BUY
            "type": "MARKET",
            "quantity": position.quantity,
        }

        result = self._request("POST", url, params, signed=True)
        if result:
            exit_price = self._get_futures_price(symbol)
            # Bei SHORT: Gewinn wenn Preis gefallen
            pnl = (position.entry_price - exit_price) / position.entry_price * 100

            self.trade_history.append({
                "symbol": symbol,
                "side": "SHORT",
                "entry_price": position.entry_price,
                "exit_price": exit_price,
                "quantity": position.quantity,
                "pnl_percent": pnl,
                "timestamp": datetime.now().isoformat()
            })

            del self.positions[key]
            self._save_state()

            emoji = "🟢" if pnl >= 0 else "🔴"
            print(f"{emoji} CLOSED SHORT: {position.quantity:.4f} {symbol.replace('USDT', '')} "
                  f"@ ${exit_price:.4f} | PnL: {pnl:+.2f}%")
            return result

        return None

    def _get_futures_price(self, symbol: str) -> Optional[float]:
        """Holt aktuellen Futures Preis"""
        url = f"{self.futures_url}/fapi/v1/ticker/price"
        result = self._request("GET", url, {"symbol": symbol})
        if result:
            return float(result.get("price", 0))
        return None

    # === LIVE DATEN VON MAINNET ===

    def get_top_losers(self, limit: int = 10) -> List[dict]:
        """Holt Top Losers von MAINNET (für Signale)"""
        # Immer Mainnet für Marktdaten
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = self.session.get(url)

        if response.status_code != 200:
            return []

        tickers = response.json()
        usdt_pairs = []

        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue

            volume = float(t.get("quoteVolume", 0))
            if volume < config.MIN_LOSER_VOLUME:
                continue

            base = symbol.replace("USDT", "")
            if base in ["USDC", "BUSD", "DAI", "TUSD", "FDUSD"]:
                continue

            change = float(t.get("priceChangePercent", 0))
            if change <= config.BUY_LOSER_THRESHOLD:
                usdt_pairs.append({
                    "symbol": symbol,
                    "base": base,
                    "price": float(t.get("lastPrice", 0)),
                    "change_percent": change,
                    "volume_usdt": volume,
                })

        return sorted(usdt_pairs, key=lambda x: x["change_percent"])[:limit]

    def get_top_gainers(self, limit: int = 10) -> List[dict]:
        """Holt Top Gainers von MAINNET (für Short Signale)"""
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = self.session.get(url)

        if response.status_code != 200:
            return []

        tickers = response.json()
        usdt_pairs = []

        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue

            volume = float(t.get("quoteVolume", 0))
            if volume < config.MIN_VOLUME_USDT:
                continue

            base = symbol.replace("USDT", "")
            if base in ["USDC", "BUSD", "DAI", "TUSD", "FDUSD"]:
                continue

            change = float(t.get("priceChangePercent", 0))
            if change >= config.SHORT_GAINER_THRESHOLD:
                usdt_pairs.append({
                    "symbol": symbol,
                    "base": base,
                    "price": float(t.get("lastPrice", 0)),
                    "change_percent": change,
                    "volume_usdt": volume,
                })

        return sorted(usdt_pairs, key=lambda x: x["change_percent"], reverse=True)[:limit]

    # === AUTO TRADING ===

    def check_positions_tp_sl(self):
        """Prüft Positionen auf TP/SL"""
        for key, pos in list(self.positions.items()):
            if pos.side == "LONG":
                current_price = self._get_spot_price(pos.symbol)
                if not current_price:
                    continue

                pnl = (current_price - pos.entry_price) / pos.entry_price * 100

                if pnl >= config.TAKE_PROFIT_PERCENT:
                    print(f"📈 TP erreicht für {pos.symbol}")
                    self.spot_sell(pos.symbol)
                elif pnl <= -config.STOP_LOSS_PERCENT:
                    print(f"📉 SL erreicht für {pos.symbol}")
                    self.spot_sell(pos.symbol)

            elif pos.side == "SHORT":
                current_price = self._get_futures_price(pos.symbol)
                if not current_price:
                    continue

                # Bei SHORT: Gewinn wenn Preis fällt
                pnl = (pos.entry_price - current_price) / pos.entry_price * 100

                if pnl >= config.SHORT_TAKE_PROFIT:
                    print(f"📈 TP erreicht für SHORT {pos.symbol}")
                    self.futures_close_short(pos.symbol)
                elif pnl <= -config.SHORT_STOP_LOSS:
                    print(f"📉 SL erreicht für SHORT {pos.symbol}")
                    self.futures_close_short(pos.symbol)

    def _get_spot_price(self, symbol: str) -> Optional[float]:
        """Holt Spot Preis"""
        url = f"https://api.binance.com/api/v3/ticker/price"
        response = self.session.get(url, params={"symbol": symbol})
        if response.status_code == 200:
            return float(response.json().get("price", 0))
        return None

    def show_status(self):
        """Zeigt aktuellen Status"""
        print(f"\n{'='*60}")
        print("  TESTNET STATUS")
        print(f"{'='*60}")

        spot_balance = self.get_spot_balance()
        futures_balance = self.get_futures_balance()

        print(f"  Spot Balance:    ${spot_balance:,.2f} USDT")
        print(f"  Futures Balance: ${futures_balance:,.2f} USDT")
        print(f"  Offene Positionen: {len(self.positions)}")

        if self.positions:
            print(f"\n  {'Symbol':<12} {'Side':<6} {'Entry':>10} {'Current':>10} {'PnL':>10}")
            print("  " + "-" * 52)

            for key, pos in self.positions.items():
                if pos.side == "LONG":
                    current = self._get_spot_price(pos.symbol) or pos.entry_price
                    pnl = (current - pos.entry_price) / pos.entry_price * 100
                else:
                    current = self._get_futures_price(pos.symbol) or pos.entry_price
                    pnl = (pos.entry_price - current) / pos.entry_price * 100

                emoji = "🟢" if pnl >= 0 else "🔴"
                print(f"  {pos.symbol.replace('USDT', ''):<12} {pos.side:<6} "
                      f"${pos.entry_price:>9.4f} ${current:>9.4f} {emoji} {pnl:>+7.2f}%")

        print(f"{'='*60}\n")


def run_testnet_auto_trading():
    """Startet automatisches Trading auf Testnet"""
    trader = BinanceTestnetTrader()

    print(f"\n{'='*70}")
    print("  🤖 TESTNET AUTO-TRADING")
    print(f"{'='*70}")
    print(f"  Mode: {'TESTNET' if config.USE_TESTNET else '⚠️ LIVE!'}")
    print(f"  LONG:  Buy bei {config.BUY_LOSER_THRESHOLD}% | TP: +{config.TAKE_PROFIT_PERCENT}%")
    print(f"  SHORT: Sell bei +{config.SHORT_GAINER_THRESHOLD}% | TP: +{config.SHORT_TAKE_PROFIT}%")
    print(f"  Scan Interval: {config.SCAN_INTERVAL_SECONDS}s")
    print(f"{'='*70}")
    print("  [Strg+C zum Beenden]\n")

    trader.show_status()

    try:
        while True:
            timestamp = time.strftime('%H:%M:%S')

            # 1. TP/SL prüfen
            trader.check_positions_tp_sl()

            # 2. Neue LONG Signale (Buy the Dip)
            if len([p for p in trader.positions.values() if p.side == "LONG"]) < 3:
                losers = trader.get_top_losers(3)
                for coin in losers:
                    if coin["symbol"] not in trader.positions:
                        print(f"\n[{timestamp}] 📉 LONG SIGNAL: {coin['base']} @ {coin['change_percent']:.1f}%")
                        trader.spot_buy(coin["symbol"], config.MAX_POSITION_SIZE)
                        break

            # 3. Neue SHORT Signale (Fade the Pump)
            if len([p for p in trader.positions.values() if p.side == "SHORT"]) < 2:
                gainers = trader.get_top_gainers(3)
                for coin in gainers:
                    key = f"{coin['symbol']}_SHORT"
                    if key not in trader.positions:
                        print(f"\n[{timestamp}] 📈 SHORT SIGNAL: {coin['base']} @ +{coin['change_percent']:.1f}%")
                        trader.futures_short(coin["symbol"], config.MAX_POSITION_SIZE)
                        break

            # 4. Status
            print(f"\n[{timestamp}] Positionen: {len(trader.positions)} | "
                  f"Spot: ${trader.get_spot_balance():,.0f} | "
                  f"Futures: ${trader.get_futures_balance():,.0f}")

            time.sleep(config.SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n\n⏹️  Auto-Trading beendet.")
        trader.show_status()


if __name__ == "__main__":
    run_testnet_auto_trading()
