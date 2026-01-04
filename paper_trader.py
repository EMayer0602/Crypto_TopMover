"""
Paper Trading Bot for Crypto Top Mover Strategy
Implements buying top losers and shorting top gainers
"""

import json
import os
from datetime import datetime
import config
from data_fetcher import DataFetcher


class Position:
    """Represents a trading position"""
    
    def __init__(self, symbol, entry_price, size, position_type, target_profit, stop_loss):
        self.symbol = symbol
        self.entry_price = entry_price
        self.size = size  # Number of units
        self.position_type = position_type  # 'LONG' or 'SHORT'
        self.target_profit = target_profit  # Target profit %
        self.stop_loss = stop_loss  # Stop loss %
        self.entry_time = datetime.now()
        self.entry_value = entry_price * size
        
    def calculate_pnl(self, current_price):
        """Calculate current profit/loss"""
        if self.position_type == 'LONG':
            # For long positions: profit when price goes up
            pnl = (current_price - self.entry_price) * self.size
            pnl_percent = ((current_price - self.entry_price) / self.entry_price) * 100
        else:  # SHORT
            # For short positions: profit when price goes down
            pnl = (self.entry_price - current_price) * self.size
            pnl_percent = ((self.entry_price - current_price) / self.entry_price) * 100
        
        return pnl, pnl_percent
    
    def should_close(self, current_price):
        """Check if position should be closed (target or stop loss hit)"""
        pnl, pnl_percent = self.calculate_pnl(current_price)
        
        # Check target profit
        if pnl_percent >= self.target_profit:
            return True, 'TARGET_HIT'
        
        # Check stop loss
        if pnl_percent <= self.stop_loss:
            return True, 'STOP_LOSS'
        
        return False, None
    
    def to_dict(self):
        """Convert position to dictionary"""
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'size': self.size,
            'position_type': self.position_type,
            'target_profit': self.target_profit,
            'stop_loss': self.stop_loss,
            'entry_time': self.entry_time.isoformat(),
            'entry_value': self.entry_value
        }


