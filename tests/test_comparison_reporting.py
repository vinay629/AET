from __future__ import annotations

from pathlib import Path

import pandas as pd

from baet.config.loader import load_settings
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
        settings.reporting.backtests_dir
        / "comparison_test_comparison"
        / "ranked_summary.parquet"
    )
    assert ranked_path.exists()
