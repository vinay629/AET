"""Order simulation for paper trading."""

from __future__ import annotations

from typing import Any, Tuple


class PaperOrderSimulator:
    """
    Simulates order execution with realistic assumptions.

    Applies slippage and fees to simulate real-world trading conditions.
    """

    def __init__(
        self,
        fee_rate: float = 0.001,  # 0.1% default fee
        slippage_rate: float = 0.0005,  # 0.05% default slippage
        logger: Any = None,
    ):
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.logger = logger

    def simulate_buy(
        self,
        price: float,
        units: float,
    ) -> Tuple[float, float, float]:
        """
        Simulate a buy order.

        Args:
            price: Requested buy price
            units: Number of units to buy

        Returns:
            Tuple of (fill_price, units_received, fee)
        """
        fill_price = price * (1.0 + self.slippage_rate)
        fee = units * fill_price * self.fee_rate

        # Log simulation if logger available
        if self.logger:
            self.logger.log_order_simulated(
                symbol="unknown",  # Symbol not known at this level
                side="BUY",
                requested_price=price,
                filled_price=fill_price,
                units=units,
                fee=fee,
                slippage=fill_price - price,
            )

        return fill_price, units, fee

    def simulate_sell(
        self,
        price: float,
        units: float,
    ) -> Tuple[float, float, float]:
        """
        Simulate a sell order.

        Args:
            price: Requested sell price
            units: Number of units to sell

        Returns:
            Tuple of (fill_price, proceeds, fee)
        """
        fill_price = price * (1.0 - self.slippage_rate)
        gross = units * fill_price
        fee = gross * self.fee_rate

        # Log simulation if logger available
        if self.logger:
            self.logger.log_order_simulated(
                symbol="unknown",  # Symbol not known at this level
                side="SELL",
                requested_price=price,
                filled_price=fill_price,
                units=units,
                fee=fee,
                slippage=price - fill_price,  # Sell slippage is negative
            )

        return fill_price, gross - fee, fee

    def calculate_fee(self, amount: float) -> float:
        """Calculate fee for a given amount."""
        return amount * self.fee_rate

    def calculate_slippage(self, price: float, side: str) -> float:
        """
        Calculate slippage amount for a given price and side.

        Args:
            price: Base price
            side: 'BUY' or 'SELL'

        Returns:
            Adjusted price after slippage
        """
        if side.upper() == "BUY":
            return price * (1.0 + self.slippage_rate)
        else:  # SELL
            return price * (1.0 - self.slippage_rate)
