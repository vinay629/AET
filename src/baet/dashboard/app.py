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
    
    # Page config
    st.set_page_config(
        page_title="BAET Dashboard",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Custom CSS
    st.markdown(
        """
        <style>
        .main > div {
            padding-top: 2rem;
        }
        .stMetric {
            background-color: #f0f2f6;
            padding: 1rem;
            border-radius: 0.5rem;
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
