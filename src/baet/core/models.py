from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from baet.core.enums import RegimeLabel


@dataclass(frozen=True)
class DatasetRef:
    symbol: str
    timeframe: str
    path: Path


@dataclass(frozen=True)
class BacktestArtifacts:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    symbol_returns: pd.DataFrame
    metrics: pd.DataFrame
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class StrategyMetadata:
    name: str
    category: str
    version: str
    description: str




@dataclass(frozen=True)
class RegimeMetadata:
    """Metadata for a regime detector."""
    name: str
    category: str
    version: str
    description: str
