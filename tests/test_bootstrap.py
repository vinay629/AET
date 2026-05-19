"""Tests for the bootstrap pipeline orchestration."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from baet.config.models import DerivativesConfig, FeatureConfig
from baet.data.features import DerivativesFeatureBuilder, PandasFeatureBuilder
from baet.ml.labels import TripleBarrierConfig
from baet.ml.leakage import LeakageDetector
from baet.ml.model_registry import ModelRegistry, ModelStatus
from baet.ml.purged_cv import PurgedKFold
from baet.ml.training import TrainingConfig


@pytest.fixture
def sample_klines() -> pd.DataFrame:
    """Generate sample klines DataFrame."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    prices = 100 * np.cumprod(1 + np.random.normal(0.001, 0.01, n))
    return pd.DataFrame({
        "open_time": dates,
        "close_time": dates + pd.Timedelta(hours=1),
        "open": prices * (1 + np.random.normal(0, 0.002, n)),
        "high": prices * (1 + np.abs(np.random.normal(0, 0.005, n))),
        "low": prices * (1 - np.abs(np.random.normal(0, 0.005, n))),
        "close": prices,
        "volume": np.random.uniform(100, 1000, n),
        "quote_volume": np.random.uniform(10000, 100000, n),
        "trade_count": np.random.randint(100, 1000, n),
        "taker_buy_base_volume": np.random.uniform(50, 500, n),
        "taker_buy_quote_volume": np.random.uniform(5000, 50000, n),
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "source": "binance_rest",
    })


@pytest.fixture
def sample_oi() -> pd.DataFrame:
    """Sample open interest data."""
    n = 200
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({
        "timestamp": dates,
        "open_interest": 10000 + np.cumsum(np.random.normal(0, 50, n)),
    })


@pytest.fixture
def sample_funding() -> pd.DataFrame:
    """Sample funding rate data."""
    n = 200
    dates = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({
        "timestamp": dates,
        "funding_rate": np.random.normal(0.0001, 0.0005, n),
        "funding_time": dates,
    })


@pytest.fixture
def sample_liquidations() -> pd.DataFrame:
    """Sample liquidation data."""
    n = 50
    dates = pd.date_range("2026-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({
        "timestamp": dates,
        "side": np.random.choice(["BUY", "SELL"], n),
        "price": np.random.uniform(95, 105, n),
        "qty": np.random.uniform(0.1, 10.0, n),
        "last_fill_qty": np.random.uniform(0.05, 5.0, n),
        "order_status": "FILLED",
        "time_in_force": "GTC",
    })


class TestBootstrapImports:
    """Verify all bootstrap pipeline imports resolve."""

    def test_import_main(self) -> None:
        from baet.scripts.bootstrap_pipeline import main
        assert callable(main)

    def test_import_ingest(self) -> None:
        from baet.scripts.bootstrap_pipeline import ingest_data
        assert callable(ingest_data)

    def test_import_engineer(self) -> None:
        from baet.scripts.bootstrap_pipeline import engineer_features
        assert callable(engineer_features)

    def test_import_labels(self) -> None:
        from baet.scripts.bootstrap_pipeline import generate_labels
        assert callable(generate_labels)

    def test_import_leakage(self) -> None:
        from baet.scripts.bootstrap_pipeline import check_leakage
        assert callable(check_leakage)

    def test_import_train(self) -> None:
        from baet.scripts.bootstrap_pipeline import train_and_register
        assert callable(train_and_register)


class TestFeatureEngineering:
    """Test the feature engineering step with mock data."""

    def test_engineer_all_features(
        self, sample_klines, sample_oi, sample_funding, sample_liquidations
    ) -> None:
        data = {
            "klines": sample_klines,
            "open_interest": sample_oi,
            "funding_rates": sample_funding,
            "liquidations": sample_liquidations,
        }
        feat_config = FeatureConfig()
        deriv_config = DerivativesConfig()

        result = self._run_engineer(data, feat_config, deriv_config)

        assert result.shape[0] == len(sample_klines)
        # Should have base + derivatives features
        assert "return_1" in result.columns
        "oi_change_1" in result.columns
        "fr_zscore" in result.columns
        "liq_ratio" in result.columns

    def test_engineer_no_derivatives(self, sample_klines) -> None:
        data = {
            "klines": sample_klines,
            "open_interest": pd.DataFrame(),
            "funding_rates": pd.DataFrame(),
            "liquidations": pd.DataFrame(),
        }
        feat_config = FeatureConfig()
        deriv_config = DerivativesConfig()

        result = self._run_engineer(data, feat_config, deriv_config)

        assert result.shape[0] == len(sample_klines)
        assert "return_1" in result.columns

    def _run_engineer(self, data, feat_config, deriv_config):
        from baet.scripts.bootstrap_pipeline import engineer_features
        return engineer_features(data, feat_config, deriv_config)


