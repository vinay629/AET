"""Paper trading portfolio state management."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class PaperPortfolio:
    """
    Paper trading portfolio state.

    Tracks cash, positions, equity curve, and trade history
    for paper trading simulation.
    """

    def __init__(self, initial_balance: float = 10000.0, logger: Any = None):
        self.initial_balance = initial_balance
        self.cash = initial_balance
        self.positions: dict[str, dict] = {}  # symbol -> {units, avg_price}
        self.trades: list[dict] = []
        self.equity_curve: list[dict] = []
        self.logger = logger
        self._initialize_equity_curve()

    def _initialize_equity_curve(self) -> None:
        """Initialize equity curve with starting point."""
        self.equity_curve.append(
            {
                "timestamp": datetime.now(),
                "cash": self.cash,
                "market_value": 0.0,
                "equity": self.cash,
            }
        )

    def buy(self, symbol: str, units: float, price: float, fee: float) -> bool:
        """
        Execute a paper buy order.

        Args:
            symbol: Trading pair symbol
            units: Number of units to buy
            price: Execution price
            fee: Trading fee amount

        Returns:
            True if order executed successfully
        """
        cost = units * price + fee

        if cost > self.cash:
            return False  # Insufficient cash

        self.cash -= cost

        if symbol not in self.positions:
            self.positions[symbol] = {"units": 0.0, "avg_price": 0.0}

        # Update position
        pos = self.positions[symbol]
        total_units = pos["units"] + units
        pos["avg_price"] = ((pos["units"] * pos["avg_price"]) + (units * price)) / total_units
        pos["units"] = total_units

        # Record trade
        trade = {
            "timestamp": datetime.now(),
            "symbol": symbol,
            "side": "BUY",
            "units": units,
            "price": price,
            "fee": fee,
        }
        self.trades.append(trade)

        # Log trade if logger available
        if self.logger:
            self.logger.log_portfolio_update(
                action="BUY",
                symbol=symbol,
                cash=self.cash,
                positions=self.get_positions(),
                total_value=self.get_total_value(),
            )

        return True

    def sell(self, symbol: str, units: float, price: float, fee: float) -> bool:
        """
        Execute a paper sell order.

        Args:
            symbol: Trading pair symbol
            units: Number of units to sell
            price: Execution price
            fee: Trading fee amount

        Returns:
            True if order executed successfully
        """
        if symbol not in self.positions:
            return False  # No position

        pos = self.positions[symbol]
        if pos["units"] < units:
            return False  # Insufficient units

        proceeds = units * price - fee
        self.cash += proceeds

        # Update position
        pos["units"] -= units
        if pos["units"] == 0.0:
            del self.positions[symbol]

        # Record trade
        trade = {
            "timestamp": datetime.now(),
            "symbol": symbol,
            "side": "SELL",
            "units": units,
            "price": price,
            "fee": fee,
        }
        self.trades.append(trade)

        # Log trade if logger available
        if self.logger:
            self.logger.log_portfolio_update(
                action="SELL",
                symbol=symbol,
                cash=self.cash,
                positions=self.get_positions(),
                total_value=self.get_total_value(),
            )

        return True

    def get_total_value(self, current_prices: dict[str, float] | None = None) -> float:
        """
        Calculate total portfolio value.

        Args:
            current_prices: Dict mapping symbol to current price (optional)

        Returns:
            Total portfolio value (cash + positions)
        """
        value = self.cash

        for symbol, pos in self.positions.items():
            price = (
                current_prices.get(symbol, pos["avg_price"]) if current_prices else pos["avg_price"]
            )
            value += pos["units"] * price

        return value

    def get_positions(self) -> dict:
        """Get current positions (copy)."""
        return {symbol: pos.copy() for symbol, pos in self.positions.items()}

    def update_equity_curve(self, current_prices: dict[str, float] | None = None) -> None:
        """
        Update equity curve with current portfolio state.

        Args:
            current_prices: Dict mapping symbol to current price (optional)
        """
        market_value = 0.0
        symbol_snapshots = {}

        for symbol, pos in self.positions.items():
            price = (
                current_prices.get(symbol, pos["avg_price"]) if current_prices else pos["avg_price"]
            )
            value = pos["units"] * price
            market_value += value
            symbol_snapshots[symbol] = value

        self.equity_curve.append(
            {
                "timestamp": datetime.now(),
                "cash": self.cash,
                "market_value": market_value,
                "equity": self.cash + market_value,
                **symbol_snapshots,
            }
        )

    def get_equity_curve(self) -> list[dict]:
        """Get equity curve (copy)."""
        return self.equity_curve.copy()

    def get_trades(self) -> list[dict]:
        """Get trade history (copy)."""
        return self.trades.copy()

    def get_summary(self) -> dict:
        """Get portfolio summary."""
        current_value = self.get_total_value()
        total_return = (current_value - self.initial_balance) / self.initial_balance

        return {
            "initial_balance": self.initial_balance,
            "current_cash": self.cash,
            "current_value": current_value,
            "total_return": total_return,
            "position_count": len(self.positions),
            "trade_count": len(self.trades),
        }
