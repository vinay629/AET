from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

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
