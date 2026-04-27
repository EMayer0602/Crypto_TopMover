"""
data_fetcher.py
===============
Fetches the top-N symbols by 24h quote volume from Binance and retrieves
their OHLCV (klines) data using only Binance public REST endpoints.

Endpoints used:
  GET /api/v3/ticker/24hr   – 24-hour rolling window ticker statistics
  GET /api/v3/klines         – OHLCV candles (paged, max 1 000 rows/request)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

BINANCE_REST = "https://api.binance.com"

# Conservative delay between klines requests to stay within Binance rate limits
_REQUEST_DELAY_SEC = 0.2


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    base: str
    quote: str
    quote_volume: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_json(url: str, params: Optional[dict] = None) -> Any:
    """GET *url* and return parsed JSON; raises on HTTP error."""
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Universe selection
# ---------------------------------------------------------------------------

def get_top_symbols_by_quote_volume(quote_asset: str, top_n: int) -> List[SymbolInfo]:
    """Return the *top_n* Binance spot symbols (by 24h quote volume) that are
    denominated in *quote_asset* (e.g. "USDC").

    Data source: GET /api/v3/ticker/24hr
    """
    data = _get_json(f"{BINANCE_REST}/api/v3/ticker/24hr")
    if not isinstance(data, list):
        raise ValueError(f"Unexpected response from /api/v3/ticker/24hr: {type(data)}")

    q = quote_asset.upper()
    results: List[SymbolInfo] = []

    for row in data:
        symbol = row.get("symbol", "")
        if not isinstance(symbol, str) or not symbol.endswith(q):
            continue
        try:
            qvol = float(row.get("quoteVolume", 0.0))
        except (TypeError, ValueError):
            continue
        base = symbol[: -len(q)]
        if not base:
            continue
        results.append(SymbolInfo(symbol=symbol, base=base, quote=q, quote_volume=qvol))

    results.sort(key=lambda x: x.quote_volume, reverse=True)
    return results[:top_n]


# ---------------------------------------------------------------------------
# Klines / OHLCV
# ---------------------------------------------------------------------------

def fetch_klines(
    symbol: str,
    interval: str,
    start_ts_ms: int,
    end_ts_ms: int,
    limit: int = 1000,
) -> List[List[Any]]:
    """Fetch all klines for *symbol* between *start_ts_ms* and *end_ts_ms*
    (both in milliseconds, UTC).  Pages through Binance's 1 000-row limit
    automatically with a small delay between requests.
    """
    url = f"{BINANCE_REST}/api/v3/klines"
    all_rows: List[List[Any]] = []
    cursor = start_ts_ms

    while cursor < end_ts_ms:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": cursor,
            "endTime": end_ts_ms,
            "limit": limit,
        }
        rows = _get_json(url, params=params)
        if not rows:
            break

        all_rows.extend(rows)

        last_open_ms = int(rows[-1][0])
        # Advance past the last returned candle to avoid duplicates
        next_cursor = last_open_ms + 1
        if next_cursor <= cursor:
            break
        cursor = next_cursor

        time.sleep(_REQUEST_DELAY_SEC)

        if last_open_ms >= end_ts_ms:
            break

    return all_rows


def klines_to_df(rows: List[List[Any]]) -> pd.DataFrame:
    """Convert raw Binance klines (list of lists) to a tidy DataFrame.

    Binance kline column order:
      0  open_time (ms)         6  close_time (ms)
      1  open                   7  quote_asset_volume
      2  high                   8  number_of_trades
      3  low                    9  taker_buy_base_asset_volume
      4  close                 10  taker_buy_quote_asset_volume
      5  volume                11  ignore
    """
    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base_volume", "taker_buy_quote_volume", "ignore",
    ]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df

    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

    numeric_cols = [
        "open", "high", "low", "close", "volume",
        "quote_volume", "taker_buy_base_volume", "taker_buy_quote_volume",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["trades"] = pd.to_numeric(df["trades"], errors="coerce").fillna(0).astype(int)
    df = df.drop(columns=["ignore"])
    df = df.dropna(subset=["open_time", "close_time", "close"])
    df = (
        df.sort_values("open_time")
        .drop_duplicates(subset=["open_time"], keep="last")
        .reset_index(drop=True)
    )
    return df


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def dt_to_ms_utc(dt: datetime) -> int:
    """Convert a datetime to millisecond epoch (UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_universe_ohlcv(
    symbols: List[str],
    interval: str,
    start: datetime,
    end: datetime,
) -> Dict[str, pd.DataFrame]:
    """Fetch klines for every symbol in *symbols* and return a dict mapping
    symbol → DataFrame.  Symbols with no data are silently omitted.
    """
    start_ms = dt_to_ms_utc(start)
    end_ms = dt_to_ms_utc(end)
    result: Dict[str, pd.DataFrame] = {}

    for sym in symbols:
        rows = fetch_klines(sym, interval, start_ms, end_ms)
        df = klines_to_df(rows)
        if df.empty:
            print(f"  WARNING: no data returned for {sym} – skipping")
            continue
        result[sym] = df
        print(
            f"  {sym}: {len(df)} bars  "
            f"({df['open_time'].min().date()} → {df['open_time'].max().date()})"
        )

    return result
