"""Strategy view — read-only projection of strategy signals and decisions.

Derived from event journal (signal events, risk decision events, order events).
"""

from __future__ import annotations

from typing import Any

from baet.dashboard.views.base import MaterializedView
from baet.core.events import EventType


class StrategyView(MaterializedView):
    """Read-only strategy signal and decision projection."""

    def __init__(self, event_store, cache_ttl: float = 1.0) -> None:
        super().__init__(event_store, cache_ttl)

    def _compute(self, **params: Any) -> dict[str, Any]:
        date = params.get("date")
        events = self.event_store.replay(date)

        # Signal stream
        signals = []
        for event in events:
            if event.event_type == EventType.SIGNAL_GENERATED:
                p = event.payload
                signals.append({
                    "timestamp": event.timestamp_exchange.isoformat(),
                    "symbol": p.get("symbol", ""),
                    "action": p.get("action", "HOLD"),
                    "confidence": p.get("confidence", 0),
                    "strategy": p.get("strategy_name", ""),
                    "reason": p.get("reason", ""),
                })

        # Risk decisions
        risk_decisions = []
        for event in events:
            if event.event_type == EventType.RISK_DECISION:
                p = event.payload
                risk_decisions.append({
                    "timestamp": event.timestamp_exchange.isoformat(),
                    "symbol": p.get("symbol", ""),
                    "action": p.get("action", ""),
                    "approved": p.get("approved", False),
                    "reason": p.get("reason", ""),
                    "risk_score": p.get("risk_score", 0),
                })

        # Decision traces (candle → signal → risk → order → fill)
        traces = self._build_decision_traces(events)

        # Per-strategy stats
        strategy_stats = self._compute_strategy_stats(events)

        return {
            "signals": signals[-50:],  # Last 50
            "signal_count": len(signals),
            "risk_decisions": risk_decisions[-50:],
            "decision_traces": traces,
            "strategy_stats": strategy_stats,
        }

    def _build_decision_traces(self, events: list) -> list[dict]:
        """Build decision traces: candle → signal → risk → order → fill."""
        traces = []
        current_trace = {}

        for event in events:
            p = event.payload

            if event.event_type == EventType.CANDLE_RECEIVED:
                if current_trace:
                    traces.append(current_trace)
                current_trace = {
                    "timestamp": event.timestamp_exchange.isoformat(),
                    "symbol": p.get("symbol", ""),
                    "candle": {
                        "open": p.get("open"),
                        "close": p.get("close"),
                        "volume": p.get("volume"),
                    },
                }

            elif event.event_type == EventType.SIGNAL_GENERATED and current_trace:
                current_trace["signal"] = {
                    "action": p.get("action"),
                    "confidence": p.get("confidence"),
                    "strategy": p.get("strategy_name"),
                }

            elif event.event_type == EventType.RISK_DECISION and current_trace:
                current_trace["risk"] = {
                    "approved": p.get("approved"),
                    "reason": p.get("reason"),
                }

            elif event.event_type == EventType.ORDER_SUBMITTED and current_trace:
                current_trace["order"] = {
                    "client_order_id": p.get("client_order_id"),
                    "side": p.get("side"),
                    "quantity": p.get("quantity"),
                }

            elif event.event_type == EventType.ORDER_FILLED and current_trace:
                current_trace["fill"] = {
                    "price": p.get("price"),
                    "units": p.get("units"),
                    "fee": p.get("fee"),
                }
                traces.append(current_trace)
                current_trace = {}

        if current_trace:
            traces.append(current_trace)

        return traces[-20:]  # Last 20 traces

    def _compute_strategy_stats(self, events: list) -> dict[str, dict]:
        """Compute per-strategy statistics."""
        stats: dict[str, dict] = {}

        for event in events:
            if event.event_type == EventType.SIGNAL_GENERATED:
                name = event.payload.get("strategy_name", "unknown")
                if name not in stats:
                    stats[name] = {"signals": 0, "buys": 0, "sells": 0, "holds": 0}
                stats[name]["signals"] += 1
                action = event.payload.get("action", "HOLD")
                if action == "BUY":
                    stats[name]["buys"] += 1
                elif action == "SELL":
                    stats[name]["sells"] += 1
                else:
                    stats[name]["holds"] += 1

        return stats
