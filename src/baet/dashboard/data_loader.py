"""Data loading utilities for the BAET dashboard."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def find_latest_log_file(log_dir: str = "logs/paper") -> Path | None:
    """Find the most recent paper trading log file.

    Args:
        log_dir: Directory containing log files

    Returns:
        Path to the most recent log file, or None if not found
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return None

    log_files = list(log_path.glob("paper_trading_*.log"))
    if not log_files:
        return None

    # Sort by date in filename (paper_trading_YYYY-MM-DD.log)
    # Extract date from filename and sort by it
    def extract_date(filepath: Path) -> str:
        # Expected format: paper_trading_YYYY-MM-DD.log
        name = filepath.stem  # Get filename without extension
        date_part = name.replace("paper_trading_", "")
        return date_part

    try:
        log_files.sort(key=extract_date, reverse=True)
    except Exception:
        # Fall back to modification time if date parsing fails
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    return log_files[0]


def parse_log_file(log_file: Path, max_entries: int = 100) -> list[dict[str, Any]]:
    """Parse a JSON-formatted log file.

    Args:
        log_file: Path to the log file
        max_entries: Maximum number of entries to return (most recent)

    Returns:
        List of log entries as dictionaries
    """
    entries = []

    if not log_file.exists():
        return entries

    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    # Return most recent entries
    return entries[-max_entries:] if max_entries else entries


def load_latest_state(log_dir: str = "logs/paper") -> dict[str, Any]:
    """Load the most recent portfolio state from logs.

    Args:
        log_dir: Directory containing log files

    Returns:
        Dictionary with current portfolio state
    """
    log_file = find_latest_log_file(log_dir)
    if not log_file:
        return {}

    entries = parse_log_file(log_file, max_entries=1000)

    # Find the most recent PORTFOLIO_UPDATE entry
    for entry in reversed(entries):
        if entry.get("type") == "PORTFOLIO_UPDATE":
            return {
                "cash": entry.get("cash", 0.0),
                "total_value": entry.get("total_value", 0.0),
                "positions": entry.get("positions", {}),
                "action": entry.get("action", ""),
                "symbol": entry.get("symbol"),
                "timestamp": entry.get("timestamp"),
            }

    return {}


def load_recent_trades(log_dir: str = "logs/paper", limit: int = 50) -> list[dict[str, Any]]:
    """Load recent trades from logs.

    Args:
        log_dir: Directory containing log files
        limit: Maximum number of trades to return

    Returns:
        List of recent trades
    """
    log_file = find_latest_log_file(log_dir)
    if not log_file:
        return []

    entries = parse_log_file(log_file, max_entries=10000)

    # Filter for portfolio updates (which include trades)
    trades: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("type") == "PORTFOLIO_UPDATE" and entry.get("action") in ["BUY", "SELL"]:
            trades.append(
                {
                    "timestamp": entry.get("timestamp"),
                    "action": entry.get("action"),
                    "symbol": entry.get("symbol"),
                    "cash_after": entry.get("cash"),
                    "total_value_after": entry.get("total_value"),
                }
            )

    # Return most recent trades
    return trades[-limit:] if limit else trades


