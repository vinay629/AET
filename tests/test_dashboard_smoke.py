"""Smoke tests for the BAET Flask dashboard API server and JSONL data loader.

Verifies:
- Documented Python callables are importable from the api_server module
- All GET-accepting API endpoints return HTTP 200 with JSON content-type
- POST-only engine endpoints accept POST with a valid JSON body
- Log-data helper gracefully handles absent files
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from baet.dashboard.data_loader import (  # noqa: E402
    find_latest_log_file,
    load_equity_curve,
    load_latest_state,
    parse_log_file,
)

# ---------------------------------------------------------------------------
# Data loader smoke tests
# ---------------------------------------------------------------------------


class TestDataLoaderMissingFiles:
    def test_find_latest_log_missing_dir(self):
        assert find_latest_log_file("logs/does-not-exist") is None

    def test_load_latest_state_missing_dir(self):
        assert load_latest_state("logs/does-not-exist") == {}

    def test_load_equity_curve_missing_dir(self):
        df = load_equity_curve("logs/does-not-exist")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_parse_missing_file(self):
        assert parse_log_file(Path("logs/does-not-exist/fake.log")) == []


# ---------------------------------------------------------------------------
# Endpoint definitions split by HTTP method
# ---------------------------------------------------------------------------

# GET endpoints — each must return HTTP 200 + JSON
_GET_ENDPOINTS = [
    "/api/status",
    "/api/ohlcv/BTCUSDT?timeframe=1h&limit=10",
    "/api/ticker/BTCUSDT",
    "/api/tickers",
    "/api/orderbook/BTCUSDT?limit=10",
    "/api/binance-trades/BTCUSDT?limit=5",
    "/api/market-summary",
    "/api/symbols",
    "/api/portfolio",
    "/api/equity",
    "/api/trades",
    "/api/positions",
    "/api/logs",
    "/api/performance",
    "/api/ai-signal",
    "/api/daily-summary",
    "/api/engine/status",
]

# POST endpoints — must accept POST and return JSON
_POST_ENDPOINTS = [
    "/api/engine/start",
    "/api/engine/stop",
    "/api/order",
]

# All endpoint paths (no HTTP-method qualifier)
_ALL_ENDPOINTS = ["/"] + _GET_ENDPOINTS + _POST_ENDPOINTS


# ---------------------------------------------------------------------------
# Import smoke
# ---------------------------------------------------------------------------


class TestApiServerSymbols:
    """Documented callable objects must be present on the module."""

    @pytest.fixture(scope="class")
    def api_server_module(self):
        from baet.dashboard.web import api_server

        return api_server

    @pytest.mark.parametrize(
        "attr",
        [
            "app",
            "get_status",
            "get_portfolio",
            "get_equity",
            "get_trades",
            "get_positions",
            "get_logs",
            "get_performance",
            "get_ai_signal",
            "get_symbols",
            "get_daily_summary",
            "get_ohlcv",
        ],
    )
    def test_symbol_exported(self, api_server_module, attr):
        assert hasattr(
            api_server_module, attr
        ), f"baet.dashboard.web.api_server is missing attribute '{attr}'"


# ---------------------------------------------------------------------------
# GET endpoint smoke
# ---------------------------------------------------------------------------


class TestApiServerGetEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        from baet.dashboard.web.api_server import app

        return app.test_client()

    @pytest.mark.parametrize("endpoint", _GET_ENDPOINTS)
    def test_returns_200(self, client, endpoint):
        r = client.get(endpoint)
        assert (
            r.status_code == 200
        ), f"{endpoint!r} → {r.status_code}: {r.get_data(as_text=True)[:200]!r}"

    @pytest.mark.parametrize("endpoint", _GET_ENDPOINTS)
    def test_returns_json(self, client, endpoint):
        r = client.get(endpoint)
        assert r.content_type.startswith(
            "application/json"
        ), f"{endpoint!r} returned content-type {r.content_type!r}, expected JSON"

    def test_root_returns_html(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "html" in r.content_type


# ---------------------------------------------------------------------------
# POST endpoint smoke
# ---------------------------------------------------------------------------


class TestApiServerPostEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        from baet.dashboard.web.api_server import app

        return app.test_client()

    @pytest.mark.parametrize("endpoint", _POST_ENDPOINTS)
    def test_accepts_post(self, client, endpoint):
        """POST endpoints must not return 405 Method Not Allowed."""
        r = client.post(endpoint, json={})
        assert (
            r.status_code != 405
        ), f"{endpoint!r} returned 405 (Method Not Allowed) — POST not registered"
        assert r.content_type.startswith(
            "application/json"
        ), f"{endpoint!r} POST returned content-type {r.content_type!r}, expected JSON"
