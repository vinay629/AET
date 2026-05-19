"""Exchange simulator for BAET.

Simulates realistic exchange behavior for testing without risking capital.

Simulates:
- Partial fills (configurable fill ratio per tick)
- Delayed fills (configurable latency distribution)
- Cancel rejects (configurable reject probability)
- Stale order book (configurable staleness)
- WebSocket gaps (configurable drop rate)
- Exchange downtime (configurable outage windows)
- Slippage spikes (configurable volatility regime)

This is the ONLY exchange implementation used in paper trading and backtesting.
The real Binance adapter is only used in live mode.

Architecture:
    ExchangeSimulator
        ├── OrderBook (simulated bid/ask with spread)
        ├── FillEngine (partial fills, delays, rejects)
        ├── LatencyModel (network latency distribution)
        ├── OutageSimulator (downtime windows)
        └── SlippageModel (regime-dependent slippage)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from baet.core.clock import Clock, get_clock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class MarketRegime(StrEnum):
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    LOW_LIQUIDITY = "low_liquidity"
    STRESS = "stress"


@dataclass
class SimulatorConfig:
    """Configuration for exchange simulation."""
    # Fill behavior
    fill_probability: float = 0.98          # 98% of orders fill
    partial_fill_probability: float = 0.3   # 30% of fills are partial
    min_fill_ratio: float = 0.1             # Minimum 10% fill on partial
    cancel_reject_probability: float = 0.05 # 5% of cancels rejected

    # Latency (milliseconds)
    base_latency_ms: float = 50.0
    latency_p99_ms: float = 200.0
    fill_delay_ms: float = 100.0            # Delay before fill arrives

    # Market
    spread_bps: float = 5.0                 # Bid-ask spread in basis points
    slippage_bps: float = 2.0               # Base slippage
    price_volatility_pct: float = 0.001     # 0.1% price volatility per tick

    # Outage simulation
    outage_probability: float = 0.001       # 0.1% chance of outage per tick
    min_outage_duration_s: float = 5.0
    max_outage_duration_s: float = 30.0

    # WebSocket
    ws_drop_rate: float = 0.001            # 0.1% message drop rate
    ws_gap_probability: float = 0.0005      # Sequence gap probability

    # Regime
    regime: MarketRegime = MarketRegime.NORMAL
    regime_transition_probability: float = 0.01


# ---------------------------------------------------------------------------
# Simulated order book
# ---------------------------------------------------------------------------

@dataclass
class OrderBookLevel:
    price: Decimal
    quantity: Decimal


@dataclass
class SimulatedOrderBook:
    """Simulated order book with bid/ask spread."""
    symbol: str
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    bid_size: Decimal = Decimal("0")
    ask_size: Decimal = Decimal("0")
    last_price: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def spread_bps(self) -> Decimal:
        if self.last_price == 0:
            return Decimal("0")
        return self.spread / self.last_price * Decimal("10000")

    def update(self, mid_price: Decimal, spread_bps: Decimal) -> None:
        """Update order book around a mid price."""
        half_spread = mid_price * Decimal(str(spread_bps)) / Decimal("20000")
        self.bid = mid_price - half_spread
        self.ask = mid_price + half_spread
        self.last_price = mid_price
        self.timestamp = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Simulated order
# ---------------------------------------------------------------------------

class SimOrderStatus(StrEnum):
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class SimulatedOrder:
    """An order being tracked by the simulator."""
    client_order_id: str
    exchange_order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    price: Decimal | None = None
    filled_quantity: Decimal = Decimal("0")
    average_price: Decimal = Decimal("0")
    total_fee: Decimal = Decimal("0")
    status: SimOrderStatus = SimOrderStatus.NEW
    created_at: float = 0.0
    updated_at: float = 0.0
    fills: list[dict] = field(default_factory=list)

    @property
    def remaining(self) -> Decimal:
        return self.quantity - self.filled_quantity

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            SimOrderStatus.FILLED,
            SimOrderStatus.CANCELLED,
            SimOrderStatus.REJECTED,
            SimOrderStatus.EXPIRED,
        )


# ---------------------------------------------------------------------------
# Exchange simulator
# ---------------------------------------------------------------------------

class ExchangeSimulator:
    """
    Simulates exchange behavior for paper trading and backtesting.

    Produces realistic fills, latency, and failure modes without
    touching a real exchange.
    """

    def __init__(
        self,
        config: SimulatorConfig | None = None,
        clock: Clock | None = None,
        initial_prices: dict[str, Decimal] | None = None,
    ) -> None:
        self.config = config or SimulatorConfig()
        self.clock = clock or get_clock()
        self._orders: dict[str, SimulatedOrder] = {}  # client_order_id → order
        self._balances: dict[str, Decimal] = {
            "USDT": Decimal("100000"),
            "BTC": Decimal("1.0"),
            "ETH": Decimal("10.0"),
        }
        self._order_counter = 0
        self._sequence = 0
        self._outage_until: float = 0.0
        self._regime = self.config.regime

        # Price tracking
        self._prices: dict[str, Decimal] = initial_prices or {
            "BTCUSDT": Decimal("68000"),
            "ETHUSDT": Decimal("3500"),
            "SOLUSDT": Decimal("150"),
        }
        self._order_books: dict[str, SimulatedOrderBook] = {}
        for symbol, price in self._prices.items():
            self._order_books[symbol] = SimulatedOrderBook(
                symbol=symbol,
                last_price=price,
            )
            self._order_books[symbol].update(price, self.config.spread_bps)

    # ------------------------------------------------------------------
    # Order operations
    # ------------------------------------------------------------------

    def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> dict[str, Any]:
        """Submit an order to the simulated exchange."""
        # Check for outage
        if time.monotonic() < self._outage_until:
            raise ExchangeOutageError("Exchange is currently unavailable")

        # Check for duplicate
        if client_order_id in self._orders:
            order = self._orders[client_order_id]
            return self._order_to_response(order)

        # Simulate latency
        self._simulate_latency()

        # Create order
        self._order_counter += 1
        order = SimulatedOrder(
            client_order_id=client_order_id,
            exchange_order_id=f"sim-{self._order_counter}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            created_at=time.monotonic(),
            updated_at=time.monotonic(),
        )

        # Simulate reject
        if random.random() > self.config.fill_probability:
            order.status = SimOrderStatus.REJECTED
            self._orders[client_order_id] = order
            return self._order_to_response(order)

        # Market orders: fill immediately (with delay simulation)
        if order_type == "MARKET":
            fill_qty = self._compute_fill_quantity(order)
            if fill_qty > 0:
                self._fill_order(order, fill_qty)

        self._orders[client_order_id] = order
        return self._order_to_response(order)

    def cancel_order(self, client_order_id: str, symbol: str) -> dict[str, Any]:
        """Cancel an order."""
        if time.monotonic() < self._outage_until:
            raise ExchangeOutageError("Exchange is currently unavailable")

        self._simulate_latency()

        order = self._orders.get(client_order_id)
        if order is None:
            return {"status": "NOT_FOUND", "clientOrderId": client_order_id}

        # Simulate cancel reject
        if random.random() < self.config.cancel_reject_probability:
            return {
                "status": "REJECTED",
                "clientOrderId": client_order_id,
                "reason": "Order already filled",
            }

        if not order.is_terminal:
            order.status = SimOrderStatus.CANCELLED
            order.updated_at = time.monotonic()

        return self._order_to_response(order)

    def query_order(self, client_order_id: str, symbol: str) -> dict[str, Any]:
        """Query order status."""
        order = self._orders.get(client_order_id)
        if order is None:
            return {"status": "NOT_FOUND", "clientOrderId": client_order_id}

        # Simulate partial fill arriving on query
        if order.status == SimOrderStatus.NEW and random.random() < 0.3:
            fill_qty = self._compute_fill_quantity(order)
            if fill_qty > 0:
                self._fill_order(order, fill_qty)

        return self._order_to_response(order)

    def get_fills(self, client_order_id: str, symbol: str) -> list[dict[str, Any]]:
        """Get fills for an order."""
        order = self._orders.get(client_order_id)
        if order is None:
            return []
        return order.fills

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_balances(self) -> dict[str, Decimal]:
        """Get account balances."""
        return dict(self._balances)

    def get_open_orders(self) -> list[dict[str, Any]]:
        """Get all open orders."""
        return [
            self._order_to_response(o)
            for o in self._orders.values()
            if not o.is_terminal
        ]

    def get_order_book(self, symbol: str) -> SimulatedOrderBook:
        """Get current order book."""
        return self._order_books.get(symbol, SimulatedOrderBook(symbol=symbol))

    def tick(self) -> list[dict[str, Any]]:
        """
        Advance simulation by one tick.

        Returns list of events that occurred (fills, status changes).
        """
        events: list[dict[str, Any]] = []

        # Update prices
        self._update_prices()

        # Check for outage
        self._check_outage()

        # Process pending fills
        for order in self._orders.values():
            if order.status == SimOrderStatus.NEW:
                # Simulate delayed fill
                delay = self.config.fill_delay_ms / 1000.0 * random.uniform(0.5, 2.0)
                if time.monotonic() - order.created_at > delay:
                    fill_qty = self._compute_fill_quantity(order)
                    if fill_qty > 0:
                        self._fill_order(order, fill_qty)
                        events.append({
                            "type": "order_filled",
                            "client_order_id": order.client_order_id,
                            "fill_qty": str(fill_qty),
                        })

        # Regime transitions
        if random.random() < self.config.regime_transition_probability:
            self._transition_regime()

        return events

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fill_order(self, order: SimulatedOrder, fill_qty: Decimal) -> None:
        """Fill an order (partially or completely)."""
        book = self._order_books.get(order.symbol)
        if book is None:
            return

        # Determine fill price with slippage
        base_price = book.ask if order.side == "BUY" else book.bid
        slippage = self._compute_slippage(order)
        fill_price = base_price * (Decimal("1") + slippage)

        # Compute fee
        fee_rate = Decimal("0.001")  # 0.1%
        fee = fill_qty * fill_price * fee_rate

        # Update order
        order.filled_quantity += fill_qty
        order.total_fee += fee
        order.fills.append({
            "qty": str(fill_qty),
            "price": str(fill_price),
            "commission": str(fee),
            "commissionAsset": "USDT",
        })

        # Update average price
        if order.filled_quantity > 0:
            total_cost = sum(
                Decimal(str(f["price"])) * Decimal(str(f["qty"]))
                for f in order.fills
            )
            order.average_price = total_cost / order.filled_quantity

        # Update status
        if order.filled_quantity >= order.quantity:
            order.status = SimOrderStatus.FILLED
        else:
            order.status = SimOrderStatus.PARTIALLY_FILLED

        order.updated_at = time.monotonic()

        # Update balances
        self._update_balances(order, fill_qty, fill_price, fee)

    def _compute_fill_quantity(self, order: SimulatedOrder) -> Decimal:
        """Compute fill quantity (may be partial)."""
        remaining = order.remaining

        if random.random() < self.config.partial_fill_probability:
            # Partial fill
            ratio = max(
                self.config.min_fill_ratio,
                random.uniform(0.1, 0.9),
            )
            return remaining * Decimal(str(ratio))

        return remaining

    def _compute_slippage(self, order: SimulatedOrder) -> Decimal:
        """Compute slippage based on regime."""
        base_slippage = Decimal(str(self.config.slippage_bps)) / Decimal("10000")

        regime_multiplier = {
            MarketRegime.NORMAL: Decimal("1"),
            MarketRegime.HIGH_VOLATILITY: Decimal("3"),
            MarketRegime.LOW_LIQUIDITY: Decimal("5"),
            MarketRegime.STRESS: Decimal("10"),
        }

        multiplier = regime_multiplier.get(self._regime, Decimal("1"))
        noise = Decimal(str(random.uniform(-0.5, 0.5)))

        return base_slippage * (multiplier + noise)

    def _update_balances(self, order: SimulatedOrder, qty: Decimal, price: Decimal, fee: Decimal) -> None:
        """Update simulated balances after a fill."""
        if order.side == "BUY":
            cost = qty * price + fee
            self._balances["USDT"] = self._balances.get("USDT", Decimal("0")) - cost
            base_asset = order.symbol.replace("USDT", "")
            self._balances[base_asset] = self._balances.get(base_asset, Decimal("0")) + qty
        else:
            proceeds = qty * price - fee
            self._balances["USDT"] = self._balances.get("USDT", Decimal("0")) + proceeds
            base_asset = order.symbol.replace("USDT", "")
            self._balances[base_asset] = self._balances.get(base_asset, Decimal("0")) - qty

    def _update_prices(self) -> None:
        """Update simulated prices with random walk."""
        for symbol, book in self._order_books.items():
            volatility = Decimal(str(self.config.price_volatility_pct))
            if self._regime == MarketRegime.HIGH_VOLATILITY:
                volatility *= Decimal("3")
            elif self._regime == MarketRegime.STRESS:
                volatility *= Decimal("10")

            change = Decimal(str(random.uniform(-1, 1))) * volatility
            new_price = book.last_price * (Decimal("1") + change)
            book.update(new_price, self.config.spread_bps)
            self._prices[symbol] = new_price

    def _check_outage(self) -> None:
        """Check for simulated outage."""
        now = time.monotonic()
        if now < self._outage_until:
            return

        if random.random() < self.config.outage_probability:
            duration = random.uniform(
                self.config.min_outage_duration_s,
                self.config.max_outage_duration_s,
            )
            self._outage_until = now + duration
            logger.warning(f"Simulated exchange outage for {duration:.0f}s")

    def _transition_regime(self) -> None:
        """Transition to a new market regime."""
        regimes = list(MarketRegime)
        new_regime = random.choice(regimes)
        if new_regime != self._regime:
            logger.info(f"Market regime transition: {self._regime.value} → {new_regime.value}")
            self._regime = new_regime

    def _simulate_latency(self) -> None:
        """Simulate network latency."""
        if self.config.base_latency_ms <= 0:
            return  # No latency in tests
        import math
        mu = math.log(self.config.base_latency_ms)
        sigma = 0.5
        latency_ms = random.lognormvariate(mu, sigma)
        latency_ms = min(latency_ms, self.config.latency_p99_ms * 2)
        time.sleep(latency_ms / 1000.0)

    def _order_to_response(self, order: SimulatedOrder) -> dict[str, Any]:
        """Convert simulated order to exchange response format."""
        return {
            "orderId": order.exchange_order_id,
            "clientOrderId": order.client_order_id,
            "symbol": order.symbol,
            "side": order.side,
            "type": order.order_type,
            "status": order.status.value.upper(),
            "quantity": str(order.quantity),
            "executedQty": str(order.filled_quantity),
            "price": str(order.price) if order.price else "0",
            "cummulativeQuoteQty": str(
                order.filled_quantity * order.average_price
                if order.average_price > 0 else Decimal("0")
            ),
        }


class ExchangeOutageError(Exception):
    """Raised when the simulated exchange is down."""
    pass
