"""Tests for ensemble decision layer."""

import pytest
import pandas as pd
import numpy as np

from baet.strategies.ensemble import EnsembleConfig, StaticEnsemble, StrategyWeight
from baet.core.models import RegimeLabel, StrategyMetadata


def create_sample_signals(strategy_name: str, n_periods: int = 10) -> pd.DataFrame:
    """Create sample signal data for testing."""
    dates = pd.date_range('2024-01-01', periods=n_periods, freq='D')
    
    signals = []
    for i, date in enumerate(dates):
        action = 'BUY' if i % 3 == 0 else ('SELL' if i % 3 == 1 else 'HOLD')
        signals.append({
            'timestamp': date,
            'symbol': 'BTCUSDT',
            'timeframe': '1d',
            'action': action,
            'target_position': 1.0 if action == 'BUY' else (-1.0 if action == 'SELL' else 0.0),
            'confidence': 0.7 + np.random.uniform(-0.2, 0.2),
            'size_hint': 0.1,
            'strategy_name': strategy_name,
            'reason': f'{strategy_name} signal at {date}'
        })
    
    return pd.DataFrame(signals)


def test_ensemble_config_creation():
    """Test that EnsembleConfig can be created correctly."""
    weights = [
        StrategyWeight(strategy_name='sma_crossover', weight=1.0),
        StrategyWeight(strategy_name='rsi_mean_reversion', weight=0.8)
    ]
    
    config = EnsembleConfig(
        name='test_ensemble',
        strategy_weights=weights,
        default_weight=0.5
    )
    
    assert config.name == 'test_ensemble'
    assert len(config.strategy_weights) == 2
    assert config.default_weight == 0.5


def test_ensemble_config_get_weight():
    """Test weight retrieval with and without regime adjustments."""
    weights = [
        StrategyWeight(strategy_name='strategy_a', weight=1.5),
        StrategyWeight(strategy_name='strategy_b', weight=0.8)
    ]
    
    regime_weights = {
        RegimeLabel.TRENDING: {'strategy_a': 2.0, 'strategy_b': 0.5},
        RegimeLabel.RANGING: {'strategy_a': 0.5, 'strategy_b': 1.5}
    }
    
    config = EnsembleConfig(
        name='regime_ensemble',
        strategy_weights=weights,
        regime_weights=regime_weights,
        default_weight=1.0
    )
    
    # Test without regime
    assert config.get_weight('strategy_a') == 1.5
    assert config.get_weight('strategy_b') == 0.8
    assert config.get_weight('unknown_strategy') == 1.0  # default
    
    # Test with regime
    assert config.get_weight('strategy_a', RegimeLabel.TRENDING) == 2.0
    assert config.get_weight('strategy_b', RegimeLabel.TRENDING) == 0.5
    assert config.get_weight('strategy_a', RegimeLabel.RANGING) == 0.5
    assert config.get_weight('strategy_b', RegimeLabel.RANGING) == 1.5


def test_static_ensemble_combine_signals():
    """Test that StaticEnsemble correctly combines multiple strategy signals."""
    config = EnsembleConfig(name='test_ensemble')
    ensemble = StaticEnsemble(config)
    
    # Create signals from two strategies
    signals_a = create_sample_signals('strategy_a', 10)
    signals_b = create_sample_signals('strategy_b', 10)
    
    strategy_signals = {
        'strategy_a': signals_a,
        'strategy_b': signals_b
    }
    
    combined = ensemble.combine_signals(strategy_signals)
    
    # Should have signals from both strategies
    assert len(combined) == 20  # 10 from each
    assert set(combined['strategy_name'].unique()) == {'strategy_a', 'strategy_b'}
    assert 'timestamp' in combined.columns
    assert 'action' in combined.columns


def test_static_ensemble_with_regime():
    """Test that ensemble applies regime-based weighting."""
    weights = [
        StrategyWeight(strategy_name='strategy_a', weight=1.0),
        StrategyWeight(strategy_name='strategy_b', weight=1.0)
    ]
    
    regime_weights = {
        RegimeLabel.TRENDING: {'strategy_a': 2.0, 'strategy_b': 0.5}
    }
    
    config = EnsembleConfig(
        name='regime_ensemble',
        strategy_weights=weights,
        regime_weights=regime_weights
    )
    ensemble = StaticEnsemble(config)
    
    # Create signals
    signals_a = create_sample_signals('strategy_a', 5)
    signals_b = create_sample_signals('strategy_b', 5)
    
    # Create regime data
    regime_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=5, freq='D'),
        'regime': [RegimeLabel.TRENDING] * 5
    })
    
    strategy_signals = {'strategy_a': signals_a, 'strategy_b': signals_b}
    combined = ensemble.combine_signals(strategy_signals, regime_data)
    
    # Check that regime-based weighting was applied (confidence adjusted)
    strategy_a_signals = combined[combined['strategy_name'] == 'strategy_a']
    strategy_b_signals = combined[combined['strategy_name'] == 'strategy_b']
    
    # In TRENDING regime, strategy_a should have higher weight (2.0 vs 0.5)
    assert not strategy_a_signals.empty
    assert not strategy_b_signals.empty


