"""Decision logging system for paper trading.

Provides structured JSON logging for all paper trading decisions,
enabling post-hoc analysis and debugging.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class PaperTradingLogger:
    """Structured logger for paper trading decisions.

    Logs all decisions as JSON-formatted entries with context,
    enabling easy parsing and analysis.
    """

    def __init__(
        self,
        log_dir: str = "logs/paper",
        level: str = "INFO",
        rotation: str = "daily",
        max_files: int = 30,
    ):
        """Initialize the logger.

        Args:
            log_dir: Directory to store log files
            level: Logging level (DEBUG, INFO, WARNING, ERROR)
            rotation: Log rotation strategy ("daily", "size")
            max_files: Maximum number of log files to keep
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.level = getattr(logging, level.upper())
        self.rotation = rotation
        self.max_files = max_files

        # Set up Python logger
        self._logger = logging.getLogger("baet.paper")
        self._logger.setLevel(self.level)

        # Remove existing handlers to avoid duplicates
        self._logger.handlers.clear()

        # Create file handler with rotation
        log_file = self._get_log_file()
        handler = logging.FileHandler(log_file)
        handler.setLevel(self.level)

        # JSON formatter
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

        self._logger.addHandler(handler)
        self._logger.propagate = False

        # Log engine start
        self.log_engine_event(
            "LOGGER_INITIALIZED",
            {
                "log_dir": str(self.log_dir),
                "level": level,
                "rotation": rotation,
            },
        )

    def _get_log_file(self) -> Path:
        """Get the current log file path based on rotation strategy."""
        if self.rotation == "daily":
            date_str = datetime.now().strftime("%Y-%m-%d")
            return self.log_dir / f"paper_trading_{date_str}.log"
        else:
            return self.log_dir / "paper_trading.log"

    def _rotate_logs(self):
        """Rotate log files, keeping only the most recent ones."""
        log_files = sorted(self.log_dir.glob("paper_trading_*.log"), reverse=True)

        if len(log_files) > self.max_files:
            for old_file in log_files[self.max_files :]:
                old_file.unlink()

    def _log_json(self, entry_type: str, data: dict[str, Any]):
        """Log a JSON-formatted entry.

        Args:
            entry_type: Type of log entry (SIGNAL, RISK, ORDER, etc.)
            data: Dictionary of data to log
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": entry_type,
            **data,
        }

        self._logger.info(json.dumps(entry))

    def log_signal_received(self, symbol: str, signal: dict[str, Any]):
        """Log a strategy signal.

        Args:
            symbol: Trading symbol
            signal: Signal details (direction, strength, strategy, etc.)
        """
        self._log_json(
            "SIGNAL_RECEIVED",
            {
                "symbol": symbol,
                "signal": signal,
            },
        )

    def log_risk_evaluation(
        self,
        symbol: str,
        signal: dict[str, Any],
        result: dict[str, Any],
    ):
        """Log a risk evaluation result.

        Args:
            symbol: Trading symbol
            signal: Original signal
            result: Risk check result (passed, violations, etc.)
        """
        self._log_json(
            "RISK_EVALUATION",
            {
                "symbol": symbol,
                "signal": signal,
                "result": result,
            },
        )

    def log_order_simulated(
        self,
        symbol: str,
        side: str,
        requested_price: float,
        filled_price: float,
        units: float,
        fee: float,
        slippage: float,
    ):
        """Log an order simulation.

        Args:
            symbol: Trading symbol
            side: "BUY" or "SELL"
            requested_price: Price requested
            filled_price: Actual fill price
            units: Number of units
            fee: Fee charged
            slippage: Slippage amount
        """
        self._log_json(
            "ORDER_SIMULATED",
            {
                "symbol": symbol,
                "side": side,
                "requested_price": requested_price,
                "filled_price": filled_price,
                "units": units,
                "fee": fee,
                "slippage": slippage,
                "price_difference": filled_price - requested_price,
            },
        )

    def log_portfolio_update(
        self,
        action: str,
        symbol: str | None,
        cash: float,
        positions: dict[str, Any],
        total_value: float,
    ):
        """Log a portfolio state update.

        Args:
            action: Action that caused update (BUY, SELL, UPDATE)
            symbol: Symbol affected (if any)
            cash: Current cash balance
            positions: Current positions
            total_value: Total portfolio value
        """
        self._log_json(
            "PORTFOLIO_UPDATE",
            {
                "action": action,
                "symbol": symbol,
                "cash": cash,
                "positions": positions,
                "total_value": total_value,
            },
        )

    def log_engine_event(self, event: str, details: dict[str, Any] | None = None):
        """Log an engine event (start, stop, error, etc.).

        Args:
            event: Event type (START, STOP, ERROR, etc.)
            details: Additional event details
        """
        data = {"event": event}
        if details:
            data["details"] = details

        self._log_json("ENGINE_EVENT", data)

    def log_error(self, error: Exception, context: dict[str, Any] | None = None):
        """Log an error.

        Args:
            error: The exception that occurred
            context: Additional context about the error
        """
        data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        if context:
            data["context"] = context

        self._log_json("ERROR", data)
        self._logger.error(f"Error: {error}", exc_info=True)


def create_paper_logger_from_config(config: dict[str, Any]) -> PaperTradingLogger | None:
    """Create a PaperTradingLogger from configuration.

    Args:
        config: Configuration dictionary with logging settings

    Returns:
        PaperTradingLogger instance or None if logging is disabled
    """
    if not config.get("enabled", True):
        return None

    return PaperTradingLogger(
        log_dir=config.get("directory", "logs/paper"),
        level=config.get("level", "INFO"),
        rotation=config.get("rotation", "daily"),
        max_files=config.get("max_files", 30),
    )
