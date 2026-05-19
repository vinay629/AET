"""Materialized views for the BAET dashboard.

Views are read-only, event-derived projections of system state.
They are computed from the event journal + reducer, never from
direct exchange queries or mutable global state.

Architecture:
    Event Journal → Reducer → Materialized View → API → UI

Views are recomputed on demand or cached with TTL.
They NEVER mutate state or call the exchange directly.
"""

from baet.dashboard.views.portfolio_view import PortfolioView
from baet.dashboard.views.health_view import HealthView
from baet.dashboard.views.risk_view import RiskView
from baet.dashboard.views.replay_view import ReplayView
from baet.dashboard.views.market_view import MarketView
from baet.dashboard.views.strategy_view import StrategyView
from baet.dashboard.views.audit_view import AuditView

__all__ = [
    "PortfolioView",
    "HealthView",
    "RiskView",
    "ReplayView",
    "MarketView",
    "StrategyView",
    "AuditView",
]
