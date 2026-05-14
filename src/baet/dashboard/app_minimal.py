"""Minimal Streamlit app for BAET dashboard - for testing."""

import streamlit as st
import time
from datetime import datetime

# Page config
st.set_page_config(
    page_title="BAET Dashboard - Test",
    page_icon="📈",
    layout="wide",
)

# Title
st.title("📈 BAET Dashboard - Test Mode")
st.caption("Testing data streaming fix")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")

    # Auto-refresh settings
    auto_refresh = st.checkbox("Auto Refresh", value=True)
    refresh_interval = st.slider("Refresh (seconds)", 10, 300, 30, disabled=not auto_refresh)

    if st.button("🔄 Refresh Now", use_container_width=True):
        st.session_state.last_refresh = 0
        st.rerun()

    # Non-blocking auto-refresh
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = time.time()

    current_time = time.time()
    time_since_refresh = current_time - st.session_state.last_refresh

    if auto_refresh and time_since_refresh > refresh_interval:
        st.session_state.last_refresh = current_time
        st.rerun()

    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

# Main content
st.header("Portfolio Overview")

# Show some test data
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Test Value", "$10,000.00")
with col2:
    st.metric("Test Return", "5.2%")
with col3:
    st.metric("Test Positions", "3")

st.info("✅ Dashboard is working! Data streaming fix applied.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**BAET** - Binance Adaptive Ensemble Trader\n"
    f"Dashboard updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
