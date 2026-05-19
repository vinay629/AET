"""Structured logging with trace IDs for BAET.

Every decision is traceable:
    trace_id → signal_id → order_id → event_id → strategy_id → replay_id

Usage:
    with trace("order_submission", symbol="BTCUSDT", side="BUY") as t:
        t.add_context(order_id="baet-xxx", strategy="sma_crossover")
        result = submit_order(...)
        t.add_context(fill_price=str(result.price))

Produces structured JSON logs that can be:
- Searched by any ID in the dashboard audit panel
- Correlated across services
- Replayed for debugging
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Context variables — propagate trace IDs through async calls
_current_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_current_signal_id: ContextVar[str | None] = ContextVar("signal_id", default=None)
_current_order_id: ContextVar[str | None] = ContextVar("order_id", default=None)
_current_strategy_id: ContextVar[str | None] = ContextVar("strategy_id", default=None)
_current_replay_id: ContextVar[str | None] = ContextVar("replay_id", default=None)


def get_current_trace_id() -> str | None:
    return _current_trace_id.get()


def get_current_context() -> dict[str, str | None]:
    """Get current trace context for log correlation."""
    return {
        "trace_id": _current_trace_id.get(),
        "signal_id": _current_signal_id.get(),
        "order_id": _current_order_id.get(),
        "strategy_id": _current_strategy_id.get(),
        "replay_id": _current_replay_id.get(),
    }


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}-{uid}" if prefix else uid


# ---------------------------------------------------------------------------
# Structured log record
# ---------------------------------------------------------------------------

@dataclass
class LogRecord:
    """A structured log record with trace context."""
    timestamp: str
    level: str
    component: str
    event: str
    trace_id: str | None = None
    signal_id: str | None = None
    order_id: str | None = None
    strategy_id: str | None = None
    replay_id: str | None = None
    duration_ms: float | None = None
    context: dict[str, Any] = field(default_factory=dict)
    message: str = ""

    def to_json(self) -> str:
        data = {
            "ts": self.timestamp,
            "lvl": self.level,
            "comp": self.component,
            "event": self.event,
        }
        # Only include non-None IDs
        for key in ("trace_id", "signal_id", "order_id", "strategy_id", "replay_id"):
            val = getattr(self, key)
            if val:
                data[key] = val
        if self.duration_ms is not None:
            data["dur_ms"] = round(self.duration_ms, 2)
        if self.context:
            data["ctx"] = self.context
        if self.message:
            data["msg"] = self.message
        return json.dumps(data, default=str)


# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------

class StructuredLogger:
    """Logger that produces structured JSON records with trace context."""

    def __init__(self, name: str, log_dir: Path | None = None) -> None:
        self.name = name
        self._logger = logging.getLogger(name)
        self._log_dir = log_dir
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)

    def _log(
        self,
        level: str,
        event: str,
        message: str = "",
        context: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        trace_id: str | None = None,
        signal_id: str | None = None,
        order_id: str | None = None,
        strategy_id: str | None = None,
        replay_id: str | None = None,
    ) -> LogRecord:
        """Create and emit a structured log record."""
        record = LogRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            component=self.name,
            event=event,
            trace_id=trace_id or get_current_trace_id(),
            signal_id=signal_id or _current_signal_id.get(),
            order_id=order_id or _current_order_id.get(),
            strategy_id=strategy_id or _current_strategy_id.get(),
            replay_id=replay_id or _current_replay_id.get(),
            duration_ms=duration_ms,
            context=context or {},
            message=message,
        )

        # Emit to standard logger
        log_line = record.to_json()
        level_map = {
            "DEBUG": self._logger.debug,
            "INFO": self._logger.info,
            "WARNING": self._logger.warning,
            "ERROR": self._logger.error,
            "CRITICAL": self._logger.critical,
        }
        log_fn = level_map.get(level, self._logger.info)
        log_fn(log_line)

        # Emit to structured log file
        if self._log_dir:
            self._write_to_file(record)

        return record

    def _write_to_file(self, record: LogRecord) -> None:
        """Write to daily structured log file."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self._log_dir / f"structured_{date_str}.jsonl"
        with log_file.open("a") as f:
            f.write(record.to_json() + "\n")

    def debug(self, event: str, **kwargs: Any) -> LogRecord:
        return self._log("DEBUG", event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> LogRecord:
        return self._log("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> LogRecord:
        return self._log("WARNING", event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> LogRecord:
        return self._log("ERROR", event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> LogRecord:
        return self._log("CRITICAL", event, **kwargs)


# ---------------------------------------------------------------------------
# Trace context manager
# ---------------------------------------------------------------------------

@contextmanager
def trace(
    event: str,
    component: str = "system",
    trace_id: str | None = None,
    **context: Any,
):
    """
    Context manager for tracing an operation.

    Usage:
        with trace("order_submission", component="execution", symbol="BTCUSDT") as t:
            t.set(signal_id="sig-xxx")
            t.add_context(side="BUY", quantity="0.01")
            result = submit_order(...)
            t.add_context(fill_price=str(result.price))
    """
    logger = StructuredLogger(component)
    tid = trace_id or generate_id("trace")
    token = _current_trace_id.set(tid)
    start = time.monotonic()

    class TraceContext:
        def __init__(self) -> None:
            self.trace_id = tid

        def set(
            self,
            signal_id: str | None = None,
            order_id: str | None = None,
            strategy_id: str | None = None,
            replay_id: str | None = None,
        ) -> None:
            if signal_id:
                _current_signal_id.set(signal_id)
            if order_id:
                _current_order_id.set(order_id)
            if strategy_id:
                _current_strategy_id.set(strategy_id)
            if replay_id:
                _current_replay_id.set(replay_id)

        def add_context(self, **kwargs: Any) -> None:
            context.update(kwargs)

    ctx = TraceContext()

    try:
        yield ctx
        duration = (time.monotonic() - start) * 1000
        logger.info(
            event,
            context=context,
            duration_ms=duration,
            trace_id=tid,
        )
    except Exception as e:
        duration = (time.monotonic() - start) * 1000
        logger.error(
            f"{event}_failed",
            context={**context, "error": str(e)},
            duration_ms=duration,
            trace_id=tid,
        )
        raise
    finally:
        _current_trace_id.reset(token)
