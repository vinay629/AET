from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from baet.config.models import Settings
from baet.data.binance import BinanceHistoricalProvider
from baet.data.storage import ParquetMarketDataStore
from baet.data.validation import validate_candles


class DataIngester:
    """Thin CLI-facing ingestion wrapper built on the Stage 1 data stack."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = BinanceHistoricalProvider(settings)
        self.store = ParquetMarketDataStore(settings)

    def fetch_historical(self, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=days)
        candles = self.provider.fetch_klines(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
        )
        return validate_candles(candles, timeframe)

    def save_raw(self, frame: pd.DataFrame, symbol: str, timeframe: str) -> Path:
        self.store.write_raw_candles(frame, symbol, timeframe)
        return self.store.raw_root / symbol / timeframe / "candles.parquet"