class PaperTrader:
    """Paper trading bot with top mover strategies"""
    
    def __init__(self):
        self.capital = config.INITIAL_CAPITAL
        self.initial_capital = config.INITIAL_CAPITAL
        self.positions = {}  # symbol -> Position
        self.trade_history = []
        self.data_fetcher = DataFetcher()
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """Create logs directory if it doesn't exist"""
        if not os.path.exists(config.LOG_DIR):
            os.makedirs(config.LOG_DIR)
    
    def get_portfolio_value(self):
        """Calculate total portfolio value (capital + position values)"""
        position_value = sum(pos.entry_value for pos in self.positions.values())
        return self.capital + position_value
    
    def get_available_capital(self):
        """Get capital available for new trades"""
        return self.capital
    
    def can_open_position(self):
        """Check if we can open a new position"""
        return len(self.positions) < config.MAX_OPEN_POSITIONS
    
    def open_position(self, signal):
        """
        Open a new position based on signal
        
        Args:
            signal: Trading signal dictionary
            
        Returns:
            True if position opened successfully
        """
        symbol = signal['symbol']
        
        # Check if we already have a position in this symbol
        if symbol in self.positions:
            print(f"Already have a position in {symbol}")
            return False
        
        # Check if we can open more positions
        if not self.can_open_position():
            print(f"Maximum open positions ({config.MAX_OPEN_POSITIONS}) reached")
            return False
        
        # Calculate position size
        position_value = self.capital * config.POSITION_SIZE_PERCENT
        
        if position_value > self.capital:
            print(f"Insufficient capital for position")
            return False
        
        entry_price = signal['current_price']
        size = position_value / entry_price
        
        # Determine position type
        if signal['signal_type'] == 'LOSER_BUY':
            if not config.ALLOW_LONG_POSITIONS:
                return False
            position_type = 'LONG'
        elif signal['signal_type'] == 'GAINER_SHORT':
            if not config.ALLOW_SHORT_POSITIONS:
                return False
            position_type = 'SHORT'
        else:
            return False
        
        # Create position
        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            size=size,
            position_type=position_type,
            target_profit=signal['target_profit'],
            stop_loss=signal['stop_loss']
        )
        
        # Update capital and positions
        self.capital -= position_value
        self.positions[symbol] = position
        
        # Log trade
        trade_log = {
            'action': 'OPEN',
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'position_type': position_type,
            'entry_price': entry_price,
            'size': size,
            'value': position_value,
            'signal_type': signal['signal_type'],
            'price_change_24h': signal['price_change_24h']
        }
        self.trade_history.append(trade_log)
        self._write_log(trade_log)
        
        print(f"Opened {position_type} position in {symbol} at ${entry_price:.4f}")
        return True
    
    def close_position(self, symbol, current_price, reason='MANUAL'):
        """
        Close an existing position
        
        Args:
            symbol: Symbol of position to close
            current_price: Current market price
            reason: Reason for closing
            
        Returns:
            True if position closed successfully
        """
        if symbol not in self.positions:
            print(f"No position found for {symbol}")
            return False
        
        position = self.positions[symbol]
        pnl, pnl_percent = position.calculate_pnl(current_price)
        
        # Calculate exit value
        exit_value = current_price * position.size
        
        # Update capital
        if position.position_type == 'LONG':
            self.capital += exit_value
        else:  # SHORT
            # For shorts, we get back entry value + profit (or - loss)
            self.capital += position.entry_value + pnl
        
        # Log trade
        trade_log = {
            'action': 'CLOSE',
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'position_type': position.position_type,
            'entry_price': position.entry_price,
            'exit_price': current_price,
            'size': position.size,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'reason': reason,
            'hold_time': (datetime.now() - position.entry_time).total_seconds() / 3600  # hours
        }
        self.trade_history.append(trade_log)
        self._write_log(trade_log)
        
        print(f"Closed {position.position_type} position in {symbol} at ${current_price:.4f} | PnL: {pnl_percent:.2f}% (${pnl:.2f}) | Reason: {reason}")
        
        # Remove position
        del self.positions[symbol]
        
        return True
    
    def update_positions(self):
        """Update all open positions and close if target/stop hit"""
        if not self.positions:
            return
        
        print(f"\nUpdating {len(self.positions)} open positions...")
        
        # Batch fetch prices for all open positions
        symbols = list(self.positions.keys())
        prices = self.data_fetcher.get_multiple_prices(symbols)
        
        symbols_to_close = []
        
        for symbol, position in self.positions.items():
            current_price = prices.get(symbol)
            
            if current_price is None:
                print(f"Could not get current price for {symbol}")
                continue
            
            pnl, pnl_percent = position.calculate_pnl(current_price)
            print(f"  {symbol} ({position.position_type}): ${current_price:.4f} | PnL: {pnl_percent:.2f}% (${pnl:.2f})")
            
            # Check if position should be closed
            should_close, reason = position.should_close(current_price)
            if should_close:
                symbols_to_close.append((symbol, current_price, reason))
        
        # Close positions that hit target or stop loss
        for symbol, price, reason in symbols_to_close:
            self.close_position(symbol, price, reason)
    
    def scan_and_trade(self):
        """Scan market for signals and open positions"""
        print("\nScanning market for trading signals...")
        signals = self.data_fetcher.get_trading_signals()
        
        buy_signals = signals['buy_signals']
        short_signals = signals['short_signals']
        
        print(f"Found {len(buy_signals)} buy signals and {len(short_signals)} short signals")
        
        # Try to open positions for buy signals (prioritize best strategy!)
        for signal in buy_signals:
            if self.can_open_position():
                self.open_position(signal)
        
        # Try to open positions for short signals
        for signal in short_signals:
            if self.can_open_position():
                self.open_position(signal)
    
    def get_statistics(self):
        """Calculate trading statistics"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl_percent': 0,
                'portfolio_value': self.get_portfolio_value(),
                'total_return': 0
            }
        
        closed_trades = [t for t in self.trade_history if t['action'] == 'CLOSE']
        
        if not closed_trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl_percent': 0,
                'portfolio_value': self.get_portfolio_value(),
                'total_return': 0
            }
        
        winning_trades = [t for t in closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in closed_trades)
        avg_pnl_percent = sum(t['pnl_percent'] for t in closed_trades) / len(closed_trades)
        
        portfolio_value = self.get_portfolio_value()
        total_return = ((portfolio_value - self.initial_capital) / self.initial_capital) * 100
        
        return {
            'total_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / len(closed_trades)) * 100 if closed_trades else 0,
            'total_pnl': total_pnl,
            'avg_pnl_percent': avg_pnl_percent,
            'portfolio_value': portfolio_value,
            'total_return': total_return
        }
    
    def print_status(self):
        """Print current trading status"""
        print("\n" + "="*60)
        print("PAPER TRADING BOT STATUS")
        print("="*60)
        
        stats = self.get_statistics()
        
        print(f"\nCapital: ${self.capital:.2f}")
        print(f"Portfolio Value: ${stats['portfolio_value']:.2f}")
        print(f"Total Return: {stats['total_return']:.2f}%")
        print(f"\nOpen Positions: {len(self.positions)}")
        
        for symbol, position in self.positions.items():
            print(f"  {symbol} ({position.position_type}): ${position.entry_price:.4f} x {position.size:.4f}")
        
        print(f"\nTrade Statistics:")
        print(f"  Total Trades: {stats['total_trades']}")
        print(f"  Winning Trades: {stats['winning_trades']}")
        print(f"  Losing Trades: {stats['losing_trades']}")
        print(f"  Win Rate: {stats['win_rate']:.2f}%")
        print(f"  Average PnL: {stats['avg_pnl_percent']:.2f}%")
        print(f"  Total PnL: ${stats['total_pnl']:.2f}")
        print("="*60)
    
    def _write_log(self, trade_log):
        """Write trade log to file"""
        log_file = os.path.join(config.LOG_DIR, config.LOG_FILE)
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(trade_log) + '\n')
    
    def save_state(self, filename='bot_state.json'):
        """Save bot state to file"""
        state = {
            'capital': self.capital,
            'initial_capital': self.initial_capital,
            'positions': {k: v.to_dict() for k, v in self.positions.items()},
            'trade_history': self.trade_history,
            'timestamp': datetime.now().isoformat()
        }
        
        filepath = os.path.join(config.LOG_DIR, filename)
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
        
        print(f"State saved to {filepath}")


if __name__ == "__main__":
    # Test the paper trader
    trader = PaperTrader()
    trader.print_status()
    
    print("\nRunning one scan and trade cycle...")
    trader.scan_and_trade()
    trader.update_positions()
    trader.print_status()
