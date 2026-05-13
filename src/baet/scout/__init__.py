"""Scout module for ratio-based multi-coin trading.

Inspired by: https://github.com/ccxt/binance-trade-bot

The scout algorithm tracks price ratios between coin pairs and identifies
trading opportunities when ratios diverge from historical norms.
"""

from baet.scout.engine import ScoutEngine

__all__ = ["ScoutEngine"]
