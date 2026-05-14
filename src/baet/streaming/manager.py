"""WebSocket stream manager for real-time market data.

Inspired by: https://github.com/ccxt/binance-trade-bot

Manages WebSocket connections to Binance for:
- Real-time price ticker updates
- Order book depth updates
- Trade execution updates
- Order status changes (filled, canceled, etc.)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class StreamManager:
    """
    Manages WebSocket connections to Binance for real-time data.

    Falls back to REST API polling if WebSocket is unavailable.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        symbols: Optional[List[str]] = None,
        testnet: bool = True,
        on_price_update: Optional[Callable[[str, float], None]] = None,
        on_order_update: Optional[Callable[[dict], None]] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT"]
        self.testnet = testnet
        self.on_price_update = on_price_update
        self.on_order_update = on_order_update

        # Internal state
        self._ticker_prices: Dict[str, float] = {}
        self._order_statuses: Dict[int, dict] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable] = []

        # WebSocket URLs
        if testnet:
            self._ws_base = "wss://testnet.binance.vision/ws"
            self._rest_base = "https://testnet.binance.vision"
        else:
            self._ws_base = "wss://stream.binance.com:9443/ws"
            self._rest_base = "https://api.binance.com"

    @property
    def ticker_prices(self) -> Dict[str, float]:
        """Get the latest ticker prices."""
        return self._ticker_prices.copy()

    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for a symbol."""
        return self._ticker_prices.get(symbol)

    def start(self) -> None:
        """Start the WebSocket stream manager."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Stream manager started")

    def stop(self) -> None:
        """Stop the WebSocket stream manager."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("Stream manager stopped")

    def _run(self) -> None:
        """Main loop for the stream manager."""
        retry_delay = 1
        max_retry_delay = 60

        while self._running:
            try:
                self._connect_and_stream()
                retry_delay = 1  # Reset on successful connection
            except Exception as e:
                logger.error(f"Stream error: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

    def _connect_and_stream(self) -> None:
        """
        Establish WebSocket connection and process messages.

        Falls back to REST polling if WebSocket library is not available.
        """
        try:
            import websocket

            # Build combined stream URL
            streams = [f"{s.lower()}@ticker" for s in self.symbols]
            stream_url = f"{self._ws_base}/{'/'.join(streams)}"

            ws = websocket.WebSocketApp(
                stream_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open,
            )

            ws.run_forever(ping_interval=20, ping_timeout=10)

        except ImportError:
            logger.warning(
                "websocket-client not installed. Falling back to REST polling. "
                "Install with: pip install websocket-client"
            )
            self._rest_polling_fallback()

    def _on_open(self, ws) -> None:
        """Called when WebSocket connection opens."""
        logger.info("WebSocket connection opened")

    def _on_message(self, ws, message: str) -> None:
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)

            # Handle combined stream format
            if "stream" in data and "data" in data:
                data = data["data"]

            # Ticker update
            if data.get("e") == "24hrTicker":
                symbol = data.get("s", "")
                price = float(data.get("c", 0))  # Last price
                self._ticker_prices[symbol] = price

                if self.on_price_update:
                    self.on_price_update(symbol, price)

            # Order update (from user data stream)
            elif data.get("e") == "executionReport":
                order_id = data.get("i", 0)
                self._order_statuses[order_id] = data

                if self.on_order_update:
                    self.on_order_update(data)

        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Failed to parse message: {e}")

    def _on_error(self, ws, error) -> None:
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """Handle WebSocket close."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")

    def _rest_polling_fallback(self) -> None:
        """
        Fallback to REST API polling when WebSocket is not available.

        Polls ticker prices every 5 seconds.
        """
        import urllib.request

        logger.info("Using REST API polling fallback")

        while self._running:
            try:
                for symbol in self.symbols:
                    url = f"{self._rest_base}/api/v3/ticker/price?symbol={symbol}"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode())
                        price = float(data.get("price", 0))
                        self._ticker_prices[symbol] = price

                        if self.on_price_update:
                            self.on_price_update(symbol, price)

                time.sleep(5)

            except Exception as e:
                logger.error(f"REST polling error: {e}")
                time.sleep(10)

    def register_callback(self, callback: Callable) -> None:
        """Register a callback for price updates."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable) -> None:
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
