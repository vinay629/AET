"""Live execution module for BAET."""

import logging
from typing import Any, Optional

try:
    from binance.client import Client as BinanceClient
    from binance.exceptions import BinanceAPIException
    HAS_BINANCE = True
except ImportError:
    HAS_BINANCE = False
    BinanceClient = None
    BinanceAPIException = Exception

logger = logging.getLogger(__name__)


class LiveExecutionClient:
    """Client for executing live trades on Binance."""
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = True,
        simulation: bool = False,
    ):
        """
        Initialize live execution client.
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            testnet: Use testnet (validation mode)
            simulation: Simulate orders (don't actually submit)
        """
        self.testnet = testnet
        self.simulation = simulation
        
        if not HAS_BINANCE:
            raise ImportError(
                "python-binance not installed. "
                "Install with: pip install python-binance"
            )
        
        # Initialize Binance client
        if testnet:
            self.client = BinanceClient(api_key, api_secret, testnet=True)
            logger.info("Initialized in TESTNET mode")
        else:
            self.client = BinanceClient(api_key, api_secret)
            logger.warning("Initialized in LIVE mode - REAL MONEY AT RISK!")
        
        if simulation:
            logger.warning("SIMULATION mode - orders will NOT be submitted")
    
    def get_account_info(self) -> dict[str, Any]:
        """Get account information."""
        if not self.simulation:
            try:
                return self.client.get_account()
            except BinanceAPIException as e:
                logger.error(f"Failed to get account info: {e}")
                raise
        else:
            logger.info("SIMULATION: Would get account info")
            return {"simulation": True, "balances": []}
    
    def get_balance(self, asset: str = "USDT") -> float:
        """Get balance for a specific asset."""
        if self.simulation:
            logger.info(f"SIMULATION: Would get balance for {asset}")
            return 10000.0  # Fake balance
        
        try:
            account = self.get_account_info()
            for balance in account['balances']:
                if balance['asset'] == asset:
                    free = float(balance['free'])
                    locked = float(balance['locked'])
                    return free + locked
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0
    
    def place_market_buy(self, symbol: str, quantity: float) -> dict[str, Any]:
        """
        Place a market buy order.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            quantity: Quantity to buy
            
        Returns:
            Order response from Binance (or simulation result)
        """
        if self.simulation:
            logger.info(f"SIMULATION: Would BUY {quantity} {symbol} at market")
            return {
                "simulation": True,
                "side": "BUY",
                "symbol": symbol,
                "quantity": quantity,
                "price": 0.0,  # Unknown in simulation
            }
        
        try:
            logger.info(f"Placing MARKET BUY: {quantity} {symbol}")
            order = self.client.order_market_buy(
                symbol=symbol,
                quantity=quantity,
            )
            logger.info(f"Order placed: {order['orderId']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Failed to place buy order: {e}")
            raise
    
    def place_market_sell(self, symbol: str, quantity: float) -> dict[str, Any]:
        """Place a market sell order."""
        if self.simulation:
            logger.info(f"SIMULATION: Would SELL {quantity} {symbol} at market")
            return {
                "simulation": True,
                "side": "SELL",
                "symbol": symbol,
                "quantity": quantity,
            }
        
        try:
            logger.info(f"Placing MARKET SELL: {quantity} {symbol}")
            order = self.client.order_market_sell(
                symbol=symbol,
                quantity=quantity,
            )
            logger.info(f"Order placed: {order['orderId']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Failed to place sell order: {e}")
            raise
    
    def get_order_status(self, symbol: str, order_id: int) -> dict[str, Any]:
        """Check order status."""
        if self.simulation:
            return {"simulation": True, "status": "FILLED"}
        
        try:
            return self.client.get_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as e:
            logger.error(f"Failed to get order status: {e}")
            raise
    
    def close(self):
        """Close the client connection."""
        # Binance client doesn't need explicit closing
        logger.info("Live execution client closed")
