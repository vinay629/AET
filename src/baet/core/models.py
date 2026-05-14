from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pandas as pd


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


class RegimeLabel(StrEnum):
    """Market regime classification labels."""

    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


@dataclass(frozen=True)
class RegimeMetadata:
    """Metadata for a regime detector."""

    name: str
    category: str
    version: str
    description: str
