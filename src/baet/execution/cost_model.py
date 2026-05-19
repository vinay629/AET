"""Execution cost model for BAET.

Models realistic execution costs:
- Spread crossing
- Queue position
- Partial fills
- Market impact curves
- Volatility-adjusted slippage
- Market impact scaling with size

This is the difference between backtest Sharpe and live Sharpe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CostModelConfig:
    """Configuration for execution cost modeling."""
    # Spread
    normal_spread_bps: float = 5.0      # Normal bid-ask spread in bps
    stress_spread_bps: float = 50.0     # Spread during stress

    # Market impact (Almgren-Chriss inspired)
    permanent_impact_coeff: float = 0.1   # Permanent impact coefficient
    temporary_impact_coeff: float = 0.05  # Temporary impact coefficient
    impact_exponent: float = 0.5          # Square-root impact model

    # Partials
    partial_fill_probability: float = 0.3
    avg_fill_ratio: float = 0.7

    # Latency
    base_latency_ms: float = 50.0
    latency_volatility_ms: float = 20.0

    # Fees
    maker_fee_bps: float = 2.0
    taker_fee_bps: float = 5.0
    maker_probability: float = 0.3  # Probability of being maker


@dataclass
class ExecutionCost:
    """Breakdown of execution costs for a single order."""
    symbol: str
    side: str
    quantity: float
    expected_price: float

    # Cost components
    spread_cost_bps: float = 0.0
    impact_cost_bps: float = 0.0
    fee_cost_bps: float = 0.0
    slippage_bps: float = 0.0
    total_cost_bps: float = 0.0

    # Fill info
    fill_price: float = 0.0
    filled_quantity: float = 0.0
    is_partial: bool = False
    n_fills: int = 1

    # Timing
    expected_latency_ms: float = 0.0
    actual_latency_ms: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        return self.filled_quantity * self.fill_price * self.total_cost_bps / 10000

    @property
    def implementation_shortfall_bps(self) -> float:
        """Difference between expected and actual execution price."""
        if self.expected_price == 0:
            return 0.0
        direction = 1 if self.side == "BUY" else -1
        return (self.fill_price - self.expected_price) / self.expected_price * 10000 * direction


class ExecutionCostModel:
    """
    Models realistic execution costs.

    Uses Almgren-Chriss inspired impact model:
    - Permanent impact: proportional to trade size
    - Temporary impact: proportional to trade rate (size/time)
    - Square-root impact: impact ∝ √(size/ADV)
    """

    def __init__(self, config: CostModelConfig | None = None) -> None:
        self.config = config or CostModelConfig()

    def estimate_cost(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        adv: float,           # Average daily volume
        volatility: float,    # Daily volatility
        spread_bps: float | None = None,
        urgency: float = 0.5,  # 0 = patient, 1 = urgent
    ) -> ExecutionCost:
        """
        Estimate execution cost for an order.

        Args:
            symbol: Trading pair.
            side: BUY or SELL.
            quantity: Order quantity.
            price: Current mid price.
            adv: Average daily volume (in same units as quantity).
            volatility: Daily volatility (as decimal, e.g., 0.02 for 2%).
            spread_bps: Current spread in bps (uses config default if None).
            urgency: Trading urgency (0=patient, 1=urgent).

        Returns:
            ExecutionCost with full cost breakdown.
        """
        cfg = self.config
        spread = spread_bps or cfg.normal_spread_bps

        # Spread cost (always pay half-spread)
        spread_cost = spread / 2

        # Market impact (square-root model)
        participation = quantity / adv if adv > 0 else 0.01
        permanent_impact = cfg.permanent_impact_coeff * volatility * np.sqrt(participation) * 10000
        temp_sqrt = np.sqrt(participation / max(urgency, 0.1))
        temporary_impact = cfg.temporary_impact_coeff * volatility * temp_sqrt * 10000
        impact_cost = permanent_impact + temporary_impact

        # Fee cost
        maker_prob = cfg.maker_probability * (1 - urgency)  # More urgent = less likely maker
        fee_cost = maker_prob * cfg.maker_fee_bps + (1 - maker_prob) * cfg.taker_fee_bps

        # Slippage (volatility during execution)
        execution_time = participation / max(urgency, 0.1)  # Fraction of day
        slippage = volatility * np.sqrt(execution_time) * 10000 * 0.5

        # Total
        total = spread_cost + impact_cost + fee_cost + slippage

        # Fill simulation
        is_partial = np.random.random() < cfg.partial_fill_probability
        fill_ratio = cfg.avg_fill_ratio if is_partial else 1.0
        filled_qty = quantity * fill_ratio

        # Fill price
        direction = 1 if side == "BUY" else -1
        fill_price = price * (1 + direction * total / 10000)

        # Latency
        latency = cfg.base_latency_ms + np.random.exponential(cfg.latency_volatility_ms)

        return ExecutionCost(
            symbol=symbol,
            side=side,
            quantity=quantity,
            expected_price=price,
            spread_cost_bps=spread_cost,
            impact_cost_bps=impact_cost,
            fee_cost_bps=fee_cost,
            slippage_bps=slippage,
            total_cost_bps=total,
            fill_price=fill_price,
            filled_quantity=filled_qty,
            is_partial=is_partial,
            n_fills=max(1, int(np.ceil(1 / fill_ratio))),
            expected_latency_ms=cfg.base_latency_ms,
            actual_latency_ms=latency,
        )

    def estimate_capacity(
        self,
        symbol: str,
        adv: float,
        volatility: float,
        target_cost_bps: float = 10.0,
    ) -> dict[str, float]:
        """
        Estimate capacity: max participation rate before costs exceed target.

        Args:
            symbol: Trading pair.
            adv: Average daily volume.
            volatility: Daily volatility.
            target_cost_bps: Maximum acceptable cost in bps.

        Returns:
            Dict with capacity metrics.
        """
        # Binary search for max participation
        low, high = 0.001, 0.5
        for _ in range(50):
            mid = (low + high) / 2
            qty = adv * mid
            cost = self.estimate_cost(symbol, "BUY", qty, 100, adv, volatility)
            if cost.total_cost_bps < target_cost_bps:
                low = mid
            else:
                high = mid

        max_participation = low
        max_quantity = adv * max_participation

        return {
            "max_participation_pct": max_participation * 100,
            "max_quantity": max_quantity,
            "target_cost_bps": target_cost_bps,
            "estimated_cost_at_max": self.estimate_cost(
                symbol, "BUY", max_quantity, 100, adv, volatility
            ).total_cost_bps,
        }

    def simulate_execution(
        self,
        orders: list[dict[str, Any]],
        market_data: pd.DataFrame,
    ) -> list[ExecutionCost]:
        """
        Simulate execution of multiple orders through market data.

        Args:
            orders: List of order dicts with symbol, side, quantity, price.
            market_data: OHLCV data for context.

        Returns:
            List of ExecutionCost results.
        """
        results = []
        for order in orders:
            # Estimate ADV from market_data
            if "volume" in market_data.columns:
                adv = market_data["volume"].mean() * 24
            else:
                adv = order["quantity"] * 10

            # Estimate volatility
            if "close" in market_data.columns:
                returns = market_data["close"].pct_change().dropna()
                vol = returns.std()
            else:
                vol = 0.01

            cost = self.estimate_cost(
                symbol=order.get("symbol", "UNKNOWN"),
                side=order["side"],
                quantity=order["quantity"],
                price=order["price"],
                adv=adv,
                volatility=vol,
            )
            results.append(cost)

        return results
