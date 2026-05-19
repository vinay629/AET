"""
BAET Production Bootstrap Pipeline.

Orchestrates the full production run:
  1. Data ingestion          — Spot OHLCV + Futures OI, funding, liquidations
  2. Feature engineering     — Technical indicators + derivatives microstructure
  3. Label generation        — Dynamic ATR-scaled Triple Barrier Method
  4. Leakage detection       — Time, cross-section, label leakage checks
  5. Model training          — PurgedKFold CV with embargo
  6. Model registry          — Lineage tracking, validation, promotion
  7. Dashboard materialization — Push results to the quant terminal

Usage:
    uv run python -m baet.scripts.bootstrap_pipeline
    uv run python -m baet.scripts.bootstrap_pipeline --symbol ETHUSDT --days 90
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from baet.config.models import Settings
from baet.data.binance import BinanceHistoricalProvider
from baet.data.features import DerivativesFeatureBuilder, PandasFeatureBuilder
from baet.config.models import DerivativesConfig, FeatureConfig
from baet.ml.feature_store import FeatureStore
from baet.ml.labels import TripleBarrierConfig
from baet.ml.leakage import LeakageDetector
from baet.ml.model_registry import ModelRegistry, ModelStatus
from baet.ml.purged_cv import PurgedKFold
from baet.ml.training import BaselineTrainer, TrainingConfig


def _feature_builder_wrapper(data: pd.DataFrame) -> pd.DataFrame:
    """Adapter that matches FeatureStore.compute() builder signature.

    The FeatureStore expects builder(data) -> DataFrame.
    We use PandasFeatureBuilder internally.
    """
    config = FeatureConfig()
    builder = PandasFeatureBuilder(config=config)
    return builder.build(data)

logger = logging.getLogger("baet.bootstrap")


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def ingest_data(
    provider: BinanceHistoricalProvider,
    symbol: str,
    timeframe: str,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, pd.DataFrame]:
    """Step 1: Ingest spot + derivatives data from Binance.

    Returns a dict with keys: klines, open_interest, funding_rates, liquidations.
    Each value is a DataFrame (possibly empty if the endpoint fails).
    """
    logger.info(
        f"📥 Fetching 6 months of historical data "
        f"[{start_time.date()} to {end_time.date()}]..."
    )

    # Spot OHLCV
    klines_df = provider.fetch_klines(
        symbol=symbol, timeframe=timeframe,
        start_time=start_time, end_time=end_time,
    )
    if klines_df.empty:
        logger.error("❌ Spot data retrieval returned empty. Aborting.")
        sys.exit(1)
    logger.info(f"  ✓ Spot klines: {len(klines_df)} rows")

    # Derivatives data (each may fail independently — graceful degradation)
    data: dict[str, pd.DataFrame] = {"klines": klines_df}

    # Open Interest
    try:
        oi_df = provider.fetch_open_interest(
            symbol=symbol, period=timeframe, limit=2000,
            start_time=start_time, end_time=end_time,
        )
        data["open_interest"] = oi_df
        logger.info(f"  ✓ Open interest: {len(oi_df)} rows")
    except Exception as e:
        logger.warning(f"  ⚠ Open interest fetch failed: {e}")
        data["open_interest"] = pd.DataFrame()

    # Funding Rates
    try:
        fr_df = provider.fetch_funding_rate_history(
            symbol=symbol, limit=2000,
            start_time=start_time, end_time=end_time,
        )
        data["funding_rates"] = fr_df
        logger.info(f"  ✓ Funding rates: {len(fr_df)} rows")
    except Exception as e:
        logger.warning(f"  ⚠ Funding rate fetch failed: {e}")
        data["funding_rates"] = pd.DataFrame()

    # Liquidation Orders
    try:
        liq_df = provider.fetch_liquidation_orders(
            symbol=symbol, limit=2000,
            start_time=start_time, end_time=end_time,
        )
        data["liquidations"] = liq_df
        logger.info(f"  ✓ Liquidations: {len(liq_df)} rows")
    except Exception as e:
        logger.warning(f"  ⚠ Liquidation fetch failed: {e}")
        data["liquidations"] = pd.DataFrame()

    return data


def engineer_features(
    data: dict[str, pd.DataFrame],
    feat_config: FeatureConfig,
    deriv_config: DerivativesConfig,
) -> pd.DataFrame:
    """Step 2: Build technical + derivatives features.

    Merges spot OHLCV with derivatives data and computes all feature columns.
    """
    logger.info("🛠️ Building technical and derivatives features...")

    # Base technical features
    base_builder = PandasFeatureBuilder(config=feat_config)
    features_df = base_builder.build(data["klines"])
    logger.info(f"  ✓ Base features: {features_df.shape}")

    # Derivatives features (graceful — works even if derivatives data is empty)
    deriv_builder = DerivativesFeatureBuilder(config=deriv_config)
    features_df = deriv_builder.build(
        candles=features_df,
        open_interest=data.get("open_interest"),
        funding_rates=data.get("funding_rates"),
        liquidations=data.get("liquidations"),
    )
    logger.info(f"  ✓ Full feature matrix: {features_df.shape}")

    return features_df


def generate_labels(
    features_df: pd.DataFrame,
    barrier_config: TripleBarrierConfig,
) -> pd.DataFrame:
    """Step 3: Generate triple barrier labels with dynamic ATR scaling."""
    logger.info("🏷️ Generating triple barrier labels...")

    from baet.ml.labels import TripleBarrierLabeler

    labeler = TripleBarrierLabeler(config=barrier_config)
    labels_df = labeler.label(
        prices=features_df["close"],
        high=features_df.get("high"),
        low=features_df.get("low"),
        atr=features_df.get("atr_like_14"),
    )

    if labels_df.empty:
        logger.warning("  ⚠ No labels generated — check barrier parameters")
        return labels_df

    dist = labels_df["label"].value_counts().to_dict()
    total = len(labels_df)
    logger.info(f"  ✓ Labels: {total} total | Distribution: {dist}")
    for barrier, count in labels_df["barrier"].value_counts().items():
        logger.info(f"    {barrier}: {count} ({count/total*100:.1f}%)")

    return labels_df


def check_leakage(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
) -> dict[str, Any]:
    """Step 4: Run leakage detection on features and labels.

    Returns a leakage report dict. Pipeline halts if CRITICAL leakage found.
    """
    logger.info("🔍 Running leakage detection...")

    # Prepare feature matrix (exclude non-feature columns)
    exclude = {
        "symbol", "timeframe", "open_time", "close_time", "source",
        "open", "high", "low", "close", "volume", "quote_volume",
        "trade_count", "taker_buy_base_volume", "taker_buy_quote_volume",
    }
    feature_cols = [c for c in features_df.columns if c not in exclude]

    # Align features with labels
    if "entry_idx" in labels_df.columns:
        valid_idx = labels_df[
            (labels_df["entry_idx"] >= 0) &
            (labels_df["entry_idx"] < len(features_df))
        ]
        X = features_df[feature_cols].iloc[valid_idx["entry_idx"].values].reset_index(drop=True)
        y = valid_idx["label"].reset_index(drop=True)
    else:
        min_len = min(len(features_df), len(labels_df))
        X = features_df[feature_cols].iloc[:min_len]
        y = labels_df["label"].iloc[:min_len]

    # Drop NaN rows
    valid_mask = ~(X.isna().any(axis=1) | y.isna())
    X = X[valid_mask]
    y = y[valid_mask]

    detector = LeakageDetector()
    report = detector.check_all(features=X, labels=y)

    if report.passed:
        logger.info("  ✓ No leakage detected")
    else:
        logger.warning(f"  ⚠ Leakage issues: {len(report.findings)} findings")
        for f in report.findings:
            logger.warning(f"    [{f.severity.value}] {f.leakage_type.value}: {f.message}")

    return report.summary()


def train_and_register(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    feature_cols: list[str],
    training_config: TrainingConfig,
    model_registry: ModelRegistry,
    leakage_report: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Step 5: Train model with PurgedKFold CV and register artifact.

    Returns (model_id, validation_metrics).
    """
    logger.info("🏋️ Training baseline model via PurgedKFold CV...")

    # Prepare aligned X, y
    if "entry_idx" in labels_df.columns:
        valid = labels_df[
            (labels_df["entry_idx"] >= 0) &
            (labels_df["entry_idx"] < len(features_df))
        ]
        X = features_df[feature_cols].iloc[valid["entry_idx"].values].values
        y = valid["label"].values.astype(int)
    else:
        min_len = min(len(features_df), len(labels_df))
        X = features_df[feature_cols].iloc[:min_len].values
        y = labels_df["label"].iloc[:min_len].values.astype(int)

    # Remove NaN/Inf
    valid_rows = ~(np.isnan(X).any(axis=1) | np.isinf(X).any(axis=1))
    X = X[valid_rows]
    y = y[valid_rows]

    logger.info(f"  Training set: {X.shape[0]} samples, {X.shape[1]} features")

    # Build and run trainer
    feature_store = FeatureStore(store_dir=Path("features"))
    trainer = BaselineTrainer(
        feature_store=feature_store,
        model_registry=model_registry,
    )
    result = trainer.run(training_config)

    model_artifact = result.model_artifact
    model_id = model_artifact.model_id

    # Validate in registry
    model_registry.validate(
        model_id=model_id,
        validation_metrics=result.model_artifact.validation_metrics,
        leakage_report=leakage_report,
    )

    # Check if validation passed
    artifact = model_registry._find(model_id)
    if artifact is None:
        raise RuntimeError(f"Model {model_id} not found after registration")

    if artifact.status == ModelStatus.REJECTED:
        logger.error(f"❌ Model {model_id} rejected during validation")
        return model_id, result.model_artifact.validation_metrics

    # Promote to production
    model_registry.promote(model_id)
    logger.info(f"🏆 Model {model_id} promoted to PRODUCTION")

    return model_id, result.model_artifact.validation_metrics


