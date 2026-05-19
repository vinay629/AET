"""ML infrastructure for BAET.

All ML components are event-sourced and deterministic:
- Leakage detection (time, cross-section, label)
- Purged cross-validation (K-fold, embargo, combinatorial)
- Labeling (triple barrier, meta-labeling)
- Feature selection (mutual info, SHAP, stability)
- Model registry (reproducible artifacts)
- Online inference monitoring (drift, confidence, latency)

Principles:
- Optimize for stable edges, not best backtest
- Purge overlapping labels to prevent leakage
- Monitor live vs train distribution drift
- All models are reproducible artifacts with full lineage
"""

from baet.ml.leakage import LeakageDetector, LeakageReport
from baet.ml.purged_cv import PurgedKFold, EmbargoCV, CombinatorialPurgedCV
from baet.ml.labels import TripleBarrierLabeler, MetaLabeler
from baet.ml.model_registry import ModelRegistry, ModelArtifact
from baet.ml.monitoring import InferenceMonitor, DriftReport

__all__ = [
    "LeakageDetector",
    "LeakageReport",
    "PurgedKFold",
    "EmbargoCV",
    "CombinatorialPurgedCV",
    "TripleBarrierLabeler",
    "MetaLabeler",
    "ModelRegistry",
    "ModelArtifact",
    "InferenceMonitor",
    "DriftReport",
]
