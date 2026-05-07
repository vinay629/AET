from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

import pandas as pd


class RegimeDetector(Protocol):
    """Protocol for regime detectors."""

    @abstractmethod
    def detect(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Detect regimes for the provided market frame.

        Parameters
        ----------
        frame : pd.DataFrame
            Market data with at least 'symbol', 'timeframe', 'close',
            and optionally 'high', 'low', 'volume'.

        Returns
        -------
        pd.DataFrame
            Must contain columns: ['symbol', 'timeframe', 'timestamp', 'regime', 'confidence']
            where 'regime' values are strings from RegimeLabel.
        """
        ...


class RegimeDetectorABC(ABC):
    """Abstract base class for regime detectors."""

    @abstractmethod
    def detect(self, frame: pd.DataFrame) -> pd.DataFrame:
        ...