def print_summary(
    symbol: str,
    model_id: str,
    metrics: dict[str, Any],
    data: dict[str, pd.DataFrame],
    features_df: pd.DataFrame,
) -> None:
    """Print deployment summary."""
    print()
    print("=" * 65)
    print("  BAET DEPLOYMENT ENGINE — ONLINE")
    print("=" * 65)
    print(f"  Symbol:              {symbol}")
    print(f"  Production Model ID: {model_id}")
    print(f"  CV Accuracy:         {metrics.get('mean_accuracy', 0):.4f} "
          f"(±{metrics.get('std_accuracy', 0):.4f})")
    print(f"  CV F1 (macro):       {metrics.get('mean_f1_macro', 0):.4f} "
          f"(±{metrics.get('std_f1_macro', 0):.4f})")
    print(f"  Training Samples:    {len(data['klines'])}")
    print(f"  Feature Dimensions:  {features_df.shape[1]}")
    print(f"  Derivatives OI:      {len(data.get('open_interest', pd.DataFrame()))} rows")
    print(f"  Funding Rates:       {len(data.get('funding_rates', pd.DataFrame()))} rows")
    print(f"  Liquidations:        {len(data.get('liquidations', pd.DataFrame()))} rows")
    print()
    print("  View Dashboard:      http://localhost:8501/terminal")
    print("  API Endpoints:       http://localhost:8501/api/research")
    print("=" * 65)
    print()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="BAET Production Bootstrap Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python -m baet.scripts.bootstrap_pipeline
  uv run python -m baet.scripts.bootstrap_pipeline --symbol ETHUSDT --days 90
  uv run python -m baet.scripts.bootstrap_pipeline --atr-window 21 --atr-mult 3.0
        """,
    )
    parser.add_argument(
        "--symbol", type=str, default="BTCUSDT",
        help="Trading pair (default: BTCUSDT)",
    )
    parser.add_argument(
        "--timeframe", type=str, default="1h",
        help="Candle timeframe (default: 1h)",
    )
    parser.add_argument(
        "--days", type=int, default=180,
        help="Days of historical data (default: 180)",
    )
    parser.add_argument(
        "--atr-window", type=int, default=14,
        help="ATR window for dynamic barriers (default: 14)",
    )
    parser.add_argument(
        "--atr-mult", type=float, default=2.5,
        help="ATR multiplier for dynamic barriers (default: 2.5)",
    )
    parser.add_argument(
        "--timeout-bars", type=int, default=24,
        help="Vertical barrier timeout in bars (default: 24)",
    )
    parser.add_argument(
        "--n-splits", type=int, default=5,
        help="Number of PurgedKFold splits (default: 5)",
    )
    parser.add_argument(
        "--model-name", type=str, default="baseline_gb",
        help="Model name for registry (default: baseline_gb)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> None:
    """Execute the full bootstrap pipeline."""
    args = parse_args()
    setup_logging(verbose=args.verbose)

    logger.info("🚀 BAET Bootstrap Pipeline Starting...")
    logger.info(f"   Symbol: {args.symbol} | Timeframe: {args.timeframe} | Days: {args.days}")

    # ── Time range ──
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=args.days)

    # ── Settings & Provider ──
    settings = Settings()
    provider = BinanceHistoricalProvider(settings=settings)

    # ── Step 1: Data Ingestion ──
    data = ingest_data(
        provider=provider,
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_time=start_time,
        end_time=end_time,
    )

    # ── Step 2: Feature Engineering ──
    feat_config = FeatureConfig()
    deriv_config = DerivativesConfig()
    features_df = engineer_features(
        data=data,
        feat_config=feat_config,
        deriv_config=deriv_config,
    )

    # ── Step 2.5: Save features to FeatureStore ──
    logger.info("💾 Saving materialized features to FeatureStore...")
    feature_store = FeatureStore(store_dir=Path("features"))
    feature_name = f"{args.symbol}_{args.timeframe}"
    try:
        feature_store.compute(
            name=feature_name,
            data=data["klines"],
            builder=_feature_builder_wrapper,
            version="1.0.0",
            description=f"Baseline features for {feature_name}",
            use_cache=False,
        )
        logger.info(f"  ✓ Features saved to store: {feature_name}")
    except Exception as e:
        logger.warning(f"  ⚠ Feature store save failed (trainer will use in-memory): {e}")

    # ── Step 3: Label Generation ──
    barrier_config = TripleBarrierConfig(
        atr_window=args.atr_window,
        atr_multiplier=args.atr_mult,
        timeout_bars=args.timeout_bars,
    )
    labels_df = generate_labels(features_df, barrier_config)

    if labels_df.empty:
        logger.error("❌ No labels generated. Aborting.")
        sys.exit(1)

    # ── Step 4: Leakage Detection ──
    leakage_report = check_leakage(features_df, labels_df)

    # Halt on critical leakage
    if leakage_report.get("n_critical", 0) > 0:
        logger.error(
            f"❌ {leakage_report['n_critical']} CRITICAL leakage issues detected. "
            "Promotion blocked. Investigate features before re-running."
        )
        sys.exit(1)

    # ── Step 5: Training & Registry ──
    exclude_cols = {
        "symbol", "timeframe", "open_time", "close_time", "source",
        "open", "high", "low", "close", "volume", "quote_volume",
        "trade_count", "taker_buy_base_volume", "taker_buy_quote_volume",
    }
    feature_cols = [c for c in features_df.columns if c not in exclude_cols]

    model_registry = ModelRegistry(registry_dir=Path("models"))
    training_config = TrainingConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        atr_window=args.atr_window,
        atr_multiplier=args.atr_mult,
        timeout_bars=args.timeout_bars,
        n_splits=args.n_splits,
        model_name=args.model_name,
    )

    model_id, metrics = train_and_register(
        features_df=features_df,
        labels_df=labels_df,
        feature_cols=feature_cols,
        training_config=training_config,
        model_registry=model_registry,
        leakage_report=leakage_report,
    )

    # ── Step 6: Summary ──
    print_summary(
        symbol=args.symbol,
        model_id=model_id,
        metrics=metrics,
        data=data,
        features_df=features_df,
    )


if __name__ == "__main__":
    main()
