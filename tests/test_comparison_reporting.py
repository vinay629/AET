from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from baet.config.loader import load_settings
from baet.core.models import BacktestArtifacts, StrategyMetadata
from baet.reporting.comparison import (
    build_metadata_table,
    build_ranked_summary,
    build_ranking_by_criteria,
    build_strategy_metrics_row,
    build_summary_statistics,
    calculate_calmar_ratio,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    persist_comparison_artifacts,
)
from baet.reporting.workflows import run_strategy_comparison


def _frame(symbol: str, timeframe: str) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=40, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "symbol": [symbol] * len(index),
            "timeframe": [timeframe] * len(index),
            "open_time": index,
            "close_time": index + pd.Timedelta(minutes=59, seconds=59),
            "open": [100.0 + i for i in range(len(index))],
            "high": [101.0 + i for i in range(len(index))],
            "low": [99.0 + i for i in range(len(index))],
            "close": [100.5 + i for i in range(len(index))],
            "volume": [10.0 + i for i in range(len(index))],
            "quote_volume": [1000.0 + i for i in range(len(index))],
            "trade_count": [100 + i for i in range(len(index))],
            "taker_buy_base_volume": [5.0 + i for i in range(len(index))],
            "taker_buy_quote_volume": [500.0 + i for i in range(len(index))],
            "source": ["fixture"] * len(index),
        }
    )


def _create_mock_artifacts(
    total_return: float, max_dd: float, trade_count: int = 10
) -> BacktestArtifacts:
    """Create mock backtest artifacts for testing."""
    index = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
    initial_equity = 10_000.0
    final_equity = initial_equity * (1.0 + total_return)

    equity_values = np.linspace(initial_equity, final_equity, len(index))
    if max_dd < 0:
        # Inject a drawdown
        mid_point = len(index) // 2
        equity_values[mid_point:] = equity_values[mid_point:] * (1.0 + max_dd)

    equity_curve = pd.DataFrame(
        {
            "timestamp": index,
            "cash": [initial_equity / 2.0] * len(index),
            "market_value": [initial_equity * (0.5 + i * 0.01) for i in range(len(index))],
            "equity": equity_values,
        }
    )

    trades = pd.DataFrame(
        {
            "timestamp": index[:trade_count],
            "symbol": ["BTCUSDT"] * trade_count,
            "timeframe": ["1h"] * trade_count,
            "side": ["BUY", "SELL"] * (trade_count // 2),
            "price": [100.0 + i for i in range(trade_count)],
            "units": [1.0] * trade_count,
            "fee": [0.1] * trade_count,
        }
    )

    symbol_returns = pd.DataFrame(
        {
            "timestamp": index,
            "symbol_key": ["BTCUSDT:1h"] * len(index),
            "market_value": np.linspace(5_000.0, 5_000.0 * (1.0 + total_return), len(index)),
            "return": [0.01] * len(index),
        }
    )

    metrics = pd.DataFrame(
        {
            "metric": ["final_equity", "total_return", "trade_count", "mean_bar_return"],
            "value": [final_equity, total_return, float(trade_count), 0.001],
        }
    )

    return BacktestArtifacts(
        equity_curve=equity_curve,
        trades=trades,
        symbol_returns=symbol_returns,
        metrics=metrics,
        metadata={"run_name": "test", "config": {}},
    )


def test_calculate_sharpe_ratio() -> None:
    returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.005] * 50, dtype="float64")
    sharpe = calculate_sharpe_ratio(returns)
    assert sharpe > 0.0
    assert isinstance(sharpe, float)


def test_calculate_sortino_ratio() -> None:
    returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.005] * 50, dtype="float64")
    sortino = calculate_sortino_ratio(returns)
    assert sortino > 0.0
    assert isinstance(sortino, float)


def test_calculate_calmar_ratio() -> None:
    returns = pd.Series([0.01, 0.02, -0.01, 0.015, 0.005] * 50, dtype="float64")
    calmar = calculate_calmar_ratio(returns, max_drawdown=-0.1)
    assert calmar > 0.0
    assert isinstance(calmar, float)


def test_calculate_profit_factor() -> None:
    trades = pd.DataFrame(
        {
            "side": ["BUY", "SELL", "BUY", "SELL"],
            "price": [100.0, 105.0, 100.0, 102.0],
            "units": [1.0, 1.0, 1.0, 1.0],
        }
    )
    profit_factor = calculate_profit_factor(trades)
    assert profit_factor > 0.0
    assert isinstance(profit_factor, float)


def test_build_strategy_metrics_row() -> None:
    artifacts = _create_mock_artifacts(0.2, -0.1, 10)
    metadata = StrategyMetadata(
        name="test_strategy",
        category="baseline",
        version="1.0.0",
        description="Test strategy",
    )

    row = build_strategy_metrics_row("test_strategy", metadata, artifacts)

    assert row["strategy_name"] == "test_strategy"
    assert row["total_return"] == 0.2
    assert row["max_drawdown"] <= -0.08
    assert "sharpe_ratio" in row
    assert "sortino_ratio" in row
    assert "calmar_ratio" in row
    assert "profit_factor" in row
    assert row["win_rate"] >= 0.0
    assert row["win_rate"] <= 1.0


