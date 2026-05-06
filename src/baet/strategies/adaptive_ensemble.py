"""Adaptive ensemble with performance-based weight updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from baet.core.models import RegimeLabel, StrategyMetadata
from baet.strategies.ensemble import EnsembleConfig, StaticEnsemble, StrategyWeight
from baet.strategies.contracts import SIGNAL_COLUMNS


@dataclass
class PerformanceTracker:
    """Tracks rolling performance metrics for strategies."""
    
    window: int = 20
    metrics: Dict[str, pd.DataFrame] = field(default_factory=dict)
    
    def update(self, strategy_name: str, signals: pd.DataFrame, returns: pd.DataFrame):
        """Update performance tracking with new signals and realized returns."""
        if strategy_name not in self.metrics:
            self.metrics[strategy_name] = pd.DataFrame(columns=['timestamp', 'return', 'cumulative_return'])
        
        # Calculate strategy returns (simplified: signal * next period return)
        merged = pd.merge(signals[['timestamp', 'action', 'target_position']], 
                         returns[['timestamp', 'return']], 
                         on='timestamp', how='left')
        
        merged['strategy_return'] = 0.0
        merged.loc[merged['action'] == 'BUY', 'strategy_return'] = merged['return']
        merged.loc[merged['action'] == 'SELL', 'strategy_return'] = -merged['return']
        
        # Update tracking
        tracking = self.metrics[strategy_name]
        new_data = merged[['timestamp', 'strategy_return']].rename(columns={'strategy_return': 'return'})
        new_data['cumulative_return'] = (1 + new_data['return']).cumprod() - 1
        
        self.metrics[strategy_name] = pd.concat([tracking, new_data], ignore_index=True)
        
        # Keep only recent window
        if len(self.metrics[strategy_name]) > self.window:
            self.metrics[strategy_name] = self.metrics[strategy_name].tail(self.window)
    
    def get_sharpe(self, strategy_name: str) -> float:
        """Calculate rolling Sharpe ratio for a strategy."""
        if strategy_name not in self.metrics or len(self.metrics[strategy_name]) < 2:
            return 0.0
        
        returns = self.metrics[strategy_name]['return'].values
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe (assuming daily data)
        sharpe = mean_return / std_return * np.sqrt(252)
        return sharpe
    
    def get_sortino(self, strategy_name: str) -> float:
        """Calculate rolling Sortino ratio for a strategy."""
        if strategy_name not in self.metrics or len(self.metrics[strategy_name]) < 2:
            return 0.0
        
        returns = self.metrics[strategy_name]['return'].values
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return mean_return * np.sqrt(252)  # No downside, return annualized mean
        
        downside_std = np.std(downside_returns)
        
        if downside_std == 0:
            return 0.0
        
        sortino = mean_return / downside_std * np.sqrt(252)
        return sortino


class AdaptiveEnsemble(StaticEnsemble):
    """Adaptive ensemble that updates strategy weights based on performance."""
    
    def __init__(self, config: EnsembleConfig, performance_window: int = 20):
        super().__init__(config)
        self.performance_tracker = PerformanceTracker(window=performance_window)
        self.historical_weights: List[Dict] = []  # Track weight history
        
    def update_weights(self, strategy_signals: Dict[str, pd.DataFrame], 
                       returns: pd.DataFrame) -> Dict[str, float]:
        """
        Update strategy weights based on recent performance.
        
        Args:
            strategy_signals: Dict mapping strategy name to signals
            returns: DataFrame with ['timestamp', 'return'] for the market
            
        Returns:
            Dict mapping strategy name to new weight
        """
        # Update performance tracking
        for strategy_name, signals in strategy_signals.items():
            self.performance_tracker.update(strategy_name, signals, returns)
        
        # Calculate performance-based weights
        sharpes = {}
        for strategy_name in strategy_signals.keys():
            sharpe = self.performance_tracker.get_sharpe(strategy_name)
            # Use max(sharpe, 0) to avoid negative weights
            sharpes[strategy_name] = max(sharpe, 0.0)
        
        # Normalize weights
        total_sharpe = sum(sharpes.values())
        
        if total_sharpe > 0:
            weights = {name: s / total_sharpe for name, s in sharpes.items()}
        else:
            # Equal weights if no positive Sharpe
            n = len(strategy_signals)
            weights = {name: 1.0 / n for name in strategy_signals.keys()}
        
        # Apply regime adjustments if applicable
        # (simplified: use the most recent regime from the first strategy's signals)
        regime = None
        first_strategy = next(iter(strategy_signals.values()), None)
        if first_strategy is not None and 'regime' in first_strategy.columns:
            regime = first_strategy.iloc[-1].get('regime')
        
        if regime and regime in self.config.regime_weights:
            regime_dict = self.config.regime_weights[regime]
            for name in weights:
                if name in regime_dict:
                    weights[name] *= regime_dict[name]
            
            # Re-normalize
            total = sum(weights.values())
            if total > 0:
                weights = {name: w / total for name, w in weights.items()}
        
        # Record weight history
        self.historical_weights.append({
            'timestamp': pd.Timestamp.now(),
            'weights': weights.copy()
        })
        
        return weights
    
    def combine_signals_adaptive(self, strategy_signals: Dict[str, pd.DataFrame],
                                returns: pd.DataFrame,
                                regime_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Combine signals with adaptive weights based on performance.
        
        Args:
            strategy_signals: Dict mapping strategy name to signals
            returns: Market returns for performance calculation
            regime_data: Optional regime data for regime-aware weighting
            
        Returns:
            DataFrame with combined signals using adaptive weights
        """
        # Update weights based on performance
        new_weights = self.update_weights(strategy_signals, returns)
        
        # Temporarily update config with new weights
        original_weights = self.config.strategy_weights.copy()
        
        self.config.strategy_weights = [
            StrategyWeight(strategy_name=name, weight=weight)
            for name, weight in new_weights.items()
        ]
        
        # Combine signals using parent class method
        combined = self.combine_signals(strategy_signals, regime_data)
        
        # Restore original weights
        self.config.strategy_weights = original_weights
        
        return combined
    
    def get_weight_history(self) -> pd.DataFrame:
        """Get historical weight assignments."""
        if not self.historical_weights:
            return pd.DataFrame()
        
        records = []
        for entry in self.historical_weights:
            record = {'timestamp': entry['timestamp']}
            record.update(entry['weights'])
            records.append(record)
        
        return pd.DataFrame(records)
