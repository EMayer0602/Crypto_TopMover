from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Config:
    # Market selection
    exchange: str = "binance"
    market_type: str = "spot"
    quote_asset: str = "USDC"
    top_n: int = 20

    # Candles
    timeframe: str = "1h"  # Binance kline interval

    # In-sample / Out-of-sample date ranges
    is_start: date = field(default_factory=lambda: date(2024, 1, 1))
    is_end: date = field(default_factory=lambda: date(2025, 9, 30))
    oos_start: date = field(default_factory=lambda: date(2025, 10, 1))
    # oos_end defaults to current date at runtime

    # Portfolio assumptions
    initial_capital: float = 10_000.0
    fee_rate: float = 0.001        # 0.10 % spot taker fee
    slippage_bps: float = 5.0      # 5 bps = 0.05 %

    # Strategy params
    top_movers_n: int = 5          # hold top N within the universe
    lookback_hours: int = 24       # momentum lookback
    rebalance_hour_utc: int = 0    # rebalance at 00:00 UTC each day
