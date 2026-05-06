"""Regime detection for adaptive strategy selection."""

from __future__ import annotations

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

from baet.core.models import RegimeLabel, RegimeMetadata


class RegimeDetector(ABC):
    """Base class for market regime detectors."""
    
    metadata: RegimeMetadata
    
    @abstractmethod
    def detect(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Detect market regimes from price/volume data.
        
        Args:
            data: DataFrame with columns [timestamp, open, high, low, close, volume]
            
        Returns:
            DataFrame with columns [timestamp, regime] where regime is a RegimeLabel
        """


class VolatilityTrendRegimeDetector(RegimeDetector):
    """Detect regimes based on volatility and trend strength."""
    
    metadata = RegimeMetadata(
        name="volatility_trend_detector",
        category="technical",
        version="1.0.0",
        description="Classifies market regimes using volatility and trend indicators"
    )
    
    def __init__(self, volatility_window: int = 20, trend_window: int = 50):
        self.volatility_window = volatility_window
        self.trend_window = trend_window
        
    def detect(self, data: pd.DataFrame) -> pd.DataFrame:
        """Detect regimes using rolling volatility and trend strength."""
        df = data.copy()
        
        # Calculate returns
        df['returns'] = df['close'].pct_change()
        
        # Calculate rolling volatility (annualized)
        df['volatility'] = df['returns'].rolling(window=self.volatility_window).std() * np.sqrt(252)
        
        # Calculate trend strength using ADX-like metric (simplified)
        # Using difference between close and moving average
        df['ma'] = df['close'].rolling(window=self.trend_window).mean()
        df['trend_strength'] = abs(df['close'] - df['ma']) / df['ma']
        
        # Calculate volatility and trend percentiles for classification
        # Use expanding windows for reproducibility
        df['vol_percentile'] = df['volatility'].expanding().apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5
        )
        df['trend_percentile'] = df['trend_strength'].expanding().apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else 0.5
        )
        
        # Classify regimes
        def classify_regime(row):
            if pd.isna(row['vol_percentile']) or pd.isna(row['trend_percentile']):
                return RegimeLabel.RANGING
            
            vol_high = row['vol_percentile'] > 0.7
            trend_strong = row['trend_percentile'] > 0.6
            
            if vol_high:
                if trend_strong:
                    return RegimeLabel.TRENDING
                else:
                    return RegimeLabel.HIGH_VOLATILITY
            else:
                if trend_strong:
                    return RegimeLabel.TRENDING
                else:
                    return RegimeLabel.LOW_VOLATILITY
        
        df['regime'] = df.apply(classify_regime, axis=1)
        
        # Return only timestamp and regime
        result = df[['timestamp', 'regime']].copy()
        return result
