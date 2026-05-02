from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import List, Sequence

import pandas as pd
import requests

from config import INTERVALS, QUOTE_ASSET, START_DATE, TOP_N
from data_fetcher import fetch_first_last_kline, get_top_symbols_by_quote_volume


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def ms_to_iso(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def build_report(
    symbols: List[str],
    intervals: Sequence[str],
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    rows = []
    with requests.Session() as session:
        for interval in intervals:
            for symbol in symbols:
                first, last = fetch_first_last_kline(
                    session,
                    symbol,
                    interval,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
                first_open = float(first[1])
                last_close = float(last[4])
                status = "ok"
                if first_open <= 0 or last_close <= 0:
                    pnl_abs = float("nan")
                    pnl_pct = float("nan")
                    status = "invalid_price"
                else:
                    pnl_abs = last_close - first_open
                    pnl_pct = (pnl_abs / first_open) * 100
                rows.append(
                    {
                        "interval": interval,
                        "symbol": symbol,
                        "start_open": first_open,
                        "end_close": last_close,
                        "pnl_abs": pnl_abs,
                        "pnl_pct": pnl_pct,
                        "status": status,
                        "first_open_time": ms_to_iso(int(first[0])),
                        "last_close_time": ms_to_iso(int(last[6])),
                    }
                )
    frame = pd.DataFrame(rows)
    return frame.sort_values(["interval", "pnl_pct"], ascending=[True, False])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PnL report for top USDC pairs on Binance.",
    )
    parser.add_argument("--quote", default=QUOTE_ASSET, help="Quote asset symbol.")
    parser.add_argument("--top-n", type=int, default=TOP_N, help="Number of symbols.")
    parser.add_argument(
        "--start-date",
        default=START_DATE,
        help="ISO start date (UTC) for PnL calculation.",
    )
    parser.add_argument(
        "--intervals",
        default=",".join(INTERVALS),
        help="Comma-separated Binance intervals.",
    )
    parser.add_argument("--output", default=None, help="Output CSV path.")
    args = parser.parse_args()

    start_dt = parse_datetime(args.start_date)
    start_ms = int(start_dt.timestamp() * 1000)
    report_time = datetime.now(timezone.utc)
    end_ms = int(report_time.timestamp() * 1000)
    intervals = [interval.strip() for interval in args.intervals.split(",") if interval]

    with requests.Session() as session:
        symbols = get_top_symbols_by_quote_volume(session, args.quote, args.top_n)

    report = build_report(symbols, intervals, start_ms, end_ms)
    output_name = args.output or f"pnl_report_{report_time:%Y%m%d_%H%M%S}.csv"
    report.to_csv(output_name, index=False)

    print(f"Top {len(symbols)} {args.quote} pairs: {', '.join(symbols)}")
    print(f"Saved PnL report to {output_name}")


if __name__ == "__main__":
    main()
