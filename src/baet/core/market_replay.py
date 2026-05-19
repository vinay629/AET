"""Replayable market stream for BAET.

Records raw websocket packets during live/paper trading,
then replays them exactly for backtesting, debugging, and certification.

The guarantee: replaying the same packet stream produces the same
events, which produce the same state transitions.

Usage:
    # During live trading:
    recorder = PacketRecorder(raw_dir)
    recorder.record(ws_packet, received_at)

    # Later, for replay:
    replay = MarketReplay(raw_dir, event_store)
    replay.replay_date("2026-05-18")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from baet.core.clock import Clock
from baet.core.events import EventStore, EventType
from baet.core.websocket_ingest import PacketRecorder, normalize_binance_kline

logger = logging.getLogger(__name__)


class MarketReplay:
    """
    Replays recorded websocket packets through the same ingestion
    pipeline used during live trading.

    This ensures that the candle → event → reducer → state path
    is identical whether data arrives from live websocket or replay.
    """

    def __init__(
        self,
        raw_dir: Path,
        event_store: EventStore,
        clock: Clock | None = None,
    ) -> None:
        self.raw_dir = raw_dir
        self.event_store = event_store
        self.clock = clock

    def replay_date(
        self,
        date: str,
        *,
        realtime: bool = False,
        speed: float = 1.0,
    ) -> int:
        """
        Replay all recorded packets for a given date.

        Args:
            date: Date string (YYYY-MM-DD).
            realtime: If True, replay at original timing intervals.
            speed: Speed multiplier for realtime replay (2.0 = 2x).

        Returns:
            Number of packets replayed.
        """
        raw_file = self.raw_dir / f"ws_raw_{date}.jsonl"
        if not raw_file.exists():
            logger.warning(f"No raw packets found for {date}")
            return 0

        count = 0
        last_ts: datetime | None = None

        with raw_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                raw_packet = record.get("packet", {})
                received_at_str = record.get("received_at", "")

                try:
                    received_at = datetime.fromisoformat(received_at_str)
                except (ValueError, TypeError):
                    received_at = datetime.now(timezone.utc)

                # Replay through the same normalization path
                try:
                    candle = normalize_binance_kline(raw_packet, received_at)
                except (KeyError, ValueError, TypeError):
                    continue

                # Realtime delay
                if realtime and last_ts is not None:
                    import time
                    delay = (received_at - last_ts).total_seconds() / speed
                    if delay > 0:
                        time.sleep(delay)

                last_ts = received_at

                # Produce event (same as live path)
                self.event_store.append(
                    event_type=EventType.CANDLE_RECEIVED,
                    timestamp_exchange=candle.open_time,
                    source="market_replay",
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
                )
                count += 1

        logger.info(f"Replayed {count} packets for {date}")
        return count

    def replay_range(
        self,
        from_date: str,
        to_date: str,
        **kwargs: Any,
    ) -> int:
        """Replay packets across a date range (inclusive)."""
        from datetime import timedelta

        current = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
        total = 0

        while current <= end:
            total += self.replay_date(current.strftime("%Y-%m-%d"), **kwargs)
            current += timedelta(days=1)

        logger.info(f"Replayed {total} packets from {from_date} to {to_date}")
        return total

    def list_available_dates(self) -> list[str]:
        """List dates that have recorded packets."""
        dates = []
        for f in sorted(self.raw_dir.glob("ws_raw_*.jsonl")):
            date_str = f.stem.replace("ws_raw_", "")
            dates.append(date_str)
        return dates
