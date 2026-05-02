from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

import requests

from config import BINANCE_BASE_URL, MAX_RETRIES, REQUEST_PAUSE_SECONDS, REQUEST_TIMEOUT


class BinanceAPIError(RuntimeError):
    pass


def _request_json(
    session: requests.Session,
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{BINANCE_BASE_URL}{path}"
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code in {418, 429}:
                time.sleep(2**attempt)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(2**attempt)
    raise BinanceAPIError(f"Binance API request failed for {path}") from last_exc


def get_top_symbols_by_quote_volume(
    session: requests.Session,
    quote_asset: str,
    top_n: int,
) -> List[str]:
    payload = _request_json(session, "/api/v3/ticker/24hr")
    ranked: List[tuple[str, float]] = []
    for item in payload:
        symbol = item.get("symbol")
        if not symbol or not symbol.endswith(quote_asset):
            continue
        try:
            quote_volume = float(item.get("quoteVolume", 0.0))
        except (TypeError, ValueError):
            continue
        ranked.append((symbol, quote_volume))
    ranked.sort(key=lambda entry: entry[1], reverse=True)
    return [symbol for symbol, _ in ranked[:top_n]]


def fetch_kline(
    session: requests.Session,
    symbol: str,
    interval: str,
    *,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> Sequence[Any]:
    params: Dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": 1}
    if start_ms is not None:
        params["startTime"] = int(start_ms)
    if end_ms is not None:
        params["endTime"] = int(end_ms)
    data = _request_json(session, "/api/v3/klines", params=params)
    if not data:
        raise BinanceAPIError(
            f"No klines returned for {symbol} {interval} {start_ms} {end_ms}"
        )
    time.sleep(REQUEST_PAUSE_SECONDS)
    return data[0]


def fetch_first_last_kline(
    session: requests.Session,
    symbol: str,
    interval: str,
    *,
    start_ms: int,
    end_ms: int,
) -> tuple[Sequence[Any], Sequence[Any]]:
    first = fetch_kline(session, symbol, interval, start_ms=start_ms)
    last = fetch_kline(session, symbol, interval, end_ms=end_ms)
    return first, last
