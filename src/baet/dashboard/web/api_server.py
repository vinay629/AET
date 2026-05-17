"""Flask API server for BAET dashboard.

Serves the HTML dashboard and provides REST API endpoints.
Fetches live market data from Binance REST API.
"""

from __future__ import annotations

import contextlib
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Add src to path so we can import baet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from baet.config.loader import load_settings

# ---------------------------------------------------------------------------
# Binance REST API helpers
# ---------------------------------------------------------------------------
_cache: dict[str, Any] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 30  # seconds


def _binance_get(path: str, params: dict | None = None) -> Any:
    """Make a GET request to Binance REST API and return parsed JSON."""
    settings = load_settings()
    base = settings.binance.rest_base_url.rstrip("/")
    url = f"{base}{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    with urlopen(url, timeout=settings.binance.request_timeout_seconds) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _cached(key: str, fetch_fn, *args, **kwargs):
    """Thread-safe TTL cache."""
    now = time.monotonic()
    with _cache_lock:
        if key in _cache and (now - _cache[key]["ts"]) < _CACHE_TTL:
            return _cache[key]["data"]
    data = fetch_fn(*args, **kwargs)
    with _cache_lock:
        _cache[key] = {"data": data, "ts": now}
    return data


def _fetch_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> list[dict]:
    """Fetch OHLCV klines from Binance."""
    raw = _binance_get(
        "/api/v3/klines",
        {"symbol": symbol.upper(), "interval": timeframe, "limit": limit},
    )
    return [
        {
            "timestamp": datetime.utcfromtimestamp(r[0] / 1000).isoformat() + "Z",
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
            "close_time": datetime.utcfromtimestamp(r[6] / 1000).isoformat() + "Z",
            "quote_volume": float(r[7]),
            "trade_count": int(r[8]),
        }
        for r in raw
    ]


def _fetch_ticker_24h(symbol: str | None = None):
    """Fetch 24h ticker from Binance."""
    params = {"symbol": symbol.upper()} if symbol else None
    raw = _binance_get("/api/v3/ticker/24hr", params)

    def _parse(row):
        return {
            "symbol": row["symbol"],
            "last_price": float(row["lastPrice"]),
            "price_change": float(row["priceChange"]),
            "price_change_pct": float(row["priceChangePercent"]),
            "high_price": float(row["highPrice"]),
            "low_price": float(row["lowPrice"]),
            "volume": float(row["volume"]),
            "quote_volume": float(row["quoteVolume"]),
            "open_price": float(row["openPrice"]),
            "prev_close": float(row["prevClosePrice"]),
            "trade_count": int(row["count"]),
        }

    if isinstance(raw, list):
        return [_parse(r) for r in raw]
    return _parse(raw)


def _fetch_orderbook(symbol: str, limit: int = 20) -> dict:
    """Fetch order book depth from Binance."""
    raw = _binance_get("/api/v3/depth", {"symbol": symbol.upper(), "limit": limit})
    return {
        "symbol": symbol.upper(),
        "last_update_id": raw["lastUpdateId"],
        "bids": [[float(p), float(q)] for p, q in raw["bids"]],
        "asks": [[float(p), float(q)] for p, q in raw["asks"]],
    }


def _fetch_recent_trades(symbol: str, limit: int = 50) -> list[dict]:
    """Fetch recent trades from Binance."""
    raw = _binance_get("/api/v3/trades", {"symbol": symbol.upper(), "limit": limit})
    return [
        {
            "id": t["id"],
            "price": float(t["price"]),
            "qty": float(t["qty"]),
            "quote_qty": float(t["quoteQty"]),
            "time": datetime.utcfromtimestamp(t["time"] / 1000).isoformat() + "Z",
            "is_buyer_maker": t["isBuyerMaker"],
            "side": "SELL" if t["isBuyerMaker"] else "BUY",
        }
        for t in raw
    ]


app = Flask(__name__)
CORS(app)

PORT = 8501
HOST = "localhost"


@app.route("/")
def dashboard():
    """Serve the main dashboard HTML."""
    return send_from_directory(".", "index.html")


@app.route("/styles.css")
def serve_css():
    return send_from_directory(".", "styles.css", mimetype="text/css")


