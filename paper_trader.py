"""
Paper Trading Bot
=================
Simuliert Trades ohne echtes Geld.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import config
from data_fetcher import BinanceScanner


@dataclass
class Position:
    """Eine offene Position"""
    symbol: str
    base: str
    entry_price: float
    quantity: float
    entry_time: str
    investment_usdt: float

    def current_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def pnl_percent(self, current_price: float) -> float:
        return ((current_price - self.entry_price) / self.entry_price) * 100

    def pnl_usdt(self, current_price: float) -> float:
        return self.current_value(current_price) - self.investment_usdt


@dataclass
class Trade:
    """Ein abgeschlossener Trade"""
    symbol: str
    side: str  # BUY oder SELL
    price: float
    quantity: float
    timestamp: str
    pnl_usdt: float = 0.0
    pnl_percent: float = 0.0


class PaperTrader:
    """Paper Trading Bot mit Take Profit und Stop Loss"""

    def __init__(self):
        self.scanner = BinanceScanner()
        self.balance = config.PAPER_TRADING_CAPITAL
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self.state_file = "paper_trader_state.json"
        self._load_state()
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Erstellt benötigte Verzeichnisse"""
        os.makedirs(config.LOG_DIR, exist_ok=True)
        os.makedirs(config.CACHE_DIR, exist_ok=True)

    def _load_state(self):
        """Lädt den gespeicherten Zustand"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    self.balance = state.get("balance", config.PAPER_TRADING_CAPITAL)
                    self.positions = {
                        k: Position(**v) for k, v in state.get("positions", {}).items()
                    }
                    self.trade_history = [
                        Trade(**t) for t in state.get("trade_history", [])
                    ]
            except Exception as e:
                print(f"Fehler beim Laden des Zustands: {e}")

    def _save_state(self):
        """Speichert den aktuellen Zustand"""
        state = {
            "balance": self.balance,
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "trade_history": [asdict(t) for t in self.trade_history],
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def buy(self, symbol: str, amount_usdt: float = None) -> Optional[Position]:
        """Kauft eine Position"""
        if amount_usdt is None:
            amount_usdt = config.MAX_POSITION_SIZE

        # Prüfungen
        if len(self.positions) >= config.MAX_OPEN_POSITIONS:
            print(f"❌ Max. Positionen ({config.MAX_OPEN_POSITIONS}) erreicht!")
            return None

        if symbol in self.positions:
            print(f"❌ Position in {symbol} bereits offen!")
            return None

        if amount_usdt > self.balance:
            print(f"❌ Nicht genug Balance! Verfügbar: ${self.balance:.2f}")
            return None

        # Preis holen
        price = self.scanner.get_ticker_price(symbol)
        if not price:
            print(f"❌ Konnte Preis für {symbol} nicht abrufen!")
            return None

        # Position eröffnen
        quantity = amount_usdt / price
        base = symbol.replace(config.QUOTE_CURRENCY, "")

        position = Position(
            symbol=symbol,
            base=base,
            entry_price=price,
            quantity=quantity,
            entry_time=datetime.now().isoformat(),
            investment_usdt=amount_usdt,
        )

        self.positions[symbol] = position
        self.balance -= amount_usdt

        # Trade loggen
        trade = Trade(
            symbol=symbol,
            side="BUY",
            price=price,
            quantity=quantity,
            timestamp=datetime.now().isoformat(),
        )
        self.trade_history.append(trade)
        self._save_state()
        self._log_trade(trade)

        print(f"✅ KAUF: {quantity:.6f} {base} @ ${price:.4f} = ${amount_usdt:.2f}")
        return position

    def sell(self, symbol: str, reason: str = "manual") -> Optional[float]:
        """Verkauft eine Position"""
        if symbol not in self.positions:
            print(f"❌ Keine offene Position in {symbol}!")
            return None

        position = self.positions[symbol]
        current_price = self.scanner.get_ticker_price(symbol)

        if not current_price:
            print(f"❌ Konnte Preis für {symbol} nicht abrufen!")
            return None

        # PnL berechnen
        pnl_usdt = position.pnl_usdt(current_price)
        pnl_percent = position.pnl_percent(current_price)
        sell_value = position.current_value(current_price)

        # Position schließen
        del self.positions[symbol]
        self.balance += sell_value

        # Trade loggen
        trade = Trade(
            symbol=symbol,
            side="SELL",
            price=current_price,
            quantity=position.quantity,
            timestamp=datetime.now().isoformat(),
            pnl_usdt=pnl_usdt,
            pnl_percent=pnl_percent,
        )
        self.trade_history.append(trade)
        self._save_state()
        self._log_trade(trade)

        emoji = "🟢" if pnl_usdt >= 0 else "🔴"
        print(f"{emoji} VERKAUF ({reason}): {position.quantity:.6f} {position.base} "
              f"@ ${current_price:.4f} | PnL: {pnl_percent:+.2f}% (${pnl_usdt:+.2f})")

        return pnl_usdt

    def check_positions(self):
        """Prüft alle Positionen auf TP/SL"""
        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]
            current_price = self.scanner.get_ticker_price(symbol)

            if not current_price:
                continue

            pnl_percent = position.pnl_percent(current_price)

            # Take Profit
            if pnl_percent >= config.TAKE_PROFIT_PERCENT:
                self.sell(symbol, reason=f"TP ({config.TAKE_PROFIT_PERCENT}%)")

            # Stop Loss
            elif pnl_percent <= -config.STOP_LOSS_PERCENT:
                self.sell(symbol, reason=f"SL ({config.STOP_LOSS_PERCENT}%)")

    def show_positions(self):
        """Zeigt alle offenen Positionen"""
        if not self.positions:
            print("\n📭 Keine offenen Positionen.\n")
            return

        print(f"\n{'='*70}")
        print(f"  OFFENE POSITIONEN")
        print(f"{'='*70}")
        print(f"{'Symbol':<12} {'Menge':>12} {'Entry':>10} {'Aktuell':>10} {'PnL %':>10} {'PnL $':>10}")
        print("-" * 70)

        total_pnl = 0
        for symbol, pos in self.positions.items():
            current_price = self.scanner.get_ticker_price(symbol) or pos.entry_price
            pnl_percent = pos.pnl_percent(current_price)
            pnl_usdt = pos.pnl_usdt(current_price)
            total_pnl += pnl_usdt

            print(f"{pos.base:<12} {pos.quantity:>12.4f} ${pos.entry_price:>9.4f} "
                  f"${current_price:>9.4f} {pnl_percent:>+9.2f}% ${pnl_usdt:>+9.2f}")

        print("-" * 70)
        print(f"{'GESAMT':<12} {'':<12} {'':<10} {'':<10} {'':<10} ${total_pnl:>+9.2f}")
        print(f"{'='*70}\n")

    def show_stats(self):
        """Zeigt Trading Statistiken"""
        sells = [t for t in self.trade_history if t.side == "SELL"]
        wins = [t for t in sells if t.pnl_usdt > 0]
        losses = [t for t in sells if t.pnl_usdt < 0]

        total_pnl = sum(t.pnl_usdt for t in sells)
        win_rate = (len(wins) / len(sells) * 100) if sells else 0

        print(f"\n{'='*50}")
        print(f"  TRADING STATISTIKEN")
        print(f"{'='*50}")
        print(f"  Startkapital:    ${config.PAPER_TRADING_CAPITAL:,.2f}")
        print(f"  Aktuelle Balance: ${self.balance:,.2f}")
        print(f"  Offene Positionen: {len(self.positions)}")
        print(f"  Abgeschl. Trades: {len(sells)}")
        print(f"  Gewinner:        {len(wins)}")
        print(f"  Verlierer:       {len(losses)}")
        print(f"  Win-Rate:        {win_rate:.1f}%")
        print(f"  Gesamt PnL:      ${total_pnl:+,.2f}")
        print(f"{'='*50}\n")

    def _log_trade(self, trade: Trade):
        """Loggt einen Trade in eine Datei"""
        if not config.LOG_TRADES:
            return

        log_file = os.path.join(config.LOG_DIR, "trades.log")
        with open(log_file, "a") as f:
            f.write(f"{trade.timestamp} | {trade.side:4} | {trade.symbol:12} | "
                    f"Price: {trade.price:.4f} | Qty: {trade.quantity:.6f} | "
                    f"PnL: {trade.pnl_percent:+.2f}% (${trade.pnl_usdt:+.2f})\n")

    def reset(self):
        """Setzt den Bot zurück"""
        self.balance = config.PAPER_TRADING_CAPITAL
        self.positions = {}
        self.trade_history = []
        self._save_state()
        print("🔄 Paper Trader wurde zurückgesetzt!")


if __name__ == "__main__":
    trader = PaperTrader()
    trader.show_stats()
    trader.show_positions()
