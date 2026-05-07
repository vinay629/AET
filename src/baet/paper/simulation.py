"""Simple simulation mode for paper trading observation period.

This module provides simulated market data and signals so the paper trading
engine can be observed during the M4.4 stability test (7-14 days).
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class SimpleMarketSimulator:
    """Simulates market data for observation period testing."""
    
    def __init__(self, symbols: list[str] = None, base_prices: dict[str, float] = None):
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT"]
        self.base_prices = base_prices or {
            "BTCUSDT": 50000.0,
            "ETHUSDT": 3000.0,
        }
        self.current_prices = self.base_prices.copy()
        self.price_history: dict[str, list[float]] = {s: [p] for s, p in self.base_prices.items()}
        
    def get_market_data(self) -> dict[str, dict[str, Any]]:
        """Generate simulated market data with realistic price movements."""
        market_data = {}
        
        for symbol in self.symbols:
            # Simulate price movement (random walk with slight upward bias)
            current = self.current_prices[symbol]
            change_pct = random.gauss(0.0001, 0.002)  # Mean 0.01% up, std 0.2%
            new_price = current * (1 + change_pct)
            
            # Add some noise
            bid = new_price * (1 - random.uniform(0, 0.0001))
            ask = new_price * (1 + random.uniform(0, 0.0001))
            
            market_data[symbol] = {
                "price": round(new_price, 2),
                "bid": round(bid, 2),
                "ask": round(ask, 2),
                "volume": random.randint(100, 10000),
                "timestamp": datetime.now().isoformat(),
            }
            
            self.current_prices[symbol] = new_price
            self.price_history[symbol].append(new_price)
            
            # Keep history manageable
            if len(self.price_history[symbol]) > 1000:
                self.price_history[symbol] = self.price_history[symbol][-1000:]
        
        return market_data
    
    def get_features(self, symbol: str) -> dict[str, Any]:
        """Calculate simple features from price history."""
        prices = self.price_history.get(symbol, [])
        if len(prices) < 20:
            return {}
        
        current = prices[-1]
        ma5 = sum(prices[-5:]) / 5
        ma20 = sum(prices[-20:]) / 20
        
        return {
            "price": current,
            "ma5": ma5,
            "ma20": ma20,
            "trend": "UP" if ma5 > ma20 else "DOWN",
            "rsi": random.uniform(30, 70),  # Simplified
        }


class SimpleStrategy:
    """Simple trading strategy for simulation."""
    
    def __init__(self, name: str = "simple_simulation"):
        self.name = name
        self.position_open = False
        self.last_signal = "HOLD"
        
    def generate_signal(self, symbol: str, features: dict[str, Any]) -> dict[str, Any]:
        """Generate a trading signal based on simple rules."""
        
        if not features:
            return {"signal": "HOLD", "confidence": 0.0}
        
        trend = features.get("trend", "UP")
        rsi = features.get("rsi", 50)
        
        # Simple logic: Buy on uptrend with low RSI, sell on downtrend with high RSI
        if not self.position_open and trend == "UP" and rsi < 40:
            self.position_open = True
            self.last_signal = "BUY"
            return {
                "signal": "BUY",
                "confidence": 0.7,
                "strategy": self.name,
                "reason": f"Uptrend detected, RSI={rsi:.1f}",
            }
        elif self.position_open and trend == "DOWN" and rsi > 60:
            self.position_open = False
            self.last_signal = "SELL"
            return {
                "signal": "SELL",
                "confidence": 0.7,
                "strategy": self.name,
                "reason": f"Downtrend detected, RSI={rsi:.1f}",
            }
        else:
            return {
                "signal": "HOLD",
                "confidence": 0.5,
                "strategy": self.name,
                "reason": "No clear signal",
            }


def patch_engine_for_simulation(engine):
    """Patch a PaperTradingEngine with simulation capabilities.
    
    This allows the engine to run with simulated data during observation.
    """
    simulator = SimpleMarketSimulator()
    strategy = SimpleStrategy()
    
    def simulated_update_market_data():
        """Replace _update_market_data with simulation."""
        return simulator.get_market_data()
    
    def simulated_update_features(market_data):
        """Replace _update_features with simulation."""
        features = {}
        for symbol in market_data:
            features[symbol] = simulator.get_features(symbol)
        return features
    
    def simulated_generate_signals(features):
        """Replace _generate_signals with simulation."""
        signals = {}
        for symbol, feat in features.items():
            signals[symbol] = strategy.generate_signal(symbol, feat)
        return signals
    
    # Patch the engine methods
    engine._update_market_data = simulated_update_market_data
    engine._update_features = simulated_update_features
    engine._generate_signals = simulated_generate_signals
    
    logger.info("Engine patched with simulation mode for observation period")
    
    return engine
