"""Machine Learning based scoring plugin."""

from __future__ import annotations

from typing import Any, Dict, Optional
import pandas as pd
import numpy as np
from baet.core.plugins import ScoringPlugin, PluginMetadata

try:
    from sklearn.ensemble import RandomForestRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class MLScoringPlugin(ScoringPlugin):
    """Plugin that uses a Random Forest to predict price change."""

    metadata = PluginMetadata(
        name="ml_random_forest",
        version="1.0.0",
        description="Predicts next period return using Random Forest"
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.model = None
        if SKLEARN_AVAILABLE:
            self.model = RandomForestRegressor(n_estimators=100, max_depth=5)
        self.is_trained = False

    def calculate_score(self, data: pd.DataFrame) -> float:
        if not SKLEARN_AVAILABLE or not self.is_trained:
            return 0.0

        # Placeholder for actual feature extraction and prediction
        # In a real scenario, we'd use the same features as MLRandomForestStrategy
        return 0.1 # Placeholder

    def learn(self, trade_outcome: Dict[str, Any]) -> None:
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
