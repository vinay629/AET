"""Streamlit UI components for BAET dashboard."""

from datetime import datetime
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_portfolio_overview(state: dict[str, Any]):
    """Render portfolio overview section.
    
    Args:
        state: Portfolio state dictionary
    """
    if not state:
        st.warning("No portfolio data available")
        return
    
    # Main metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💵 Cash",
            value=f"${state.get('cash', 0):,.2f}"
        )
    
    with col2:
        st.metric(
            label="📊 Total Value",
            value=f"${state.get('total_value', 0):,.2f}"
        )
    
    with col3:
        initial = state.get('initial_balance', state.get('total_value', 0))
        total_return = (state.get('total_value', 0) - initial) / initial if initial > 0 else 0
        delta_color = "normal" if total_return >= 0 else "inverse"
        st.metric(
            label="📈 Total Return",
            value=f"{total_return:.2%}",
            delta=f"{total_return:.2%}",
            delta_color=delta_color
        )
    
    with col4:
        positions_value = state.get('total_value', 0) - state.get('cash', 0)
        st.metric(
            label="💼 Positions Value",
            value=f"${positions_value:,.2f}"
        )
    
    # Portfolio allocation chart
    render_portfolio_allocation(state)


def render_portfolio_allocation(state: dict[str, Any]):
    """Render portfolio allocation pie chart.
    
    Args:
        state: Portfolio state dictionary
    """
    positions = state.get('positions', {})
    cash = state.get('cash', 0)
    
    if not positions and cash <= 0:
        return
    
    # Prepare data for pie chart
    data = []
    
    # Add cash
    if cash > 0:
        data.append({"Asset": "Cash", "Value": cash})
    
    # Add positions
    for symbol, pos in positions.items():
        value = pos.get('market_value', 0)
        if value > 0:
            data.append({"Asset": symbol, "Value": value})
    
    if not data:
        return
    
    df = pd.DataFrame(data)
    
    # Create pie chart
    fig = px.pie(
        df,
        values="Value",
        names="Asset",
        title="Portfolio Allocation",
        hole=0.3,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        hovertemplate='<b>%{label}</b><br>Value: $%{value:,.2f}<br>Percentage: %{percent:.1%}<extra></extra>'
    )
    
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        height=400,
        font=dict(family="Arial, sans-serif", size=12),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_positions_table(positions: dict[str, dict]):
    """Render current positions table with color coding.
    
    Args:
        positions: Dictionary of positions
    """
    if not positions:
        st.info("📭 No open positions")
        return
    
    # Convert to DataFrame with numeric values for coloring
    data = []
    for symbol, pos in positions.items():
        pnl = pos.get('pnl', 0)
        pnl_pct = pos.get('pnl_pct', 0)
        data.append({
            "Symbol": symbol,
            "Units": pos.get("units", 0),
            "Avg Price": pos.get('avg_price', 0),
            "Current Price": pos.get('current_price', pos.get('avg_price', 0)),
            "Market Value": pos.get('market_value', 0),
            "P&L ($)": pnl,
            "P&L (%)": pnl_pct,
        })
    
    df = pd.DataFrame(data)
    
    # Display with color coding using Styler
    def color_pnl(val):
        """Color code P&L values."""
        if isinstance(val, (int, float)):
            if val > 0:
                return 'color: green; font-weight: bold'
            elif val < 0:
                return 'color: red; font-weight: bold'
        return ''
    
    # Apply styling
    styled_df = df.style.applymap(color_pnl, subset=['P&L ($)', 'P&L (%)'])
    
    # Format currency and percentage columns
    styled_df = styled_df.format({
        'Avg Price': '${:,.2f}',
        'Current Price': '${:,.2f}',
        'Market Value': '${:,.2f}',
        'P&L ($)': '${:,.2f}',
        'P&L (%)': '{:.2%}'
    })
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def render_recent_trades(trades: list[dict], limit: int = 50):
    """Render recent trades table with improved formatting.
    
    Args:
        trades: List of trade dictionaries
        limit: Maximum number of trades to display
    """
    if not trades:
        st.info("📭 No recent trades")
        return
    
    # Take most recent trades
    recent = trades[-limit:] if limit else trades
    
    # Convert to DataFrame with better formatting
    data = []
    for trade in recent:
        action = trade.get("action", "")
        # Add emoji based on action
        if action.upper() == "BUY":
            action_display = "🟢 BUY"
        elif action.upper() == "SELL":
            action_display = "🔴 SELL"
        else:
            action_display = action
        
        data.append({
            "Time": trade.get("timestamp", ""),
            "Action": action_display,
            "Symbol": trade.get("symbol", ""),
            "Cash After": trade.get('cash_after', 0),
            "Value After": trade.get('total_value_after', 0),
        })
    
    df = pd.DataFrame(data)
    
    # Format currency columns
    styled_df = df.style.format({
        'Cash After': '${:,.2f}',
        'Value After': '${:,.2f}'
    })
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)


