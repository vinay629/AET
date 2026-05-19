"""Research dashboard view for BAET.

Serves data for the quantitative trading terminal:
- Label quality metrics and distribution
- Feature importance and SHAP values
- Cross-validation split visualization
- Model registry comparison
- Derivatives microstructure data

All methods are read-only and return JSON-serializable dicts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from baet.core.events import EventStore
from baet.ml.feature_store import FeatureStore
from baet.ml.labels import TripleBarrierConfig, TripleBarrierLabeler
from baet.ml.model_registry import ModelRegistry
from baet.ml.purged_cv import PurgedKFold
from baet.data.features import DerivativesFeatureBuilder
from baet.config.models import DerivativesConfig

logger = logging.getLogger(__name__)


@dataclass
class ViewCache:
    """Simple TTL cache for view results."""
    data: dict[str, Any] = field(default_factory=dict)
    computed_at: float = 0.0
    ttl_seconds: float = 2.0

    @property
    def is_stale(self) -> bool:
        return (time.monotonic() - self.computed_at) > self.ttl_seconds


class ResearchView:
    """Materialized view for the ML research terminal."""

    def __init__(
        self,
        event_store: EventStore,
        feature_store: FeatureStore | None = None,
        model_registry: ModelRegistry | None = None,
        cache_ttl: float = 2.0,
    ) -> None:
        self.event_store = event_store
        self.feature_store = feature_store
        self.model_registry = model_registry
        self._cache = ViewCache(ttl_seconds=cache_ttl)

    def refresh(self, **kwargs: Any) -> dict[str, Any]:
        """Return the full research dashboard payload."""
        if not self._cache.is_stale and self._cache.data:
            return self._cache.data

        result: dict[str, Any] = {
            "labels": self._get_label_quality(),
            "features": self._get_feature_importance(),
            "cv_splits": self._get_cv_split_map(),
            "models": self._get_model_comparison(),
            "derivatives": self._get_microstructure_data(),
            "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
        }

        self._cache.data = result
        self._cache.computed_at = time.monotonic()
        return result

    def get_labels(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "1h",
        atr_window: int = 14,
        atr_multiplier: float = 2.0,
        timeout_bars: int = 20,
    ) -> dict[str, Any]:
        """Generate and return label quality data for the terminal."""
        return self._compute_labels(
            symbol=symbol,
            timeframe=timeframe,
            atr_window=atr_window,
            atr_multiplier=atr_multiplier,
            timeout_bars=timeout_bars,
        )

    def get_cv_splits(
        self,
        n_samples: int = 500,
        n_splits: int = 5,
        purge_gap: int = 2,
        embargo_gap: int = 1,
        label_horizon: int = 20,
    ) -> dict[str, Any]:
        """Return PurgedKFold split visualization data."""
        cv = PurgedKFold(
            n_splits=n_splits,
            purge_gap=purge_gap,
            embargo_gap=embargo_gap,
        )
        folds = cv.split(n_samples, label_horizon=label_horizon)

        return {
            "n_samples": n_samples,
            "n_splits": n_splits,
            "purge_gap": purge_gap,
            "embargo_gap": embargo_gap,
            "label_horizon": label_horizon,
            "folds": [
                {
                    "fold_index": f.fold_index,
                    "train_indices": f.train_indices.tolist(),
                    "test_indices": f.test_indices.tolist(),
                    "purged_count": f.purged_count,
                    "embargo_count": f.embargo_count,
                }
                for f in folds
            ],
        }

    def get_models(self) -> dict[str, Any]:
        """Return model registry comparison data."""
        return self._get_model_comparison()

    def get_derivatives(
        self,
        symbol: str = "BTCUSDT",
    ) -> dict[str, Any]:
        """Return derivatives microstructure data."""
        return self._get_microstructure_data(symbol=symbol)

    # ------------------------------------------------------------------
    # Internal computation methods
    # ------------------------------------------------------------------

    def _get_label_quality(self) -> dict[str, Any]:
        """Compute label distribution and quality metrics."""
        try:
            return self._compute_labels()
        except Exception as e:
            logger.warning(f"Label quality computation failed: {e}")
            return {"error": str(e), "distribution": {}, "barriers": []}

    def _compute_labels(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "1h",
        atr_window: int = 14,
        atr_multiplier: float = 2.0,
        timeout_bars: int = 20,
    ) -> dict[str, Any]:
        """Generate labels and compute quality metrics."""
        # Try to load features from the store
        prices = None
        high = None
        low = None

        if self.feature_store is not None:
            try:
                versions = self.feature_store.list_features()
                matching = [v for v in versions if v.name == f"{symbol}_{timeframe}"]
                if matching:
                    latest = sorted(matching, key=lambda v: v.created_at)[-1]
                    snapshot = self.feature_store.get(latest.name, latest.version)
                    if snapshot is not None:
                        df = snapshot.data
                        prices = df["close"]
                        high = df.get("high")
                        low = df.get("low")
            except Exception as e:
                logger.debug(f"Could not load features: {e}")

        if prices is None:
            # Return empty structure if no data available
            return {
                "available": False,
                "message": f"No feature data for {symbol}/{timeframe}. Run feature computation first.",
                "distribution": {},
                "barriers": [],
                "config": {
                    "atr_window": atr_window,
                    "atr_multiplier": atr_multiplier,
                    "timeout_bars": timeout_bars,
                },
            }

        config = TripleBarrierConfig(
            atr_window=atr_window,
            atr_multiplier=atr_multiplier,
            timeout_bars=timeout_bars,
        )
        labeler = TripleBarrierLabeler(config=config)
        labels_df = labeler.label(prices=prices, high=high, low=low)

        if labels_df.empty:
            return {
                "available": True,
                "distribution": {},
                "barriers": [],
                "message": "No labels generated.",
            }

        # Distribution
        dist = labels_df["label"].value_counts().to_dict()
        dist = {str(k): int(v) for k, v in dist.items()}
        total = sum(dist.values())

        # Barrier touch statistics
        barrier_counts = labels_df["barrier"].value_counts().to_dict()

        # Sample barrier data for visualization (last 50 labels)
        recent = labels_df.tail(50)
        barrier_points = []
        for _, row in recent.iterrows():
            idx = int(row["entry_idx"])
            if idx < len(prices):
                barrier_points.append({
                    "idx": idx,
                    "price": float(prices.iloc[idx]),
                    "label": int(row["label"]),
                    "barrier": str(row["barrier"]),
                    "return_pct": float(row["return_pct"]),
                    "holding_bars": int(row["holding_bars"]),
                })

        return {
            "available": True,
            "total_labels": total,
            "distribution": dist,
            "distribution_pct": {
                k: round(v / total * 100, 1) if total > 0 else 0
                for k, v in dist.items()
            },
            "barrier_counts": barrier_counts,
            "barrier_points": barrier_points,
            "config": {
                "atr_window": atr_window,
                "atr_multiplier": atr_multiplier,
                "timeout_bars": timeout_bars,
            },
        }

    def _get_feature_importance(self) -> dict[str, Any]:
        """Return feature importance data from the latest model."""
        if self.model_registry is None:
            return {"available": False, "message": "No model registry configured."}

        try:
            models = self.model_registry.list_models()
            if not models:
                return {"available": False, "message": "No models registered."}

            # Get latest model
            latest = sorted(models, key=lambda m: m.created_at)[-1]
            importance = latest.validation_metrics.get("feature_importance", {})

            return {
                "available": True,
                "model_id": latest.model_id,
                "model_name": latest.name,
                "model_version": latest.version,
                "feature_importance": importance,
                "top_features": sorted(
                    importance.items(), key=lambda x: x[1], reverse=True
                )[:20] if importance else [],
            }
        except Exception as e:
            logger.warning(f"Feature importance computation failed: {e}")
            return {"available": False, "error": str(e)}

    def _get_cv_split_map(self) -> dict[str, Any]:
        """Return cross-validation split visualization data."""
        return self.get_cv_splits()

    def _get_model_comparison(self) -> dict[str, Any]:
        """Return model registry comparison data."""
        if self.model_registry is None:
            return {"available": False, "message": "No model registry configured."}

        try:
            models = self.model_registry.list_models()
            return {
                "available": True,
                "count": len(models),
                "models": [
                    {
                        "model_id": m.model_id,
                        "name": m.name,
                        "version": m.version,
                        "status": m.status.value,
                        "created_at": m.created_at,
                        "validation_metrics": m.validation_metrics,
                        "tags": m.tags,
                    }
                    for m in sorted(models, key=lambda x: x.created_at, reverse=True)
                ],
            }
        except Exception as e:
            logger.warning(f"Model comparison failed: {e}")
            return {"available": False, "error": str(e)}

    def _get_microstructure_data(self, symbol: str = "BTCUSDT") -> dict[str, Any]:
        """Return derivatives microstructure visualization data."""
        if self.feature_store is None:
            return {"available": False, "message": "No feature store configured."}

        try:
            # Look for derivatives features
            versions = self.feature_store.list_features()
            deriv_versions = [v for v in versions if "derivatives" in v.name and symbol in v.name]

            if not deriv_versions:
                return {
                    "available": False,
                    "message": f"No derivatives features for {symbol}. Run feature computation first.",
                }

            latest = sorted(deriv_versions, key=lambda v: v.created_at)[-1]
            snapshot = self.feature_store.get(latest.name, latest.version)
            if snapshot is None:
                return {"available": False, "message": "Could not load derivatives data."}

            df = snapshot.data

            # Extract key columns for visualization
            result: dict[str, Any] = {"available": True}

            if "fr_zscore" in df.columns:
                result["funding_rate_zscore"] = df["fr_zscore"].dropna().tail(200).tolist()
            if "oi_change_1" in df.columns:
                result["oi_change"] = df["oi_change_1"].dropna().tail(200).tolist()
            if "liq_ratio" in df.columns:
                result["liquidation_ratio"] = df["liq_ratio"].dropna().tail(200).tolist()
            if "oi_price_signal" in df.columns:
                signals = df["oi_price_signal"].dropna().tail(200)
                result["oi_price_signals"] = signals.tolist()
                result["oi_signal_distribution"] = signals.value_counts().to_dict()

            return result

        except Exception as e:
            logger.warning(f"Microstructure data failed: {e}")
            return {"available": False, "error": str(e)}
