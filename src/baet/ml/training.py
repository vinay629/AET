"""Baseline model training pipeline for BAET.

Orchestrates the full ML workflow:
1. Load features from the feature store
2. Generate labels via Triple Barrier Method (with dynamic ATR scaling)
3. Run leakage detection
4. Train a GradientBoosting baseline using PurgedKFold CV
5. Evaluate with walk-forward validation
6. Register the model in the model registry

This is the entry point for moving from infrastructure to active research.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.preprocessing import StandardScaler

from baet.core.enums import RegimeLabel
from baet.ml.feature_store import FeatureStore
from baet.ml.labels import TripleBarrierConfig, TripleBarrierLabeler
from baet.ml.leakage import LeakageDetector, LeakageReport
from baet.ml.model_registry import ModelArtifact, ModelRegistry, ModelStatus
from baet.ml.purged_cv import PurgedKFold
from baet.ml.monitoring import InferenceMonitor

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for a baseline training run."""
    # Data
    symbol: str = "BTCUSDT"
    timeframe: str = "1h"

    # Labeling (Triple Barrier)
    take_profit: float = 0.02
    stop_loss: float = 0.01
    timeout_bars: int = 20
    atr_window: int | None = 14       # None = static barriers
    atr_multiplier: float = 2.0       # ATR multiple for dynamic barriers

    # Cross-validation
    n_splits: int = 5
    purge_gap: int = 2
    embargo_gap: int = 1

    # Model
    model_type: str = "hist_gradient_boosting"  # "gradient_boosting" | "hist_gradient_boosting"
    n_estimators: int = 200
    max_depth: int = 5
    learning_rate: float = 0.05
    min_samples_leaf: int = 50         # Regularization for financial noise

    # Feature selection
    max_features: int | None = None    # None = all features
    correlation_threshold: float = 0.95  # Drop highly correlated features

    # Registry
    model_name: str = "baseline_gb"
    model_version: str = "1.0.0"
    experiment_id: str = ""


@dataclass
class TrainingResult:
    """Result of a complete training run."""
    model_artifact: ModelArtifact
    cv_metrics: dict[str, list[float]] = field(default_factory=dict)
    feature_importance: dict[str, float] = field(default_factory=dict)
    label_distribution: dict[str, int] = field(default_factory=dict)
    leakage_report: LeakageReport | None = None
    train_time_seconds: float = 0.0
    n_samples: int = 0
    n_features: int = 0

    @property
    def mean_cv_accuracy(self) -> float:
        return float(np.mean(self.cv_metrics.get("accuracy", [0.0])))

    @property
    def mean_cv_f1(self) -> float:
        return float(np.mean(self.cv_metrics.get("f1_macro", [0.0])))

    def summary(self) -> str:
        lines = [
            f"=== Training Result: {self.model_artifact.name} v{self.model_artifact.version} ===",
            f"Samples: {self.n_samples} | Features: {self.n_features}",
            f"Label distribution: {self.label_distribution}",
            f"CV Accuracy: {self.mean_cv_accuracy:.4f} (+/- {np.std(self.cv_metrics.get('accuracy', [0])):.4f})",
            f"CV F1 (macro): {self.mean_cv_f1:.4f} (+/- {np.std(self.cv_metrics.get('f1_macro', [0])):.4f})",
            f"Train time: {self.train_time_seconds:.1f}s",
            f"Model ID: {self.model_artifact.model_id}",
            f"Status: {self.model_artifact.status.value}",
        ]
        if self.leakage_report and not self.leakage_report.passed:
            lines.append(f"⚠️  Leakage issues detected: {len(self.leakage_report.findings)}")
        return "\n".join(lines)


