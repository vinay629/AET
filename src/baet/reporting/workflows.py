from __future__ import annotations

import pandas as pd

from baet.config.models import Settings
from baet.execution.backtest import PortfolioBacktestEngine
from baet.reporting.comparison import (
    build_metadata_table,
    build_ranked_summary,
    build_run_manifest,
    build_strategy_metrics_row,
    persist_comparison_artifacts,
)
from baet.strategies.discovery import discover_strategies


def run_strategy_comparison(
    settings: Settings,
    market_frames: dict[tuple[str, str], pd.DataFrame],
    run_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    engine = PortfolioBacktestEngine(settings.backtest)
    strategies = discover_strategies()

    strategy_rows: list[dict[str, object]] = []
    strategy_metadata = []
    for strategy in strategies:
        signals: dict[tuple[str, str], pd.DataFrame] = {}
        for key, market in market_frames.items():
            symbol, timeframe = key
            if strategy.supports(symbol, timeframe):
                signals[key] = strategy.generate_signals(market)
        if not signals:
            continue
        artifacts = engine.run_order_intent(
            market_frames=market_frames,
            signals=signals,
            run_name=f"{run_name}_{strategy.metadata.name}",
        )
        strategy_rows.append(
            build_strategy_metrics_row(
                strategy_name=strategy.metadata.name,
                metadata=strategy.metadata,
                artifacts=artifacts,
            )
        )
        strategy_metadata.append(strategy.metadata)

    metrics = pd.DataFrame(strategy_rows)
    ranked = build_ranked_summary(metrics)
    metadata_table = build_metadata_table(strategy_metadata)
    manifest = build_run_manifest(
        run_name=run_name,
        symbols=sorted({key[0] for key in market_frames}),
        timeframes=sorted({key[1] for key in market_frames}),
        strategy_names=[strategy.name for strategy in strategy_metadata],
        config=settings.backtest.model_dump(),
    )
    persist_comparison_artifacts(
        root=settings.reporting.backtests_dir,
        run_name=run_name,
        metrics=metrics,
        ranked=ranked,
        metadata_table=metadata_table,
        manifest=manifest,
    )
    return metrics, ranked, metadata_table, manifest
