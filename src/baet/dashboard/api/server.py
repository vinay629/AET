"""FastAPI dashboard server for BAET.

Read-only API that serves materialized views derived from the event journal.
Never mutates state. Never queries the exchange directly.

Architecture:
    Event Journal → Materialized Views → FastAPI → React Dashboard
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from baet.core.events import EventStore
from baet.core.health import HealthMonitor
from baet.core.certify import Certifier
from baet.core.snapshot import SnapshotManager
from baet.dashboard.views import (
    PortfolioView,
    HealthView,
    RiskView,
    ReplayView,
    MarketView,
    StrategyView,
    AuditView,
    ResearchView,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application state (injected, not global mutable state)
# ---------------------------------------------------------------------------


class DashboardState:
    """Immutable dashboard configuration. Set once at startup."""

    def __init__(
        self,
        event_store: EventStore,
        health_monitor: HealthMonitor | None = None,
        certifier: Certifier | None = None,
        snapshot_manager: SnapshotManager | None = None,
        ui_dir: Path | None = None,
    ) -> None:
        self.event_store = event_store
        self.health_monitor = health_monitor
        self.certifier = certifier
        self.snapshot_manager = snapshot_manager
        self.ui_dir = ui_dir

        # Materialized views (read-only, event-derived)
        self.portfolio_view = PortfolioView(event_store, cache_ttl=1.0)
        self.health_view = HealthView(event_store, health_monitor, cache_ttl=0.5)
        self.risk_view = RiskView(event_store, cache_ttl=1.0)
        self.replay_view = ReplayView(event_store, certifier, cache_ttl=5.0)
        self.market_view = MarketView(event_store, cache_ttl=1.0)
        self.strategy_view = StrategyView(event_store, cache_ttl=1.0)
        self.audit_view = AuditView(event_store, cache_ttl=0.5)
        self.research_view = ResearchView(event_store, cache_ttl=2.0)

        # WebSocket connections for live streaming
        self._ws_connections: list[WebSocket] = []


# Global reference set at startup (read-only after init)
_state: DashboardState | None = None


def get_state() -> DashboardState:
    if _state is None:
        raise RuntimeError("Dashboard state not initialized")
    return _state


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("Dashboard API starting")
    yield
    logger.info("Dashboard API shutting down")
    # Close all WebSocket connections
    state = get_state()
    for ws in state._ws_connections:
        try:
            await ws.close()
        except Exception:
            pass


app = FastAPI(
    title="BAET Dashboard",
    description="Read-only event-derived dashboard for BAET trading infrastructure",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Mount static files (React build output)
# ---------------------------------------------------------------------------

def mount_static_files():
    """Mount the React build output if it exists."""
    state = get_state()
    if state.ui_dir and (state.ui_dir / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=str(state.ui_dir / "assets")), name="assets")
        logger.info(f"Mounted static files from {state.ui_dir}")


# ---------------------------------------------------------------------------
# API Routes — all read-only, all derived from materialized views
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def get_health() -> dict[str, Any]:
    """System health overview."""
    return get_state().health_view.refresh()


@app.get("/api/portfolio")
async def get_portfolio(date: str | None = None) -> dict[str, Any]:
    """Portfolio state — equity, positions, PnL, drawdown."""
    return get_state().portfolio_view.refresh(date=date)


@app.get("/api/risk")
async def get_risk(date: str | None = None) -> dict[str, Any]:
    """Risk metrics — exposure, drawdown, kill switch, limits."""
    return get_state().risk_view.refresh(date=date)


@app.get("/api/market")
async def get_market(
    symbol: str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="1h"),
    limit: int = Query(default=100, le=1000),
    date: str | None = None,
) -> dict[str, Any]:
    """Market data — candles from event journal."""
    return get_state().market_view.refresh(
        symbol=symbol, timeframe=timeframe, limit=limit, date=date
    )


@app.get("/api/strategy")
async def get_strategy(date: str | None = None) -> dict[str, Any]:
    """Strategy signals, decisions, and traces."""
    return get_state().strategy_view.refresh(date=date)


@app.get("/api/replay")
async def get_replay(date: str | None = None) -> dict[str, Any]:
    """Replay and certification status."""
    return get_state().replay_view.refresh(date=date)


@app.get("/api/audit")
async def get_audit(
    event_id: str | None = None,
    order_id: str | None = None,
    symbol: str | None = None,
    event_type: str | None = None,
    date: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
) -> dict[str, Any]:
    """Event explorer with search and hash chain verification."""
    return get_state().audit_view.refresh(
        event_id=event_id,
        order_id=order_id,
        symbol=symbol,
        event_type=event_type,
        date=date,
        limit=limit,
        offset=offset,
    )


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Combined status for the top status strip."""
    state = get_state()
    health = state.health_view.refresh()
    portfolio = state.portfolio_view.refresh()
    risk = state.risk_view.refresh()

    return {
        "engine": health.get("engine_status", "UNKNOWN"),
        "equity": portfolio.get("equity", "0"),
        "total_pnl": portfolio.get("total_pnl", "0"),
        "total_pnl_pct": portfolio.get("total_pnl_pct", "0"),
        "drawdown": risk.get("drawdown", {}).get("current_pct", "0"),
        "kill_switch": risk.get("kill_switch", {}).get("active", False),
        "risk_score": risk.get("risk_score", "unknown"),
        "event_count": health.get("event_pipeline", {}).get("total_events", 0),
        "latest_sequence": health.get("event_pipeline", {}).get("latest_sequence", 0),
        "invariants": health.get("invariants", {}).get("status", "unknown"),
    }


