"""Regime detection engine for BAET.

Classifies market state into regimes:
- Trending / Mean reverting
- High volatility / Low volatility
- Panic/stress
- Range-bound
- Momentum expansion
- Liquidity vacuum

Strategies declare which regimes they support.
Risk engine adapts leverage per regime.
Portfolio weights adapt automatically.

All regime classifications are:
- Deterministic (same data → same regime)
- Event-sourced (regime changes are events)
- Auditable (full classification history)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RegimeLabel(StrEnum):
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    PANIC = "panic"
    RANGE_BOUND = "range_bound"
    MOMENTUM_EXPANSION = "momentum_expansion"
    LIQUIDITY_VACUUM = "liquidity_vacuum"


@dataclass
class Regime:
    """A single regime classification."""
    label: RegimeLabel
    confidence: float  # 0.0 to 1.0
    timestamp: str = ""
    features: dict[str, float] = field(default_factory=dict)
    duration_bars: int = 0  # How long we've been in this regime

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "features": self.features,
            "duration_bars": self.duration_bars,
        }


@dataclass
class RegimeSegment:
    """A continuous period in the same regime."""
    label: RegimeLabel
    start_idx: int
    end_idx: int
    start_time: str = ""
    end_time: str = ""
    confidence: float = 0.0
    avg_return: float = 0.0
    volatility: float = 0.0
    max_drawdown: float = 0.0

    @property
    def duration_bars(self) -> int:
        return self.end_idx - self.start_idx


class RegimeDetector:
    """
    Detects market regimes from OHLCV data.

    Uses multiple signals:
    - Trend: ADX, price vs moving averages
    - Volatility: ATR, realized vol, Bollinger width
    - Momentum: rate of change, volume acceleration
    - Stress: volume spikes, correlation shifts, drawdown

    All computations are deterministic and side-effect-free.
    """

    def __init__(
        self,
        lookback: int = 100,
        volatility_window: int = 20,
        trend_window: int = 50,
    ) -> None:
        self.lookback = lookback
        self.volatility_window = volatility_window
        self.trend_window = trend_window

    def detect(self, data: pd.DataFrame) -> list[Regime]:
        """
        Detect regimes for each bar in the data.

        Args:
            data: DataFrame with 'open', 'high', 'low', 'close', 'volume' columns.

        Returns:
            List of Regime objects, one per bar.
        """
        if len(data) < self.lookback:
            return []

        regimes = []

        # Compute features
        features = self._compute_features(data)

        for i in range(self.lookback, len(data)):
            window = features.iloc[max(0, i - self.lookback):i]
            regime = self._classify(window, i, data)
            regimes.append(regime)

        # Compute durations
        regimes = self._compute_durations(regimes)

        return regimes

    def _compute_durations(self, regimes: list[Regime]) -> list[Regime]:
        """Compute how long each bar has been in its current regime."""
        if not regimes:
            return regimes

        # Walk backwards to find regime start
        for i in range(len(regimes) - 1, -1, -1):
            if i == 0:
                regimes[i].duration_bars = 0
            elif regimes[i].label == regimes[i - 1].label:
                regimes[i].duration_bars = regimes[i - 1].duration_bars + 1
            else:
                regimes[i].duration_bars = 0

        return regimes

    def detect_latest(self, data: pd.DataFrame) -> Regime:
        """Detect the current regime from the latest data."""
        regimes = self.detect(data)
        if not regimes:
            return Regime(label=RegimeLabel.RANGE_BOUND, confidence=0.0)
        return regimes[-1]

    def segment(self, data: pd.DataFrame) -> list[RegimeSegment]:
        """
        Segment data into contiguous regime periods.

        Returns:
            List of RegimeSegment objects.
        """
        regimes = self.detect(data)
        if not regimes:
            return []

        segments = []
        current_label = regimes[0].label
        start_idx = 0

        for i, regime in enumerate(regimes):
            if regime.label != current_label or i == len(regimes) - 1:
                segment = RegimeSegment(
                    label=current_label,
                    start_idx=start_idx,
                    end_idx=i,
                    confidence=np.mean([r.confidence for r in regimes[start_idx:i]]),
                )
                segments.append(segment)
                current_label = regime.label
                start_idx = i

        return segments

    def _compute_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Compute regime detection features."""
        features = pd.DataFrame(index=data.index)

        close = data["close"]
        high = data["high"]
        low = data["low"]
        volume = data["volume"]

        # Trend features
        sma_short = close.rolling(20).mean()
        sma_long = close.rolling(self.trend_window).mean()
        features["trend_strength"] = (sma_short - sma_long) / sma_long

        # ADX-like trend persistence
        features["adx_proxy"] = self._compute_adx_proxy(high, low, close)

        # Volatility features
        returns = close.pct_change()
        features["realized_vol"] = returns.rolling(self.volatility_window).std() * np.sqrt(365)

        # ATR
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        features["atr"] = tr.rolling(self.volatility_window).mean()
        features["atr_pct"] = features["atr"] / close

        # Bollinger bandwidth
        sma = close.rolling(20).mean()
        std = close.rolling(20).std()
        features["bb_width"] = (2 * std) / sma

        # Momentum
        features["roc_10"] = close.pct_change(10)
        features["roc_30"] = close.pct_change(30)

        # Volume features
        vol_sma = volume.rolling(20).mean()
        features["volume_ratio"] = volume / vol_sma
        features["volume_acceleration"] = features["volume_ratio"].diff(5)

        # Stress features
        features["max_drawdown_20"] = self._rolling_drawdown(close, 20)
        features["return_skew"] = returns.rolling(20).skew()

        # Range detection
        features["high_low_range"] = (high.rolling(20).max() - low.rolling(20).min()) / close

        return features.fillna(0)

    def _classify(self, window: pd.DataFrame, idx: int, data: pd.DataFrame) -> Regime:
        """Classify the current regime from a feature window."""
        if window.empty:
            return Regime(label=RegimeLabel.RANGE_BOUND, confidence=0.0)

        # Get latest feature values
        latest = window.iloc[-1]

        # Compute regime scores
        scores: dict[RegimeLabel, float] = {}

        # Trending: strong trend + high ADX
        trend_score = min(1.0, abs(latest.get("trend_strength", 0)) * 10)
        adx_score = min(1.0, latest.get("adx_proxy", 0) / 50)
        scores[RegimeLabel.TRENDING] = (trend_score + adx_score) / 2

        # Mean reverting: low trend + low ADX + negative autocorrelation
        mr_score = 1.0 - (trend_score + adx_score) / 2
        scores[RegimeLabel.MEAN_REVERTING] = mr_score * 0.7

        # High volatility: high realized vol + wide Bollinger
        vol_percentile = self._percentile_rank(window["realized_vol"], latest.get("realized_vol", 0))
        bb_percentile = self._percentile_rank(window["bb_width"], latest.get("bb_width", 0))
        scores[RegimeLabel.HIGH_VOLATILITY] = (vol_percentile + bb_percentile) / 2

        # Low volatility: low realized vol + narrow Bollinger
        scores[RegimeLabel.LOW_VOLATILITY] = 1.0 - (vol_percentile + bb_percentile) / 2

        # Panic: high volume + large drawdown + high skew
        vol_spike = min(1.0, latest.get("volume_ratio", 1) / 3)
        dd_score = min(1.0, abs(latest.get("max_drawdown_20", 0)) * 5)
        scores[RegimeLabel.PANIC] = (vol_spike + dd_score) / 2 * 0.8

        # Range-bound: low trend + low vol + moderate range
        range_score = (1.0 - trend_score) * (1.0 - vol_percentile)
        range_score *= min(1.0, latest.get("high_low_range", 0) * 20)
        scores[RegimeLabel.RANGE_BOUND] = range_score

        # Momentum expansion: high ROC + volume acceleration
        roc_score = min(1.0, abs(latest.get("roc_10", 0)) * 10)
        vol_acc = min(1.0, max(0, latest.get("volume_acceleration", 0)))
        scores[RegimeLabel.MOMENTUM_EXPANSION] = (roc_score + vol_acc) / 2

        # Liquidity vacuum: low volume + wide spread + high range
        liq_score = (1.0 - min(1.0, latest.get("volume_ratio", 1))) * bb_percentile
        scores[RegimeLabel.LIQUIDITY_VACUUM] = liq_score * 0.6

        # Select highest-scoring regime
        best_label = max(scores, key=scores.get)
        best_score = scores[best_label]

        # Confidence is the score difference between best and second-best
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[0] > 0:
            confidence = min(1.0, (sorted_scores[0] - sorted_scores[1]) / sorted_scores[0])
        else:
            confidence = 0.5

        timestamp = ""
        if "timestamp" in data.columns and idx < len(data):
            timestamp = str(data.iloc[idx].get("timestamp", ""))

        return Regime(
            label=best_label,
            confidence=confidence,
            timestamp=timestamp,
            features=latest.to_dict(),
        )

    @staticmethod
    def _compute_adx_proxy(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Compute ADX-like trend strength indicator."""
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        # Where plus_dm > minus_dm, keep plus_dm, else 0
        mask = plus_dm > minus_dm
        plus_dm = plus_dm * mask
        minus_dm = minus_dm * (~mask)

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()

        return adx.fillna(0)

    @staticmethod
    def _rolling_drawdown(series: pd.Series, window: int) -> pd.Series:
        """Compute rolling maximum drawdown."""
        rolling_max = series.rolling(window, min_periods=1).max()
        drawdown = (series - rolling_max) / rolling_max
        return drawdown

    @staticmethod
    def _percentile_rank(series: pd.Series, value: float) -> float:
        """Compute the percentile rank of a value within a series."""
        valid = series.dropna()
        if len(valid) == 0:
            return 0.5
        return float((valid <= value).sum()) / len(valid)
