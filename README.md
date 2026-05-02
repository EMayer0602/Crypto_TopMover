# Crypto_TopMover

Fetch the top 20 Binance symbols quoted in USDC and calculate PnL from 2024-01-01
until the current hour for 5m, 15m, 1h, and 1d timeframes.

## Structure

/home/user/Crypto_TopMover/
├── config.py        # Einstellungen (Thresholds, Capital, API)
├── data_fetcher.py  # Binance market data helpers
├── run.py           # PnL report generator
└── requirements.txt

## Usage

```bash
pip install -r requirements.txt
python run.py
```

Optional overrides:

```bash
python run.py --quote USDC --top-n 20 --start-date 2024-01-01T00:00:00Z \
  --intervals 5m,15m,1h,1d --output pnl_report.csv
```

The script writes a CSV report with open/close prices and PnL percentage for each
symbol and interval.
