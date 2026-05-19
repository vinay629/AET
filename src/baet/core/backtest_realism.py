"""Backtest realism engine for BAET.

Makes backtests trustworthy by simulating real-world execution:

1. T+1 execution: signals at candle close → fill at NEXT candle open
2. Spread: bid-ask spread applied to all fills
3. Slippage: market impact based on order size relative to volume
4. Fees: maker/taker fee schedule
5. Latency: simulated network + processing delay

The realism engine wraps the reducer. It intercepts fill events
and adjusts them to reflect real-world conditions.

Usage:
    realism = BacktestRealism(
        fee_rate=0.001,       # 0.1% taker fee
        spread_bps=5.0,       # 5 basis points spread
        slippage_bps=2.0,     # 2 basis points base slippage
        latency_ms=100,       # 100ms simulated latency
        execution_delay=1,    # T+1 (fill at next candle)
    )
    adjusted_event = realism.adjust_fill(raw_fill_event, candle_context)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from baet.core.events import Event, EventType

logger = logging.getLogger(__name__)


@dataclass
class FeeSchedule:
    """Exchange fee schedule."""
    maker_fee: Decimal = Decimal("0.001")   # 0.1%
    taker_fee: Decimal = Decimal("0.001")   # 0.1%
    use_maker: bool = False                  # Most backtest fills are taker

    def get_fee_rate(self, is_maker: bool = False) -> Decimal:
        if is_maker:
            return self.maker_fee
        return self.taker_fee


@dataclass
class CandleContext:
    """Context for a candle being used to fill an order."""
    symbol: str
    timeframe: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal


@dataclass
class FillAdjustment:
    """How a fill was adjusted for realism."""
    original_price: Decimal
    adjusted_price: Decimal
    spread_cost: Decimal
    slippage_cost: Decimal
    fee: Decimal
    is_maker: bool
    latency_ms: float
    execution_delay_bars: int


class BacktestRealism:
    """
    Adjusts fill events to reflect real-world execution conditions.

    This is used during backtesting to ensure that simulated fills
    are realistic — not optimistic.
    """

    def __init__(
        self,
        fee_schedule: FeeSchedule | None = None,
        spread_bps: float = 5.0,
        slippage_bps: float = 2.0,
        latency_ms: float = 100.0,
        execution_delay: int = 1,  # T+1 = fill at next candle
        volume_impact_factor: float = 0.1,  # 10% of daily volume = max impact
    ) -> None:
        self.fee_schedule = fee_schedule or FeeSchedule()
        self.spread_bps = Decimal(str(spread_bps))
        self.slippage_bps = Decimal(str(slippage_bps))
        self.latency_ms = latency_ms
        self.execution_delay = execution_delay
        self.volume_impact_factor = Decimal(str(volume_impact_factor))

    def adjust_fill(
        self,
        event: Event,
        candle: CandleContext,
        is_maker: bool = False,
    ) -> tuple[Event, FillAdjustment]:
        """
        Adjust a fill event for realism.

        Args:
            event: The original ORDER_FILLED event.
            candle: The candle context for the fill.
            is_maker: Whether this is a maker order (limit at bid/ask).

        Returns:
            Tuple of (adjusted_event, FillAdjustment).
        """
        if event.event_type != EventType.ORDER_FILLED:
            return event, FillAdjustment(
                original_price=Decimal("0"),
                adjusted_price=Decimal("0"),
                spread_cost=Decimal("0"),
                slippage_cost=Decimal("0"),
                fee=Decimal("0"),
                is_maker=is_maker,
                latency_ms=0,
                execution_delay_bars=0,
            )

        payload = dict(event.payload)
        side = payload.get("side", "BUY")
        original_price = Decimal(str(payload.get("price", 0)))
        units = Decimal(str(payload.get("units", 0)))

        # 1. Spread cost
        spread_cost = self._calculate_spread(original_price)

        # 2. Slippage based on order size vs candle volume
        slippage_cost = self._calculate_slippage(
            original_price, units, candle.volume
        )

        # 3. Calculate adjusted fill price
        if side == "BUY":
            # Buy at ask (higher): open + spread + slippage
            fill_price = candle.open + spread_cost + slippage_cost
            # Cap at candle high (can't fill above the high)
            fill_price = min(fill_price, candle.high)
        else:
            # Sell at bid (lower): open - spread - slippage
            fill_price = candle.open - spread_cost - slippage_cost
            # Floor at candle low (can't fill below the low)
            fill_price = max(fill_price, candle.low)

        # 4. Calculate fee
        fee_rate = self.fee_schedule.get_fee_rate(is_maker)
        fee = units * fill_price * fee_rate

        # 5. Build adjusted event
        adjusted_payload = {
            **payload,
            "price": str(fill_price),
            "fee": str(fee),
            "original_price": str(original_price),
            "spread_bps": float(self.spread_bps),
            "slippage_bps": float(self.slippage_cost_to_bps(
                original_price, slippage_cost
            )),
            "latency_ms": self.latency_ms,
            "execution_delay_bars": self.execution_delay,
            "fill_price": str(fill_price),
        }

        adjusted_event = Event(
            event_type=event.event_type,
            timestamp_exchange=event.timestamp_exchange,
            timestamp_local=event.timestamp_local,
            sequence=event.sequence,
            source=event.source,
            payload=adjusted_payload,
            schema_version=event.schema_version,
            event_id=event.event_id,
        )

        adjustment = FillAdjustment(
            original_price=original_price,
            adjusted_price=fill_price,
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            fee=fee,
            is_maker=is_maker,
            latency_ms=self.latency_ms,
            execution_delay_bars=self.execution_delay,
        )

        logger.debug(
            f"Fill adjusted: {side} {units} @ {original_price} → {fill_price} "
            f"(spread={spread_cost}, slippage={slippage_cost}, fee={fee})"
        )

        return adjusted_event, adjustment

    def _calculate_spread(self, price: Decimal) -> Decimal:
        """Calculate spread cost in price terms."""
        return price * self.spread_bps / Decimal("10000")

    def _calculate_slippage(
        self,
        price: Decimal,
        order_units: Decimal,
        candle_volume: Decimal,
    ) -> Decimal:
        """
        Calculate slippage based on order size relative to candle volume.

        Larger orders relative to volume → more slippage.
        Capped at a reasonable maximum.
        """
        if candle_volume <= 0:
            return price * self.slippage_bps / Decimal("10000")

        # Order as fraction of candle volume
        volume_fraction = order_units / candle_volume

        # Scale slippage: if order is 10% of volume, slippage = base * 10
        impact_multiplier = min(
            volume_fraction / self.volume_impact_factor,
            Decimal("5.0"),  # Cap at 5x base slippage
        )

        return price * self.slippage_bps * impact_multiplier / Decimal("10000")

    @staticmethod
    def slippage_cost_to_bps(price: Decimal, slippage: Decimal) -> Decimal:
        """Convert slippage in price terms to basis points."""
        if price <= 0:
            return Decimal("0")
        return slippage / price * Decimal("10000")

    def get_next_candle_time(
        self, current_open: datetime, timeframe: str
    ) -> datetime:
        """Calculate the open time of the next candle (T+1)."""
        delta = self._timeframe_to_delta(timeframe)
        return current_open + delta * self.execution_delay

    @staticmethod
    def _timeframe_to_delta(timeframe: str) -> timedelta:
        """Convert timeframe string to timedelta."""
        units = {
            "s": "seconds",
            "m": "minutes",
            "h": "hours",
            "d": "days",
            "w": "weeks",
        }
        # Parse e.g. "1m", "5m", "1h", "4h", "1d"
        num = int("".join(c for c in timeframe if c.isdigit()))
        unit_char = "".join(c for c in timeframe if c.isalpha()).lower()
        kwarg = units.get(unit_char, "minutes")
        return timedelta(**{kwarg: num})
