"""Tests for intelligence stack validation reporting."""

import pandas as pd

from baet.reporting.comparison import (
    build_intelligence_stack_comparison,
    build_regime_performance_report,
    validate_intelligence_stack,
)


def create_sample_metrics(strategy_names: list, category: str = 'baseline', 
                         sharpe_range: tuple = (0.5, 1.5)) -> pd.DataFrame:
    """Create sample metrics DataFrame for testing."""
    records = []
    for i, name in enumerate(strategy_names):
        records.append({
            'strategy_name': name,
            'category': category,
            'version': '1.0.0',
            'description': f'{category} strategy',
            'final_equity': 10000 + i * 1000,
            'total_return': 0.1 + i * 0.02,
            'trade_count': 20 + i,
            'mean_bar_return': 0.001,
            'max_drawdown': -0.1 - i * 0.02,
            'win_rate': 0.5 + i * 0.05,
            'average_trade_return': 0.02,
            'sharpe_ratio': sharpe_range[0] + (sharpe_range[1] - sharpe_range[0]) * i / len(strategy_names),
            'sortino_ratio': 1.0 + i * 0.1,
            'calmar_ratio': 0.8 + i * 0.05,
            'profit_factor': 1.5 + i * 0.1
        })
    
    return pd.DataFrame(records)


def test_build_intelligence_stack_comparison():
    """Test building intelligence stack comparison table."""
    baseline = create_sample_metrics(['sma_cross', 'rsi_reversal'], 'baseline', (0.5, 1.0))
    ensemble = create_sample_metrics(['static_ensemble', 'adaptive_ensemble'], 'ensemble', (0.8, 1.3))
    ml = create_sample_metrics(['ml_random_forest'], 'ml', (1.0, 1.5))
    
    comparison = build_intelligence_stack_comparison(baseline, ensemble, ml)
    
    assert not comparison.empty
    assert 'strategy_type' in comparison.columns
    assert set(comparison['strategy_type'].unique()) == {'baseline', 'ensemble', 'ml'}
    assert len(comparison) == 5  # 2 baseline + 2 ensemble + 1 ml


def test_build_intelligence_stack_empty():
    """Test with empty DataFrames."""
    empty = pd.DataFrame()
    baseline = create_sample_metrics(['sma'], 'baseline')
    
    # All empty
    result = build_intelligence_stack_comparison(empty, empty, empty)
    assert result.empty
    
    # Some empty
    result = build_intelligence_stack_comparison(baseline, empty, empty)
    assert not result.empty
    assert result['strategy_type'].iloc[0] == 'baseline'


def test_build_intelligence_stack_improvement():
    """Test that improvement metrics are calculated."""
    baseline = create_sample_metrics(['sma'], 'baseline', (0.5, 0.5))
    ensemble = create_sample_metrics(['ensemble'], 'ensemble', (1.0, 1.0))  # Better
    
    comparison = build_intelligence_stack_comparison(baseline, ensemble, pd.DataFrame())
    
    assert 'ensemble_improvement' in comparison.columns
    # Ensemble should show improvement
    ensemble_row = comparison[comparison['strategy_type'] == 'ensemble'].iloc[0]
    assert ensemble_row['ensemble_improvement'] > 0  # Should be positive improvement


def test_build_regime_performance_report():
    """Test building regime performance report."""
    regime_metrics = {
        'TRENDING': create_sample_metrics(['sma_trend'], 'baseline', (1.0, 1.2)),
        'RANGING': create_sample_metrics(['rsi_range'], 'baseline', (0.8, 1.0)),
        'HIGH_VOLATILITY': create_sample_metrics(['vol_strategy'], 'baseline', (0.5, 0.7))
    }
    
    report = build_regime_performance_report(regime_metrics)
    
    assert not report.empty
    assert len(report) == 3
    assert 'regime' in report.columns
    assert 'avg_sharpe' in report.columns
    assert 'best_strategy' in report.columns


def test_build_regime_performance_empty():
    """Test with empty regime metrics."""
    report = build_regime_performance_report({})
    assert report.empty
    
    report = build_regime_performance_report({'TRENDING': pd.DataFrame()})
    assert report.empty


