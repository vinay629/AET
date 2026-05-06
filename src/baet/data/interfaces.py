from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class HistoricalDataProvider(ABC):
    @abstractmethod
    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """Fetch normalized candle data for a symbol/timeframe range."""


class MarketDataStore(ABC):
    @abstractmethod
    def write_raw_candles(self, frame: pd.DataFrame, symbol: str, timeframe: str) -> None:
        """Persist normalized raw candles."""

    @abstractmethod
    def read_raw_candles(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Read persisted raw candles."""

    @abstractmethod
    def write_features(self, frame: pd.DataFrame, symbol: str, timeframe: str) -> None:
        """Persist processed feature data."""

    @abstractmethod
    def read_features(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Read persisted features."""

    @abstractmethod
    def write_backtest_artifacts(
        self,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        symbol_returns: pd.DataFrame,
        metrics: pd.DataFrame,
        run_name: str,
    ) -> None:
        """Persist backtest outputs."""


class FeatureBuilder(ABC):
    @abstractmethod
    def build(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Build deterministic features from normalized candles."""


class BacktestEngine(ABC):
    @abstractmethod
    def run(
        self,
        market_frames: dict[tuple[str, str], pd.DataFrame],
        signals: dict[tuple[str, str], pd.DataFrame],
        run_name: str,
    ) -> object:
        """Run a portfolio-aware backtest."""
