from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from baet.config.models import Settings
from baet.data.interfaces import HistoricalDataProvider
from baet.data.schemas import (
    CANONICAL_CANDLE_COLUMNS,
    CANONICAL_DERIVATIVES_COLUMNS,
)

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
        self.session = None  # For future session-based requests

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

    def fetch_open_interest(
        self,
        symbol: str,
        period: str = "1h",
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch open interest history from Binance Futures API.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT").
            period: OI aggregation period ("5m", "15m", "1h", "4h", "1d").
            limit: Max records to return (default 500, max 2000).
            start_time: Optional start of range.
            end_time: Optional end of range.

        Returns:
            DataFrame with columns: symbol, timestamp, open_interest, source.
        """
        params: dict[str, object] = {
            "symbol": symbol,
            "period": period,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = _to_millis(start_time)
        if end_time is not None:
            params["endTime"] = _to_millis(end_time)

        query = urlencode(params)
        url = f"{self.settings.binance.futures_rest_base_url}/fapi/v1/openInterestHist?{query}"
        with urlopen(url, timeout=self.settings.binance.request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not payload:
            return pd.DataFrame(columns=["symbol", "timestamp", "open_interest", "source"])

        frame = pd.DataFrame(payload)
        frame["open_interest"] = frame["sumOpenInterest"].astype("float64")
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        frame["symbol"] = symbol
        frame["source"] = "binance_futures"
        return frame[["symbol", "timestamp", "open_interest", "source"]].sort_values(
            "timestamp"
        ).reset_index(drop=True)

    def fetch_funding_rate_history(
        self,
        symbol: str,
        limit: int = 1000,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch funding rate history from Binance Futures API.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT").
            limit: Max records to return (default 1000, max 1000).
            start_time: Optional start of range.
            end_time: Optional end of range.

        Returns:
            DataFrame with columns: symbol, timestamp, funding_rate, funding_time, source.
        """
        params: dict[str, object] = {
            "symbol": symbol,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = _to_millis(start_time)
        if end_time is not None:
            params["endTime"] = _to_millis(end_time)

        query = urlencode(params)
        url = f"{self.settings.binance.futures_rest_base_url}/fapi/v1/fundingRate?{query}"
        with urlopen(url, timeout=self.settings.binance.request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not payload:
            return pd.DataFrame(
                columns=["symbol", "timestamp", "funding_rate", "funding_time", "source"]
            )

        frame = pd.DataFrame(payload)
        frame["funding_rate"] = frame["fundingRate"].astype("float64")
        frame["funding_time"] = pd.to_datetime(frame["fundingTime"], unit="ms", utc=True)
        frame["timestamp"] = frame["funding_time"]
        frame["symbol"] = symbol
        frame["source"] = "binance_futures"
        return frame[
            ["symbol", "timestamp", "funding_rate", "funding_time", "source"]
        ].sort_values("timestamp").reset_index(drop=True)

    def fetch_liquidation_orders(
        self,
        symbol: str,
        limit: int = 1000,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> pd.DataFrame:
        """Fetch forced liquidation orders from Binance Futures API.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT").
            limit: Max records to return (default 1000, max 1000).
            start_time: Optional start of range.
            end_time: Optional end of range.

        Returns:
            DataFrame with liquidation details per order.
        """
        params: dict[str, object] = {
            "symbol": symbol,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = _to_millis(start_time)
        if end_time is not None:
            params["endTime"] = _to_millis(end_time)

        query = urlencode(params)
        url = f"{self.settings.binance.futures_rest_base_url}/fapi/v1/allForceOrders?{query}"
        with urlopen(url, timeout=self.settings.binance.request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if not payload:
            return pd.DataFrame(
                columns=[
                    "symbol", "timestamp", "side", "price", "qty", "last_fill_qty",
                    "order_status", "time_in_force", "source",
                ]
            )

        frame = pd.DataFrame(payload)
        frame["timestamp"] = pd.to_datetime(frame["time"], unit="ms", utc=True)
        frame["price"] = frame["price"].astype("float64")
        frame["qty"] = frame["qty"].astype("float64")
        frame["last_fill_qty"] = frame["lastFillQty"].astype("float64")
        frame["symbol"] = symbol
        frame["source"] = "binance_futures"
        return frame[
            [
                "symbol", "timestamp", "side", "price", "qty",
                "last_fill_qty", "order_status", "time_in_force", "source",
            ]
        ].sort_values("timestamp").reset_index(drop=True)

    def fetch_block_trades(
        self,
        symbol: str,
        from_id: int,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch historical block trades (New - May 2026)."""
        query = urlencode(
            {
                "symbol": symbol,
                "fromId": from_id,
                "limit": limit,
            }
        )
        url = f"{self.settings.binance.rest_base_url}/api/v3/historicalBlockTrades?{query}"
        with urlopen(url, timeout=self.settings.binance.request_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_reference_price(
        self,
        symbol: str,
    ) -> dict:
        """ "Fetch reference price (New - March 2026)."""
        query = urlencode({"symbol": symbol})
        url = f"{self.settings.binance.rest_base_url}/api/v3/referencePrice?{query}"
        with urlopen(url, timeout=self.settings.binance.request_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_execution_rules(
        self,
        symbol: str = None,
    ) -> dict:
        """ "Fetch price range execution rules (New - March 2026)."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        query = urlencode(params)
        url = f"{self.settings.binance.rest_base_url}/api/v3/executionRules?{query}"
        with urlopen(url, timeout=self.settings.binance.request_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


class BinanceLiveStream:
    def __init__(self, settings: Settings, symbol: str, timeframe: str) -> None:
        self.settings = settings
        self.symbol = symbol.lower()
        self.timeframe = timeframe
        self._on_shutdown_callback = None

    @property
    def stream_name(self) -> str:
        return f"{self.symbol}@kline_{self.timeframe}"

    @property
    def stream_url(self) -> str:
        return f"{self.settings.binance.websocket_base_url}/{self.stream_name}"

    def set_shutdown_callback(self, callback) -> None:
        """Set callback for serverShutdown event (New - May 2026)."""
        self._on_shutdown_callback = callback

    def handle_message(self, message: str) -> dict:
        """Handle incoming WebSocket messages including serverShutdown."""
        data = json.loads(message)

        # Handle serverShutdown event (New - May 2026)
        if isinstance(data, dict) and data.get("e") == "serverShutdown":
            if self._on_shutdown_callback:
                self._on_shutdown_callback(data)
            return {"event": "shutdown", "data": data}

        return data
