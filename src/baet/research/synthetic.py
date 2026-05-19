"""Synthetic market generator for BAET.

Generates controlled market environments for strategy testing:
- Trending (with/without mean reversion)
- Mean reverting (Ornstein-Uhlenbeck)
- Volatility clustering (GARCH-like)
- Jump diffusion
- Liquidity shocks
- Flash crashes
- Spread widening
- Regime transitions

All generators are deterministic given the same seed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SyntheticConfig:
    """Configuration for synthetic market generation."""
    n_bars: int = 1000
    initial_price: float = 100.0
    base_volatility: float = 0.01
    base_drift: float = 0.0
    seed: int = 42


def generate_trending(
    config: SyntheticConfig | None = None,
    trend_strength: float = 0.001,
    noise_ratio: float = 0.3,
) -> pd.DataFrame:
    """Generate trending market with optional mean reversion."""
    cfg = config or SyntheticConfig()
    rng = np.random.RandomState(cfg.seed)

    n = cfg.n_bars
    dt = 1.0

    # Trend component
    trend = np.cumsum(np.ones(n) * trend_strength + rng.randn(n) * cfg.base_volatility * noise_ratio)

    # Mean reversion component (pulls back to trend)
    prices = np.zeros(n)
    prices[0] = cfg.initial_price
    for i in range(1, n):
        mr_pull = -0.01 * (prices[i - 1] - cfg.initial_price - trend[i] * cfg.initial_price)
        prices[i] = prices[i - 1] * (1 + trend[i] * dt + mr_pull + rng.randn() * cfg.base_volatility * noise_ratio)

    prices = np.maximum(prices, 0.01)

    return _prices_to_ohlcv(prices, cfg, rng)


def generate_mean_reverting(
    config: SyntheticConfig | None = None,
    mean: float = 100.0,
    speed: float = 0.05,
    vol: float = 0.01,
) -> pd.DataFrame:
    """Generate mean-reverting market (Ornstein-Uhlenbeck)."""
    cfg = config or SyntheticConfig()
    rng = np.random.RandomState(cfg.seed)

    n = cfg.n_bars
    prices = np.zeros(n)
    prices[0] = mean

    for i in range(1, n):
        # OU process: dX = speed * (mean - X) * dt + vol * dW
        drift = speed * (mean - prices[i - 1])
        diffusion = vol * prices[i - 1] * rng.randn()
        prices[i] = prices[i - 1] + drift + diffusion

    prices = np.maximum(prices, 0.01)
    return _prices_to_ohlcv(prices, cfg, rng)


def generate_garch(
    config: SyntheticConfig | None = None,
    omega: float = 0.00001,
    alpha: float = 0.1,
    beta: float = 0.85,
) -> pd.DataFrame:
    """Generate market with GARCH(1,1) volatility clustering."""
    cfg = config or SyntheticConfig()
    rng = np.random.RandomState(cfg.seed)

    n = cfg.n_bars
    returns = np.zeros(n)
    variance = np.zeros(n)
    variance[0] = cfg.base_volatility ** 2

    for i in range(1, n):
        variance[i] = omega + alpha * returns[i - 1] ** 2 + beta * variance[i - 1]
        vol = np.sqrt(variance[i])
        returns[i] = cfg.base_drift + vol * rng.randn()

    prices = cfg.initial_price * np.exp(np.cumsum(returns))
    prices = np.maximum(prices, 0.01)
    return _prices_to_ohlcv(prices, cfg, rng)


def generate_jump_diffusion(
    config: SyntheticConfig | None = None,
    jump_intensity: float = 0.01,
    jump_mean: float = -0.02,
    jump_std: float = 0.03,
) -> pd.DataFrame:
    """Generate market with jump diffusion (Merton model)."""
    cfg = config or SyntheticConfig()
    rng = np.random.RandomState(cfg.seed)

    n = cfg.n_bars
    returns = np.zeros(n)

    for i in range(n):
        # Diffusion component
        diffusion = cfg.base_drift + cfg.base_volatility * rng.randn()

        # Jump component
        if rng.random() < jump_intensity:
            jump = jump_mean + jump_std * rng.randn()
        else:
            jump = 0

        returns[i] = diffusion + jump

    prices = cfg.initial_price * np.exp(np.cumsum(returns))
    prices = np.maximum(prices, 0.01)
    return _prices_to_ohlcv(prices, cfg, rng)


def generate_liquidity_shock(
    config: SyntheticConfig | None = None,
    shock_bar: int = 500,
    shock_magnitude: float = 0.05,
    recovery_bars: int = 50,
) -> pd.DataFrame:
    """Generate market with a liquidity shock (spread widening + price drop)."""
    cfg = config or SyntheticConfig()
    rng = np.random.RandomState(cfg.seed)

    n = cfg.n_bars
    returns = np.zeros(n)

    for i in range(n):
        returns[i] = cfg.base_drift + cfg.base_volatility * rng.randn()

    # Apply shock
    if shock_bar < n:
        # Immediate drop
        returns[shock_bar] -= shock_magnitude
        # Elevated volatility during shock
        for i in range(shock_bar + 1, min(shock_bar + recovery_bars, n)):
            vol_multiplier = 1 + (shock_magnitude * 10) * (1 - (i - shock_bar) / recovery_bars)
            returns[i] = cfg.base_drift + cfg.base_volatility * vol_multiplier * rng.randn()

    prices = cfg.initial_price * np.exp(np.cumsum(returns))
    prices = np.maximum(prices, 0.01)
    return _prices_to_ohlcv(prices, cfg, rng)


def generate_flash_crash(
    config: SyntheticConfig | None = None,
    crash_bar: int = 500,
    crash_magnitude: float = 0.15,
    recovery_pct: float = 0.7,
) -> pd.DataFrame:
    """Generate market with flash crash (rapid drop + partial recovery)."""
    cfg = config or SyntheticConfig()
    rng = np.random.RandomState(cfg.seed)

    n = cfg.n_bars
    returns = np.zeros(n)

    for i in range(n):
        returns[i] = cfg.base_drift + cfg.base_volatility * rng.randn()

    # Crash: rapid drop over 5 bars
    if crash_bar + 5 < n:
        for j in range(5):
            returns[crash_bar + j] -= crash_magnitude / 5

    # Partial recovery over next 20 bars
    recovery_start = crash_bar + 5
    recovery_end = min(recovery_start + 20, n)
    for i in range(recovery_start, recovery_end):
        recovery_return = (crash_magnitude * recovery_pct) / (recovery_end - recovery_start)
        returns[i] += recovery_return + cfg.base_volatility * 3 * rng.randn()

    prices = cfg.initial_price * np.exp(np.cumsum(returns))
    prices = np.maximum(prices, 0.01)
    return _prices_to_ohlcv(prices, cfg, rng)


def generate_regime_transition(
    config: SyntheticConfig | None = None,
    transition_bar: int = 500,
    from_regime: str = "low_vol",
    to_regime: str = "high_vol",
) -> pd.DataFrame:
    """Generate market with regime transition."""
    cfg = config or SyntheticConfig()
    rng = np.random.RandomState(cfg.seed)

    n = cfg.n_bars
    returns = np.zeros(n)

    # Regime parameters
    regime_params = {
        "low_vol": {"vol": 0.005, "drift": 0.0001},
        "high_vol": {"vol": 0.03, "drift": -0.0001},
        "trending": {"vol": 0.008, "drift": 0.001},
        "mean_reverting": {"vol": 0.01, "drift": 0.0},
        "panic": {"vol": 0.05, "drift": -0.001},
    }

    from_params = regime_params.get(from_regime, regime_params["low_vol"])
    to_params = regime_params.get(to_regime, regime_params["high_vol"])

    transition_length = 50  # Bars for smooth transition

    for i in range(n):
        if i < transition_bar:
            params = from_params
        elif i < transition_bar + transition_length:
            # Smooth interpolation
            t = (i - transition_bar) / transition_length
            vol = from_params["vol"] * (1 - t) + to_params["vol"] * t
            drift = from_params["drift"] * (1 - t) + to_params["drift"] * t
            returns[i] = drift + vol * rng.randn()
        else:
            returns[i] = to_params["drift"] + to_params["vol"] * rng.randn()

    prices = cfg.initial_price * np.exp(np.cumsum(returns))
    prices = np.maximum(prices, 0.01)
    return _prices_to_ohlcv(prices, cfg, rng)


def generate_spread_widening(
    config: SyntheticConfig | None = None,
    normal_spread_bps: float = 5.0,
    wide_spread_bps: float = 50.0,
    shock_bar: int = 500,
    duration: int = 100,
) -> pd.DataFrame:
    """Generate market with spread widening event."""
    cfg = config or SyntheticConfig()
    rng = np.random.RandomState(cfg.seed)

    n = cfg.n_bars
    returns = np.zeros(n)

    for i in range(n):
        returns[i] = cfg.base_drift + cfg.base_volatility * rng.randn()

    prices = cfg.initial_price * np.exp(np.cumsum(returns))
    prices = np.maximum(prices, 0.01)

    df = _prices_to_ohlcv(prices, cfg, rng)

    # Add spread column
    spread = np.full(n, normal_spread_bps)
    if shock_bar < n:
        end = min(shock_bar + duration, n)
        spread[shock_bar:end] = wide_spread_bps
        # Gradual recovery
        recovery = min(end + 50, n)
        for i in range(end, recovery):
            t = (i - end) / (recovery - end)
            spread[i] = wide_spread_bps * (1 - t) + normal_spread_bps * t

    df["spread_bps"] = spread
    return df


def _prices_to_ohlcv(
    prices: np.ndarray,
    config: SyntheticConfig,
    rng: np.random.RandomState,
) -> pd.DataFrame:
    """Convert price series to OHLCV DataFrame."""
    n = len(prices)
    vol = config.base_volatility

    # Generate OHLV from close prices
    close = prices
    high = close * (1 + abs(rng.randn(n)) * vol * 0.5)
    low = close * (1 - abs(rng.randn(n)) * vol * 0.5)
    open_price = close * (1 + rng.randn(n) * vol * 0.1)

    # Ensure OHLC consistency
    high = np.maximum(high, np.maximum(open_price, close))
    low = np.minimum(low, np.minimum(open_price, close))

    volume = rng.uniform(100, 1000, n) * (1 + abs(rng.randn(n)) * 0.5)

    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
