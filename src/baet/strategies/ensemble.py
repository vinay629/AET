"""Ensemble decision layer for combining multiple strategy signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd

if TYPE_CHECKING:
    from baet.risk.engine import RiskEngine

from baet.core.models import RegimeLabel, StrategyMetadata
from baet.strategies.contracts import SIGNAL_COLUMNS


@dataclass
class StrategyWeight:
    """Weight configuration for a strategy in the ensemble."""

    strategy_name: str
    weight: float
    metadata: Optional[StrategyMetadata] = None


@dataclass
class EnsembleConfig:
    """Configuration for ensemble decision making."""

    name: str
    strategy_weights: List[StrategyWeight] = field(default_factory=list)
    regime_weights: Dict[RegimeLabel, Dict[str, float]] = field(default_factory=dict)
    default_weight: float = 1.0

    def get_weight(self, strategy_name: str, regime: Optional[RegimeLabel] = None) -> float:
        """Get weight for a strategy, optionally adjusted by regime."""
        # Start with default or specific strategy weight
        base_weight = self.default_weight
        for sw in self.strategy_weights:
            if sw.strategy_name == strategy_name:
                base_weight = sw.weight
                break

        # Adjust by regime if applicable
        if regime and regime in self.regime_weights:
            regime_dict = self.regime_weights[regime]
            if strategy_name in regime_dict:
                return regime_dict[strategy_name]

        return base_weight


class StaticEnsemble:
    """Static ensemble that combines multiple strategy signals into one decision stream."""

    def __init__(self, config: EnsembleConfig, risk_engine: Optional["RiskEngine"] = None):
        self.config = config
        self.risk_engine = risk_engine  # NEW: Optional RiskEngine

    def combine_signals(
        self, strategy_signals: Dict[str, pd.DataFrame], regime_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Combine signals from multiple strategies into a single decision stream.

        Args:
            strategy_signals: Dict mapping strategy_name to its signals DataFrame
            regime_data: Optional DataFrame with [timestamp, regime] for regime-aware weighting

        Returns:
            DataFrame with combined signals as a single decision stream
        """
        if not strategy_signals:
            return pd.DataFrame(columns=SIGNAL_COLUMNS)

        # Ensure all signal DataFrames have required columns
        for name, signals in strategy_signals.items():
            missing_cols = set(SIGNAL_COLUMNS) - set(signals.columns)
            if missing_cols:
                raise ValueError(f"Strategy {name} missing columns: {missing_cols}")

        # Merge regime data if provided
        regime_map = {}
        if regime_data is not None and "regime" in regime_data.columns:
            regime_map = dict(zip(regime_data["timestamp"], regime_data["regime"], strict=False))

        # Combine all signals with weights
        all_signals = []

        for strategy_name, signals in strategy_signals.items():
            weighted_signals = signals.copy()

            # Apply weight to confidence
            for idx, row in weighted_signals.iterrows():
                regime = regime_map.get(row["timestamp"])
                weight = self.config.get_weight(strategy_name, regime)
                weighted_signals.at[idx, "confidence"] = row["confidence"] * weight
                weighted_signals.at[idx, "reason"] = f"[{self.config.name}] {row['reason']}"

            all_signals.append(weighted_signals)

        # Concatenate all signals
        if not all_signals:
            return pd.DataFrame(columns=SIGNAL_COLUMNS)

        combined = pd.concat(all_signals, ignore_index=True)

        # Sort by timestamp
        combined = combined.sort_values("timestamp").reset_index(drop=True)

        return combined

    def make_decisions(self, combined_signals: pd.DataFrame) -> pd.DataFrame:
        """
        Make final trading decisions from combined signals.

        For each timestamp, aggregate signals and produce one decision.
        Uses confidence-weighted voting.
        All signals pass through risk checks if risk_engine is provided.
        """
        if combined_signals.empty:
            return pd.DataFrame(columns=SIGNAL_COLUMNS)

        # NEW: Run risk checks if risk engine is available
        if self.risk_engine:
            from baet.risk.integration import evaluate_combined_signals

            combined_signals = evaluate_combined_signals(
                self.risk_engine, combined_signals, regime=None
            )
            if combined_signals.empty:
                return pd.DataFrame(columns=SIGNAL_COLUMNS)

        decisions = []

        # Group by timestamp, symbol, timeframe
        grouped = combined_signals.groupby(["timestamp", "symbol", "timeframe"])

        for (timestamp, symbol, timeframe), group in grouped:
            # Aggregate actions by confidence-weighted voting
            buy_conf = group[group["action"] == "BUY"]["confidence"].sum()
            sell_conf = group[group["action"] == "SELL"]["confidence"].sum()
            hold_conf = group[group["action"] == "HOLD"]["confidence"].sum()

            # Determine final action
            confidences = {"BUY": buy_conf, "SELL": sell_conf, "HOLD": hold_conf}
            final_action = max(confidences, key=confidences.get)
            final_confidence = confidences[final_action]

            # Calculate target position (average of weighted positions)
            valid_positions = group[group["target_position"].notna()]
            if not valid_positions.empty:
                weighted_positions = (
                    valid_positions["target_position"] * valid_positions["confidence"]
                )
                target_position = weighted_positions.sum() / valid_positions["confidence"].sum()
            else:
                target_position = 0.0

            # Calculate size hint (average of weighted hints)
            valid_hints = group[group["size_hint"].notna()]
            if not valid_hints.empty:
                weighted_hints = valid_hints["size_hint"] * valid_hints["confidence"]
                size_hint = weighted_hints.sum() / valid_hints["confidence"].sum()
            else:
                size_hint = None

            # Combine reasons
            reasons = group["reason"].tolist()
            combined_reason = f"Ensemble decision: {', '.join(reasons[:3])}"  # Limit to first 3

            decision = {
                "timestamp": timestamp,
                "symbol": symbol,
                "timeframe": timeframe,
                "action": final_action,
                "target_position": target_position,
                "confidence": final_confidence,
                "size_hint": size_hint,
                "strategy_name": self.config.name,
                "reason": combined_reason,
            }

            decisions.append(decision)

        result = pd.DataFrame(decisions)
        return result
