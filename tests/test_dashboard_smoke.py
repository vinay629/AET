from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_data_loader_handles_missing_logs() -> None:
    from baet.dashboard.data_loader import (
        find_latest_log_file,
        load_equity_curve,
        load_latest_state,
        parse_log_file,
    )

    assert find_latest_log_file("logs/does-not-exist") is None
    assert load_latest_state("logs/does-not-exist") == {}
    assert isinstance(load_equity_curve("logs/does-not-exist"), pd.DataFrame)
    assert parse_log_file(Path("logs/does-not-exist/fake.log")) == []


def test_api_server_imports_cleanly() -> None:
    from baet.dashboard.web import api_server

    assert hasattr(api_server, "app")
    assert hasattr(api_server, "get_status")
    assert hasattr(api_server, "get_portfolio")
    assert hasattr(api_server, "get_equity")
    assert hasattr(api_server, "get_trades")
    assert hasattr(api_server, "get_positions")
    assert hasattr(api_server, "get_logs")
    assert hasattr(api_server, "get_performance")
    assert hasattr(api_server, "get_ohlcv")
    assert hasattr(api_server, "get_ai_signal")
    assert hasattr(api_server, "get_symbols")
    assert hasattr(api_server, "get_daily_summary")


def test_api_endpoints_return_valid_json() -> None:
    from baet.dashboard.web.api_server import app

    client = app.test_client()

    endpoints = [
        "/",
        "/api/status",
        "/api/portfolio",
        "/api/equity",
        "/api/trades",
        "/api/positions",
        "/api/logs",
        "/api/performance",
        "/api/ai-signal",
        "/api/symbols",
        "/api/daily-summary",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code in (200, 308), f"{endpoint} returned {response.status_code}"
        if response.status_code == 200:
            assert response.content_type.startswith("application/json") or endpoint == "/"
