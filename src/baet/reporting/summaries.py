from __future__ import annotations

import pandas as pd

from baet.data.validation import summarize_data_quality


def build_ingestion_summary(frame: pd.DataFrame, symbol: str, timeframe: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": int(len(frame)),
        "start": frame["open_time"].min().isoformat() if not frame.empty else None,
        "end": frame["open_time"].max().isoformat() if not frame.empty else None,
    }


def build_data_quality_summary(frame: pd.DataFrame, timeframe: str) -> dict[str, object]:
    return summarize_data_quality(frame, timeframe)


def build_feature_coverage_summary(frame: pd.DataFrame) -> dict[str, object]:
    excluded_columns = {"symbol", "timeframe", "open_time", "close_time"}
    feature_columns = [col for col in frame.columns if col not in excluded_columns]
    missing_counts = {col: int(frame[col].isna().sum()) for col in feature_columns}
    return {
        "row_count": int(len(frame)),
        "feature_count": len(feature_columns),
        "missing_counts": missing_counts,
    }


def build_backtest_results_summary(
    metrics: pd.DataFrame,
    trades: pd.DataFrame,
) -> dict[str, object]:
    metric_map: dict[str, object] = {
        str(row["metric"]): float(row["value"]) for _, row in metrics.iterrows()
    }
    metric_map["trade_count"] = int(len(trades))
    return metric_map
