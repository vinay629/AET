"""Tests for WebSocket ingestion pipeline."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from baet.core.clock import Clock, set_clock, reset_clock
from baet.core.events import EventStore, EventType
from baet.core.websocket_ingest import (
    NormalizedCandle,
    PacketRecorder,
    WebSocketIngest,
    normalize_binance_kline,
    normalize_binance_trade,
)


TEST_TS = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def env(tmp_path):
    event_dir = tmp_path / "events"
    raw_dir = tmp_path / "raw"
    event_dir.mkdir()
    raw_dir.mkdir()
    set_clock(Clock.offset(TEST_TS, speed=1000.0))  # Fast-forward clock for testing
    store = EventStore(event_dir)
    recorder = PacketRecorder(raw_dir)
    ingest = WebSocketIngest(event_store=store, packet_recorder=recorder)
    yield {"store": store, "recorder": recorder, "ingest": ingest, "raw_dir": raw_dir}
    store.close()
    recorder.close()
    reset_clock()


def _make_binance_kline(
    symbol: str = "BTCUSDT",
    timeframe: str = "1m",
    open_price: float = 50000.0,
    close_price: float = 50100.0,
    high: float = 50200.0,
    low: float = 49900.0,
    volume: float = 100.0,
    is_closed: bool = True,
    open_time_ms: int = 1779105600000,  # 2026-05-18 12:00:00 UTC
) -> dict:
    close_time_ms = open_time_ms + 60000  # 1 minute later
    return {
        "e": "kline",
        "E": open_time_ms,
        "s": symbol,
        "k": {
            "t": open_time_ms,
            "T": close_time_ms,
            "s": symbol,
            "i": timeframe,
            "f": 100,
            "L": 200,
            "o": str(open_price),
            "c": str(close_price),
            "h": str(high),
            "l": str(low),
            "v": str(volume),
            "n": 50,
            "x": is_closed,
            "q": str(volume * close_price),
            "V": str(volume * 0.6),
            "Q": str(volume * close_price * 0.6),
            "B": "123456",
        },
    }


class TestNormalizeBinanceKline:
    def test_basic_normalization(self) -> None:
        raw = _make_binance_kline()
        candle = normalize_binance_kline(raw, TEST_TS)
        assert candle.symbol == "BTCUSDT"
        assert candle.timeframe == "1m"
        assert candle.open == 50000.0
        assert candle.close == 50100.0
        assert candle.high == 50200.0
        assert candle.low == 49900.0
        assert candle.volume == 100.0
        assert candle.is_closed is True

    def test_different_symbol(self) -> None:
        raw = _make_binance_kline(symbol="ETHUSDT")
        candle = normalize_binance_kline(raw, TEST_TS)
        assert candle.symbol == "ETHUSDT"

    def test_different_timeframe(self) -> None:
        raw = _make_binance_kline(timeframe="5m")
        candle = normalize_binance_kline(raw, TEST_TS)
        assert candle.timeframe == "5m"

    def test_received_at_set(self) -> None:
        raw = _make_binance_kline()
        candle = normalize_binance_kline(raw, TEST_TS)
        assert candle.received_at == TEST_TS


class TestNormalizeBinanceTrade:
    def test_basic_normalization(self) -> None:
        raw = {
            "e": "trade",
            "E": 1747569600000,
            "s": "BTCUSDT",
            "t": 12345,
            "p": "50000.0",
            "q": "0.01",
            "m": True,
        }
        trade = normalize_binance_trade(raw, TEST_TS)
        assert trade["symbol"] == "BTCUSDT"
        assert trade["price"] == 50000.0
        assert trade["quantity"] == 0.01
        assert trade["is_buyer_maker"] is True


class TestWebSocketIngest:
    def test_on_kline_produces_event(self, env) -> None:
        raw = _make_binance_kline()
        env["ingest"].on_kline(raw)

        events = env["store"].replay()
        assert len(events) == 1
        assert events[0].event_type == EventType.CANDLE_RECEIVED
        assert events[0].payload["symbol"] == "BTCUSDT"

    def test_on_kline_records_raw_packet(self, env) -> None:
        raw = _make_binance_kline()
        env["ingest"].on_kline(raw)

        # Check raw file
        raw_files = list(env["raw_dir"].glob("ws_raw_*.jsonl"))
        assert len(raw_files) == 1

        with raw_files[0].open("r") as f:
            line = f.readline()
            record = json.loads(line)
            assert "received_at" in record
            assert "packet" in record

    def test_multiple_klines(self, env) -> None:
        for i in range(5):
            raw = _make_binance_kline(
                open_time_ms=1779105600000 + i * 60000,
                close_price=50000.0 + i * 10,
            )
            env["ingest"].on_kline(raw)

        events = env["store"].replay()
        assert len(events) == 5

    def test_malformed_packet_skipped(self, env) -> None:
        env["ingest"].on_kline({"invalid": "data"})
        events = env["store"].replay()
        assert len(events) == 0

    def test_no_strategy_calls(self, env) -> None:
        """Verify that on_kline only produces events, no side effects."""
        raw = _make_binance_kline()
        env["ingest"].on_kline(raw)

        events = env["store"].replay()
        # Only CANDLE_RECEIVED — no SIGNAL_GENERATED, no ORDER_SUBMITTED
        assert all(e.event_type == EventType.CANDLE_RECEIVED for e in events)


class TestPacketRecorder:
    def test_record_and_read(self, tmp_path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        recorder = PacketRecorder(raw_dir)

        packet = {"test": "data", "value": 42}
        recorder.record(packet, TEST_TS)
        recorder.close()

        raw_files = list(raw_dir.glob("ws_raw_*.jsonl"))
        assert len(raw_files) == 1

        with raw_files[0].open("r") as f:
            line = f.readline()
            record = json.loads(line)
            assert record["packet"] == packet
            assert record["received_at"] == TEST_TS.isoformat()

    def test_context_manager(self, tmp_path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        with PacketRecorder(raw_dir) as recorder:
            recorder.record({"test": True}, TEST_TS)

        raw_files = list(raw_dir.glob("ws_raw_*.jsonl"))
        assert len(raw_files) == 1
