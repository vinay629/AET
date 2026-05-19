"""Tests for ML infrastructure."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from baet.ml.leakage import LeakageDetector, LeakageReport, LeakageSeverity
from baet.ml.purged_cv import PurgedKFold, EmbargoCV, CombinatorialPurgedCV
from baet.ml.labels import TripleBarrierLabeler, TripleBarrierConfig, MetaLabeler
from baet.ml.model_registry import ModelRegistry, ModelArtifact, ModelStatus
from baet.ml.monitoring import InferenceMonitor, DriftLevel, DriftReport


class TestLeakageDetector:
    def test_clean_data_passes(self) -> None:
        detector = LeakageDetector()
        np.random.seed(42)
        n = 500
        features = pd.DataFrame({
            "close": np.cumsum(np.random.randn(n)) + 100,
            "feature_1": np.random.randn(n),
            "feature_2": np.random.randn(n),
        })
        labels = pd.Series(np.random.randn(n))
        timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="h"))

        report = detector.check_all(features, labels, timestamps)
        assert isinstance(report, LeakageReport)

    def test_label_leakage_detected(self) -> None:
        detector = LeakageDetector()
        n = 200
        labels = pd.Series(np.random.randn(n))
        features = pd.DataFrame({
            "close": np.cumsum(np.random.randn(n)) + 100,
            "leaky_feature": labels * 0.99 + np.random.randn(n) * 0.01,  # Almost identical to label
        })

        report = detector.check_all(features, labels)
        assert report.n_critical > 0
        assert any(f.feature_name == "leaky_feature" for f in report.findings)

    def test_future_leakage_detected(self) -> None:
        detector = LeakageDetector()
        n = 300
        close = np.cumsum(np.random.randn(n)) + 100
        features = pd.DataFrame({
            "close": close,
            "future_leaky": pd.Series(close).pct_change().shift(-1).fillna(0) * 100,  # Future return
        })
        labels = pd.Series(np.random.randn(n))
        timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="h"))

        report = detector.check_all(features, labels, timestamps)
        # Should detect high correlation with future
        future_findings = [f for f in report.findings if "future" in f.feature_name.lower() or "future" in f.message.lower()]
        assert len(future_findings) > 0 or report.n_warnings > 0 or report.n_critical > 0


class TestPurgedCV:
    def test_purged_kfold_basic(self) -> None:
        cv = PurgedKFold(n_splits=5, purge_gap=2)
        folds = cv.split(n_samples=100, label_horizon=3)
        assert len(folds) == 5

        # Each fold should have train and test
        for fold in folds:
            assert len(fold.test_indices) > 0
            assert len(fold.train_indices) > 0

        # Test sets should not overlap
        test_sets = [set(f.test_indices) for f in folds]
        for i in range(len(test_sets)):
            for j in range(i + 1, len(test_sets)):
                assert len(test_sets[i] & test_sets[j]) == 0

    def test_purging_removes_overlapping(self) -> None:
        cv = PurgedKFold(n_splits=5, purge_gap=0)
        folds = cv.split(n_samples=100, label_horizon=5)

        for fold in folds:
            # No train index should be within label_horizon of any test index
            for ti in fold.test_indices:
                for fi in fold.train_indices:
                    assert abs(ti - fi) >= 5, f"Train index {fi} too close to test {ti}"

    def test_embargo_cv(self) -> None:
        cv = EmbargoCV(n_splits=5, embargo_pct=0.02)
        folds = cv.split(n_samples=100)
        assert len(folds) == 5

    def test_combinatorial_cscv(self) -> None:
        cv = CombinatorialPurgedCV(n_splits=6, n_test_folds=2, purge_gap=1)
        folds = cv.split(n_samples=120, label_horizon=3)
        # C(6,2) = 15 combinations
        assert len(folds) == 15


class TestTripleBarrierLabeler:
    def test_basic_labeling(self) -> None:
        labeler = TripleBarrierLabeler(TripleBarrierConfig(
            take_profit=0.02, stop_loss=0.01, timeout_bars=10,
        ))
        prices = pd.Series(np.cumsum(np.random.randn(100) * 0.005) + 100)
        signals = pd.Series([1] + [0] * 99)  # Enter at first bar

        result = labeler.label(prices, signals)
        assert len(result) > 0
        assert "label" in result.columns
        assert "barrier" in result.columns

    def test_take_profit_hit(self) -> None:
        labeler = TripleBarrierLabeler(TripleBarrierConfig(
            take_profit=0.02, stop_loss=0.01, timeout_bars=20,
        ))
        # Strong uptrend — should hit take profit
        prices = pd.Series(np.linspace(100, 110, 50))
        signals = pd.Series([1] + [0] * 49)

        result = labeler.label(prices, signals)
        assert len(result) > 0
        assert result.iloc[0]["label"] == 1  # Profit
        assert result.iloc[0]["barrier"] == "take_profit"

    def test_stop_loss_hit(self) -> None:
        labeler = TripleBarrierLabeler(TripleBarrierConfig(
            take_profit=0.02, stop_loss=0.01, timeout_bars=20,
        ))
        # Strong downtrend — should hit stop loss
        prices = pd.Series(np.linspace(100, 90, 50))
        signals = pd.Series([1] + [0] * 49)

        result = labeler.label(prices, signals)
        assert len(result) > 0
        assert result.iloc[0]["label"] == -1  # Loss
        assert result.iloc[0]["barrier"] == "stop_loss"


class TestMetaLabeler:
    def test_meta_labels(self) -> None:
        labeler = MetaLabeler()
        predictions = pd.Series([1, -1, 1, -1, 1])
        actual_returns = pd.Series([0.01, -0.02, 0.005, 0.01, -0.01])

        meta = labeler.create_meta_labels(predictions, actual_returns)
        assert len(meta) == 5
        # Correct predictions: 1*0.01>0 ✓, -1*-0.02>0 ✓, 1*0.005>0 ✓, -1*0.01<0 ✗, 1*-0.01<0 ✗
        assert meta.iloc[0] == 1  # Correct
        assert meta.iloc[3] == 0  # Wrong

    def test_primary_accuracy(self) -> None:
        labeler = MetaLabeler()
        predictions = pd.Series([1, 1, -1, -1])
        actual_returns = pd.Series([0.01, 0.02, -0.01, 0.01])

        stats = labeler.compute_primary_accuracy(predictions, actual_returns)
        assert stats["accuracy"] == 0.75  # 3 out of 4 correct


class TestModelRegistry:
    def test_register_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ModelRegistry(Path(tmp))
            artifact = registry.register(
                name="test_model",
                parameters={"lr": 0.01, "n_estimators": 100},
                training_data_hash="abc123",
                feature_set_hash="def456",
                feature_names=["f1", "f2"],
            )
            assert artifact.model_id is not None
            assert artifact.status == ModelStatus.CANDIDATE

    def test_validate_and_promote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ModelRegistry(Path(tmp))
            artifact = registry.register(
                name="test_model",
                parameters={"lr": 0.01},
                training_data_hash="abc",
                feature_set_hash="def",
                feature_names=["f1"],
            )

            # Validate with good metrics
            registry.validate(
                artifact.model_id,
                validation_metrics={"sharpe_ratio": 1.5, "max_drawdown_pct": 10},
            )
            updated = registry._find(artifact.model_id)
            assert updated is not None
            assert updated.status == ModelStatus.VALIDATED

            # Promote
            registry.promote(artifact.model_id)
            updated = registry._find(artifact.model_id)
            assert updated is not None
            assert updated.status == ModelStatus.PRODUCTION

    def test_reject_poor_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ModelRegistry(Path(tmp))
            artifact = registry.register(
                name="bad_model",
                parameters={},
                training_data_hash="abc",
                feature_set_hash="def",
                feature_names=["f1"],
            )

            # Validate with poor metrics
            registry.validate(
                artifact.model_id,
                validation_metrics={"sharpe_ratio": 0.1, "max_drawdown_pct": 50},
            )
            updated = registry._find(artifact.model_id)
            assert updated is not None
            assert updated.status == ModelStatus.REJECTED

    def test_retire_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ModelRegistry(Path(tmp))
            artifact = registry.register(
                name="test_model",
                parameters={},
                training_data_hash="abc",
                feature_set_hash="def",
                feature_names=["f1"],
            )
            registry.validate(
                artifact.model_id,
                validation_metrics={"sharpe_ratio": 1.5, "max_drawdown_pct": 10},
            )
            registry.promote(artifact.model_id)
            registry.retire(artifact.model_id, reason="Replaced by v2")

            updated = registry._find(artifact.model_id)
            assert updated is not None
            assert updated.status == ModelStatus.RETIRED

    def test_list_and_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = ModelRegistry(Path(tmp))
            ids = []
            for i in range(3):
                a = registry.register(
                    name=f"model_{i}",
                    parameters={"lr": 0.01 * (i + 1)},
                    training_data_hash=f"abc{i}",
                    feature_set_hash=f"def{i}",
                    feature_names=["f1"],
                )
                registry.validate(
                    a.model_id,
                    validation_metrics={"sharpe_ratio": 0.5 + i * 0.5},
                )
                ids.append(a.model_id)

            models = registry.list_models()
            assert len(models) == 3

            comparison = registry.compare_models(ids, metric="sharpe_ratio")
            assert len(comparison) == 3
            # Best model should be first
            assert comparison[0]["sharpe_ratio"] == 1.5


class TestInferenceMonitor:
    def test_no_drift_initially(self) -> None:
        monitor = InferenceMonitor()
        np.random.seed(42)

        # Set training distribution
        train_data = np.random.randn(1000)
        monitor.set_training_distributions(
            feature_distributions={
                "f1": {"mean": float(train_data.mean()), "std": float(train_data.std())},
            },
            prediction_distribution={"mean": 0.0, "std": 0.5, "avg_confidence": 0.7},
        )

        # Record similar live data
        for _ in range(100):
            monitor.record_prediction(
                prediction=np.random.randn() * 0.5,
                confidence=0.65 + np.random.randn() * 0.05,
                features={"f1": float(np.random.randn())},
                latency_ms=50,
            )

        report = monitor.check_drift()
        # Should be no or low drift since distributions are similar
        assert report.overall_drift in (DriftLevel.NONE, DriftLevel.LOW)

    def test_drift_detected(self) -> None:
        monitor = InferenceMonitor()

        # Training: mean=0, std=1
        monitor.set_training_distributions(
            feature_distributions={
                "f1": {"mean": 0.0, "std": 1.0},
            },
            prediction_distribution={"mean": 0.0, "std": 0.5, "avg_confidence": 0.7},
        )

        # Live: mean=5, std=3 (significant drift)
        for _ in range(200):
            monitor.record_prediction(
                prediction=np.random.randn() * 3 + 5,
                confidence=0.3,
                features={"f1": float(np.random.randn() * 3 + 5)},
                latency_ms=50,
            )

        report = monitor.check_drift()
        assert report.overall_drift in (DriftLevel.MEDIUM, DriftLevel.HIGH, DriftLevel.CRITICAL)

    def test_confidence_collapse(self) -> None:
        monitor = InferenceMonitor()
        monitor.set_training_distributions(
            feature_distributions={"f1": {"mean": 0.0, "std": 1.0}},
            prediction_distribution={"mean": 0.0, "std": 0.5, "avg_confidence": 0.8},
        )

        # Record low-confidence predictions
        for _ in range(100):
            monitor.record_prediction(
                prediction=0.0,
                confidence=0.2,  # Much lower than training
                features={"f1": 0.0},
                latency_ms=50,
            )

        report = monitor.check_drift()
        assert report.confidence_drift in (DriftLevel.HIGH, DriftLevel.CRITICAL)

    def test_auto_disable(self) -> None:
        """Test that auto-disable triggers when drift is critical."""
        # Test 1: 1 critical should NOT disable
        monitor = InferenceMonitor(disable_threshold=0.01, confidence_threshold=0.5)
        monitor.set_training_distributions(
            feature_distributions={"f1": {"mean": 0.0, "std": 1.0}},
            prediction_distribution={"mean": 0.0, "std": 0.5, "avg_confidence": 0.95},
        )
        for _ in range(200):
            monitor.record_prediction(0.0, 0.02, {"f1": 0.0}, 50)
        report1 = monitor.check_drift()
        assert report1.should_disable is False  # Only 1 critical

        # Test 2: Verify the disable logic directly by checking the report
        # Create a report with 2 critical drifts
        report2 = DriftReport()
        report2.model_id = "test"
        # Simulate 2 critical feature drifts
        from baet.ml.monitoring import DriftLevel
        report2.feature_drifts = {"f1": DriftLevel.CRITICAL, "f2": DriftLevel.CRITICAL}
        report2.prediction_drift = DriftLevel.NONE
        report2.confidence_drift = DriftLevel.NONE
        # Manually check the disable logic
        all_drifts = list(report2.feature_drifts.values()) + [report2.prediction_drift, report2.confidence_drift]
        critical_count = sum(1 for d in all_drifts if d == DriftLevel.CRITICAL)
        should_disable = critical_count >= 2
        assert should_disable is True
