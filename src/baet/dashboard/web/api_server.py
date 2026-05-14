"""Flask API server for BAET dashboard.

Serves the HTML dashboard and provides REST API endpoints for real-time data.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Add src to path so we can import baet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from baet.config.loader import load_settings
from baet.dashboard.data_loader import (
    calculate_daily_summary,
    find_latest_log_file,
    load_equity_curve,
    load_latest_brain_scoring,
    load_ohlcv_data,
    load_recent_trades,
    load_latest_state,
    parse_log_file,
)

app = Flask(__name__)
CORS(app)

# Configuration
LOG_DIR = "logs/paper"
PORT = 8501
HOST = "localhost"

# Cache for performance
cache = {}
cache_timeout = 30  # seconds


def get_cached_data(key: str, fetch_func, *args, **kwargs):
    """Get cached data or fetch fresh data if expired."""
    now = datetime.now().timestamp()
    if key in cache and (now - cache[key]['timestamp']) < cache_timeout:
        return cache[key]['data']
    
    data = fetch_func(*args, **kwargs)
    cache[key] = {
        'data': data,
        'timestamp': now
    }
    return data


@app.route('/')
def dashboard():
    """Serve the main dashboard HTML."""
    return send_from_directory('.', 'index.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS, etc.)."""
    return send_from_directory('.', filename)


@app.route('/api/portfolio')
def get_portfolio():
    """Get current portfolio state."""
    try:
        portfolio_state = get_cached_data('portfolio', load_latest_state, LOG_DIR)
        return jsonify(portfolio_state)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/equity')
def get_equity():
    """Get equity curve data."""
    try:
        equity_data = get_cached_data('equity', load_equity_curve, LOG_DIR)
        # Convert to list of dicts for JSON serialization
        return jsonify([
            {
                'timestamp': item['timestamp'].isoformat() if isinstance(item['timestamp'], datetime) else item['timestamp'],
                'cash': item.get('cash', 0),
                'total_value': item.get('total_value', 0),
                'action': item.get('action', ''),
                'symbol': item.get('symbol', '')
            }
            for item in equity_data.to_dict('records')
        ])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/trades')
def get_trades():
    """Get recent trades."""
    try:
        trades = get_cached_data('trades', load_recent_trades, LOG_DIR, limit=50)
        return jsonify(trades)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions')