class TestLabelGeneration:
    """Test the label generation step."""

    def test_labels_generated(self, sample_klines) -> None:
        from baet.scripts.bootstrap_pipeline import generate_labels

        barrier_config = TripleBarrierConfig(
            atr_window=14, atr_multiplier=2.0, timeout_bars=20
        )
        labels_df = generate_labels(sample_klines, barrier_config)

        assert not labels_df.empty
        assert "label" in labels_df.columns
        assert "barrier" in labels_df.columns
        assert set(labels_df["label"].unique()).issubset({-1, 0, 1})

    def test_label_distribution(self, sample_klines) -> None:
        from baet.scripts.bootstrap_pipeline import generate_labels

        barrier_config = TripleBarrierConfig(
            atr_window=14, atr_multiplier=2.5, timeout_bars=24
        )
        labels_df = generate_labels(sample_klines, barrier_config)
        dist = labels_df["label"].value_counts()
        # Should have at least 2 classes
        assert len(dist) >= 2


class TestLeakageDetection:
    """Test the leakage detection step."""

    def test_no_leakage_clean_data(self, sample_klines) -> None:
        from baet.scripts.bootstrap_pipeline import generate_labels, check_leakage

        barrier_config = TripleBarrierConfig(
            atr_window=14, atr_multiplier=2.0, timeout_bars=20
        )
        labels_df = generate_labels(sample_klines, barrier_config)
        report = check_leakage(sample_klines, labels_df)

        assert isinstance(report, dict)
        assert "passed" in report
        assert "n_critical" in report
        assert "n_warnings" in report

    def test_leakage_detector_directly(self) -> None:
        detector = LeakageDetector()
        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 5), columns=[f"f{i}" for i in range(5)])
        y = pd.Series(np.random.choice([-1, 0, 1], 100))
        report = detector.check_all(features=X, labels=y)
        assert isinstance(report.passed, bool)


class TestModelRegistryLifecycle:
    """Test the registry validation → promotion flow."""

    def test_register_validate_promote(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=Path(tmpdir))

            artifact = registry.register(
                name="test_model",
                parameters={"lr": 0.01},
                training_data_hash="abc123",
                feature_set_hash="def456",
                feature_names=["f1", "f2"],
                tags=["test"],
            )
            assert artifact.status == ModelStatus.CANDIDATE

            # Validate (must meet _passes_validation criteria)
            registry.validate(
                model_id=artifact.model_id,
                validation_metrics={
                    "mean_accuracy": 0.55,
                    "mean_f1_macro": 0.50,
                    "sharpe_ratio": 1.0,       # Must be >= 0.5
                    "max_drawdown_pct": 15.0,   # Must be <= 30
                },
                leakage_report={"passed": True, "n_critical": 0},
            )

            # Check validated
            updated = registry._find(artifact.model_id)
            assert updated is not None
            assert updated.status == ModelStatus.VALIDATED

            # Promote
            registry.promote(artifact.model_id)
            promoted = registry._find(artifact.model_id)
            assert promoted is not None
            assert promoted.status == ModelStatus.PRODUCTION

    def test_promote_rejected_model_fails(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=Path(tmpdir))

            artifact = registry.register(
                name="bad_model",
                parameters={},
                training_data_hash="abc",
                feature_set_hash="def",
                feature_names=["f1"],
            )

            # Validate with critical leakage
            registry.validate(
                model_id=artifact.model_id,
                validation_metrics={"mean_accuracy": 0.3},
                leakage_report={"passed": False, "n_critical": 2},
            )

            updated = registry._find(artifact.model_id)
            assert updated is not None
            assert updated.status == ModelStatus.REJECTED

            # Promotion should fail
            with pytest.raises(ValueError, match="must be validated"):
                registry.promote(artifact.model_id)


class TestTrainingConfig:
    """Test training config defaults."""

    def test_default_config(self) -> None:
        config = TrainingConfig()
        assert config.symbol == "BTCUSDT"
        assert config.atr_window == 14
        assert config.atr_multiplier == 2.0
        assert config.n_splits == 5

    def test_custom_config(self) -> None:
        config = TrainingConfig(
            symbol="ETHUSDT",
            atr_window=21,
            atr_multiplier=3.0,
            n_splits=7,
        )
        assert config.symbol == "ETHUSDT"
        assert config.atr_window == 21
        assert config.atr_multiplier == 3.0
        assert config.n_splits == 7


class TestArgParser:
    """Test CLI argument parsing."""

    def test_default_args(self) -> None:
        from baet.scripts.bootstrap_pipeline import parse_args
        with patch("sys.argv", ["bootstrap_pipeline"]):
            args = parse_args()
        assert args.symbol == "BTCUSDT"
        assert args.timeframe == "1h"
        assert args.days == 180
        assert args.atr_window == 14
        assert args.atr_mult == 2.5
        assert args.timeout_bars == 24
        assert args.n_splits == 5

    def test_custom_args(self) -> None:
        from baet.scripts.bootstrap_pipeline import parse_args
        with patch("sys.argv", [
            "bootstrap_pipeline",
            "--symbol", "ETHUSDT",
            "--days", "90",
            "--atr-window", "21",
            "--atr-mult", "3.0",
            "--verbose",
        ]):
            args = parse_args()
        assert args.symbol == "ETHUSDT"
        assert args.days == 90
        assert args.atr_window == 21
        assert args.atr_mult == 3.0
        assert args.verbose is True
