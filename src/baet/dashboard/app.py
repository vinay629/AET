"""Authoritative Streamlit dashboard for BAET stabilization."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

if TYPE_CHECKING:
    from baet.config.models import Settings

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

# Title - load config safely
try:
    from baet.config.loader import load_settings

    settings = load_settings()
    is_live_mode = settings.live.enabled if hasattr(settings, "live") and settings.live else False
except Exception as e:
    st.title("📈 BAET Dashboard")
    st.error(f"Config error: {e}")
    is_live_mode = False

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")

    # Mode indicator
    if is_live_mode:
        st.success("🔴 LIVE MODE ACTIVE")
    else:
        st.info("🟢 Observation Mode")

    st.divider()

    # Auto-refresh settings (non-blocking)
    auto_refresh = st.checkbox(
        "Auto Refresh", value=True, help="Automatically refresh dashboard data"
    )
    refresh_interval = st.slider(
        "Refresh Interval (seconds)",
        min_value=10,
        max_value=300,
        value=30,
        step=10,
        disabled=not auto_refresh,
        help="Time between automatic refreshes",
    )

    # Manual refresh button
    if st.button("🔄 Refresh Now", use_container_width=True):
        st.session_state.last_refresh = 0  # Force refresh
        st.rerun()

    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

def load_dashboard_payload(log_dir: str = LOG_DIR) -> dict[str, object]:
    """Load the paper-trading data needed by the dashboard."""
    portfolio_state = load_latest_state(log_dir)
    recent_trades = load_recent_trades(log_dir, limit=50)
    equity_df = load_equity_curve(log_dir)
    today = datetime.now().strftime("%Y-%m-%d")
    daily_summary = calculate_daily_summary(log_dir, date=today)
    metrics = calculate_performance_metrics(log_dir)

if auto_refresh:
    current_time = time.time()
    time_since_refresh = current_time - st.session_state.last_refresh

    if time_since_refresh > refresh_interval:
        st.session_state.last_refresh = current_time
        st.rerun()

    return {
        "portfolio_state": portfolio_state,
        "recent_trades": recent_trades,
        "equity_df": equity_df,
        "daily_summary": daily_summary,
        "metrics": metrics,
        "log_entries": log_entries,
        "today": today,
    }

# Add a toggle to load live data only when requested
if is_live_mode:
    load_live = st.sidebar.checkbox(
        "Load Live Data", value=False, help="Check to load live account data from Binance testnet"
    )
else:
    load_live = False

if is_live_mode and load_live:
    try:
        from baet.dashboard.data_loader import load_live_account_info_cached

        with st.spinner("Loading live account data (5s timeout)..."):
            account_info = load_live_account_info_cached(timeout_seconds=5)

        if account_info and account_info.get("success"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Value (USDT)", f"${account_info.get('total_usdt_value', 0):.2f}")
            with col2:
                st.metric("Account Type", account_info.get("account_type", "N/A"))
            with col3:
                can_trade = "✅ Yes" if account_info.get("can_trade") else "❌ No"
                st.metric("Can Trade", can_trade)

            # Show balances
            st.subheader("Account Balances (Testnet)")
            balances = account_info.get("balances", {})

            cols = st.columns(4)
            with cols[0]:
                if "BTC" in balances:
                    btc = balances["BTC"]
                    st.metric("BTC", f"{btc['total']:.6f}")
            with cols[1]:
                if "ETH" in balances:
                    eth = balances["ETH"]
                    st.metric("ETH", f"{eth['total']:.6f}")
            with cols[2]:
                if "USDT" in balances:
                    usdt = balances["USDT"]
                    st.metric("USDT", f"${usdt['total']:.2f}")
            with cols[3]:
                if "BNB" in balances:
                    bnb = balances["BNB"]
                    st.metric("BNB", f"{bnb['total']:.6f}")
        else:
            err_msg = account_info.get("error", "Unknown error") if account_info else "Not loaded"
            st.error(f"Cannot load account: {err_msg}")
    except Exception as e:
        st.error(f"Error loading live account: {e}")
else:
    # Load paper trading data from logs
    try:
        from baet.dashboard.data_loader import (
            calculate_daily_summary,
            calculate_performance_metrics,
            find_latest_log_file,
            load_equity_curve,
            load_latest_state,
            load_recent_trades,
            parse_log_file,
        )

        # Load data from paper trading logs
        log_dir = "logs/paper"
        portfolio_state = load_latest_state(log_dir)
        recent_trades = load_recent_trades(log_dir, limit=50)
        equity_df = load_equity_curve(log_dir)
        today = datetime.now().strftime("%Y-%m-%d")
        daily_summary = calculate_daily_summary(log_dir, date=today)
        metrics = calculate_performance_metrics(log_dir)

        # Recent log entries
        log_file = find_latest_log_file(log_dir)
        log_entries = parse_log_file(log_file, max_entries=100) if log_file else []
    except Exception as e:
        st.error(f"Error loading dashboard data: {e}")
        portfolio_state = {}
        recent_trades = []
        equity_df = pd.DataFrame()
        daily_summary = {}
        metrics = {}
        log_entries = []

    # Main content
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Overview", "Positions", "Trades", "Performance", "Logs"]
    )

    with tab1:
        st.header("Portfolio Overview")

        # Portfolio overview
        render_portfolio_overview(portfolio_state)

        # Equity and Win Rate Charts
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

        # Brain Transparency
        render_brain_transparency(log_entries)

        # Daily summary
        st.subheader("Today's Summary")
        render_daily_summary(daily_summary)

    with tab2:
        st.header("Current Positions")

        positions = portfolio_state.get("positions", {})
        render_positions_table(positions)

    with tab3:
        st.header("Recent Trades")

        render_recent_trades(recent_trades, limit=50)

    with tab4:
        st.header("Performance Metrics")

        # Performance metrics
        render_performance_metrics(metrics)

        # Equity chart (full width)
        st.subheader("Equity Curve (Detailed)")
        render_equity_chart(equity_df, key="performance_equity")

        # Export button
        if not equity_df.empty:
            csv = equity_df.to_csv(index=False)
            st.download_button(
                label="Download Equity Curve (CSV)",
                data=csv_data,
                file_name=f"baet_equity_curve_{today}.csv",
                mime="text/csv",
            )

    with tab5:
        st.header("Log Viewer")

        render_log_viewer(log_entries, max_entries=100)

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**BAET** - Binance Adaptive Ensemble Trader\n"
        f"Dashboard updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


if __name__ == "__main__":
    main()
