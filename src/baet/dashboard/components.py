"""Streamlit UI components for BAET dashboard."""

from typing import Any, Optional

import pandas as pd
import plotly.express as px
import streamlit as st


def render_portfolio_overview(state: dict[str, Any]):
    """Render portfolio overview section.
    
    Args:
        state: Portfolio state dictionary
    """
    if not state:
        st.warning("No portfolio data available")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Cash",
            value=f"${state.get('cash', 0):,.2f}"
        )
    
    with col2:
        st.metric(
            label="Total Value",
            value=f"${state.get('total_value', 0):,.2f}"
        )
    
    with col3:
        initial = state.get('initial_balance', state.get('total_value', 0))
        total_return = (state.get('total_value', 0) - initial) / initial if initial > 0 else 0
        st.metric(
            label="Total Return",
            value=f"{total_return:.2%}",
            delta=f"{total_return:.2%}"
        )


def render_positions_table(positions: dict[str, dict]):
    """Render current positions table.
    
    Args:
        positions: Dictionary of positions
    """
    if not positions:
        st.info("No open positions")
        return
    
    # Convert to DataFrame
    data = []
    for symbol, pos in positions.items():
        data.append({
            "Symbol": symbol,
            "Units": pos.get("units", 0),
            "Avg Price": f"${pos.get('avg_price', 0):,.2f}",
            "Current Price": f"${pos.get('current_price', pos.get('avg_price', 0)):,.2f}",
            "Market Value": f"${pos.get('market_value', 0):,.2f}",
            "P&L": f"${pos.get('pnl', 0):,.2f}",
            "P&L %": f"{pos.get('pnl_pct', 0):.2%}",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)


def render_recent_trades(trades: list[dict], limit: int = 50):
    """Render recent trades table.
    
    Args:
        trades: List of trade dictionaries
        limit: Maximum number of trades to display
    """
    if not trades:
        st.info("No recent trades")
        return
    
    # Take most recent trades
    recent = trades[-limit:] if limit else trades
    
    # Convert to DataFrame
    data = []
    for trade in recent:
        data.append({
            "Time": trade.get("timestamp", ""),
            "Action": trade.get("action", ""),
            "Symbol": trade.get("symbol", ""),
            "Cash After": f"${trade.get('cash_after', 0):,.2f}",
            "Value After": f"${trade.get('total_value_after', 0):,.2f}",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)


def render_performance_metrics(metrics: dict[str, Any]):
    """Render performance metrics section.
    
    Args:
        metrics: Dictionary of performance metrics
    """
    if not metrics:
        st.warning("No performance data available")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Sharpe Ratio",
            value=f"{metrics.get('sharpe_ratio', 0):.2f}"
        )
    
    with col2:
        st.metric(
            label="Sortino Ratio",
            value=f"{metrics.get('sortino_ratio', 0):.2f}"
        )
    
    with col3:
        st.metric(
            label="Max Drawdown",
            value=f"{metrics.get('max_drawdown', 0):.2%}"
        )
    
    with col4:
        st.metric(
            label="Win Rate",
            value=f"{metrics.get('win_rate', 0):.2%}"
        )
    
    # Second row
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric(
            label="Total Return",
            value=f"{metrics.get('total_return', 0):.2%}"
        )
    
    with col6:
        st.metric(
            label="Annualized Return",
            value=f"{metrics.get('annualized_return', 0):.2%}"
        )
    
    with col7:
        st.metric(
            label="Volatility",
            value=f"{metrics.get('volatility', 0):.2%}"
        )
    
    with col8:
        st.metric(
            label="Trades",
            value=f"{metrics.get('trade_count', 0)}"
        )


def render_equity_chart(df: pd.DataFrame):
    """Render equity curve chart.
    
    Args:
        df: DataFrame with equity curve data
    """
    if df.empty:
        st.info("No equity curve data")
        return
    
    fig = px.line(
        df,
        x="timestamp",
        y="total_value",
        title="Portfolio Equity Curve",
        labels={"total_value": "Total Value ($)", "timestamp": "Time"}
    )
    
    fig.update_layout(
        hovermode="x unified",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_daily_summary(summary: dict[str, Any]):
    """Render daily summary section.
    
    Args:
        summary: Dictionary with daily summary
    """
    if not summary:
        st.warning("No summary data available")
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Daily P&L",
            value=f"${summary.get('daily_pnl', 0):,.2f}",
            delta=f"{summary.get('daily_return', 0):.2%}"
        )
    
    with col2:
        st.metric(
            label="Trades Today",
            value=summary.get("trade_count", 0)
        )
    
    with col3:
        st.metric(
            label="Signals Today",
            value=summary.get("signal_count", 0)
        )
    
    # Risk summary
    col4, col5 = st.columns(2)
    
    with col4:
        st.metric(
            label="Risk Evaluations",
            value=summary.get("risk_evaluation_count", 0)
        )
    
    with col5:
        passed = summary.get("passed_risk", 0)
        failed = summary.get("failed_risk", 0)
        st.metric(
            label="Risk Passed/Failed",
            value=f"{passed}/{failed}"
        )


def render_risk_status(risk_state: Optional[dict] = None):
    """Render risk status section.
    
    Args:
        risk_state: Optional risk state dictionary
    """
    if risk_state is None:
        st.info("Risk engine not active")
        return
    
    # Check for violations
    violations = risk_state.get("violations", [])
    
    if violations:
        st.error(f"**{len(violations)} Risk Violation(s) Detected**")
        for v in violations:
            st.write(f"- {v}")
    else:
        st.success("No risk violations")


def render_log_viewer(entries: list[dict], max_entries: int = 100):
    """Render recent log entries.
    
    Args:
        entries: List of log entries
        max_entries: Maximum number of entries to display
    """
    if not entries:
        st.info("No log entries")
        return
    
    # Take most recent entries
    recent = entries[-max_entries:] if max_entries else entries
    
    # Filter options
    entry_types = list(set(e.get("type", "UNKNOWN") for e in recent))
    selected_types = st.multiselect(
        "Filter by type:",
        options=entry_types,
        default=entry_types
    )
    
    # Filter
    filtered = [e for e in recent if e.get("type") in selected_types]
    
    # Display
    for entry in reversed(filtered):
        with st.expander(f"{entry.get('type', 'UNKNOWN')} - {entry.get('timestamp', '')}"):
            st.json(entry)
