"""Strategy interfaces and implementations."""

from baet.strategies.baselines import build_buy_and_hold_signals, build_sma_crossover_signals

__all__ = ["build_buy_and_hold_signals", "build_sma_crossover_signals"]
