# Milestones

## TL;DR
Track delivery by validated checkpoints, not by code volume.

## Stage 0
- `M0.1` PRD and roadmap finalized
- `M0.2` Python project scaffold created
- `M0.3` config system supports `dev`, `paper`, and `live`
- `M0.4` setup docs and folder structure documented
- `M0.5` baseline tests pass

## Stage 1
- `M1.1` historical data ingestion works for target symbols
- `M1.2` feature pipeline is reproducible
- `M1.3` backtester handles fees and slippage
- `M1.4` strategy comparison reports exist

## Stage 3
- `M3.1a` regime labels are formally defined
- `M3.1b` regime labels are generated reproducibly
- `M3.1c` regime detector runs end to end
- `M3.2a` strategy signal schema is standardized
- `M3.2b` static ensemble produces one decision stream
- `M3.3a` adaptive weights update deterministically
- `M3.3b` at least one ML strategy is integrated
- `M3.4` portfolio comparison reports validate the intelligence stack

## Stage 4
- `M4.1a` risk policy is documented and decision-complete
- `M4.1b` centralized risk checks gate every trade path
- `M4.2a` paper trading loop runs continuously without crashing
- `M4.3a` paper trading logs explain decisions end to end
- `M4.3b` Streamlit dashboard shows current paper trading state and daily summaries
- `M4.4` paper trading is stable over the target observation window

## Stage 5
- `M5.1a` live readiness controls are implemented and documented
- `M5.1b` live execution path works in controlled validation conditions
- `M5.2` first tiny-capital live pilot completes with audit trail
- `M5.3` no hard risk rule breaches occur during initial live observation

## Current Status
- `M0.1` validated
- `M0.2` validated
- `M0.3` validated
- `M0.4` validated
- `M0.5` validated
- `M1.1` validated
- `M1.2` validated
- `M1.3` validated
- `M1.4` validated
- `M2.1` implemented
- `M2.2` implemented
- `M2.3` implemented
- `M3.1a` implemented
- `M3.1b` implemented
- `M3.1c` implemented
- `M3.2a` implemented
- `M3.2b` implemented
- `M3.3a` implemented
- `M3.3b` implemented
- `M3.4` implemented
- `M4.1a` implemented
- `M4.1b` implemented
- `M4.2a` implemented
- `M4.3a` implemented
- `M4.3b` implemented

## Verification Notes
- Stage 0 remains green under current checks
- Stage 1 ingestion, storage, feature generation, and baseline backtesting are verified
- Stage 1 reporting now includes strategy-to-strategy comparison outputs with ranking tables
- Stage 2.1 strategy contracts, filesystem discovery, and order-intent signal adaptation are implemented
- Stage 2.2 baseline strategies implemented: 7 strategies (buy_and_hold, sma_crossover, rsi_mean_reversion, bollinger_bands, ema_crossover, breakout_momentum, adx_trend_filter)
- Stage 2.3 strategy comparison reports now rank by Sharpe ratio, Sortino, Calmar, returns, and drawdown metrics
- Stage 3.1 regime detection module implemented with VolatilityTrendRegimeDetector that classifies TRENDING, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY regimes using expanding window percentiles for reproducibility
- Stage 3.2 ensemble decision layer implemented with StaticEnsemble that combines multiple strategy signals using confidence-weighted voting and regime-aware weighting; produces single decision stream per timestamp
- Stage 3.3a adaptive ensemble implemented with AdaptiveEnsemble that updates strategy weights deterministically based on rolling Sharpe ratio performance; includes PerformanceTracker for rolling metrics calculation
- Stage 3.3b ML strategy integrated: MLRandomForestStrategy uses Random Forest classifier with technical features (RSI, MA ratios, volatility) to predict price direction; includes automated feature generation and probability-based signal generation
- Stage 3.4 intelligence stack validation reporting implemented: build_intelligence_stack_comparison(), build_regime_performance_report(), and validate_intelligence_stack() functions compare baseline vs ensemble vs ML strategies and validate that intelligence stack improves performance
- Stage 4.1a risk policy documented and decision-complete: RiskPolicy model with PositionSizingPolicy, DrawdownProtectionPolicy, RegimeRiskPolicy, StrategyRiskPolicy, PortfolioRiskPolicy, EmergencyPolicy; RiskEngine evaluates all signals and CAN override strategy decisions; 35 unit tests validate all components
- Stage 4.1b centralized risk checks gate every trade path: RiskEngine integrated into ensemble layer (StaticEnsemble, AdaptiveEnsemble) and backtest engine (PortfolioBacktestEngine); integration module (risk/integration.py) provides helper functions; 22 integration tests validate all paths; backward compatible (risk engine is optional)
- Stage 4.2a paper trading loop runs continuously without crashing: PaperPortfolio tracks positions/cash; PaperOrderSimulator applies slippage/fees; PaperTradingEngine runs continuous loop with error handling; 28 unit tests validate all components; integrates with risk engine (optional)
- Stage 4.3a paper trading logs explain decisions end-to-end: PaperTradingLogger provides structured JSON logging; all decisions logged (signals, risk evaluations, order simulations, portfolio updates, engine events); log analysis script created; 17 unit tests validate logging system
- Stage 4.3b Streamlit dashboard shows current paper trading state and daily summaries: Dashboard module with data_loader.py (find_latest_log_file, parse_log_file, load_latest_state, load_recent_trades, load_equity_curve, calculate_daily_summary, calculate_performance_metrics); components.py with 8 UI components; main app.py with 5 tabs; 19 unit tests validate all data loading functions; launcher script created
## Validation States
- `pending`
- `active`
- `blocked`
- `validated`
