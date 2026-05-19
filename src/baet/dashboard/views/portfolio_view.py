"""Portfolio view — read-only projection of portfolio state.

Derived entirely from the event journal via the pure reducer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from baet.dashboard.views.base import MaterializedView
from baet.core.events import EventType


class PortfolioView(MaterializedView):
    """Read-only portfolio state projection."""

    def __init__(self, event_store, cache_ttl: float = 1.0) -> None:
        super().__init__(event_store, cache_ttl)

    def _compute(self, **params: Any) -> dict[str, Any]:
        date = params.get("date")
        state = self._reconstruct_state(date)
        events = self.event_store.replay(date)

        # Compute equity curve from events
        equity_curve = self._compute_equity_curve(events)

        # Compute PnL
        initial_cash = Decimal("10000.0")  # Default initial
        realized_pnl = self._compute_realized_pnl(events)
        unrealized_pnl = self._compute_unrealized_pnl(state)

        # Positions
        positions = []
        for symbol, pos in state.positions.items():
            positions.append({
                "symbol": symbol,
                "units": str(pos["units"]),
                "avg_entry_price": str(pos["avg_price"]),
                "notional": str(pos["units"] * pos["avg_price"]),
            })

        # Recent trades
        recent_trades = []
        for trade in state.trades[-20:]:  # Last 20 trades
            recent_trades.append({
                "symbol": trade.symbol,
                "side": trade.side,
                "price": str(trade.price),
                "units": str(trade.units),
                "fee": str(trade.fee),
                "timestamp": trade.timestamp.isoformat() if trade.timestamp else None,
            })

        total_equity = state.cash + sum(
            pos["units"] * pos["avg_price"]
            for pos in state.positions.values()
        )

        return {
            "equity": str(total_equity),
            "cash": str(state.cash),
            "initial_cash": str(initial_cash),
            "realized_pnl": str(realized_pnl),
            "unrealized_pnl": str(unrealized_pnl),
            "total_pnl": str(realized_pnl + unrealized_pnl),
            "total_pnl_pct": str(
                (realized_pnl + unrealized_pnl) / initial_cash * 100
            ) if initial_cash > 0 else "0",
            "positions": positions,
            "position_count": len(positions),
            "trade_count": len(state.trades),
            "recent_trades": recent_trades,
            "equity_curve": equity_curve,
            "drawdown": self._compute_drawdown(equity_curve),
        }

    def _compute_equity_curve(self, events: list) -> list[dict]:
        """Compute equity curve from equity snapshot events."""
        curve = []
        for event in events:
            if event.event_type == EventType.EQUITY_SNAPSHOT:
                p = event.payload
                curve.append({
                    "timestamp": p.get("timestamp", ""),
                    "equity": p.get("equity", "0"),
                    "cash": p.get("cash", "0"),
                })
        return curve

    def _compute_realized_pnl(self, events: list) -> Decimal:
        """Sum realized PnL from fill events."""
        pnl = Decimal("0")
        for event in events:
            if event.event_type == EventType.ORDER_FILLED:
                p = event.payload
                if p.get("pnl"):
                    pnl += Decimal(str(p["pnl"]))
        return pnl

    def _compute_unrealized_pnl(self, state) -> Decimal:
        """Estimate unrealized PnL (would need current prices for accuracy)."""
        # Without live prices, we use avg_entry as current price → zero unrealized
        return Decimal("0")

    def _compute_drawdown(self, equity_curve: list) -> dict[str, Any]:
        """Compute drawdown statistics from equity curve."""
        if not equity_curve:
            return {"current": "0", "max": "0", "max_pct": "0"}

        equities = [Decimal(str(e.get("equity", 0))) for e in equity_curve]
        if not equities:
            return {"current": "0", "max": "0", "max_pct": "0"}

        peak = equities[0]
        max_dd = Decimal("0")
        for eq in equities:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else Decimal("0")
            if dd > max_dd:
                max_dd = dd

        current_dd = (peak - equities[-1]) / peak if peak > 0 else Decimal("0")

        return {
            "current": str(current_dd),
            "max": str(max_dd),
            "max_pct": str(max_dd * 100),
        }
