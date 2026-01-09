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
from typing import Dict, List, Optional, Tuple
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
    peak_price: float = 0.0  # Höchstpreis (LONG) / Tiefstpreis (SHORT) für Trailing Stop
    partial_closed: bool = False  # Partial TP bereits genommen


@dataclass
class BlockedTrade:
    """Ein durch Filter geblockter Trade zur Nachverfolgung"""
    symbol: str
    side: str
    filter_name: str
    block_price: float
    block_time: str
    checked: bool = False
    outcome_price: float = 0.0
    would_be_winner: bool = False


class FilterStats:
    """Trackt Filter-Performance"""

    def __init__(self, stats_file: str = "filter_stats.json"):
        self.stats_file = stats_file
        self.blocked_trades: List[BlockedTrade] = []
        self.filter_counts = {
            "volume": {"blocked": 0, "would_win": 0, "would_lose": 0},
            "funding": {"blocked": 0, "would_win": 0, "would_lose": 0},
            "rsi": {"blocked": 0, "would_win": 0, "would_lose": 0},
            "trend": {"blocked": 0, "would_win": 0, "would_lose": 0},
            "supertrend_entry": {"blocked": 0, "would_win": 0, "would_lose": 0},
        }
        self.passed_trades = {"total": 0, "wins": 0, "losses": 0}
        self._load_stats()

    def _load_stats(self):
        """Lädt gespeicherte Statistiken"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    data = json.load(f)
                    self.filter_counts = data.get("filter_counts", self.filter_counts)
                    self.passed_trades = data.get("passed_trades", self.passed_trades)
                    self.blocked_trades = [
                        BlockedTrade(**bt) for bt in data.get("blocked_trades", [])
                    ]
            except Exception as e:
                print(f"⚠️  Konnte Filter-Stats nicht laden: {e}")

    def _save_stats(self):
        """Speichert Statistiken"""
        try:
            with open(self.stats_file, "w") as f:
                json.dump({
                    "filter_counts": self.filter_counts,
                    "passed_trades": self.passed_trades,
                    "blocked_trades": [
                        {
                            "symbol": bt.symbol,
                            "side": bt.side,
                            "filter_name": bt.filter_name,
                            "block_price": bt.block_price,
                            "block_time": bt.block_time,
                            "checked": bt.checked,
                            "outcome_price": bt.outcome_price,
                            "would_be_winner": bt.would_be_winner,
                        }
                        for bt in self.blocked_trades[-100:]  # Nur letzte 100 behalten
                    ]
                }, f, indent=2)
        except Exception as e:
            print(f"⚠️  Konnte Filter-Stats nicht speichern: {e}")

    def record_blocked(self, symbol: str, side: str, filter_name: str, price: float):
        """Zeichnet geblockten Trade auf"""
        self.blocked_trades.append(BlockedTrade(
            symbol=symbol,
            side=side,
            filter_name=filter_name,
            block_price=price,
            block_time=datetime.now().isoformat()
        ))
        if filter_name in self.filter_counts:
            self.filter_counts[filter_name]["blocked"] += 1
        self._save_stats()

    def record_trade_result(self, is_winner: bool):
        """Zeichnet Ergebnis eines durchgelassenen Trades auf"""
        self.passed_trades["total"] += 1
        if is_winner:
            self.passed_trades["wins"] += 1
        else:
            self.passed_trades["losses"] += 1
        self._save_stats()

    def check_blocked_outcomes(self, get_price_func, tp_percent: float = 4.0, sl_percent: float = 2.0):
        """Prüft Outcome der geblockten Trades"""
        for bt in self.blocked_trades:
            if bt.checked:
                continue

            # Nur Trades prüfen die älter als 4 Stunden sind
            block_time = datetime.fromisoformat(bt.block_time)
            hours_passed = (datetime.now() - block_time).total_seconds() / 3600
            if hours_passed < 4:
                continue

            current_price = get_price_func(bt.symbol)
            if not current_price:
                continue

            bt.outcome_price = current_price
            bt.checked = True

            # Berechne ob es ein Gewinner gewesen wäre
            if bt.side == "LONG":
                pnl = (current_price - bt.block_price) / bt.block_price * 100
            else:  # SHORT
                pnl = (bt.block_price - current_price) / bt.block_price * 100

            # Vereinfachte Logik: Gewinner wenn > 2%, Verlierer wenn < -1%
            bt.would_be_winner = pnl >= 2.0

            if bt.filter_name in self.filter_counts:
                if bt.would_be_winner:
                    self.filter_counts[bt.filter_name]["would_win"] += 1
                elif pnl <= -1.0:
                    self.filter_counts[bt.filter_name]["would_lose"] += 1

        self._save_stats()

    def get_summary(self) -> str:
        """Gibt Statistik-Zusammenfassung zurück"""
        lines = [
            "",
            "📊 FILTER STATISTIKEN",
            "━" * 50,
        ]

        for filter_name, counts in self.filter_counts.items():
            blocked = counts["blocked"]
            if blocked == 0:
                continue

            would_win = counts["would_win"]
            would_lose = counts["would_lose"]
            checked = would_win + would_lose

            if checked > 0:
                win_rate = would_win / checked * 100
                verdict = "⚠️ blockt Gewinner!" if win_rate > 40 else "✓ spart Verluste"
            else:
                win_rate = 0
                verdict = "⏳ noch keine Daten"

            filter_display = filter_name.replace("_", " ").title()
            lines.append(
                f"  {filter_display:20} │ {blocked:3} geblockt │ "
                f"{would_win}/{checked} wären Gewinner ({win_rate:.0f}%) {verdict}"
            )

        lines.append("━" * 50)

        total = self.passed_trades["total"]
        wins = self.passed_trades["wins"]
        if total > 0:
            win_rate = wins / total * 100
            lines.append(f"  Durchgelassene Trades: {total} │ Win Rate: {win_rate:.1f}%")
        else:
            lines.append("  Noch keine abgeschlossenen Trades")

        lines.append("")
        return "\n".join(lines)

    def reset(self):
        """Setzt alle Statistiken zurück"""
        self.blocked_trades = []
        self.filter_counts = {
            "volume": {"blocked": 0, "would_win": 0, "would_lose": 0},
            "funding": {"blocked": 0, "would_win": 0, "would_lose": 0},
            "rsi": {"blocked": 0, "would_win": 0, "would_lose": 0},
            "trend": {"blocked": 0, "would_win": 0, "would_lose": 0},
            "supertrend_entry": {"blocked": 0, "would_win": 0, "would_lose": 0},
        }
        self.passed_trades = {"total": 0, "wins": 0, "losses": 0}
        self._save_stats()
        print("🔄 Filter-Statistiken zurückgesetzt")


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
        self.filter_stats = FilterStats()  # Filter-Statistiken
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

    def futures_partial_close(self, symbol: str, side: str, close_ratio: float = 0.5) -> Optional[dict]:
        """Schließt einen Teil der Position (Partial Take Profit)"""
        key = f"{symbol}_{side}"
        if key not in self.positions:
            print(f"❌ Keine {side} Position in {symbol}")
            return None

        position = self.positions[key]

        # Berechne Partial Quantity
        precision = self._get_futures_precision(symbol)
        partial_qty = round(position.quantity * close_ratio, precision)

        if partial_qty <= 0:
            print(f"⚠️  Partial Quantity zu klein für {symbol}")
            return None

        url = f"{self.futures_url}/fapi/v1/order"

        # LONG schließen = SELL, SHORT schließen = BUY
        close_side = "SELL" if side == "LONG" else "BUY"

        params = {
            "symbol": symbol,
            "side": close_side,
            "type": "MARKET",
            "quantity": partial_qty,
        }

        result = self._request("POST", url, params, signed=True)
        if result:
            exit_price = self._get_futures_price(symbol)

            # PnL berechnen
            if side == "LONG":
                pnl = (exit_price - position.entry_price) / position.entry_price * 100
            else:  # SHORT
                pnl = (position.entry_price - exit_price) / position.entry_price * 100

            # Position aktualisieren (reduzierte Quantity)
            position.quantity = round(position.quantity - partial_qty, precision)
            position.partial_closed = True
            self._save_state()

            print(f"🎯 PARTIAL TP ({close_ratio*100:.0f}%): {partial_qty:.4f} {symbol.replace('USDT', '')} "
                  f"@ ${exit_price:.4f} | PnL: {pnl:+.2f}%")
            print(f"   Verbleibend: {position.quantity:.4f} {symbol.replace('USDT', '')}")

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

    def close_all_positions(self) -> dict:
        """Schließt ALLE offenen Positionen sofort"""
        print(f"\n{'='*60}")
        print("  ⚠️  CLOSE ALL POSITIONS")
        print(f"{'='*60}")

        if not self.positions:
            print("  Keine offenen Positionen vorhanden.")
            return {"closed": 0, "failed": 0}

        closed = 0
        failed = 0
        total_pnl = 0.0

        # Kopie der Keys, da wir während Iteration löschen
        position_keys = list(self.positions.keys())

        for key in position_keys:
            pos = self.positions.get(key)
            if not pos:
                continue

            print(f"\n  Schließe {pos.side} {pos.symbol}...")

            if pos.side == "LONG":
                result = self.futures_close_long(pos.symbol)
            else:  # SHORT
                result = self.futures_close_short(pos.symbol)

            if result:
                closed += 1
                # PnL aus letztem Trade holen
                if self.trade_history:
                    total_pnl += self.trade_history[-1]["pnl_percent"]
            else:
                failed += 1

        print(f"\n{'='*60}")
        print(f"  ✅ Geschlossen: {closed} | ❌ Fehlgeschlagen: {failed}")
        print(f"  📊 Gesamt PnL: {total_pnl:+.2f}%")
        print(f"{'='*60}\n")

        # Dashboard aktualisieren
        self.export_dashboard_data()

        return {"closed": closed, "failed": failed, "total_pnl": total_pnl}

    def check_close_all_signal(self) -> bool:
        """Prüft ob Close-All Signal existiert und führt es aus"""
        signal_file = "close_all.signal"
        if os.path.exists(signal_file):
            print("\n🚨 CLOSE ALL SIGNAL EMPFANGEN!")
            self.close_all_positions()
            # Signal-Datei löschen
            try:
                os.remove(signal_file)
            except:
                pass
            return True
        return False

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
        """Prüft Positionen auf TP/SL mit Trailing Stop"""
        for key, pos in list(self.positions.items()):
            if pos.side == "LONG":
                current_price = self._get_futures_price(pos.symbol)
                if not current_price:
                    print(f"⚠️  Konnte Preis für {pos.symbol} nicht abrufen")
                    continue

                pnl = (current_price - pos.entry_price) / pos.entry_price * 100

                # Trailing Stop Logik für LONG
                if config.USE_TRAILING_STOP and pnl >= config.TRAILING_STOP_ACTIVATION:
                    # Peak-Preis aktualisieren
                    if pos.peak_price == 0.0 or current_price > pos.peak_price:
                        pos.peak_price = current_price
                        self._save_state()

                    # Trailing Stop Level berechnen
                    trailing_stop_level = pos.peak_price * (1 - config.TRAILING_STOP_DISTANCE / 100)

                    if current_price <= trailing_stop_level:
                        pnl_at_close = (current_price - pos.entry_price) / pos.entry_price * 100
                        print(f"🔔 TRAILING STOP für LONG {pos.symbol} ({pnl_at_close:+.2f}%)")
                        print(f"   Peak: ${pos.peak_price:.4f} → Stop: ${trailing_stop_level:.4f} → Aktuell: ${current_price:.4f}")
                        result = self.futures_close_long(pos.symbol)
                        if result:
                            self.filter_stats.record_trade_result(pnl_at_close > 0)
                        else:
                            print(f"❌ FEHLER: Konnte LONG {pos.symbol} nicht schließen!")
                        continue

                # Partial Take Profit für LONG
                if config.USE_PARTIAL_TP and not pos.partial_closed:
                    if pnl >= config.PARTIAL_TP_PERCENT:
                        print(f"🎯 PARTIAL TP erreicht für LONG {pos.symbol} ({pnl:+.2f}%)")
                        result = self.futures_partial_close(
                            pos.symbol, "LONG", config.PARTIAL_TP_CLOSE_RATIO
                        )
                        if not result:
                            print(f"⚠️  Partial TP fehlgeschlagen für LONG {pos.symbol}")
                        continue  # Zum nächsten Position, nicht sofort Full TP prüfen

                # Normaler TP/SL
                if pnl >= config.TAKE_PROFIT_PERCENT:
                    print(f"📈 TP erreicht für LONG {pos.symbol} ({pnl:+.2f}%)")
                    result = self.futures_close_long(pos.symbol)
                    if result:
                        self.filter_stats.record_trade_result(True)  # TP = Winner
                    else:
                        print(f"❌ FEHLER: Konnte LONG {pos.symbol} nicht schließen!")
                elif pnl <= -config.STOP_LOSS_PERCENT:
                    print(f"📉 SL erreicht für LONG {pos.symbol} ({pnl:+.2f}%)")
                    result = self.futures_close_long(pos.symbol)
                    if result:
                        self.filter_stats.record_trade_result(False)  # SL = Loser
                    else:
                        print(f"❌ FEHLER: Konnte LONG {pos.symbol} nicht schließen!")

            elif pos.side == "SHORT":
                current_price = self._get_futures_price(pos.symbol)
                if not current_price:
                    print(f"⚠️  Konnte Preis für {pos.symbol} nicht abrufen")
                    continue

                # Bei SHORT: Gewinn wenn Preis fällt
                pnl = (pos.entry_price - current_price) / pos.entry_price * 100

                # Trailing Stop Logik für SHORT
                if config.USE_TRAILING_STOP and pnl >= config.TRAILING_STOP_ACTIVATION:
                    # Peak-Preis aktualisieren (für SHORT: niedrigster Preis)
                    if pos.peak_price == 0.0 or current_price < pos.peak_price:
                        pos.peak_price = current_price
                        self._save_state()

                    # Trailing Stop Level berechnen (für SHORT: Preis darf nicht zu stark steigen)
                    trailing_stop_level = pos.peak_price * (1 + config.TRAILING_STOP_DISTANCE / 100)

                    if current_price >= trailing_stop_level:
                        pnl_at_close = (pos.entry_price - current_price) / pos.entry_price * 100
                        print(f"🔔 TRAILING STOP für SHORT {pos.symbol} ({pnl_at_close:+.2f}%)")
                        print(f"   Low: ${pos.peak_price:.4f} → Stop: ${trailing_stop_level:.4f} → Aktuell: ${current_price:.4f}")
                        result = self.futures_close_short(pos.symbol)
                        if result:
                            self.filter_stats.record_trade_result(pnl_at_close > 0)
                        else:
                            print(f"❌ FEHLER: Konnte SHORT {pos.symbol} nicht schließen!")
                        continue

                # Partial Take Profit für SHORT
                if config.USE_PARTIAL_TP and not pos.partial_closed:
                    if pnl >= config.PARTIAL_TP_PERCENT:
                        print(f"🎯 PARTIAL TP erreicht für SHORT {pos.symbol} ({pnl:+.2f}%)")
                        result = self.futures_partial_close(
                            pos.symbol, "SHORT", config.PARTIAL_TP_CLOSE_RATIO
                        )
                        if not result:
                            print(f"⚠️  Partial TP fehlgeschlagen für SHORT {pos.symbol}")
                        continue  # Zum nächsten Position, nicht sofort Full TP prüfen

                # Normaler TP/SL
                if pnl >= config.SHORT_TAKE_PROFIT:
                    print(f"📈 TP erreicht für SHORT {pos.symbol} ({pnl:+.2f}%)")
                    result = self.futures_close_short(pos.symbol)
                    if result:
                        self.filter_stats.record_trade_result(True)  # TP = Winner
                    else:
                        print(f"❌ FEHLER: Konnte SHORT {pos.symbol} nicht schließen!")
                elif pnl <= -config.SHORT_STOP_LOSS:
                    print(f"📉 SL erreicht für SHORT {pos.symbol} ({pnl:+.2f}%)")
                    result = self.futures_close_short(pos.symbol)
                    if result:
                        self.filter_stats.record_trade_result(False)  # SL = Loser
                    else:
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

    def calculate_rsi(self, symbol: str, period: int = 14) -> float:
        """
        Berechnet RSI (Relative Strength Index) für ein Symbol.
        Returns: RSI Wert (0-100) oder 50 bei Fehler
        """
        # Hole genug Klines für RSI Berechnung
        klines = self.get_klines(symbol, "1h", period + 10)
        if len(klines) < period + 1:
            return 50.0  # Neutral wenn nicht genug Daten

        closes = [k["close"] for k in klines]

        # Berechne Gains und Losses
        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))

        # Berechne Average Gain und Loss
        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def check_rsi_entry(self, symbol: str, side: str) -> Tuple[bool, str]:
        """
        Prüft ob RSI einen Entry erlaubt.
        Returns: (erlaubt, grund)
        """
        if not config.USE_RSI_FILTER:
            return (True, "RSI Filter deaktiviert")

        rsi = self.calculate_rsi(symbol, config.RSI_PERIOD)

        if side == "LONG":
            if rsi <= config.RSI_OVERSOLD:
                return (True, f"RSI {rsi:.1f} ≤ {config.RSI_OVERSOLD} (überverkauft) ✓")
            else:
                return (False, f"RSI {rsi:.1f} > {config.RSI_OVERSOLD} (nicht überverkauft)")

        elif side == "SHORT":
            if rsi >= config.RSI_OVERBOUGHT:
                return (True, f"RSI {rsi:.1f} ≥ {config.RSI_OVERBOUGHT} (überkauft) ✓")
            else:
                return (False, f"RSI {rsi:.1f} < {config.RSI_OVERBOUGHT} (nicht überkauft)")

        return (True, "RSI OK")

    def check_supertrend_entry(self, symbol: str, side: str) -> Tuple[bool, str]:
        """
        Prüft ob Supertrend einen Entry erlaubt (verhindert Chasing nach Pump).
        DYNAMISCH: Verwendet ATR statt fester Prozente - passt sich an Volatilität an.
        Returns: (erlaubt, grund)
        """
        if not config.USE_SUPERTREND_ENTRY_FILTER:
            return (True, "Supertrend Entry Filter deaktiviert")

        # Hole 5min Klines für Entry-Check
        limit = config.ENTRY_SUPERTREND_PERIOD * 3 + 10
        klines = self.get_klines(symbol, config.ENTRY_SUPERTREND_TIMEFRAME, limit)

        if len(klines) < config.ENTRY_SUPERTREND_PERIOD + 2:
            return (True, "Nicht genug Daten für Supertrend")

        # Berechne ATR für dynamische Schwelle
        atr_values = self.calculate_atr(klines, config.ENTRY_SUPERTREND_PERIOD)
        if not atr_values or atr_values[-1] is None:
            return (True, "ATR nicht verfügbar")

        current_atr = atr_values[-1]
        current_price = klines[-1]["close"]

        # Berechne Supertrend
        st = self.calculate_supertrend(
            klines,
            config.ENTRY_SUPERTREND_PERIOD,
            config.ENTRY_SUPERTREND_MULTIPLIER
        )

        if st["direction"] == "NEUTRAL" or st["value"] == 0:
            return (True, "Supertrend nicht verfügbar")

        st_value = st["value"]

        # Berechne Abstand zum Supertrend in ATR-Einheiten (dynamisch!)
        distance_price = current_price - st_value
        distance_atr = distance_price / current_atr if current_atr > 0 else 0

        # Max erlaubter Abstand in ATR (config)
        max_atr_distance = config.ENTRY_MAX_ATR_DISTANCE

        if side == "LONG":
            # Für LONG: Preis sollte NAH AM oder UNTER Supertrend sein
            if distance_atr > max_atr_distance:
                return (False, f"Preis {distance_atr:.1f}x ATR über ST → Pump! (max {max_atr_distance}x)")
            elif distance_atr < 0:
                return (True, f"Preis {abs(distance_atr):.1f}x ATR unter ST → Pullback ✓")
            else:
                return (True, f"Preis {distance_atr:.1f}x ATR über ST → OK ✓")

        elif side == "SHORT":
            # Für SHORT: Preis sollte NAH AM oder ÜBER Supertrend sein
            if distance_atr < -max_atr_distance:
                return (False, f"Preis {abs(distance_atr):.1f}x ATR unter ST → Dump! (max {max_atr_distance}x)")
            elif distance_atr > 0:
                return (True, f"Preis {distance_atr:.1f}x ATR über ST → Extended ✓")
            else:
                return (True, f"Preis {abs(distance_atr):.1f}x ATR unter ST → OK ✓")

        return (True, "Supertrend OK")

    def check_volume_filter(self, symbol: str) -> Tuple[bool, str]:
        """
        Prüft ob das aktuelle Volume überdurchschnittlich ist.
        Bestätigt echte Bewegungen vs. Fake-Moves mit wenig Volumen.
        """
        if not config.USE_VOLUME_FILTER:
            return (True, "Volume Filter deaktiviert")

        klines = self.get_klines(symbol, "1h", config.VOLUME_LOOKBACK + 1)
        if len(klines) < config.VOLUME_LOOKBACK + 1:
            return (True, "Nicht genug Daten für Volume")

        # Durchschnitts-Volume berechnen (ohne letzte Kerze)
        volumes = [k["volume"] for k in klines[:-1]]
        avg_volume = sum(volumes) / len(volumes)

        # Aktuelles Volume
        current_volume = klines[-1]["volume"]

        if avg_volume == 0:
            return (True, "Volume nicht verfügbar")

        volume_ratio = current_volume / avg_volume

        if volume_ratio >= config.VOLUME_MIN_RATIO:
            return (True, f"Volume {volume_ratio:.1f}x Avg ✓")
        else:
            return (False, f"Volume {volume_ratio:.1f}x Avg < {config.VOLUME_MIN_RATIO}x (zu niedrig)")

    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """Holt aktuelle Funding Rate für ein Symbol"""
        try:
            url = f"{self.futures_url}/fapi/v1/fundingRate"
            params = {"symbol": symbol, "limit": 1}
            result = self._request("GET", url, params)
            if result and len(result) > 0:
                return float(result[0].get("fundingRate", 0))
        except:
            pass
        return None

    def check_funding_rate_filter(self, symbol: str, side: str) -> Tuple[bool, str]:
        """
        Prüft Funding Rate als Contrarian-Indikator.
        - Hohe positive Funding → zu viele Longs → bevorzuge Shorts
        - Hohe negative Funding → zu viele Shorts → bevorzuge Longs
        """
        if not config.USE_FUNDING_RATE_FILTER:
            return (True, "Funding Filter deaktiviert")

        funding = self.get_funding_rate(symbol)
        if funding is None:
            return (True, "Funding nicht verfügbar")

        threshold = config.FUNDING_RATE_THRESHOLD
        funding_pct = funding * 100  # Als Prozent

        if side == "LONG":
            if funding > threshold:
                # Hohe positive Funding = viele Longs = gefährlich für Long
                return (False, f"Funding {funding_pct:.3f}% zu hoch → Longs riskant")
            elif funding < -threshold:
                # Negative Funding = wenige Longs = gut für Long
                return (True, f"Funding {funding_pct:.3f}% negativ → Longs bevorzugt ✓")
            return (True, f"Funding {funding_pct:.3f}% neutral ✓")

        elif side == "SHORT":
            if funding < -threshold:
                # Hohe negative Funding = viele Shorts = gefährlich für Short
                return (False, f"Funding {funding_pct:.3f}% zu negativ → Shorts riskant")
            elif funding > threshold:
                # Positive Funding = wenige Shorts = gut für Short
                return (True, f"Funding {funding_pct:.3f}% positiv → Shorts bevorzugt ✓")
            return (True, f"Funding {funding_pct:.3f}% neutral ✓")

        return (True, "Funding OK")

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

    def calculate_atr(self, klines: List[dict], period: int = 10) -> List[float]:
        """
        Berechnet Average True Range (ATR).
        """
        if len(klines) < period + 1:
            return []

        tr_values = []
        for i in range(1, len(klines)):
            high = klines[i]["high"]
            low = klines[i]["low"]
            prev_close = klines[i-1]["close"]

            # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

        # ATR als Simple Moving Average der TR-Werte
        atr_values = []
        for i in range(len(tr_values)):
            if i < period - 1:
                atr_values.append(None)
            else:
                atr = sum(tr_values[i-period+1:i+1]) / period
                atr_values.append(atr)

        return atr_values

    def calculate_kama(self, klines: List[dict], period: int = 10, fast: int = 2, slow: int = 30) -> dict:
        """
        Berechnet Kaufman Adaptive Moving Average (KAMA).
        KAMA passt sich der Marktvolatilität an.
        Returns: {"direction": "BULLISH"|"BEARISH"|"NEUTRAL", "value": float, "price": float}
        """
        if len(klines) < period + 1:
            return {"direction": "NEUTRAL", "value": 0, "price": 0}

        closes = [k["close"] for k in klines]

        # Efficiency Ratio (ER) berechnen
        # ER = Change / Volatility
        # Change = |Close - Close[period ago]|
        # Volatility = Sum of |Close - Close[1]| over period

        kama_values = [None] * period
        kama = closes[period - 1]  # Start mit SMA

        fast_sc = 2 / (fast + 1)  # Fast smoothing constant
        slow_sc = 2 / (slow + 1)  # Slow smoothing constant

        for i in range(period, len(closes)):
            # Change (Richtungsbewegung)
            change = abs(closes[i] - closes[i - period])

            # Volatility (Summe aller kleinen Bewegungen)
            volatility = sum(abs(closes[j] - closes[j - 1]) for j in range(i - period + 1, i + 1))

            # Efficiency Ratio
            er = change / volatility if volatility != 0 else 0

            # Smoothing Constant
            sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

            # KAMA berechnen
            kama = kama + sc * (closes[i] - kama)
            kama_values.append(kama)

        current_price = closes[-1]
        current_kama = kama_values[-1] if kama_values[-1] is not None else current_price

        # Direction bestimmen
        if current_price > current_kama * 1.001:  # 0.1% über KAMA
            direction = "BULLISH"
        elif current_price < current_kama * 0.999:  # 0.1% unter KAMA
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        return {
            "direction": direction,
            "value": current_kama,
            "price": current_price
        }

    def calculate_jma(self, klines: List[dict], period: int = 7, phase: int = 50, power: int = 2) -> dict:
        """
        Berechnet Jurik Moving Average (JMA) - vereinfachte Version.
        JMA ist sehr smooth mit wenig Lag.
        Returns: {"direction": "BULLISH"|"BEARISH"|"NEUTRAL", "value": float, "price": float}
        """
        if len(klines) < period + 1:
            return {"direction": "NEUTRAL", "value": 0, "price": 0}

        closes = [k["close"] for k in klines]

        # Vereinfachte JMA Implementierung (ähnlich zu T3 Moving Average)
        # Nutzt mehrfach geglättete EMAs

        # Phase adjustment (-100 to +100, default 50)
        phase_ratio = (phase / 100 + 1.5) * 0.5
        beta = 0.45 * (period - 1) / (0.45 * (period - 1) + 2)

        # Initialisierung
        e0 = closes[0]
        e1 = closes[0]
        e2 = closes[0]
        jma = closes[0]

        jma_values = []

        for i, close in enumerate(closes):
            # Erste Glättung
            e0 = (1 - beta) * close + beta * e0
            # Zweite Glättung
            e1 = (close - e0) * (1 - beta) + beta * e1
            # Dritte Glättung mit Phase
            e2 = (e0 + phase_ratio * e1 - jma) * ((1 - beta) ** power) + (beta ** power) * e2
            # JMA Wert
            jma = jma + e2

            jma_values.append(jma)

        current_price = closes[-1]
        current_jma = jma_values[-1]

        # Trend durch Vergleich mit vorherigem JMA
        prev_jma = jma_values[-2] if len(jma_values) > 1 else current_jma

        if current_price > current_jma and current_jma > prev_jma:
            direction = "BULLISH"
        elif current_price < current_jma and current_jma < prev_jma:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        return {
            "direction": direction,
            "value": current_jma,
            "price": current_price
        }

    def calculate_supertrend(self, klines: List[dict], period: int = 10, multiplier: float = 3.0) -> dict:
        """
        Berechnet Supertrend Indikator.
        Returns: {"direction": "BULLISH"|"BEARISH", "value": float, "price": float}
        """
        if len(klines) < period + 2:
            return {"direction": "NEUTRAL", "value": 0, "price": 0}

        atr_values = self.calculate_atr(klines, period)
        if not atr_values or atr_values[-1] is None:
            return {"direction": "NEUTRAL", "value": 0, "price": 0}

        # Supertrend Berechnung
        supertrend_up = []
        supertrend_down = []
        supertrend = []
        direction = []

        for i in range(len(klines)):
            if i < period:
                supertrend_up.append(None)
                supertrend_down.append(None)
                supertrend.append(None)
                direction.append(1)  # Default bullish
                continue

            atr = atr_values[i-1] if i > 0 and atr_values[i-1] is not None else 0
            hl2 = (klines[i]["high"] + klines[i]["low"]) / 2

            # Basic Upper und Lower Band
            basic_upper = hl2 + (multiplier * atr)
            basic_lower = hl2 - (multiplier * atr)

            # Final Upper Band
            prev_upper = supertrend_up[i-1] if supertrend_up[i-1] is not None else basic_upper
            if basic_upper < prev_upper or klines[i-1]["close"] > prev_upper:
                final_upper = basic_upper
            else:
                final_upper = prev_upper

            # Final Lower Band
            prev_lower = supertrend_down[i-1] if supertrend_down[i-1] is not None else basic_lower
            if basic_lower > prev_lower or klines[i-1]["close"] < prev_lower:
                final_lower = basic_lower
            else:
                final_lower = prev_lower

            supertrend_up.append(final_upper)
            supertrend_down.append(final_lower)

            # Direction
            prev_dir = direction[i-1]
            prev_st = supertrend[i-1] if supertrend[i-1] is not None else final_lower

            if prev_dir == 1:  # War bullish
                if klines[i]["close"] < final_lower:
                    direction.append(-1)  # Wechsel zu bearish
                    supertrend.append(final_upper)
                else:
                    direction.append(1)
                    supertrend.append(final_lower)
            else:  # War bearish
                if klines[i]["close"] > final_upper:
                    direction.append(1)  # Wechsel zu bullish
                    supertrend.append(final_lower)
                else:
                    direction.append(-1)
                    supertrend.append(final_upper)

        current_price = klines[-1]["close"]
        current_direction = "BULLISH" if direction[-1] == 1 else "BEARISH"
        current_st_value = supertrend[-1] if supertrend[-1] is not None else 0

        return {
            "direction": current_direction,
            "value": current_st_value,
            "price": current_price
        }

    def get_htf_supertrend(self, symbol: str = "BTCUSDT") -> dict:
        """
        Holt Supertrend für BTC auf Higher Timeframe.
        """
        limit = config.SUPERTREND_PERIOD * 3 + 10
        klines = self.get_klines(symbol, config.HTF_TIMEFRAME, limit)

        if len(klines) < config.SUPERTREND_PERIOD + 2:
            return {"direction": "NEUTRAL", "value": 0, "price": 0, "info": "Nicht genug Daten"}

        result = self.calculate_supertrend(
            klines,
            config.SUPERTREND_PERIOD,
            config.SUPERTREND_MULTIPLIER
        )

        if result["direction"] == "BULLISH":
            result["info"] = f"ST: BULL (${result['value']:,.0f})"
        elif result["direction"] == "BEARISH":
            result["info"] = f"ST: BEAR (${result['value']:,.0f})"
        else:
            result["info"] = "ST: NEUTRAL"

        return result

    def get_htf_consensus(self, symbol: str = "BTCUSDT") -> dict:
        """
        Berechnet alle 3 HTF-Indikatoren für ein Symbol.
        Returns direction und consensus count.
        """
        limit = 50
        klines = self.get_klines(symbol, config.HTF_TIMEFRAME, limit)

        if len(klines) < 15:
            return {
                "direction": "NEUTRAL",
                "consensus": 0,
                "supertrend": "NEUTRAL",
                "kama": "NEUTRAL",
                "jma": "NEUTRAL"
            }

        st = self.calculate_supertrend(klines, config.SUPERTREND_PERIOD, config.SUPERTREND_MULTIPLIER)
        kama = self.calculate_kama(klines, period=10)
        jma = self.calculate_jma(klines, period=7)

        bullish_votes = sum(1 for d in [st["direction"], kama["direction"], jma["direction"]] if d == "BULLISH")
        bearish_votes = sum(1 for d in [st["direction"], kama["direction"], jma["direction"]] if d == "BEARISH")

        if bullish_votes >= 2:
            direction = "BULLISH"
            consensus = bullish_votes
        elif bearish_votes >= 2:
            direction = "BEARISH"
            consensus = bearish_votes
        else:
            direction = "NEUTRAL"
            consensus = 0

        return {
            "direction": direction,
            "consensus": consensus,
            "supertrend": st["direction"],
            "kama": kama["direction"],
            "jma": jma["direction"],
            "st_value": st["value"],
            "kama_value": kama["value"],
            "jma_value": jma["value"],
            "price": klines[-1]["close"]
        }

    def get_market_consensus(self) -> dict:
        """
        Kombiniert BTC + ETH Konsens für ultimatives Markt-Signal.
        Berechnet auch Signal-Stärke (0-6 Punkte).
        """
        btc = self.get_htf_consensus("BTCUSDT")
        eth = self.get_htf_consensus("ETHUSDT")

        # Emojis für Anzeige
        def get_emoji(direction):
            return "🟢" if direction == "BULLISH" else "🔴" if direction == "BEARISH" else "⚪"

        btc_emoji = get_emoji(btc["direction"])
        eth_emoji = get_emoji(eth["direction"])

        # Signal-Stärke berechnen (0-6)
        # BTC: max 3 Punkte, ETH: max 3 Punkte
        strength = 0
        if btc["direction"] == "BULLISH":
            strength += btc["consensus"]
        elif btc["direction"] == "BEARISH":
            strength -= btc["consensus"]

        if eth["direction"] == "BULLISH":
            strength += eth["consensus"]
        elif eth["direction"] == "BEARISH":
            strength -= eth["consensus"]

        # Finale Richtung bestimmen
        # Beide müssen in dieselbe Richtung zeigen für starkes Signal
        if btc["direction"] == "BULLISH" and eth["direction"] == "BULLISH":
            direction = "BULLISH"
            strength_label = "STARK" if strength >= 5 else "MODERAT"
        elif btc["direction"] == "BEARISH" and eth["direction"] == "BEARISH":
            direction = "BEARISH"
            strength_label = "STARK" if strength <= -5 else "MODERAT"
        elif btc["direction"] == "BULLISH" and eth["direction"] == "NEUTRAL":
            direction = "WEAK_BULLISH"
            strength_label = "SCHWACH"
        elif btc["direction"] == "BEARISH" and eth["direction"] == "NEUTRAL":
            direction = "WEAK_BEARISH"
            strength_label = "SCHWACH"
        elif btc["direction"] == "NEUTRAL" and eth["direction"] == "BULLISH":
            direction = "WEAK_BULLISH"
            strength_label = "SCHWACH"
        elif btc["direction"] == "NEUTRAL" and eth["direction"] == "BEARISH":
            direction = "WEAK_BEARISH"
            strength_label = "SCHWACH"
        elif btc["direction"] != eth["direction"] and btc["direction"] != "NEUTRAL" and eth["direction"] != "NEUTRAL":
            # BTC und ETH widersprechen sich
            direction = "KONFLIKT"
            strength_label = "KONFLIKT"
        else:
            direction = "NEUTRAL"
            strength_label = "NEUTRAL"

        # Info-String
        btc_detail = f"ST{get_emoji(btc['supertrend'])}K{get_emoji(btc['kama'])}J{get_emoji(btc['jma'])}"
        eth_detail = f"ST{get_emoji(eth['supertrend'])}K{get_emoji(eth['kama'])}J{get_emoji(eth['jma'])}"

        info = f"BTC{btc_emoji}({btc['consensus']}/3) ETH{eth_emoji}({eth['consensus']}/3)"

        if direction == "BULLISH":
            info += f" → {strength_label} BULL → Nur Longs"
        elif direction == "BEARISH":
            info += f" → {strength_label} BEAR → Nur Shorts"
        elif direction == "WEAK_BULLISH":
            info += f" → SCHWACH BULL → Longs OK"
        elif direction == "WEAK_BEARISH":
            info += f" → SCHWACH BEAR → Shorts OK"
        elif direction == "KONFLIKT":
            info += f" → KONFLIKT → Kein Trade!"
        else:
            info += f" → NEUTRAL → Beide OK"

        return {
            "direction": direction,
            "strength": abs(strength),
            "strength_label": strength_label,
            "btc": btc,
            "eth": eth,
            "info": info,
            "detail": f"BTC: {btc_detail} | ETH: {eth_detail}"
        }

    def get_market_trend(self) -> dict:
        """
        Prüft BTC + ETH als kombinierte Markt-Indikatoren (Legacy).
        """
        url = "https://api.binance.com/api/v3/ticker/24hr"
        btc_response = self.session.get(url, params={"symbol": "BTCUSDT"})
        btc_change = float(btc_response.json().get("priceChangePercent", 0)) if btc_response.status_code == 200 else 0.0
        eth_response = self.session.get(url, params={"symbol": "ETHUSDT"})
        eth_change = float(eth_response.json().get("priceChangePercent", 0)) if eth_response.status_code == 200 else 0.0

        btc_bearish = btc_change <= -config.BTC_TREND_THRESHOLD
        eth_bearish = eth_change <= -config.BTC_TREND_THRESHOLD
        btc_bullish = btc_change >= config.BTC_TREND_THRESHOLD
        eth_bullish = eth_change >= config.BTC_TREND_THRESHOLD

        if btc_bearish and eth_bearish:
            direction = "BEARISH"
        elif btc_bullish and eth_bullish:
            direction = "BULLISH"
        elif btc_bearish or eth_bearish:
            direction = "WEAK_BEARISH"
        elif btc_bullish or eth_bullish:
            direction = "WEAK_BULLISH"
        else:
            direction = "NEUTRAL"

        return {"direction": direction, "btc_change": btc_change, "eth_change": eth_change}

    def get_fear_greed_index(self) -> dict:
        """
        Holt den aktuellen Fear & Greed Index von alternative.me
        Returns: {"value": 0-100, "classification": str, "timestamp": str}
        """
        try:
            url = "https://api.alternative.me/fng/"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    fng = data["data"][0]
                    return {
                        "value": int(fng.get("value", 50)),
                        "classification": fng.get("value_classification", "Neutral"),
                        "timestamp": fng.get("timestamp", "")
                    }
        except Exception as e:
            print(f"  ⚠️ Fear & Greed API Error: {e}")

        # Fallback: Neutral
        return {"value": 50, "classification": "Neutral", "timestamp": ""}

    def get_dynamic_position_limits(self) -> dict:
        """
        Berechnet dynamische Long/Short Limits basierend auf Fear & Greed Index.

        MOMENTUM-Modus (config.FEAR_GREED_MODE = "MOMENTUM"):
        - Greed (70-100): Mehr Longs (Trend folgen)
        - Fear (0-30): Mehr Shorts (Trend folgen)

        CONTRARIAN-Modus (config.FEAR_GREED_MODE = "CONTRARIAN"):
        - Fear (0-30): Mehr Longs (Kaufgelegenheit)
        - Greed (70-100): Mehr Shorts (Überkauft)

        Returns: {"max_longs": int, "max_shorts": int, "reason": str}
        """
        total_positions = config.MAX_OPEN_POSITIONS

        # Wenn F&G Allocation deaktiviert → 50/50
        if not config.USE_FEAR_GREED_ALLOCATION:
            half = total_positions // 2
            return {
                "max_longs": half,
                "max_shorts": total_positions - half,
                "fear_greed": 50,
                "classification": "Disabled",
                "reason": f"F&G deaktiviert → {half}L/{total_positions - half}S"
            }

        # Versuche Fear & Greed Index zu holen
        fng = self.get_fear_greed_index()
        value = fng["value"]

        # Fallback auf BTC/ETH Trend wenn F&G nicht verfügbar
        if value == 50 and fng["classification"] == "Neutral":
            market = self.get_market_trend()
            if market["direction"] in ["BEARISH", "WEAK_BEARISH"]:
                value = 30  # Simuliere Fear
            elif market["direction"] in ["BULLISH", "WEAK_BULLISH"]:
                value = 70  # Simuliere Greed

        # Dezile: 0-10, 10-20, ..., 90-100
        decile = min(9, value // 10)  # 0-9

        # Modus-abhängige Berechnung
        mode = getattr(config, 'FEAR_GREED_MODE', 'MOMENTUM')

        if mode == "MOMENTUM":
            # MOMENTUM: Greed = mehr Longs, Fear = mehr Shorts
            if decile >= 7:  # Greed (70-100) → Mehr Longs
                long_ratio = 0.7 + (decile - 7) * 0.1  # 0.7, 0.8, 0.9
            elif decile <= 2:  # Fear (0-30) → Mehr Shorts
                long_ratio = 0.3 - (2 - decile) * 0.1  # 0.3, 0.2, 0.1
            else:  # Neutral
                long_ratio = 0.5
            mode_label = "MOM"
        else:
            # CONTRARIAN: Fear = mehr Longs, Greed = mehr Shorts
            if decile <= 2:  # Fear (0-30) → Mehr Longs
                long_ratio = 0.7 + (2 - decile) * 0.1
            elif decile >= 7:  # Greed (70-100) → Mehr Shorts
                long_ratio = 0.3 - (decile - 7) * 0.1
            else:  # Neutral
                long_ratio = 0.5
            mode_label = "CON"

        max_longs = max(1, int(total_positions * long_ratio))
        max_shorts = max(1, total_positions - max_longs)

        reason = f"F&G: {value} ({fng['classification']}) [{mode_label}] → {max_longs}L/{max_shorts}S"

        return {
            "max_longs": max_longs,
            "max_shorts": max_shorts,
            "fear_greed": value,
            "classification": fng["classification"],
            "mode": mode,
            "reason": reason
        }

    def is_trade_allowed_by_market(self, trade_side: str) -> tuple:
        """
        Prüft ob Trade-Richtung vom Markt erlaubt ist.
        VEREINFACHT: Nur BTC Supertrend (1 Indikator).
        """
        # Einfacher BTC Supertrend Filter
        if config.USE_HTF_SUPERTREND:
            st = self.get_htf_supertrend("BTCUSDT")

            if st["direction"] == "BULLISH":
                if trade_side == "SHORT":
                    return (False, f"BTC Supertrend BULL → Keine Shorts")
                return (True, f"BTC Supertrend BULL → Longs OK")

            elif st["direction"] == "BEARISH":
                if trade_side == "LONG":
                    return (False, f"BTC Supertrend BEAR → Keine Longs")
                return (True, f"BTC Supertrend BEAR → Shorts OK")

            return (True, "BTC Supertrend NEUTRAL → Beide OK")

        # Legacy BTC/ETH Filter
        if config.USE_BTC_MARKET_FILTER:
            market = self.get_market_trend()
            info = f"BTC {market['btc_change']:+.1f}% | ETH {market['eth_change']:+.1f}%"

            if market["direction"] in ["BEARISH", "WEAK_BEARISH"]:
                if trade_side == "LONG":
                    return (False, f"{info} - keine Longs")
                return (True, f"{info} - Shorts OK")

            elif market["direction"] in ["BULLISH", "WEAK_BULLISH"]:
                if trade_side == "SHORT":
                    return (False, f"{info} - keine Shorts")
                return (True, f"{info} - Longs OK")

            return (True, f"{info} - beide OK")

        return (True, "Markt-Filter deaktiviert")

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

    def get_trading_stats(self) -> dict:
        """Berechnet Trading-Statistiken in % und USD"""
        position_size = config.MAX_POSITION_SIZE

        if not self.trade_history:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "total_pnl_usd": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "avg_win_usd": 0.0,
                "avg_loss_usd": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
                "best_trade_usd": 0.0,
                "worst_trade_usd": 0.0,
                "equity_curve": [],
                "equity_curve_usd": [],
                "position_size": position_size
            }

        wins = [t for t in self.trade_history if t["pnl_percent"] > 0]
        losses = [t for t in self.trade_history if t["pnl_percent"] <= 0]

        total_pnl = sum(t["pnl_percent"] for t in self.trade_history)
        avg_win = sum(t["pnl_percent"] for t in wins) / len(wins) if wins else 0.0
        avg_loss = sum(t["pnl_percent"] for t in losses) / len(losses) if losses else 0.0
        best_trade = max(t["pnl_percent"] for t in self.trade_history) if self.trade_history else 0.0
        worst_trade = min(t["pnl_percent"] for t in self.trade_history) if self.trade_history else 0.0

        # Equity Curve berechnen (kumulative PnL in % und USD)
        equity_curve = []
        equity_curve_usd = []
        cumulative = 0.0
        cumulative_usd = 0.0
        for t in self.trade_history:
            cumulative += t["pnl_percent"]
            # USD = Position Size * PnL% / 100
            pnl_usd = position_size * t["pnl_percent"] / 100
            cumulative_usd += pnl_usd
            equity_curve.append(cumulative)
            equity_curve_usd.append(cumulative_usd)

        return {
            "total_trades": len(self.trade_history),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(self.trade_history) * 100 if self.trade_history else 0.0,
            "total_pnl": total_pnl,
            "total_pnl_usd": position_size * total_pnl / 100,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_win_usd": position_size * avg_win / 100,
            "avg_loss_usd": position_size * avg_loss / 100,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "best_trade_usd": position_size * best_trade / 100,
            "worst_trade_usd": position_size * worst_trade / 100,
            "equity_curve": equity_curve,
            "equity_curve_usd": equity_curve_usd,
            "position_size": position_size
        }

    def show_trade_history(self, limit: int = 10):
        """Zeigt letzte Trades"""
        if not self.trade_history:
            print("  Keine Trades bisher.")
            return

        print(f"\n  📋 LETZTE {min(limit, len(self.trade_history))} TRADES:")
        print(f"  {'#':<3} {'Symbol':<10} {'Side':<6} {'Entry':>10} {'Exit':>10} {'PnL':>8}")
        print("  " + "-" * 52)

        for i, trade in enumerate(self.trade_history[-limit:][::-1], 1):
            emoji = "🟢" if trade["pnl_percent"] > 0 else "🔴"
            symbol = trade["symbol"].replace("USDT", "")
            print(f"  {i:<3} {symbol:<10} {trade['side']:<6} "
                  f"${trade['entry_price']:>9.4f} ${trade['exit_price']:>9.4f} "
                  f"{emoji} {trade['pnl_percent']:>+6.2f}%")

    def show_equity_curve(self, width: int = 40, height: int = 8):
        """Zeigt ASCII Kapitalkurve"""
        stats = self.get_trading_stats()
        curve = stats["equity_curve"]

        if len(curve) < 2:
            print("  Nicht genug Trades für Kapitalkurve.")
            return

        print(f"\n  📈 KAPITALKURVE ({len(curve)} Trades):")

        # Normalisieren für Anzeige
        min_val = min(curve)
        max_val = max(curve)
        range_val = max_val - min_val if max_val != min_val else 1

        # ASCII Chart erstellen
        chart = [[' ' for _ in range(width)] for _ in range(height)]

        for x, val in enumerate(curve):
            if x >= width:
                break
            # Y-Position berechnen (invertiert weil Terminal von oben nach unten)
            y = height - 1 - int((val - min_val) / range_val * (height - 1))
            y = max(0, min(height - 1, y))
            chart[y][x] = '█' if val >= 0 else '▄'

        # Nulllinie zeichnen
        zero_y = height - 1 - int((0 - min_val) / range_val * (height - 1)) if min_val < 0 else height - 1
        zero_y = max(0, min(height - 1, zero_y))

        # Chart ausgeben
        print(f"  {max_val:>+6.1f}% ┤", end="")
        for row in range(height):
            if row > 0:
                if row == zero_y:
                    print(f"     0.0% ┼", end="")
                else:
                    print("           │", end="")
            for col in range(width):
                if chart[row][col] != ' ':
                    print(chart[row][col], end="")
                elif row == zero_y:
                    print("─", end="")
                else:
                    print(" ", end="")
            print()
        print(f"  {min_val:>+6.1f}% └" + "─" * width)
        print(f"           Trade 1" + " " * (width - 15) + f"Trade {len(curve)}")

    def show_status(self):
        """Zeigt aktuellen Status inkl. Trade History und Statistiken"""
        print(f"\n{'='*60}")
        print("  TESTNET STATUS (Futures Only)")
        print(f"{'='*60}")

        futures_balance = self.get_futures_balance()
        stats = self.get_trading_stats()

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
                trailing = " TS" if pos.peak_price > 0 else ""
                print(f"  {pos.symbol.replace('USDT', ''):<12} {pos.side:<6} "
                      f"${pos.entry_price:>9.4f} ${current:>9.4f} {emoji} {pnl:>+7.2f}%{trailing}")

        # Trading Statistiken
        print(f"\n  📊 TRADING STATISTIKEN:")
        print(f"  Trades: {stats['total_trades']} | "
              f"Wins: {stats['wins']} | Losses: {stats['losses']} | "
              f"Win-Rate: {stats['win_rate']:.1f}%")
        if stats['total_trades'] > 0:
            print(f"  Gesamt PnL: {stats['total_pnl']:+.2f}% | "
                  f"Avg Win: {stats['avg_win']:+.2f}% | Avg Loss: {stats['avg_loss']:+.2f}%")
            print(f"  Best: {stats['best_trade']:+.2f}% | Worst: {stats['worst_trade']:+.2f}%")

        # Trade History
        self.show_trade_history(5)

        # Equity Curve
        if stats['total_trades'] >= 3:
            self.show_equity_curve()

        print(f"{'='*60}\n")

    def export_dashboard_data(self):
        """Exportiert Daten für das HTML-Dashboard"""
        stats = self.get_trading_stats()

        # Positionen mit aktuellen PnL
        positions_data = {}
        for key, pos in self.positions.items():
            current_price = self._get_futures_price(pos.symbol) or pos.entry_price
            if pos.side == "LONG":
                current_pnl = (current_price - pos.entry_price) / pos.entry_price * 100
            else:
                current_pnl = (pos.entry_price - current_price) / pos.entry_price * 100

            positions_data[key] = {
                "symbol": pos.symbol,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "quantity": pos.quantity,
                "entry_time": pos.entry_time,
                "peak_price": pos.peak_price,
                "current_price": current_price,
                "current_pnl": current_pnl
            }

        # BTC Supertrend Status
        btc_st = None
        if config.USE_HTF_SUPERTREND:
            st = self.get_htf_supertrend("BTCUSDT")
            btc_st = {
                "direction": st["direction"],
                "value": st["value"],
                "price": st["price"]
            }

        data = {
            "timestamp": datetime.now().isoformat(),
            "balance": self.get_futures_balance(),
            "positions": positions_data,
            "trade_history": self.trade_history,
            "stats": stats,
            "btc_supertrend": btc_st
        }

        try:
            with open("dashboard_data.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Dashboard Export Fehler: {e}")


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
    print(f"  BTC Supertrend Filter: {'✅ AN' if config.USE_HTF_SUPERTREND else '❌ AUS'}")
    if config.USE_HTF_SUPERTREND:
        print(f"    BTC {config.HTF_TIMEFRAME} Supertrend (Period={config.SUPERTREND_PERIOD}, Mult={config.SUPERTREND_MULTIPLIER})")
    print(f"  BTC/ETH 24h-Filter: {'✅ AN' if config.USE_BTC_MARKET_FILTER else '❌ AUS'}")
    print(f"  Trailing Stop: {'✅ AN' if config.USE_TRAILING_STOP else '❌ AUS'}")
    if config.USE_TRAILING_STOP:
        print(f"    Aktivierung: +{config.TRAILING_STOP_ACTIVATION}% | Abstand: {config.TRAILING_STOP_DISTANCE}%")
    print(f"  RSI Filter: {'✅ AN' if config.USE_RSI_FILTER else '❌ AUS'}")
    if config.USE_RSI_FILTER:
        print(f"    Long: RSI ≤ {config.RSI_OVERSOLD} | Short: RSI ≥ {config.RSI_OVERBOUGHT}")
    print(f"  Mean Reversion:")
    print(f"    LONG:  Entry bei {config.BUY_LOSER_THRESHOLD}% | TP: +{config.TAKE_PROFIT_PERCENT}% | SL: -{config.STOP_LOSS_PERCENT}%")
    print(f"    SHORT: Entry bei +{config.SHORT_GAINER_THRESHOLD}% | TP: +{config.SHORT_TAKE_PROFIT}% | SL: -{config.SHORT_STOP_LOSS}%")
    print(f"  Scan Interval: {config.SCAN_INTERVAL_SECONDS}s")
    print(f"{'='*70}")
    print("  📊 Dashboard: dashboard.html öffnen für Live-Ansicht")
    print("  [Strg+C zum Beenden]\n")

    trader.show_status()

    try:
        while True:
            timestamp = time.strftime('%H:%M:%S')

            # 0. Close-All Signal prüfen
            trader.check_close_all_signal()

            # 1. TP/SL prüfen
            trader.check_positions_tp_sl()

            # Zähle offene Positionen
            long_count = len([p for p in trader.positions.values() if p.side == "LONG"])
            short_count = len([p for p in trader.positions.values() if p.side == "SHORT"])

            # Dynamische Limits basierend auf Fear & Greed Index
            limits = trader.get_dynamic_position_limits()
            max_longs = limits["max_longs"]
            max_shorts = limits["max_shorts"]
            print(f"  📊 {limits['reason']}")

            # 2. Markt-Check (HTF Supertrend oder BTC/ETH)
            long_allowed, long_reason = trader.is_trade_allowed_by_market("LONG")
            short_allowed, short_reason = trader.is_trade_allowed_by_market("SHORT")

            if config.USE_HTF_SUPERTREND:
                st = trader.get_htf_supertrend("BTCUSDT")
                st_emoji = "🟢" if st["direction"] == "BULLISH" else "🔴" if st["direction"] == "BEARISH" else "⚪"
                print(f"\n[{timestamp}] 📊 BTC {config.HTF_TIMEFRAME}: {st_emoji} {st['direction']} @ ${st['price']:,.0f} (ST: ${st['value']:,.0f})")
            else:
                market = trader.get_market_trend()
                print(f"\n[{timestamp}] 📊 Markt: BTC {market['btc_change']:+.1f}% | ETH {market['eth_change']:+.1f}%")

            if not long_allowed:
                print(f"  ⛔ Keine Longs: {long_reason}")
            if not short_allowed:
                print(f"  ⛔ Keine Shorts: {short_reason}")

            # 3. BREAKOUT DETECTION (wenn aktiviert)
            if config.USE_BREAKOUT_DETECTION and (long_count < max_longs or short_count < max_shorts):
                print(f"\n[{timestamp}] 🔍 Suche Breakout-Signale...")
                breakout_signals = trader.get_breakout_signals(5)

                for coin in breakout_signals:
                    if coin["breakout"] == "BREAKOUT_UP" and long_count < max_longs and long_allowed:
                        key = f"{coin['symbol']}_LONG"
                        if key not in trader.positions:
                            # Nicht LONG wenn bereits SHORT offen
                            if f"{coin['symbol']}_SHORT" in trader.positions:
                                continue
                            print(f"\n[{timestamp}] 🚀 BREAKOUT LONG: {coin['base']} @ {coin['change_percent']:+.1f}% (über {config.BREAKOUT_LOOKBACK_DAYS}-Tage High)")
                            result = trader.futures_long(coin["symbol"], config.MAX_POSITION_SIZE)
                            if result:
                                long_count += 1
                                break

                    elif coin["breakout"] == "BREAKOUT_DOWN" and short_count < max_shorts and short_allowed:
                        key = f"{coin['symbol']}_SHORT"
                        if key not in trader.positions:
                            # Nicht SHORT wenn bereits LONG offen
                            if f"{coin['symbol']}_LONG" in trader.positions:
                                continue
                            print(f"\n[{timestamp}] 💥 BREAKOUT SHORT: {coin['base']} @ {coin['change_percent']:+.1f}% (unter {config.BREAKOUT_LOOKBACK_DAYS}-Tage Low)")
                            result = trader.futures_short(coin["symbol"], config.MAX_POSITION_SIZE)
                            if result:
                                short_count += 1
                                break

            # 3b. TREND-FOLLOWING (Fallback wenn kein Breakout)
            elif config.USE_TREND_FILTER and (long_count < max_longs or short_count < max_shorts):
                print(f"\n[{timestamp}] 🔍 Suche Trend-Signale...")
                trend_signals = trader.get_trend_signals(5)

                for coin in trend_signals:
                    if coin["trend"] == "UP" and long_count < max_longs and long_allowed:
                        key = f"{coin['symbol']}_LONG"
                        if key not in trader.positions:
                            # Nicht LONG wenn bereits SHORT offen
                            if f"{coin['symbol']}_SHORT" in trader.positions:
                                continue
                            print(f"\n[{timestamp}] 📈 TREND LONG: {coin['base']} @ {coin['change_percent']:+.1f}% (3-Tage UP)")
                            result = trader.futures_long(coin["symbol"], config.MAX_POSITION_SIZE)
                            if result:
                                long_count += 1
                                break

                    elif coin["trend"] == "DOWN" and short_count < max_shorts and short_allowed:
                        key = f"{coin['symbol']}_SHORT"
                        if key not in trader.positions:
                            # Nicht SHORT wenn bereits LONG offen
                            if f"{coin['symbol']}_LONG" in trader.positions:
                                continue
                            print(f"\n[{timestamp}] 📉 TREND SHORT: {coin['base']} @ {coin['change_percent']:+.1f}% (3-Tage DOWN)")
                            result = trader.futures_short(coin["symbol"], config.MAX_POSITION_SIZE)
                            if result:
                                short_count += 1
                                break

            # 4. MEAN REVERSION (Fallback wenn keine Trend-Signale)
            # Nur wenn Trend-Filter aus ist ODER keine Trend-Signale gefunden wurden

            # LONG: Buy the Dip
            if long_count < max_longs and long_allowed:
                losers = trader.get_top_losers(5)
                for coin in losers:
                    key = f"{coin['symbol']}_LONG"
                    if key not in trader.positions:
                        # WICHTIG: Nicht LONG gehen wenn bereits SHORT offen!
                        if f"{coin['symbol']}_SHORT" in trader.positions:
                            continue

                        # Bei aktivem Trend-Filter: Prüfe ob NICHT im Downtrend
                        if config.USE_TREND_FILTER:
                            trend = trader.check_trend_consistency(coin["symbol"])
                            if trend == "DOWN":
                                print(f"  ⏭️  Skip {coin['base']} - im Downtrend (kein Mean Reversion)")
                                trader.filter_stats.record_blocked(coin["symbol"], "LONG", "trend", coin["price"])
                                continue

                        # RSI Filter: Nur kaufen wenn überverkauft
                        if config.USE_RSI_FILTER:
                            rsi_ok, rsi_reason = trader.check_rsi_entry(coin["symbol"], "LONG")
                            if not rsi_ok:
                                print(f"  ⏭️  Skip {coin['base']} - {rsi_reason}")
                                trader.filter_stats.record_blocked(coin["symbol"], "LONG", "rsi", coin["price"])
                                continue

                        # Supertrend Entry Filter: Nicht einsteigen wenn zu weit über ST (Chasing)
                        if config.USE_SUPERTREND_ENTRY_FILTER:
                            st_ok, st_reason = trader.check_supertrend_entry(coin["symbol"], "LONG")
                            if not st_ok:
                                print(f"  ⏭️  Skip {coin['base']} - {st_reason}")
                                trader.filter_stats.record_blocked(coin["symbol"], "LONG", "supertrend_entry", coin["price"])
                                continue

                        # Volume Filter: Nur bei überdurchschnittlichem Volume
                        if config.USE_VOLUME_FILTER:
                            vol_ok, vol_reason = trader.check_volume_filter(coin["symbol"])
                            if not vol_ok:
                                print(f"  ⏭️  Skip {coin['base']} - {vol_reason}")
                                trader.filter_stats.record_blocked(coin["symbol"], "LONG", "volume", coin["price"])
                                continue

                        # Funding Rate Filter: Contrarian bei extremer Funding
                        if config.USE_FUNDING_RATE_FILTER:
                            fund_ok, fund_reason = trader.check_funding_rate_filter(coin["symbol"], "LONG")
                            if not fund_ok:
                                print(f"  ⏭️  Skip {coin['base']} - {fund_reason}")
                                trader.filter_stats.record_blocked(coin["symbol"], "LONG", "funding", coin["price"])
                                continue

                        print(f"\n[{timestamp}] 📉 MEAN REV LONG: {coin['base']} @ {coin['change_percent']:.1f}%")
                        result = trader.futures_long(coin["symbol"], config.MAX_POSITION_SIZE)
                        if result:
                            break

            # SHORT: Fade the Pump
            if short_count < max_shorts and short_allowed:
                gainers = trader.get_top_gainers(5)
                for coin in gainers:
                    key = f"{coin['symbol']}_SHORT"
                    if key not in trader.positions:
                        # WICHTIG: Nicht SHORT gehen wenn bereits LONG offen!
                        if f"{coin['symbol']}_LONG" in trader.positions:
                            continue

                        # Bei aktivem Trend-Filter: Prüfe ob NICHT im Uptrend
                        if config.USE_TREND_FILTER:
                            trend = trader.check_trend_consistency(coin["symbol"])
                            if trend == "UP":
                                print(f"  ⏭️  Skip {coin['base']} - im Uptrend (kein Mean Reversion)")
                                trader.filter_stats.record_blocked(coin["symbol"], "SHORT", "trend", coin["price"])
                                continue

                        # RSI Filter: Nur shorten wenn überkauft
                        if config.USE_RSI_FILTER:
                            rsi_ok, rsi_reason = trader.check_rsi_entry(coin["symbol"], "SHORT")
                            if not rsi_ok:
                                print(f"  ⏭️  Skip {coin['base']} - {rsi_reason}")
                                trader.filter_stats.record_blocked(coin["symbol"], "SHORT", "rsi", coin["price"])
                                continue

                        # Supertrend Entry Filter: Nicht einsteigen wenn zu weit unter ST (Chasing)
                        if config.USE_SUPERTREND_ENTRY_FILTER:
                            st_ok, st_reason = trader.check_supertrend_entry(coin["symbol"], "SHORT")
                            if not st_ok:
                                print(f"  ⏭️  Skip {coin['base']} - {st_reason}")
                                trader.filter_stats.record_blocked(coin["symbol"], "SHORT", "supertrend_entry", coin["price"])
                                continue
                            print(f"  ✓ ST Entry: {st_reason}")

                        # Volume Filter: Nur bei überdurchschnittlichem Volume
                        if config.USE_VOLUME_FILTER:
                            vol_ok, vol_reason = trader.check_volume_filter(coin["symbol"])
                            if not vol_ok:
                                print(f"  ⏭️  Skip {coin['base']} - {vol_reason}")
                                trader.filter_stats.record_blocked(coin["symbol"], "SHORT", "volume", coin["price"])
                                continue

                        # Funding Rate Filter: Contrarian bei extremer Funding
                        if config.USE_FUNDING_RATE_FILTER:
                            fund_ok, fund_reason = trader.check_funding_rate_filter(coin["symbol"], "SHORT")
                            if not fund_ok:
                                print(f"  ⏭️  Skip {coin['base']} - {fund_reason}")
                                trader.filter_stats.record_blocked(coin["symbol"], "SHORT", "funding", coin["price"])
                                continue

                        print(f"\n[{timestamp}] 📈 MEAN REV SHORT: {coin['base']} @ +{coin['change_percent']:.1f}%")
                        result = trader.futures_short(coin["symbol"], config.MAX_POSITION_SIZE)
                        if result:
                            break

            # 4. Status
            futures_bal = trader.get_futures_balance()
            print(f"\n[{timestamp}] Positionen: {len(trader.positions)} | "
                  f"Futures: ${futures_bal:,.0f}")

            # 5. Dashboard aktualisieren
            trader.export_dashboard_data()

            # 6. Filter-Stats: Blocked Trades nach 4h auswerten
            trader.filter_stats.check_blocked_outcomes(trader._get_futures_price)

            # 7. Filter-Stats alle 10 Zyklen anzeigen
            if not hasattr(trader, '_stats_cycle'):
                trader._stats_cycle = 0
            trader._stats_cycle += 1
            if trader._stats_cycle >= 10:
                print(trader.filter_stats.get_summary())
                trader._stats_cycle = 0

            time.sleep(config.SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n\n⏹️  Auto-Trading beendet.")
        print(trader.filter_stats.get_summary())
        trader.show_status()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

        if mode == "backtest":
            print("\n" + "="*60)
            print("  BACKTEST MODUS")
            print("  Starte: python backtest_supertrend.py")
            print("="*60)
            import subprocess
            subprocess.run([sys.executable, "backtest_supertrend.py"])

        elif mode == "analyze":
            print("\n" + "="*60)
            print("  ANALYSE MODUS")
            print("  Starte: python analyze_peaks.py")
            print("="*60)
            import subprocess
            subprocess.run([sys.executable, "analyze_peaks.py"])

        elif mode == "stats":
            print("\n" + "="*60)
            print("  FILTER STATISTIKEN")
            print("="*60)
            stats = FilterStats()
            print(stats.get_summary())

        elif mode == "resetstats":
            print("\n" + "="*60)
            print("  STATISTIKEN ZURÜCKSETZEN")
            print("="*60)
            stats = FilterStats()
            stats.reset()

        elif mode == "help":
            print("\n" + "="*60)
            print("  CRYPTO TOPMOVER - HILFE")
            print("="*60)
            print("\n  Verwendung:")
            print("    python testnet_trader.py           → Live Trading")
            print("    python testnet_trader.py backtest  → Backtest starten")
            print("    python testnet_trader.py analyze   → Peak-Analyse")
            print("    python testnet_trader.py stats     → Filter-Statistiken anzeigen")
            print("    python testnet_trader.py resetstats → Statistiken zurücksetzen")
            print("    python testnet_trader.py help      → Diese Hilfe")
            print("\n  Config (config.py):")
            print("    FEAR_GREED_MODE = 'MOMENTUM'    → Greed=Longs, Fear=Shorts")
            print("    FEAR_GREED_MODE = 'CONTRARIAN'  → Fear=Longs, Greed=Shorts")
            print("="*60 + "\n")

        else:
            print(f"\n  ❌ Unbekannter Modus: {mode}")
            print("  Verwende: python testnet_trader.py help")
    else:
        # Standard: Live Trading
        run_testnet_auto_trading()
