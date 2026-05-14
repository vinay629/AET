"""Main Streamlit app for BAET dashboard - Redesigned TradingView-inspired Terminal."""

import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path so we can import baet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import streamlit as st

# Page config
st.set_page_config(
    page_title="BAET Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for Dark Terminal Theme
st.markdown(
    """
<style>
    :root {
        --background-color: #0b0f14;
        --panel-color: #121a24;
        --panel-alt: #0f1720;
        --border-color: #233041;
        --text-color: #d8e1ea;
        --muted-color: #8ea0b5;
        --green-color: #22c55e;
        --red-color: #ef4444;
        --amber-color: #f59e0b;
        --cyan-color: #22d3ee;
    }

    /* Main background */
    .stApp {
        background-color: var(--background-color);
        color: var(--text-color);
    }

    /* Top Strip */
    .top-strip {
        background-color: var(--panel-color);
        border-bottom: 1px solid var(--border-color);
        padding: 5px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        border-radius: 4px;
    }

    .status-item {
        margin-right: 20px;
        font-size: 0.85rem;
    }

    .status-label {
        color: var(--muted-color);
        text-transform: uppercase;
        font-size: 0.7rem;
        margin-right: 5px;
    }

    .status-value {
        font-weight: 600;
        font-family: 'Courier New', Courier, monospace;
    }

    /* Panels */
    .terminal-panel {
        background-color: var(--panel-color);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        padding: 15px;
        height: 100%;
        margin-bottom: 10px;
    }

    .panel-header {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--muted-color);
        text-transform: uppercase;
        border-bottom: 1px solid var(--border-color);
        margin-bottom: 10px;
        padding-bottom: 5px;
        display: flex;
        justify-content: space-between;
    }

    /* Metrics grid */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: 10px;
    }

    .metric-box {
        padding: 8px;
        background-color: var(--panel-alt);
        border-radius: 3px;
    }

    .metric-label {
        font-size: 0.65rem;
        color: var(--muted-color);
        text-transform: uppercase;
    }

    .metric-value {
        font-size: 1.1rem;
        font-weight: 600;
        font-family: 'Courier New', Courier, monospace;
    }

    /* Semantic colors */
    .bullish { color: var(--green-color); }
    .bearish { color: var(--red-color); }
    .warning { color: var(--amber-color); }
    .info { color: var(--cyan-color); }

    /* Hide standard Streamlit header/footer */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* Tables styling */
    .stDataFrame {
        border: 1px solid var(--border-color);
    }
    
    /* Plotly background */
    .js-plotly-plot {
        background-color: transparent !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Load data
from baet.config.loader import load_settings
from baet.dashboard.components import (
    render_equity_chart,
    render_win_rate_chart,
)
from baet.dashboard.data_loader import (
    calculate_daily_summary,
    load_equity_curve,
    load_latest_brain_scoring,
    load_latest_state,
    load_ohlcv_data,
    load_recent_signals,
    load_recent_trades,
)

# Load settings
settings = load_settings()

# Initialize Session State
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()
if "symbol" not in st.session_state:
    st.session_state.symbol = settings.market.symbols[0] if settings.market.symbols else "BTCUSDT"
if "timeframe" not in st.session_state:
    st.session_state.timeframe = (
        settings.market.timeframes[0] if settings.market.timeframes else "1h"
    )

# Top Status Strip
log_dir = settings.paper.logging.get("directory", "logs/paper")
portfolio_state = load_latest_state(log_dir)
daily_summary = calculate_daily_summary(log_dir)
brain_scoring = load_latest_brain_scoring(log_dir)


def render_top_strip():
    equity = portfolio_state.get("total_value", 0)
    pnl = daily_summary.get("daily_pnl", 0)
    pnl_color = "bullish" if pnl >= 0 else "bearish"

    # Mode from config
    mode_str = str(settings.app.mode).upper()

    signal = "NEUTRAL"
    score = brain_scoring.get("score", 0)
    if score > 0.3:
        signal = "BULLISH"
    elif score < -0.3:
        signal = "BEARISH"
    signal_color = (
        "bullish" if signal == "BULLISH" else "bearish" if signal == "BEARISH" else "warning"
    )

    # Dynamic risk status
    failed_risk = daily_summary.get("failed_risk", 0)
    risk_status = "STABLE" if failed_risk == 0 else "VIOLATION"
    risk_color = "bullish" if failed_risk == 0 else "bearish"

    st.markdown(
        f"""
    <div class="top-strip">
        <div style="display: flex;">
            <div class="status-item"><span class="status-label">MODE:</span><span class="status-value info">{mode_str}</span></div>
            <div class="status-item"><span class="status-label">EQUITY:</span><span class="status-value">${equity:,.2f}</span></div>
            <div class="status-item"><span class="status-label">DAILY P&L:</span><span class="status-value {pnl_color}">${pnl:+,.2f}</span></div>
            <div class="status-item"><span class="status-label">POSITIONS:</span><span class="status-value">{len(portfolio_state.get("positions", {}))}</span></div>
        </div>
        <div style="display: flex;">
            <div class="status-item"><span class="status-label">AI SIGNAL:</span><span class="status-value {signal_color}">{signal}</span></div>
            <div class="status-item"><span class="status-label">RISK:</span><span class="status-value {risk_color}">{risk_status}</span></div>
            <div class="status-item"><span class="status-label">LAST UPDATE:</span><span class="status-value">{datetime.now().strftime("%H:%M:%S")}</span></div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )


render_top_strip()

# Main Body
col_main, col_side = st.columns([0.7, 0.3])

with col_main:
    # Zone 1: Chart
    st.markdown('<div class="terminal-panel">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 1, 4])
    with c1:
        st.session_state.symbol = st.selectbox(
            "Symbol",
            settings.market.symbols if settings.market.symbols else ["BTCUSDT"],
            label_visibility="collapsed",
        )
    with c2:
        st.session_state.timeframe = st.selectbox(
            "TF",
            settings.market.timeframes if settings.market.timeframes else ["1h"],
            label_visibility="collapsed",
        )

    ohlcv_df = load_ohlcv_data(st.session_state.symbol, st.session_state.timeframe)
    if not ohlcv_df.empty:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        # Calculate indicators
        ohlcv_df = ohlcv_df.copy()
        # EMA
        ohlcv_df["EMA20"] = ohlcv_df["close"].ewm(span=20, adjust=False).mean()
        # BB
        std = ohlcv_df["close"].rolling(window=20).std()
        ohlcv_df["BB_upper"] = ohlcv_df["EMA20"] + (std * 2)
        ohlcv_df["BB_lower"] = ohlcv_df["EMA20"] - (std * 2)
        # RSI
        delta = ohlcv_df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        ohlcv_df["RSI"] = 100 - (100 / (1 + rs))

        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=("", "", ""),
            row_width=[0.15, 0.15, 0.7],
        )

        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=ohlcv_df["timestamp"],
                open=ohlcv_df["open"],
                high=ohlcv_df["high"],
                low=ohlcv_df["low"],
                close=ohlcv_df["close"],
                name="Price",
                increasing_line_color="#22c55e",
                decreasing_line_color="#ef4444",
            ),
            row=1,
            col=1,
        )

        # EMA
        fig.add_trace(
            go.Scatter(
                x=ohlcv_df["timestamp"],
                y=ohlcv_df["EMA20"],
                line=dict(color="#22d3ee", width=1),
                name="EMA20",
            ),
            row=1,
            col=1,
        )

        # BB
        fig.add_trace(
            go.Scatter(
                x=ohlcv_df["timestamp"],
                y=ohlcv_df["BB_upper"],
                line=dict(color="rgba(142, 160, 181, 0.3)", width=1),
                name="BB Upper",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=ohlcv_df["timestamp"],
                y=ohlcv_df["BB_lower"],
                line=dict(color="rgba(142, 160, 181, 0.3)", width=1),
                fill="tonexty",
                fillcolor="rgba(142, 160, 181, 0.05)",
                name="BB Lower",
            ),
            row=1,
            col=1,
        )

        # Volume
        fig.add_trace(
            go.Bar(
                x=ohlcv_df["timestamp"],
                y=ohlcv_df["volume"],
                name="Volume",
                marker_color="rgba(142, 160, 181, 0.3)",
            ),
            row=2,
            col=1,
        )

        # RSI
        fig.add_trace(
            go.Scatter(
                x=ohlcv_df["timestamp"],
                y=ohlcv_df["RSI"],
                line=dict(color="#f59e0b", width=1.5),
                name="RSI",
            ),
            row=3,
            col=1,
        )
        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", row=3, col=1)

        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            height=600,
            xaxis_rangeslider_visible=False,
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor="#233041"),
            yaxis=dict(showgrid=True, gridcolor="#233041"),
            xaxis2=dict(showgrid=True, gridcolor="#233041"),
            yaxis2=dict(showgrid=True, gridcolor="#233041"),
            xaxis3=dict(showgrid=True, gridcolor="#233041"),
            yaxis3=dict(showgrid=True, gridcolor="#233041", range=[0, 100]),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No chart data available")
    st.markdown("</div>", unsafe_allow_html=True)

    # Zone 2: Equity & Win Rate
    st.markdown('<div class="terminal-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-header">Performance Analytics</div>', unsafe_allow_html=True)
    e_col, w_col = st.columns(2)
    equity_df = load_equity_curve(log_dir)
    with e_col:
        render_equity_chart(equity_df, key="main_equity")
    with w_col:
        render_win_rate_chart(equity_df)
    st.markdown("</div>", unsafe_allow_html=True)

