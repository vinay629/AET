"""Strategy interfaces and implementations."""

from baet.strategies.adapters import adapt_order_intent_to_backtest_signals
from baet.strategies.adaptive_ensemble import AdaptiveEnsemble, PerformanceTracker
from baet.strategies.baselines import (
    AdxTrendFilterStrategy,
    BollingerBandsStrategy,
    BreakoutMomentumStrategy,
    BuyAndHoldStrategy,
    EmaCrossoverStrategy,
    RsiMeanReversionStrategy,
    SmaCrossoverStrategy,
    build_buy_and_hold_signals,
    build_sma_crossover_signals,
)
from baet.strategies.contracts import SIGNAL_COLUMNS, StrategyContract
from baet.strategies.discovery import discover_strategies, filter_supported_strategies
from baet.strategies.ensemble import EnsembleConfig, StaticEnsemble, StrategyWeight
from baet.strategies.ml_strategy import MLRandomForestStrategy
from baet.strategies.regime import RegimeDetector, VolatilityTrendRegimeDetector

__all__ = [
    "SIGNAL_COLUMNS",
    "StrategyContract",
    "BuyAndHoldStrategy",
    "SmaCrossoverStrategy",
    "RsiMeanReversionStrategy",
    "BollingerBandsStrategy",
    "EmaCrossoverStrategy",
    "BreakoutMomentumStrategy",
    "AdxTrendFilterStrategy",
    "adapt_order_intent_to_backtest_signals",
    "build_buy_and_hold_signals",
    "build_sma_crossover_signals",
    "discover_strategies",
    "filter_supported_strategies",
    "RegimeDetector",
    "VolatilityTrendRegimeDetector",
    "EnsembleConfig",
    "StaticEnsemble",
    "StrategyWeight",
    "AdaptiveEnsemble",
    "PerformanceTracker",
    "MLRandomForestStrategy",
]
