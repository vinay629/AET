"""Main Streamlit app for BAET dashboard."""

import sys
from pathlib import Path

# Add src to path so we can import baet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Try to import streamlit
try:
    import streamlit as st
except ImportError:
    # Allow importing without streamlit (for testing)
    st = None

# Only define the dashboard if streamlit is available
if st is not None:
    # Import components and data loader
    from baet.dashboard.components import (
        render_portfolio_overview,
        render_positions_table,
        render_recent_trades,
        render_performance_metrics,
        render_equity_chart,
        render_daily_summary,
        render_risk_status,
        render_log_viewer,
    )
    from baet.dashboard.data_loader import (
        load_latest_state,
        load_recent_trades,
        load_equity_curve,
        calculate_daily_summary,
        calculate_performance_metrics,
        find_latest_log_file,
        parse_log_file,
    )
    
    # Page config with explicit light theme
    st.set_page_config(
        page_title="BAET Dashboard",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Force light theme configuration
    st._config.set_option("theme.base", "light")
    st._config.set_option("theme.primaryColor", "#007bff")
    st._config.set_option("theme.backgroundColor", "#ffffff")
    st._config.set_option("theme.secondaryBackgroundColor", "#f8f9fa")
    st._config.set_option("theme.textColor", "#000000")
    
    # Custom CSS for maximum visibility and contrast
    # Using aggressive !important overrides to ensure visibility
    st.markdown(
        """
        <style>
        /* Force all text to be visible - global override */
        * {
            color: #000000 !important;
        }
        
        /* Force ALL backgrounds to be white/light - comprehensive override */
        *, *::before, *::after {
            background-color: transparent !important;
        }
        
        /* Main content area - pure white background */
        .main > div, .main, .block-container, .stApp {
            padding-top: 2rem;
            background-color: #ffffff !important;
        }
        
        /* All text elements - force black color */
        p, span, div, label, h1, h2, h3, h4, h5, h6, li, td, th, a, button {
            color: #000000 !important;
            background-color: transparent !important;
        }
        
        /* Streamlit specific elements */
        .stText, .stMarkdown, .stHeader, .stSubheader {
            color: #000000 !important;
            background-color: transparent !important;
        }
        
        /* Force all backgrounds to be light */
        .main, .block-container, .stApp, body, html {
            background-color: #ffffff !important;
        }
        
        /* Tab headers - ensure they have white backgrounds and black text */
        [data-baseweb="tab"], [data-baseweb="tab"] * {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #cccccc !important;
        }
        
        /* Active tab - make sure it's distinguishable */
        [data-baseweb="tab"][aria-selected="true"] {
            background-color: #f0f0f0 !important;
            color: #000000 !important;
            border-bottom: 3px solid #007bff !important;
        }
        
        /* Tab content areas - white background */
        [data-baseweb="tab-panel"] {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        
        /* Chart containers - white background */
        .stPlotlyChart, .plotly-graph-div, .js-plotly-plot {
            background-color: #ffffff !important;
        }
        
        /* Chart titles and labels - black text */
        .plotly .gtitle, .plotly text {
            fill: #000000 !important;
            color: #000000 !important;
        }
        
        /* Metrics - maximum contrast */
        .stMetric {
            background-color: #f8f9fa !important;
            padding: 1rem !important;
            border-radius: 0.5rem !important;
            border: 2px solid #dee2e6 !important;
        }
        
        /* Metric labels - black text */
        .stMetric label {
            color: #000000 !important;
            font-weight: 700 !important;
            font-size: 0.875rem !important;
            background-color: transparent !important;
        }
        
        /* Metric values - black text, large */
        .stMetric .metric-value {
            color: #000000 !important;
            font-weight: 900 !important;
            font-size: 1.75rem !important;
            background-color: transparent !important;
        }
        
        /* Metric deltas - black text */
        .stMetric .metric-delta {
            color: #000000 !important;
            font-weight: 700 !important;
            background-color: transparent !important;
        }
        
        /* DataFrames - black text on white */
        .stDataFrame {
            border: 2px solid #000000 !important;
            border-radius: 0.25rem !important;
            background-color: #ffffff !important;
        }
        
        /* DataFrame cells - black text */
        .stDataFrame td, .stDataFrame th {
            color: #000000 !important;
            background-color: #ffffff !important;
            border: 1px solid #cccccc !important;
        }
        
        /* Headers - black text, bold */
        h1, h2, h3, h4, h5, h6 {
            color: #000000 !important;
            font-weight: 900 !important;
            background-color: transparent !important;
        }
        
        /* Sidebar - white background with black text */
        section[data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 2px solid #000000 !important;
        }
        
        /* Sidebar content - black text */
        section[data-testid="stSidebar"] * {
            color: #000000 !important;
            background-color: transparent !important;
        }
        
        /* Input fields - black text on white */
        input, textarea, select {
            color: #000000 !important;
            background-color: #ffffff !important;
            border: 2px solid #cccccc !important;
        }
        
        /* Buttons - black text on light gray */
        button {
            color: #000000 !important;
            background-color: #f0f0f0 !important;
            border: 2px solid #999999 !important;
        }
        
        /* Alert boxes - black text with colored backgrounds */
        .stAlert {
            color: #000000 !important;
            border: 3px solid #000000 !important;
            background-color: #ffff99 !important;
        }
        
        /* Success messages - black text */
        .stSuccess {
            color: #000000 !important;
            border: 3px solid #000000 !important;
            background-color: #ccffcc !important;
        }
        
        /* Error messages - black text */
        .stError {
            color: #000000 !important;
            border: 3px solid #000000 !important;
            background-color: #ffcccc !important;
        }
        
        /* Info messages - black text */
        .stInfo {
            color: #000000 !important;
            border: 3px solid #000000 !important;
            background-color: #ccccff !important;
        }
        
        /* Plotly charts - black text */
        .js-plotly-plot .plotly .main-svg text {
            fill: #000000 !important;
            stroke: #000000 !important;
        }
        
        /* Tabs - black text */
        .stTabs [data-baseweb="tab"] {
            color: #000000 !important;
            background-color: #ffffff !important;
        }
        
        /* Tab content - black text */
        .stTabs [data-baseweb="tab-panel"] * {
            color: #000000 !important;
            background-color: transparent !important;
        }
        
        /* Code blocks - black text on light background */
        code, pre {
            color: #000000 !important;
            background-color: #f5f5f5 !important;
            border: 1px solid #cccccc !important;
        }
        
        /* Specific fix for tab titles that might be blending */
        .stTabs [data-baseweb="tab"] span {
            color: #000000 !important;
            background-color: transparent !important;
        }
        
        /* Ensure all containers have white backgrounds */
        .stContainer, .stVerticalBlock, .stHorizontalBlock {
            background-color: #ffffff !important;
        }
        
        /* Fix for any dark theme remnants */
        [data-theme="dark"], [data-testid*="dark"] {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        
        /* Force all text in plotly charts to be black */
        .plotly-graph-div text, .plotly-graph-div tspan {
            fill: #000000 !important;
        }
        
        /* Override any remaining dark backgrounds */
        .css-1d391kg, .css-1r6slb0, .css-12ttj6m, .css-1kyxreq {
            background-color: #ffffff !important;
        }
        
        /* Streamlit internal classes that might have dark backgrounds */
        .css-1avcm0n, .css-1lcbmhc, .css-1q8dd3e, .css-1n76uvr {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        
        /* Force all divs and spans to have transparent backgrounds unless specified */
        div:not(.stMetric):not(.stDataFrame):not(.stAlert):not(.stSuccess):not(.stError):not(.stInfo) {
            background-color: transparent !important;
        }
        
        /* Override any CSS variables that might set dark backgrounds */
        :root {
            --background-color: #ffffff !important;
            --secondary-background-color: #f8f9fa !important;
            --text-color: #000000 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    # Title
    st.title("📈 BAET Paper Trading Dashboard")
    
    # Sidebar
    st.sidebar.header("Configuration")
    
    # Control Panel (if available)
    try:
        from baet.dashboard.control import render_control_panel
        render_control_panel()
        st.sidebar.divider()
    except ImportError:
        pass  # Control panel not available
    
    # Log directory
    log_dir = st.sidebar.text_input(
        "Log Directory",
        value="logs/paper",
    )
    
    # Auto-refresh
    auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
    refresh_interval = st.sidebar.slider(
        "Refresh Interval (seconds)",
        min_value=10,
        max_value=300,
        value=30,
        step=10,
        disabled=not auto_refresh,
    )
    
    # Manual refresh button
    if st.sidebar.button("Refresh Now"):
        st.rerun()
    
    # Load data
    with st.spinner("Loading data..."):
        # Portfolio state
        portfolio_state = load_latest_state(log_dir)
        
        # Recent trades
        recent_trades = load_recent_trades(log_dir, limit=50)
        
        # Equity curve
        equity_df = load_equity_curve(log_dir)
        
        # Performance metrics
        metrics = calculate_performance_metrics(log_dir)
        
        # Daily summary (today)
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        daily_summary = calculate_daily_summary(log_dir, date=today)
        
        # Recent log entries
        log_file = find_latest_log_file(log_dir)
        log_entries = parse_log_file(log_file, max_entries=100) if log_file else []
    
    # Main content
    # Check if live mode is enabled
    from baet.config.loader import load_settings
    try:
        settings = load_settings()
        is_live_mode = settings.live.enabled if hasattr(settings, 'live') else False
        is_paper_mode = settings.paper.enabled if hasattr(settings, 'paper') else False
    except:
        is_live_mode = False
        is_paper_mode = False
    
    # Show mode indicator in sidebar
    with st.sidebar:
        st.markdown("---")
        if is_live_mode:
            st.error("🔴 **LIVE MODE ACTIVE**")
            st.warning("Real money at risk! Check positions regularly.")
            
            # Show live account info
            st.markdown("### Live Account")
            try:
                from baet.dashboard.data_loader import load_live_account_info
                account_info = load_live_account_info()
                
                if account_info.get("success"):
                    st.metric("Total Value (USDT)", f"${account_info.get('total_usdt_value', 0):.2f}")
                    
                    # Show key balances
                    balances = account_info.get("balances", {})
                    if "USDT" in balances:
                        usdt = balances["USDT"]
                        st.text(f"USDT: {usdt['free']:.2f} (free) / {usdt['locked']:.2f} (locked)")
                    
                    # Show other assets
                    for asset, data in balances.items():
                        if asset != "USDT" and data["total"] > 0:
                            st.text(f"{asset}: {data['total']:.6f}")
                else:
                    st.error(f"Cannot load account: {account_info.get('error', 'Unknown error')}")
            except Exception as e:
                st.error(f"Account info error: {e}")
                
        elif is_paper_mode:
            st.info("🟡 **PAPER TRADING MODE**")
        else:
            st.success("🟢 **OBSERVATION MODE**")
        
        # Emergency stop button (only in live mode)
        if is_live_mode:
            if st.button("🚨 EMERGENCY STOP", type="primary", use_container_width=True):
                import os
                with open("EMERGENCY_STOP.txt", "w") as f:
                    f.write("Emergency stop triggered from dashboard")
                st.error("Emergency stop file created! Bot should stop soon.")
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Overview", "Positions", "Trades", "Performance", "Logs"]
    )
    
    with tab1:
        st.header("Portfolio Overview")
        
        # Portfolio overview
        render_portfolio_overview(portfolio_state)
        
        # Equity chart
        st.subheader("Equity Curve")
        render_equity_chart(equity_df)
        
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
        render_equity_chart(equity_df)
        
        # Export button
        if not equity_df.empty:
            csv = equity_df.to_csv(index=False)
            st.download_button(
                label="Download Equity Curve (CSV)",
                data=csv,
                file_name=f"baet_equity_curve_{today}.csv",
                mime="text/csv",
            )
    
    with tab5:
        st.header("Log Viewer")
        
        render_log_viewer(log_entries, max_entries=100)
    
    # Auto-refresh logic
    if auto_refresh:
        import time
        time.sleep(refresh_interval)
        st.rerun()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**BAET** - Binance Adaptive Ensemble Trader\n"
        f"Dashboard updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
