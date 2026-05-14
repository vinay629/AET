"""Scout engine for ratio-based trading decisions.

Inspired by: https://github.com/ccxt/binance-trade-bot

The scout algorithm works by:
1. Tracking price ratios between all coin pairs over time
2. Comparing current ratios to historical averages
3. When a ratio diverges beyond a threshold (scout_multiplier), signal a trade
4. Trade the "strong" coin for the "weak" coin, expecting reversion
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from baet.database.manager import DatabaseManager
from baet.database.models import Coin, Pair

logger = logging.getLogger(__name__)


@dataclass
class ScoutObservation:
    """A single scout observation for a coin pair."""
    from_coin: str
    to_coin: str
    current_ratio: float
    target_ratio: float
    price_from: float
    price_to: float
    deviation_pct: float  # Percentage deviation from target


@dataclass
class ScoutDecision:
    """A trading decision from the scout algorithm."""
    action: str  # "BUY", "SELL", or "HOLD"
    from_coin: str
    to_coin: str
    confidence: float  # 0.0 to 1.0
    reason: str
    observations: List[ScoutObservation] = field(default_factory=list)


class ScoutEngine:
    """
    Scout engine that monitors coin pair ratios and generates trading signals.

    The core idea: coins oscillate relative to each other. When one spikes
    relative to another, trade the strong coin for the weak one, expecting
    the ratio to revert.
    """

    def __init__(
        self,
        db: DatabaseManager,
        scout_multiplier: float = 5.0,
        scout_sleep_time: int = 5,
        bridge_symbol: str = "USDT",
    ):
        self.db = db
        self.scout_multiplier = scout_multiplier
        self.scout_sleep_time = scout_sleep_time
        self.bridge_symbol = bridge_symbol
        self._price_cache: Dict[str, float] = {}

    def update_prices(self, prices: Dict[str, float]) -> None:
        """Update the price cache with latest market data."""
        self._price_cache.update(prices)

    def get_ticker_price(self, symbol: str) -> Optional[float]:
        """Get the cached ticker price for a symbol."""
        return self._price_cache.get(symbol)

    def scout_all_pairs(self, coins: List[Coin]) -> List[ScoutDecision]:
        """
        Scout all coin pairs and return trading decisions.

        For each pair, compares the current ratio to the historical ratio
        and signals a trade if the deviation exceeds the threshold.
        """
        decisions = []

        for from_coin in coins:
            for to_coin in coins:
                if from_coin == to_coin:
                    continue

                pair = self.db.get_pair(from_coin, to_coin)
                if pair is None or not pair.enabled:
                    continue

                decision = self._scout_pair(pair)
                if decision is not None:
                    decisions.append(decision)

        return decisions

    def _scout_pair(self, pair: Pair) -> Optional[ScoutDecision]:
        """Scout a single pair and return a decision if there's an opportunity."""
        from_symbol = pair.from_coin.symbol
        to_symbol = pair.to_coin.symbol

        # Get current prices via bridge
        price_from = self._get_bridge_price(from_symbol)
        price_to = self._get_bridge_price(to_symbol)

        if price_from is None or price_to is None or price_to == 0:
            return None

        # Calculate current ratio
        current_ratio = price_from / price_to

        # Get historical target ratio from database
        target_ratio = pair.ratio
        if target_ratio == 0:
            # No history yet, initialize and skip
            self._update_pair_ratio(pair, current_ratio)
            return None

        # Calculate deviation
        deviation = (current_ratio - target_ratio) / target_ratio
        deviation_pct = deviation * 100

        # Log scout observation
        self.db.log_scout(pair, target_ratio, price_from, price_to)

        # Check if deviation exceeds threshold
        threshold = self.scout_multiplier * 0.001  # Convert multiplier to ratio

        if abs(deviation) > threshold:
            if deviation > 0:
                # From coin is strong relative to to_coin
                # SELL from_coin, BUY to_coin
                return ScoutDecision(
                    action="SELL",
                    from_coin=from_symbol,
                    to_coin=to_symbol,
                    confidence=min(abs(deviation) / threshold, 1.0),
                    reason=(
                        f"{from_symbol} is {deviation_pct:.2f}% above "
                        f"historical ratio vs {to_symbol}. "
                        f"Expected reversion."
                    ),
                    observations=[
                        ScoutObservation(
                            from_coin=from_symbol,
                            to_coin=to_symbol,
                            current_ratio=current_ratio,
                            target_ratio=target_ratio,
                            price_from=price_from,
                            price_to=price_to,
                            deviation_pct=deviation_pct,
                        )
                    ],
                )
            else:
                # To coin is strong relative to from_coin
                # BUY from_coin, SELL to_coin
                return ScoutDecision(
                    action="BUY",
                    from_coin=from_symbol,
                    to_coin=to_symbol,
                    confidence=min(abs(deviation) / threshold, 1.0),
                    reason=(
                        f"{to_symbol} is {abs(deviation_pct):.2f}% above "
                        f"historical ratio vs {from_symbol}. "
                        f"Expected reversion."
                    ),
                    observations=[
                        ScoutObservation(
                            from_coin=from_symbol,
                            to_coin=to_symbol,
                            current_ratio=current_ratio,
                            target_ratio=target_ratio,
                            price_from=price_from,
                            price_to=price_to,
                            deviation_pct=deviation_pct,
                        )
                    ],
                )

        return None

    def _get_bridge_price(self, coin_symbol: str) -> Optional[float]:
        """Get the price of a coin in terms of the bridge currency."""
        if coin_symbol == self.bridge_symbol:
            return 1.0
        pair_symbol = coin_symbol + self.bridge_symbol
        return self.get_ticker_price(pair_symbol)

    def _update_pair_ratio(self, pair: Pair, ratio: float) -> None:
        """Update the historical ratio for a pair."""
        pair.ratio = ratio

    def get_recommended_trade(
        self, coins: List[Coin], current_coin: Optional[Coin] = None
    ) -> Optional[ScoutDecision]:
        """
        Get the single best trade recommendation.

        Filters decisions to only include trades from the current coin,
        and returns the one with the highest confidence.
        """
        all_decisions = self.scout_all_pairs(coins)

        if current_coin is not None:
            # Only consider trades from the current coin
            all_decisions = [
                d for d in all_decisions if d.from_coin == current_coin.symbol
            ]

        if not all_decisions:
            return None

        # Return the highest confidence decision
        return max(all_decisions, key=lambda d: d.confidence)