# ---------------------------------------------------------------------------
# Research & ML Terminal API
# ---------------------------------------------------------------------------


@app.get("/api/research")
async def get_research() -> dict[str, Any]:
    """Full research dashboard payload (labels, features, CV, models, derivatives)."""
    return get_state().research_view.refresh()


@app.get("/api/research/labels")
async def get_research_labels(
    symbol: str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="1h"),
    atr_window: int = Query(default=14, ge=1, le=200),
    atr_multiplier: float = Query(default=2.0, ge=0.5, le=10.0),
    timeout_bars: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Label quality data with configurable barrier parameters."""
    return get_state().research_view.get_labels(
        symbol=symbol,
        timeframe=timeframe,
        atr_window=atr_window,
        atr_multiplier=atr_multiplier,
        timeout_bars=timeout_bars,
    )


@app.get("/api/research/cv-splits")
async def get_research_cv_splits(
    n_samples: int = Query(default=500, ge=100, le=10000),
    n_splits: int = Query(default=5, ge=2, le=10),
    purge_gap: int = Query(default=2, ge=0, le=20),
    embargo_gap: int = Query(default=1, ge=0, le=10),
    label_horizon: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """PurgedKFold cross-validation split visualization data."""
    return get_state().research_view.get_cv_splits(
        n_samples=n_samples,
        n_splits=n_splits,
        purge_gap=purge_gap,
        embargo_gap=embargo_gap,
        label_horizon=label_horizon,
    )


@app.get("/api/research/models")
async def get_research_models() -> dict[str, Any]:
    """Model registry comparison data."""
    return get_state().research_view.get_models()


@app.get("/api/research/derivatives")
async def get_research_derivatives(
    symbol: str = Query(default="BTCUSDT"),
) -> dict[str, Any]:
    """Derivatives microstructure data (OI, funding, liquidations)."""
    return get_state().research_view.get_derivatives(symbol=symbol)


# ---------------------------------------------------------------------------
# WebSocket — live event stream
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Stream live events to connected clients."""
    await websocket.accept()
    state = get_state()
    state._ws_connections.append(websocket)

    try:
        # Send initial state
        await websocket.send_json({
            "type": "init",
            "data": await get_status(),
        })

        # Keep connection alive, push updates periodically
        while True:
            await asyncio.sleep(1)
            status = await get_status()
            await websocket.send_json({
                "type": "status",
                "data": status,
            })
    except WebSocketDisconnect:
        state._ws_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in state._ws_connections:
            state._ws_connections.remove(websocket)


# ---------------------------------------------------------------------------
# Serve React app (catch-all for SPA routing)
# ---------------------------------------------------------------------------


@app.get("/terminal", response_class=HTMLResponse)
async def serve_terminal():
    """Serve the quantitative intelligence terminal."""
    terminal_path = Path(__file__).parent.parent / "quant_terminal.html"
    if terminal_path.exists():
        return HTMLResponse(content=terminal_path.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(content="<h1>Terminal not found</h1>", status_code=404)


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_react(full_path: str):
    """Serve the React SPA for all non-API routes."""
    # Don't intercept API or terminal routes
    if full_path.startswith("api/") or full_path == "terminal":
        return HTMLResponse(content="", status_code=404)
    state = get_state()
    if state.ui_dir:
        index_path = state.ui_dir / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(), status_code=200)
    # Default: redirect to terminal
    terminal_path = Path(__file__).parent / "quant_terminal.html"
    if terminal_path.exists():
        return HTMLResponse(content=terminal_path.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(
        content="<h1>BAET Dashboard</h1><p>UI not built yet. Use API endpoints directly.</p>",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# Startup helper
# ---------------------------------------------------------------------------

def create_app(
    event_store: EventStore,
    health_monitor: HealthMonitor | None = None,
    certifier: Certifier | None = None,
    snapshot_manager: SnapshotManager | None = None,
    ui_dir: Path | None = None,
) -> FastAPI:
    """Create and configure the dashboard app."""
    global _state
    _state = DashboardState(
        event_store=event_store,
        health_monitor=health_monitor,
        certifier=certifier,
        snapshot_manager=snapshot_manager,
        ui_dir=ui_dir,
    )
    mount_static_files()
    return app
