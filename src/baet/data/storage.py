from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from baet.config.models import Settings
from baet.data.interfaces import MarketDataStore


class ParquetMarketDataStore(MarketDataStore):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.raw_root = settings.storage.raw_data_dir
        self.processed_root = settings.storage.processed_data_dir
        self.backtests_root = settings.reporting.backtests_dir

    def _symbol_timeframe_dir(self, root: Path, symbol: str, timeframe: str) -> Path:
        return root / symbol / timeframe

    def _ensure_parent(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def write_raw_candles(self, frame: pd.DataFrame, symbol: str, timeframe: str) -> None:
        path = self._symbol_timeframe_dir(self.raw_root, symbol, timeframe) / "candles.parquet"
        self._ensure_parent(path)
        frame.to_parquet(path, index=False)

    def read_raw_candles(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = self._symbol_timeframe_dir(self.raw_root, symbol, timeframe) / "candles.parquet"
        return pd.read_parquet(path)

    def write_features(self, frame: pd.DataFrame, symbol: str, timeframe: str) -> None:
        path = (
            self._symbol_timeframe_dir(self.processed_root, symbol, timeframe) / "features.parquet"
        )
        self._ensure_parent(path)
        frame.to_parquet(path, index=False)

    def read_features(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = (
            self._symbol_timeframe_dir(self.processed_root, symbol, timeframe) / "features.parquet"
        )
        return pd.read_parquet(path)

    def write_backtest_artifacts(
        self,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        symbol_returns: pd.DataFrame,
        metrics: pd.DataFrame,
        run_name: str,
    ) -> None:
        root = self.backtests_root / run_name
        root.mkdir(parents=True, exist_ok=True)
        equity_curve.to_parquet(root / "equity_curve.parquet", index=False)
        trades.to_parquet(root / "trades.parquet", index=False)
        symbol_returns.to_parquet(root / "symbol_returns.parquet", index=False)
        metrics.to_parquet(root / "metrics.parquet", index=False)

    def write_metadata(self, metadata: dict[str, object], run_name: str) -> None:
        root = self.backtests_root / run_name
        root.mkdir(parents=True, exist_ok=True)
        (root / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