with col_side:
    # Zone 3: AI Brain
    st.markdown('<div class="terminal-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-header">AI Brain Confidence</div>', unsafe_allow_html=True)

    score = brain_scoring.get("score", 0)
    confidence = abs(score) * 100
    conf_color = "bullish" if score > 0 else "bearish" if score < 0 else "warning"

    st.markdown(
        f"""
    <div style="margin-bottom: 15px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <span class="status-label">CONFIDENCE</span>
            <span class="status-value {conf_color}">{confidence:.1f}%</span>
        </div>
        <div style="height: 8px; background-color: var(--panel-alt); border-radius: 4px;">
            <div style="width: {confidence}%; height: 100%; background-color: var(--{conf_color if score != 0 else "amber"}-color); border-radius: 4px;"></div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    components = brain_scoring.get("components", {})
    if components:
        comp_data = []
        for name, data in components.items():
            comp_data.append(
                {
                    "Plugin": name,
                    "Score": f"{data.get('score', 0):+.2f}",
                    "Weight": f"{data.get('weight', 0):.2f}",
                }
            )
        st.table(pd.DataFrame(comp_data))
    else:
        st.caption("No component data")
    st.markdown("</div>", unsafe_allow_html=True)

    # Zone 4: Portfolio & Positions
    st.markdown('<div class="terminal-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-header">Portfolio & Positions</div>', unsafe_allow_html=True)

    positions = portfolio_state.get("positions", {})
    if positions:
        pos_data = []
        for sym, data in positions.items():
            pnl_pct = data.get("pnl_pct", 0)
            pnl_color = "bullish" if pnl_pct >= 0 else "bearish"
            pos_data.append(
                {"Symbol": sym, "Size": f"{data.get('units', 0):.4f}", "P&L%": f"{pnl_pct:+.2%}"}
            )
        st.table(pd.DataFrame(pos_data))
    else:
        st.caption("No open positions")
    st.markdown("</div>", unsafe_allow_html=True)

    # Zone 5: Risk Status
    st.markdown('<div class="terminal-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-header">Risk Guard</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
    <div class="metrics-grid">
        <div class="metric-box"><div class="metric-label">Daily Trades</div><div class="metric-value">{daily_summary.get("trade_count", 0)}</div></div>
        <div class="metric-box"><div class="metric-label">Risk Passed</div><div class="metric-value bullish">{daily_summary.get("passed_risk", 0)}</div></div>
        <div class="metric-box"><div class="metric-label">Risk Failed</div><div class="metric-value {"bearish" if daily_summary.get("failed_risk", 0) > 0 else ""}">{daily_summary.get("failed_risk", 0)}</div></div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# Zone 6: Bottom Tables
st.markdown('<div class="terminal-panel">', unsafe_allow_html=True)
tab_trades, tab_signals = st.tabs(["Recent Trades", "AI Signals"])
with tab_trades:
    recent_trades = load_recent_trades(log_dir)
    if recent_trades:
        st.dataframe(
            pd.DataFrame(recent_trades).sort_values("timestamp", ascending=False),
            use_container_width=True,
        )
    else:
        st.caption("No trades recorded")
with tab_signals:
    recent_signals = load_recent_signals(log_dir)
    if recent_signals:
        st.dataframe(
            pd.DataFrame(recent_signals).sort_values("timestamp", ascending=False),
            use_container_width=True,
        )
    else:
        st.caption("No signals recorded")
st.markdown("</div>", unsafe_allow_html=True)

# Auto-refresh logic
if st.checkbox("Auto Refresh", value=True):
    refresh_interval = 30
    current_time = time.time()
    if current_time - st.session_state.last_refresh > refresh_interval:
        st.session_state.last_refresh = current_time
        st.rerun()
    st.caption(
        f"Next refresh in {int(refresh_interval - (current_time - st.session_state.last_refresh))}s"
    )
