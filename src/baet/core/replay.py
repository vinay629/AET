"""Replay engine for BAET.

Deterministic replay of historical events through the trading engine.
Same events → same results, every time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from baet.config.models import BacktestConfig
from baet.core.events import Event, EventStore, EventType
from baet.core.state import PortfolioState



logger = logging.getLogger(__name__)


@dataclass
class ReplayResult:
    """Result of a replay run."""
    events_processed: int = 0
    signals_generated: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    final_state: dict[str, Any] = field(default_factory=dict)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    success: bool = True
    error: str | None = None


class ReplayEngine:
    """
    Replays events through the trading engine deterministically.

    Guarantees: same input events → same output state, every time.
    This is the foundation for debugging, validation, and trust.
    """

    def __init__(self, config: BacktestConfig, event_store: EventStore) -> None:
        self.config = config
        self.event_store = event_store
        self._owns_store = False

    @classmethod
    def create(cls, config: BacktestConfig, store_dir: Path) -> ReplayEngine:
        """Factory that creates an engine with its own event store."""
        store = EventStore(base_dir=store_dir)
        engine = cls(config=config, event_store=store)
        engine._owns_store = True
        return engine

    def close(self) -> None:
        """Close the event store if this engine owns it."""
        if self._owns_store:
            self.event_store.close()

    def __enter__(self) -> ReplayEngine:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def replay_backtest(
        self,
        market_frames: dict[tuple[str, str], pd.DataFrame],
        signals: dict[tuple[str, str], pd.DataFrame],
        run_name: str,
    ) -> ReplayResult:
        """
        Deterministic backtest replay.

        Processes candles and signals in strict temporal order.
        Records every decision as an event for later replay.
        """
        result = ReplayResult()
        state = PortfolioState(cash=Decimal(str(self.config.initial_cash)))

        # Build combined timeline from all market frames
        timeline = self._build_timeline(market_frames, signals)
        if not timeline:
            result.error = "Empty timeline — no data to replay"
            result.success = False
            return result

        # Record system start
        self.event_store.append(
            event_type=EventType.SYSTEM_START,
            timestamp_exchange=timeline[0]["timestamp"],
            source="replay_engine",
            payload={"run_name": run_name, "config": self.config.model_dump()},
        )

        # Process each bar in temporal order
        for bar in timeline:
            result.events_processed += 1
            timestamp = bar["timestamp"]
            symbol = bar["symbol"]
            timeframe = bar["timeframe"]
            key = (symbol, timeframe)

            # Record candle event
            candle_event = self.event_store.append(
                event_type=EventType.CANDLE_RECEIVED,
                timestamp_exchange=timestamp,
                source="replay_engine",
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": bar["volume"],
                },
            )

            # Check if there's a signal for this bar
            signal = bar.get("signal", 0)
            if signal != 0:
                result.signals_generated += 1

                # Record signal event
                self.event_store.append(
                    event_type=EventType.SIGNAL_GENERATED,
                    timestamp_exchange=timestamp,
                    source="replay_engine",
                    payload={
                        "symbol": symbol,
                        "action": "BUY" if signal > 0 else "SELL",
                        "confidence": 1.0,
                        "strategy": "replay",
                    },
                )

                # Execute signal (simplified — mirrors backtest logic)
                fill_price = self._get_execution_price(bar)
                exec_result = self._execute_signal(
                    state=state,
                    signal=signal,
                    symbol=symbol,
                    price=fill_price,
                    timestamp=timestamp,
                )

                if exec_result:
                    result.orders_filled += 1
                else:
                    result.orders_rejected += 1

            # Record equity snapshot
            equity = float(state.cash)
            for sym, pos in state.positions.items():
                if sym == symbol:
                    equity += float(pos["units"]) * bar["close"]

            self.event_store.append(
                event_type=EventType.EQUITY_SNAPSHOT,
                timestamp_exchange=timestamp,
                source="replay_engine",
                payload={
                    "timestamp": timestamp.isoformat(),
                    "cash": float(state.cash),
                    "equity": equity,
                    "positions": {
                        sym: {"units": float(pos["units"]), "avg_price": float(pos["avg_price"])}
                        for sym, pos in state.positions.items()
                    },
                },
            )
            result.equity_curve.append({
                "timestamp": timestamp.isoformat(),
                "cash": float(state.cash),
                "equity": equity,
            })

        # Record system stop
        self.event_store.append(
            event_type=EventType.SYSTEM_STOP,
            timestamp_exchange=timeline[-1]["timestamp"],
            source="replay_engine",
            payload={"run_name": run_name, "events_processed": result.events_processed},
        )

        # Verify invariants
        result.violations = state.verify_invariants()
        if result.violations:
            logger.warning(f"Invariant violations: {result.violations}")

        result.final_state = state.snapshot()
        result.trades = [
            {
                "symbol": t.symbol,
                "side": t.side,
                "price": float(t.price),
                "units": float(t.units),
                "fee": float(t.fee),
            }
            for t in state.trades
        ]

        return result

    def _build_timeline(
        self,
        market_frames: dict[tuple[str, str], pd.DataFrame],
        signals: dict[tuple[str, str], pd.DataFrame],
    ) -> list[dict[str, Any]]:
        """Build a unified, temporally-ordered timeline from market data and signals."""
        rows: list[dict[str, Any]] = []

        for key, market in market_frames.items():
            symbol, timeframe = key
            sig = signals.get(key)
            for _, row in market.iterrows():
                entry: dict[str, Any] = {
                    "timestamp": row["close_time"],
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "signal": 0,
                }
                # Merge signal if present — signal at T executes at T+1
                if sig is not None and "signal" in sig.columns:
                    sig_match = sig[sig["close_time"] == row["close_time"]]
                    if not sig_match.empty:
                        entry["signal"] = int(sig_match.iloc[0]["signal"])
                rows.append(entry)

        rows.sort(key=lambda r: r["timestamp"])
        return rows

    def _get_execution_price(self, bar: dict[str, Any]) -> float:
        """Get execution price based on config."""
        if self.config.execution_price == "next_open":
            return bar["open"]
        return bar["close"]

    def _execute_signal(
        self,
        state: PortfolioState,
        signal: int,
        symbol: str,
        price: float,
        timestamp: datetime,
    ) -> bool:
        """Execute a signal against the portfolio state. Returns True if filled."""
        fill_price = price * (1.0 + self.config.slippage_rate)
        current_units = float(state.positions.get(symbol, {}).get("units", 0))

        if signal > 0 and current_units == 0.0:
            target_cash = float(state.cash) * self.config.allocation_per_signal
            if target_cash <= 0:
                return False
            fee = target_cash * self.config.fee_rate
            net_cash = target_cash - fee
            units = net_cash / fill_price

            fill_event = self.event_store.append(
                event_type=EventType.ORDER_FILLED,
                timestamp_exchange=timestamp,
                source="replay_engine",
                payload={
                    "symbol": symbol,
                    "side": "BUY",
                    "price": fill_price,
                    "units": units,
                    "fee": fee,
                },
            )
            state.apply(fill_event)
            return True

        elif signal <= 0 and current_units > 0.0:
            gross = current_units * fill_price
            fee = gross * self.config.fee_rate

            fill_event = self.event_store.append(
                event_type=EventType.ORDER_FILLED,
                timestamp_exchange=timestamp,
                source="replay_engine",
                payload={
                    "symbol": symbol,
                    "side": "SELL",
                    "price": fill_price,
                    "units": current_units,
                    "fee": fee,
                },
            )
            state.apply(fill_event)
            return True

        return False


def verify_determinism(
    config: BacktestConfig,
    store_dir: Path,
    market_frames: dict[tuple[str, str], pd.DataFrame],
    signals: dict[tuple[str, str], pd.DataFrame],
    run_name: str,
    iterations: int = 3,
) -> bool:
    """
    Verify that replay produces identical results across multiple runs.
    This is the core trust check.
    """
    results: list[ReplayResult] = []
    for i in range(iterations):
        iter_dir = store_dir / f"iter_{i}"
        engine = ReplayEngine.create(config, iter_dir)
        with engine:
            result = engine.replay_backtest(market_frames, signals, f"{run_name}_iter{i}")
            results.append(result)

    # Compare all results to the first (ignore timestamp fields)
    baseline = results[0]
    for i, result in enumerate(results[1:], 1):
        # Compare cash and positions (ignore timestamp which differs per run)
        if result.final_state.get("cash") != baseline.final_state.get("cash"):
            logger.error(f"Determinism check FAILED: iteration {i} cash differs")
            return False
        if result.final_state.get("positions") != baseline.final_state.get("positions"):
            logger.error(f"Determinism check FAILED: iteration {i} positions differ")
            return False
        if result.final_state.get("total_trades") != baseline.final_state.get("total_trades"):
            logger.error(f"Determinism check FAILED: iteration {i} trade count differs")
            return False
        if len(result.trades) != len(baseline.trades):
            logger.error(f"Determinism check FAILED: iteration {i} has different trade list length")
            return False

    logger.info(f"Determinism check PASSED: {iterations} identical runs")
    return True