def get_positions():
    """Get current positions."""
    try:
        portfolio_state = get_cached_data('positions', load_latest_state, LOG_DIR)
        positions = portfolio_state.get('positions', {})
        
        # Calculate P&L for each position
        result = {}
        for symbol, pos in positions.items():
            # Calculate P&L if we have current price
            current_price = pos.get('current_price', pos.get('avg_price', 0))
            avg_price = pos.get('avg_price', 0)
            units = pos.get('units', 0)
            
            market_value = current_price * units
            cost_basis = avg_price * units
            pnl = market_value - cost_basis
            pnl_percent = (pnl / cost_basis) * 100 if cost_basis > 0 else 0
            
            result[symbol] = {
                'units': units,
                'avg_price': avg_price,
                'current_price': current_price,
                'market_value': market_value,
                'pnl': pnl,
                'pnl_percent': pnl_percent
            }
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs')
def get_logs():
    """Get recent logs."""
    try:
        log_file = find_latest_log_file(LOG_DIR)
        if not log_file:
            return jsonify([])
        
        entries = parse_log_file(log_file, max_entries=100)
        
        # Format logs for display
        formatted_logs = []
        for entry in entries:
            log_type = entry.get('type', 'UNKNOWN')
            message = entry.get('message', '')
            
            if not message:
                # Create a message from the entry data
                if log_type == 'PORTFOLIO_UPDATE':
                    message = f"Portfolio updated: ${entry.get('total_value', 0):,.2f}"
                elif log_type == 'TRADE':
                    message = f"Trade executed: {entry.get('action', '')} {entry.get('symbol', '')}"
                elif log_type == 'BRAIN_SCORING':
                    score = entry.get('score', 0)
                    message = f"AI Score: {score:.3f}"
                else:
                    message = json.dumps(entry)
            
            formatted_logs.append({
                'timestamp': entry.get('timestamp', ''),
                'type': log_type,
                'message': message
            })
        
        return jsonify(formatted_logs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/performance')
def get_performance():
    """Get performance metrics."""
    try:
        # Calculate performance metrics from equity data
        equity_data = load_equity_curve(LOG_DIR)
        
        if equity_data.empty:
            return jsonify({
                'sharpe_ratio': 0,
                'sortino_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'total_return': 0,
                'annualized_return': 0,
                'volatility': 0,
                'trade_count': 0,
                'ai_score': 0
            })
        
        # Calculate returns
        returns = equity_data['total_value'].pct_change().dropna()
        
        # Basic metrics
        total_return = (equity_data['total_value'].iloc[-1] / equity_data['total_value'].iloc[0]) - 1
        annualized_return = (1 + total_return) ** (365 / len(equity_data)) - 1 if len(equity_data) > 1 else 0
        volatility = returns.std() * (365 ** 0.5) if len(returns) > 1 else 0
        
        # Sharpe ratio (assuming risk-free rate = 0)
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0
        
        # Sortino ratio (downside deviation only)
        downside_returns = returns[returns < 0]
        downside_deviation = downside_returns.std() * (365 ** 0.5) if len(downside_returns) > 1 else 0
        sortino_ratio = (annualized_return / downside_deviation) if downside_deviation > 0 else 0
        
        # Max drawdown
        cumulative_max = equity_data['total_value'].expanding().max()
        drawdown = (equity_data['total_value'] - cumulative_max) / cumulative_max
        max_drawdown = drawdown.min()
        
        # Win rate (from trades with positive P&L)
        trades = load_recent_trades(LOG_DIR, limit=1000)
        profitable_trades = sum(1 for trade in trades if trade.get('pnl', 0) > 0)
        win_rate = profitable_trades / len(trades) if trades else 0
        
        # AI score
        brain_scoring = load_latest_brain_scoring(LOG_DIR)
        ai_score = brain_scoring.get('score', 0)
        
        return jsonify({
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volatility': volatility,
            'trade_count': len(trades),
            'ai_score': ai_score
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ohlcv/<symbol>')
def get_ohlcv(symbol: str):
    """Get OHLCV data for a symbol."""
    try:
        timeframe = request.args.get('timeframe', '1h')
        
        # Load OHLCV data
        ohlcv_df = load_ohlcv_data(symbol, timeframe)
        
        if ohlcv_df.empty:
            return jsonify([])
        
        # Convert to list of dicts for JSON serialization
        result = []
        for _, row in ohlcv_df.iterrows():
            result.append({
                'timestamp': row['timestamp'].isoformat() if isinstance(row['timestamp'], datetime) else row['timestamp'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row.get('volume', 0)
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/daily-summary')
def get_daily_summary():
    """Get daily summary."""
    try:
        summary = get_cached_data('daily_summary', calculate_daily_summary, LOG_DIR)
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai-signal')
def get_ai_signal():
    """Get latest AI signal."""
    try:
        brain_scoring = get_cached_data('ai_signal', load_latest_brain_scoring, LOG_DIR)
        
        score = brain_scoring.get('score', 0)
        signal = 'NEUTRAL'
        
        if score > 0.3:
            signal = 'BULLISH'
        elif score < -0.3:
            signal = 'BEARISH'
        
        return jsonify({
            'signal': signal,
            'score': score,
            'timestamp': brain_scoring.get('timestamp', '')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/status')
def get_status():
    """Get system status."""
    try:
        settings = load_settings()
        portfolio_state = load_latest_state(LOG_DIR)
        
        # Calculate daily P&L
        daily_summary = calculate_daily_summary(LOG_DIR)
        daily_pnl = daily_summary.get('daily_pnl', 0)
        
        # Determine status
        status = 'RUNNING'
        if daily_pnl < -100:  # Large loss
            status = 'WARNING'
        elif daily_pnl < -500:  # Very large loss
            status = 'CRITICAL'
        
        return jsonify({
            'status': status,
            'mode': settings.app.mode.value,
            'equity': portfolio_state.get('total_value', 0),
            'daily_pnl': daily_pnl,
            'positions_count': len(portfolio_state.get('positions', {})),
            'last_update': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/symbols')
def get_symbols():
    """Get available trading symbols."""
    try:
        settings = load_settings()
        return jsonify({
            'symbols': settings.market.symbols,
            'timeframes': settings.market.timeframes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print(f"Starting BAET Dashboard API server on http://{HOST}:{PORT}")
    print(f"Serving dashboard from: {Path(__file__).parent}")
    app.run(host=HOST, port=PORT, debug=True)