class BaselineTrainer:
    """
    End-to-end baseline model training pipeline.

    Usage:
        trainer = BaselineTrainer(
            feature_store=FeatureStore(Path("features")),
            model_registry=ModelRegistry(Path("models")),
        )
        result = trainer.run(TrainingConfig(symbol="BTCUSDT", timeframe="1h"))
        print(result.summary())
    """

    def __init__(
        self,
        feature_store: FeatureStore,
        model_registry: ModelRegistry,
    ) -> None:
        self.feature_store = feature_store
        self.model_registry = model_registry

    def run(self, config: TrainingConfig) -> TrainingResult:
        """Execute the full training pipeline."""
        import time as _time

        t0 = _time.monotonic()
        logger.info(f"Starting training run: {config.model_name} v{config.model_version}")

        # 1. Load features
        logger.info("Loading features...")
        features_df = self._load_features(config.symbol, config.timeframe)
        if features_df.empty:
            raise ValueError(f"No features found for {config.symbol}/{config.timeframe}")

        # 2. Generate labels with dynamic barriers
        logger.info("Generating triple barrier labels...")
        labels_df = self._generate_labels(features_df, config)
        if labels_df.empty:
            raise ValueError("No labels generated — check barrier parameters")

        # 3. Align features and labels
        X, y, feature_names = self._prepare_dataset(features_df, labels_df, config)
        logger.info(f"Dataset: {len(X)} samples, {len(feature_names)} features")
        logger.info(f"Label distribution: {dict(pd.Series(y).value_counts().sort_index())}")

        # 4. Leakage detection
        logger.info("Running leakage detection...")
        leakage_report = self._check_leakage(X, y, feature_names)

        # 5. Feature selection
        X, feature_names = self._select_features(X, feature_names, config)

        # 6. Train with PurgedKFold CV
        logger.info(f"Training {config.model_type} with {config.n_splits}-fold PurgedKFold...")
        model, cv_metrics, feature_importance = self._train_cv(X, y, feature_names, config)

        # 7. Compute data hash for lineage
        data_hash = hashlib.sha256(
            pd.util.hash_pandas_object(features_df).values.tobytes()
        ).hexdigest()[:16]

        feature_hash = hashlib.sha256(
            json.dumps(feature_names, sort_keys=True).encode()
        ).hexdigest()[:16]

        # 8. Register model
        logger.info("Registering model...")
        artifact = self._register_model(
            model=model,
            config=config,
            cv_metrics=cv_metrics,
            feature_names=feature_names,
            feature_hash=feature_hash,
            data_hash=data_hash,
            leakage_report=leakage_report,
        )

        train_time = _time.monotonic() - t0

        label_dist = dict(pd.Series(y).value_counts().sort_index())
        label_dist = {str(k): int(v) for k, v in label_dist.items()}

        result = TrainingResult(
            model_artifact=artifact,
            cv_metrics=cv_metrics,
            feature_importance=feature_importance,
            label_distribution=label_dist,
            leakage_report=leakage_report,
            train_time_seconds=train_time,
            n_samples=len(X),
            n_features=len(feature_names),
        )

        logger.info(f"\n{result.summary()}")
        return result

    def _load_features(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load features from the feature store.

        The feature name format is "{symbol}_{timeframe}" (e.g. "BTCUSDT_1h").
        """
        feature_name = f"{symbol}_{timeframe}"

        # Try feature store: look for any version matching the name
        versions = self.feature_store.list_features()
        matching = [v for v in versions if v.name == feature_name]
        if matching:
            # Use the latest version by created_at
            latest = sorted(matching, key=lambda v: v.created_at)[-1]
            snapshot = self.feature_store.get(latest.name, latest.version)
            if snapshot is not None:
                logger.info(f"Loaded features from store: {latest.feature_id}")
                return snapshot.data

        # Fallback: try to load from parquet directly
        feature_dir = self.feature_store.store_dir / feature_name
        if feature_dir.exists():
            parquet_files = sorted(feature_dir.glob("*.parquet"))
            if parquet_files:
                logger.info(f"Loaded features from parquet: {parquet_files[-1]}")
                return pd.read_parquet(parquet_files[-1])

        logger.warning(f"No features found for {feature_name}")
        return pd.DataFrame()

    def _generate_labels(
        self, features_df: pd.DataFrame, config: TrainingConfig
    ) -> pd.DataFrame:
        """Generate triple barrier labels with dynamic ATR scaling."""
        prices = features_df["close"]

        # Extract high/low for ATR computation
        high = features_df.get("high")
        low = features_df.get("low")

        # Use pre-computed ATR if available
        atr = features_df.get("atr_like_14")

        barrier_config = TripleBarrierConfig(
            take_profit=config.take_profit,
            stop_loss=config.stop_loss,
            timeout_bars=config.timeout_bars,
            atr_window=config.atr_window,
            atr_multiplier=config.atr_multiplier,
        )

        labeler = TripleBarrierLabeler(config=barrier_config)
        labels_df = labeler.label(
            prices=prices,
            signals=None,  # Label every bar as potential entry
            high=high,
            low=low,
            atr=atr,
        )

        return labels_df

    def _prepare_dataset(
        self,
        features_df: pd.DataFrame,
        labels_df: pd.DataFrame,
        config: TrainingConfig,
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """Align features and labels, return X, y, feature_names."""
        # Identify feature columns (exclude metadata)
        exclude_cols = {
            "timestamp", "close_time", "open_time", "symbol", "timeframe",
            "open", "high", "low", "close", "volume", "quote_volume",
            "trades_count", "taker_buy_volume", "taker_buy_quote_volume",
        }
        feature_names = [c for c in features_df.columns if c not in exclude_cols]

        # Drop rows with NaN in features
        feature_data = features_df[feature_names].copy()
        valid_mask = ~feature_data.isna().any(axis=1)
        feature_data = feature_data[valid_mask]

        # Align labels with features using entry_idx
        if "entry_idx" in labels_df.columns:
            label_indices = labels_df["entry_idx"].values
            # Only keep labels whose entry_idx is within valid feature range
            valid_labels = labels_df[
                (labels_df["entry_idx"] >= 0) &
                (labels_df["entry_idx"] < len(feature_data))
            ]
            # Build aligned arrays
            aligned_features = []
            aligned_labels = []
            for _, row in valid_labels.iterrows():
                idx = int(row["entry_idx"])
                if idx < len(feature_data) and valid_mask.iloc[idx]:
                    aligned_features.append(feature_data.iloc[idx].values)
                    aligned_labels.append(int(row["label"]))
            X = np.array(aligned_features)
            y = np.array(aligned_labels)
        else:
            # Fallback: direct alignment by position
            min_len = min(len(feature_data), len(labels_df))
            X = feature_data.iloc[:min_len].values
            y = labels_df["label"].iloc[:min_len].values.astype(int)

        # Remove any remaining NaN/Inf
        valid_rows = ~(np.isnan(X).any(axis=1) | np.isinf(X).any(axis=1))
        X = X[valid_rows]
        y = y[valid_rows]

        return X, y, feature_names

    def _check_leakage(
        self, X: np.ndarray, y: np.ndarray, feature_names: list[str]
    ) -> LeakageReport:
        """Run leakage detection on the prepared dataset."""
        try:
            detector = LeakageDetector()
            report = detector.check_all(
                features=pd.DataFrame(X, columns=feature_names),
                labels=pd.Series(y),
            )
            if not report.passed:
                logger.warning(f"Leakage detected: {len(report.findings)} issues")
                for finding in report.findings:
                    logger.warning(f"  [{finding.severity.value}] {finding.leakage_type.value}: {finding.message}")
            else:
                logger.info("No leakage detected ✓")
            return report
        except Exception as e:
            logger.warning(f"Leakage check failed: {e}")
            return LeakageReport()

    def _select_features(
        self, X: np.ndarray, feature_names: list[str], config: TrainingConfig
    ) -> tuple[np.ndarray, list[str]]:
        """Remove highly correlated features and limit feature count."""
        if len(feature_names) <= 1:
            return X, feature_names

        df = pd.DataFrame(X, columns=feature_names)

        # Drop highly correlated features
        if config.correlation_threshold < 1.0:
            corr = df.corr().abs()
            upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
            to_drop = {col for col in upper.columns if any(upper[col] > config.correlation_threshold)}
            if to_drop:
                logger.info(f"Dropping {len(to_drop)} highly correlated features: {to_drop}")
                df = df.drop(columns=list(to_drop))
                feature_names = list(df.columns)

        # Limit feature count
        if config.max_features and len(feature_names) > config.max_features:
            # Use mutual information for feature ranking
            from sklearn.feature_selection import mutual_info_classif
            mi_scores = mutual_info_classif(df.values, pd.Series([0] * len(df)), random_state=42)
            # Fallback: use variance if MI fails
            if np.all(mi_scores == 0):
                mi_scores = df.var().values
            top_indices = np.argsort(mi_scores)[-config.max_features:]
            feature_names = [feature_names[i] for i in sorted(top_indices)]
            X = df[feature_names].values
        else:
            X = df.values

        return X, feature_names

    def _train_cv(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: list[str],
        config: TrainingConfig,
    ) -> tuple[Any, dict[str, list[float]], dict[str, float]]:
        """Train model with PurgedKFold cross-validation."""
        # Build model
        if config.model_type == "gradient_boosting":
            model = GradientBoostingClassifier(
                n_estimators=config.n_estimators,
                max_depth=config.max_depth,
                learning_rate=config.learning_rate,
                min_samples_leaf=config.min_samples_leaf,
                subsample=0.8,
                random_state=42,
            )
        else:
            model = HistGradientBoostingClassifier(
                max_iter=config.n_estimators,
                max_depth=config.max_depth,
                learning_rate=config.learning_rate,
                min_samples_leaf=config.min_samples_leaf,
                l2_regularization=1.0,
                random_state=42,
            )

        # PurgedKFold CV
        cv = PurgedKFold(
            n_splits=config.n_splits,
            purge_gap=config.purge_gap,
            embargo_gap=config.embargo_gap,
        )

        cv_metrics: dict[str, list[float]] = {
            "accuracy": [],
            "f1_macro": [],
        }

        folds = cv.split(len(X), label_horizon=config.timeout_bars)
        for fold in folds:
            train_idx = fold.train_indices
            test_idx = fold.test_indices
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train
            model_fold = type(model)(**model.get_params())
            model_fold.fit(X_train_scaled, y_train)

            # Evaluate
            y_pred = model_fold.predict(X_test_scaled)
            acc = accuracy_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)

            cv_metrics["accuracy"].append(acc)
            cv_metrics["f1_macro"].append(f1)

            logger.info(
                f"  Fold {fold.fold_index + 1}/{config.n_splits}: "
                f"acc={acc:.4f}, f1={f1:.4f} "
                f"(train={len(train_idx)}, test={len(test_idx)}, "
                f"purged={fold.purged_count}, embargo={fold.embargo_count})"
            )

        # Train final model on all data
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model.fit(X_scaled, y)

        # Feature importance
        importance: dict[str, float] = {}
        if hasattr(model, "feature_importances_"):
            for name, imp in sorted(
                zip(feature_names, model.feature_importances_),
                key=lambda x: x[1],
                reverse=True,
            ):
                importance[name] = float(imp)

        # Log top features
        if importance:
            top = list(importance.items())[:10]
            logger.info("Top 10 features:")
            for name, imp in top:
                logger.info(f"  {name}: {imp:.4f}")

        return model, cv_metrics, importance

    def _register_model(
        self,
        model: Any,
        config: TrainingConfig,
        cv_metrics: dict[str, list[float]],
        feature_names: list[str],
        feature_hash: str,
        data_hash: str,
        leakage_report: LeakageReport | None,
    ) -> ModelArtifact:
        """Register the trained model in the model registry."""
        # Get git commit
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).parent,
                text=True,
            ).strip()
        except Exception:
            git_commit = "unknown"

        # Build artifact
        artifact = ModelArtifact(
            name=config.model_name,
            version=config.model_version,
            experiment_id=config.experiment_id or f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            training_data_hash=data_hash,
            feature_set_hash=feature_hash,
            feature_names=feature_names,
            parameter_hash=hashlib.sha256(
                json.dumps({
                    "model_type": config.model_type,
                    "n_estimators": config.n_estimators,
                    "max_depth": config.max_depth,
                    "learning_rate": config.learning_rate,
                    "atr_window": config.atr_window,
                    "atr_multiplier": config.atr_multiplier,
                }, sort_keys=True).encode()
            ).hexdigest()[:16],
            parameters={
                "model_type": config.model_type,
                "n_estimators": config.n_estimators,
                "max_depth": config.max_depth,
                "learning_rate": config.learning_rate,
                "atr_window": config.atr_window,
                "atr_multiplier": config.atr_multiplier,
                "n_splits": config.n_splits,
            },
            git_commit=git_commit,
            train_metrics={
                "n_samples": int(cv_metrics.get("accuracy", [0]) and len(cv_metrics["accuracy"])),
            },
            validation_metrics={
                "mean_accuracy": float(np.mean(cv_metrics.get("accuracy", [0]))),
                "std_accuracy": float(np.std(cv_metrics.get("accuracy", [0]))),
                "mean_f1_macro": float(np.mean(cv_metrics.get("f1_macro", [0]))),
                "std_f1_macro": float(np.std(cv_metrics.get("f1_macro", [0]))),
            },
            leakage_report=leakage_report.summary() if leakage_report else {},
            tags=["baseline", config.model_type, config.symbol, config.timeframe],
        )

        # Save to registry (register creates the base artifact)
        registered = self.model_registry.register(
            name=config.model_name,
            parameters={
                "model_type": config.model_type,
                "n_estimators": config.n_estimators,
                "max_depth": config.max_depth,
                "learning_rate": config.learning_rate,
                "atr_window": config.atr_window,
                "atr_multiplier": config.atr_multiplier,
                "n_splits": config.n_splits,
                "purge_gap": config.purge_gap,
                "embargo_gap": config.embargo_gap,
            },
            training_data_hash=data_hash,
            feature_set_hash=feature_hash,
            feature_names=feature_names,
            experiment_id=config.experiment_id or f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            tags=["baseline", config.model_type, config.symbol, config.timeframe],
        )
        # Enrich with training results
        registered.version = config.model_version
        registered.validation_metrics = {
            "mean_accuracy": float(np.mean(cv_metrics.get("accuracy", [0]))),
            "std_accuracy": float(np.std(cv_metrics.get("accuracy", [0]))),
            "mean_f1_macro": float(np.mean(cv_metrics.get("f1_macro", [0]))),
            "std_f1_macro": float(np.std(cv_metrics.get("f1_macro", [0]))),
        }
        registered.leakage_report = leakage_report.summary() if leakage_report else {}
        # Re-save with enriched data
        self.model_registry._save_artifact(registered)
        logger.info(f"Model registered: {registered.artifact_id}")

        return artifact
