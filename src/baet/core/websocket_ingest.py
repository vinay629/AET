"""WebSocket market data ingestion for BAET.

Architecture:
    WebSocket stream
        → normalize (raw packet → canonical candle)
        → event store (CANDLE_RECEIVED event)
        → (strategies read from event store later)

CRITICAL: WebSocket handlers NEVER call strategies directly.
They only normalize and persist. This ensures:
1. Deterministic replay (same packets → same events → same decisions)
2. No hidden state mutations from the hot path
3. Clean separation between data ingestion and decision making

Raw packets are also saved for exact replay later.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from baet.core.clock import Clock, get_clock
from baet.core.events import EventStore, EventType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalized candle from websocket
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizedCandle:
    """Canonical candle format from any websocket source."""
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int
    is_closed: bool
    source: str = "websocket"
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Packet recorder — saves raw websocket packets for exact replay
# ---------------------------------------------------------------------------

class PacketRecorder:
    """Records raw websocket packets to disk for later replay."""

    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._handle = None
        self._current_file: Path | None = None

    def _file_for(self, dt: datetime) -> Path:
        return self.raw_dir / f"ws_raw_{dt.strftime('%Y-%m-%d')}.jsonl"

    def _ensure_handle(self, dt: datetime) -> None:
        path = self._file_for(dt)
        if path != self._current_file:
            if self._handle:
                self._handle.close()
            self._handle = path.open("a", encoding="utf-8")
            self._current_file = path

    def record(self, raw_packet: dict[str, Any], received_at: datetime) -> None:
        """Record a raw websocket packet with receive timestamp."""
        self._ensure_handle(received_at)
        record = {
            "received_at": received_at.isoformat(),
            "packet": raw_packet,
        }
        self._handle.write(json.dumps(record, default=str) + "\n")
        self._handle.flush()

    def close(self) -> None:
        if self._handle:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> PacketRecorder:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Binance websocket normalizer
# ---------------------------------------------------------------------------

def normalize_binance_kline(
    raw: dict[str, Any],
    received_at: datetime | None = None,
) -> NormalizedCandle:
    """
    Normalize a Binance websocket kline packet to canonical format.

    Binance kline stream format:
        {
            "e": "kline",
            "E": 123456789,
            "s": "BTCUSDT",
            "k": {
                "t": 123400000,   // open time
                "T": 123460000,   // close time
                "s": "BTCUSDT",
                "i": "1m",        // interval
                "f": 100,         // first trade id
                "L": 200,         // last trade id
                "o": "0.0010",    // open
                "c": "0.0020",    // close
                "h": "0.0025",    // high
                "l": "0.0005",    // low
                "v": "1000",      // base volume
                "n": 100,         // trade count
                "x": false,       // is closed
                "q": "1.2",       // quote volume
                "V": "500",       // taker buy base volume
                "Q": "0.6",       // taker buy quote volume
                "B": "123456"     // ignore
            }
        }
    """
    received_at = received_at or datetime.now(timezone.utc)

    # Handle both direct kline data and wrapped stream data
    kline = raw.get("k", raw)
    symbol = kline.get("s", raw.get("s", "UNKNOWN"))
    timeframe = kline.get("i", "1m")

    open_time = datetime.fromtimestamp(kline["t"] / 1000.0, tz=timezone.utc)
    close_time = datetime.fromtimestamp(kline["T"] / 1000.0, tz=timezone.utc)

    return NormalizedCandle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=open_time,
        close_time=close_time,
        open=float(kline["o"]),
        high=float(kline["h"]),
        low=float(kline["l"]),
        close=float(kline["c"]),
        volume=float(kline["v"]),
        quote_volume=float(kline.get("q", 0)),
        trade_count=int(kline.get("n", 0)),
        is_closed=kline.get("x", False),
        source="binance_ws",
        received_at=received_at,
    )


def normalize_binance_trade(
    raw: dict[str, Any],
    received_at: datetime | None = None,
) -> dict[str, Any]:
    """Normalize a Binance websocket trade packet."""
    received_at = received_at or datetime.now(timezone.utc)
    return {
        "symbol": raw.get("s", "UNKNOWN"),
        "price": float(raw.get("p", 0)),
        "quantity": float(raw.get("q", 0)),
        "trade_time": raw.get("T", 0),
        "is_buyer_maker": raw.get("m", False),
        "received_at": received_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Ingestion pipeline — the ONLY path from websocket to event store
# ---------------------------------------------------------------------------

class WebSocketIngest:
    """
    Ingests normalized websocket data into the event store.

    This is a pure data pipeline:
        raw packet → normalize → event store

    NO strategy calls. NO state mutations. NO portfolio updates.
    """

    def __init__(
        self,
        event_store: EventStore,
        packet_recorder: PacketRecorder | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.event_store = event_store
        self.packet_recorder = packet_recorder
        self.clock = clock or get_clock()

    def on_kline(self, raw_packet: dict[str, Any]) -> None:
        """
        Process a raw kline packet from the websocket.

        1. Record raw packet (for replay)
        2. Normalize to canonical format
        3. Append CANDLE_RECEIVED event to journal
        """
        received_at = self.clock.now()

        # Step 1: Record raw packet
        if self.packet_recorder:
            self.packet_recorder.record(raw_packet, received_at)

        # Step 2: Normalize
        try:
            candle = normalize_binance_kline(raw_packet, received_at)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Failed to normalize kline packet: {e}")
            return

        # Step 3: Persist as event
        self.event_store.append(
            event_type=EventType.CANDLE_RECEIVED,
            timestamp_exchange=candle.open_time,
            source="websocket_ingest",
            payload={
                "symbol": candle.symbol,
                "timeframe": candle.timeframe,
                "open_time": candle.open_time.isoformat(),
                "close_time": candle.close_time.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "quote_volume": candle.quote_volume,
                "trade_count": candle.trade_count,
                "is_closed": candle.is_closed,
            },
            clock=self.clock,
        )

        logger.debug(
            f"Candle persisted: {candle.symbol} {candle.timeframe} "
            f"O={candle.open} C={candle.close} V={candle.volume}"
        )

    def on_trade(self, raw_packet: dict[str, Any]) -> None:
        """Process a raw trade packet from the websocket."""
        received_at = self.clock.now()

        if self.packet_recorder:
            self.packet_recorder.record(raw_packet, received_at)

        try:
            trade = normalize_binance_trade(raw_packet, received_at)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Failed to normalize trade packet: {e}")
            return

        self.event_store.append(
            event_type=EventType.CANDLE_RECEIVED,  # Could add TRADE_RECEIVED
            timestamp_exchange=datetime.fromtimestamp(
                trade["trade_time"] / 1000.0, tz=timezone.utc
            ),
            source="websocket_ingest",
            payload=trade,
            clock=self.clock,
        )
