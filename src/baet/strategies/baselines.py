from __future__ import annotations

import pandas as pd

from baet.core.models import StrategyMetadata
from baet.strategies.contracts import SIGNAL_COLUMNS, StrategyContract


def _normalize_confidence(values: pd.Series) -> pd.Series:
    values = values.fillna(0.0).astype("float64")
    max_abs = float(values.abs().max())
    if max_abs <= 0.0:
        return values
    return (values / max_abs).astype("float64")


def _build_base_signals(frame: pd.DataFrame) -> pd.DataFrame:
    signals = frame[["symbol", "timeframe", "close_time"]].copy()
    return signals.rename(columns={"close_time": "timestamp"})


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = ((up_move > down_move) & (up_move > 0.0)) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0.0)) * down_move

    tr_components = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    )
    tr = tr_components.max(axis=1)
    atr = tr.rolling(period).mean()

    plus_di = 100.0 * plus_dm.rolling(period).sum() / atr.replace(0.0, pd.NA)
    minus_di = 100.0 * minus_dm.rolling(period).sum() / atr.replace(0.0, pd.NA)
    directional_index = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, pd.NA)
    dx = 100.0 * directional_index
    adx = dx.rolling(period).mean()
    return adx.fillna(0.0), plus_di.fillna(0.0), minus_di.fillna(0.0)


def build_buy_and_hold_signals(frame: pd.DataFrame) -> pd.DataFrame:
    signals = _build_base_signals(frame)
    signals["action"] = "BUY"
    signals["target_position"] = 1.0
    signals["confidence"] = 1.0
    signals["size_hint"] = 1.0
    signals["strategy_name"] = "buy_and_hold"
    signals["reason"] = "always_long"
    return signals[SIGNAL_COLUMNS]


def build_sma_crossover_signals(frame: pd.DataFrame, fast: int = 5, slow: int = 20) -> pd.DataFrame:
    fast_sma = frame["close"].rolling(fast).mean()
    slow_sma = frame["close"].rolling(slow).mean()
    long_mask = fast_sma > slow_sma

    signals = _build_base_signals(frame)
    signals["action"] = long_mask.map({True: "BUY", False: "HOLD"})
    signals["target_position"] = long_mask.astype("float64")
    signals["confidence"] = _normalize_confidence((fast_sma - slow_sma).abs())
    signals["size_hint"] = 1.0
    signals["strategy_name"] = "sma_crossover"
    signals["reason"] = "fast_above_slow"
    return signals[SIGNAL_COLUMNS]


class BuyAndHoldStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="buy_and_hold",
        category="baseline",
        version="1.0.0",
        description="Always targets a long position for supported bars.",
    )

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        signals = _build_base_signals(frame)
        signals["action"] = "BUY"
        signals["target_position"] = 1.0
        signals["confidence"] = 1.0
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "always_long"
        return signals[SIGNAL_COLUMNS]


class SmaCrossoverStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="sma_crossover",
        category="baseline",
        version="1.0.0",
        description="Simple moving-average crossover baseline strategy.",
    )

    def __init__(self, fast: int = 5, slow: int = 20) -> None:
        self.fast = fast
        self.slow = slow

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        fast_sma = frame["close"].rolling(self.fast).mean()
        slow_sma = frame["close"].rolling(self.slow).mean()
        long_mask = fast_sma > slow_sma

        signals = _build_base_signals(frame)
        signals["action"] = long_mask.map({True: "BUY", False: "HOLD"})
        signals["target_position"] = long_mask.astype("float64")
        signals["confidence"] = _normalize_confidence((fast_sma - slow_sma).abs())
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "fast_above_slow"
        return signals[SIGNAL_COLUMNS]


class RsiMeanReversionStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="rsi_mean_reversion",
        category="baseline",
        version="1.0.0",
        description="Mean reversion strategy that buys on oversold RSI conditions.",
    )

    def __init__(self, period: int = 14, oversold: int = 30) -> None:
        self.period = period
        self.oversold = oversold

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        rsi = _rsi(frame["close"], self.period)
        long_mask = rsi < self.oversold
        confidence = ((self.oversold - rsi).clip(lower=0.0) / float(self.oversold)).fillna(0.0)

        signals = _build_base_signals(frame)
        signals["action"] = long_mask.map({True: "BUY", False: "HOLD"})
        signals["target_position"] = long_mask.astype("float64")
        signals["confidence"] = confidence
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "rsi_oversold"
        return signals[SIGNAL_COLUMNS]


class BollingerBandsStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="bollinger_bands",
        category="baseline",
        version="1.0.0",
        description="Mean reversion strategy that buys when price drops below the lower Bollinger Band.",
    )

    def __init__(self, window: int = 20, multiplier: float = 2.0) -> None:
        self.window = window
        self.multiplier = multiplier

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        sma = frame["close"].rolling(self.window).mean()
        std = frame["close"].rolling(self.window).std(ddof=0)
        lower_band = sma - self.multiplier * std
        long_mask = frame["close"] < lower_band
        confidence = ((lower_band - frame["close"]) / frame["close"]).clip(lower=0.0).fillna(0.0)

        signals = _build_base_signals(frame)
        signals["action"] = long_mask.map({True: "BUY", False: "HOLD"})
        signals["target_position"] = long_mask.astype("float64")
        signals["confidence"] = confidence
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "below_lower_band"
        return signals[SIGNAL_COLUMNS]


class EmaCrossoverStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="ema_crossover",
        category="baseline",
        version="1.0.0",
        description="Exponential moving-average crossover strategy.",
    )

    def __init__(self, fast: int = 8, slow: int = 21) -> None:
        self.fast = fast
        self.slow = slow

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        fast_ema = frame["close"].ewm(span=self.fast, adjust=False).mean()
        slow_ema = frame["close"].ewm(span=self.slow, adjust=False).mean()
        long_mask = fast_ema > slow_ema

        signals = _build_base_signals(frame)
        signals["action"] = long_mask.map({True: "BUY", False: "HOLD"})
        signals["target_position"] = long_mask.astype("float64")
        signals["confidence"] = _normalize_confidence((fast_ema - slow_ema).abs())
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "ema_fast_above_slow"
        return signals[SIGNAL_COLUMNS]


class BreakoutMomentumStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="breakout_momentum",
        category="baseline",
        version="1.0.0",
        description="Momentum strategy that buys when price breaks above recent resistance.",
    )

    def __init__(self, window: int = 20) -> None:
        self.window = window

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        prior_high = frame["high"].rolling(self.window, min_periods=1).max().shift(1)
        long_mask = frame["close"] > prior_high
        confidence = ((frame["close"] - prior_high) / prior_high).clip(lower=0.0).fillna(0.0)

        signals = _build_base_signals(frame)
        signals["action"] = long_mask.map({True: "BUY", False: "HOLD"})
        signals["target_position"] = long_mask.astype("float64")
        signals["confidence"] = confidence
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "breakout_above_resistance"
        return signals[SIGNAL_COLUMNS]


class AdxTrendFilterStrategy(StrategyContract):
    metadata = StrategyMetadata(
        name="adx_trend_filter",
        category="baseline",
        version="1.0.0",
        description="Trend filter strategy that buys when ADX confirms rising directional momentum.",
    )

    def __init__(self, period: int = 14, adx_threshold: float = 20.0) -> None:
        self.period = period
        self.adx_threshold = float(adx_threshold)

    def supports(self, symbol: str, timeframe: str) -> bool:
        return bool(symbol and timeframe)

    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        adx, plus_di, minus_di = _adx(frame["high"], frame["low"], frame["close"], self.period)
        long_mask = (adx > self.adx_threshold) & (plus_di > minus_di)
        confidence = ((adx - self.adx_threshold) / self.adx_threshold).clip(lower=0.0).fillna(0.0)

        signals = _build_base_signals(frame)
        signals["action"] = long_mask.map({True: "BUY", False: "HOLD"})
        signals["target_position"] = long_mask.astype("float64")
        signals["confidence"] = confidence
        signals["size_hint"] = 1.0
        signals["strategy_name"] = self.metadata.name
        signals["reason"] = "adx_trend_confirmed"
        return signals[SIGNAL_COLUMNS]


STRATEGY_CLASSES = [
    BuyAndHoldStrategy,
    SmaCrossoverStrategy,
    RsiMeanReversionStrategy,
    BollingerBandsStrategy,
    EmaCrossoverStrategy,
    BreakoutMomentumStrategy,
    AdxTrendFilterStrategy,
]
