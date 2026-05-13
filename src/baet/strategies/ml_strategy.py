"""Machine Learning based trading strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from baet.core.models import StrategyMetadata
from baet.strategies.contracts import SIGNAL_COLUMNS, StrategyContract


@dataclass
class MLStrategyMetadata:
    """Metadata for ML strategy."""
    name: str = "ml_random_forest"
    category: str = "ml"
    version: str = "1.0.0"
    description: str = "Random Forest classifier for trend prediction"


class MLRandomForestStrategy(StrategyContract):
    """Machine Learning strategy using Random Forest classifier."""
    
    metadata = StrategyMetadata(
        name="ml_random_forest",
        category="ml",
        version="1.0.0",
        description="Predicts price direction using Random Forest on technical features"
    )
    
    def __init__(self, lookback_window: int = 20, prediction_threshold: float = 0.6,
                 n_estimators: int = 100, max_depth: Optional[int] = 5):
        """
        Initialize ML strategy.
        
        Args:
            lookback_window: Number of periods to use for feature generation
            prediction_threshold: Confidence threshold for making trades
            n_estimators: Number of trees in Random Forest
            max_depth: Maximum depth of trees
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for MLRandomForestStrategy. Install with: pip install scikit-learn")
        
        self.lookback_window = lookback_window
        self.prediction_threshold = prediction_threshold
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_columns = []
        
    def supports(self, symbol: str, timeframe: str) -> bool:
        """Return whether the strategy supports the requested market slice."""
        # Supports any symbol/timeframe with enough data
        return True
    
    def _generate_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate technical features for ML model."""
        df = data.copy()
        
        # Price-based features
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Moving averages
        for period in [5, 10, 20, 50]:
            df[f'ma_{period}'] = df['close'].rolling(window=period).mean()
            df[f'ma_ratio_{period}'] = df['close'] / df[f'ma_{period}']
        
        # Volatility features
        df['volatility_5'] = df['returns'].rolling(window=5).std()
        df['volatility_20'] = df['returns'].rolling(window=20).std()
        
        # RSI-like feature
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Volume features
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # Price position features
        df['high_low_range'] = (df['high'] - df['low']) / df['close']
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        
        # Target: future direction (1 if price goes up in next period, 0 otherwise)
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        
        return df
    
    def _prepare_features(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Prepare feature matrix and target vector."""
        feature_cols = [
            'returns', 'log_returns',
            'ma_ratio_5', 'ma_ratio_10', 'ma_ratio_20', 'ma_ratio_50',
            'volatility_5', 'volatility_20',
            'rsi', 'volume_ratio',
            'high_low_range', 'close_position'
        ]
        
        # Store feature columns for later use
        self.feature_columns = feature_cols
        
        # Drop rows with NaN values
        clean_df = df[feature_cols + ['target']].dropna()
        
        if len(clean_df) == 0:
            return np.array([]), np.array([])
        
        X = clean_df[feature_cols].values
        y = clean_df['target'].values
        
        return X, y
    
    def _train_model(self, data: pd.DataFrame):
        """Train the ML model on historical data."""
        df = self._generate_features(data)
        X, y = self._prepare_features(df)
        
        if len(X) < 50:  # Need minimum samples
            return False
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model.fit(X_scaled, y)
        self.is_trained = True
        return True
    
    def generate_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals using ML predictions."""
        if len(frame) < self.lookback_window + 20:
            # Not enough data, return HOLD signals
            return self._generate_hold_signals(frame)
        
        # Train model if not trained
        if not self.is_trained:
            train_data = frame.iloc[:-10]  # Train on all but last 10 periods
            self._train_model(train_data)
        
        if not self.is_trained:
            return self._generate_hold_signals(frame)
        
        # Generate features for prediction
        df = self._generate_features(frame)
        
        # Prepare features for prediction (use last lookback_window periods)
        pred_df = df.tail(self.lookback_window).copy()
        
        if len(pred_df) < self.lookback_window:
            return self._generate_hold_signals(frame)
        
        # Get features
        feature_cols = self.feature_columns
        if not feature_cols:
            # Fallback to default feature columns
            feature_cols = [
                'returns', 'log_returns',
                'ma_ratio_5', 'ma_ratio_10', 'ma_ratio_20', 'ma_ratio_50',
                'volatility_5', 'volatility_20',
                'rsi', 'volume_ratio',
                'high_low_range', 'close_position'
            ]
        
        # Check if we have the required columns
        available_cols = [col for col in feature_cols if col in pred_df.columns]
        if not available_cols:
            return self._generate_hold_signals(frame)
        
        X_pred = pred_df[available_cols].dropna()
        
        if len(X_pred) == 0:
            return self._generate_hold_signals(frame)
        
        # Scale and predict
        X_scaled = self.scaler.transform(X_pred)
        probabilities = self.model.predict_proba(X_scaled)
        
        # Last prediction is for the most recent period
        latest_prob = probabilities[-1]
        buy_prob = latest_prob[1] if len(latest_prob) > 1 else 0.5
        
        # Generate signal for the latest timestamp
        latest_timestamp = pred_df.iloc[-1]['timestamp']
        
        if buy_prob > self.prediction_threshold:
            action = 'BUY'
            target_position = 1.0
            confidence = buy_prob
            reason = f"ML predicts UP with {buy_prob:.2f} probability"
        elif buy_prob < (1 - self.prediction_threshold):
            action = 'SELL'
            target_position = -1.0
            confidence = 1 - buy_prob
            reason = f"ML predicts DOWN with {1-buy_prob:.2f} probability"
        else:
            action = 'HOLD'
            target_position = 0.0
            confidence = 0.5
            reason = f"ML uncertain ({buy_prob:.2f}), holding"
        
        signal = pd.DataFrame([{
            'timestamp': latest_timestamp,
            'symbol': frame.iloc[-1]['symbol'] if 'symbol' in frame.columns else 'UNKNOWN',
            'timeframe': frame.iloc[-1]['timeframe'] if 'timeframe' in frame.columns else '1d',
            'action': action,
            'target_position': target_position,
            'confidence': confidence,
            'size_hint': 0.1,
            'strategy_name': self.metadata.name,
            'reason': reason
        }])
        
        return signal
    
    def _generate_hold_signals(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Generate HOLD signals when model can't predict."""
        if len(frame) == 0:
            return pd.DataFrame(columns=SIGNAL_COLUMNS)
        
        signals = []
        for _, row in frame.iterrows():
            signals.append({
                'timestamp': row['timestamp'],
                'symbol': row['symbol'] if 'symbol' in frame.columns else 'UNKNOWN',
                'timeframe': row['timeframe'] if 'timeframe' in frame.columns else '1d',
                'action': 'HOLD',
                'target_position': 0.0,
                'confidence': 0.5,
                'size_hint': 0.0,
                'strategy_name': self.metadata.name,
                'reason': 'ML model not ready or insufficient data'
            })
        
        return pd.DataFrame(signals)
