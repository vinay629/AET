"""Risk view — read-only projection of risk metrics.

Derived from event journal + risk policy.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from baet.dashboard.views.base import MaterializedView
from baet.core.events import EventType


class RiskView(MaterializedView):
    """Read-only risk metrics projection."""

    def __init__(self, event_store, risk_policy=None, cache_ttl: float = 1.0) -> None:
        super().__init__(event_store, cache_ttl)
        self.risk_policy = risk_policy

    def _compute(self, **params: Any) -> dict[str, Any]:
        state = self._reconstruct_state(params.get("date"))
        events = self.event_store.replay(params.get("date"))

        # Exposure metrics
        total_equity = state.cash + sum(
            pos["units"] * pos["avg_price"]
            for pos in state.positions.values()
        )

        positions_exposure = []
        total_exposure = Decimal("0")
        for symbol, pos in state.positions.items():
            notional = pos["units"] * pos["avg_price"]
            pct = (notional / total_equity * 100) if total_equity > 0 else Decimal("0")
            total_exposure += notional
            positions_exposure.append({
                "symbol": symbol,
                "notional": str(notional),
                "pct_of_equity": str(pct),
            })

        exposure_pct = (
            (total_exposure / total_equity * 100) if total_equity > 0 else Decimal("0")
        )

        # Drawdown
        peak_equity = self._compute_peak_equity(events)
        current_dd = (
            (peak_equity - total_equity) / peak_equity
            if peak_equity > 0 else Decimal("0")
        )

        # Daily PnL
        daily_pnl = self._compute_daily_pnl(events)

        # Kill switch state
        kill_switch = self._check_kill_switch(events, current_dd, daily_pnl, total_equity)

        # Risk limits from policy
        limits = {}
        if self.risk_policy:
            limits = {
                "max_position_size": str(self.risk_policy.position_sizing.max_position_size),
                "max_portfolio_drawdown": str(self.risk_policy.drawdown.max_portfolio_drawdown),
                "max_daily_loss": str(self.risk_policy.drawdown.max_daily_loss),
                "kill_switch_drawdown": str(self.risk_policy.drawdown.kill_switch_drawdown),
                "max_total_exposure": str(self.risk_policy.portfolio.max_total_exposure),
                "max_concentration": str(self.risk_policy.portfolio.max_concentration),
            }

        return {
            "total_equity": str(total_equity),
            "total_exposure": str(total_exposure),
            "exposure_pct": str(exposure_pct),
            "positions": positions_exposure,
            "position_count": len(positions_exposure),
            "drawdown": {
                "current": str(current_dd),
                "current_pct": str(current_dd * 100),
                "peak_equity": str(peak_equity),
            },
            "daily_pnl": str(daily_pnl),
            "kill_switch": kill_switch,
            "limits": limits,
            "risk_score": self._compute_risk_score(
                current_dd, daily_pnl, total_equity, exposure_pct
            ),
        }

    def _compute_peak_equity(self, events: list) -> Decimal:
        """Compute peak equity from equity snapshot events."""
        peak = Decimal("10000.0")
        for event in events:
            if event.event_type == EventType.EQUITY_SNAPSHOT:
                eq = Decimal(str(event.payload.get("equity", 0)))
                if eq > peak:
                    peak = eq
        return peak

    def _compute_daily_pnl(self, events: list) -> Decimal:
        """Compute today's PnL from fill events."""
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date()
        pnl = Decimal("0")
        for event in events:
            if event.event_type == EventType.ORDER_FILLED:
                if event.timestamp_exchange.date() == today:
                    p = event.payload
                    if p.get("pnl"):
                        pnl += Decimal(str(p["pnl"]))
        return pnl

    def _check_kill_switch(
        self, events: list, current_dd: Decimal, daily_pnl: Decimal, total_equity: Decimal
    ) -> dict[str, Any]:
        """Check kill switch conditions."""
        conditions = {
            "active": False,
            "reasons": [],
        }

        # Check if kill switch was triggered in recent events
        for event in events[-50:]:
            if event.event_type == EventType.ERROR:
                p = event.payload
                if p.get("type") == "RECONCILIATION_HALT":
                    conditions["active"] = True
                    conditions["reasons"].append(p.get("reason", "Reconciliation halt"))

        # Check drawdown limits
        if self.risk_policy:
            if current_dd > self.risk_policy.drawdown.kill_switch_drawdown:
                conditions["active"] = True
                conditions["reasons"].append(
                    f"Drawdown {current_dd:.2%} exceeds kill-switch "
                    f"{self.risk_policy.drawdown.kill_switch_drawdown:.2%}"
                )

            max_daily = self.risk_policy.drawdown.max_daily_loss * total_equity
            if daily_pnl < -max_daily:
                conditions["active"] = True
                conditions["reasons"].append(
                    f"Daily loss {daily_pnl} exceeds limit {-max_daily}"
                )

        return conditions

    @staticmethod
    def _compute_risk_score(
        drawdown: Decimal, daily_pnl: Decimal, equity: Decimal, exposure: Decimal
    ) -> str:
        """Compute overall risk score: low / medium / high / critical."""
        score = 0
        if drawdown > Decimal("0.10"):
            score += 3
        elif drawdown > Decimal("0.05"):
            score += 1

        if equity > 0 and daily_pnl < -equity * Decimal("0.03"):
            score += 2

        if exposure > Decimal("0.40"):
            score += 2
        elif exposure > Decimal("0.25"):
            score += 1

        if score >= 5:
            return "critical"
        elif score >= 3:
            return "high"
        elif score >= 1:
            return "medium"
        return "low"
