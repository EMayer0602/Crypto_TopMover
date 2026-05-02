from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import requests

from config import (
    BINANCE_BASE_URL,
    MAX_RETRIES,
    RATE_LIMIT_BASE_SECONDS,
    RATE_LIMIT_JITTER_SECONDS,
    REQUEST_PAUSE_SECONDS,
    REQUEST_TIMEOUT,
)


class BinanceAPIError(RuntimeError):
    """Raised when Binance API requests fail, rate-limit, or return bans."""


def _request_json(
    session: requests.Session,
    path: str,
    params: Optional[dict[str, Any]] = None,
) -> Any:
    url = f"{BINANCE_BASE_URL}{path}"
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code == 418:
                raise BinanceAPIError("Binance API IP banned (418).")
            if response.status_code == 429:
                last_exc = BinanceAPIError("Binance API rate limit hit (429).")
                if attempt < MAX_RETRIES:
                    time.sleep(_backoff_delay(attempt))
                    continue
                break
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(_backoff_delay(attempt))
                continue
            break
    raise BinanceAPIError(f"Binance API request failed for {path}") from last_exc


def _backoff_delay(attempt: int) -> float:
    base = RATE_LIMIT_BASE_SECONDS * (2 ** (attempt - 1))
    jitter = random.uniform(0, RATE_LIMIT_JITTER_SECONDS)
    return base + jitter


def _ms_to_iso(value: Optional[int]) -> str:
    if value is None:
        return "n/a"
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def get_top_symbols_by_quote_volume(
    session: requests.Session,
    quote_asset: str,
    top_n: int,
) -> list[str]:
    payload = _request_json(session, "/api/v3/ticker/24hr")
    ranked: list[tuple[str, float]] = []
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
    params: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": 1}
    if start_ms is not None:
        params["startTime"] = int(start_ms)
    if end_ms is not None:
        params["endTime"] = int(end_ms)
    data = _request_json(session, "/api/v3/klines", params=params)
    if not data:
        raise BinanceAPIError(
            "No klines returned for "
            f"{symbol} {interval} start={_ms_to_iso(start_ms)} end={_ms_to_iso(end_ms)}"
        )
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
    time.sleep(REQUEST_PAUSE_SECONDS)
    last = fetch_kline(session, symbol, interval, end_ms=end_ms)
    time.sleep(REQUEST_PAUSE_SECONDS)
    return first, last
