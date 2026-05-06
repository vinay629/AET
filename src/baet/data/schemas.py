from dataclasses import dataclass

CANONICAL_CANDLE_COLUMNS = [
    "symbol",
    "timeframe",
    "open_time",
    "close_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "source",
]


@dataclass(frozen=True)
class CandleSchema:
    symbol: str
    timeframe: str
    source: str
