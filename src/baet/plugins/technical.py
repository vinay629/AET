"""Technical indicator based scoring plugin."""

from __future__ import annotations

from typing import Any, Dict, Optional
import pandas as pd
import numpy as np

from baet.core.plugins import ScoringPlugin, PluginMetadata


class TechnicalIndicatorPlugin(ScoringPlugin):
    """Plugin that uses classical technical indicators for scoring."""

    metadata = PluginMetadata(
        name="technical_indicators",
        version="1.0.0",
        description="Scores based on RSI, MACD, and Bollinger Bands"
    )

    def calculate_score(self, data: pd.DataFrame) -> float:
        """
        Calculate a score based on technical indicators.

        Currently uses RSI to determine overbought (>70) or oversold (<30) conditions.
        """
        if len(data) < 30:
            return 0.0

        # Simple RSI scoring
        close = data['close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        latest_rsi = rsi.iloc[-1]

        # RSI score: -1.0 if > 70, 1.0 if < 30, scale in between
        if latest_rsi > 70:
            rsi_score = -((latest_rsi - 70) / 30)
        elif latest_rsi < 30:
            rsi_score = (30 - latest_rsi) / 30
        else:
            rsi_score = 0.0

        return float(np.clip(rsi_score, -1.0, 1.0))

    def learn(self, trade_outcome: Dict[str, Any]) -> None:
        """
        Evolve the plugin weight based on trade performance.

        If the plugin contributed to a losing trade, its influence is reduced.
        If it contributed to a winning trade, its influence is increased.
        """
        pnl = trade_outcome.get("pnl_pct", 0.0)
        self.performance_history.append(pnl)

        # Adjust weight based on performance
        if pnl < 0:
            self.weight *= 0.95  # Reduce weight on loss
        else:
            self.weight *= 1.02  # Increase weight on profit

        self.weight = np.clip(self.weight, 0.1, 2.0)
