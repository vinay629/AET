from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import numpy as np

from baet.core.models import BacktestArtifacts, StrategyMetadata


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    excess_returns = returns - (risk_free_rate / 252.0)
    std_dev = float(excess_returns.std())
    if std_dev <= 0.0:
        return 0.0
    return float(excess_returns.mean() / std_dev * np.sqrt(252.0))


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0, target: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    excess_returns = returns - (risk_free_rate / 252.0)
    downside = excess_returns[excess_returns < target]
    if len(downside) == 0:
        return 0.0
    downside_std = float(np.sqrt(np.mean(np.square(downside))))
    if downside_std <= 0.0:
        return 0.0
    return float(excess_returns.mean() / downside_std * np.sqrt(252.0))


def calculate_calmar_ratio(returns: pd.Series, max_drawdown: float) -> float:
    if len(returns) < 2 or max_drawdown >= 0.0:
        return 0.0
    annual_return = float((1.0 + returns.sum()) ** (252.0 / len(returns)) - 1.0)
    if abs(max_drawdown) <= 0.0:
        return 0.0
    return abs(float(annual_return / max_drawdown))


def calculate_profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    buy_rows = trades[trades["side"] == "BUY"].reset_index(drop=True)
    sell_rows = trades[trades["side"] == "SELL"].reset_index(drop=True)
    total_gain = 0.0
    total_loss = 0.0
    for idx in range(min(len(buy_rows), len(sell_rows))):
        buy_price = float(buy_rows["price"].iloc[idx])
        sell_price = float(sell_rows["price"].iloc[idx])
        pnl = (sell_price - buy_price) * float(buy_rows["units"].iloc[idx])
        if pnl > 0.0:
            total_gain += pnl
        else:
            total_loss += abs(pnl)
    if total_loss <= 0.0:
        return 0.0 if total_gain <= 0.0 else float("inf")
    return float(total_gain / total_loss)


def build_strategy_metrics_row(
    strategy_name: str,
    metadata: StrategyMetadata,
    artifacts: BacktestArtifacts,
) -> dict[str, object]:
    metric_values = {
        str(row["metric"]): float(row["value"])
        for _, row in artifacts.metrics.iterrows()
    }
    trades = artifacts.trades.copy()
    avg_trade_return = 0.0
    win_rate = 0.0
    max_drawdown = 0.0
    sharpe_ratio = 0.0
    sortino_ratio = 0.0
    calmar_ratio = 0.0
    profit_factor = 0.0

    if not trades.empty:
        buy_mask = trades["side"] == "BUY"
        sell_mask = trades["side"] == "SELL"
        round_trip_returns = []
        buy_rows = trades[buy_mask].reset_index(drop=True)
        sell_rows = trades[sell_mask].reset_index(drop=True)
        for idx in range(min(len(buy_rows), len(sell_rows))):
            buy_price = float(buy_rows["price"].iloc[idx])
            sell_price = float(sell_rows["price"].iloc[idx])
            round_trip_returns.append((sell_price / buy_price) - 1.0)
        if round_trip_returns:
            returns_series = pd.Series(round_trip_returns, dtype="float64")
            avg_trade_return = float(returns_series.mean())
            win_rate = float((returns_series > 0.0).mean())
        profit_factor = calculate_profit_factor(trades)

    if not artifacts.equity_curve.empty:
        equity = artifacts.equity_curve["equity"].astype("float64")
        running_max = equity.cummax()
        drawdowns = (equity / running_max) - 1.0
        max_drawdown = float(drawdowns.min())
        daily_returns = equity.pct_change().fillna(0.0)
        sharpe_ratio = calculate_sharpe_ratio(daily_returns)
        sortino_ratio = calculate_sortino_ratio(daily_returns)
        calmar_ratio = calculate_calmar_ratio(daily_returns, max_drawdown)

    return {
        "strategy_name": strategy_name,
        "category": metadata.category,
        "version": metadata.version,
        "description": metadata.description,
        "final_equity": metric_values.get("final_equity", 0.0),
        "total_return": metric_values.get("total_return", 0.0),
        "trade_count": int(metric_values.get("trade_count", 0.0)),
        "mean_bar_return": metric_values.get("mean_bar_return", 0.0),
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "average_trade_return": avg_trade_return,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "profit_factor": profit_factor,
    }


def build_ranked_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return metrics
    ranked = metrics.sort_values(
        by=["sharpe_ratio", "total_return", "max_drawdown"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    return ranked


def build_ranking_by_criteria(metrics: pd.DataFrame, criteria: str = "sharpe") -> pd.DataFrame:
    """Build rankings by specific criteria: sharpe, return, drawdown, or composite."""
    if metrics.empty:
        return metrics
    if criteria == "sharpe":
        ranked = metrics.sort_values(by="sharpe_ratio", ascending=False).reset_index(drop=True)
    elif criteria == "return":
        ranked = metrics.sort_values(by="total_return", ascending=False).reset_index(drop=True)
    elif criteria == "drawdown":
        ranked = metrics.sort_values(by="max_drawdown", ascending=True).reset_index(drop=True)
    elif criteria == "calmar":
        ranked = metrics.sort_values(by="calmar_ratio", ascending=False).reset_index(drop=True)
    else:
        ranked = metrics.sort_values(
            by=["sharpe_ratio", "total_return", "max_drawdown"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    return ranked


def build_summary_statistics(metrics: pd.DataFrame) -> dict[str, object]:
    """Build summary statistics across all strategies."""
    if metrics.empty:
        return {}
    return {
        "total_strategies": int(len(metrics)),
        "best_sharpe": float(metrics["sharpe_ratio"].max()),
        "avg_sharpe": float(metrics["sharpe_ratio"].mean()),
        "best_return": float(metrics["total_return"].max()),
        "avg_return": float(metrics["total_return"].mean()),
        "worst_drawdown": float(metrics["max_drawdown"].min()),
        "avg_drawdown": float(metrics["max_drawdown"].mean()),
        "best_win_rate": float(metrics["win_rate"].max()),
        "avg_win_rate": float(metrics["win_rate"].mean()),
    }


def build_metadata_table(strategies: list[StrategyMetadata]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strategy_name": strategy.name,
                "category": strategy.category,
                "version": strategy.version,
                "description": strategy.description,
            }
            for strategy in strategies
        ]
    )


def build_run_manifest(
    run_name: str,
    symbols: list[str],
    timeframes: list[str],
    strategy_names: list[str],
    config: dict[str, object],
) -> dict[str, object]:
    return {
        "run_name": run_name,
        "symbols": symbols,
        "timeframes": timeframes,
        "strategies": strategy_names,
        "config": config,
    }


def persist_comparison_artifacts(
    root: Path,
    run_name: str,
    metrics: pd.DataFrame,
    ranked: pd.DataFrame,
    metadata_table: pd.DataFrame,
    manifest: dict[str, object],
) -> None:
    comparison_root = root / f"{run_name}_comparison"
    comparison_root.mkdir(parents=True, exist_ok=True)
    metrics.to_parquet(comparison_root / "strategy_metrics.parquet", index=False)
    ranked.to_parquet(comparison_root / "ranked_summary.parquet", index=False)
    metadata_table.to_parquet(comparison_root / "strategy_metadata.parquet", index=False)
    (comparison_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    summary_stats = build_summary_statistics(metrics)
    (comparison_root / "summary_statistics.json").write_text(json.dumps(summary_stats, indent=2), encoding="utf-8")
