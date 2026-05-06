# Binance Adaptive Ensemble Trader (BAET) - Project Blueprint

## TL;DR
BAET is a modular, local-first Python trading system for Binance that combines multiple strategy types, adapts to market regimes, applies strict risk controls, and progresses from backtesting to paper trading to limited live trading.

## 1. Vision
Build an intelligent crypto trading platform that can:
- collect Binance market data
- generate features and detect market regimes
- run multiple independent strategies
- combine strategy outputs with ensemble logic
- enforce risk checks before execution
- learn and improve over time

## 2. Core Principles
- 100% free or low-cost local-first stack
- modular architecture
- risk-first design
- gradual rollout from simple to advanced
- human oversight early on
- measurable validation before live capital

## 3. High-Level Architecture

### Data Layer
- historical Binance market data
- real-time Binance data streams
- optional free sentiment/news inputs
- local storage using files or lightweight database

### Feature Engineering Layer
- technical indicators
- volatility and momentum features
- statistical features
- cross-asset and correlation features
- regime-related features

### Strategy Layer
- rule-based strategies
- statistical strategies
- machine learning strategies
- reinforcement learning strategies
- LLM-assisted strategy ideation via Ollama

### Ensemble Decision Layer
- signal aggregation
- strategy weighting
- regime-aware strategy switching
- position sizing recommendations

### Risk and Execution Layer
- pre-trade checks
- exposure limits
- stop-loss and take-profit logic
- Binance spot or futures execution
- emergency kill-switch

### Monitoring and Feedback Layer
- performance tracking
- health checks per strategy
- drift and degradation alerts
- retraining or reweighting triggers
- dashboard and logs

## 4. Strategy Zoo

### Classical
- RSI mean reversion
- Bollinger band reversal
- EMA crossover
- breakout momentum
- trend-following with ADX filter

### Statistical
- mean reversion
- z-score reversal
- pairs or spread trading
- volatility compression expansion setups

### Machine Learning
- tree-based directional prediction
- probability-based long/short classifier
- return forecasting models

### Reinforcement Learning
- agent-based action selection
- adaptive position management

### Hybrid
- LLM-generated strategy ideas
- ML-filtered classical strategies
- regime-switched strategy groups

## 5. Key Intelligence Modules

### Regime Detector
Classifies market state such as trending, ranging, high-volatility, or low-volatility.

### Performance Tracker
Tracks rolling Sharpe, drawdown, win rate, profit factor, stability, and recent degradation.

### Meta-Learner
Allocates capital across strategies based on recent performance, confidence, and current regime.

### Strategy Generator
Uses Ollama to suggest new ideas, filters them through validation rules, and promotes only tested candidates.

### Backtester
Supports walk-forward testing, realistic fees, slippage, and strict out-of-sample validation.

### Paper Trader
Runs live simulation before real execution to validate latency, logic, and risk controls.

## 6. Risk Framework
- cap risk per trade
- define max portfolio exposure
- enforce max daily and weekly drawdown
- limit correlation and crowded positioning
- use volatility-aware stops
- block trading during extreme anomalies
- require circuit breaker behavior after loss limits

## 7. Major Design Decisions

### Trading Style
- scalping vs swing
- 5m/15m vs 1h/4h
- spot only vs futures

### Asset Scope
- BTCUSDT only
- BTC + ETH
- limited basket of major alts

### Autonomy
- manual approval for all live trades
- manual approval only for new strategies
- mostly autonomous with hard safeguards

### Adaptation Frequency
- retrain models on schedule
- reweight ensemble daily or hourly
- regenerate ideas periodically

### Compute
- local PC first
- optional VPS later
- GPU only if RL or deep models justify it

## 8. Recommended Delivery Phases

### Phase 1 - Foundation
- data ingestion
- local storage
- basic backtesting
- 8 to 10 classical strategies

### Phase 2 - Intelligence
- regime detection
- ML models
- simple ensemble weighting
- richer evaluation metrics

### Phase 3 - Advanced
- RL experiments
- Ollama-driven strategy ideation
- meta-learning allocation
- full risk engine

### Phase 4 - Live Rollout
- paper trading
- Binance test environment
- small-capital live deployment
- monitoring and iterative improvement

## 9. Main Risks
- overfitting
- bad market data
- concept drift
- API limits
- slippage and execution mismatch
- false confidence from simulated performance

## 10. Mitigations
- walk-forward validation
- strict out-of-sample testing
- caching and resilient data ingestion
- regime-aware monitoring
- realistic cost assumptions
- phased deployment with tiny live capital first

## 11. Success Metrics
- stable out-of-sample performance
- controlled drawdown
- acceptable Sharpe or risk-adjusted return
- low operational failure rate
- no breach of defined risk rules
- improvement over baseline strategies

## 12. Recommended First Scope
Start with:
- Binance spot only
- BTCUSDT and ETHUSDT
- 1h and 4h timeframe focus
- classical + ML strategies only
- paper trading before any live execution

This keeps the system simpler, cheaper, and easier to validate before adding futures, RL, or autonomous strategy generation.

## 13. Proposed Next Documents
- product requirements
- folder structure blueprint
- data schema plan
- strategy catalog
- risk policy
- testing and evaluation plan
- deployment roadmap
