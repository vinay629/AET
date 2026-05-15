"""Flask API server for BAET dashboard.

Serves the HTML dashboard and provides REST API endpoints.
Fetches live market data from Binance REST API.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timedelta
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
            _fetch_ohlcv, symbol, timeframe, limit,
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
            _fetch_recent_trades, symbol, limit,
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

        return jsonify({
            "tickers": filtered,
            "server_time": datetime.utcnow().isoformat() + "Z",
            "symbols_configured": settings.market.symbols,
            "timeframes_configured": settings.market.timeframes,
        })
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


@app.route("/api/performance")
def get_performance():
    """Get performance metrics (placeholder for live trading)."""
    try:
        return jsonify(
            {
                "sharpe_ratio": 0,
                "sortino_ratio": 0,
                "max_drawdown": 0,
                "win_rate": 0,
                "total_return": 0,
                "annualized_return": 0,
                "volatility": 0,
                "trade_count": 0,
                "ai_score": 0,
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


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    print(f"Starting BAET Dashboard API server on http://{HOST}:{PORT}")
    print(f"Serving dashboard from: {Path(__file__).parent}")
    app.run(host=HOST, port=PORT, debug=True)
