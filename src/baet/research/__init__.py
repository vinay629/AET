"""Research infrastructure for BAET.

Provides:
- Experiment tracking (config, metrics, artifacts)
- Walk-forward validation (rolling train/test)
- Regime detection integration
- Feature registry with governance
- Metrics engine (Sharpe, Sortino, Calmar, etc.)

All research is:
- Reproducible (config hash + event hash)
- Statistically valid (walk-forward, out-of-sample)
- Auditable (full experiment lineage)
"""

from baet.research.experiment import Experiment, ExperimentTracker
from baet.research.walk_forward import WalkForwardValidator, WindowConfig
from baet.research.feature_registry import FeatureRegistry, FeatureSpec
from baet.research.metrics import MetricsEngine

__all__ = [
    "Experiment",
    "ExperimentTracker",
    "WalkForwardValidator",
    "WindowConfig",
    "FeatureRegistry",
    "FeatureSpec",
    "MetricsEngine",
]
