"""Walk-forward validation for BAET.

Replaces the naive train/test split with rolling windows:

    train 6m → test 1m
    slide window
    repeat
    aggregate

This prevents:
- Overfitting to a single test period
- Regime-specific bias
- Lookahead bias from fixed splits

Architecture:
    WalkForwardValidator
        ├── WindowConfig (train/test/step sizes)
        ├── WindowResult (metrics per window)
        └── AggregateResult (combined statistics)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pandas as pd

from baet.research.experiment import ExperimentConfig, ExperimentMetrics

logger = logging.getLogger(__name__)


@dataclass
class WindowConfig:
    """Configuration for walk-forward windows."""
    train_period: str = "6m"     # Training window size
    test_period: str = "1m"      # Test window size
    step_period: str = "1m"      # Step size (how far to slide)
    min_train_samples: int = 100  # Minimum samples in training

    def _parse_period(self, period: str) -> timedelta:
        """Parse period string like '6m', '1w', '1d' to timedelta."""
        units = {"d": "days", "w": "weeks", "m": "days"}
        num = int("".join(c for c in period if c.isdigit()))
        unit_char = "".join(c for c in period if c.isalpha()).lower()
        kwarg = units.get(unit_char, "days")
        if unit_char == "m":
            num = num * 30  # Approximate month as 30 days
        return timedelta(**{kwarg: num})


@dataclass
class WindowResult:
    """Results from a single walk-forward window."""
    window_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    metrics: ExperimentMetrics = field(default_factory=ExperimentMetrics)
    trades_count: int = 0
    status: str = "pending"
    error: str = ""


@dataclass
class AggregateResult:
    """Aggregated results across all walk-forward windows."""
    total_windows: int = 0
    completed_windows: int = 0
    failed_windows: int = 0

    # Average metrics
    avg_sharpe: float = 0.0
    avg_sortino: float = 0.0
    avg_calmar: float = 0.0
    avg_max_drawdown: float = 0.0
    avg_return: float = 0.0
    avg_hit_rate: float = 0.0

    # Consistency
    sharpe_std: float = 0.0
    pct_positive_windows: float = 0.0
    worst_window_sharpe: float = 0.0
    best_window_sharpe: float = 0.0

    # Robustness
    max_consecutive_lossing_windows: int = 0
    avg_turnover: float = 0.0
    total_trades: int = 0

    # Per-window details
    window_results: list[WindowResult] = field(default_factory=list)

    @property
    def is_robust(self) -> bool:
        """A strategy is robust if:
        - Sharpe > 0 in > 60% of windows
        - No more than 2 consecutive losing windows
        - Sharpe std < mean Sharpe (consistent)
        """
        if self.completed_windows < 3:
            return False
        if self.pct_positive_windows < 0.6:
            return False
        if self.max_consecutive_lossing_windows > 2:
            return False
        if self.sharpe_std > abs(self.avg_sharpe) * 2:
            return False
        return True


class WalkForwardValidator:
    """
    Walk-forward validation engine.

    For each window:
    1. Train on train_period
    2. Test on test_period (out-of-sample)
    3. Record metrics
    4. Slide window by step_period
    5. Aggregate results
    """

    def __init__(
        self,
        config: WindowConfig | None = None,
    ) -> None:
        self.config = config or WindowConfig()

    def generate_windows(
        self,
        start_date: str,
        end_date: str,
    ) -> list[tuple[str, str, str, str]]:
        """
        Generate train/test window pairs.

        Returns list of (train_start, train_end, test_start, test_end).
        """
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        train_delta = self.config._parse_period(self.config.train_period)
        test_delta = self.config._parse_period(self.config.test_period)
        step_delta = self.config._parse_period(self.config.step_period)

        windows = []
        current = start

        while current + train_delta + test_delta <= end:
            train_start = current
            train_end = current + train_delta
            test_start = train_end
            test_end = test_start + test_delta

            windows.append((
                train_start.isoformat(),
                train_end.isoformat(),
                test_start.isoformat(),
                test_end.isoformat(),
            ))

            current += step_delta

        logger.info(f"Generated {len(windows)} walk-forward windows")
        return windows

    def validate(
        self,
        strategy_fn: callable,
        data: pd.DataFrame,
        start_date: str,
        end_date: str,
        *,
        strategy_params: dict[str, Any] | None = None,
    ) -> AggregateResult:
        """
        Run walk-forward validation.

        Args:
            strategy_fn: Function that takes (train_data, test_data, params) → metrics
            data: Full dataset with 'timestamp' column
            start_date: Start of validation period
            end_date: End of validation period
            strategy_params: Parameters passed to strategy_fn

        Returns:
            AggregateResult with combined statistics.
        """
        windows = self.generate_windows(start_date, end_date)
        result = AggregateResult(total_windows=len(windows))

        consecutive_lossing = 0
        sharpes = []

        for i, (train_start, train_end, test_start, test_end) in enumerate(windows):
            logger.info(
                f"Window {i + 1}/{len(windows)}: "
                f"train=[{train_start[:10]} → {train_end[:10]}] "
                f"test=[{test_start[:10]} → {test_end[:10]}]"
            )

            window = WindowResult(
                window_index=i,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )

            try:
                # Split data
                train_mask = (
                    (data["timestamp"] >= train_start) &
                    (data["timestamp"] < train_end)
                )
                test_mask = (
                    (data["timestamp"] >= test_start) &
                    (data["timestamp"] < test_end)
                )

                train_data = data[train_mask].copy()
                test_data = data[test_mask].copy()

                if len(train_data) < self.config.min_train_samples:
                    window.status = "skipped"
                    window.error = f"Insufficient train samples: {len(train_data)}"
                    result.window_results.append(window)
                    continue

                # Run strategy
                metrics = strategy_fn(
                    train_data,
                    test_data,
                    strategy_params or {},
                )

                window.metrics = metrics
                window.trades_count = metrics.total_trades
                window.status = "completed"
                result.completed_windows += 1

                sharpes.append(metrics.sharpe_ratio)

                # Track consecutive losing windows
                if metrics.sharpe_ratio < 0:
                    consecutive_lossing += 1
                    result.max_consecutive_lossing_windows = max(
                        result.max_consecutive_lossing_windows,
                        consecutive_lossing,
                    )
                else:
                    consecutive_lossing = 0

            except Exception as e:
                window.status = "failed"
                window.error = str(e)
                result.failed_windows += 1
                logger.error(f"Window {i} failed: {e}")

            result.window_results.append(window)

        # Aggregate
        completed = [w for w in result.window_results if w.status == "completed"]
        if completed:
            result.avg_sharpe = sum(w.metrics.sharpe_ratio for w in completed) / len(completed)
            result.avg_sortino = sum(w.metrics.sortino_ratio for w in completed) / len(completed)
            result.avg_calmar = sum(w.metrics.calmar_ratio for w in completed) / len(completed)
            result.avg_max_drawdown = sum(w.metrics.max_drawdown_pct for w in completed) / len(completed)
            result.avg_return = sum(w.metrics.total_return_pct for w in completed) / len(completed)
            result.avg_hit_rate = sum(w.metrics.hit_rate for w in completed) / len(completed)
            result.avg_turnover = sum(w.metrics.turnover for w in completed) / len(completed)
            result.total_trades = sum(w.metrics.total_trades for w in completed)

            if len(sharpes) > 1:
                import statistics
                result.sharpe_std = statistics.stdev(sharpes)

            positive = sum(1 for s in sharpes if s > 0)
            result.pct_positive_windows = positive / len(sharpes)
            result.worst_window_sharpe = min(sharpes)
            result.best_window_sharpe = max(sharpes)

        logger.info(
            f"Walk-forward complete: {result.completed_windows}/{result.total_windows} windows, "
            f"avg Sharpe={result.avg_sharpe:.2f}, "
            f"robust={result.is_robust}"
        )
        return result
