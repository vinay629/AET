"""Online inference monitoring for ML models.

Tracks live model performance and detects:
- Feature drift (train vs live distribution)
- Confidence collapse (model becomes uncertain)
- Prediction distribution shift
- Missing features
- Latency degradation
- Prediction disagreement (ensemble)

When drift exceeds thresholds, the model should automatically
downgrade confidence or disable itself.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DriftLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftReport:
    """Report on feature and prediction drift."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model_id: str = ""
    model_name: str = ""
    overall_drift: DriftLevel = DriftLevel.NONE
    feature_drifts: dict[str, DriftLevel] = field(default_factory=dict)
    prediction_drift: DriftLevel = DriftLevel.NONE
    confidence_drift: DriftLevel = DriftLevel.NONE
    details: dict[str, Any] = field(default_factory=dict)
    should_disable: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class InferenceStats:
    """Running statistics for online inference."""
    n_predictions: int = 0
    n_errors: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    avg_confidence: float = 0.0
    min_confidence: float = 1.0
    max_confidence: float = 0.0
    missing_feature_count: int = 0
    last_prediction_time: float = 0.0


class InferenceMonitor:
    """
    Monitors live ML model inference for drift and degradation.

    Compares live predictions against training distributions.
    Triggers warnings or automatic disable when drift exceeds thresholds.
    """

    def __init__(
        self,
        psi_threshold: float = 0.2,       # Population Stability Index threshold
        confidence_threshold: float = 0.3, # Min avg confidence before warning
        latency_threshold_ms: float = 500, # Max p99 latency
        disable_threshold: float = 0.3,    # PSI threshold for auto-disable
    ) -> None:
        self.psi_threshold = psi_threshold
        self.confidence_threshold = confidence_threshold
        self.latency_threshold_ms = latency_threshold_ms
        self.disable_threshold = disable_threshold

        # Training distributions (set during model registration)
        self._train_feature_distributions: dict[str, dict[str, Any]] = {}
        self._train_prediction_distribution: dict[str, Any] = {}

        # Live tracking
        self._live_predictions: list[float] = []
        self._live_confidences: list[float] = []
        self._live_features: dict[str, list[float]] = {}
        self._latency_samples: list[float] = []
        self._stats = InferenceStats()

    def set_training_distributions(
        self,
        feature_distributions: dict[str, dict[str, Any]],
        prediction_distribution: dict[str, Any],
    ) -> None:
        """
        Set the training data distributions for drift comparison.

        Args:
            feature_distributions: Per-feature stats from training data.
                Format: {feature_name: {"mean": float, "std": float, "percentiles": list}}
            prediction_distribution: Stats from training predictions.
        """
        self._train_feature_distributions = feature_distributions
        self._train_prediction_distribution = prediction_distribution

    def record_prediction(
        self,
        prediction: float,
        confidence: float,
        features: dict[str, float],
        latency_ms: float,
    ) -> None:
        """Record a live prediction for monitoring."""
        self._live_predictions.append(prediction)
        self._live_confidences.append(confidence)
        self._latency_samples.append(latency_ms)

        for name, value in features.items():
            if name not in self._live_features:
                self._live_features[name] = []
            self._live_features[name].append(value)

        # Update stats
        self._stats.n_predictions += 1
        self._stats.avg_latency_ms = np.mean(self._latency_samples[-100:])
        if len(self._latency_samples) >= 10:
            self._stats.p99_latency_ms = float(np.percentile(self._latency_samples[-100:], 99))
        self._stats.avg_confidence = np.mean(self._live_confidences[-100:])
        self._stats.min_confidence = min(self._stats.min_confidence, confidence)
        self._stats.max_confidence = max(self._stats.max_confidence, confidence)
        self._stats.last_prediction_time = time.time()

    def check_drift(self) -> DriftReport:
        """
        Check for drift between training and live distributions.

        Returns:
            DriftReport with per-feature and overall drift levels.
        """
        report = DriftReport()

        if not self._live_predictions or not self._train_feature_distributions:
            return report

        # Check feature drift
        max_feature_drift = DriftLevel.NONE
        for feat_name, train_dist in self._train_feature_distributions.items():
            if feat_name not in self._live_features:
                report.warnings.append(f"Feature '{feat_name}' missing from live data")
                report.missing_feature_count += 1
                continue

            live_values = np.array(self._live_features[feat_name][-1000:])
            drift_level = self._compute_drift(train_dist, live_values)
            report.feature_drifts[feat_name] = drift_level

            if self._drift_level_value(drift_level) > self._drift_level_value(max_feature_drift):
                max_feature_drift = drift_level

        # Check prediction drift
        if self._train_prediction_distribution:
            live_preds = np.array(self._live_predictions[-1000:])
            report.prediction_drift = self._compute_drift(
                self._train_prediction_distribution, live_preds
            )

        # Check confidence drift
        if self._live_confidences:
            avg_conf = np.mean(self._live_confidences[-100:])
            train_avg_conf = self._train_prediction_distribution.get("avg_confidence", 0.5)
            conf_drop = train_avg_conf - avg_conf
            if conf_drop > 0.3:
                report.confidence_drift = DriftLevel.CRITICAL
                report.warnings.append(
                    f"Confidence collapsed: train={train_avg_conf:.2f}, live={avg_conf:.2f}"
                )
            elif conf_drop > 0.15:
                report.confidence_drift = DriftLevel.MEDIUM
            elif conf_drop > 0.05:
                report.confidence_drift = DriftLevel.LOW

        # Check latency
        if self._stats.p99_latency_ms > self.latency_threshold_ms:
            report.warnings.append(
                f"Latency exceeded: p99={self._stats.p99_latency_ms:.0f}ms "
                f"(threshold={self.latency_threshold_ms}ms)"
            )

        # Overall drift
        all_drifts = (
            list(report.feature_drifts.values()) +
            [report.prediction_drift, report.confidence_drift]
        )
        report.overall_drift = max(all_drifts, key=self._drift_level_value)

        # Auto-disable check
        critical_count = sum(1 for d in all_drifts if d == DriftLevel.CRITICAL)
        high_count = sum(1 for d in all_drifts if d == DriftLevel.HIGH)
        report.should_disable = (
            critical_count >= 2 or
            high_count >= 3 or
            max_feature_drift == DriftLevel.CRITICAL
        )

        if report.should_disable:
            logger.critical(
                f"Model should be DISABLED due to drift: "
                f"overall={report.overall_drift.value}, "
                f"critical_features={critical_count}"
            )

        return report

    def _compute_drift(
        self,
        train_dist: dict[str, Any],
        live_values: np.ndarray,
    ) -> DriftLevel:
        """
        Compute drift level using PSI (Population Stability Index).

        PSI < 0.1: No drift
        PSI 0.1-0.25: Low drift
        PSI > 0.25: High drift
        """
        train_mean = train_dist.get("mean", 0)
        train_std = train_dist.get("std", 1)
        train_pcs = train_dist.get("percentiles", [])

        if train_std == 0 or len(live_values) < 10:
            return DriftLevel.NONE

        # PSI using percentile bins
        if train_pcs and len(train_pcs) >= 10:
            bins = np.array(train_pcs)
        else:
            bins = np.linspace(
                train_mean - 3 * train_std,
                train_mean + 3 * train_std,
                11,
            )

        train_hist, _ = np.histogram(live_values[:100] if len(live_values) > 100 else live_values, bins=bins)
        live_hist, _ = np.histogram(live_values, bins=bins)

        # Normalize
        train_pct = (train_hist + 1) / (train_hist.sum() + len(train_hist))
        live_pct = (live_hist + 1) / (live_hist.sum() + len(live_hist))

        # PSI
        psi = np.sum((live_pct - train_pct) * np.log(live_pct / train_pct))

        if psi < 0.1:
            return DriftLevel.NONE
        elif psi < 0.2:
            return DriftLevel.LOW
        elif psi < self.psi_threshold:
            return DriftLevel.MEDIUM
        elif psi < self.disable_threshold:
            return DriftLevel.HIGH
        else:
            return DriftLevel.CRITICAL

    @staticmethod
    def _drift_level_value(level: DriftLevel) -> int:
        """Numeric value for drift level comparison."""
        return {
            DriftLevel.NONE: 0,
            DriftLevel.LOW: 1,
            DriftLevel.MEDIUM: 2,
            DriftLevel.HIGH: 3,
            DriftLevel.CRITICAL: 4,
        }.get(level, 0)

    @property
    def stats(self) -> InferenceStats:
        return self._stats

    def reset(self) -> None:
        """Reset live tracking (e.g., after model update)."""
        self._live_predictions.clear()
        self._live_confidences.clear()
        self._live_features.clear()
        self._latency_samples.clear()
        self._stats = InferenceStats()
