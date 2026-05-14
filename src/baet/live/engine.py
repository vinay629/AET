"""Live trading engine for BAET."""

import logging
from datetime import datetime
from typing import Any, Optional

from baet.config.models import Settings
from baet.live.execution import LiveExecutionClient

logger = logging.getLogger(__name__)


class LiveTradingEngine:
    """Engine for live trading with safety controls."""

    def __init__(
        self,
        config: Settings,
        execution_client: Optional[LiveExecutionClient] = None,
    ):
        """
        Initialize live trading engine.

        Args:
            config: BAET settings
            execution_client: Pre-configured execution client (optional)
        """
        self.config = config
        self.running = False
        self.start_time: Optional[datetime] = None
        self.daily_trade_count = 0

        # Initialize execution client
        if execution_client:
            self.client = execution_client
        else:
            # Create from config
            from baet.config.models import SecretsConfig

            secrets = SecretsConfig()  # Loads from env

            if config.live.require_explicit_confirmation:
                logger.warning("Live trading requires explicit confirmation!")
                self.client = None
                return

            if not secrets.live_binance_api_key or not secrets.live_binance_api_secret:
                logger.error("Live API credentials not found!")
                self.client = None
                return

            self.client = LiveExecutionClient(
                api_key=secrets.live_binance_api_key,
                api_secret=secrets.live_binance_api_secret,
                testnet=True,  # Always start with testnet
                simulation=config.live.simulation_mode,
            )

    def start(self) -> bool:
        """Start live trading engine.

        Returns:
            True if started successfully
        """
        if not self.client:
            logger.error("Execution client not initialized")
            return False

        if not self.config.live.enabled:
            logger.error("Live trading not enabled in config")
            return False

        try:
            # Validation: Check account access
            account = self.client.get_account_info()
            logger.info(f"Account accessible: {account.get('accountType', 'Unknown')}")

            # Check USDT balance
            balance = self.client.get_balance("USDT")
            logger.info(f"USDT Balance: ${balance:.2f}")

            if balance < self.config.live.safety.min_order_size:
                logger.error(f"Insufficient balance: ${balance:.2f}")
                return False

            self.running = True
            self.start_time = datetime.now()
            self.daily_trade_count = 0

            logger.info("Live trading engine STARTED")
            return True

        except Exception as e:
            logger.error(f"Failed to start live trading: {e}")
            return False

    def stop(self):
        """Stop live trading engine."""
        self.running = False
        if self.client:
            self.client.close()
        logger.info("Live trading engine STOPPED")

    def execute_signal(self, symbol: str, signal: dict[str, Any]) -> dict[str, Any]:
        """Execute a trading signal.

        Args:
            symbol: Trading pair
            signal: Signal dictionary (side, confidence, etc.)

        Returns:
            Execution result dictionary
        """
        if not self.running:
            raise RuntimeError("Engine not running")

        if not self.client:
            raise RuntimeError("Execution client not initialized")

        side = signal.get("signal", "HOLD")
        if side == "HOLD":
            logger.debug("HOLD signal - no execution")
            return {"executed": False, "reason": "HOLD signal"}

        # Check daily trade limit
        safety = self.config.live.safety
        max_daily = (
            safety.get("max_daily_trades", 5)
            if isinstance(safety, dict)
            else safety.max_daily_trades
        )

        if self.daily_trade_count >= max_daily:
            logger.warning(f"Daily trade limit reached: {self.daily_trade_count}")
            return {"executed": False, "reason": "Daily trade limit reached"}

        # Calculate quantity (simplified)
        quantity = signal.get("units", 0.001)  # Small default

        # Safety: Check max position value
        max_value = (
            safety.get("max_position_value", 100.0)
            if isinstance(safety, dict)
            else safety.max_position_value
        )

        if quantity * signal.get("price", 0) > max_value:
            logger.warning(f"Position value exceeds limit: ${max_value}")
            return {"executed": False, "reason": "Position value limit"}

        try:
            if side == "BUY":
                result = self.client.place_market_buy(symbol, quantity)
            elif side == "SELL":
                result = self.client.place_market_sell(symbol, quantity)
            else:
                return {"executed": False, "reason": f"Unknown signal: {side}"}

            self.daily_trade_count += 1
            logger.info(f"Executed {side} for {symbol}: {result}")

            return {
                "executed": True,
                "side": side,
                "symbol": symbol,
                "quantity": quantity,
                "result": result,
            }

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {"executed": False, "error": str(e)}

    def get_status(self) -> dict[str, Any]:
        """Get current engine status."""
        return {
            "running": self.running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "daily_trades": self.daily_trade_count,
            "simulation": self.client.simulation if self.client else True,
            "testnet": self.client.testnet if self.client else True,
        }
