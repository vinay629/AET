from __future__ import annotations

import pandas as pd

from baet.config.models import FeatureConfig
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
