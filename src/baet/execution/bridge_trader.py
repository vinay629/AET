"""Bridge trader for multi-coin trading via a bridge currency.

Inspired by: https://github.com/ccxt/binance-trade-bot

Enables trading between any two coins using a bridge currency (e.g., USDT):
  Coin A → USDT → Coin B

This allows trading any coin pair even when a direct market doesn't exist.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from baet.database.manager import DatabaseManager
from baet.database.models import Coin, TradeState

logger = logging.getLogger(__name__)


@dataclass
class BridgeTrade:
    """Represents a bridge trade: from_coin → bridge → to_coin."""
    from_coin: str
    to_coin: str
    bridge: str
    from_amount: float
    bridge_amount: float
    to_amount: float
    fee_paid: float
    fee_coin: str


@dataclass
class OrderResult:
    """Result of an order attempt."""
    success: bool
    order_id: Optional[int] = None
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    filled_quantity: float = 0.0
    fee: float = 0.0
    error: str = ""


class BridgeTrader:
    """
    Executes trades between coins using a bridge currency.

    Trading flow:
    1. Sell from_coin for bridge currency (e.g., BTC → USDT)
    2. Buy to_coin with bridge currency (e.g., USDT → ETH)

    Includes BNB fee discount detection and order timeout handling.
    """

    def __init__(
        self,
        client,  # Binance client
        db: DatabaseManager,
        bridge_symbol: str = "USDT",
        buy_timeout: int = 0,  # 0 = no timeout
        sell_timeout: int = 0,
        use_bnb_for_fees: bool = True,
    ):
        self.client = client
        self.db = db
        self.bridge_symbol = bridge_symbol
        self.buy_timeout = buy_timeout
        self.sell_timeout = sell_timeout
        self.use_bnb_for_fees = use_bnb_for_fees

        # Cache for symbol info
        self._symbol_info: Dict[str, dict] = {}
        self._trade_fees: Dict[str, float] = {}

    def get_trade_fee(self, symbol: str) -> float:
        """Get the trade fee for a symbol, applying BNB discount if available."""
        if symbol not in self._trade_fees:
            try:
                fees = self.client.get_trade_fee(symbol=symbol)
                if fees:
                    self._trade_fees[symbol] = float(fees[0]["takerCommission"])
                else:
                    self._trade_fees[symbol] = 0.001  # Default 0.1%
            except Exception:
                self._trade_fees[symbol] = 0.001

        base_fee = self._trade_fees[symbol]

        # Apply BNB discount if enabled
        if self.use_bnb_for_fees and self._has_bnb_discount():
            return base_fee * 0.75

        return base_fee

    def _has_bnb_discount(self) -> bool:
        """Check if BNB fee discount is enabled and BNB balance is sufficient."""
        try:
            bnb_burn = self.client.get_bnb_burn_spot_margin()
            return bnb_burn.get("spotBNBBurn", False)
        except Exception:
            return False

    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """Get symbol trading rules (cached)."""
        if symbol not in self._symbol_info:
            try:
                info = self.client.get_symbol_info(symbol)
                if info:
                    self._symbol_info[symbol] = info
            except Exception as e:
                logger.error(f"Failed to get symbol info for {symbol}: {e}")
                return None
        return self._symbol_info.get(symbol)

    def get_tick_size(self, symbol: str) -> int:
        """Get the number of decimal places for quantity."""
        info = self.get_symbol_info(symbol)
        if info is None:
            return 8

        for f in info.get("filters", []):
            if f["filterType"] == "LOT_SIZE":
                step = f["stepSize"]
                if step.find("1") == 0:
                    return 1 - step.find(".")
                return step.find("1") - 1
        return 8

    def get_min_notional(self, symbol: str) -> float:
        """Get the minimum notional value for a trade."""
        info = self.get_symbol_info(symbol)
        if info is None:
            return 10.0  # Default $10

        for f in info.get("filters", []):
            if f["filterType"] == "NOTIONAL":
                return float(f["minNotional"])
        return 10.0

    def get_balance(self, symbol: str) -> float:
        """Get the available balance for a coin."""
        try:
            account = self.client.get_account()
            for balance in account.get("balances", []):
                if balance["asset"] == symbol:
                    return float(balance["free"])
        except Exception as e:
            logger.error(f"Failed to get balance for {symbol}: {e}")
        return 0.0

    def get_price(self, symbol: str) -> Optional[float]:
        """Get the current price of a symbol."""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    def execute_bridge_trade(
        self,
        from_coin: Coin,
        to_coin: Coin,
        from_amount: Optional[float] = None,
    ) -> Optional[BridgeTrade]:
        """
        Execute a bridge trade: from_coin → bridge → to_coin.

        Args:
            from_coin: The coin to sell
            to_coin: The coin to buy
            from_amount: Amount to sell (None = sell all available)

        Returns:
            BridgeTrade if successful, None otherwise
        """
        from_symbol = from_coin.symbol
        to_symbol = to_coin.symbol
        bridge = self.bridge_symbol

        logger.info(f"Bridge trade: {from_symbol} → {bridge} → {to_symbol}")

        # Step 1: Sell from_coin for bridge currency
        sell_symbol = from_symbol + bridge
        sell_amount = from_amount or self.get_balance(from_symbol)

        if sell_amount <= 0:
            logger.warning(f"No {from_symbol} balance to sell")
            return None

        sell_result = self._execute_sell(sell_symbol, sell_amount)
        if not sell_result.success:
            logger.error(f"Sell failed: {sell_result.error}")
            return None

        bridge_amount = sell_result.filled_quantity * sell_result.price
        logger.info(f"Sold {sell_amount} {from_symbol} for {bridge_amount} {bridge}")

        # Step 2: Buy to_coin with bridge currency
        buy_symbol = to_symbol + bridge
        buy_result = self._execute_buy(buy_symbol, bridge_amount)

        if not buy_result.success:
            logger.error(f"Buy failed: {buy_result.error}")
            return None

        to_amount = buy_result.filled_quantity
        logger.info(f"Bought {to_amount} {to_symbol}")

        return BridgeTrade(
            from_coin=from_symbol,
            to_coin=to_symbol,
            bridge=bridge,
            from_amount=sell_amount,
            bridge_amount=bridge_amount,
            to_amount=to_amount,
            fee_paid=sell_result.fee + buy_result.fee,
            fee_coin=bridge,
        )

    def _execute_sell(self, symbol: str, amount: float) -> OrderResult:
        """Execute a sell order with retry and timeout logic."""
        return self._execute_order(symbol, "SELL", amount)

    def _execute_buy(self, symbol: str, bridge_amount: float) -> OrderResult:
        """Execute a buy order with retry and timeout logic."""
        price = self.get_price(symbol)
        if price is None or price == 0:
            return OrderResult(success=False, error="Failed to get price")

        # Calculate quantity from bridge amount
        quantity = bridge_amount / price
        return self._execute_order(symbol, "BUY", quantity)

    def _execute_order(
        self, symbol: str, side: str, quantity: float
    ) -> OrderResult:
        """
        Execute an order with retry logic.

        Uses limit orders for better price control.
        """
        max_retries = 20
        tick_size = self.get_tick_size(symbol)

        # Round quantity to tick size
        quantity = math.floor(quantity * 10**tick_size) / float(10**tick_size)

        # Check minimum notional
        price = self.get_price(symbol)
        if price is not None:
            notional = quantity * price
            min_notional = self.get_min_notional(symbol)
            if notional < min_notional:
                # Adjust quantity to meet minimum
                quantity = (min_notional / price) * 1.01  # Add 1% buffer
                quantity = math.floor(quantity * 10**tick_size) / float(10**tick_size)

        for attempt in range(max_retries):
            try:
                if side == "SELL":
                    order = self.client.order_limit_sell(
                        symbol=symbol,
                        quantity=quantity,
                        price=price,
                    )
                else:
                    order = self.client.order_limit_buy(
                        symbol=symbol,
                        quantity=quantity,
                        price=price,
                    )

                order_id = int(order["orderId"])

                # Wait for fill
                filled_order = self._wait_for_order(order_id, symbol, side)

                if filled_order is not None:
                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=float(filled_order.get("price", price)),
                        filled_quantity=float(
                            filled_order.get("executedQty", quantity)
                        ),
                        fee=float(filled_order.get("commission", 0)),
                    )

            except Exception as e:
                logger.warning(
                    f"Order attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                time.sleep(1)

        return OrderResult(
            success=False,
            symbol=symbol,
            side=side,
            quantity=quantity,
            error=f"Failed after {max_retries} attempts",
        )

    def _wait_for_order(
        self, order_id: int, symbol: str, side: str
    ) -> Optional[dict]:
        """Wait for an order to be filled, with timeout handling."""
        timeout = self.sell_timeout if side == "SELL" else self.buy_timeout
        start_time = time.time()

        while True:
            try:
                order = self.client.get_order(symbol=symbol, orderId=order_id)
                status = order.get("status", "")

                if status == "FILLED":
                    return order

                if status == "CANCELED":
                    logger.info(f"Order {order_id} was canceled")
                    return None

                if status == "PARTIALLY_FILLED" and side == "SELL":
                    # For sell orders, cancel and sell partially filled amount
                    if timeout and (time.time() - start_time) / 60 > timeout:
                        self.client.cancel_order(symbol=symbol, orderId=order_id)
                        return order

                # Check timeout for unfilled orders
                if timeout and (time.time() - start_time) / 60 > timeout:
                    if status == "NEW":
                        self.client.cancel_order(symbol=symbol, orderId=order_id)
                        logger.info(f"Order {order_id} timed out and was canceled")
                        return None

                time.sleep(1)

            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                time.sleep(1)
