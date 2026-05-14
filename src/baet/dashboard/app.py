"""Authoritative Streamlit dashboard for BAET stabilization."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from baet.config.models import Settings

import pandas as pd
import streamlit as st

from baet.dashboard.components import (
    render_brain_transparency,
    render_daily_summary,
    render_equity_chart,
    render_log_viewer,
    render_performance_metrics,
    render_portfolio_overview,
    render_positions_table,
    render_recent_trades,
    render_win_rate_chart,
)
from baet.dashboard.data_loader import (
    calculate_daily_summary,
    calculate_performance_metrics,
    find_latest_log_file,
    load_equity_curve,
    load_latest_state,
    load_recent_trades,
    parse_log_file,
)

LOG_DIR = "logs/paper"


def load_dashboard_payload(log_dir: str = LOG_DIR) -> dict[str, object]:
    """Load the paper-trading data needed by the dashboard."""
    portfolio_state = load_latest_state(log_dir)
    recent_trades = load_recent_trades(log_dir, limit=50)
    equity_df = load_equity_curve(log_dir)
    today = datetime.now().strftime("%Y-%m-%d")
    daily_summary = calculate_daily_summary(log_dir, date=today)
    metrics = calculate_performance_metrics(log_dir)

    log_file = find_latest_log_file(log_dir)
    log_entries = parse_log_file(log_file, max_entries=100) if log_file else []

    return {
        "portfolio_state": portfolio_state,
        "recent_trades": recent_trades,
        "equity_df": equity_df,
        "daily_summary": daily_summary,
        "metrics": metrics,
        "log_entries": log_entries,
        "today": today,
    }


def render_dashboard(payload: dict[str, object]) -> None:
    """Render the paper-trading dashboard tabs."""
    portfolio_state = payload["portfolio_state"]
    recent_trades = payload["recent_trades"]
    equity_df = payload["equity_df"]
    daily_summary = payload["daily_summary"]
    metrics = payload["metrics"]
    log_entries = payload["log_entries"]
    today = payload["today"]

    st.header("Paper Trading Overview")
    st.caption("Authoritative paper-first dashboard for the stabilized BAET core path.")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Overview", "Positions", "Trades", "Performance", "Logs"]
    )

    with tab1:
        render_portfolio_overview(portfolio_state if isinstance(portfolio_state, dict) else {})

        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("Equity Curve")
            render_equity_chart(
                equity_df if isinstance(equity_df, pd.DataFrame) else pd.DataFrame(),
                key="overview_equity",
            )
        with col_right:
            st.subheader("Win Rate")
            render_win_rate_chart(
                equity_df if isinstance(equity_df, pd.DataFrame) else pd.DataFrame(),
                window=1000,
            )

        render_brain_transparency(log_entries if isinstance(log_entries, list) else [])

        st.subheader("Today's Summary")
        render_daily_summary(daily_summary if isinstance(daily_summary, dict) else {})

    with tab2:
        positions = {}
        if isinstance(portfolio_state, dict):
            positions = portfolio_state.get("positions", {})
        render_positions_table(positions if isinstance(positions, dict) else {})

    with tab3:
        render_recent_trades(recent_trades if isinstance(recent_trades, list) else [], limit=50)

    with tab4:
        render_performance_metrics(metrics if isinstance(metrics, dict) else {})
        st.subheader("Equity Curve (Detailed)")
        equity = equity_df if isinstance(equity_df, pd.DataFrame) else pd.DataFrame()
        render_equity_chart(equity, key="performance_equity")
        if not equity.empty:
            csv_data = equity.to_csv(index=False)
            st.download_button(
                label="Download Equity Curve (CSV)",
                data=csv_data,
                file_name=f"baet_equity_curve_{today}.csv",
                mime="text/csv",
            )

    with tab5:
        render_log_viewer(log_entries if isinstance(log_entries, list) else [], max_entries=100)


def main() -> None:
    """Run the Streamlit dashboard."""
    st.set_page_config(
        page_title="BAET Dashboard",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📈 BAET Dashboard")

    with st.sidebar:
        st.header("Configuration")
        st.info("Paper mode dashboard")
        if st.button("Refresh", use_container_width=True):
            st.rerun()
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    try:
        payload = load_dashboard_payload()
    except Exception as error:
        st.error(f"Failed to load paper-trading data: {error}")
        payload = {
            "portfolio_state": {},
            "recent_trades": [],
            "equity_df": pd.DataFrame(),
            "daily_summary": {},
            "metrics": {},
            "log_entries": [],
            "today": datetime.now().strftime("%Y-%m-%d"),
        }

    render_dashboard(payload)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**BAET** - Binance Adaptive Ensemble Trader\n"
        f"Dashboard updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


if __name__ == "__main__":
    main()
