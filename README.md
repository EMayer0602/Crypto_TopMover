# Crypto Top Mover - Paper Trading Bot

A paper trading bot that implements proven cryptocurrency trading strategies based on market movers.

## 📁 Project Structure

```
/home/user/Crypto_TopMover/
├── config.py        # Einstellungen (Thresholds, Capital, API)
├── data_fetcher.py  # Top Gainer/Loser Scanner
├── paper_trader.py  # Paper Trading Bot
├── run.py           # Haupteinstieg
├── logs/            # Trade Logs
└── ohlcv_cache/     # Daten Cache
```

## 🎯 Key Findings & Strategies

Based on extensive backtesting, the following strategies have been implemented:

### ⭐ Best Strategy: Buy Top Losers
- **Entry**: Buy when price drops ≥10% in 24h
- **Target**: +4% average profit
- **Win Rate**: 79-93%
- **Status**: PRIMARY STRATEGY ✓

### 📉 Bear Market Optimization
- **Entry**: Buy when price drops ≥15% in bear market
- **Target**: +7.23% average profit
- **Status**: Enhanced loser strategy for bear markets

### 📈 Short Top Gainers
- **Entry**: Short when price rises ≥30% in 24h
- **Target**: +2.79% average profit
- **Status**: SECONDARY STRATEGY

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/EMayer0602/Crypto_TopMover.git
cd Crypto_TopMover
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## 💻 Usage

### Run Continuous Trading Mode (Default)
```bash
python run.py
# or
python run.py continuous
```

### Run Single Iteration
```bash
python run.py once
```

### Run Backtest
```bash
python run.py backtest
```

### Show Help
```bash
python run.py help
```

## ⚙️ Configuration

Edit `config.py` to customize:

- **Capital Settings**: Initial capital and position sizing
- **Strategy Thresholds**: Entry and exit points for each strategy
- **Risk Management**: Stop losses and profit targets
- **Market Scanner**: Number of coins to scan, volume filters
- **API Settings**: Rate limits and timeouts

### Enable Bear Market Mode
Set `BEAR_MARKET_MODE = True` in `config.py` to use the enhanced bear market strategy.

## 📊 Features

- ✅ Real-time market scanning using CoinGecko API
- ✅ Automatic position management
- ✅ Target profit and stop loss automation
- ✅ Comprehensive trade logging
- ✅ Portfolio tracking and statistics
- ✅ Multi-position support
- ✅ Long and short trading
- ✅ Data caching to reduce API calls

## 📈 Statistics Tracking

The bot tracks:
- Total trades and win rate
- Average profit/loss per trade
- Portfolio value and returns
- Position hold times
- Detailed trade logs in JSON format

## 🔒 Risk Management

- Configurable position sizing (default: 10% per trade)
- Maximum open positions limit (default: 5)
- Automatic stop loss execution
- Automatic target profit taking

## 📝 Logs

All trades are logged to `logs/trades.log` in JSON format.
Bot state is saved to `logs/bot_state.json` after each iteration.

## 🔑 API

Uses the free CoinGecko API - no API key required for basic usage.
Includes rate limiting to respect API guidelines.

## ⚠️ Disclaimer

This is a paper trading bot for educational and research purposes only.
Not financial advice. Always do your own research before trading real money.

## 📜 License

MIT License
