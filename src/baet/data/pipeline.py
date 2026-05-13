from __future__ import annotations

from datetime import datetime

from baet.config.models import Settings
from baet.core.models import BacktestArtifacts
from baet.data.features import PandasFeatureBuilder
from baet.data.interfaces import HistoricalDataProvider, MarketDataStore
from baet.data.validation import validate_candles
from baet.strategies.baselines import build_buy_and_hold_signals


# Lazy imports to avoid circular imports
def _get_summaries():
    from baet.reporting import summaries
    return summaries


# Lazy import to avoid circular imports
def _get_portfolio_backtest_engine():
    from baet.execution.backtest import PortfolioBacktestEngine
    return PortfolioBacktestEngine


class ResearchPipeline:
    def __init__(
        self,
        settings: Settings,
        provider: HistoricalDataProvider,
        store: MarketDataStore,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.store = store
        self.feature_builder = PandasFeatureBuilder(settings.features)
        PortfolioBacktestEngine = _get_portfolio_backtest_engine()
        self.backtest_engine = PortfolioBacktestEngine(settings.backtest)

    def ingest_symbol_timeframe(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, object]:
        candles = self.provider.fetch_klines(symbol, timeframe, start_time, end_time)
        validated = validate_candles(candles, timeframe)
        self.store.write_raw_candles(validated, symbol, timeframe)
        summaries = _get_summaries()
        return {
            "ingestion": summaries.build_ingestion_summary(validated, symbol, timeframe),
            "quality": summaries.build_data_quality_summary(validated, timeframe),
        }

    def build_features(self, symbol: str, timeframe: str) -> dict[str, object]:
        candles = self.store.read_raw_candles(symbol, timeframe)
        features = self.feature_builder.build(candles)
        self.store.write_features(features, symbol, timeframe)
        summaries = _get_summaries()
        return summaries.build_feature_coverage_summary(features)

    def run_baseline_backtest(self, run_name: str) -> tuple[BacktestArtifacts, dict[str, object]]:
        market_frames = {}
        signals = {}
        for symbol in self.settings.market.symbols:
            for timeframe in self.settings.market.timeframes:
                features = self.store.read_features(symbol, timeframe)
                key = (symbol, timeframe)
                market_frames[key] = features
                signals[key] = build_buy_and_hold_signals(features)

        artifacts = self.backtest_engine.run(market_frames, signals, run_name=run_name)
        self.store.write_backtest_artifacts(
            artifacts.equity_curve,
            artifacts.trades,
            artifacts.symbol_returns,
            artifacts.metrics,
            run_name,
        )
        if hasattr(self.store, "write_metadata"):
            self.store.write_metadata(dict(artifacts.metadata), run_name)
        
        # Build summary without importing from reporting (avoid circular import)
        metric_map = {}
        if not artifacts.metrics.empty:
            metric_map = {
                str(row["metric"]): float(row["value"]) 
                for _, row in artifacts.metrics.iterrows()
            }
        metric_map["trade_count"] = int(len(artifacts.trades))
        return artifacts, metric_map
