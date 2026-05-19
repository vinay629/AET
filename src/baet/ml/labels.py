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
    """Configuration for triple barrier labeling."""
    take_profit: float = 0.02    # 2% profit target
    stop_loss: float = 0.01      # 1% stop loss
    timeout_bars: int = 20       # Max holding period in bars
    min_return: float = 0.0      # Minimum return threshold


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
    1. Upper barrier: entry_price * (1 + take_profit)
    2. Lower barrier: entry_price * (1 - stop_loss)
    3. Vertical barrier: t + timeout_bars

    The first barrier touched determines the label:
    - Upper → label = 1 (profit)
    - Lower → label = -1 (loss)
    - Vertical → label = sign(return) or 0 (timeout)

    This is superior to naive return prediction because it:
    - Accounts for asymmetric risk/reward
    - Handles transaction costs implicitly
    - Limits maximum holding period
    """

    def __init__(self, config: TripleBarrierConfig | None = None) -> None:
        self.config = config or TripleBarrierConfig()

    def label(
        self,
        prices: pd.Series,
        signals: pd.Series | None = None,
    ) -> pd.DataFrame:
        """
        Generate triple barrier labels.

        Args:
            prices: Price series (close prices).
            signals: Optional signal series (1 = enter long, -1 = enter short, 0 = no trade).
                     If None, labels every bar as a potential entry.

        Returns:
            DataFrame with columns: label, barrier, return_pct, holding_bars.
        """
        if signals is None:
            signals = pd.Series(1, index=prices.index)

        results = []

        for i in range(len(prices) - 1):
            if signals.iloc[i] == 0:
                continue

            entry_price = prices.iloc[i]
            direction = signals.iloc[i]  # 1 or -1

            # Set barriers
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
