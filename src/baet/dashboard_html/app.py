"""HTML-based dashboard for BAET using Flask and Plotly."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# Add src to path so we can import baet
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from baet.config.loader import load_settings
from baet.dashboard_html.data_loader import find_latest_log_file, parse_log_file, load_latest_state

app = Flask(__name__)
CORS(app)

# Global variables for caching
cache = {
    'portfolio_state': None,
    'trades': [],
    'performance_data': None,
    'last_update': None
}

def get_portfolio_state() -> dict[str, Any]:
    """Get the latest portfolio state."""
    global cache
    
    # Check if we need to refresh cache
    if cache['last_update'] is None or (datetime.now() - cache['last_update']).seconds > 30:
        try:
            state = load_latest_state()
            cache['portfolio_state'] = state
            cache['last_update'] = datetime.now()
        except Exception as e:
            print(f"Error loading portfolio state: {e}")
            cache['portfolio_state'] = {}
    return cache['portfolio_state']

def get_trades() -> list[dict[str, Any]]:
    """Get recent trades."""
    global cache
    
    if cache['trades']:
        return cache['trades']
    
    try:
        log_file = find_latest_log_file()
        if log_file:
            entries = parse_log_file(log_file, max_entries=200)
            # Filter for TRADE events
            cache['trades'] = [entry for entry in entries if entry.get('type') == 'TRADE']
    except Exception as e:
        print(f"Error loading trades: {e}")
        cache['trades'] = []
    
    return cache['trades']

def get_performance_data() -> pd.DataFrame:
    """Get performance data for charts."""
    global cache
    
    if cache['performance_data'] is not None:
        return cache['performance_data']
    
    try:
        log_file = find_latest_log_file()
        if log_file:
            entries = parse_log_file(log_file, max_entries=1000)
            
            # Extract portfolio updates for equity curve
            portfolio_updates = []
            for entry in entries:
                if entry.get('type') == 'PORTFOLIO_UPDATE':
                    portfolio_updates.append({
                        'timestamp': entry.get('timestamp'),
                        'total_value': entry.get('total_value', 0),
                        'cash': entry.get('cash', 0),
                        'action': entry.get('action', '')
                    })
            
            if portfolio_updates:
                df = pd.DataFrame(portfolio_updates)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp')
                cache['performance_data'] = df
                return df
    except Exception as e:
        print(f"Error loading performance data: {e}")
    
    return pd.DataFrame()

@app.route('/')
def dashboard():
    """Main dashboard page."""
    return render_template('dashboard.html')

@app.route('/api/portfolio')
def api_portfolio():
    """API endpoint for portfolio data."""
    state = get_portfolio_state()
    return jsonify(state)

@app.route('/api/trades')
def api_trades():
    """API endpoint for trades data."""
    trades = get_trades()
    return jsonify(trades)

@app.route('/api/performance')
def api_performance():
    """API endpoint for performance data."""
    df = get_performance_data()
    return jsonify(df.to_dict('records'))

@app.route('/api/charts/portfolio_allocation')
def api_portfolio_allocation():
    """API endpoint for portfolio allocation chart."""
    state = get_portfolio_state()
    positions = state.get('positions', {})
    cash = state.get('cash', 0)
    
    data = []
    
    # Add cash
    if cash > 0:
        data.append({'Asset': 'Cash', 'Value': cash})
    
    # Add positions
    for symbol, pos in positions.items():
        value = pos.get('market_value', 0)
        if value > 0:
            data.append({'Asset': symbol, 'Value': value})
    
    return jsonify(data)

@app.route('/api/charts/equity_curve')
def api_equity_curve():
    """API endpoint for equity curve chart."""
    df = get_performance_data()
    if df.empty:
        return jsonify([])
    
    return jsonify({
        'timestamps': df['timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist(),
        'equity': df['total_value'].tolist(),
        'cash': df['cash'].tolist()
    })

@app.route('/api/charts/daily_pnl')
def api_daily_pnl():
    """API endpoint for daily P&L chart."""
    df = get_performance_data()
    if df.empty:
        return jsonify([])
    
    # Calculate daily P&L (simplified - would need proper daily aggregation)
    df['date'] = df['timestamp'].dt.date
    daily_data = df.groupby('date').agg({
        'total_value': 'last',
        'cash': 'last'
    }).reset_index()
    
    # Calculate P&L
    daily_data['pnl'] = daily_data['total_value'].diff()
    
    return jsonify({
        'dates': daily_data['date'].dt.strftime('%Y-%m-%d').tolist(),
        'pnl': daily_data['pnl'].fillna(0).tolist()
    })

if __name__ == '__main__':
    # Load settings
    settings = load_settings()
    
    # Run the app
    app.run(
        host='0.0.0.0',
        port=settings.dashboard.port,
        debug=False,
        threaded=True
    )