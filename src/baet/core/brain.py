"""AI Brain: Ensemble of scoring plugins with feedback loop."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from baet.core.plugins import ScoringPlugin

logger = logging.getLogger(__name__)


class ScoringEnsemble:
    """
    The 'AI Brain' that coordinates multiple scoring plugins.

    It aggregates scores from all plugins using their weights and
    provides a final recommendation. It also distributes learning
    feedback to all plugins, allowing the system to evolve over time
    by learning from 'wrong' trades.
    """

    def __init__(self, plugins: List[ScoringPlugin]):
        """
        Initialize the ScoringEnsemble with a list of plugins.

        Args:
            plugins: List of ScoringPlugin instances that will contribute to the decision.
        """
        self.plugins = plugins
        # Stores the last calculated scores per plugin for the learning feedback loop
        self.last_scores: Dict[str, float] = {}

    def calculate_combined_score(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate weighted average score from all plugins.

        Returns:
            Dict containing the final score and individual plugin scores.
        """
        if not self.plugins:
            return {"score": 0.0, "components": {}}

        total_score = 0.0
        total_weight = 0.0
        components = {}

        for plugin in self.plugins:
            score = plugin.calculate_score(data)
            weight = plugin.weight

            total_score += score * weight
            total_weight += weight

            components[plugin.metadata.name] = {
                "score": score,
                "weight": weight,
                "contribution": score * weight,
            }

        final_score = total_score / total_weight if total_weight > 0 else 0.0
        self.last_scores = {name: info["score"] for name, info in components.items()}

        return {"score": final_score, "components": components, "total_weight": total_weight}

    def learn_from_trade(self, trade_outcome: Dict[str, Any]) -> None:
        """
        Pass trade feedback to all plugins so they can evolve.
        """
        logger.info(
            f"AI Brain learning from trade outcome: PnL {trade_outcome.get('pnl_pct', 0):.2%}"
        )

        for plugin in self.plugins:
            # We can also pass how much this specific plugin contributed to the decision
            plugin_score = self.last_scores.get(plugin.metadata.name, 0.0)

            # If plugin score matched trade direction, it was 'right'
            # (Simplified logic)
            plugin.learn(trade_outcome)

        # Optional: Global ensemble weight adjustment logic here

    def get_brain_state(self) -> List[Dict[str, Any]]:
        """Return the current state of all plugins in the brain."""
        return [plugin.get_status() for plugin in self.plugins]
