"""Metrics engine for BAET.

Computes comprehensive performance metrics:
- Sharpe, Sortino, Calmar ratios
- Drawdown statistics
- Trade statistics (hit rate, expectancy, profit factor)
- Turnover and fee analysis
- Tail risk (VaR, CVaR, skewness, kurtosis)
- Regime breakdown
- Long/short decomposition

All metrics are computed from equity curves and trade logs.
No lookahead bias — only past data is used.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from baet.research.experiment import ExperimentMetrics

logger = logging.getLogger(__name__)


class MetricsEngine:
    """
    Computes comprehensive performance metrics from equity curves and trades.
    """

    def __init__(
        self,
        risk_free_rate_annual: float = 0.05,  # 5% annual risk-free rate
        periods_per_year: int = 8760,          # Hourly data
    ) -> None:
        self.risk_free_rate = risk_free_rate_annual
        self.periods_per_year = periods_per_year

    def compute(
        self,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame | None = None,
        initial_cash: float = 10000.0,
    ) -> ExperimentMetrics:
        """
        Compute all metrics from an equity curve and optional trade log.

        Args:
            equity_curve: DataFrame with 'timestamp' and 'equity' columns.
            trades: Optional DataFrame with trade records.
            initial_cash: Starting capital.

        Returns:
            ExperimentMetrics with all fields populated.
        """
        metrics = ExperimentMetrics()

        if equity_curve.empty or "equity" not in equity_curve.columns:
            return metrics

        equity = equity_curve["equity"].values
        returns = np.diff(equity) / equity[:-1]
        returns = returns[np.isfinite(returns)]  # Remove inf/nan

        if len(returns) == 0:
            return metrics

        # Returns
        metrics.total_return_pct = (equity[-1] - initial_cash) / initial_cash * 100
        n_periods = len(returns)
        years = n_periods / self.periods_per_year
        if years > 0:
            metrics.annualized_return_pct = (
                (equity[-1] / initial_cash) ** (1 / years) - 1
            ) * 100

        # Volatility
        metrics.volatility_annualized = float(np.std(returns) * np.sqrt(self.periods_per_year)) * 100

        # Sharpe ratio
        rf_per_period = self.risk_free_rate / self.periods_per_year
        excess_returns = returns - rf_per_period
        if np.std(excess_returns) > 0:
            metrics.sharpe_ratio = float(
                np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(self.periods_per_year)
            )

        # Sortino ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and np.std(downside_returns) > 0:
            metrics.sortino_ratio = float(
                np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(self.periods_per_year)
            )

        # Drawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        metrics.max_drawdown_pct = float(np.max(drawdown)) * 100
        metrics.current_drawdown_pct = float(drawdown[-1]) * 100

        # Max drawdown duration
        dd_duration = self._max_drawdown_duration(equity)
        metrics.max_drawdown_duration_days = dd_duration / 24  # Assuming hourly

        # Calmar ratio
        if metrics.max_drawdown_pct > 0:
            metrics.calmar_ratio = metrics.annualized_return_pct / metrics.max_drawdown_pct

        # Tail risk
        if len(returns) > 10:
            metrics.skewness = float(pd.Series(returns).skew())
            metrics.kurtosis = float(pd.Series(returns).kurtosis())
            metrics.var_95 = float(np.percentile(returns, 5))
            metrics.cvar_95 = float(returns[returns <= metrics.var_95].mean())

        # Trade statistics
        if trades is not None and not trades.empty:
            self._compute_trade_metrics(metrics, trades, initial_cash)

        return metrics

    def _compute_trade_metrics(
        self,
        metrics: ExperimentMetrics,
        trades: pd.DataFrame,
        initial_cash: float,
    ) -> None:
        """Compute trade-level metrics."""
        metrics.total_trades = len(trades)

        if metrics.total_trades == 0:
            return

        # Win/loss
        if "pnl" in trades.columns:
            pnl = trades["pnl"].astype(float)
            metrics.winning_trades = int((pnl > 0).sum())
            metrics.losing_trades = int((pnl <= 0).sum())
            metrics.hit_rate = metrics.winning_trades / metrics.total_trades

            wins = pnl[pnl > 0]
            losses = pnl[pnl <= 0]

            if len(wins) > 0:
                metrics.avg_win_pct = float(wins.mean() / initial_cash * 100)
            if len(losses) > 0:
                metrics.avg_loss_pct = float(losses.mean() / initial_cash * 100)

            # Profit factor
            gross_profit = wins.sum() if len(wins) > 0 else 0
            gross_loss = abs(losses.sum()) if len(losses) > 0 else 1
            metrics.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

            # Expectancy
            metrics.expectancy = float(pnl.mean() / initial_cash * 100)

        # Fees
        if "fee" in trades.columns:
            metrics.total_fees = float(trades["fee"].astype(float).sum())
            total_return = metrics.total_return_pct / 100 * initial_cash
            metrics.fee_adjusted_return_pct = (
                (total_return - metrics.total_fees) / initial_cash * 100
            )

        # Turnover
        if "units" in trades.columns and "price" in trades.columns:
            trade_values = trades["units"].astype(float) * trades["price"].astype(float)
            total_turnover = trade_values.sum()
            metrics.turnover = total_turnover / initial_cash

        # Long/short decomposition
        if "side" in trades.columns:
            long_trades = trades[trades["side"] == "BUY"]
            short_trades = trades[trades["side"] == "SELL"]

            if "pnl" in trades.columns:
                if len(long_trades) > 0:
                    long_pnl = long_trades["pnl"].astype(float).sum()
                    metrics.long_return_pct = long_pnl / initial_cash * 100
                    metrics.long_hit_rate = (
                        (long_trades["pnl"].astype(float) > 0).sum() / len(long_trades)
                    )

                if len(short_trades) > 0:
                    short_pnl = short_trades["pnl"].astype(float).sum()
                    metrics.short_return_pct = short_pnl / initial_cash * 100
                    metrics.short_hit_rate = (
                        (short_trades["pnl"].astype(float) > 0).sum() / len(short_trades)
                    )

    @staticmethod
    def _max_drawdown_duration(equity: np.ndarray) -> float:
        """Compute maximum drawdown duration in periods."""
        peak = np.maximum.accumulate(equity)
        in_drawdown = equity < peak

        if not in_drawdown.any():
            return 0.0

        # Find consecutive drawdown periods
        max_duration = 0
        current_duration = 0
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        return float(max_duration)

    def regime_breakdown(
        self,
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        regime_series: pd.Series,
    ) -> dict[str, dict[str, float]]:
        """
        Compute metrics broken down by market regime.

        Args:
            equity_curve: Equity curve DataFrame.
            trades: Trade DataFrame.
            regime_series: Series mapping timestamp → regime label.

        Returns:
            Dict of regime → {sharpe, return, max_dd, trades, hit_rate}.
        """
        breakdown = {}

        for regime in regime_series.unique():
            mask = regime_series == regime
            if mask.sum() < 10:
                continue

            regime_equity = equity_curve[mask]
            regime_trades = trades[mask] if "timestamp" in trades.columns else pd.DataFrame()

            regime_metrics = self.compute(
                regime_equity,
                regime_trades if not regime_trades.empty else None,
            )

            breakdown[regime] = {
                "sharpe": regime_metrics.sharpe_ratio,
                "return_pct": regime_metrics.total_return_pct,
                "max_drawdown_pct": regime_metrics.max_drawdown_pct,
                "trades": regime_metrics.total_trades,
                "hit_rate": regime_metrics.hit_rate,
            }

        return breakdown
