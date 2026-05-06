"""Execution adapters for paper and live modes."""

# Lazy import to avoid circular imports
def __getattr__(name):
    if name == "PortfolioBacktestEngine":
        from baet.execution.backtest import PortfolioBacktestEngine
        return PortfolioBacktestEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["PortfolioBacktestEngine"]
