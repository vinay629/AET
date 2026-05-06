from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from baet.config.models import Settings
from baet.data.interfaces import HistoricalDataProvider
from baet.data.schemas import CANONICAL_CANDLE_COLUMNS

_BINANCE_KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trade_count",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]


def _to_millis(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def normalize_klines(
    payload: list[list[object]],
    symbol: str,
    timeframe: str,
    source: str,
) -> pd.DataFrame:
    frame = pd.DataFrame(payload, columns=_BINANCE_KLINE_COLUMNS)
    if frame.empty:
        normalized = pd.DataFrame(columns=CANONICAL_CANDLE_COLUMNS)
        return normalized

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ]
    frame[numeric_columns] = frame[numeric_columns].astype("float64")
    frame["trade_count"] = frame["trade_count"].astype("int64")
    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
    frame["symbol"] = symbol
    frame["timeframe"] = timeframe
    frame["source"] = source
    normalized = frame[CANONICAL_CANDLE_COLUMNS].copy()
    return normalized.sort_values("open_time").reset_index(drop=True)


class BinanceHistoricalProvider(HistoricalDataProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        query = urlencode(
            {
                "symbol": symbol,
                "interval": timeframe,
                "startTime": _to_millis(start_time),
                "endTime": _to_millis(end_time),
                "limit": self.settings.binance.historical_limit,
            }
        )
        url = f"{self.settings.binance.rest_base_url}/api/v3/klines?{query}"
        with urlopen(url, timeout=self.settings.binance.request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return normalize_klines(payload, symbol=symbol, timeframe=timeframe, source="binance_rest")


class BinanceLiveStream:
    def __init__(self, settings: Settings, symbol: str, timeframe: str) -> None:
        self.settings = settings
        self.symbol = symbol.lower()
        self.timeframe = timeframe

    @property
    def stream_name(self) -> str:
        return f"{self.symbol}@kline_{self.timeframe}"

    @property
    def stream_url(self) -> str:
        return f"{self.settings.binance.websocket_base_url}/{self.stream_name}"
