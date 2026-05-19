"""Shadow deployment framework for BAET.

Runs strategies live without capital to compare:
- Expected fills vs actual fills
- Expected latency vs actual latency
- Feature distributions: train vs live
- Prediction confidence: expected vs actual
- Drift detection over time

This is the final validation step before capital deployment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ShadowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    PROMOTED = "promoted"  # Moved to capital deployment
    REJECTED = "rejected"  # Failed shadow, sent back to research


@dataclass
class ShadowMetrics:
    """Metrics collected during shadow deployment."""

    n_predictions: int = 0
    n_signals: int = 0
    n_orders: int = 0
    n_fills: int = 0

    # Fill quality
    avg_slippage_bps: float = 0.0
    max_slippage_bps: float = 0.0
    fill_rate: float = 0.0
    avg_fill_ratio: float = 0.0

    # Latency
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    # Prediction quality
    prediction_accuracy: float = 0.0
    avg_confidence: float = 0.0
    confidence_calibration_error: float = 0.0

    # Drift
    feature_drift_score: float = 0.0
    prediction_drift_score: float = 0.0

    # Performance (paper)
    paper_sharpe: float = 0.0
    paper_max_drawdown_pct: float = 0.0
    paper_total_return_pct: float = 0.0


@dataclass
class ShadowDeployment:
    """A shadow deployment of a strategy."""

    deployment_id: str = ""
    experiment_id: str = ""
    strategy_name: str = ""
    status: ShadowStatus = ShadowStatus.PENDING
    metrics: ShadowMetrics = field(default_factory=ShadowMetrics)

    # Thresholds for promotion
    min_fill_rate: float = 0.95
    max_slippage_bps: float = 10.0
    max_latency_ms: float = 500.0
    min_prediction_accuracy: float = 0.5
    max_drift_score: float = 0.3
    min_paper_sharpe: float = 0.5
    min_shadow_bars: int = 1000

    # History
    start_time: str = ""
    end_time: str = ""
    n_bars: int = 0
    daily_metrics: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_ready_for_promotion(self) -> bool:
        """Check if shadow deployment passes all criteria."""
        m = self.metrics
        return (
            self.n_bars >= self.min_shadow_bars
            and m.fill_rate >= self.min_fill_rate
            and m.avg_slippage_bps <= self.max_slippage_bps
            and m.p99_latency_ms <= self.max_latency_ms
            and m.prediction_accuracy >= self.min_prediction_accuracy
            and m.feature_drift_score <= self.max_drift_score
            and m.paper_sharpe >= self.min_paper_sharpe
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "experiment_id": self.experiment_id,
            "strategy_name": self.strategy_name,
            "status": self.status.value,
            "metrics": self.metrics.__dict__,
            "n_bars": self.n_bars,
            "is_ready_for_promotion": self.is_ready_for_promotion,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


class ShadowDeploymentManager:
    """
    Manages shadow deployments.

    Each shadow deployment runs a strategy live (without capital)
    and compares expected vs actual behavior.
    """

    def __init__(self) -> None:
        self._deployments: dict[str, ShadowDeployment] = {}

    def create_deployment(
        self,
        experiment_id: str,
        strategy_name: str,
        min_fill_rate: float = 0.95,
        max_slippage_bps: float = 10.0,
        min_shadow_bars: int = 1000,
    ) -> ShadowDeployment:
        """Create a new shadow deployment."""
        import uuid

        dep = ShadowDeployment(
            deployment_id=str(uuid.uuid4())[:12],
            experiment_id=experiment_id,
            strategy_name=strategy_name,
            status=ShadowStatus.PENDING,
            min_fill_rate=min_fill_rate,
            max_slippage_bps=max_slippage_bps,
            min_shadow_bars=min_shadow_bars,
        )
        self._deployments[dep.deployment_id] = dep
        logger.info(f"Shadow deployment created: {dep.deployment_id} ({strategy_name})")
        return dep

    def start(self, deployment_id: str) -> None:
        """Start a shadow deployment."""
        dep = self._get(deployment_id)
        dep.status = ShadowStatus.RUNNING
        dep.start_time = datetime.now(UTC).isoformat()
        logger.info(f"Shadow deployment started: {deployment_id}")

    def record_bar(
        self,
        deployment_id: str,
        prediction: float,
        confidence: float,
        actual_return: float,
        expected_fill_price: float,
        actual_fill_price: float,
        latency_ms: float,
        features: dict[str, float],
    ) -> None:
        """Record a single bar of shadow deployment data."""
        dep = self._get(deployment_id)
        m = dep.metrics
        dep.n_bars += 1

        m.n_predictions += 1

        # Signal generated
        if abs(prediction) > 0.1:
            m.n_signals += 1

        # Fill analysis
        if actual_fill_price > 0:
            m.n_fills += 1
            slippage = abs(actual_fill_price - expected_fill_price) / expected_fill_price * 10000
            m.avg_slippage_bps = (m.avg_slippage_bps * (m.n_fills - 1) + slippage) / m.n_fills
            m.max_slippage_bps = max(m.max_slippage_bps, slippage)

        # Fill rate
        if m.n_signals > 0:
            m.fill_rate = m.n_fills / m.n_signals

        # Latency
        m.avg_latency_ms = (m.avg_latency_ms * (dep.n_bars - 1) + latency_ms) / dep.n_bars

        # Prediction accuracy
        correct = (prediction * actual_return) > 0
        m.prediction_accuracy = (
            m.prediction_accuracy * (m.n_predictions - 1) + int(correct)
        ) / m.n_predictions

        # Confidence calibration
        m.avg_confidence = (m.avg_confidence * (m.n_predictions - 1) + confidence) / m.n_predictions
        calibration_error = abs(confidence - int(correct))
        m.confidence_calibration_error = (
            m.confidence_calibration_error * (m.n_predictions - 1) + calibration_error
        ) / m.n_predictions

    def evaluate(self, deployment_id: str) -> dict[str, Any]:
        """Evaluate shadow deployment against promotion criteria."""
        dep = self._get(deployment_id)
        m = dep.metrics

        checks = {
            "min_bars": dep.n_bars >= dep.min_shadow_bars,
            "fill_rate": m.fill_rate >= dep.min_fill_rate,
            "slippage": m.avg_slippage_bps <= dep.max_slippage_bps,
            "latency": m.p99_latency_ms <= dep.max_latency_ms,
            "accuracy": m.prediction_accuracy >= dep.min_prediction_accuracy,
            "drift": m.feature_drift_score <= dep.max_drift_score,
            "paper_sharpe": m.paper_sharpe >= dep.min_paper_sharpe,
        }

        all_passed = all(checks.values())

        if all_passed:
            dep.status = ShadowStatus.PASSED
            logger.info(f"Shadow deployment PASSED: {deployment_id}")
        elif dep.n_bars >= dep.min_shadow_bars * 2:
            # Failed after sufficient data
            dep.status = ShadowStatus.FAILED
            logger.warning(f"Shadow deployment FAILED: {deployment_id}")

        return {
            "deployment_id": deployment_id,
            "status": dep.status.value,
            "n_bars": dep.n_bars,
            "checks": checks,
            "all_passed": all_passed,
            "metrics": m.__dict__,
        }

    def promote(self, deployment_id: str) -> None:
        """Promote a passed shadow deployment to capital."""
        dep = self._get(deployment_id)
        if dep.status != ShadowStatus.PASSED:
            raise ValueError(
                f"Deployment {deployment_id} has not passed shadow. " f"Status: {dep.status.value}"
            )
        dep.status = ShadowStatus.PROMOTED
        dep.end_time = datetime.now(UTC).isoformat()
        logger.info(f"Shadow deployment PROMOTED to capital: {deployment_id}")

    def reject(self, deployment_id: str, reason: str = "") -> None:
        """Reject a failed shadow deployment."""
        dep = self._get(deployment_id)
        dep.status = ShadowStatus.REJECTED
        dep.end_time = datetime.now(UTC).isoformat()
        logger.info(f"Shadow deployment REJECTED: {deployment_id} ({reason})")

    def get_deployment(self, deployment_id: str) -> ShadowDeployment | None:
        return self._deployments.get(deployment_id)

    def list_deployments(
        self,
        status: ShadowStatus | None = None,
    ) -> list[ShadowDeployment]:
        """List deployments, optionally filtered by status."""
        deps = list(self._deployments.values())
        if status:
            deps = [d for d in deps if d.status == status]
        return deps

    def _get(self, deployment_id: str) -> ShadowDeployment:
        dep = self._deployments.get(deployment_id)
        if dep is None:
            raise ValueError(f"Deployment not found: {deployment_id}")
        return dep
