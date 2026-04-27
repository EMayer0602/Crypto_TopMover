"""
strategies/topmover_v0.py
=========================
TopMover v0 – simple long-only daily momentum rotation strategy.

Logic
-----
At *rebalance_hour_utc* (default 00:00 UTC) each day:
  1. Compute the 24-hour (``lookback_hours``) return for every symbol in the
     universe.
  2. Rank descending; take the top *n_hold* symbols.
  3. Equal-weight portfolio; rebalance with realistic fees + slippage on
     the traded notional (turnover).

Returns an equity-curve DataFrame indexed by rebalance timestamp.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class TopMoverV0Params:
    lookback_hours: int = 24   # momentum window in hours
    n_hold: int = 5            # number of symbols to hold
    rebalance_hour_utc: int = 0


def _build_price_matrix(ohlcv_by_symbol: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Align all symbols on their open_time index and return a close-price matrix."""
    frames = []
    for sym, df in ohlcv_by_symbol.items():
        if df.empty:
            continue
        tmp = (
            df[["open_time", "close"]]
            .rename(columns={"close": sym})
            .set_index("open_time")
        )
        frames.append(tmp)

    if not frames:
        return pd.DataFrame()

    price = pd.concat(frames, axis=1).sort_index()
    # Forward-fill minor gaps (e.g. exchange maintenance candles)
    price = price.ffill()
    return price


def _compute_momentum(price: pd.DataFrame, lookback_hours: int) -> pd.Series:
    """Return percentage change over *lookback_hours* periods for the latest row."""
    if len(price) < lookback_hours + 1:
        return pd.Series(dtype=float)
    past = price.iloc[-lookback_hours]
    current = price.iloc[-1]
    mom = (current / past) - 1.0
    return mom.dropna()


def run_topmover_backtest(
    ohlcv_by_symbol: Dict[str, pd.DataFrame],
    params: TopMoverV0Params,
    initial_capital: float,
    fee_rate: float,
    slippage_bps: float,
) -> pd.DataFrame:
    """Run a vectorised daily-rebalance backtest.

    Parameters
    ----------
    ohlcv_by_symbol:
        Dict mapping symbol → OHLCV DataFrame (must include ``open_time`` and
        ``close`` columns, with timezone-aware UTC timestamps).
    params:
        Strategy hyper-parameters.
    initial_capital:
        Starting portfolio value in quote currency.
    fee_rate:
        One-way trading fee as a decimal (e.g. 0.001 for 0.1 %).
    slippage_bps:
        One-way slippage in basis points (e.g. 5 = 0.05 %).

    Returns
    -------
    pd.DataFrame with columns:
        ts          – rebalance timestamp (UTC)
        equity      – portfolio value after applying costs
        turnover    – fraction of portfolio rebalanced [0, 1]
        holdings    – comma-separated list of held symbols
    """
    price = _build_price_matrix(ohlcv_by_symbol)
    if price.empty:
        return pd.DataFrame(columns=["ts", "equity", "turnover", "holdings"])

    rets = price.pct_change()

    equity = initial_capital
    weights: Dict[str, float] = {}
    prev_weights: Optional[Dict[str, float]] = None
    records = []

    slippage_rate = slippage_bps / 10_000.0

    for i, ts in enumerate(price.index):
        # --- Mark-to-market: apply bar returns to current holdings ---
        if weights and i > 0:
            bar_ret = sum(
                weights[s] * rets.iloc[i][s]
                for s in weights
                if s in rets.columns and not pd.isna(rets.iloc[i][s])
            )
            equity *= 1.0 + bar_ret

        # --- Rebalance once per day at the specified UTC hour ---
        if ts.hour == params.rebalance_hour_utc and ts.minute == 0:
            # Need at least lookback_hours + 1 rows of history
            if i < params.lookback_hours:
                continue

            price_window = price.iloc[: i + 1]
            mom = _compute_momentum(price_window, params.lookback_hours)
            if mom.empty:
                continue

            top_symbols = (
                mom.sort_values(ascending=False)
                .head(params.n_hold)
                .index.tolist()
            )
            if not top_symbols:
                continue

            new_weights: Dict[str, float] = {
                s: 1.0 / len(top_symbols) for s in top_symbols
            }

            # Turnover = half the L1 norm of weight change (long-only convention)
            if prev_weights is None:
                turnover = 1.0
            else:
                all_syms = set(prev_weights) | set(new_weights)
                turnover = 0.5 * sum(
                    abs(new_weights.get(s, 0.0) - prev_weights.get(s, 0.0))
                    for s in all_syms
                )

            # Apply round-trip transaction costs on the traded notional.
            # turnover = one-way fraction rebalanced; multiply by 2 to account
            # for both the sell leg and the buy leg (except on initial entry
            # where there is no sell, so keep 1x there via the turnover=1.0 path).
            legs = 1 if prev_weights is None else 2
            cost_rate = (fee_rate + slippage_rate) * legs * turnover
            equity *= 1.0 - cost_rate

            weights = new_weights
            prev_weights = dict(new_weights)

            records.append(
                {
                    "ts": ts,
                    "equity": equity,
                    "turnover": turnover,
                    "holdings": ",".join(top_symbols),
                }
            )

    return pd.DataFrame(records)


def summary_stats(equity_curve: pd.DataFrame) -> Dict[str, float]:
    """Compute basic performance statistics from an equity-curve DataFrame."""
    if equity_curve.empty or len(equity_curve) < 2:
        return {"total_return": float("nan"), "max_drawdown": float("nan")}

    eq = equity_curve["equity"]
    total_return = eq.iloc[-1] / eq.iloc[0] - 1.0
    running_max = eq.cummax()
    drawdown = (eq / running_max) - 1.0
    max_drawdown = drawdown.min()

    return {
        "total_return": total_return,
        "max_drawdown": max_drawdown,
    }
