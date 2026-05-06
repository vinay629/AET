# Risk Module - BAET Risk Policy

## Overview
The `risk` module provides centralized risk management for the BAET trading platform. All trade signals MUST pass through the `RiskEngine` before execution. The risk engine can **approve**, **reject**, or **modify** any trade signal based on comprehensive risk rules.

## Risk Philosophy
- **Conservative by default**: Risk limits err on the side of safety
- **Override-capable**: Risk engine CAN override strategy decisions
- **Transparent**: All decisions include detailed reasons and violation details
- **Decision-complete**: Every trade path goes through centralized risk checks

## Risk Hierarchy

```
Signal Generated → RiskEngine.evaluate_signal()
    ├─ Emergency Checks (kill-switch)
    ├─ Strategy Risk (blacklist, min Sharpe)
    ├─ Position Sizing (max size, min size, risk per trade)
    ├─ Drawdown Protection (portfolio DD, daily loss, trailing stop)
    ├─ Regime Risk (exposure limits by market regime)
    └─ Portfolio Risk (total exposure, concentration, active positions)
```

## Policy Models

### PositionSizingPolicy
Controls individual position sizes:
- `max_risk_per_trade`: 1% default max risk per trade
- `max_position_size`: 10% default max in any single position
- `min_position_size`: 0.1% default minimum (avoid dust)
- `sizing_method`: "fixed", "kelly", or "percent_risk"

### DrawdownProtectionPolicy
Protects against excessive losses:
- `max_portfolio_drawdown`: 15% default max drawdown
- `max_daily_loss`: 5% default max daily loss
- `trailing_stop_enabled`: True (enabled by default)
- `trailing_stop_distance`: 3% trailing stop
- `kill_switch_drawdown`: 20% triggers emergency kill-switch

### RegimeRiskPolicy
Adjusts risk based on market conditions:
- `trending_max_exposure`: 20% max in trending markets
- `ranging_max_exposure`: 15% max in ranging markets
- `high_volatility_max_exposure`: 10% max in high volatility
- `low_volatility_max_exposure`: 25% max in low volatility
- `regime_confidence_threshold`: 60% minimum confidence for regime-based adjustments

### StrategyRiskPolicy
Per-strategy risk controls:
- `enabled_strategies`: Empty = all enabled, or specify allowed strategies
- `blacklisted_strategies`: Strategies never allowed
- `max_strategy_allocation`: Per-strategy max allocation
- `strategy_min_sharpe`: 0.5 minimum Sharpe ratio to allow strategy
- `strategy_max_drawdown`: 15% max drawdown per strategy

### PortfolioRiskPolicy
Portfolio-level limits:
- `max_total_exposure`: 50% max total exposure
- `max_correlation`: 70% max correlation between positions
- `max_concentration`: 30% max in any one symbol
- `max_active_positions`: 10 maximum active positions
- `max_leverage`: 1.0 (no leverage for initial release)

### EmergencyPolicy
Emergency controls and kill-switch:
- `kill_switch_enabled`: True (enabled by default)
- `kill_switch_conditions`: ["portfolio_drawdown_exceeded", "daily_loss_exceeded", "consecutive_losses_10", "manual_trigger"]
- `cooldown_period_hours`: 24 hours cooldown after kill-switch
- `require_manual_reset`: True (requires manual reset)
- `notify_on_trigger`: True (sends notifications)

## Risk Check Results

The `RiskEngine` returns a `RiskCheckResult` with:
- `approved`: Whether trade is approved (may be modified)
- `action`: Original action (BUY, SELL, HOLD)
- `adjusted_action`: May be modified to HOLD or reduced
- `adjusted_size`: May be reduced from original
- `confidence`: Confidence in risk decision (0.0 to 1.0)
- `reasons`: List of reasons for the decision
- `risk_score`: 0.0 (safe) to 1.0 (high risk)
- `violations`: List of `RiskViolation` objects with details

## Usage Example

```python
from baet.risk import RiskEngine, RiskPolicy

# Create policy (uses defaults)
policy = RiskPolicy()

# Create engine
engine = RiskEngine(policy)

# Evaluate a signal
signal = {
    'action': 'BUY',
    'target_position': 1.0,
    'confidence': 0.8,
    'size_hint': 0.05,
    'strategy_name': 'sma_crossover',
    'symbol': 'BTCUSDT',
    'timestamp': datetime.now(),
}

result = engine.evaluate_signal(signal, regime=None)

if result.approved:
    print(f"Trade approved: {result.adjusted_action} with size {result.adjusted_size}")
else:
    print(f"Trade rejected: {result.reasons}")
```

## Integration Points

The RiskEngine integrates with:
- **Ensemble layer** (`src/baet/strategies/ensemble.py`): Run risk checks on combined signals
- **Backtest engine** (`src/baet/execution/backtest.py`): Run risk checks before simulated trades
- **Paper trading** (future): Run risk checks before paper orders
- **Live trading** (future): Run risk checks before real orders

## Configuration

Risk policy is configured in `config/base.yaml`:

```yaml
risk:
  max_risk_per_trade: 0.01
  max_portfolio_exposure: 0.20
  policy:
    position_sizing:
      max_risk_per_trade: 0.01
      max_position_size: 0.10
      min_position_size: 0.001
      sizing_method: "percent_risk"
    drawdown:
      max_portfolio_drawdown: 0.15
      kill_switch_drawdown: 0.20
    # ... (see policy.py for all options)
```

## Testing

Run the risk policy tests:
```bash
python -m pytest tests/test_risk_policy.py -v
```

Current test coverage: **35 tests** covering:
- Policy model creation and validation
- Risk check result creation
- Risk engine evaluation (approve/reject/modify)
- Kill-switch functionality
- Drawdown protection
- Regime-based risk adjustments
- Strategy blacklisting
- Portfolio exposure limits
- Emergency conditions

## Success Criteria (M4.1a)

✅ **Documentation**: All risk rules documented with rationale  
✅ **Decision-Completeness**: Risk policy models exist for ALL risk categories  
✅ **Override Capability**: Risk engine CAN override strategy decisions (tested)  
✅ **Code Quality**: All models use Pydantic for validation  
✅ **Unit Tests**: 35 tests cover happy path and edge cases  
✅ **Integration Ready**: Risk engine interface is clear and easy to integrate  

## Next Steps

After M4.1a is committed:
- **M4.1b**: Implement centralized risk checks in ALL trade paths
- **M4.2a**: Paper trading loop runs continuously
- **M4.3a**: Paper trading logs explain decisions end-to-end
- **M4.3b**: Streamlit dashboard shows risk state
