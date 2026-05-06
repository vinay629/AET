"""Strategy interfaces and implementations."""

from baet.strategies.adapters import adapt_order_intent_to_backtest_signals
from baet.strategies.baselines import (
    BuyAndHoldStrategy,
    SmaCrossoverStrategy,
    build_buy_and_hold_signals,
    build_sma_crossover_signals,
)
from baet.strategies.contracts import SIGNAL_COLUMNS, StrategyContract
from baet.strategies.discovery import discover_strategies, filter_supported_strategies

__all__ = [
    "SIGNAL_COLUMNS",
    "StrategyContract",
    "BuyAndHoldStrategy",
    "SmaCrossoverStrategy",
    "adapt_order_intent_to_backtest_signals",
    "build_buy_and_hold_signals",
    "build_sma_crossover_signals",
    "discover_strategies",
    "filter_supported_strategies",
]
