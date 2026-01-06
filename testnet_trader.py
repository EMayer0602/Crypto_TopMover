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

    def _get_futures_symbols(self) -> set:
        """Holt alle verfügbaren Futures Symbole (nur aktiv handelbare)"""
        if hasattr(self, '_futures_symbols_cache'):
            return self._futures_symbols_cache

        url = f"{self.futures_url}/fapi/v1/exchangeInfo"
        result = self._request("GET", url)
        if result:
            # Nur Symbole mit Status "TRADING" sind handelbar
            self._futures_symbols_cache = {
                s["symbol"] for s in result.get("symbols", [])
                if s.get("status") == "TRADING"
            }
            return self._futures_symbols_cache
        return set()

    def _get_futures_precision(self, symbol: str) -> int:
        """Holt die Quantity Precision für ein Symbol"""
        url = f"{self.futures_url}/fapi/v1/exchangeInfo"
        result = self._request("GET", url)
        if result:
            for s in result.get("symbols", []):
                if s["symbol"] == symbol:
                    return s.get("quantityPrecision", 3)
        return 3  # Default

    def futures_short(self, symbol: str, usdt_amount: float) -> Optional[dict]:
        """Öffnet SHORT Position (Futures)"""
        # Erst Preis holen
        price = self._get_futures_price(symbol)
        if not price:
            print(f"❌ Konnte Preis für {symbol} nicht abrufen")
            return None

        # Precision für dieses Symbol holen
        precision = self._get_futures_precision(symbol)
        quantity = round(usdt_amount / price, precision)

        if quantity <= 0:
            print(f"❌ Quantity zu klein für {symbol}")
            return None

        url = f"{self.futures_url}/fapi/v1/order"
        params = {
            "symbol": symbol,
            "side": "SELL",  # SHORT = SELL to open
            "type": "MARKET",
            "quantity": quantity,
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

    def futures_long(self, symbol: str, usdt_amount: float) -> Optional[dict]:
        """Öffnet LONG Position (Futures) - Buy the Dip"""
        price = self._get_futures_price(symbol)
        if not price:
            print(f"❌ Konnte Preis für {symbol} nicht abrufen")
            return None

        precision = self._get_futures_precision(symbol)
        quantity = round(usdt_amount / price, precision)

        if quantity <= 0:
            print(f"❌ Quantity zu klein für {symbol}")
            return None

        url = f"{self.futures_url}/fapi/v1/order"
        params = {
            "symbol": symbol,
            "side": "BUY",  # LONG = BUY to open
            "type": "MARKET",
            "quantity": quantity,
        }

        result = self._request("POST", url, params, signed=True)
        if result:
            self.positions[f"{symbol}_LONG"] = TestnetPosition(
                symbol=symbol,
                side="LONG",
                entry_price=price,
                quantity=quantity,
                entry_time=datetime.now().isoformat(),
                order_id=str(result.get("orderId", ""))
            )
            self._save_state()

            print(f"✅ LONG: {quantity:.4f} {symbol.replace('USDT', '')} @ ${price:.4f}")
            return result

        return None

    def futures_close_long(self, symbol: str) -> Optional[dict]:
        """Schließt LONG Position"""
        key = f"{symbol}_LONG"
        if key not in self.positions:
            print(f"❌ Keine LONG Position in {symbol}")
            return None

        position = self.positions[key]

        url = f"{self.futures_url}/fapi/v1/order"
        params = {
            "symbol": symbol,
            "side": "SELL",  # LONG schließen = SELL
            "type": "MARKET",
            "quantity": position.quantity,
        }

        result = self._request("POST", url, params, signed=True)
        if result:
            exit_price = self._get_futures_price(symbol)
            # Bei LONG: Gewinn wenn Preis gestiegen
            pnl = (exit_price - position.entry_price) / position.entry_price * 100

            self.trade_history.append({
                "symbol": symbol,
                "side": "LONG",
                "entry_price": position.entry_price,
                "exit_price": exit_price,
                "quantity": position.quantity,
                "pnl_percent": pnl,
                "timestamp": datetime.now().isoformat()
            })

            del self.positions[key]
            self._save_state()

            emoji = "🟢" if pnl >= 0 else "🔴"
            print(f"{emoji} CLOSED LONG: {position.quantity:.4f} {symbol.replace('USDT', '')} "
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
        """Holt Top Losers von MAINNET (für Signale) - nur Futures-fähige"""
        futures_symbols = self._get_futures_symbols()
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

            # NUR Symbole die auf Futures Testnet verfügbar sind
            if symbol not in futures_symbols:
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
        """Holt Top Gainers von MAINNET (für Short Signale) - nur Futures-fähige"""
        futures_symbols = self._get_futures_symbols()
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

            # NUR Symbole die auf Futures Testnet verfügbar sind
            if symbol not in futures_symbols:
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
                current_price = self._get_futures_price(pos.symbol)
                if not current_price:
                    print(f"⚠️  Konnte Preis für {pos.symbol} nicht abrufen")
                    continue

                pnl = (current_price - pos.entry_price) / pos.entry_price * 100

                if pnl >= config.TAKE_PROFIT_PERCENT:
                    print(f"📈 TP erreicht für LONG {pos.symbol} ({pnl:+.2f}%)")
                    result = self.futures_close_long(pos.symbol)
                    if not result:
                        print(f"❌ FEHLER: Konnte LONG {pos.symbol} nicht schließen!")
                elif pnl <= -config.STOP_LOSS_PERCENT:
                    print(f"📉 SL erreicht für LONG {pos.symbol} ({pnl:+.2f}%)")
                    result = self.futures_close_long(pos.symbol)
                    if not result:
                        print(f"❌ FEHLER: Konnte LONG {pos.symbol} nicht schließen!")

            elif pos.side == "SHORT":
                current_price = self._get_futures_price(pos.symbol)
                if not current_price:
                    print(f"⚠️  Konnte Preis für {pos.symbol} nicht abrufen")
                    continue

                # Bei SHORT: Gewinn wenn Preis fällt
                pnl = (pos.entry_price - current_price) / pos.entry_price * 100

                if pnl >= config.SHORT_TAKE_PROFIT:
                    print(f"📈 TP erreicht für SHORT {pos.symbol} ({pnl:+.2f}%)")
                    result = self.futures_close_short(pos.symbol)
                    if not result:
                        print(f"❌ FEHLER: Konnte SHORT {pos.symbol} nicht schließen!")
                elif pnl <= -config.SHORT_STOP_LOSS:
                    print(f"📉 SL erreicht für SHORT {pos.symbol} ({pnl:+.2f}%)")
                    result = self.futures_close_short(pos.symbol)
                    if not result:
                        print(f"❌ FEHLER: Konnte SHORT {pos.symbol} nicht schließen!")

    def _get_spot_price(self, symbol: str) -> Optional[float]:
        """Holt Spot Preis"""
        url = f"https://api.binance.com/api/v3/ticker/price"
        response = self.session.get(url, params={"symbol": symbol})
        if response.status_code == 200:
            return float(response.json().get("price", 0))
        return None

    # === TREND CHECK ===

    def get_klines(self, symbol: str, interval: str = "1d", limit: int = 4) -> List[dict]:
        """Holt historische Klines von Mainnet"""
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        response = self.session.get(url, params=params)
        if response.status_code != 200:
            return []

        klines = response.json()
        return [{
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        } for k in klines]

    def check_trend_consistency(self, symbol: str) -> str:
        """
        Prüft die letzten 3 Tage auf Trend-Konsistenz.
        Returns: "UP", "DOWN", oder "CHOPPY"
        """
        klines = self.get_klines(symbol, "1d", config.TREND_CHECK_DAYS + 1)
        if len(klines) < config.TREND_CHECK_DAYS + 1:
            return "CHOPPY"  # Nicht genug Daten

        # Berechne tägliche Änderungen
        daily_changes = []
        max_pullback = 0.0

        for i in range(1, len(klines)):
            prev_close = klines[i-1]["close"]
            curr = klines[i]

            # Tägliche Änderung (Close zu Close)
            change = ((curr["close"] - prev_close) / prev_close) * 100
            daily_changes.append(change)

            # Intraday Pullback berechnen
            if change > 0:  # Aufwärtstag
                # Pullback = wie weit fiel der Preis vom High?
                pullback = ((curr["high"] - curr["low"]) / curr["high"]) * 100
            else:  # Abwärtstag
                # Pullback = wie weit stieg der Preis vom Low?
                pullback = ((curr["high"] - curr["low"]) / curr["low"]) * 100

            max_pullback = max(max_pullback, pullback)

        # Gesamtbewegung über die Periode
        total_move = sum(daily_changes)

        # Prüfe auf konsistenten Trend
        all_up = all(c > 0 for c in daily_changes)
        all_down = all(c < 0 for c in daily_changes)

        # Debug output
        print(f"  📊 {symbol}: Daily: {[f'{c:+.1f}%' for c in daily_changes]} | "
              f"Total: {total_move:+.1f}% | MaxPullback: {max_pullback:.1f}%")

        # Entscheidung
        if max_pullback > config.TREND_MAX_PULLBACK * 2:  # Zu volatile
            return "CHOPPY"

        if all_up and total_move >= config.TREND_MIN_MOVE:
            return "UP"
        elif all_down and abs(total_move) >= config.TREND_MIN_MOVE:
            return "DOWN"
        else:
            return "CHOPPY"

    def get_market_trend(self) -> dict:
        """
        Prüft BTC + ETH als kombinierte Markt-Indikatoren.
        Returns: {"direction": "BULLISH"|"BEARISH"|"NEUTRAL",
                  "btc_change": float, "eth_change": float, "avg_change": float}
        """
        url = "https://api.binance.com/api/v3/ticker/24hr"

        # BTC abrufen
        btc_response = self.session.get(url, params={"symbol": "BTCUSDT"})
        btc_change = 0.0
        if btc_response.status_code == 200:
            btc_change = float(btc_response.json().get("priceChangePercent", 0))

        # ETH abrufen
        eth_response = self.session.get(url, params={"symbol": "ETHUSDT"})
        eth_change = 0.0
        if eth_response.status_code == 200:
            eth_change = float(eth_response.json().get("priceChangePercent", 0))

        # Durchschnitt (BTC gewichtet stärker: 60/40)
        avg_change = (btc_change * 0.6) + (eth_change * 0.4)

        # Richtung bestimmen - beide müssen in dieselbe Richtung zeigen für klares Signal
        btc_bullish = btc_change >= config.BTC_TREND_THRESHOLD
        btc_bearish = btc_change <= -config.BTC_TREND_THRESHOLD
        eth_bullish = eth_change >= config.BTC_TREND_THRESHOLD
        eth_bearish = eth_change <= -config.BTC_TREND_THRESHOLD

        if btc_bearish and eth_bearish:
            direction = "BEARISH"
        elif btc_bullish and eth_bullish:
            direction = "BULLISH"
        elif btc_bearish or eth_bearish:
            # Einer fällt stark - vorsichtig sein mit Longs
            direction = "WEAK_BEARISH"
        elif btc_bullish or eth_bullish:
            # Einer steigt stark - vorsichtig sein mit Shorts
            direction = "WEAK_BULLISH"
        else:
            direction = "NEUTRAL"

        return {
            "direction": direction,
            "btc_change": btc_change,
            "eth_change": eth_change,
            "avg_change": avg_change
        }

    def is_trade_allowed_by_market(self, trade_side: str) -> tuple:
        """
        Prüft ob Trade-Richtung vom Markt erlaubt ist.
        trade_side: "LONG" oder "SHORT"
        Returns: (allowed: bool, reason: str)
        """
        if not config.USE_BTC_MARKET_FILTER:
            return (True, "Filter deaktiviert")

        market = self.get_market_trend()
        info = f"BTC {market['btc_change']:+.1f}% | ETH {market['eth_change']:+.1f}%"

        if market["direction"] == "BEARISH":
            if trade_side == "LONG":
                return (False, f"{info} - keine Longs bei Gewinnmitnahmen")
            else:
                return (True, f"{info} - Shorts erlaubt")

        elif market["direction"] == "WEAK_BEARISH":
            if trade_side == "LONG":
                return (False, f"{info} - Markt schwächelt, keine Longs")
            else:
                return (True, f"{info} - Shorts erlaubt")

        elif market["direction"] == "BULLISH":
            if trade_side == "SHORT":
                return (False, f"{info} - keine Shorts im Bullenmarkt")
            else:
                return (True, f"{info} - Longs erlaubt")

        elif market["direction"] == "WEAK_BULLISH":
            if trade_side == "SHORT":
                return (False, f"{info} - Markt bullish, keine Shorts")
            else:
                return (True, f"{info} - Longs erlaubt")

        else:  # NEUTRAL
            return (True, f"{info} - beide Richtungen erlaubt")

    def check_breakout(self, symbol: str) -> str:
        """
        Prüft ob aktueller Preis ein Breakout/Breakdown ist.
        Returns: "BREAKOUT_UP", "BREAKOUT_DOWN", oder "NONE"
        """
        klines = self.get_klines(symbol, "1d", config.BREAKOUT_LOOKBACK_DAYS + 1)
        if len(klines) < config.BREAKOUT_LOOKBACK_DAYS + 1:
            return "NONE"

        # Aktueller Preis (letzter Close)
        current_price = klines[-1]["close"]

        # High/Low der vorherigen Tage (ohne heute)
        previous_days = klines[:-1]
        highest_high = max(k["high"] for k in previous_days)
        lowest_low = min(k["low"] for k in previous_days)

        # Breakout-Schwellen
        breakout_up_level = highest_high * (1 + config.BREAKOUT_MIN_PERCENT / 100)
        breakout_down_level = lowest_low * (1 - config.BREAKOUT_MIN_PERCENT / 100)

        # Debug
        print(f"  🔍 {symbol}: Preis=${current_price:.4f} | "
              f"High={highest_high:.4f} (+{config.BREAKOUT_MIN_PERCENT}%={breakout_up_level:.4f}) | "
              f"Low={lowest_low:.4f} (-{config.BREAKOUT_MIN_PERCENT}%={breakout_down_level:.4f})")

        if current_price >= breakout_up_level:
            return "BREAKOUT_UP"
        elif current_price <= breakout_down_level:
            return "BREAKOUT_DOWN"
        else:
            return "NONE"

    def get_breakout_signals(self, limit: int = 10) -> List[dict]:
        """
        Sucht Coins die gerade einen Breakout machen.
        """
        futures_symbols = self._get_futures_symbols()
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = self.session.get(url)

        if response.status_code != 200:
            return []

        tickers = response.json()
        signals = []

        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            if symbol not in futures_symbols:
                continue

            volume = float(t.get("quoteVolume", 0))
            if volume < config.MIN_VOLUME_USDT:
                continue

            base = symbol.replace("USDT", "")
            if base in ["USDC", "BUSD", "DAI", "TUSD", "FDUSD"]:
                continue

            change_24h = float(t.get("priceChangePercent", 0))

            # Nur Coins mit Bewegung prüfen
            if abs(change_24h) >= 2.0:
                breakout = self.check_breakout(symbol)
                if breakout != "NONE":
                    signals.append({
                        "symbol": symbol,
                        "base": base,
                        "price": float(t.get("lastPrice", 0)),
                        "change_percent": change_24h,
                        "volume_usdt": volume,
                        "breakout": breakout,
                    })

        return sorted(signals, key=lambda x: abs(x["change_percent"]), reverse=True)[:limit]

    def get_trend_signals(self, limit: int = 10) -> List[dict]:
        """
        Holt Coins mit klarem Trend (für Trend-Following).
        """
        futures_symbols = self._get_futures_symbols()
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = self.session.get(url)

        if response.status_code != 200:
            return []

        tickers = response.json()
        signals = []

        for t in tickers:
            symbol = t.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue
            if symbol not in futures_symbols:
                continue

            volume = float(t.get("quoteVolume", 0))
            if volume < config.MIN_VOLUME_USDT:
                continue

            base = symbol.replace("USDT", "")
            if base in ["USDC", "BUSD", "DAI", "TUSD", "FDUSD"]:
                continue

            change_24h = float(t.get("priceChangePercent", 0))

            # Nur Coins mit signifikanter Bewegung prüfen
            if abs(change_24h) >= 3.0:
                trend = self.check_trend_consistency(symbol)
                if trend != "CHOPPY":
                    signals.append({
                        "symbol": symbol,
                        "base": base,
                        "price": float(t.get("lastPrice", 0)),
                        "change_percent": change_24h,
                        "volume_usdt": volume,
                        "trend": trend,
                    })

        # Sortiere nach Stärke der Bewegung
        return sorted(signals, key=lambda x: abs(x["change_percent"]), reverse=True)[:limit]

    def show_status(self):
        """Zeigt aktuellen Status"""
        print(f"\n{'='*60}")
        print("  TESTNET STATUS (Futures Only)")
        print(f"{'='*60}")

        futures_balance = self.get_futures_balance()

        print(f"  Futures Balance: ${futures_balance:,.2f} USDT")
        print(f"  Offene Positionen: {len(self.positions)}")

        if self.positions:
            print(f"\n  {'Symbol':<12} {'Side':<6} {'Entry':>10} {'Current':>10} {'PnL':>10}")
            print("  " + "-" * 52)

            for key, pos in self.positions.items():
                current = self._get_futures_price(pos.symbol) or pos.entry_price
                if pos.side == "LONG":
                    pnl = (current - pos.entry_price) / pos.entry_price * 100
                else:  # SHORT
                    pnl = (pos.entry_price - current) / pos.entry_price * 100

                emoji = "🟢" if pnl >= 0 else "🔴"
                print(f"  {pos.symbol.replace('USDT', ''):<12} {pos.side:<6} "
                      f"${pos.entry_price:>9.4f} ${current:>9.4f} {emoji} {pnl:>+7.2f}%")

        print(f"{'='*60}\n")


def run_testnet_auto_trading():
    """Startet automatisches Trading auf Testnet"""
    trader = BinanceTestnetTrader()

    print(f"\n{'='*70}")
    print("  🤖 TESTNET AUTO-TRADING (Futures LONG & SHORT)")
    print(f"{'='*70}")
    print(f"  Mode: {'TESTNET' if config.USE_TESTNET else '⚠️ LIVE!'}")
    print(f"  Position Size: ${config.MAX_POSITION_SIZE}")
    print(f"  Breakout-Detection: {'✅ AN' if config.USE_BREAKOUT_DETECTION else '❌ AUS'}")
    if config.USE_BREAKOUT_DETECTION:
        print(f"    Lookback: {config.BREAKOUT_LOOKBACK_DAYS} Tage | Min Breakout: {config.BREAKOUT_MIN_PERCENT}%")
    print(f"  Trend-Filter: {'✅ AN' if config.USE_TREND_FILTER else '❌ AUS'}")
    if config.USE_TREND_FILTER:
        print(f"    Trend-Check: {config.TREND_CHECK_DAYS} Tage | Max Pullback: {config.TREND_MAX_PULLBACK}%")
    print(f"  BTC/ETH Markt-Filter: {'✅ AN' if config.USE_BTC_MARKET_FILTER else '❌ AUS'}")
    if config.USE_BTC_MARKET_FILTER:
        print(f"    Threshold: +/-{config.BTC_TREND_THRESHOLD}%")
    print(f"  Mean Reversion:")
    print(f"    LONG:  Entry bei {config.BUY_LOSER_THRESHOLD}% | TP: +{config.TAKE_PROFIT_PERCENT}% | SL: -{config.STOP_LOSS_PERCENT}%")
    print(f"    SHORT: Entry bei +{config.SHORT_GAINER_THRESHOLD}% | TP: +{config.SHORT_TAKE_PROFIT}% | SL: -{config.SHORT_STOP_LOSS}%")
    print(f"  Scan Interval: {config.SCAN_INTERVAL_SECONDS}s")
    print(f"{'='*70}")
    print("  [Strg+C zum Beenden]\n")

    trader.show_status()

    try:
        while True:
            timestamp = time.strftime('%H:%M:%S')

            # 1. TP/SL prüfen
            trader.check_positions_tp_sl()

            # Zähle offene Positionen
            long_count = len([p for p in trader.positions.values() if p.side == "LONG"])
            short_count = len([p for p in trader.positions.values() if p.side == "SHORT"])

            # 2. Markt-Check (BTC + ETH)
            market = trader.get_market_trend()
            market_info = f"BTC {market['btc_change']:+.1f}% | ETH {market['eth_change']:+.1f}%"
            long_allowed, long_reason = trader.is_trade_allowed_by_market("LONG")
            short_allowed, short_reason = trader.is_trade_allowed_by_market("SHORT")

            print(f"\n[{timestamp}] 📊 Markt: {market_info} → {market['direction']}")
            if not long_allowed:
                print(f"  ⛔ Keine Longs: {long_reason}")
            if not short_allowed:
                print(f"  ⛔ Keine Shorts: {short_reason}")

            # 3. BREAKOUT DETECTION (wenn aktiviert)
            if config.USE_BREAKOUT_DETECTION and (long_count < 2 or short_count < 2):
                print(f"\n[{timestamp}] 🔍 Suche Breakout-Signale...")
                breakout_signals = trader.get_breakout_signals(5)

                for coin in breakout_signals:
                    if coin["breakout"] == "BREAKOUT_UP" and long_count < 2 and long_allowed:
                        key = f"{coin['symbol']}_LONG"
                        if key not in trader.positions:
                            print(f"\n[{timestamp}] 🚀 BREAKOUT LONG: {coin['base']} @ {coin['change_percent']:+.1f}% (über {config.BREAKOUT_LOOKBACK_DAYS}-Tage High)")
                            result = trader.futures_long(coin["symbol"], config.MAX_POSITION_SIZE)
                            if result:
                                long_count += 1
                                break

                    elif coin["breakout"] == "BREAKOUT_DOWN" and short_count < 2 and short_allowed:
                        key = f"{coin['symbol']}_SHORT"
                        if key not in trader.positions:
                            print(f"\n[{timestamp}] 💥 BREAKOUT SHORT: {coin['base']} @ {coin['change_percent']:+.1f}% (unter {config.BREAKOUT_LOOKBACK_DAYS}-Tage Low)")
                            result = trader.futures_short(coin["symbol"], config.MAX_POSITION_SIZE)
                            if result:
                                short_count += 1
                                break

            # 3b. TREND-FOLLOWING (Fallback wenn kein Breakout)
            elif config.USE_TREND_FILTER and (long_count < 2 or short_count < 2):
                print(f"\n[{timestamp}] 🔍 Suche Trend-Signale...")
                trend_signals = trader.get_trend_signals(5)

                for coin in trend_signals:
                    if coin["trend"] == "UP" and long_count < 2 and long_allowed:
                        key = f"{coin['symbol']}_LONG"
                        if key not in trader.positions:
                            print(f"\n[{timestamp}] 📈 TREND LONG: {coin['base']} @ {coin['change_percent']:+.1f}% (3-Tage UP)")
                            result = trader.futures_long(coin["symbol"], config.MAX_POSITION_SIZE)
                            if result:
                                long_count += 1
                                break

                    elif coin["trend"] == "DOWN" and short_count < 2 and short_allowed:
                        key = f"{coin['symbol']}_SHORT"
                        if key not in trader.positions:
                            print(f"\n[{timestamp}] 📉 TREND SHORT: {coin['base']} @ {coin['change_percent']:+.1f}% (3-Tage DOWN)")
                            result = trader.futures_short(coin["symbol"], config.MAX_POSITION_SIZE)
                            if result:
                                short_count += 1
                                break

            # 4. MEAN REVERSION (Fallback wenn keine Trend-Signale)
            # Nur wenn Trend-Filter aus ist ODER keine Trend-Signale gefunden wurden

            # LONG: Buy the Dip
            if long_count < 2 and long_allowed:
                losers = trader.get_top_losers(5)
                for coin in losers:
                    key = f"{coin['symbol']}_LONG"
                    if key not in trader.positions:
                        # Bei aktivem Trend-Filter: Prüfe ob NICHT im Downtrend
                        if config.USE_TREND_FILTER:
                            trend = trader.check_trend_consistency(coin["symbol"])
                            if trend == "DOWN":
                                print(f"  ⏭️  Skip {coin['base']} - im Downtrend (kein Mean Reversion)")
                                continue

                        print(f"\n[{timestamp}] 📉 MEAN REV LONG: {coin['base']} @ {coin['change_percent']:.1f}%")
                        result = trader.futures_long(coin["symbol"], config.MAX_POSITION_SIZE)
                        if result:
                            break

            # SHORT: Fade the Pump
            if short_count < 2 and short_allowed:
                gainers = trader.get_top_gainers(5)
                for coin in gainers:
                    key = f"{coin['symbol']}_SHORT"
                    if key not in trader.positions:
                        # Bei aktivem Trend-Filter: Prüfe ob NICHT im Uptrend
                        if config.USE_TREND_FILTER:
                            trend = trader.check_trend_consistency(coin["symbol"])
                            if trend == "UP":
                                print(f"  ⏭️  Skip {coin['base']} - im Uptrend (kein Mean Reversion)")
                                continue

                        print(f"\n[{timestamp}] 📈 MEAN REV SHORT: {coin['base']} @ +{coin['change_percent']:.1f}%")
                        result = trader.futures_short(coin["symbol"], config.MAX_POSITION_SIZE)
                        if result:
                            break

            # 4. Status
            futures_bal = trader.get_futures_balance()
            print(f"\n[{timestamp}] Positionen: {len(trader.positions)} | "
                  f"Futures: ${futures_bal:,.0f}")

            time.sleep(config.SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n\n⏹️  Auto-Trading beendet.")
        trader.show_status()


if __name__ == "__main__":
    run_testnet_auto_trading()
