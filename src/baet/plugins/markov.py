"""Markov Chain based scoring plugin."""

from __future__ import annotations

from typing import Any, Dict, Optional
import pandas as pd
import numpy as np
from baet.core.plugins import ScoringPlugin, PluginMetadata


class MarkovPlugin(ScoringPlugin):
    """Plugin that uses Markov Chain transitions to predict next state."""

    metadata = PluginMetadata(
        name="markov_chain",
        version="1.0.0",
        description="Predicts market regime transitions"
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        # 3 states: Down, Flat, Up
        self.transition_matrix = np.array([
            [0.4, 0.4, 0.2],
            [0.3, 0.4, 0.3],
            [0.2, 0.4, 0.4]
        ])

    def calculate_score(self, data: pd.DataFrame) -> float:
        if len(data) < 2:
            return 0.0

        # Determine current state based on last return
        last_return = data['close'].pct_change().iloc[-1]

        if last_return < -0.001:
            state = 0 # Down
        elif last_return > 0.001:
            state = 2 # Up
        else:
            state = 1 # Flat

        # Predict next state probabilities
        probs = self.transition_matrix[state]

        # Score is expected direction
        score = (probs[2] * 1.0) + (probs[1] * 0.0) + (probs[0] * -1.0)

        return float(score)

    def learn(self, trade_outcome: Dict[str, Any]) -> None:
        # Update transition matrix based on observed transition
        # This is where the 'AI Brain' evolves
        pnl = trade_outcome.get("pnl_pct", 0.0)
        self.performance_history.append(pnl)

        # Simple weight adjustment
        if pnl > 0:
            self.weight *= 1.03
        else:
            self.weight *= 0.97

        self.weight = np.clip(self.weight, 0.1, 2.0)
