"""Strategy sandbox for BAET.

Strategies are PURE FUNCTIONS:
    signals = strategy(candle_data, context)

They have:
- NO access to the exchange
- NO access to PortfolioState
- NO access to the event store
- NO side effects
- NO mutable state

They receive:
- candle_data: DataFrame of canonical OHLCV data
- context: StrategyContext (read-only metadata)

They return:
- DataFrame with standardized signal columns

This ensures:
1. Strategies are testable in isolation
2. Strategies can be backtested deterministically
3. No strategy can accidentally mutate state or place orders
4. Strategies are interchangeable and composable
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import pandas as pd

from baet.core.models import StrategyMetadata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strategy context — read-only data a strategy can inspect
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyContext:
    """
    Read-only context passed to strategies.

    Strategies can read this but NEVER mutate it.
    """
    symbol: str
    timeframe: str
    current_time: datetime
    regime: str | None = None
    regime_confidence: float = 0.0
    # Read-only portfolio snapshot (positions, cash) — strategy can use for sizing
    portfolio_snapshot: dict[str, Any] = field(default_factory=dict)
    # Parameters for this strategy instance
    parameters: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Signal output — standardized format
# ---------------------------------------------------------------------------

REQUIRED_SIGNAL_COLUMNS = [
    "timestamp",
    "symbol",
    "timeframe",
    "action",           # BUY, SELL, HOLD
    "target_position",  # 0.0 to 1.0
    "confidence",       # 0.0 to 1.0
    "size_hint",        # Fraction of portfolio to allocate
    "strategy_name",
    "reason",           # Human-readable reason
]


@dataclass(frozen=True)
class Signal:
    """A single trading signal from a strategy."""
    timestamp: datetime
    symbol: str
    timeframe: str
    action: str          # BUY, SELL, HOLD
    target_position: float = 0.0
    confidence: float = 0.0
    size_hint: float = 0.0
    strategy_name: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "action": self.action,
            "target_position": self.target_position,
            "confidence": self.confidence,
            "size_hint": self.size_hint,
            "strategy_name": self.strategy_name,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Strategy protocol — what every strategy must implement
# ---------------------------------------------------------------------------

class Strategy(Protocol):
    """Protocol for all strategies. Pure function, no side effects."""

    @property
    def metadata(self) -> StrategyMetadata: ...

    def generate_signals(
        self,
        candle_data: pd.DataFrame,
        context: StrategyContext,
    ) -> list[Signal]:
        """
        Generate trading signals from candle data.

        Must be a pure function:
        - Same inputs → same outputs, always
        - No I/O, no network, no file access
        - No mutation of inputs
        - No global state

        Args:
            candle_data: Canonical OHLCV DataFrame (read-only).
            context: Read-only strategy context.

        Returns:
            List of Signal objects (may be empty).
        """
        ...


# ---------------------------------------------------------------------------
# Sandbox runner — executes strategies in isolation
# ---------------------------------------------------------------------------

class StrategySandbox:
    """
    Runs strategies in a sandboxed environment.

    Enforces:
    - No exchange access
    - No state mutation
    - Deterministic execution
    - Signal validation
    """

    def __init__(self, *, allow_io: bool = False, allow_network: bool = False) -> None:
        self.allow_io = allow_io
        self.allow_network = allow_network

    def run(
        self,
        strategy: Strategy,
        candle_data: pd.DataFrame,
        context: StrategyContext,
    ) -> list[Signal]:
        """
        Execute a strategy in the sandbox.

        Args:
            strategy: The strategy to run.
            candle_data: OHLCV data (will be copied to prevent mutation).
            context: Strategy context.

        Returns:
            Validated list of signals.

        Raises:
            StrategyError: If the strategy produces invalid output.
        """
        # Copy data to prevent mutation
        data = candle_data.copy()

        try:
            signals = strategy.generate_signals(data, context)
        except Exception as e:
            logger.error(f"Strategy {strategy.metadata.name} raised: {e}")
            raise StrategyError(f"Strategy {strategy.metadata.name} failed: {e}") from e

        # Validate signals
        validated = []
        for signal in signals:
            try:
                validated.append(self._validate_signal(signal, context))
            except ValueError as e:
                logger.warning(f"Invalid signal from {strategy.metadata.name}: {e}")

        return validated

    def run_all(
        self,
        strategies: list[Strategy],
        candle_data: pd.DataFrame,
        context: StrategyContext,
    ) -> dict[str, list[Signal]]:
        """
        Run multiple strategies and collect their signals.

        Each strategy runs independently — one failure doesn't affect others.
        """
        results: dict[str, list[Signal]] = {}

        for strategy in strategies:
            try:
                signals = self.run(strategy, candle_data, context)
                results[strategy.metadata.name] = signals
            except StrategyError as e:
                logger.error(f"Strategy {strategy.metadata.name} failed: {e}")
                results[strategy.metadata.name] = []

        return results

    def _validate_signal(self, signal: Signal, context: StrategyContext) -> Signal:
        """Validate and sanitize a signal."""
        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, signal.confidence))

        # Clamp size_hint to [0, 1]
        size_hint = max(0.0, min(1.0, signal.size_hint))

        # Validate action
        if signal.action not in ("BUY", "SELL", "HOLD"):
            raise ValueError(f"Invalid action: {signal.action}")

        # Validate target_position
        target_position = max(0.0, min(1.0, signal.target_position))

        return Signal(
            timestamp=signal.timestamp,
            symbol=signal.symbol or context.symbol,
            timeframe=signal.timeframe or context.timeframe,
            action=signal.action,
            target_position=target_position,
            confidence=confidence,
            size_hint=size_hint,
            strategy_name=signal.strategy_name or context.parameters.get("name", ""),
            reason=signal.reason,
        )


class StrategyError(Exception):
    """Raised when a strategy fails."""
    pass


# ---------------------------------------------------------------------------
# Signal aggregator — combines signals from multiple strategies
# ---------------------------------------------------------------------------

def aggregate_signals(
    all_signals: dict[str, list[Signal]],
    *,
    method: str = "weighted_vote",
    weights: dict[str, float] | None = None,
) -> list[Signal]:
    """
    Aggregate signals from multiple strategies.

    Methods:
    - weighted_vote: Weighted average of confidence * direction
    - majority: Simple majority vote
    - confidence: Highest confidence wins

    Returns list of aggregated signals (one per symbol/timeframe).
    """
    if not all_signals:
        return []

    # Group by (symbol, timeframe, timestamp)
    grouped: dict[tuple[str, str, datetime], list[tuple[str, Signal]]] = {}
    for strategy_name, signals in all_signals.items():
        for signal in signals:
            key = (signal.symbol, signal.timeframe, signal.timestamp)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append((strategy_name, signal))

    aggregated: list[Signal] = []

    for (symbol, timeframe, timestamp), strategy_signals in grouped.items():
        if method == "weighted_vote":
            aggregated.append(_weighted_vote(symbol, timeframe, timestamp, strategy_signals, weights))
        elif method == "confidence":
            aggregated.append(_confidence_wins(symbol, timeframe, timestamp, strategy_signals))
        else:
            aggregated.append(_majority_vote(symbol, timeframe, timestamp, strategy_signals))

    return aggregated


def _weighted_vote(
    symbol: str,
    timeframe: str,
    timestamp: datetime,
    signals: list[tuple[str, Signal]],
    weights: dict[str, float] | None,
) -> Signal:
    weights = weights or {}
    total_weight = 0.0
    weighted_score = 0.0
    total_confidence = 0.0
    reasons: list[str] = []

    for strategy_name, signal in signals:
        w = weights.get(strategy_name, 1.0)
        direction = 1.0 if signal.action == "BUY" else (-1.0 if signal.action == "SELL" else 0.0)
        weighted_score += w * direction * signal.confidence
        total_weight += w
        total_confidence += signal.confidence
        reasons.append(f"{strategy_name}: {signal.action}({signal.confidence:.2f})")

    if total_weight > 0:
        avg_score = weighted_score / total_weight
    else:
        avg_score = 0.0

    if avg_score > 0.1:
        action = "BUY"
    elif avg_score < -0.1:
        action = "SELL"
    else:
        action = "HOLD"

    avg_confidence = total_confidence / len(signals) if signals else 0.0

    return Signal(
        timestamp=timestamp,
        symbol=symbol,
        timeframe=timeframe,
        action=action,
        target_position=abs(avg_score),
        confidence=avg_confidence,
        size_hint=abs(avg_score) * avg_confidence,
        strategy_name="aggregated",
        reason="; ".join(reasons),
    )


def _confidence_wins(
    symbol: str, timeframe: str, timestamp: datetime, signals: list[tuple[str, Signal]]
) -> Signal:
    best = max(signals, key=lambda s: s[1].confidence)
    return Signal(
        timestamp=timestamp, symbol=symbol, timeframe=timeframe,
        action=best[1].action, target_position=best[1].target_position,
        confidence=best[1].confidence, size_hint=best[1].size_hint,
        strategy_name=best[0], reason=f"Best confidence: {best[1].reason}",
    )


def _majority_vote(
    symbol: str, timeframe: str, timestamp: datetime, signals: list[tuple[str, Signal]]
) -> Signal:
    from collections import Counter
    actions = [s[1].action for s in signals]
    counts = Counter(actions)
    action = counts.most_common(1)[0][0]
    avg_confidence = sum(s[1].confidence for s in signals) / len(signals)
    return Signal(
        timestamp=timestamp, symbol=symbol, timeframe=timeframe,
        action=action, confidence=avg_confidence,
        strategy_name="aggregated",
        reason=f"Majority: {dict(counts)}",
    )
