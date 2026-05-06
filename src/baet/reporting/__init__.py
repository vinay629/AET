"""Reporting and metrics output."""

from baet.reporting.comparison import (
    build_intelligence_stack_comparison,
    build_metadata_table,
    build_ranked_summary,
    build_regime_performance_report,
    build_run_manifest,
    build_strategy_metrics_row,
    persist_comparison_artifacts,
    validate_intelligence_stack,
)
from baet.reporting.summaries import (
    build_backtest_results_summary,
    build_data_quality_summary,
    build_feature_coverage_summary,
    build_ingestion_summary,
)
from baet.reporting.workflows import run_strategy_comparison

__all__ = [
    "build_intelligence_stack_comparison",
    "build_metadata_table",
    "build_ranked_summary",
    "build_regime_performance_report",
    "build_run_manifest",
    "build_strategy_metrics_row",
    "build_backtest_results_summary",
    "build_data_quality_summary",
    "build_feature_coverage_summary",
    "build_ingestion_summary",
    "persist_comparison_artifacts",
    "run_strategy_comparison",
    "validate_intelligence_stack",
]
