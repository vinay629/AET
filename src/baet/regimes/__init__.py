"""Regime detection and labeling."""

from baet.regimes.contracts import RegimeDetector
from baet.regimes.detectors import SimpleTrendRegimeDetector, VolatilityRegimeDetector
from baet.regimes.discovery import discover_regimes, filter_supported_regimes

__all__ = [
    "RegimeDetector",
    "SimpleTrendRegimeDetector",
    "VolatilityRegimeDetector",
    "discover_regimes",
    "filter_supported_regimes",
]
