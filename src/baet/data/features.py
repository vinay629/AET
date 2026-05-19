from __future__ import annotations

import numpy as np
import pandas as pd

from baet.config.models import DerivativesConfig, FeatureConfig
from baet.data.interfaces import FeatureBuilder


class PandasFeatureBuilder(FeatureBuilder):
    def __init__(self, config: FeatureConfig) -> None:
        self.config = config

    def build(self, candles: pd.DataFrame) -> pd.DataFrame:
        frame = candles.copy().sort_values("close_time").reset_index(drop=True)
        frame["return_1"] = frame["close"].pct_change()

        for window in self.config.return_windows:
            frame[f"return_{window}"] = frame["close"].pct_change(window)
            frame[f"roc_{window}"] = frame["close"].diff(window) / frame["close"].shift(window)

        for window in self.config.volatility_windows:
            frame[f"volatility_{window}"] = frame["return_1"].rolling(window).std()

        true_range = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - frame["close"].shift(1)).abs(),
                (frame["low"] - frame["close"].shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        frame["atr_like_14"] = true_range.rolling(14).mean()

        for window in self.config.trend_windows:
            ma_col = f"sma_{window}"
            frame[ma_col] = frame["close"].rolling(window).mean()
            frame[f"distance_to_{ma_col}"] = (frame["close"] / frame[ma_col]) - 1.0
            frame[f"momentum_{window}"] = frame["close"] - frame["close"].shift(window)

        for window in self.config.volume_windows:
            volume_ma_col = f"volume_sma_{window}"
            frame[volume_ma_col] = frame["volume"].rolling(window).mean()
            frame[f"relative_volume_{window}"] = frame["volume"] / frame[volume_ma_col]

        frame["candle_body"] = frame["close"] - frame["open"]
        frame["candle_range"] = frame["high"] - frame["low"]
        frame["upper_wick"] = frame["high"] - frame[["open", "close"]].max(axis=1)
        frame["lower_wick"] = frame[["open", "close"]].min(axis=1) - frame["low"]
        frame["body_to_range"] = frame["candle_body"] / frame["candle_range"].replace(0.0, pd.NA)

        return frame


class DerivativesFeatureBuilder(FeatureBuilder):
    """Engineer features from derivatives data (OI, funding rates, liquidations).

    Each method takes a DataFrame and returns the same DataFrame with
    additional feature columns. Methods are composable — call them in
    sequence to build a full derivatives feature set.

    All features are:
    - Stationary (ratios, z-scores, not raw levels)
    - Point-in-time correct (no future data leakage)
    - Aligned to the candle timestamp for merging with spot features
    """

    def __init__(self, config: DerivativesConfig | None = None) -> None:
        self.config = config or DerivativesConfig()

    def build(
        self,
        candles: pd.DataFrame,
        open_interest: pd.DataFrame | None = None,
        funding_rates: pd.DataFrame | None = None,
        liquidations: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Build all available derivatives features and merge into candles.

        Args:
            candles: OHLCV candle DataFrame (must have close_time column).
            open_interest: DataFrame with columns [timestamp, open_interest].
            funding_rates: DataFrame with columns [timestamp, funding_rate].
            liquidations: DataFrame with columns [timestamp, side, qty].

        Returns:
            Candles DataFrame with derivatives feature columns appended.
        """
        frame = candles.copy().sort_values("close_time").reset_index(drop=True)

        if open_interest is not None and not open_interest.empty:
            frame = self.add_oi_features(frame, open_interest)

        if funding_rates is not None and not funding_rates.empty:
            frame = self.add_funding_rate_features(frame, funding_rates)

        if liquidations is not None and not liquidations.empty:
            frame = self.add_liquidation_features(frame, liquidations)

        return frame

    def add_oi_features(
        self, candles: pd.DataFrame, oi_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Add open interest features.

        Features:
            oi_change_1: Relative OI change over 1 bar (ΔOI / OI_prev)
            oi_change_N: Relative OI change over N bars
            oi_price_divergence: Correlation between OI change and price change
                over a rolling window. Positive = both rising (trend continuation).
                Negative = diverging (potential reversal).
        """
        frame = candles.copy()

        # Merge OI onto candles using nearest timestamp (forward-fill)
        oi_sorted = oi_data.sort_values("timestamp").reset_index(drop=True)
        frame = pd.merge_asof(
            frame,
            oi_sorted[["timestamp", "open_interest"]],
            left_on="close_time",
            right_on="timestamp",
            direction="backward",
        )
        frame = frame.drop(columns=["timestamp"], errors="ignore")

        # Relative OI change
        for window in self.config.oi_change_windows:
            frame[f"oi_change_{window}"] = (
                frame["open_interest"] - frame["open_interest"].shift(window)
            ) / frame["open_interest"].shift(window).replace(0.0, pd.NA)

        # OI-price divergence: rolling correlation of OI change vs price change
        corr_window = self.config.oi_price_corr_window
        oi_pct = frame["open_interest"].pct_change()
        price_pct = frame["close"].pct_change()
        frame["oi_price_divergence"] = (
            oi_pct.rolling(corr_window).corr(price_pct)
        )

        # Classify OI-price relationship into discrete signals
        oi_change_1 = frame.get("oi_change_1", pd.Series(0.0, index=frame.index))
        price_change_1 = frame["close"].pct_change()

        conditions = [
            (oi_change_1 > 0) & (price_change_1 > 0),   # Rising OI + Rising price
            (oi_change_1 > 0) & (price_change_1 < 0),   # Rising OI + Falling price
            (oi_change_1 < 0) & (price_change_1 > 0),   # Falling OI + Rising price
            (oi_change_1 < 0) & (price_change_1 < 0),   # Falling OI + Falling price
        ]
        choices = [
            "aggressive_long",     # New longs entering, trend continuation
            "short_adding",        # New shorts entering, bearish
            "short_covering",      # Shorts exiting, weak rally
            "long_liquidating",    # Longs exiting, bearish
        ]
        frame["oi_price_signal"] = np.select(conditions, choices, default="neutral")

        return frame

    def add_funding_rate_features(
        self, candles: pd.DataFrame, fr_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Add funding rate features.

        Features:
            funding_rate: Raw funding rate (merged from futures API)
            fr_zscore: Z-score of funding rate over rolling window
                Extreme positive (>2.0) = over-leveraged longs (long squeeze risk)
                Extreme negative (<-2.0) = over-leveraged shorts (short squeeze risk)
            fr_extreme: Binary flag for extreme funding rates
            fr_trend: Direction of funding rate change (1 = rising, -1 = falling, 0 = flat)
        """
        frame = candles.copy()

        # Merge funding rates onto candles
        fr_sorted = fr_data.sort_values("timestamp").reset_index(drop=True)
        frame = pd.merge_asof(
            frame,
            fr_sorted[["timestamp", "funding_rate"]],
            left_on="close_time",
            right_on="timestamp",
            direction="backward",
        )
        frame = frame.drop(columns=["timestamp"], errors="ignore")

        # Z-score of funding rate
        z_window = self.config.fr_zscore_window
        fr_mean = frame["funding_rate"].rolling(z_window, min_periods=1).mean()
        fr_std = frame["funding_rate"].rolling(z_window, min_periods=1).std()
        frame["fr_zscore"] = (
            (frame["funding_rate"] - fr_mean) / fr_std.replace(0.0, pd.NA)
        )

        # Extreme funding rate flag
        threshold = self.config.fr_extreme_threshold
        frame["fr_extreme"] = (
            frame["fr_zscore"].abs() > threshold
        ).astype(int)

        # Funding rate trend (direction of change)
        fr_diff = frame["funding_rate"].diff()
        frame["fr_trend"] = pd.Series(0, index=frame.index, dtype="int64")
        frame.loc[fr_diff > 0, "fr_trend"] = 1
        frame.loc[fr_diff < 0, "fr_trend"] = -1

        return frame

    def add_liquidation_features(
        self, candles: pd.DataFrame, liq_data: pd.DataFrame
    ) -> pd.DataFrame:
        """Add liquidation features.

        Features:
            liq_long_volume: Total long liquidation volume in lookback window
            liq_short_volume: Total short liquidation volume in lookback window
            liq_ratio: (Long liq - Short liq) / total volume
                Positive = more longs liquidated (potential bottom)
                Negative = more shorts liquidated (potential top)
            liq_spike: Binary flag for liquidation volume spikes
            liq_imbalance: Net liquidation direction normalized by average
        """
        frame = candles.copy()

        # Parse liquidation data
        liq = liq_data.copy()
        liq["timestamp"] = pd.to_datetime(liq["timestamp"], utc=True)
        liq["qty"] = liq["qty"].astype("float64")

        # Separate long and short liquidations
        long_liq = liq[liq["side"] == "SELL"].copy()   # SELL side = long liquidation
        short_liq = liq[liq["side"] == "BUY"].copy()    # BUY side = short liquidation

        # Aggregate liquidations into candle-aligned windows
        lookback = self.config.liq_lookback_window

        # For each candle, sum liquidations in the lookback window
        frame["liq_long_volume"] = 0.0
        frame["liq_short_volume"] = 0.0

        if not long_liq.empty:
            long_agg = self._aggregate_liquidations(long_liq, frame, lookback)
            frame["liq_long_volume"] = long_agg

        if not short_liq.empty:
            short_agg = self._aggregate_liquidations(short_liq, frame, lookback)
            frame["liq_short_volume"] = short_agg

        # Liquidation ratio: net liquidation direction / candle volume
        total_liq = frame["liq_long_volume"] + frame["liq_short_volume"]
        frame["liq_ratio"] = (
            (frame["liq_long_volume"] - frame["liq_short_volume"])
            / frame["volume"].replace(0.0, pd.NA)
        )

        # Liquidation spike detection
        avg_liq = total_liq.rolling(lookback * 6, min_periods=1).mean()
        frame["liq_spike"] = (
            total_liq > avg_liq * self.config.liq_spike_threshold
        ).astype(int)

        # Liquidation imbalance (normalized)
        frame["liq_imbalance"] = (
            (frame["liq_long_volume"] - frame["liq_short_volume"])
            / avg_liq.replace(0.0, pd.NA)
        )

        return frame

    def _aggregate_liquidations(
        self,
        liq_data: pd.DataFrame,
        candles: pd.DataFrame,
        lookback: int,
    ) -> pd.Series:
        """Aggregate liquidation quantities into candle-aligned windows.

        For each candle, sums all liquidations within the lookback window.
        Uses searchsorted for efficient O(n log n) aggregation.
        """
        result = pd.Series(0.0, index=candles.index)

        candle_times = candles["close_time"].values
        liq_times = liq_data["timestamp"].values
        liq_qtys = liq_data["qty"].values

        # Sort liquidation times for searchsorted
        sort_idx = np.argsort(liq_times)
        sorted_times = liq_times[sort_idx]
        sorted_qtys = liq_qtys[sort_idx]

        for i in range(len(candles)):
            t_current = candle_times[i]
            t_start = t_current - pd.Timedelta(hours=lookback)

            # Use searchsorted to find the range [t_start, t_current]
            idx_lo = np.searchsorted(sorted_times, t_start, side="left")
            idx_hi = np.searchsorted(sorted_times, t_current, side="right")

            if idx_hi > idx_lo:
                result.iloc[i] = sorted_qtys[idx_lo:idx_hi].sum()

        return result
