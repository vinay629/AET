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
        render_daily_summary,
        render_equity_chart,
        render_log_viewer,
        render_performance_metrics,
        render_portfolio_overview,
        render_positions_table,
        render_recent_trades,
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

    # Custom CSS for clean, professional appearance
    st.markdown(
        """
        <style>
        /* Main app styling */
        .main > div {
            padding-top: 2rem;
        }

        /* Metric styling */
        .stMetric {
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 0.5rem;
            border: 1px solid #dee2e6;
        }

        /* Metric value styling */
        .stMetric .metric-value {
            font-weight: 700;
            font-size: 1.5rem;
        }

        /* DataFrame styling */
        .stDataFrame {
            border: 1px solid #dee2e6;
            border-radius: 0.25rem;
        }

        /* Tab styling */
        [data-baseweb="tab"][aria-selected="true"] {
            border-bottom: 3px solid #007bff;
            background-color: #e7f3ff;
        }

        /* Alert styling */
        .stAlert {
            border-radius: 0.5rem;
        }

        /* Button styling */
        button[kind="primary"] {
            font-weight: 600;
        }

        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            border-right: 1px solid #dee2e6;
        }

        /* Container borders */
        [data-testid="stContainer"] {
            border-radius: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Title - dynamic based on mode
    from baet.config.loader import load_settings

    try:
        settings = load_settings()
        if hasattr(settings, "live") and settings.live and settings.live.enabled:
            st.title("📈 BAET Live Trading Dashboard")
            st.caption("Environment: Testnet • Real-time demo trading")
        elif hasattr(settings, "paper") and settings.paper and settings.paper.enabled:
            st.title("📈 BAET Paper Trading Dashboard")
            st.caption("Simulated trading with virtual funds")
        else:
            st.title("📈 BAET Observation Dashboard")
            st.caption("Market observation mode • No trading active")
    except Exception as e:
        st.title("📈 BAET Dashboard")
        st.error(f"Config error: {e}")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Control Panel (if available)
        try:
            from baet.dashboard.control import render_control_panel

            render_control_panel()
            st.divider()
        except ImportError:
            pass  # Control panel not available

        # Log directory
        st.subheader("📁 Data Source")
        log_dir = st.text_input(
            "Log Directory", value="logs/paper", help="Directory containing trading logs"
        )

        st.divider()

        # Auto-refresh settings
        st.subheader("🔄 Refresh Settings")
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
        if st.button("🔄 Refresh Now", width="stretch"):
            st.rerun()

        # Auto-refresh logic
        if auto_refresh:
            import time

            time.sleep(refresh_interval)
            st.rerun()

        # Last updated timestamp (updated on each refresh)
        from datetime import datetime

        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Check if live mode is enabled
    try:
        settings = load_settings()
        is_live_mode = (
            settings.live.enabled if hasattr(settings, "live") and settings.live else False
        )
        is_paper_mode = (
            settings.paper.enabled if hasattr(settings, "paper") and settings.paper else False
        )
    except:
        is_live_mode = False
        is_paper_mode = False

    # Load data based on mode
    if is_live_mode:
        try:
            from baet.dashboard.data_loader import load_live_account_info

            live_account = load_live_account_info()
            portfolio_state = {
                "cash": live_account.get("total_usdt_value", 0)
                if live_account.get("success")
                else 0,
                "total_value": live_account.get("total_usdt_value", 0)
                if live_account.get("success")
                else 0,
                "positions": live_account.get("balances", {}),
                "is_live": True,
            }
            recent_trades = []
            equity_df = None
            metrics = {}
            daily_summary = {}
            log_entries = []
        except Exception as e:
            st.error(f"Error loading live account: {e}")
            portfolio_state = {}
            recent_trades = []
            equity_df = None
            metrics = {}
            daily_summary = {}
            log_entries = []
    else:
        # Load paper/observation data
        try:
            log_dir = st.session_state.get("log_dir", "logs/paper")
            portfolio_state = load_latest_state(log_dir)
            recent_trades = load_recent_trades(log_dir, limit=50)
            equity_df = load_equity_curve(log_dir)
            metrics = calculate_performance_metrics(log_dir)
            from datetime import datetime

            today = datetime.now().strftime("%Y-%m-%d")
            daily_summary = calculate_daily_summary(log_dir, date=today)
            log_file = find_latest_log_file(log_dir)
            log_entries = parse_log_file(log_file, max_entries=100) if log_file else []
        except Exception as e:
            st.error(f"Error loading data: {e}")
            portfolio_state = {}
            recent_trades = []
            equity_df = None
            metrics = {}
            daily_summary = {}
            log_entries = []

    # Load data based on mode
    if is_live_mode:
        # Load live account info
        try:
            from baet.dashboard.data_loader import load_live_account_info

            live_account = load_live_account_info()
            portfolio_state = {
                "cash": live_account.get("total_usdt_value", 0)
                if live_account.get("success")
                else 0,
                "total_value": live_account.get("total_usdt_value", 0)
                if live_account.get("success")
                else 0,
                "positions": live_account.get("balances", {}),
                "is_live": True,
            }
            recent_trades = []
            equity_df = None
            metrics = {}
            daily_summary = {}
            log_entries = []
        except Exception as e:
            st.error(f"Error loading live account: {e}")
            portfolio_state = {}
            recent_trades = []
            equity_df = None
            metrics = {}
            daily_summary = {}
            log_entries = []
    else:
        # Load paper/observation data
        try:
            portfolio_state = load_latest_state(log_dir)
            recent_trades = load_recent_trades(log_dir, limit=50)
            equity_df = load_equity_curve(log_dir)
            metrics = calculate_performance_metrics(log_dir)
            from datetime import datetime

            today = datetime.now().strftime("%Y-%m-%d")
            daily_summary = calculate_daily_summary(log_dir, date=today)
            log_file = find_latest_log_file(log_dir)
            log_entries = parse_log_file(log_file, max_entries=100) if log_file else []
        except Exception as e:
            st.error(f"Error loading data: {e}")
            portfolio_state = {}
            recent_trades = []
            equity_df = None
            metrics = {}
            daily_summary = {}
            log_entries = []

    # Show mode indicator in sidebar with enhanced visuals
    with st.sidebar:
        st.divider()

        # Mode status with colored containers
        if is_live_mode:
            with st.container(border=True):
                st.markdown("### 🔴 LIVE MODE ACTIVE")
                st.warning("⚠️ Demo money at risk! Monitor positions closely.")

                # Show live account info in sidebar
                st.markdown("#### 💼 Live Account (Testnet)")
                try:
                    from baet.dashboard.data_loader import load_live_account_info

                    account_info = load_live_account_info()

                    if account_info.get("success"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric(
                                "Total Value", f"${account_info.get('total_usdt_value', 0):.2f}"
                            )
                        with col2:
                            can_trade = "✅" if account_info.get("can_trade") else "❌"
                            st.metric("Can Trade", can_trade)

                        # Show key balances in expandable section
                        balances = account_info.get("balances", {})
                        with st.expander("View Balances", expanded=False):
                            if "USDT" in balances:
                                usdt = balances["USDT"]
                                st.text(
                                    f"USDT: {usdt['free']:.2f} free / {usdt['locked']:.2f} locked"
                                )

                            # Show other assets
                            for asset, data in sorted(balances.items()):
                                if asset != "USDT" and data["total"] > 0:
                                    st.text(
                                        f"{asset}: {data['total']:.6f} (free: {data['free']:.6f})"
                                    )
                    else:
                        st.error(
                            f"Cannot load account: {account_info.get('error', 'Unknown error')}"
                        )
                except Exception as e:
                    st.error(f"Account info error: {e}")
        elif is_paper_mode:
            with st.container(border=True):
                st.markdown("### 🟡 PAPER TRADING MODE")
                st.info("📊 Simulated trading with virtual funds")
        else:
            with st.container(border=True):
                st.markdown("### 🟢 OBSERVATION MODE")
                st.success("👁️ Market observation only • No trading")

        # Emergency stop button (only in live mode)
        if is_live_mode:
            st.divider()
            if st.button(
                "🚨 EMERGENCY STOP", type="primary", width="stretch", key="main_emergency_stop"
            ):
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

        # Show live account info prominently if in live mode
        if is_live_mode:
            try:
                from baet.dashboard.data_loader import load_live_account_info

                account_info = load_live_account_info()

                if account_info.get("success"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(
                            "Total Value (USDT)", f"${account_info.get('total_usdt_value', 0):.2f}"
                        )
                    with col2:
                        st.metric("Account Type", account_info.get("account_type", "N/A"))
                    with col3:
                        st.metric(
                            "Can Trade", "✅ Yes" if account_info.get("can_trade") else "❌ No"
                        )

                    # Show key balances
                    st.subheader("Demo Account Balances (Testnet)")
                    balances = account_info.get("balances", {})

                    # Display key assets
                    cols = st.columns(4)
                    with cols[0]:
                        if "BTC" in balances:
                            btc = balances["BTC"]
                            st.metric("BTC", f"{btc['total']:.6f}", f"Free: {btc['free']:.6f}")
                    with cols[1]:
                        if "ETH" in balances:
                            eth = balances["ETH"]
                            st.metric("ETH", f"{eth['total']:.6f}", f"Free: {eth['free']:.6f}")
                    with cols[2]:
                        if "USDT" in balances:
                            usdt = balances["USDT"]
                            st.metric("USDT", f"{usdt['total']:.2f}", f"Free: {usdt['free']:.2f}")
                    with cols[3]:
                        if "BNB" in balances:
                            bnb = balances["BNB"]
                            st.metric("BNB", f"{bnb['total']:.6f}", f"Free: {bnb['free']:.6f}")

                    # Show all balances in expander
                    with st.expander("View All Balances"):
                        for asset, data in sorted(balances.items()):
                            if data["total"] > 0:
                                st.text(
                                    f"{asset}: {data['total']:.6f} (Free: {data['free']:.6f}, Locked: {data['locked']:.6f})"
                                )
                else:
                    st.error(
                        f"Cannot load live account: {account_info.get('error', 'Unknown error')}"
                    )
            except Exception as e:
                st.error(f"Live account error: {e}")
        else:
            # Portfolio overview (paper/observation mode)
            render_portfolio_overview(portfolio_state)

            # Equity chart
            st.subheader("Equity Curve")
            render_equity_chart(equity_df)

            # Daily summary
            st.subheader("Today's Summary")
            render_daily_summary(daily_summary)

    with tab2:
        st.header("Current Positions")

        if is_live_mode:
            # In live mode, show message that positions come from live account
            st.info("📡 **Live Mode**: Positions are managed by the live trading bot.")
            try:
                from baet.dashboard.data_loader import load_live_account_info

                account_info = load_live_account_info()
                if account_info.get("success"):
                    balances = account_info.get("balances", {})
                    # Show non-zero balances as "positions"
                    positions_data = []
                    for asset, data in balances.items():
                        if data["total"] > 0 and asset != "USDT":
                            positions_data.append(
                                {
                                    "Asset": asset,
                                    "Total": data["total"],
                                    "Free": data["free"],
                                    "Locked": data["locked"],
                                }
                            )
                    if positions_data:
                        import pandas as pd

                        df = pd.DataFrame(positions_data)
                        st.dataframe(df, width="stretch")
                    else:
                        st.warning("No open positions found.")
            except Exception as e:
                st.error(f"Error loading positions: {e}")
        else:
            positions = portfolio_state.get("positions", {})
            render_positions_table(positions)

    with tab3:
        st.header("Recent Trades")

        if is_live_mode:
            st.info(
                "📡 **Live Mode**: Trade history will appear here when the live bot places orders."
            )
            st.warning("No trades yet. The bot is in observation mode (no orders placed).")
        else:
            render_recent_trades(recent_trades, limit=50)

    with tab4:
        st.header("Performance Metrics")

        if is_live_mode:
            st.info(
                "📡 **Live Mode**: Performance metrics will be calculated after trades are executed."
            )
            # Show account value instead
            try:
                from baet.dashboard.data_loader import load_live_account_info

                account_info = load_live_account_info()
                if account_info.get("success"):
                    st.metric(
                        "Current Account Value (USDT)",
                        f"${account_info.get('total_usdt_value', 0):.2f}",
                    )
                    st.metric("Account Type", account_info.get("account_type", "N/A"))
            except Exception as e:
                st.error(f"Error loading metrics: {e}")
        else:
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

        if is_live_mode:
            st.info("📡 **Live Mode**: Live trading logs will appear here.")
            st.warning("No logs yet. Start the live trading bot to see logs.")
        else:
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
