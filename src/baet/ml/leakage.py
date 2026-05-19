"""Leakage detection engine for BAET.

Detects three types of leakage that invalidate research:

1. Time Leakage: feature at time t uses data from t+1 or later
2. Cross-Section Leakage: future universe membership, survivorship bias
3. Label Leakage: label overlaps with features, horizon contamination

All checks are deterministic and produce auditable reports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LeakageType(StrEnum):
    TIME = "time"
    CROSS_SECTION = "cross_section"
    LABEL = "label"


class LeakageSeverity(StrEnum):
    CRITICAL = "critical"   # Definitely invalidates results
    WARNING = "warning"     # Suspicious, needs investigation
    INFO = "info"           # Informational


@dataclass
class LeakageFinding:
    """A single detected leakage issue."""
    leakage_type: LeakageType
    severity: LeakageSeverity
    feature_name: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LeakageReport:
    """Full leakage detection report."""
    findings: list[LeakageFinding] = field(default_factory=list)
    passed: bool = True
    n_features_checked: int = 0
    n_critical: int = 0
    n_warnings: int = 0

    def add(self, finding: LeakageFinding) -> None:
        self.findings.append(finding)
        if finding.severity == LeakageSeverity.CRITICAL:
            self.n_critical += 1
            self.passed = False
        elif finding.severity == LeakageSeverity.WARNING:
            self.n_warnings += 1

    def summary(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "n_features_checked": self.n_features_checked,
            "n_critical": self.n_critical,
            "n_warnings": self.n_warnings,
            "findings": [
                {
                    "type": f.leakage_type.value,
                    "severity": f.severity.value,
                    "feature": f.feature_name,
                    "message": f.message,
                }
                for f in self.findings
            ],
        }


class LeakageDetector:
    """
    Detects data leakage in feature matrices and labels.

    All methods are pure functions — same inputs → same outputs.
    """

    def check_all(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        timestamps: pd.Series | None = None,
        symbols: pd.Series | None = None,
    ) -> LeakageReport:
        """
        Run all leakage checks.

        Args:
            features: Feature matrix (rows = samples, cols = features).
            labels: Target variable (aligned with features).
            timestamps: Optional timestamp per sample.
            symbols: Optional symbol per sample (for cross-section checks).

        Returns:
            LeakageReport with all findings.
        """
        report = LeakageReport(n_features_checked=len(features.columns))

        # Time leakage checks
        if timestamps is not None:
            self._check_future_candle_access(features, timestamps, report)
            self._check_centered_windows(features, timestamps, report)

        # Label leakage checks
        self._check_label_overlap(features, labels, report)
        self._check_label_correlation(features, labels, report)

        # Cross-section leakage checks
        if symbols is not None:
            self._check_universe_membership(features, symbols, report)

        # Feature drift checks
        self._check_feature_stationarity(features, report)

        if report.passed:
            logger.info("Leakage detection passed — no critical issues found")
        else:
            logger.warning(
                f"Leakage detection FAILED: {report.n_critical} critical, "
                f"{report.n_warnings} warnings"
            )

        return report

    def _check_future_candle_access(
        self,
        features: pd.DataFrame,
        timestamps: pd.Series,
        report: LeakageReport,
    ) -> None:
        """
        Check if any feature has higher correlation with future prices
        than current prices (suggests future leakage).

        For each feature, compare correlation with current close vs next close.
        """
        if "close" not in features.columns:
            return

        close = features["close"]
        future_return = close.pct_change().shift(-1)

        for col in features.columns:
            if col == "close":
                continue

            feat = features[col].dropna()
            if len(feat) < 20:
                continue

            # Align
            aligned = pd.concat([feat, future_return], axis=1).dropna()
            if len(aligned) < 20:
                continue

            corr_current = abs(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))

            # Compare with correlation to past returns
            past_return = close.pct_change()
            aligned_past = pd.concat([feat, past_return], axis=1).dropna()
            if len(aligned_past) < 20:
                continue
            corr_past = abs(aligned_past.iloc[:, 0].corr(aligned_past.iloc[:, 1]))

            # If future correlation is much higher, likely leakage
            if corr_current > 0.3 and corr_current > corr_past * 1.5:
                report.add(LeakageFinding(
                    leakage_type=LeakageType.TIME,
                    severity=LeakageSeverity.CRITICAL,
                    feature_name=col,
                    message=(
                        f"Feature '{col}' has higher correlation with future returns "
                        f"({corr_current:.3f}) than past returns ({corr_past:.3f}). "
                        f"Possible future leakage."
                    ),
                    details={
                        "corr_future": float(corr_current),
                        "corr_past": float(corr_past),
                    },
                ))

    def _check_centered_windows(
        self,
        features: pd.DataFrame,
        timestamps: pd.Series,
        report: LeakageReport,
    ) -> None:
        """
        Check for centered rolling windows (which use future data).

        A centered window at time t uses data from [t-k, t+k].
        This is a common source of leakage.

        Detection: check if feature leads price by more than 1 bar.
        """
        if "close" not in features.columns:
            return

        close = features["close"]

        for col in features.columns:
            if col in ("close", "open", "high", "low", "volume"):
                continue

            feat = features[col].dropna()
            if len(feat) < 50:
                continue

            # Check cross-correlation at different lags
            max_lead = 5
            best_lag = 0
            best_corr = 0

            for lag in range(-max_lead, max_lead + 1):
                if lag == 0:
                    corr = abs(feat.corr(close))
                elif lag > 0:
                    # Feature leads price (suspicious)
                    corr = abs(feat.iloc[:-lag].corr(close.iloc[lag:])) if lag < len(feat) else 0
                else:
                    # Feature lags price (normal)
                    corr = abs(feat.iloc[-lag:].corr(close.iloc[:lag])) if -lag < len(feat) else 0

                if corr > best_corr:
                    best_corr = corr
                    best_lag = lag

            # If best correlation is at positive lag, feature leads price
            if best_lag >= 2 and best_corr > 0.3:
                report.add(LeakageFinding(
                    leakage_type=LeakageType.TIME,
                    severity=LeakageSeverity.WARNING,
                    feature_name=col,
                    message=(
                        f"Feature '{col}' leads price by {best_lag} bars "
                        f"(corr={best_corr:.3f}). Possible centered window."
                    ),
                    details={"best_lag": best_lag, "best_corr": float(best_corr)},
                ))

    def _check_label_overlap(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        report: LeakageReport,
    ) -> None:
        """
        Check if labels overlap with features (label leakage).

        If a feature is perfectly correlated with the label,
        it likely contains the label itself.
        """
        for col in features.columns:
            feat = features[col].dropna()
            aligned = pd.concat([feat, labels], axis=1).dropna()

            if len(aligned) < 20:
                continue

            corr = abs(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))

            if corr > 0.95:
                report.add(LeakageFinding(
                    leakage_type=LeakageType.LABEL,
                    severity=LeakageSeverity.CRITICAL,
                    feature_name=col,
                    message=(
                        f"Feature '{col}' has {corr:.3f} correlation with label. "
                        f"Likely contains label information."
                    ),
                    details={"correlation": float(corr)},
                ))
            elif corr > 0.8:
                report.add(LeakageFinding(
                    leakage_type=LeakageType.LABEL,
                    severity=LeakageSeverity.WARNING,
                    feature_name=col,
                    message=(
                        f"Feature '{col}' has {corr:.3f} correlation with label. "
                        f"Possible label contamination."
                    ),
                    details={"correlation": float(corr)},
                ))

    def _check_label_correlation(
        self,
        features: pd.DataFrame,
        labels: pd.Series,
        report: LeakageReport,
    ) -> None:
        """
        Check if feature distribution differs significantly between
        positive and negative label groups (suggests label leakage).
        """
        if not pd.api.types.is_numeric_dtype(labels):
            return

        pos_mask = labels > 0
        neg_mask = labels <= 0

        if pos_mask.sum() < 10 or neg_mask.sum() < 10:
            return

        for col in features.columns:
            feat = features[col]
            pos_mean = feat[pos_mask].mean()
            neg_mean = feat[neg_mask].mean()
            overall_std = feat.std()

            if overall_std == 0:
                continue

            # Standardized mean difference
            smd = abs(pos_mean - neg_mean) / overall_std

            if smd > 1.0:
                report.add(LeakageFinding(
                    leakage_type=LeakageType.LABEL,
                    severity=LeakageSeverity.WARNING,
                    feature_name=col,
                    message=(
                        f"Feature '{col}' has large mean difference between "
                        f"positive/negative labels (SMD={smd:.2f}). "
                        f"Possible label leakage."
                    ),
                    details={"smd": float(smd), "pos_mean": float(pos_mean), "neg_mean": float(neg_mean)},
                ))

    def _check_universe_membership(
        self,
        features: pd.DataFrame,
        symbols: pd.Series,
        report: LeakageReport,
    ) -> None:
        """
        Check for survivorship bias in multi-asset features.

        If a feature only exists for currently-active symbols,
        it may contain survivorship bias.
        """
        # Check if any symbol has missing feature values
        for col in features.columns:
            missing_by_symbol = features.groupby(symbols)[col].apply(lambda x: x.isna().mean())
            if missing_by_symbol.max() > 0.5:
                report.add(LeakageFinding(
                    leakage_type=LeakageType.CROSS_SECTION,
                    severity=LeakageSeverity.INFO,
                    feature_name=col,
                    message=(
                        f"Feature '{col}' has >50% missing values for some symbols. "
                        f"Check for survivorship bias."
                    ),
                ))

    def _check_feature_stationarity(
        self,
        features: pd.DataFrame,
        report: LeakageReport,
    ) -> None:
        """
        Check if features are approximately stationary.

        Non-stationary features can cause spurious correlations.
        Uses a simple ADF-like check (rolling mean stability).
        """
        for col in features.columns:
            feat = features[col].dropna()
            if len(feat) < 100:
                continue

            # Split into halves and compare means
            mid = len(feat) // 2
            first_half = feat.iloc[:mid]
            second_half = feat.iloc[mid:]

            overall_std = feat.std()
            if overall_std == 0:
                continue

            mean_diff = abs(first_half.mean() - second_half.mean()) / overall_std

            if mean_diff > 1.0:
                report.add(LeakageFinding(
                    leakage_type=LeakageType.TIME,
                    severity=LeakageSeverity.INFO,
                    feature_name=col,
                    message=(
                        f"Feature '{col}' shows significant mean shift "
                        f"between first/second half (diff={mean_diff:.2f} std). "
                        f"May be non-stationary."
                    ),
                    details={"mean_diff_std": float(mean_diff)},
                ))
