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

# ---------------------------------------------------------------------------
# Derivatives data schemas
# ---------------------------------------------------------------------------

CANONICAL_DERIVATIVES_COLUMNS = [
    "symbol",
    "timestamp",
    "open_interest",
    "open_interest_change",
    "funding_rate",
    "funding_time",
    "liquidation_long_qty",
    "liquidation_short_qty",
    "liquidation_total_qty",
    "mark_price",
    "index_price",
    "source",
]


@dataclass(frozen=True)
class CandleSchema:
    symbol: str
    timeframe: str
    source: str


@dataclass(frozen=True)
class DerivativesSchema:
    symbol: str
    source: str
