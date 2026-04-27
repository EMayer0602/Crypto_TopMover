# Crypto_TopMover

A backtesting skeleton for the **TopMover v0** strategy on Binance Spot.

## Strategy Overview

* **Universe** – Top 20 USDC-denominated spot symbols by 24h quote volume  
  (fetched live from Binance `/api/v3/ticker/24hr`)
* **Timeframe** – 1-hour candles via Binance `/api/v3/klines`
* **Signal** – 24-hour momentum; rebalance daily at 00:00 UTC into the top 5 movers
* **Costs** – 0.10 % fee + 5 bps slippage applied on rebalance turnover
* **Dates**
  * In-Sample (IS): 2024-01-01 → 2025-09-30
  * Out-of-Sample (OOS): 2025-10-01 → current date

## Project Structure

```
Crypto_TopMover/
├── config.py              # All configurable parameters
├── data_fetcher.py        # Binance data helpers (universe + klines)
├── strategies/
│   ├── __init__.py
│   └── topmover_v0.py     # Strategy & backtest engine
├── run_backtest.py        # Entry point
├── logs/                  # Output CSVs (created automatically)
├── requirements.txt
└── .gitignore
```

## Setup

```bash
# 1. Clone
git clone https://github.com/EMayer0602/Crypto_TopMover.git
cd Crypto_TopMover

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Run

```bash
python run_backtest.py
```

The script will:
1. Print the live Top-20 USDC universe with their 24h quote volumes.
2. Download 1h OHLCV data for the full date range (IS + OOS).
3. Run the TopMover v0 backtest on the IS period and print summary stats.
4. Run the TopMover v0 backtest on the OOS period and print summary stats.
5. Save equity curves to `logs/equity_is.csv` and `logs/equity_oos.csv`.

### Example output

```
============================================================
Fetching Top-20 USDC symbols by 24h quote volume …

Universe (Top 20 | quote=USDC):
  BTCUSDC              24h quoteVolume =      123,456,789.00
  ETHUSDC              24h quoteVolume =       98,765,432.00
  ...

============================================================
Downloading 1h klines from 2024-01-01 to 2026-04-27 …

  BTCUSDC: 11352 bars  (2024-01-01 → 2026-04-26)
  ...

============================================================
Running IS backtest  (2024-01-01 → 2025-09-30) | universe=20 symbols …

  [IS]  rebalance points :  638
  [IS]  total return      : +42.50 %
  [IS]  max drawdown      : -18.23 %

============================================================
Running OOS backtest (2025-10-01 → 2026-04-27) | universe=19 symbols …

  [OOS] rebalance points :  208
  [OOS] total return      :  +8.10 %
  [OOS] max drawdown      :  -6.40 %

============================================================
Saved  logs/equity_is.csv
Saved  logs/equity_oos.csv
Done.
```

## Configuration

Edit `config.py` to adjust:

| Parameter | Default | Description |
|---|---|---|
| `quote_asset` | `"USDC"` | Quote asset filter for Binance pairs |
| `top_n` | `20` | Universe size |
| `timeframe` | `"1h"` | Kline interval |
| `initial_capital` | `10 000` | Starting portfolio value |
| `fee_rate` | `0.001` | One-way taker fee (0.1 %) |
| `slippage_bps` | `5.0` | One-way slippage in basis points |
| `top_movers_n` | `5` | Number of symbols held at once |
| `lookback_hours` | `24` | Momentum lookback window |

## Notes

* No API key is required – only public Binance endpoints are used.
* All timestamps are UTC.
* The `logs/` directory is created automatically if it does not exist.
* `logs/*.csv` and cache files are excluded from version control via `.gitignore`.