def render_performance_metrics(metrics: dict[str, Any]):
    """Render performance metrics section with visual indicators.
    
    Args:
        metrics: Dictionary of performance metrics
    """
    if not metrics:
        st.warning("No performance data available")
        return
    
    # First row - Risk-adjusted returns
    st.subheader("📊 Risk-Adjusted Performance")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        sharpe = metrics.get('sharpe_ratio', 0)
        delta_color = "normal" if sharpe >= 1 else "inverse"
        st.metric(
            label="Sharpe Ratio",
            value=f"{sharpe:.2f}",
            delta="Good" if sharpe >= 1 else "Poor",
            delta_color=delta_color
        )
    
    with col2:
        sortino = metrics.get('sortino_ratio', 0)
        delta_color = "normal" if sortino >= 1 else "inverse"
        st.metric(
            label="Sortino Ratio",
            value=f"{sortino:.2f}",
            delta="Good" if sortino >= 1 else "Poor",
            delta_color=delta_color
        )
    
    with col3:
        max_dd = metrics.get('max_drawdown', 0)
        delta_color = "inverse" if max_dd < 0 else "normal"
        st.metric(
            label="Max Drawdown",
            value=f"{max_dd:.2%}",
            delta="High Risk" if max_dd < -0.2 else "Acceptable",
            delta_color=delta_color
        )
    
    with col4:
        win_rate = metrics.get('win_rate', 0)
        delta_color = "normal" if win_rate >= 0.5 else "inverse"
        st.metric(
            label="Win Rate",
            value=f"{win_rate:.2%}",
            delta="Profitable" if win_rate >= 0.5 else "Needs Work",
            delta_color=delta_color
        )
    
    # Second row - Returns and activity
    st.subheader("📈 Returns & Activity")
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        total_ret = metrics.get('total_return', 0)
        delta_color = "normal" if total_ret >= 0 else "inverse"
        st.metric(
            label="Total Return",
            value=f"{total_ret:.2%}",
            delta_color=delta_color
        )
    
    with col6:
        ann_ret = metrics.get('annualized_return', 0)
        delta_color = "normal" if ann_ret >= 0 else "inverse"
        st.metric(
            label="Annualized Return",
            value=f"{ann_ret:.2%}",
            delta_color=delta_color
        )
    
    with col7:
        vol = metrics.get('volatility', 0)
        delta_color = "inverse" if vol > 0.3 else "normal"
        st.metric(
            label="Volatility",
            value=f"{vol:.2%}",
            delta="High" if vol > 0.3 else "Normal",
            delta_color=delta_color
        )
    
    with col8:
        st.metric(
            label="📊 Total Trades",
            value=f"{metrics.get('trade_count', 0)}"
        )


