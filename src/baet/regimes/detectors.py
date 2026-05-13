from __future__ import annotations

import pandas as pd

from baet.core.enums import RegimeLabel
from baet.core.models import RegimeMetadata


class VolatilityRegimeDetector:
    """Detect high/low volatility regimes using rolling std of returns."""

    metadata = RegimeMetadata(
        name="volatility_regime",
        version="1.0.0",
        description="Classifies periods as high/low volatility based on rolling std of returns.",
    )

    def __init__(
        self, window: int = 20, high_threshold: float = 1.0, low_threshold: float = 0.3
    ) -> None:
        self.window = window
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold

    def detect(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        frame = frame.sort_values("close_time").reset_index(drop=True)
        returns = frame["close"].pct_change().abs()
        rolling_std = returns.rolling(self.window, min_periods=1).std()

        regime = pd.Series(RegimeLabel.RANGING, index=frame.index)
        regime[rolling_std >= self.high_threshold] = RegimeLabel.HIGH_VOLATILITY
        regime[rolling_std <= self.low_threshold] = RegimeLabel.LOW_VOLATILITY

        out = frame[["symbol", "timeframe", "close_time"]].copy()
        out = out.rename(columns={"close_time": "timestamp"})
        out["regime"] = regime.astype(str)
        out["confidence"] = 1.0
        return out


class SimpleTrendRegimeDetector:
    """Detect trending vs ranging regimes using ADX-like heuristic."""

    metadata = RegimeMetadata(
        name="simple_trend",
        version="1.0.0",
        description="Heuristic trend/ranging detector using price direction consistency.",
    )

    def __init__(self, window: int = 14, trend_threshold: float = 0.5) -> None:
        self.window = window
        self.trend_threshold = trend_threshold

    def detect(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.copy()
        frame = frame.sort_values("close_time").reset_index(drop=True)
        close = frame["close"]
        up = close.diff().clip(lower=0.0)
        down = (-close.diff()).clip(lower=0.0)

        roll_up = up.rolling(self.window, min_periods=1).mean()
        roll_down = down.rolling(self.window, min_periods=1).mean()
        directional_index = (roll_up - roll_down).abs() / (roll_up + roll_down).replace(0.0, 1e-9)

        regime = pd.Series(RegimeLabel.RANGING, index=frame.index)
        regime[directional_index >= self.trend_threshold] = RegimeLabel.TRENDING

        out = frame[["symbol", "timeframe", "close_time"]].copy()
        out = out.rename(columns={"close_time": "timestamp"})
        out["regime"] = regime.astype(str)
        out["confidence"] = directional_index.clip(0.0, 1.0)
        return out
