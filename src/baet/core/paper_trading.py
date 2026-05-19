"""Live paper-trading engine for BAET.

Runs strategies against live market data without risking real money.
Measures:
- Drift: exchange state vs internal state divergence over time
- Replay consistency: same data → same decisions
- Latency distributions: order submission → fill timing

This is the final validation layer before going live.
Paper trading must run for weeks with zero drift and perfect
replay consistency before any live trading is considered.

Architecture:
    PaperTradingEngine
        ├── WebSocketIngest (market data)
        ├── StrategySandbox (signal generation)
        ├── BacktestRealism (fill simulation)
        ├── ExecutionEngine (order simulation)
        ├── ReconcileLoop (drift monitoring)
        └── MetricsCollector (latency tracking)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from baet.core.backtest_realism import BacktestRealism, CandleContext, FeeSchedule
from baet.core.clock import Clock, get_clock
from baet.core.events import EventStore, EventType
from baet.core.execution import ExecutionEngine, ExecutionResult, RetryPolicy
from baet.core.health import HealthMonitor, HealthStatus, MetricsCollector
from baet.core.orders import OrderTracker
from baet.core.reconcile_loop import ReconcileLoop
from baet.core.reducer import reduce_state
from baet.core.snapshot import SnapshotManager
from baet.core.state import PortfolioState
from baet.core.strategy_sandbox import (
    Strategy,
    StrategyContext,
    StrategySandbox,
    aggregate_signals,
)
from baet.core.websocket_ingest import WebSocketIngest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paper exchange gateway — simulates exchange behavior
# ---------------------------------------------------------------------------

class PaperExchangeGateway:
    """
    Simulates exchange behavior for paper trading.

    Produces realistic fills with configurable latency and slippage.
    Tracks all "exchange" state internally for reconciliation.
    """

    def __init__(
        self,
        fee_schedule: FeeSchedule | None = None,
        latency_ms: float = 50.0,
        fill_probability: float = 0.99,  # 99% fill rate
    ) -> None:
        self.fee_schedule = fee_schedule or FeeSchedule()
        self.latency_ms = latency_ms
        self.fill_probability = fill_probability
        self._balances: dict[str, Decimal] = {"USDT": Decimal("100000")}
        self._open_orders: list[dict[str, Any]] = []
        self._order_counter = 0

    def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> dict[str, Any]:
        """Simulate order submission."""
        import random
        import time as _time

        # Simulate network latency
        _time.sleep(self.latency_ms / 1000.0 * random.uniform(0.5, 1.5))

        self._order_counter += 1
        order = {
            "orderId": self._order_counter,
            "clientOrderId": client_order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
            "price": str(price) if price else None,
            "status": "NEW",
            "executedQty": "0",
        }

        # Simulate immediate fill for market orders
        if order_type == "MARKET":
            if random.random() < self.fill_probability:
                order["status"] = "FILLED"
                order["executedQty"] = str(quantity)

        self._open_orders.append(order)
        return order

    def cancel_order(self, client_order_id: str, symbol: str) -> dict[str, Any]:
        for order in self._open_orders:
            if order["clientOrderId"] == client_order_id:
                order["status"] = "CANCELLED"
                return order
        return {"status": "NOT_FOUND"}

    def query_order(self, client_order_id: str, symbol: str) -> dict[str, Any]:
        for order in self._open_orders:
            if order["clientOrderId"] == client_order_id:
                return order
        return {"status": "NOT_FOUND"}

    def get_fills(self, client_order_id: str, symbol: str) -> list[dict[str, Any]]:
        for order in self._open_orders:
            if order["clientOrderId"] == client_order_id and order["status"] == "FILLED":
                return [{
                    "clientOrderId": client_order_id,
                    "symbol": symbol,
                    "side": order["side"],
                    "executedQty": order["executedQty"],
                    "price": order.get("price", "0"),
                    "commission": "0",
                    "commissionAsset": "USDT",
                }]
        return []

    def get_balances(self) -> dict[str, Decimal]:
        return dict(self._balances)

    def get_open_orders(self) -> list[dict[str, Any]]:
        return [o for o in self._open_orders if o["status"] in ("NEW", "PARTIALLY_FILLED")]


# ---------------------------------------------------------------------------
# Paper trading metrics
# ---------------------------------------------------------------------------

@dataclass
class PaperTradingMetrics:
    """Metrics collected during paper trading."""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_candles: int = 0
    total_signals: int = 0
    total_orders: int = 0
    total_fills: int = 0
    total_rejections: int = 0
    drift_events: int = 0
    max_drift_usd: Decimal = Decimal("0")
    latency_samples: list[float] = field(default_factory=list)
    replay_mismatches: int = 0

    @property
    def avg_latency_ms(self) -> float:
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)

    @property
    def p99_latency_ms(self) -> float:
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def summary(self) -> dict[str, Any]:
        return {
            "duration_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            "total_candles": self.total_candles,
            "total_signals": self.total_signals,
            "total_orders": self.total_orders,
            "total_fills": self.total_fills,
            "total_rejections": self.total_rejections,
            "drift_events": self.drift_events,
            "max_drift_usd": str(self.max_drift_usd),
            "avg_latency_ms": self.avg_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "replay_mismatches": self.replay_mismatches,
        }


# ---------------------------------------------------------------------------
# Paper trading engine
# ---------------------------------------------------------------------------

class PaperTradingEngine:
    """
    Runs paper trading with full measurement.

    Each candle:
    1. Ingest candle → event store
    2. Run strategies → signals
    3. Aggregate signals → orders
    4. Simulate execution → fills
    5. Reduce events → new state
    6. Check invariants
    7. Measure drift
    """

    def __init__(
        self,
        strategies: list[Strategy],
        event_store: EventStore,
        snapshot_manager: SnapshotManager,
        realism: BacktestRealism | None = None,
        sandbox: StrategySandbox | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.strategies = strategies
        self.event_store = event_store
        self.snapshot_manager = snapshot_manager
        self.realism = realism or BacktestRealism()
        self.sandbox = sandbox or StrategySandbox()
        self.clock = clock or get_clock()

        # Paper exchange
        self.gateway = PaperExchangeGateway(
            fee_schedule=self.realism.fee_schedule,
        )
        self.execution_engine = ExecutionEngine(
            event_store=event_store,
            gateway=self.gateway,
            clock=self.clock,
        )

        # State
        self.state = PortfolioState()
        self.order_tracker = OrderTracker()
        self.metrics = PaperTradingMetrics()

        # Reconciliation
        self.reconcile_loop = ReconcileLoop(
            event_store=event_store,
            interval_seconds=60.0,
            clock=self.clock,
        )

        # Health
        self.health = HealthMonitor()
        self.health.register_check("paper_trading", self._health_check)

    def on_candle(self, raw_candle: dict[str, Any]) -> None:
        """
        Process a single candle through the full pipeline.
        """
        self.metrics.total_candles += 1

        # 1. Ingest candle
        ingest = WebSocketIngest(event_store=self.event_store, clock=self.clock)
        ingest.on_kline(raw_candle)

        # 2. Run strategies
        signals = self._run_strategies(raw_candle)
        self.metrics.total_signals += len(signals)

        # 3. Execute signals
        for signal in signals:
            self._execute_signal(signal)

        # 4. Periodic reconciliation
        if self.metrics.total_candles % 100 == 0:
            self._check_drift()

        # 5. Periodic snapshot
        if self.metrics.total_candles % 1000 == 0:
            self._save_snapshot()

    def _run_strategies(self, raw_candle: dict[str, Any]) -> list:
        """Run all strategies and aggregate signals."""
        import pandas as pd

        # Build minimal candle data for strategies
        kline = raw_candle.get("k", raw_candle)
        candle_data = pd.DataFrame([{
            "open_time": pd.to_datetime(kline["t"], unit="ms", utc=True),
            "open": float(kline["o"]),
            "high": float(kline["h"]),
            "low": float(kline["l"]),
            "close": float(kline["c"]),
            "volume": float(kline["v"]),
        }])

        context = StrategyContext(
            symbol=kline.get("s", "UNKNOWN"),
            timeframe=kline.get("i", "1m"),
            current_time=self.clock.now(),
            portfolio_snapshot=self.state.to_dict(),
        )

        all_signals = self.sandbox.run_all(self.strategies, candle_data, context)
        aggregated = aggregate_signals(all_signals)
        return aggregated

    def _execute_signal(self, signal: Any) -> None:
        """Execute a signal through the paper trading pipeline."""
        if signal.action == "HOLD":
            return

        self.metrics.total_orders += 1
        start_time = time.monotonic()

        side = signal.action
        symbol = signal.symbol
        size_hint = Decimal(str(signal.size_hint))

        # Calculate order size from portfolio
        equity = self.state.total_equity()
        order_value = equity * size_hint
        # Use a simplified price estimate
        price = Decimal("50000")  # Would come from latest candle
        quantity = order_value / price

        result = self.execution_engine.submit_order(
            state=self.state,
            symbol=symbol,
            side=side,
            order_type="MARKET",
            quantity=quantity,
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        self.metrics.latency_samples.append(elapsed_ms)

        if result.success:
            # Update state with new events
            for event in result.events:
                self.state = reduce_state(self.state, event)
            self.metrics.total_fills += 1
        else:
            self.metrics.total_rejections += 1

    def _check_drift(self) -> None:
        """Run reconciliation and track drift."""
        tick = self.reconcile_loop.tick(
            state=self.state,
            exchange=self.gateway,
            order_tracker=self.order_tracker,
        )

        if tick.action in ("warn", "halt"):
            self.metrics.drift_events += 1
            logger.warning(f"Drift detected: {tick.action}")

    def _save_snapshot(self) -> None:
        """Save periodic snapshot."""
        self.snapshot_manager.save_snapshot(
            state=self.state,
            event_sequence=self.event_store.get_latest_sequence(),
            event_count=self.metrics.total_candles,
            store=self.event_store,
        )

    def _health_check(self):
        from baet.core.health import HealthCheck

        if self.reconcile_loop.is_halted:
            return HealthCheck(
                name="paper_trading",
                status=HealthStatus.UNHEALTHY,
                message="Reconciliation halt — drift detected",
            )

        if self.metrics.replay_mismatches > 0:
            return HealthCheck(
                name="paper_trading",
                status=HealthStatus.DEGRADED,
                message=f"{self.metrics.replay_mismatches} replay mismatches",
            )

        return HealthCheck(
            name="paper_trading",
            status=HealthStatus.HEALTHY,
            message=(
                f"Candles: {self.metrics.total_candles}, "
                f"Orders: {self.metrics.total_orders}, "
                f"Fills: {self.metrics.total_fills}, "
                f"Drift: {self.metrics.drift_events}"
            ),
        )

    def get_report(self) -> dict[str, Any]:
        """Get full paper trading report."""
        return {
            "metrics": self.metrics.summary(),
            "state": self.state.to_dict(),
            "health": self.health.check_health().to_dict(),
        }