@app.route("/dashboard.js")
def serve_js():
    return send_from_directory(".", "dashboard.js", mimetype="application/javascript")


# ---------------------------------------------------------------------------
# Live market data endpoints (Binance REST API)
# ---------------------------------------------------------------------------


@app.route("/api/ohlcv/<symbol>")
def get_ohlcv(symbol: str):
    """Get OHLCV kline data from Binance."""
    try:
        timeframe = request.args.get("timeframe", "1h")
        limit = int(request.args.get("limit", 500))
        data = _cached(
            f"ohlcv_{symbol}_{timeframe}_{limit}",
            _fetch_ohlcv,
            symbol,
            timeframe,
            limit,
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ticker/<symbol>")
def get_ticker(symbol: str):
    """Get 24h ticker for a symbol from Binance."""
    try:
        data = _cached(f"ticker_{symbol}", _fetch_ticker_24h, symbol)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tickers")
def get_all_tickers():
    """Get 24h tickers for all configured symbols."""
    try:
        settings = load_settings()
        data = _cached("all_tickers", _fetch_ticker_24h, None)
        symbols = {s.upper() for s in settings.market.symbols}
        if isinstance(data, list):
            filtered = [t for t in data if t["symbol"] in symbols]
        else:
            filtered = [data] if data["symbol"] in symbols else []
        return jsonify(filtered)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/orderbook/<symbol>")
def get_orderbook(symbol: str):
    """Get order book depth from Binance."""
    try:
        limit = int(request.args.get("limit", 20))
        data = _cached(f"ob_{symbol}_{limit}", _fetch_orderbook, symbol, limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/binance-trades/<symbol>")
def get_binance_trades(symbol: str):
    """Get recent trades from Binance."""
    try:
        limit = int(request.args.get("limit", 50))
        data = _cached(
            f"btrades_{symbol}_{limit}",
            _fetch_recent_trades,
            symbol,
            limit,
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/market-summary")
def get_market_summary():
    """Get a combined market summary: tickers + server time."""
    try:
        settings = load_settings()
        tickers = _cached("all_tickers", _fetch_ticker_24h, None)
        symbols = {s.upper() for s in settings.market.symbols}
        if isinstance(tickers, list):
            filtered = [t for t in tickers if t["symbol"] in symbols]
        else:
            filtered = [tickers] if tickers["symbol"] in symbols else []

        return jsonify(
            {
                "tickers": filtered,
                "server_time": datetime.utcnow().isoformat() + "Z",
                "symbols_configured": settings.market.symbols,
                "timeframes_configured": settings.market.timeframes,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Portfolio / equity / positions / trades / logs endpoints
# (derived from config and, where available, the in-process running engine)
# ---------------------------------------------------------------------------


def _portfolio_snapshot() -> dict[str, object]:
    """Derive a portfolio dict from the running engine or from default config."""
    global _paper_engine, _live_engine
    cash = 0.0
    total_value = 0.0
    initial_balance = 10_000.0
    daily_pnl = 0.0
    positions_raw: list[dict[str, object]] = []
    try:
        settings = load_settings()
        initial_balance = settings.paper.initial_balance
    except Exception:
        pass

    with _engine_lock:
        if _paper_engine and getattr(_paper_engine, "running", False):
            try:
                p = getattr(_paper_engine, "portfolio", None)
                if p is not None:
                    cash = getattr(p, "cash", 0.0)
                    total_value = getattr(p, "total_value", getattr(p, "cash", 0.0))
                    initial_balance = getattr(p, "initial_balance", initial_balance)
                    daily_pnl = getattr(p, "daily_pnl", 0.0)
                    for sym, pos in getattr(p, "positions", {}).items():
                        positions_raw.append(
                            {
                                "symbol": sym,
                                "units": pos.get("units", 0),
                                "avg_price": pos.get("avg_price", 0),
                                "current_price": pos.get("current_price", 0),
                            }
                        )
            except Exception:
                pass
        elif _live_engine and getattr(_live_engine, "running", False):
            try:
                p = getattr(_live_engine, "portfolio", None)
                if p is not None:
                    cash = getattr(p, "cash", 0.0)
                    total_value = getattr(p, "total_value", getattr(p, "cash", 0.0))
                    initial_balance = getattr(p, "initial_balance", initial_balance)
                    daily_pnl = getattr(p, "daily_pnl", 0.0)
            except Exception:
                pass

    if total_value == 0.0:
        total_value = initial_balance + daily_pnl

    return {
        "cash": cash,
        "total_value": total_value,
        "initial_balance": initial_balance,
        "daily_pnl": daily_pnl,
        "positions": positions_raw,
    }


def _positions_snapshot() -> list[dict[str, object]]:
    """Return open positions list from the running engine."""
    port = _portfolio_snapshot()
    return port["positions"]  # type: ignore[return-value]


def _recent_trades_snapshot(limit: int = 50) -> list[dict[str, object]]:
    """Return recent trade list from the running paper engine if available."""
    global _paper_engine
    try:
        if _paper_engine and getattr(_paper_engine, "running", False):
            oms = getattr(_paper_engine, "order_simulator", None)
            if oms:
                raw = getattr(oms, "trade_history", [])
                return raw[-limit:]
    except Exception:
        pass
    return []


def _logs_snapshot(limit: int = 50) -> list[dict[str, object]]:
    """Return recent log entries from `logs/paper/` JSONL files.

    Non-JSON lines (plain-text iteration summaries, engine init messages, etc.)
    are wrapped in a synthetic LOG_ENTRY so they still appear in the dashboard.
    """
    log_dir = Path("logs/paper")
    if not log_dir.exists():
        return []
    today_file = log_dir / f"paper_trading_{datetime.utcnow().strftime('%Y-%m-%d')}.log"
    if not today_file.exists():
        return []
    entries: list[dict[str, object]] = []
    try:
        with today_file.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    # Wrap non-JSON lines (iteration summaries, init messages, etc.)
                    entries.append(
                        {
                            "type": "LOG_ENTRY",
                            "message": line,
                        }
                    )
    except Exception:
        return []
    return entries[-limit:]


def _ai_signal_snapshot() -> dict[str, object]:
    """Return latest AI brain score entry from paper logs or empty default."""
    entries = _logs_snapshot(limit=1_000)
    for entry in reversed(entries):
        if entry.get("type") == "BRAIN_SCORING":
            return entry
    return {"score": 0.0, "label": "NEUTRAL", "timestamp": "", "components": {}}


def _equity_snapshot() -> dict[str, object]:
    """Return a simple equity array derived from paper log PORTFOLIO_UPDATE entries.

    Falls back to parsing plain-text iteration summary lines when no
    PORTFOLIO_UPDATE JSON entries are present (e.g. before the engine
    has been updated to emit them on every iteration).
    """
    import re as _re

    log_dir = Path("logs/paper")
    if not log_dir.exists():
        return {"equity": []}

    today_file = log_dir / f"paper_trading_{datetime.utcnow().strftime('%Y-%m-%d')}.log"
    if not today_file.exists():
        return {"equity": []}

    curve: list[dict[str, object]] = []
    # Pattern for plain-text iteration lines:
    # "Iteration: cash=10000.00, positions=0, value=10000.00"
    iter_pattern = _re.compile(r"Iteration:\s*cash=([\d.]+),\s*positions=(\d+),\s*value=([\d.]+)")
    last_timestamp = ""

    try:
        with today_file.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue

                # Try JSON first
                try:
                    entry = json.loads(line)
                    ts = entry.get("timestamp", "")
                    if ts:
                        last_timestamp = ts
                    if entry.get("type") == "PORTFOLIO_UPDATE":
                        curve.append(
                            {
                                "timestamp": ts,
                                "total_value": entry.get("total_value", 0.0),
                                "cash": entry.get("cash", 0.0),
                            }
                        )
                    continue
                except Exception:
                    pass

                # Fallback: parse plain-text iteration summary
                m = iter_pattern.search(line)
                if m:
                    curve.append(
                        {
                            "timestamp": last_timestamp,
                            "total_value": float(m.group(3)),
                            "cash": float(m.group(1)),
                        }
                    )
    except Exception:
        return {"equity": []}
    return {"equity": curve}


def _daily_summary_snapshot() -> dict[str, object]:
    """Return a simple daily summary dict derived from today's log."""
    from baet.dashboard.data_loader import calculate_daily_summary

    try:
        return calculate_daily_summary("logs/paper")
    except Exception:
        return {
            "date": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d"),
            "daily_pnl": 0.0,
            "daily_return": 0.0,
            "trade_count": 0,
            "signal_count": 0,
        }


@app.route("/api/portfolio")
def get_portfolio():
    """Return current portfolio state from running engine or config defaults."""
    try:
        return jsonify(_portfolio_snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/equity")
def get_equity():
    """Return equity curve snapshot from paper logs."""
    try:
        return jsonify(_equity_snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trades")
def get_trades():
    """Return recent trades from running engine or empty list."""
    try:
        return jsonify(_recent_trades_snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/positions")
def get_positions():
    """Return open positions from running engine."""
    try:
        return jsonify(_positions_snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logs")
def get_logs():
    """Return recent log entries from paper-trading JSONL files."""
    try:
        limit = int(request.args.get("limit", 50))
        return jsonify(_logs_snapshot(limit))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/performance")
def get_performance():
    """Return performance metrics, derived from equity log where available."""
    try:
        from baet.dashboard.data_loader import calculate_performance_metrics

        metrics = calculate_performance_metrics("logs/paper")
        if not metrics:
            return jsonify(
                {
                    "sharpe_ratio": 0,
                    "sortino_ratio": 0,
                    "max_drawdown": 0,
                    "total_return": 0,
                    "annualized_return": 0,
                    "volatility": 0,
                    "win_rate": 0,
                    "trade_count": 0,
                    "ai_score": 0,
                }
            )
        return jsonify(metrics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai-signal")
def get_ai_signal():
    """Return latest AI brain scoring event."""
    try:
        return jsonify(_ai_signal_snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/daily-summary")
def get_daily_summary():
    """Return today's trading activity summary."""
    try:
        return jsonify(_daily_summary_snapshot())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# System status endpoint
# ---------------------------------------------------------------------------


@app.route("/api/status")
def get_status():
    """Get system status including live market data."""
    try:
        settings = load_settings()

        # Get live ticker data for configured symbols
        tickers = _cached("status_tickers", _fetch_ticker_24h, None)
        symbols = {s.upper() for s in settings.market.symbols}
        if isinstance(tickers, list):
            filtered = [t for t in tickers if t["symbol"] in symbols]
        else:
            filtered = [tickers] if tickers["symbol"] in symbols else []

        return jsonify(
            {
                "status": "RUNNING",
                "mode": settings.app.mode.value,
                "equity": 0,
                "initial_balance": settings.paper.initial_balance,
                "daily_pnl": 0,
                "positions_count": 0,
                "tickers": filtered,
                "server_time": datetime.utcnow().isoformat() + "Z",
                "last_update": datetime.utcnow().isoformat() + "Z",
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/symbols")
def get_symbols():
    """Get available trading symbols and timeframes."""
    try:
        settings = load_settings()
        return jsonify(
            {"symbols": settings.market.symbols, "timeframes": settings.market.timeframes}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Trading engine control
# ---------------------------------------------------------------------------
_paper_engine = None
_live_engine = None
_engine_lock = threading.Lock()


@app.route("/api/engine/start", methods=["POST"])
def start_engine():
    """Start the trading engine (paper or live)."""
    global _paper_engine, _live_engine
    try:
        data = request.json or {}
        mode = data.get("mode", "paper")
        settings = load_settings()

        # Stop any running engine first
        with _engine_lock:
            if _paper_engine and getattr(_paper_engine, "running", False):
                with contextlib.suppress(Exception):
                    _paper_engine.stop()
                _paper_engine = None
            if _live_engine and getattr(_live_engine, "running", False):
                with contextlib.suppress(Exception):
                    _live_engine.stop()
                _live_engine = None

        # Create engine outside the lock
        if mode == "paper":
            from baet.paper.engine import PaperTradingEngine
            from baet.risk.engine import RiskEngine
            from baet.risk.policy import RiskPolicy

            risk_engine = RiskEngine(policy=RiskPolicy())
            engine = PaperTradingEngine(config=settings, risk_engine=risk_engine)
            with _engine_lock:
                _paper_engine = engine

            # Start the engine loop in a daemon thread
            def _run_engine():
                try:
                    engine.start()
                except Exception as e:
                    import logging

                    logging.error(f"Engine error: {e}")

            t = threading.Thread(target=_run_engine, daemon=True, name="paper-engine")
            t.start()
            return jsonify({"status": "started", "mode": "paper"})

        elif mode == "live":
            from baet.live.engine import LiveTradingEngine

            engine = LiveTradingEngine(config=settings)
            with _engine_lock:
                _live_engine = engine

            def _run_live():
                try:
                    engine.start()
                except Exception as e:
                    import logging

                    logging.error(f"Live engine error: {e}")

            t = threading.Thread(target=_run_live, daemon=True, name="live-engine")
            t.start()
            return jsonify({"status": "started", "mode": "live"})

        return jsonify({"error": f"Unknown mode: {mode}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/engine/stop", methods=["POST"])
def stop_engine():
    """Stop the running trading engine."""
    global _paper_engine, _live_engine
    try:
        with _engine_lock:
            if _paper_engine and getattr(_paper_engine, "running", False):
                with contextlib.suppress(Exception):
                    _paper_engine.stop()
                _paper_engine = None
            if _live_engine and getattr(_live_engine, "running", False):
                with contextlib.suppress(Exception):
                    _live_engine.stop()
                _live_engine = None
        return jsonify({"status": "stopped"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/engine/status")
def engine_status():
    """Get current engine status including portfolio state."""
    global _paper_engine, _live_engine
    try:
        paper_running = _paper_engine is not None and getattr(_paper_engine, "running", False)
        live_running = _live_engine is not None and getattr(_live_engine, "running", False)

        mode = "none"
        portfolio = {}
        positions = []
        trades = []

        if paper_running:
            mode = "paper"
            eng = _paper_engine
            if hasattr(eng, "portfolio"):
                p = eng.portfolio
                portfolio = {
                    "cash": p.cash,
                    "total_value": p.cash,
                    "initial_balance": p.initial_balance,
                    "daily_pnl": 0,
                }
                for sym, pos in p.positions.items():
                    positions.append(
                        {
                            "symbol": sym,
                            "units": pos.get("units", 0),
                            "avg_price": pos.get("avg_price", 0),
                            "current_price": pos.get("current_price", 0),
                        }
                    )
            if hasattr(eng, "order_simulator") and hasattr(eng.order_simulator, "trade_history"):
                trades = eng.order_simulator.trade_history[-20:]

        elif live_running:
            mode = "live"
            eng = _live_engine
            if hasattr(eng, "portfolio"):
                p = eng.portfolio
                portfolio = {
                    "cash": getattr(p, "cash", 0),
                    "total_value": getattr(p, "total_value", 0),
                    "initial_balance": getattr(p, "initial_balance", 10000),
                    "daily_pnl": getattr(p, "daily_pnl", 0),
                }

        return jsonify(
            {
                "mode": mode,
                "running": paper_running or live_running,
                "paper_running": paper_running,
                "live_running": live_running,
                "portfolio": portfolio,
                "positions": positions,
                "recent_trades": trades,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/order", methods=["POST"])
def place_order():
    """Place an order through the running engine."""
    global _paper_engine, _live_engine
    try:
        data = request.json or {}
        symbol = data.get("symbol", "BTCUSDT").upper()
        side = data.get("side", "BUY").upper()
        qty = float(data.get("qty", 0.001))

        if side not in ("BUY", "SELL"):
            return jsonify({"error": f"Invalid side: {side}"}), 400
        if qty <= 0:
            return jsonify({"error": "Quantity must be positive"}), 400

        with _engine_lock:
            if _paper_engine and getattr(_paper_engine, "running", False):
                result = _paper_engine.place_order(symbol, side, qty)
                if "error" in result:
                    return jsonify({"error": result["error"]}), 400
                return jsonify({"status": "filled", "mode": "paper", "result": result})

            if _live_engine and getattr(_live_engine, "running", False):
                result = _live_engine.place_order(symbol, side, qty)
                if "error" in result:
                    return jsonify({"error": result["error"]}), 400
                return jsonify({"status": "filled", "mode": "live", "result": result})

            return jsonify({"error": "No engine running. Start an engine first."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(_error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    print(f"Starting BAET Dashboard API server on http://{HOST}:{PORT}")
    print(f"Serving dashboard from: {Path(__file__).parent}")
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
