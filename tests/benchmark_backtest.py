import time

import numpy as np
import pandas as pd

from baet.config.models import BacktestConfig
from baet.execution.backtest import PortfolioBacktestEngine


def run_benchmark():
    n_symbols = 50
    n_days = 100
    n_timestamps = n_days * 24  # Hourly

    symbols = [f"SYM{i}" for i in range(n_symbols)]
    timestamps = pd.date_range("2024-01-01", periods=n_timestamps, freq="1h")

    market_frames = {}
    signals = {}

    for symbol in symbols:
        df = pd.DataFrame(
            {
                "close_time": timestamps,
                "open": np.random.uniform(100, 200, n_timestamps),
                "high": np.random.uniform(200, 300, n_timestamps),
                "low": np.random.uniform(50, 100, n_timestamps),
                "close": np.random.uniform(100, 200, n_timestamps),
                "volume": np.random.uniform(1000, 10000, n_timestamps),
                "symbol": symbol,
                "timeframe": "1h",
            }
        )
        market_frames[(symbol, "1h")] = df

        # Simple signal: buy if price went up
        sig_df = pd.DataFrame(
            {"close_time": timestamps, "signal": np.random.choice([0, 1], n_timestamps)}
        )
        signals[(symbol, "1h")] = sig_df

    config = BacktestConfig()
    engine = PortfolioBacktestEngine(config)

    print(f"Starting benchmark with {n_symbols} symbols and {n_timestamps} timestamps...")
    start_time = time.time()
    artifacts = engine.run(market_frames, signals, "bench")
    end_time = time.time()

    print(f"Backtest completed in {end_time - start_time:.4f} seconds")
    print(f"Trade count: {len(artifacts.trades)}")
    print(f"Equity rows: {len(artifacts.equity_curve)}")


if __name__ == "__main__":
    run_benchmark()
