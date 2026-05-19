"""Durable portfolio state for BAET.

Portfolio state is reconstructed entirely from events.
No state is held in memory that cannot be rebuilt from the event journal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from baet.core.events import Event, EventStore, EventType


@dataclass(frozen=True)
class Position:
    """Immutable snapshot of a single position."""
    symbol: str
    units: Decimal
    avg_entry_price: Decimal
    unrealized_pnl: Decimal = Decimal("0")


@dataclass(frozen=True)
class TradeRecord:
    """Immutable record of a completed trade."""
    event_id: str
    timestamp: datetime
    symbol: str
    side: str
    price: Decimal
    units: Decimal
    fee: Decimal
    pnl: Decimal = Decimal("0")


@dataclass
class PortfolioState:
    """
    Current portfolio state. Every mutation produces an event.

    State is always derived from the event journal.
    On restart, call `from_events()` to reconstruct.
    """

    cash: Decimal = Decimal("10000.0")
    positions: dict[str, dict[str, Decimal]] = field(default_factory=dict)
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)

    def apply(self, event: Event) -> list[Event]:
        """Apply an event. Returns any emitted events.

        NOTE: This mutates in place for backward compatibility.
        For pure reduction, use baet.core.reducer.reduce_state().
        """
        from baet.core.reducer import reduce_state
        new_state = reduce_state(self, event)
        self.cash = new_state.cash
        self.positions = new_state.positions
        self.trades = new_state.trades
        self.equity_curve = new_state.equity_curve
        return []

    def total_equity(self, current_prices: dict[str, Decimal] | None = None) -> Decimal:
        """Calculate total equity using current market prices."""
        equity = self.cash
        if current_prices:
            for symbol, pos in self.positions.items():
                price = current_prices.get(symbol, pos["avg_price"])
                equity += pos["units"] * price
        return equity

    def to_dict(self) -> dict[str, Any]:
        return {
            "cash": str(self.cash),
            "positions": {
                sym: {k: str(v) for k, v in pos.items()}
                for sym, pos in self.positions.items()
            },
            "trade_count": len(self.trades),
        }

    @classmethod
    def from_events(cls, events: list[Event]) -> PortfolioState:
        """Reconstruct portfolio state from an event stream.

        Uses the pure reducer — deterministic and side-effect-free.
        """
        from baet.core.reducer import reduce_many
        return reduce_many(cls(), events)

    @classmethod
    def from_journal(cls, store: EventStore, date: str | None = None) -> PortfolioState:
        """Reconstruct state from the event journal."""
        events = store.replay(date)
        return cls.from_events(events)

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot of current state."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cash": str(self.cash),
            "positions": {
                sym: {
                    "units": str(pos["units"]),
                    "avg_price": str(pos["avg_price"]),
                }
                for sym, pos in self.positions.items()
            },
            "total_trades": len(self.trades),
        }

    def verify_invariants(self) -> list[str]:
        """Check invariants. Returns list of violations (empty = OK)."""
        violations = []
        if self.cash < 0:
            violations.append(f"Cash is negative: {self.cash}")
        for symbol, pos in self.positions.items():
            if pos["units"] < 0:
                violations.append(f"Negative position in {symbol}: {pos['units']}")
        return violations

    def state_hash(self) -> str:
        """Deterministic hash of meaningful state (excludes timestamps)."""
        data = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()


def save_snapshot(state: PortfolioState, path: Path) -> None:
    """Save a portfolio state snapshot to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state.snapshot(), f, indent=2, default=str)


def load_snapshot(path: Path) -> dict[str, Any]:
    """Load a portfolio state snapshot from disk."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
