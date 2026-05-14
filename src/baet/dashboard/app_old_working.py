"""Main Streamlit app for BAET dashboard - Corrected version."""

import sys
from pathlib import Path

# Add src to path so we can import baet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import time
from datetime import datetime

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
    st.info("🟢 Observation Mode - No live data to display")
    st.warning("Configure live mode in config/live.yaml to see live data")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**BAET** - Binance Adaptive Ensemble Trader\n"
    f"Dashboard updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