def load_equity_curve(log_dir: str = "logs/paper") -> pd.DataFrame:
    """Load equity curve data from logs.

    Args:
        log_dir: Directory containing log files

    Returns:
        DataFrame with equity curve data
    """
    log_file = find_latest_log_file(log_dir)
    if not log_file:
        return pd.DataFrame()

    entries = parse_log_file(log_file, max_entries=10000)

    # Filter for portfolio updates
    equity_data = []
    for entry in entries:
        if entry.get("type") == "PORTFOLIO_UPDATE":
            equity_data.append(
                {
                    "timestamp": entry.get("timestamp"),
                    "cash": entry.get("cash", 0.0),
                    "total_value": entry.get("total_value", 0.0),
                    "action": entry.get("action", ""),
                    "symbol": entry.get("symbol"),
                }
            )

    if not equity_data:
        return pd.DataFrame()

    df = pd.DataFrame(equity_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    # Add returns for win rate calculation
    df["returns"] = df["total_value"].pct_change()

    return df


from datetime import timedelta

import streamlit as st


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_ohlcv_data(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load OHLCV data prioritizing local Parquet data, then Binance API.

    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        timeframe: Candle timeframe (e.g., 1h)

    Returns:
        DataFrame with OHLCV data
    """
    from baet.config.loader import load_settings

    settings = load_settings()

    # 1. Try local Parquet storage first
    try:
        from baet.data.storage import ParquetMarketDataStore

        store = ParquetMarketDataStore(settings)
        df = store.read_raw_candles(symbol, timeframe)
        if not df.empty:
            if "open_time" in df.columns and "timestamp" not in df.columns:
                df = df.rename(columns={"open_time": "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp")
            return df
    except Exception:
        # File not found or other storage error, proceed to API
        pass

    # 2. Fallback to Binance API
    try:
        from baet.data.binance import BinanceHistoricalProvider

        provider = BinanceHistoricalProvider(settings)

        # Fetch candles based on historical_limit
        limit = settings.binance.historical_limit
        end_time = datetime.now()

        # Approximate start time based on timeframe
        if timeframe == "1h":
            start_time = end_time - timedelta(hours=100)
        elif timeframe == "4h":
            start_time = end_time - timedelta(hours=400)
        elif timeframe == "1m":
            start_time = end_time - timedelta(minutes=100)
        elif timeframe == "5m":
            start_time = end_time - timedelta(minutes=500)
        elif timeframe == "15m":
            start_time = end_time - timedelta(minutes=1500)
        elif timeframe == "1d":
            start_time = end_time - timedelta(days=100)
        else:
            start_time = end_time - timedelta(hours=100)

        df = provider.fetch_klines(symbol, timeframe, start_time, end_time)

        if not df.empty:
            if "open_time" in df.columns and "timestamp" not in df.columns:
                df = df.rename(columns={"open_time": "timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            return df.sort_values("timestamp")

    except Exception as e:
        print(f"Error loading OHLCV data for {symbol} {timeframe} from Binance: {e}")
        # Fallback to local data if API fails
        try:
            from baet.data.storage import ParquetMarketDataStore

            store = ParquetMarketDataStore(load_settings())
            df = store.read_raw_candles(symbol, timeframe)
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.sort_values("timestamp")
            return df
        except:
            return pd.DataFrame()


def load_latest_brain_scoring(log_dir: str = "logs/paper") -> dict[str, Any]:
    """Load the latest AI Brain scoring event.

    Args:
        log_dir: Directory containing log files

    Returns:
        Latest brain scoring event or empty dict
    """
    log_file = find_latest_log_file(log_dir)
    if not log_file:
        return {}

    entries = parse_log_file(log_file, max_entries=1000)

    for entry in reversed(entries):
        if entry.get("type") == "BRAIN_SCORING":
            return entry

    return {}


def load_recent_signals(log_dir: str = "logs/paper", limit: int = 50) -> list[dict[str, Any]]:
    """Load recent signals from logs.

    Args:
        log_dir: Directory containing log files
        limit: Maximum number of signals to return

    Returns:
        List of recent signals
    """
    log_file = find_latest_log_file(log_dir)
    if not log_file:
        return []

    entries = parse_log_file(log_file, max_entries=5000)

    signals: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("type") == "SIGNAL_RECEIVED":
            signals.append(entry)

    return signals[-limit:] if limit else signals


def calculate_daily_summary(log_dir: str = "logs/paper", date: str | None = None) -> dict[str, Any]:
    """Calculate daily summary from logs.

    Args:
        log_dir: Directory containing log files
        date: Date string (YYYY-MM-DD), or None for today

    Returns:
        Dictionary with daily summary
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    log_file = Path(log_dir) / f"paper_trading_{date}.log"
    if not log_file.exists():
        return {}

    entries = parse_log_file(log_file, max_entries=100000)

    # Calculate summary
    trades = [
        e
        for e in entries
        if e.get("type") == "PORTFOLIO_UPDATE" and e.get("action") in ["BUY", "SELL"]
    ]
    signals = [e for e in entries if e.get("type") == "SIGNAL_RECEIVED"]
    risk_evals = [e for e in entries if e.get("type") == "RISK_EVALUATION"]

    # Get start and end portfolio values
    portfolio_updates = [e for e in entries if e.get("type") == "PORTFOLIO_UPDATE"]

    start_value = portfolio_updates[0].get("total_value", 0.0) if portfolio_updates else 0.0
    end_value = portfolio_updates[-1].get("total_value", 0.0) if portfolio_updates else 0.0

    daily_pnl = end_value - start_value
    daily_return = (end_value - start_value) / start_value if start_value > 0 else 0.0

    return {
        "date": date,
        "start_value": start_value,
        "end_value": end_value,
        "daily_pnl": daily_pnl,
        "daily_return": daily_return,
        "trade_count": len(trades),
        "signal_count": len(signals),
        "risk_evaluation_count": len(risk_evals),
        "passed_risk": sum(1 for e in risk_evals if e.get("result", {}).get("passed", True)),
        "failed_risk": sum(1 for e in risk_evals if not e.get("result", {}).get("passed", True)),
    }


def calculate_performance_metrics(log_dir: str = "logs/paper") -> dict[str, Any]:
    """Calculate performance metrics from equity curve.

    Args:
        log_dir: Directory containing log files

    Returns:
        Dictionary with performance metrics
    """
    df = load_equity_curve(log_dir)

    if df.empty or len(df) < 2:
        return {}

    # Calculate returns
    df["returns"] = df["total_value"].pct_change()

    # Remove NaN values
    returns = df["returns"].dropna()

    if len(returns) < 2:
        return {}

    # Sharpe ratio (assuming risk-free rate = 0)
    sharpe = returns.mean() / returns.std() * (252**0.5) if returns.std() > 0 else 0.0

    # Sortino ratio (downside deviation)
    downside_returns = returns[returns < 0]
    sortino = (
        returns.mean() / downside_returns.std() * (252**0.5)
        if len(downside_returns) > 0 and downside_returns.std() > 0
        else 0.0
    )

    # Maximum drawdown
    df["cumulative_max"] = df["total_value"].cummax()
    df["drawdown"] = (df["total_value"] - df["cumulative_max"]) / df["cumulative_max"]
    max_drawdown = df["drawdown"].min()

    # Total return
    start_value = df["total_value"].iloc[0]
    end_value = df["total_value"].iloc[-1]
    total_return = (end_value - start_value) / start_value if start_value > 0 else 0.0

    return {
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
        "total_return": total_return,
        "annualized_return": (1 + total_return) ** (252 / len(df)) - 1 if len(df) > 0 else 0.0,
        "volatility": returns.std() * (252**0.5),
        "win_rate": (returns > 0).sum() / len(returns) if len(returns) > 0 else 0.0,
    }
