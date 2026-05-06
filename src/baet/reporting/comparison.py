from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from baet.core.models import BacktestArtifacts, StrategyMetadata


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

    if not artifacts.equity_curve.empty:
        equity = artifacts.equity_curve["equity"].astype("float64")
        running_max = equity.cummax()
        drawdowns = (equity / running_max) - 1.0
        max_drawdown = float(drawdowns.min())

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
    }


def build_ranked_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    ranked = metrics.sort_values(
        by=["total_return", "final_equity", "mean_bar_return"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    ranked["rank"] = ranked.index + 1
    return ranked


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
