"""Labeling engine for financial ML.

Supports:
1. Triple Barrier Method (De Prado 2018): take-profit, stop-loss, timeout
2. Meta-labeling: primary model predicts direction, secondary model predicts whether to trade

These are far superior to naive next-return prediction because they:
- Account for transaction costs via profit taking
- Limit losses via stop-loss
- Handle holding period via timeout
- Separate direction prediction from sizing (meta-labeling)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BarrierType(StrEnum):
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TIMEOUT = "timeout"


@dataclass
class TripleBarrierConfig:
    """Configuration for triple barrier labeling.

    Barriers can be defined as static percentages or dynamically scaled
    by a volatility measure (ATR or rolling std). When `atr_window` is set,
    barriers are computed as:
        upper = entry + atr_multiplier * ATR(t)
        lower = entry - atr_multiplier * ATR(t)
    This ensures barriers tighten in low-vol and widen in high-vol,
    preventing "Sideways" from absorbing 95% of samples.
    """
    take_profit: float = 0.02    # 2% profit target (static fallback)
    stop_loss: float = 0.01      # 1% stop loss (static fallback)
    timeout_bars: int = 20       # Max holding period in bars
    min_return: float = 0.0      # Minimum return threshold for timeout label
    atr_window: int | None = None  # ATR window for dynamic barriers (None = static)
    atr_multiplier: float = 2.0  # ATR multiple for barrier width
    vol_lookback: int = 20       # Rolling vol lookback when ATR not available


@dataclass
class BarrierResult:
    """Result of triple barrier evaluation."""
    label: int                    # 1 = profit, -1 = loss, 0 = timeout/neutral
    barrier_touched: BarrierType  # Which barrier was hit first
    return_pct: float             # Actual return when barrier hit
    holding_bars: int             # Number of bars held


class TripleBarrierLabeler:
    """
    Triple Barrier Method (De Prado 2018).

    For each entry at time t, three barriers are set:
    1. Upper barrier: entry_price + direction * volatility * multiplier
    2. Lower barrier: entry_price - direction * volatility * multiplier
    3. Vertical barrier: t + timeout_bars

    The first barrier touched determines the label:
    - Upper → label = 1 (profit)
    - Lower → label = -1 (loss)
    - Vertical → label = sign(return) or 0 (timeout / "Sideways")

    Barriers can be static percentages or dynamically scaled by ATR/rolling vol.
    Dynamic barriers are critical for crypto: they tighten during low-volatility
    compression (preventing "Sideways" from dominating) and widen during
    high-volatility trends (avoiding premature stop-outs).

    This is superior to naive return prediction because it:
    - Accounts for asymmetric risk/reward
    - Handles transaction costs implicitly
    - Limits maximum holding period
    - Adapts to current market volatility
    """

    def __init__(self, config: TripleBarrierConfig | None = None) -> None:
        self.config = config or TripleBarrierConfig()

    def label(
        self,
        prices: pd.Series,
        signals: pd.Series | None = None,
        high: pd.Series | None = None,
        low: pd.Series | None = None,
        atr: pd.Series | None = None,
    ) -> pd.DataFrame:
        """
        Generate triple barrier labels.

        Args:
            prices: Price series (close prices).
            signals: Optional signal series (1 = enter long, -1 = enter short, 0 = no trade).
                     If None, labels every bar as a potential entry.
            high: Optional high price series (for ATR computation).
            low: Optional low price series (for ATR computation).
            atr: Optional pre-computed ATR series. If None and `atr_window` is set,
                 ATR will be computed from high/low/close.

        Returns:
            DataFrame with columns: label, barrier, return_pct, holding_bars.
        """
        if signals is None:
            signals = pd.Series(1, index=prices.index)

        # Compute volatility series for dynamic barriers
        vol = self._compute_volatility(prices, high, low, atr)

        results = []

        for i in range(len(prices) - 1):
            if signals.iloc[i] == 0:
                continue

            entry_price = prices.iloc[i]
            direction = signals.iloc[i]  # 1 or -1

            # Set barriers — dynamic if vol is available, static otherwise
            if vol is not None and not pd.isna(vol.iloc[i]) and vol.iloc[i] > 0:
                upper = entry_price + direction * vol.iloc[i] * self.config.atr_multiplier
                lower = entry_price - direction * vol.iloc[i] * self.config.atr_multiplier
            else:
                if direction > 0:
                    upper = entry_price * (1 + self.config.take_profit)
                    lower = entry_price * (1 - self.config.stop_loss)
                else:
                    upper = entry_price * (1 + self.config.stop_loss)
                    lower = entry_price * (1 - self.config.take_profit)

            # Find first barrier touch
            max_bars = min(self.config.timeout_bars, len(prices) - i - 1)
            result = BarrierResult(
                label=0,
                barrier_touched=BarrierType.TIMEOUT,
                return_pct=0.0,
                holding_bars=max_bars,
            )

            for j in range(1, max_bars + 1):
                future_price = prices.iloc[i + j]

                if direction > 0:
                    if future_price >= upper:
                        result = BarrierResult(
                            label=1,
                            barrier_touched=BarrierType.TAKE_PROFIT,
                            return_pct=(future_price - entry_price) / entry_price,
                            holding_bars=j,
                        )
                        break
                    elif future_price <= lower:
                        result = BarrierResult(
                            label=-1,
                            barrier_touched=BarrierType.STOP_LOSS,
                            return_pct=(future_price - entry_price) / entry_price,
                            holding_bars=j,
                        )
                        break
                else:
                    if future_price <= lower:
                        result = BarrierResult(
                            label=1,
                            barrier_touched=BarrierType.TAKE_PROFIT,
                            return_pct=(entry_price - future_price) / entry_price,
                            holding_bars=j,
                        )
                        break
                    elif future_price >= upper:
                        result = BarrierResult(
                            label=-1,
                            barrier_touched=BarrierType.STOP_LOSS,
                            return_pct=(entry_price - future_price) / entry_price,
                            holding_bars=j,
                        )
                        break

            # If timeout, label based on return direction
            if result.barrier_touched == BarrierType.TIMEOUT:
                final_return = (prices.iloc[i + max_bars] - entry_price) / entry_price
                if direction > 0:
                    result.return_pct = final_return
                    result.label = 1 if final_return > self.config.min_return else (-1 if final_return < -self.config.min_return else 0)
                else:
                    result.return_pct = -final_return
                    result.label = 1 if -final_return > self.config.min_return else (-1 if -final_return < -self.config.min_return else 0)

            results.append({
                "entry_idx": i,
                "label": result.label,
                "barrier": result.barrier_touched.value,
                "return_pct": result.return_pct,
                "holding_bars": result.holding_bars,
            })

        return pd.DataFrame(results)

    def _compute_volatility(
        self,
        prices: pd.Series,
        high: pd.Series | None = None,
        low: pd.Series | None = None,
        atr: pd.Series | None = None,
    ) -> pd.Series | None:
        """Compute per-bar volatility for dynamic barrier scaling.

        Priority:
        1. Use pre-computed ATR if provided.
        2. Compute ATR from high/low/close if `atr_window` is set.
        3. Fall back to rolling std of returns.
        4. Return None if no volatility can be computed (static barriers).
        """
        if self.config.atr_window is None:
            return None

        if atr is not None:
            return atr

        if high is not None and low is not None:
            # Compute ATR using the standard formula
            prev_close = prices.shift(1)
            tr = pd.concat([
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ], axis=1).max(axis=1)
            return tr.rolling(self.config.atr_window, min_periods=1).mean()

        # Fallback: rolling std of returns as volatility proxy
        returns = prices.pct_change().abs()
        return returns.rolling(self.config.vol_lookback, min_periods=1).std() * prices


class MetaLabeler:
    """
    Meta-labeling (De Prado 2018).

    Two-model approach:
    1. Primary model: predicts direction (up/down)
    2. Meta model: predicts whether to take the trade (based on primary's prediction)

    This separates:
    - Direction prediction (primary)
    - Sizing / confidence (meta)

    The meta model learns when the primary model is likely to be correct.
    """

    def __init__(
        self,
        primary_threshold: float = 0.5,
    ) -> None:
        self.primary_threshold = primary_threshold

    def create_meta_labels(
        self,
        primary_predictions: pd.Series,
        actual_returns: pd.Series,
    ) -> pd.Series:
        """
        Create meta labels from primary model predictions.

        Meta label = 1 if primary prediction was correct (should trade)
        Meta label = 0 if primary prediction was wrong (should not trade)

        Args:
            primary_predictions: Primary model's predicted direction (-1 to 1).
            actual_returns: Actual forward returns.

        Returns:
            Meta labels (1 = correct, 0 = incorrect).
        """
        # Primary prediction correct if sign matches actual return
        correct = (primary_predictions * actual_returns) > 0
        meta_labels = correct.astype(int)
        return meta_labels

    def compute_primary_accuracy(
        self,
        primary_predictions: pd.Series,
        actual_returns: pd.Series,
    ) -> dict[str, float]:
        """Compute primary model accuracy statistics."""
        correct = (primary_predictions * actual_returns) > 0
        n = len(correct)

        if n == 0:
            return {"accuracy": 0.0, "n": 0}

        return {
            "accuracy": float(correct.sum() / n),
            "n": n,
            "correct": int(correct.sum()),
            "incorrect": int((~correct).sum()),
            "avg_return_when_correct": float(actual_returns[correct].mean()) if correct.any() else 0,
            "avg_return_when_wrong": float(actual_returns[~correct].mean()) if (~correct).any() else 0,
        }
