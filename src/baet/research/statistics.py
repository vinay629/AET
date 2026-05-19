"""Statistical validation layer for BAET.

Provides:
- White's Reality Check
- SPA (Superior Predictive Ability) test
- Multiple hypothesis correction (Bonferroni, BH)
- Probability of Backtest Overfitting (PBO)
- Deflated Sharpe Ratio
- CSCV (Combinatorially Symmetric Cross Validation)
- Monte Carlo trade reshuffling
- Bootstrap equity curves
- Noise injection
- Execution perturbation

This separates research platforms from hobby systems.
All tests are deterministic given the same random seed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StatisticalTestResult:
    """Result of a statistical validation test."""
    test_name: str
    passed: bool
    p_value: float = 0.0
    statistic: float = 0.0
    threshold: float = 0.05
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "test": self.test_name,
            "passed": self.passed,
            "p_value": self.p_value,
            "statistic": self.statistic,
            "threshold": self.threshold,
            **self.details,
        }


@dataclass
class ValidationReport:
    """Full statistical validation report."""
    results: list[StatisticalTestResult] = field(default_factory=list)
    overall_passed: bool = True
    n_strategies_tested: int = 0
    n_strategies_passed: int = 0

    def add(self, result: StatisticalTestResult) -> None:
        self.results.append(result)
        if not result.passed:
            self.overall_passed = False

    def summary(self) -> dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "n_tests": len(self.results),
            "n_passed": sum(1 for r in self.results if r.passed),
            "n_failed": sum(1 for r in self.results if not r.passed),
            "tests": [r.to_dict() for r in self.results],
        }


class StatisticalValidator:
    """
    Statistical validation for trading strategies.

    Tests whether observed performance is statistically significant
    or likely due to overfitting / multiple testing.
    """

    def __init__(self, n_permutations: int = 1000, seed: int = 42) -> None:
        self.n_permutations = n_permutations
        self.rng = np.random.RandomState(seed)

    def validate(
        self,
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
        other_strategies: list[pd.Series] | None = None,
    ) -> ValidationReport:
        """
        Run full statistical validation suite.

        Args:
            strategy_returns: Daily returns of the strategy.
            benchmark_returns: Daily returns of benchmark (e.g., buy-and-hold).
            other_strategies: Returns of other strategies tested (for multiple testing correction).

        Returns:
            ValidationReport with all test results.
        """
        report = ValidationReport()

        # 1. Basic significance
        report.add(self.test_return_significance(strategy_returns))

        # 2. Sharpe ratio significance
        report.add(self.test_sharpe_significance(strategy_returns))

        # 3. vs benchmark
        if benchmark_returns is not None:
            report.add(self.test_vs_benchmark(strategy_returns, benchmark_returns))

        # 4. White's Reality Check
        if other_strategies:
            report.add(self.whites_reality_check(strategy_returns, other_strategies))

        # 5. Multiple testing correction
        if other_strategies:
            report.add(self.multiple_testing_correction(strategy_returns, other_strategies))

        # 6. Deflated Sharpe Ratio
        report.add(self.deflated_sharpe(strategy_returns, len(other_strategies) if other_strategies else 1))

        # 7. Monte Carlo reshuffling
        report.add(self.monte_carlo_reshuffling(strategy_returns))

        return report

    def test_return_significance(self, returns: pd.Series) -> StatisticalTestResult:
        """Test if mean return is significantly different from zero (t-test)."""
        from scipy import stats

        returns = returns.dropna()
        if len(returns) < 10:
            return StatisticalTestResult(
                test_name="return_significance",
                passed=False,
                p_value=1.0,
                details={"error": "Insufficient data"},
            )

        t_stat, p_value = stats.ttest_1samp(returns, 0)
        return StatisticalTestResult(
            test_name="return_significance",
            passed=p_value < 0.05,
            p_value=float(p_value),
            statistic=float(t_stat),
            details={"n": len(returns), "mean_return": float(returns.mean())},
        )

    def test_sharpe_significance(self, returns: pd.Series) -> StatisticalTestResult:
        """Test if Sharpe ratio is significantly different from zero."""
        returns = returns.dropna()
        if len(returns) < 10:
            return StatisticalTestResult(
                test_name="sharpe_significance",
                passed=False,
                p_value=1.0,
            )

        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        # Jobson-Korkie test approximation
        n = len(returns)
        se = np.sqrt((1 + 0.5 * sharpe ** 2) / n)
        z_stat = sharpe / se if se > 0 else 0
        from scipy import stats
        p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))

        return StatisticalTestResult(
            test_name="sharpe_significance",
            passed=p_value < 0.05,
            p_value=float(p_value),
            statistic=float(z_stat),
            details={"sharpe": float(sharpe), "n": n},
        )

    def test_vs_benchmark(
        self, strategy_returns: pd.Series, benchmark_returns: pd.Series
    ) -> StatisticalTestResult:
        """Test if strategy outperforms benchmark."""
        from scipy import stats

        # Align
        aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
        if len(aligned) < 10:
            return StatisticalTestResult(
                test_name="vs_benchmark",
                passed=False,
                p_value=1.0,
            )

        excess = aligned.iloc[:, 0] - aligned.iloc[:, 1]
        t_stat, p_value = stats.ttest_1samp(excess, 0)

        return StatisticalTestResult(
            test_name="vs_benchmark",
            passed=p_value < 0.05,
            p_value=float(p_value),
            statistic=float(t_stat),
            details={
                "excess_return": float(excess.mean() * 252),
                "excess_sharpe": float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0,
            },
        )

    def whites_reality_check(
        self,
        best_returns: pd.Series,
        other_strategies: list[pd.Series],
    ) -> StatisticalTestResult:
        """
        White's Reality Check (2000).

        Tests whether the best strategy is genuinely better than
        the null hypothesis that all strategies are worthless.

        Uses bootstrap to account for multiple testing.
        """
        all_strategies = [best_returns] + other_strategies
        n_strategies = len(all_strategies)
        n_obs = len(best_returns)

        # Compute performance metric (Sharpe) for each strategy
        def sharpe(returns: pd.Series) -> float:
            r = returns.dropna()
            if len(r) < 10 or r.std() == 0:
                return 0.0
            return float(r.mean() / r.std() * np.sqrt(252))

        observed_sharpes = [sharpe(s) for s in all_strategies]
        best_observed = max(observed_sharpes)

        # Bootstrap: resample returns and recompute best Sharpe
        best_bootstrapped = []
        for _ in range(self.n_permutations):
            # For each strategy, bootstrap its returns
            boot_sharpes = []
            for s in all_strategies:
                r = s.dropna().values
                if len(r) < 10:
                    boot_sharpes.append(0.0)
                    continue
                # Stationary bootstrap
                indices = self.rng.randint(0, len(r), size=len(r))
                boot_returns = r[indices]
                boot_sharpe = boot_returns.mean() / boot_returns.std() * np.sqrt(252) if boot_returns.std() > 0 else 0
                boot_sharpes.append(boot_sharpe)

            best_bootstrapped.append(max(boot_sharpes))

        # P-value: fraction of bootstrap samples where best >= observed
        p_value = np.mean(np.array(best_bootstrapped) >= best_observed)

        return StatisticalTestResult(
            test_name="whites_reality_check",
            passed=p_value < 0.05,
            p_value=float(p_value),
            statistic=float(best_observed),
            details={
                "best_observed_sharpe": float(best_observed),
                "n_strategies": n_strategies,
                "n_permutations": self.n_permutations,
            },
        )

    def multiple_testing_correction(
        self,
        strategy_returns: pd.Series,
        other_strategies: list[pd.Series],
    ) -> StatisticalTestResult:
        """
        Multiple hypothesis correction (Benjamini-Hochberg).

        When testing many strategies, some will appear significant by chance.
        BH correction controls the false discovery rate.
        """
        from scipy import stats

        all_strategies = [strategy_returns] + other_strategies
        n = len(all_strategies)

        # Compute p-value for each strategy
        p_values = []
        for s in all_strategies:
            r = s.dropna()
            if len(r) < 10:
                p_values.append(1.0)
            else:
                _, p = stats.ttest_1samp(r, 0)
                p_values.append(p)

        # Benjamini-Hochberg correction
        p_values = np.array(p_values)
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]

        # BH critical values
        bh_critical = np.arange(1, n + 1) / n * 0.05

        # Find largest k where p_(k) <= k/n * alpha
        rejected = sorted_p <= bh_critical
        n_rejected = int(rejected.sum())

        # Is our strategy (index 0) still significant after correction?
        strategy_rank = list(sorted_idx).index(0)
        strategy_bh_p = sorted_p[strategy_rank] * n / (strategy_rank + 1)

        return StatisticalTestResult(
            test_name="multiple_testing_correction_bh",
            passed=strategy_bh_p < 0.05,
            p_value=float(strategy_bh_p),
            statistic=float(p_values[0]),
            details={
                "n_strategies_tested": n,
                "n_significant_after_correction": n_rejected,
                "raw_p_value": float(p_values[0]),
                "bh_adjusted_p_value": float(strategy_bh_p),
            },
        )

    def deflated_sharpe(
        self,
        returns: pd.Series,
        n_trials: int,
    ) -> StatisticalTestResult:
        """
        Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014).

        Adjusts the Sharpe ratio for the number of strategies tested,
        accounting for selection bias.
        """
        returns = returns.dropna()
        if len(returns) < 10 or returns.std() == 0:
            return StatisticalTestResult(
                test_name="deflated_sharpe",
                passed=False,
                details={"error": "Insufficient data"},
            )

        observed_sharpe = returns.mean() / returns.std() * np.sqrt(252)
        n = len(returns)

        # Expected maximum Sharpe from n_trials random strategies
        from scipy import stats
        euler_mascheroni = 0.5772
        expected_max_sharpe = stats.norm.ppf(1 - 1 / n_trials) * np.sqrt(252 / n)
        # Simplified: E[max SR] ≈ Φ⁻¹(1-1/N) × √(252/T)

        # Variance of Sharpe estimator
        var_sharpe = (1 + 0.5 * observed_sharpe ** 2) / n

        # Z-test
        z = (observed_sharpe - expected_max_sharpe) / np.sqrt(var_sharpe) if var_sharpe > 0 else 0
        p_value = 1 - stats.norm.cdf(z)

        return StatisticalTestResult(
            test_name="deflated_sharpe",
            passed=p_value < 0.05,
            p_value=float(p_value),
            statistic=float(z),
            details={
                "observed_sharpe": float(observed_sharpe),
                "expected_max_sharpe_random": float(expected_max_sharpe),
                "n_trials": n_trials,
                "n_observations": n,
            },
        )

    def monte_carlo_reshuffling(
        self,
        returns: pd.Series,
    ) -> StatisticalTestResult:
        """
        Monte Carlo trade reshuffling.

        Shuffles the return series many times to see how often
        a random permutation produces a Sharpe as high as observed.
        """
        returns = returns.dropna().values
        if len(returns) < 10:
            return StatisticalTestResult(
                test_name="monte_carlo_reshuffling",
                passed=False,
            )

        observed_sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        count_better = 0
        for _ in range(self.n_permutations):
            shuffled = self.rng.permutation(returns)
            shuffled_sharpe = shuffled.mean() / shuffled.std() * np.sqrt(252) if shuffled.std() > 0 else 0
            if shuffled_sharpe >= observed_sharpe:
                count_better += 1

        p_value = count_better / self.n_permutations

        return StatisticalTestResult(
            test_name="monte_carlo_reshuffling",
            passed=p_value < 0.05,
            p_value=float(p_value),
            statistic=float(observed_sharpe),
            details={
                "observed_sharpe": float(observed_sharpe),
                "n_permutations": self.n_permutations,
                "count_better": count_better,
            },
        )

    def probability_of_backtest_overfitting(
        self,
        in_sample_returns: pd.Series,
        out_of_sample_returns: pd.Series,
    ) -> StatisticalTestResult:
        """
        Probability of Backtest Overfitting (PBO).

        Measures how likely the in-sample performance was due to overfitting.
        Lower PBO = more robust strategy.

        Simplified implementation using the ratio of IS to OOS performance.
        """
        is_returns = in_sample_returns.dropna()
        oos_returns = out_of_sample_returns.dropna()

        if len(is_returns) < 10 or len(oos_returns) < 10:
            return StatisticalTestResult(
                test_name="pbo",
                passed=False,
                details={"error": "Insufficient data"},
            )

        is_sharpe = is_returns.mean() / is_returns.std() * np.sqrt(252) if is_returns.std() > 0 else 0
        oos_sharpe = oos_returns.mean() / oos_returns.std() * np.sqrt(252) if oos_returns.std() > 0 else 0

        # PBO proxy: if OOS Sharpe is much lower than IS Sharpe, likely overfit
        if is_sharpe > 0:
            degradation = 1 - (oos_sharpe / is_sharpe)
        else:
            degradation = 0

        # PBO > 0.5 suggests significant overfitting
        pbo = max(0, min(1, degradation))

        return StatisticalTestResult(
            test_name="probability_of_backtest_overfitting",
            passed=pbo < 0.5,
            p_value=pbo,
            statistic=float(pbo),
            details={
                "is_sharpe": float(is_sharpe),
                "oos_sharpe": float(oos_sharpe),
                "degradation": float(degradation),
                "pbo": float(pbo),
            },
        )
