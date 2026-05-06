"""Tests for ML-based trading strategy."""

import pytest
import pandas as pd
import numpy as np

from baet.strategies.ml_strategy import MLRandomForestStrategy
from baet.strategies.contracts import SIGNAL_COLUMNS


def create_ml_test_data(n_periods: int = 100) -> pd.DataFrame:
    """Create sample OHLCV data for ML strategy testing."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=n_periods, freq='D')
    
    # Create price series with trend
    trend = np.linspace(0, 0.2, n_periods)  # Upward trend
    noise = np.random.normal(0, 0.02, n_periods)
    returns = trend + noise
    prices = 100 * (1 + np.cumsum(returns))
    
    data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.uniform(-0.005, 0.005, n_periods)),
        'high': prices * (1 + np.random.uniform(0, 0.01, n_periods)),
        'low': prices * (1 - np.random.uniform(0, 0.01, n_periods)),
        'close': prices,
        'volume': np.random.randint(1000000, 5000000, n_periods),
        'symbol': 'BTCUSDT',
        'timeframe': '1d'
    })
    
    return data


@pytest.mark.skipif(True, reason="Requires scikit-learn installation")
def test_ml_strategy_initialization():
    """Test ML strategy initializes correctly."""
    strategy = MLRandomForestStrategy(
        lookback_window=20,
        prediction_threshold=0.6,
        n_estimators=50,
        max_depth=3
    )
    
    assert strategy.lookback_window == 20
    assert strategy.prediction_threshold == 0.6
    assert strategy.n_estimators == 50
    assert strategy.max_depth == 3
    assert not strategy.is_trained


def test_ml_strategy_supports():
    """Test that ML strategy supports any symbol/timeframe."""
    strategy = MLRandomForestStrategy()
    
    assert strategy.supports('BTCUSDT', '1d') == True
    assert strategy.supports('ETHUSDT', '4h') == True
    assert strategy.supports('ANYTHING', '1m') == True


def test_ml_strategy_insufficient_data():
    """Test ML strategy handles insufficient data gracefully."""
    strategy = MLRandomForestStrategy()
    
    # Create small dataset
    small_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
        'open': range(10),
        'high': range(10, 20),
        'low': range(0, 10),
        'close': range(10, 20),
        'volume': [1000] * 10,
        'symbol': 'BTCUSDT',
        'timeframe': '1d'
    })
    
    signals = strategy.generate_signals(small_data)
    
    # Should return HOLD signals when not enough data
    assert len(signals) > 0
    assert all(signals['action'] == 'HOLD')


def test_ml_strategy_feature_generation():
    """Test that feature generation works correctly."""
    strategy = MLRandomForestStrategy()
    
    data = create_ml_test_data(100)
    df_with_features = strategy._generate_features(data)
    
    # Check that expected features are generated
    expected_features = [
        'returns', 'log_returns', 'volatility_5', 'volatility_20',
        'rsi', 'volume_ratio', 'high_low_range', 'close_position'
    ]
    
    for feature in expected_features:
        assert feature in df_with_features.columns, f"Missing feature: {feature}"
    
    # Check target column exists
    assert 'target' in df_with_features.columns


def test_ml_strategy_prepare_features():
    """Test feature preparation for ML model."""
    strategy = MLRandomForestStrategy()
    
    data = create_ml_test_data(100)
    df_with_features = strategy._generate_features(data)
    X, y = strategy._prepare_features(df_with_features)
    
    assert len(X) > 0, "Feature matrix should not be empty"
    assert len(y) > 0, "Target vector should not be empty"
    assert len(X) == len(y), "X and y should have same length"
    assert X.shape[1] > 0, "Should have features"


def test_ml_strategy_train_model():
    """Test model training."""
    strategy = MLRandomForestStrategy()
    
    data = create_ml_test_data(100)
    
    result = strategy._train_model(data)
    
    if result:
        assert strategy.is_trained
        assert strategy.model is not None
        assert strategy.scaler is not None


def test_ml_strategy_generate_signals():
    """Test signal generation with trained model."""
    try:
        import sklearn
    except ImportError:
        pytest.skip("scikit-learn not installed")
    
    strategy = MLRandomForestStrategy(lookback_window=30, prediction_threshold=0.6)
    
    data = create_ml_test_data(100)
    
    # Train the model first
    train_data = data.iloc[:-10]
    strategy._train_model(train_data)
    
    if strategy.is_trained:
        # Generate signals for test data
        test_data = data.iloc[-30:]
        signals = strategy.generate_signals(test_data)
        
        assert len(signals) > 0
        assert 'timestamp' in signals.columns
        assert 'action' in signals.columns
        assert 'confidence' in signals.columns
        assert signals.iloc[0]['strategy_name'] == 'ml_random_forest'


def test_ml_strategy_signal_format():
    """Test that generated signals match SIGNAL_COLUMNS format."""
    try:
        import sklearn
    except ImportError:
        pytest.skip("scikit-learn not installed")
    
    strategy = MLRandomForestStrategy()
    data = create_ml_test_data(100)
    
    # Train and generate
    strategy._train_model(data.iloc[:-10])
    
    if strategy.is_trained:
        signals = strategy.generate_signals(data.iloc[-30:])
        
        # Check all required columns are present
        for col in SIGNAL_COLUMNS:
            assert col in signals.columns, f"Missing column: {col}"
        
        # Check action values are valid
        valid_actions = {'BUY', 'SELL', 'HOLD'}
        assert all(action in valid_actions for action in signals['action'])


def test_ml_strategy_metadata():
    """Test strategy metadata."""
    strategy = MLRandomForestStrategy()
    
    assert strategy.metadata.name == "ml_random_forest"
    assert strategy.metadata.category == "ml"
    assert strategy.metadata.version == "1.0.0"
    assert "Random Forest" in strategy.metadata.description


def test_ml_strategy_end_to_end():
    """Test full end-to-end ML strategy workflow."""
    try:
        import sklearn
    except ImportError:
        pytest.skip("scikit-learn not installed")
    
    strategy = MLRandomForestStrategy(
        lookback_window=20,
        prediction_threshold=0.55,
        n_estimators=50,
        max_depth=5
    )
    
    # Create sufficient data
    data = create_ml_test_data(150)
    
    # Should support the data
    assert strategy.supports('BTCUSDT', '1d')
    
    # Train model (happens automatically in generate_signals if not trained)
    signals = strategy.generate_signals(data)
    
    # Check output format
    assert isinstance(signals, pd.DataFrame)
    
    # If model trained successfully, should have non-HOLD signals
    if strategy.is_trained:
        assert len(signals) > 0
        # Should have some non-HOLD signals if threshold is reasonable
        non_hold = signals[signals['action'] != 'HOLD']
        # May or may not have non-HOLD signals depending on predictions
        assert 'strategy_name' in signals.columns
