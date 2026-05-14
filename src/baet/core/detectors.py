from __future__ import annotations

import pandas as pd

from baet.core.models import RegimeLabel


class Detector:
    """Base class for all regime detectors"""

    def detect_regime(self, data: pd.DataFrame) -> RegimeLabel:
        """Detect regime based on input data"""
        raise NotImplementedError("Subclasses must implement this method")


class VolatilityDetector(Detector):
    """Detects regime based on rolling volatility"""

    def __init__(self, window: int = 20):
        self.window = window

    def detect_regime(self, data: pd.DataFrame) -> RegimeLabel:
        """Calculate rolling volatility and classify regime"""
        if "returns" not in data.columns:
            # Handle case where returns are not provided
            returns = data["close"].pct_change().rolling(window=self.window).std()
        else:
            returns = data["returns"].rolling(window=self.window).std()

        avg_volatility = returns.mean()
        if avg_volatility > 0.02:
            return RegimeLabel.HIGH_VOLATILITY
        elif avg_volatility > 0.01:
            return RegimeLabel.LOW_VOLATILITY
        else:
            return RegimeLabel.RANGING
