"""Main Streamlit app for BAET dashboard - Fixed version."""

import sys
from pathlib import Path

# Add src to path so we can import baet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time
from datetime import datetime

import streamlit as st

# Page config
st.set_page_config(
    page_title="BAET Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Title - load config safely
try:
    from baet.config.loader import load_settings

    settings = load_settings()
    is_live_mode = settings.live.enabled if hasattr(settings, "live") and settings.live else False

    if is_live_mode:
        st.title("📈 BAET Live Trading Dashboard (Testnet)")
        st.caption("Environment: Testnet • Real-time demo trading")
    else:
        st.title("📈 BAET Observation Dashboard")
        st.caption("Market observation mode • No trading active")
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

# Non-blocking auto-refresh using session state (outside sidebar for proper execution)
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if auto_refresh:
    current_time = time.time()
    time_since_refresh = current_time - st.session_state.last_refresh

    if time_since_refresh > refresh_interval:
        st.session_state.last_refresh = current_time
        st.rerun()

# Main content
st.header("Portfolio Overview")

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
            st.error(
                f"Cannot load account: {account_info.get('error', 'Unknown error') if account_info else 'Not loaded'}"
            )
    except Exception as e:
        st.error(f"Error loading live account: {e}")
else:
    # Load paper trading data from logs
    try:
        from datetime import datetime as dt

        from baet.dashboard.data_loader import (
            calculate_daily_summary,
            calculate_performance_metrics,
            load_equity_curve,
            load_latest_state,
            load_recent_trades,
        )

        # Load data from paper trading logs
        log_dir = "logs/paper"
        portfolio_state = load_latest_state(log_dir)
        recent_trades = load_recent_trades(log_dir, limit=50)
        equity_df = load_equity_curve(log_dir)
        today = dt.now().strftime("%Y-%m-%d")
        daily_summary = calculate_daily_summary(log_dir, date=today)
        metrics = calculate_performance_metrics(log_dir)

        # Show portfolio overview
        if portfolio_state:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Portfolio Value", f"${portfolio_state.get('total_value', 0):.2f}")
            with col2:
                cash = portfolio_state.get("cash", 0)
                st.metric("Cash", f"${cash:.2f}")
            with col3:
                positions_count = len(
                    [
                        p
                        for p in portfolio_state.get("positions", {}).values()
                        if p.get("amount", 0) > 0
                    ]
                )
                st.metric("Open Positions", positions_count)

            # Show positions
            st.subheader("Current Positions")
            positions = portfolio_state.get("positions", {})
            if positions:
                import pandas as pd

                pos_data = []
                for symbol, pos in positions.items():
                    if pos.get("amount", 0) > 0:
                        pos_data.append(
                            {
                                "Symbol": symbol,
                                "Amount": pos.get("amount", 0),
                                "Entry Price": pos.get("entry_price", 0),
                                "Current Value": pos.get("current_value", 0),
                            }
                        )
                if pos_data:
                    df = pd.DataFrame(pos_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No open positions")
            else:
                st.info("No position data available")

            # Show recent trades
            if recent_trades:
                st.subheader("Recent Trades")
                import pandas as pd

                trades_df = pd.DataFrame(recent_trades)
                st.dataframe(trades_df, use_container_width=True)

            # Show equity curve
            if not equity_df.empty:
                st.subheader("Equity Curve")
                st.line_chart(equity_df.set_index("timestamp")["total_value"])

    except Exception as e:
        st.error(f"Error loading paper trading data: {e}")
        st.info("🟢 Observation Mode - No live data to display")

        # Show placeholder data as fallback
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Portfolio Value", "$10,000.00 (demo)")
        with col2:
            st.metric("Daily P&L", "+$52.30 (+0.52%)")
        with col3:
            st.metric("Open Positions", "0")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**BAET** - Binance Adaptive Ensemble Trader\n"
    f"Dashboard updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