def test_validate_intelligence_stack():
    """Test intelligence stack validation."""
    baseline = create_sample_metrics(['sma', 'rsi'], 'baseline', (0.5, 0.8))
    ensemble = create_sample_metrics(['static_ens'], 'ensemble', (1.0, 1.2))  # Better
    ml = create_sample_metrics(['ml_rf'], 'ml', (0.9, 1.1))  # Also better
    
    validation = validate_intelligence_stack(baseline, ensemble, ml)
    
    assert validation['baseline_count'] == 2
    assert validation['ensemble_count'] == 1
    assert validation['ml_count'] == 1
    assert validation['ensemble_improves_sharpe']
    assert validation['ml_improves_sharpe']
    assert validation['validation_passed']


def test_validate_intelligence_stack_no_improvement():
    """Test validation when there's no improvement."""
    baseline = create_sample_metrics(['sma', 'rsi'], 'baseline', (1.0, 1.2))
    ensemble = create_sample_metrics(['static_ens'], 'ensemble', (0.5, 0.8))  # Worse
    ml = create_sample_metrics(['ml_rf'], 'ml', (0.6, 0.9))  # Also worse
    
    validation = validate_intelligence_stack(baseline, ensemble, ml, min_improvement=0.0)
    
    assert not validation['ensemble_improves_sharpe']
    assert not validation['ml_improves_sharpe']
    assert not validation['validation_passed']


def test_validate_intelligence_stack_empty():
    """Test validation with empty inputs."""
    empty = pd.DataFrame()
    baseline = create_sample_metrics(['sma'], 'baseline')
    
    validation = validate_intelligence_stack(empty, empty, empty)
    
    assert validation['baseline_count'] == 0
    assert validation['ensemble_count'] == 0
    assert validation['ml_count'] == 0
    assert not validation['validation_passed']
    
    validation = validate_intelligence_stack(baseline, empty, empty)
    assert validation['baseline_count'] == 1
    assert validation['ensemble_count'] == 0


def test_validate_intelligence_stack_mixed():
    """Test validation with mixed empty/non-empty inputs."""
    baseline = create_sample_metrics(['sma'], 'baseline', (0.5, 0.5))
    ensemble = create_sample_metrics(['ens'], 'ensemble', (1.0, 1.0))
    
    # Only baseline and ensemble, no ML
    validation = validate_intelligence_stack(baseline, ensemble, pd.DataFrame())
    
    assert validation['baseline_count'] == 1
    assert validation['ensemble_count'] == 1
    assert validation['ml_count'] == 0
    assert validation['ensemble_improves_sharpe']
    assert not validation['ml_improves_sharpe']
    assert validation['validation_passed']  # Ensemble improves


def test_intelligence_stack_end_to_end():
    """Test full end-to-end intelligence stack validation."""
    # Simulate realistic scenario: baseline OK, ensemble better, ML best
    baseline = create_sample_metrics(
        ['sma_cross', 'rsi_reversal', 'bollinger'],
        'baseline',
        (0.3, 0.8)  # Sharpe range
    )
    
    ensemble = create_sample_metrics(
        ['static_ensemble', 'adaptive_ensemble'],
        'ensemble',
        (0.7, 1.2)  # Better than baseline
    )
    
    ml = create_sample_metrics(
        ['ml_random_forest'],
        'ml',
        (1.0, 1.5)  # Best performance
    )
    
    # Build comparison
    comparison = build_intelligence_stack_comparison(baseline, ensemble, ml)
    assert not comparison.empty
    assert len(comparison) == 6
    
    # Build regime report (simulate regime-specific performance)
    regime_metrics = {
        'TRENDING': ensemble.iloc[:1],  # Static ensemble in trending
        'RANGING': baseline.iloc[:1],    # SMA in ranging
        'HIGH_VOLATILITY': ml           # ML in high vol
    }
    regime_report = build_regime_performance_report(regime_metrics)
    assert len(regime_report) == 3
    
    # Validate stack
    validation = validate_intelligence_stack(baseline, ensemble, ml, min_improvement=10.0)  # 10% improvement
    
    assert validation['validation_passed']
    assert validation['ensemble_improves_sharpe']
    assert validation['ml_improves_sharpe']
    assert validation['ensemble_sharpe_improvement'] > 10.0
    assert validation['ml_sharpe_improvement'] > 10.0
