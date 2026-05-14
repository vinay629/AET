from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from baet.config.models import Settings
from baet.data.features import PandasFeatureBuilder
from baet.data.storage import ParquetMarketDataStore
from baet.execution.backtest import PortfolioBacktestEngine
from baet.reporting.comparison import build_strategy_metrics_row
from baet.strategies.contracts import StrategyContract
from baet.strategies.discovery import discover_strategies


class BacktestPipeline:
    """Thin CLI-facing backtest wrapper built on the Stage 1 research stack."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = ParquetMarketDataStore(settings)
        self.engine = PortfolioBacktestEngine(settings.backtest)
        self.feature_builder = PandasFeatureBuilder(settings.features)

    def run(
        self,
        strategy_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        symbols: list[str] | None = None,
    ) -> dict[str, float]:
        strategy = self._resolve_strategy(strategy_name)
        market_frames = self._load_market_frames(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )
        signals: dict[tuple[str, str], pd.DataFrame] = {}

        for key, market in market_frames.items():
            symbol, timeframe = key
            if strategy.supports(symbol, timeframe):
                signals[key] = strategy.generate_signals(market)

        if not signals:
            raise ValueError(f"Strategy {strategy_name} does not support the available market data")

        artifacts = self.engine.run_order_intent(
            market_frames=market_frames,
            signals=signals,
            run_name=f"cli_{strategy.metadata.name}",
        )
        metrics = build_strategy_metrics_row(strategy.metadata.name, strategy.metadata, artifacts)
        return {
            "total_return": self._metric_as_float(metrics, "total_return"),
            "sharpe_ratio": self._metric_as_float(metrics, "sharpe_ratio"),
            "max_drawdown": self._metric_as_float(metrics, "max_drawdown"),
            "total_trades": self._metric_as_float(metrics, "trade_count"),
            "win_rate": self._metric_as_float(metrics, "win_rate"),
        }

    def _resolve_strategy(self, strategy_name: str) -> StrategyContract:
        for strategy in discover_strategies():
            if strategy.metadata.name == strategy_name:
                return strategy
        raise ValueError(f"Unknown strategy: {strategy_name}")

    def _load_market_frames(
        self,
        symbols: list[str] | None,
        start_date: str | None,
        end_date: str | None,
    ) -> dict[tuple[str, str], pd.DataFrame]:
        selected_symbols = symbols or self.settings.market.symbols
        start_ts = self._parse_date(start_date)
        end_ts = self._parse_date(end_date, end_of_day=True)

        market_frames: dict[tuple[str, str], pd.DataFrame] = {}
        for symbol in selected_symbols:
            for timeframe in self.settings.market.timeframes:
                frame = self._load_or_build_features(symbol, timeframe)
                filtered = frame
                if start_ts is not None:
                    filtered = filtered[filtered["close_time"] >= start_ts]
                if end_ts is not None:
                    filtered = filtered[filtered["close_time"] <= end_ts]
                filtered = filtered.reset_index(drop=True)
                if not filtered.empty:
                    market_frames[(symbol, timeframe)] = filtered

        if not market_frames:
            raise ValueError("No stored market data available for the requested backtest")
        return market_frames

    def _load_or_build_features(self, symbol: str, timeframe: str) -> pd.DataFrame:
        try:
            return self.store.read_features(symbol, timeframe)
        except FileNotFoundError:
            candles = self.store.read_raw_candles(symbol, timeframe)
            features = self.feature_builder.build(candles)
            self.store.write_features(features, symbol, timeframe)
            return features

    def _parse_date(self, value: str | None, end_of_day: bool = False) -> pd.Timestamp | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        if end_of_day:
            parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
        return pd.Timestamp(parsed)

    def _metric_as_float(self, metrics: dict[str, object], key: str) -> float:
        value = metrics.get(key, 0.0)
        if isinstance(value, int | float):
            return float(value)
        return 0.0
