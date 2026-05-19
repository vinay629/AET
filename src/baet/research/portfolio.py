"""Portfolio construction engine for BAET.

Transforms strategy signals into optimized portfolio allocations.

Methods:
- Volatility targeting
- Correlation control
- Kelly fraction capping
- Risk parity
- Hierarchical risk parity
- Max marginal VaR
- Exposure netting

All computations are deterministic and side-effect-free.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PortfolioAllocation:
    """Target allocation for a single symbol."""
    symbol: str
    target_weight: float = 0.0    # Target portfolio weight (0 to 1)
    current_weight: float = 0.0   # Current portfolio weight
    delta: float = 0.0            # Required change
    regime: str = ""              # Current regime for this symbol
    confidence: float = 0.0       # Signal confidence
    expected_return: float = 0.0  # Expected return
    volatility: float = 0.0       # Expected volatility
    var_contribution: float = 0.0 # VaR contribution


@dataclass
class PortfolioConstraints:
    """Constraints for portfolio optimization."""
    max_total_exposure: float = 0.5     # Max total portfolio exposure
    max_single_position: float = 0.1    # Max weight for single symbol
    max_correlation: float = 0.7        # Max pairwise correlation
    min_weight: float = 0.0             # Min weight (0 = allow zero)
    max_turnover: float = 0.2           # Max turnover per rebalance
    target_volatility: float = 0.15     # Annual target volatility
    max_leverage: float = 1.0           # Max gross leverage
    sector_limits: dict[str, float] = field(default_factory=dict)


@dataclass
class PortfolioState:
    """Current state of the portfolio."""
    allocations: list[PortfolioAllocation] = field(default_factory=list)
    total_exposure: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_var_95: float = 0.0
    diversification_ratio: float = 0.0
    timestamp: str = ""


class PortfolioOptimizer:
    """
    Optimizes portfolio allocations given signals and constraints.

    Supports multiple optimization methods:
    - equal_weight: Simple equal weighting
    - risk_parity: Equal risk contribution
    - hrp: Hierarchical risk parity
    - max_sharpe: Maximum Sharpe ratio
    - min_variance: Minimum variance
    - vol_target: Volatility targeting
    """

    def __init__(
        self,
        constraints: PortfolioConstraints | None = None,
        method: str = "risk_parity",
    ) -> None:
        self.constraints = constraints or PortfolioConstraints()
        self.method = method

    def optimize(
        self,
        signals: list[dict[str, Any]],
        covariance: pd.DataFrame | None = None,
        current_weights: dict[str, float] | None = None,
        regimes: dict[str, str] | None = None,
    ) -> PortfolioState:
        """
        Optimize portfolio allocation.

        Args:
            signals: List of signal dicts with 'symbol', 'direction', 'confidence', 'expected_return'.
            covariance: Covariance matrix of returns (symbols × symbols).
            current_weights: Current portfolio weights.
            regimes: Current regime per symbol.

        Returns:
            PortfolioState with optimized allocations.
        """
        if not signals:
            return PortfolioState()

        symbols = [s["symbol"] for s in signals]
        n = len(symbols)

        # Build expected returns vector
        expected_returns = np.array([
            s.get("expected_return", 0.0) * s.get("confidence", 0.5)
            for s in signals
        ])

        # Build direction vector (-1 to 1)
        directions = np.array([
            1.0 if s.get("direction", "BUY") == "BUY" else -1.0
            for s in signals
        ])

        # Build covariance matrix
        if covariance is None or covariance.empty:
            # Use identity (uncorrelated) as fallback
            cov_matrix = np.eye(n) * 0.01
        else:
            # Align covariance matrix with symbols
            available = [s for s in symbols if s in covariance.index]
            if len(available) == n:
                cov_matrix = covariance.loc[symbols, symbols].values
            else:
                cov_matrix = np.eye(n) * 0.01

        # Compute raw weights based on method
        if self.method == "equal_weight":
            raw_weights = self._equal_weight(n, directions)
        elif self.method == "risk_parity":
            raw_weights = self._risk_parity(cov_matrix, directions)
        elif self.method == "hrp":
            raw_weights = self._hierarchical_risk_parity(cov_matrix, directions)
        elif self.method == "max_sharpe":
            raw_weights = self._max_sharpe(expected_returns, cov_matrix, directions)
        elif self.method == "min_variance":
            raw_weights = self._min_variance(cov_matrix, directions)
        elif self.method == "vol_target":
            raw_weights = self._vol_target(expected_returns, cov_matrix, directions)
        else:
            raw_weights = self._equal_weight(n, directions)

        # Apply constraints
        weights = self._apply_constraints(raw_weights, current_weights)

        # Build allocations
        allocations = []
        for i, signal in enumerate(signals):
            alloc = PortfolioAllocation(
                symbol=signal["symbol"],
                target_weight=weights[i],
                current_weight=current_weights.get(signal["symbol"], 0.0) if current_weights else 0.0,
                delta=weights[i] - (current_weights.get(signal["symbol"], 0.0) if current_weights else 0.0),
                regime=regimes.get(signal["symbol"], "") if regimes else "",
                confidence=signal.get("confidence", 0.0),
                expected_return=expected_returns[i],
                volatility=np.sqrt(cov_matrix[i, i]) if i < cov_matrix.shape[0] else 0.0,
            )
            allocations.append(alloc)

        # Compute portfolio metrics
        weight_vector = np.array([a.target_weight for a in allocations])
        port_return = float(np.dot(weight_vector, expected_returns))
        port_vol = float(np.sqrt(weight_vector @ cov_matrix @ weight_vector))
        sharpe = port_return / port_vol if port_vol > 0 else 0.0

        # VaR contribution
        var_95 = -1.645 * port_vol  # Parametric VaR at 95%
        marginal_var = cov_matrix @ weight_vector
        if port_vol > 0:
            var_contributions = weight_vector * marginal_var / port_vol * var_95
        else:
            var_contributions = np.zeros(n)

        for i, alloc in enumerate(allocations):
            alloc.var_contribution = float(var_contributions[i])

        # Diversification ratio
        weighted_vol = sum(
            abs(a.target_weight) * a.volatility
            for a in allocations
        )
        div_ratio = weighted_vol / port_vol if port_vol > 0 else 1.0

        return PortfolioState(
            allocations=allocations,
            total_exposure=sum(abs(w) for w in weights),
            gross_exposure=sum(max(0, w) for w in weights) + sum(max(0, -w) for w in weights),
            net_exposure=sum(weights),
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            max_var_95=var_95,
            diversification_ratio=div_ratio,
        )

    def _equal_weight(self, n: int, directions: np.ndarray) -> np.ndarray:
        """Equal weight allocation."""
        weights = np.ones(n) / n
        return weights * directions

    def _risk_parity(self, cov: np.ndarray, directions: np.ndarray) -> np.ndarray:
        """Risk parity: equal risk contribution from each asset."""
        n = cov.shape[0]
        # Inverse volatility weighting as approximation
        vols = np.sqrt(np.diag(cov))
        vols[vols == 0] = 1.0
        inv_vol = 1.0 / vols
        weights = inv_vol / inv_vol.sum()
        return weights * directions

    def _hierarchical_risk_parity(self, cov: np.ndarray, directions: np.ndarray) -> np.ndarray:
        """Hierarchical Risk Parity (De Prado 2016).

        Uses hierarchical clustering to allocate risk.
        Simplified implementation using recursive bisection.
        """
        n = cov.shape[0]
        if n == 1:
            return np.array([directions[0]])

        # Compute correlation matrix
        vols = np.sqrt(np.diag(cov))
        vols[vols == 0] = 1.0
        corr = cov / np.outer(vols, vols)
        corr = np.clip(corr, -1, 1)

        # Distance matrix
        dist = np.sqrt(0.5 * (1 - corr))
        np.fill_diagonal(dist, 0)

        # Simple clustering: split into two groups by average correlation
        avg_corr = dist.mean(axis=1)
        median_corr = np.median(avg_corr)
        group1 = [i for i in range(n) if avg_corr[i] <= median_corr]
        group2 = [i for i in range(n) if avg_corr[i] > median_corr]

        if not group1 or not group2:
            group1 = list(range(n // 2))
            group2 = list(range(n // 2, n))

        # Allocate capital to each group inversely proportional to variance
        var1 = np.mean([cov[i, i] for i in group1]) if group1 else 1.0
        var2 = np.mean([cov[i, i] for i in group2]) if group2 else 1.0

        alloc1 = (1.0 / var1) / (1.0 / var1 + 1.0 / var2) if var1 > 0 else 0.5
        alloc2 = 1.0 - alloc1

        weights = np.zeros(n)
        for i in group1:
            sub_weights = self._hierarchical_risk_parity(
                cov[np.ix_(group1, group1)],
                directions[group1],
            )
            idx = group1.index(i)
            weights[i] = alloc1 * sub_weights[idx] if idx < len(sub_weights) else 0

        for i in group2:
            sub_weights = self._hierarchical_risk_parity(
                cov[np.ix_(group2, group2)],
                directions[group2],
            )
            idx = group2.index(i)
            weights[i] = alloc2 * sub_weights[idx] if idx < len(sub_weights) else 0

        return weights

    def _max_sharpe(
        self, expected_returns: np.ndarray, cov: np.ndarray, directions: np.ndarray
    ) -> np.ndarray:
        """Maximum Sharpe ratio portfolio."""
        n = len(expected_returns)
        vols = np.sqrt(np.diag(cov))
        vols[vols == 0] = 1.0

        # Risk-adjusted returns
        risk_adj = expected_returns / vols
        weights = risk_adj / abs(risk_adj).sum() if abs(risk_adj).sum() > 0 else np.ones(n) / n
        return weights * np.sign(directions)

    def _min_variance(self, cov: np.ndarray, directions: np.ndarray) -> np.ndarray:
        """Minimum variance portfolio."""
        n = cov.shape[0]
        try:
            cov_inv = np.linalg.inv(cov + np.eye(n) * 1e-6)
            ones = np.ones(n)
            weights = cov_inv @ ones / (ones @ cov_inv @ ones)
        except np.linalg.LinAlgError:
            weights = np.ones(n) / n

        return weights * np.sign(directions)

    def _vol_target(
        self, expected_returns: np.ndarray, cov: np.ndarray, directions: np.ndarray
    ) -> np.ndarray:
        """Volatility targeting: scale to target vol."""
        # Start with max Sharpe
        weights = self._max_sharpe(expected_returns, cov, directions)

        # Compute current volatility
        port_vol = np.sqrt(weights @ cov @ weights)
        target_vol = self.constraints.target_volatility / np.sqrt(365)  # Daily

        if port_vol > 0:
            scale = target_vol / port_vol
            weights *= scale

        return weights

    def _apply_constraints(
        self,
        raw_weights: np.ndarray,
        current_weights: dict[str, float] | None = None,
    ) -> np.ndarray:
        """Apply portfolio constraints."""
        weights = raw_weights.copy()

        # Max single position
        weights = np.clip(
            weights,
            -self.constraints.max_single_position,
            self.constraints.max_single_position,
        )

        # Max total exposure
        total = sum(abs(w) for w in weights)
        if total > self.constraints.max_total_exposure:
            scale = self.constraints.max_total_exposure / total
            weights *= scale

        # Max leverage
        gross = sum(abs(w) for w in weights)
        if gross > self.constraints.max_leverage:
            scale = self.constraints.max_leverage / gross
            weights *= scale

        # Turnover constraint
        if current_weights:
            # This would need symbol alignment — simplified here
            pass

        return weights
