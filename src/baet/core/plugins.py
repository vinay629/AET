"""Base classes and interfaces for BAET scoring plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd


@dataclass
class PluginMetadata:
    """Metadata for a scoring plugin."""
    name: str
    version: str
    description: str
    author: str = "BAET"


class ScoringPlugin(ABC):
    """
    Base class for all scoring plugins.

    A plugin takes market data and produces a score between -1.0 (strong sell)
    and 1.0 (strong buy), where 0.0 is neutral.
    """

    metadata: PluginMetadata

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.weight = 1.0  # Initial weight in the ensemble
        self.performance_history: list[float] = []

    @abstractmethod
    def calculate_score(self, data: pd.DataFrame) -> float:
        """
        Calculate a score based on the provided data.

        Args:
            data: DataFrame containing OHLCV and other relevant features.

        Returns:
            Score between -1.0 and 1.0.
        """
        pass

    @abstractmethod
    def learn(self, trade_outcome: Dict[str, Any]) -> None:
        """
        Learn from a trade outcome.

        Args:
            trade_outcome: Dictionary containing trade details and result (PnL, etc.)
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """Return the current status/health of the plugin."""
        return {
            "name": self.metadata.name,
            "weight": self.weight,
            "avg_performance": sum(self.performance_history) / len(self.performance_history) if self.performance_history else 0.0
        }
