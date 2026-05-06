from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from baet.core.models import StrategyMetadata

SIGNAL_COLUMNS = [
    "timestamp",
    "symbol",
    "timeframe",
    "action",
    "target_position",
    "confidence",
    "size_hint",
    "strategy_name",
    "reason",
]


class StrategyContract(ABC):
    metadata: StrategyMetadata

    @abstractmethod
    def supports(self, symbol: str, timeframe: str) -> bool:
        """Return whether the strategy supports the requested market slice."""

    @abstractmethod
    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Return standardized order-intent signals."""