def test_build_ranked_summary() -> None:
    metrics = pd.DataFrame(
        {
            "strategy_name": ["strat1", "strat2", "strat3"],
            "sharpe_ratio": [1.5, 2.0, 1.2],
            "total_return": [0.1, 0.15, 0.08],
            "max_drawdown": [-0.1, -0.08, -0.12],
        }
    )

    ranked = build_ranked_summary(metrics)

    assert len(ranked) == 3
    assert "rank" in ranked.columns
    assert ranked.iloc[0]["strategy_name"] == "strat2"
    assert ranked.iloc[0]["rank"] == 1


def test_build_ranking_by_criteria() -> None:
    metrics = pd.DataFrame(
        {
            "strategy_name": ["strat1", "strat2", "strat3"],
            "sharpe_ratio": [1.5, 2.0, 1.2],
            "total_return": [0.1, 0.15, 0.08],
            "max_drawdown": [-0.1, -0.08, -0.12],
            "calmar_ratio": [1.0, 1.875, 0.666],
        }
    )

    ranked_sharpe = build_ranking_by_criteria(metrics, "sharpe")
    assert ranked_sharpe.iloc[0]["strategy_name"] == "strat2"

    ranked_return = build_ranking_by_criteria(metrics, "return")
    assert ranked_return.iloc[0]["strategy_name"] == "strat2"

    ranked_drawdown = build_ranking_by_criteria(metrics, "drawdown")
    assert ranked_drawdown.iloc[0]["strategy_name"] == "strat2"


def test_build_summary_statistics() -> None:
    metrics = pd.DataFrame(
        {
            "strategy_name": ["strat1", "strat2", "strat3"],
            "sharpe_ratio": [1.5, 2.0, 1.2],
            "total_return": [0.1, 0.15, 0.08],
            "max_drawdown": [-0.1, -0.08, -0.12],
            "win_rate": [0.5, 0.6, 0.4],
        }
    )

    stats = build_summary_statistics(metrics)

    assert stats["total_strategies"] == 3
    assert stats["best_sharpe"] == 2.0
    assert stats["best_return"] == 0.15
    assert stats["worst_drawdown"] == -0.12
    assert stats["avg_sharpe"] > 0.0


def test_build_metadata_table() -> None:
    strategies = [
        StrategyMetadata("strat1", "baseline", "1.0", "Strategy 1"),
        StrategyMetadata("strat2", "baseline", "1.0", "Strategy 2"),
    ]

    table = build_metadata_table(strategies)

    assert len(table) == 2
    assert list(table["strategy_name"]) == ["strat1", "strat2"]


def test_persist_comparison_artifacts() -> None:
    metrics = pd.DataFrame(
        {
            "strategy_name": ["strat1", "strat2"],
            "sharpe_ratio": [1.5, 2.0],
            "total_return": [0.1, 0.15],
            "max_drawdown": [-0.1, -0.08],
            "win_rate": [0.5, 0.6],
        }
    )

    ranked = build_ranked_summary(metrics)
    metadata_table = build_metadata_table(
        [
            StrategyMetadata("strat1", "baseline", "1.0", "S1"),
            StrategyMetadata("strat2", "baseline", "1.0", "S2"),
        ]
    )
    manifest = {
        "run_name": "test_run",
        "symbols": ["BTCUSDT"],
        "timeframes": ["1h"],
        "strategies": ["strat1", "strat2"],
        "config": {},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        persist_comparison_artifacts(root, "test_run", metrics, ranked, metadata_table, manifest)

        comparison_root = root / "test_run_comparison"
        assert comparison_root.exists()
        assert (comparison_root / "strategy_metrics.parquet").exists()
        assert (comparison_root / "ranked_summary.parquet").exists()
        assert (comparison_root / "strategy_metadata.parquet").exists()
        assert (comparison_root / "manifest.json").exists()
        assert (comparison_root / "summary_statistics.json").exists()

        loaded_metrics = pd.read_parquet(comparison_root / "strategy_metrics.parquet")
        assert len(loaded_metrics) == 2


def test_strategy_comparison_emits_ranked_outputs(tmp_path: Path) -> None:
    settings = load_settings(mode="dev", env_file=Path(".env.example"))
    settings.reporting.backtests_dir = tmp_path / "results" / "backtests"
    market_frames = {
        ("BTCUSDT", "1h"): _frame("BTCUSDT", "1h"),
        ("ETHUSDT", "1h"): _frame("ETHUSDT", "1h"),
    }

    metrics, ranked, metadata_table, manifest = run_strategy_comparison(
        settings=settings,
        market_frames=market_frames,
        run_name="comparison_test",
    )

    assert len(metrics) >= 2
    assert "rank" in ranked.columns
    assert len(metadata_table) >= 2
    assert manifest["strategies"]
    ranked_path = (
        settings.reporting.backtests_dir / "comparison_test_comparison" / "ranked_summary.parquet"
    )
    assert ranked_path.exists()