def test_static_ensemble_make_decisions():
    """Test that ensemble makes final decisions from combined signals."""
    config = EnsembleConfig(name='test_ensemble')
    ensemble = StaticEnsemble(config)
    
    # Create signals that will produce a clear decision
    dates = pd.date_range('2024-01-01', periods=3, freq='D')
    
    signals = []
    for date in dates:
        # Add multiple BUY signals to ensure BUY wins
        signals.extend([
            {
                'timestamp': date,
                'symbol': 'BTCUSDT',
                'timeframe': '1d',
                'action': 'BUY',
                'target_position': 1.0,
                'confidence': 0.9,
                'size_hint': 0.1,
                'strategy_name': 'strategy_a',
                'reason': 'Strong buy signal'
            },
            {
                'timestamp': date,
                'symbol': 'BTCUSDT',
                'timeframe': '1d',
                'action': 'BUY',
                'target_position': 1.0,
                'confidence': 0.8,
                'size_hint': 0.1,
                'strategy_name': 'strategy_b',
                'reason': 'Buy signal'
            }
        ])
    
    combined = pd.DataFrame(signals)
    decisions = ensemble.make_decisions(combined)
    
    assert len(decisions) == 3  # One decision per timestamp
    assert all(decisions['action'] == 'BUY')
    assert all(decisions['symbol'] == 'BTCUSDT')
    assert 'strategy_name' in decisions.columns


def test_static_ensemble_empty_signals():
    """Test ensemble handling of empty signal inputs."""
    config = EnsembleConfig(name='test_ensemble')
    ensemble = StaticEnsemble(config)
    
    # Test with empty dict
    combined = ensemble.combine_signals({})
    assert combined.empty
    assert list(combined.columns) == list(ensemble.combine_signals({}).columns)
    
    # Test make_decisions with empty DataFrame
    empty_df = pd.DataFrame(columns=['timestamp', 'symbol', 'timeframe', 'action', 
                                     'target_position', 'confidence', 'size_hint', 
                                     'strategy_name', 'reason'])
    decisions = ensemble.make_decisions(empty_df)
    assert decisions.empty


def test_static_ensemble_end_to_end():
    """Test full end-to-end ensemble workflow."""
    # Create ensemble with regime-aware weights
    weights = [
        StrategyWeight(strategy_name='trend_follower', weight=1.0),
        StrategyWeight(strategy_name='mean_reverter', weight=1.0)
    ]
    
    regime_weights = {
        RegimeLabel.TRENDING: {'trend_follower': 2.0, 'mean_reverter': 0.3},
        RegimeLabel.RANGING: {'trend_follower': 0.3, 'mean_reverter': 2.0}
    }
    
    config = EnsembleConfig(
        name='adaptive_ensemble',
        strategy_weights=weights,
        regime_weights=regime_weights
    )
    ensemble = StaticEnsemble(config)
    
    # Create signals for different timestamps
    n_periods = 20
    dates = pd.date_range('2024-01-01', periods=n_periods, freq='D')
    
    trend_signals = []
    mean_signals = []
    
    for i, date in enumerate(dates):
        # Alternate actions
        action = 'BUY' if i % 2 == 0 else 'SELL'
        trend_signals.append({
            'timestamp': date,
            'symbol': 'BTCUSDT',
            'timeframe': '1d',
            'action': action,
            'target_position': 1.0 if action == 'BUY' else -1.0,
            'confidence': 0.8,
            'size_hint': 0.1,
            'strategy_name': 'trend_follower',
            'reason': f'Trend signal {action}'
        })
        mean_signals.append({
            'timestamp': date,
            'symbol': 'BTCUSDT',
            'timeframe': '1d',
            'action': 'HOLD',
            'target_position': 0.0,
            'confidence': 0.6,
            'size_hint': 0.05,
            'strategy_name': 'mean_reverter',
            'reason': f'Mean reversion HOLD'
        })
    
    strategy_signals = {
        'trend_follower': pd.DataFrame(trend_signals),
        'mean_reverter': pd.DataFrame(mean_signals)
    }
    
    # Create regime data (first half trending, second half ranging)
    regime_data = pd.DataFrame({
        'timestamp': dates,
        'regime': [RegimeLabel.TRENDING] * 10 + [RegimeLabel.RANGING] * 10
    })
    
    # Combine signals
    combined = ensemble.combine_signals(strategy_signals, regime_data)
    assert len(combined) == n_periods * 2  # Both strategies
    
    # Make decisions
    decisions = ensemble.make_decisions(combined)
    assert len(decisions) == n_periods  # One decision per timestamp
    assert all(decisions['strategy_name'] == 'adaptive_ensemble')
