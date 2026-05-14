"""WebSocket streaming module for real-time market data.

Inspired by: https://github.com/ccxt/binance-trade-bot

Provides WebSocket-based price streaming and order status updates
as an alternative to REST API polling.
"""

from baet.streaming.manager import StreamManager

__all__ = ["StreamManager"]
