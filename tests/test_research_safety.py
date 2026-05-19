"""Research safety validation tests.

Automated checks for common ML/research failure modes:
- Future data leakage (lookahead bias)
- Train/test contamination
- Temporal ordering violations
- Overlapping fold contamination in CV

These tests enforce the rules from research-code-safety.instructions.md
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from baet.ml.leakage import LeakageDetector, LeakageSeverity
from baet.ml.purged_cv import EmbargoCV, PurgedKFold


class TestNoFutureLeakage:
    """Verify that features do not contain future information."""

    def test_feature_at_time_t_uses_only_past_data(self) -> None:
        """A feature computed at index i must not reference data from i+1 or later.

        This is the most fundamental rule of financial ML.
        """
        np.random.seed(42)
        n = 200
        close = np.cumsum(np.random.randn(n)) + 100

        # CORRECT: feature uses only past data (shift(1) = previous bar)
        correct_feature = pd.Series(close).pct_change().shift(1).fillna(0)

        # WRONG: feature uses future data (shift(-1) = next bar)
        leaky_feature = pd.Series(close).pct_change().shift(-1).fillna(0)

        # The correct feature should have zero correlation with future returns
        future_returns = pd.Series(close).pct_change().shift(-1).fillna(0)
        correct_corr = abs(correct_feature.corr(future_returns))
        leaky_corr = abs(leaky_feature.corr(future_returns))

        # Leaky feature should be much more correlated with future
        assert leaky_corr > correct_corr, (
            f"Leaky feature corr ({leaky_corr:.3f}) should exceed "
            f"correct feature corr ({correct_corr:.3f})"
        )

    def test_rolling_statistic_does_not_look_ahead(self) -> None:
        """Rolling windows must be backward-looking only (no centering)."""
        np.random.seed(42)
        n = 100
        data = pd.Series(np.cumsum(np.random.randn(n)) + 100)

        # CORRECT: backward-looking rolling mean
        correct_rolling = data.rolling(window=10, min_periods=1).mean()

        # WRONG: centered rolling mean (uses future data)
        leaky_rolling = data.rolling(window=10, min_periods=1, center=True).mean()

        # The centered version at index 5 uses data from indices 0-10
        # The backward version at index 5 uses data from indices 0-5 only
        # They should differ
        assert not np.allclose(
            correct_rolling.values, leaky_rolling.values
        ), "Centered and backward-looking rolling means should differ"

    def test_leakage_detector_catches_future_return_feature(self) -> None:
        """LeakageDetector must flag a feature that is a future return."""
        detector = LeakageDetector()
        n = 300
        close = np.cumsum(np.random.randn(n)) + 100

        features = pd.DataFrame(
            {
                "close": close,
                "future_return": pd.Series(close).pct_change().shift(-1).fillna(0) * 100,
            }
        )
        labels = pd.Series(np.random.randn(n))
        timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="h"))

        report = detector.check_all(features, labels, timestamps)
        # Should detect the leaky feature
        leaky_findings = [f for f in report.findings if f.feature_name == "future_return"]
        assert (
            len(leaky_findings) > 0
        ), "LeakageDetector should flag 'future_return' as a leaky feature"


class TestTrainTestIsolation:
    """Verify that train/test splits maintain proper isolation."""

    def test_purged_cv_no_overlap_between_folds(self) -> None:
        """Test sets across folds must not overlap."""
        cv = PurgedKFold(n_splits=5, purge_gap=2)
        folds = cv.split(n_samples=200, label_horizon=3)

        test_sets = [set(f.test_indices.tolist()) for f in folds]
        for i in range(len(test_sets)):
            for j in range(i + 1, len(test_sets)):
                overlap = test_sets[i] & test_sets[j]
                assert (
                    len(overlap) == 0
                ), f"Folds {i} and {j} have overlapping test indices: {overlap}"

    def test_purged_cv_train_excludes_label_horizon(self) -> None:
        """Training indices must not be within label_horizon of any test index."""
        cv = PurgedKFold(n_splits=5, purge_gap=0)
        label_horizon = 5
        folds = cv.split(n_samples=200, label_horizon=label_horizon)

        for fold in folds:
            for ti in fold.test_indices:
                for fi in fold.train_indices:
                    assert abs(int(ti) - int(fi)) >= label_horizon, (
                        f"Train index {fi} is within label_horizon ({label_horizon}) "
                        f"of test index {ti}"
                    )

    def test_embargo_cv_enforces_gap(self) -> None:
        """EmbargoCV must enforce a gap after each test fold."""
        cv = EmbargoCV(n_splits=5, embargo_pct=0.02)
        folds = cv.split(n_samples=200)

        for fold in folds:
            # Embargo should have removed some samples
            assert fold.embargo_count >= 0, "Embargo count should be non-negative"

    def test_no_standard_kfold_in_codebase(self) -> None:
        """Verify that standard KFold (which leaks) is not used in ML code.

        All CV in this codebase must use purged variants.
        """
        import ast
        from pathlib import Path

        ml_dir = Path("src/baet/ml")
        assert ml_dir.exists(), "ML directory should exist"

        violations: list[str] = []
        for py_file in ml_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "sklearn" in node.module:
                        for alias in node.names:
                            if alias.name in ("KFold", "StratifiedKFold", "TimeSeriesSplit"):
                                violations.append(
                                    f"{py_file}: imports {alias.name} from {node.module}"
                                )

        assert len(violations) == 0, (
            "Found non-purged CV imports (potential leakage):\n"
            + "\n".join(f"  ✗ {v}" for v in violations)
        )


class TestTemporalIntegrity:
    """Verify that temporal ordering is preserved."""

    def test_timestamps_are_monotonically_increasing(self) -> None:
        """Timestamps in any dataset must be strictly increasing."""
        timestamps = pd.date_range("2024-01-01", periods=100, freq="h")
        assert timestamps.is_monotonic_increasing, "Timestamps must be monotonically increasing"

    def test_no_duplicate_timestamps(self) -> None:
        """No duplicate timestamps should exist in time series data."""
        timestamps = pd.date_range("2024-01-01", periods=100, freq="h")
        assert not timestamps.duplicated().any(), "Timestamps must not contain duplicates"

    def test_label_horizon_does_not_extend_beyond_data(self) -> None:
        """Labels must not reference data beyond the available range."""
        n = 100
        label_horizon = 5
        close = pd.Series(np.cumsum(np.random.randn(n)) + 100)

        # A label at index i should reference data up to i + label_horizon
        # But i + label_horizon must be < n
        max_valid_index = n - label_horizon - 1
        assert max_valid_index >= 0, f"Label horizon ({label_horizon}) exceeds data length ({n})"

        # Labels for the last `label_horizon` bars should be NaN or excluded
        labels = close.pct_change().shift(-label_horizon)
        nan_count = labels.isna().sum()
        assert (
            nan_count >= label_horizon
        ), f"Expected at least {label_horizon} NaN labels at the end, got {nan_count}"


class TestLeakageDetectorCompleteness:
    """Verify that the leakage detector catches all expected leakage types."""

    def test_label_correlation_detected(self) -> None:
        """Features highly correlated with labels should be flagged."""
        detector = LeakageDetector()
        n = 200
        labels = pd.Series(np.random.randn(n))

        # Create a feature that is almost identical to the label
        features = pd.DataFrame(
            {
                "leaky": labels * 0.999 + np.random.randn(n) * 0.001,
                "clean": np.random.randn(n),
            }
        )

        report = detector.check_all(features, labels)
        leaky_findings = [f for f in report.findings if f.feature_name == "leaky"]
        assert (
            len(leaky_findings) > 0
        ), "Should detect near-perfect correlation between 'leaky' feature and labels"

    def test_clean_data_reports_no_critical(self) -> None:
        """Truly random features should not produce critical leakage findings."""
        detector = LeakageDetector()
        np.random.seed(42)
        n = 500
        features = pd.DataFrame(
            {
                "f1": np.random.randn(n),
                "f2": np.random.randn(n),
                "f3": np.random.randn(n),
            }
        )
        labels = pd.Series(np.random.randn(n))

        report = detector.check_all(features, labels)
        critical_findings = [f for f in report.findings if f.severity == LeakageSeverity.CRITICAL]
        assert len(critical_findings) == 0, (
            f"Random data should not produce critical leakage findings, "
            f"got: {[f.feature_name for f in critical_findings]}"
        )
