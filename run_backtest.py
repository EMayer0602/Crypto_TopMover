"""
run_backtest.py
===============
Entry point for the Crypto TopMover backtesting pipeline.

Usage
-----
    python run_backtest.py

What it does
------------
1. Fetches the top-N USDC symbols by 24h quote volume from Binance.
2. Downloads OHLCV data for the full IS + OOS date range.
3. Runs the TopMover v0 strategy on the In-Sample (IS) period.
4. Runs the TopMover v0 strategy on the Out-of-Sample (OOS) period.
5. Prints a summary (total return, max drawdown) for both periods.
6. Saves equity curves to logs/equity_is.csv and logs/equity_oos.csv.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from config import Config
from data_fetcher import (
    dt_to_ms_utc,
    fetch_klines,
    fetch_universe_ohlcv,
    get_top_symbols_by_quote_volume,
    klines_to_df,
)
from strategies.topmover_v0 import (
    TopMoverV0Params,
    run_topmover_backtest,
    summary_stats,
)

LOGS_DIR = "logs"


def _ensure_logs_dir() -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)


def _date_to_utc(d) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _slice(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    mask = (df["open_time"] >= start) & (df["open_time"] <= end)
    return df.loc[mask].copy()


def main() -> None:
    _ensure_logs_dir()
    cfg = Config()

    # --- 1. Universe ----------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"Fetching Top-{cfg.top_n} {cfg.quote_asset} symbols by 24h quote volume …")
    top_symbols = get_top_symbols_by_quote_volume(cfg.quote_asset, cfg.top_n)
    if not top_symbols:
        print("ERROR: No symbols found. Check your internet connection and quote asset.")
        return

    print(f"\nUniverse (Top {cfg.top_n} | quote={cfg.quote_asset}):")
    for info in top_symbols:
        print(f"  {info.symbol:<20} 24h quoteVolume = {info.quote_volume:>20,.2f}")

    symbols = [s.symbol for s in top_symbols]

    # --- 2. Data download -------------------------------------------------------
    is_start = _date_to_utc(cfg.is_start)
    is_end = _date_to_utc(cfg.is_end)
    oos_start = _date_to_utc(cfg.oos_start)
    now_utc = datetime.now(timezone.utc)

    print(f"\n{'='*60}")
    print(
        f"Downloading {cfg.timeframe} klines from {is_start.date()} to {now_utc.date()} …"
    )

    ohlcv_all = fetch_universe_ohlcv(symbols, cfg.timeframe, is_start, now_utc)

    if not ohlcv_all:
        print("ERROR: No OHLCV data returned for any symbol.")
        return

    # --- 3. Split IS / OOS -------------------------------------------------------
    ohlcv_is = {s: _slice(df, is_start, is_end) for s, df in ohlcv_all.items()}
    ohlcv_oos = {s: _slice(df, oos_start, now_utc) for s, df in ohlcv_all.items()}

    # Drop symbols with empty IS or OOS slices
    ohlcv_is = {s: df for s, df in ohlcv_is.items() if not df.empty}
    ohlcv_oos = {s: df for s, df in ohlcv_oos.items() if not df.empty}

    # --- 4. Strategy parameters -------------------------------------------------
    params = TopMoverV0Params(
        lookback_hours=cfg.lookback_hours,
        n_hold=cfg.top_movers_n,
        rebalance_hour_utc=cfg.rebalance_hour_utc,
    )

    # --- 5. Backtest IS ----------------------------------------------------------
    print(f"\n{'='*60}")
    print(
        f"Running IS backtest  ({cfg.is_start} → {cfg.is_end}) | "
        f"universe={len(ohlcv_is)} symbols …"
    )
    eq_is = run_topmover_backtest(
        ohlcv_is,
        params,
        initial_capital=cfg.initial_capital,
        fee_rate=cfg.fee_rate,
        slippage_bps=cfg.slippage_bps,
    )

    stats_is = summary_stats(eq_is)
    print(f"\n  [IS]  rebalance points : {len(eq_is)}")
    print(f"  [IS]  total return      : {stats_is['total_return']*100:+.2f} %")
    print(f"  [IS]  max drawdown      : {stats_is['max_drawdown']*100:.2f} %")

    # --- 6. Backtest OOS ---------------------------------------------------------
    print(f"\n{'='*60}")
    print(
        f"Running OOS backtest ({cfg.oos_start} → {now_utc.date()}) | "
        f"universe={len(ohlcv_oos)} symbols …"
    )
    eq_oos = run_topmover_backtest(
        ohlcv_oos,
        params,
        initial_capital=cfg.initial_capital,
        fee_rate=cfg.fee_rate,
        slippage_bps=cfg.slippage_bps,
    )

    stats_oos = summary_stats(eq_oos)
    print(f"\n  [OOS] rebalance points : {len(eq_oos)}")
    print(f"  [OOS] total return      : {stats_oos['total_return']*100:+.2f} %")
    print(f"  [OOS] max drawdown      : {stats_oos['max_drawdown']*100:.2f} %")

    # --- 7. Save results ---------------------------------------------------------
    is_path = os.path.join(LOGS_DIR, "equity_is.csv")
    oos_path = os.path.join(LOGS_DIR, "equity_oos.csv")

    eq_is.to_csv(is_path, index=False)
    eq_oos.to_csv(oos_path, index=False)

    print(f"\n{'='*60}")
    print(f"Saved  {is_path}")
    print(f"Saved  {oos_path}")
    print("Done.\n")


if __name__ == "__main__":
    main()
