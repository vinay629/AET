from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_dashboard_payload_loader_handles_missing_logs() -> None:
    from baet.dashboard.app import load_dashboard_payload

    payload = load_dashboard_payload(log_dir="logs/does-not-exist")

    assert payload["portfolio_state"] == {}
    assert payload["recent_trades"] == []
    assert isinstance(payload["equity_df"], pd.DataFrame)
    assert payload["daily_summary"] == {}
    assert payload["metrics"] == {}
    assert payload["log_entries"] == []


def test_dashboard_module_imports_cleanly() -> None:
    from baet.dashboard import app

    assert hasattr(app, "main")
    assert hasattr(app, "render_dashboard")
