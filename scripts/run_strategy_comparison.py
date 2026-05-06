#!/usr/bin/env python3
"""End-to-end strategy comparison workflow for validating M2.3."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Add src to path so baet can be imported
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baet.config.loader import load_settings
from baet.data.storage import ParquetMarketDataStore
from baet.reporting.comparison import build_summary_statistics, build_ranking_by_criteria
from baet.reporting.workflows import run_strategy_comparison


def main() -> None:
    """Run strategy comparison and report results."""
    print("=" * 80)
    print("BAET Stage 2 Strategy Comparison Validation")
    print("=" * 80)
    
    # Load settings
    settings = load_settings(mode="dev")
    store = ParquetMarketDataStore(settings)
    print(f"\nSettings loaded from mode: dev")
    print(f"Processing data from: {settings.storage.processed_data_dir}")
    
    # Load market data
    market_frames: dict[tuple[str, str], pd.DataFrame] = {}
    for symbol in settings.market.symbols:
        for timeframe in settings.market.timeframes:
            try:
                data = store.read_features(symbol, timeframe)
                if data is not None and not data.empty:
                    market_frames[(symbol, timeframe)] = data
                    print(f"✓ Loaded {symbol} {timeframe}: {len(data)} bars")
            except Exception as e:
                print(f"✗ Failed to load {symbol} {timeframe}: {e}")
    
    if not market_frames:
        print("\n⚠ No market data found. Please run data ingestion first.")
        print("Example: python -m baet.data.binance")
        sys.exit(1)
    
    # Run strategy comparison
    print(f"\nRunning strategy comparison on {len(market_frames)} market frames...")
    try:
        metrics, ranked, metadata_table, manifest = run_strategy_comparison(
            settings=settings,
            market_frames=market_frames,
            run_name="stage2_comparison",
        )
    except Exception as e:
        print(f"✗ Strategy comparison failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Print results
    print(f"\n✓ Comparison completed successfully!")
    print(f"✓ Backtested {len(metrics)} strategies\n")
    
    # Print rankings
    print("-" * 80)
    print("STRATEGY RANKINGS (by Sharpe Ratio)")
    print("-" * 80)
    print(ranked[[
        "rank",
        "strategy_name",
        "total_return",
        "max_drawdown",
        "sharpe_ratio",
        "sortino_ratio",
        "win_rate",
    ]].to_string(index=False))
    
    # Print summary statistics
    print("\n" + "-" * 80)
    print("SUMMARY STATISTICS")
    print("-" * 80)
    stats = build_summary_statistics(metrics)
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key:.<40} {value:.4f}")
        else:
            print(f"{key:.<40} {value}")
    
    # Print best strategies by different criteria
    print("\n" + "-" * 80)
    print("BEST STRATEGIES BY CRITERIA")
    print("-" * 80)
    
    for criteria in ["sharpe", "return", "drawdown", "calmar"]:
        ranked_by_criteria = build_ranking_by_criteria(metrics, criteria)
        best = ranked_by_criteria.iloc[0]
        print(f"{criteria.upper():.<40} {best['strategy_name']}")
    
    # Print artifacts location
    output_dir = settings.reporting.backtests_dir / "stage2_comparison_comparison"
    print("\n" + "-" * 80)
    print("ARTIFACTS SAVED TO")
    print("-" * 80)
    print(f"Location: {output_dir}")
    print(f"Files:")
    if output_dir.exists():
        for file in output_dir.glob("*"):
            print(f"  - {file.name}")
    
    print("\n" + "=" * 80)
    print("✓ Stage 2 Strategy Comparison Validation Complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