def render_equity_chart(df: pd.DataFrame):
    """Render equity curve chart with enhanced styling.
    
    Args:
        df: DataFrame with equity curve data
    """
    if df.empty:
        st.info("📉 No equity curve data available")
        return
    
    # Create figure with better styling
    fig = px.line(
        df,
        x="timestamp",
        y="total_value",
        title="Portfolio Equity Curve",
        labels={"total_value": "Total Value ($)", "timestamp": "Time"},
        template="plotly_white"
    )
    
    # Add gradient fill under the line
    fig.add_scatter(
        x=df["timestamp"],
        y=df["total_value"],
        fill='tozeroy',
        fillcolor='rgba(0, 123, 255, 0.1)',
        line=dict(color='#007bff', width=2),
        showlegend=False
    )
    
    # Update layout for better appearance
    fig.update_layout(
        hovermode="x unified",
        showlegend=False,
        xaxis_title="Time",
        yaxis_title="Total Value ($)",
        font=dict(family="Arial, sans-serif", size=12),
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0'),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0')
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Also show drawdown chart if we have returns data
    if 'total_value' in df.columns and len(df) > 1:
        render_drawdown_chart(df)


def render_drawdown_chart(df: pd.DataFrame):
    """Render drawdown chart.
    
    Args:
        df: DataFrame with equity curve data
    """
    if df.empty or 'total_value' not in df.columns or len(df) < 2:
        return
    
    # Calculate drawdown
    df = df.copy()
    df['peak'] = df['total_value'].cummax()
    df['drawdown'] = (df['total_value'] - df['peak']) / df['peak']
    
    # Create drawdown chart
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['drawdown'] * 100,  # Convert to percentage
            fill='tozeroy',
            fillcolor='rgba(255, 0, 0, 0.1)',
            line=dict(color='red', width=1),
            name='Drawdown'
        )
    )
    
    fig.update_layout(
        title="Portfolio Drawdown",
        xaxis_title="Time",
        yaxis_title="Drawdown (%)",
        yaxis_tickformat='.1%',
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0'),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor='#f0f0f0', tickformat='.1%')
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_daily_summary(summary: dict[str, Any]):
    """Render daily summary section with enhanced visuals.
    
    Args:
        summary: Dictionary with daily summary
    """
    if not summary:
        st.warning("📅 No summary data available for today")
        return
    
    st.subheader("📅 Today's Trading Activity")
    
    # Main metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        daily_pnl = summary.get('daily_pnl', 0)
        daily_ret = summary.get('daily_return', 0)
        delta_color = "normal" if daily_pnl >= 0 else "inverse"
        st.metric(
            label="💰 Daily P&L",
            value=f"${daily_pnl:,.2f}",
            delta=f"{daily_ret:.2%}",
            delta_color=delta_color
        )
    
    with col2:
        st.metric(
            label="📊 Trades Today",
            value=summary.get("trade_count", 0),
            delta=f"{summary.get('trade_count', 0)} executed"
        )
    
    with col3:
        st.metric(
            label="📡 Signals Today",
            value=summary.get("signal_count", 0),
            delta=f"{summary.get('signal_count', 0)} generated"
        )
    
    # Risk summary
    st.subheader("🛡️ Risk Evaluation Summary")
    col4, col5 = st.columns(2)
    
    with col4:
        risk_evals = summary.get("risk_evaluation_count", 0)
        st.metric(
            label="🔍 Risk Evaluations",
            value=risk_evals,
            delta=f"{risk_evals} checks run"
        )
    
    with col5:
        passed = summary.get("passed_risk", 0)
        failed = summary.get("failed_risk", 0)
        total = passed + failed
        pass_rate = (passed / total * 100) if total > 0 else 0
        delta_color = "normal" if pass_rate >= 80 else "inverse"
        st.metric(
            label="✅ Risk Passed/Failed",
            value=f"{passed}/{failed}",
            delta=f"{pass_rate:.0f}% pass rate",
            delta_color=delta_color
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
