"""Machine Learning based scoring plugin."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from baet.core.plugins import PluginMetadata, ScoringPlugin

try:
    from sklearn.ensemble import RandomForestRegressor

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class MLScoringPlugin(ScoringPlugin):
    """
    Plugin that uses a Machine Learning model (Random Forest) to predict price changes.

    This plugin represents the 'ML' tool in the AI Brain ensemble. It can be extended
    to perform online learning or periodic retraining based on trade feedback.
    """

    metadata = PluginMetadata(
        name="ml_random_forest",
        version="1.0.0",
        description="Predicts next period return using a Random Forest regressor",
    )

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the ML plugin and the underlying Random Forest model.
        """
        super().__init__(config)
        self.model = None
        if SKLEARN_AVAILABLE:
            self.model = RandomForestRegressor(n_estimators=100, max_depth=5)
        self.is_trained = False

    def calculate_score(self, data: pd.DataFrame) -> float:
        """
        Calculate a score based on ML model predictions.

        Uses the trained Random Forest to predict the expected return of the next period.
        """
        if not SKLEARN_AVAILABLE or not self.is_trained:
            return 0.0

        # Placeholder for actual feature extraction and prediction
        # In a real scenario, we'd use the same features as MLRandomForestStrategy
        return 0.1  # Placeholder

    def learn(self, trade_outcome: dict[str, Any]) -> None:
        """
        Update the plugin's ensemble weight based on prediction accuracy (trade PnL).

        This allows the ensemble to automatically favor the ML model when it's performing
        well and discount it when it's consistently wrong.
        """
        pnl = trade_outcome.get("pnl_pct", 0.0)
        self.performance_history.append(pnl)

        # Incremental learning or weight adjustment
        if pnl < 0:
            self.weight *= 0.9  # ML often needs more aggressive weight reduction if it's wrong
        else:
            self.weight *= 1.05

        self.weight = np.clip(self.weight, 0.05, 3.0)

        # In a real implementation, we might trigger a re-train here
        # or update the model with the new data point.
