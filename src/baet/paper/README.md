# Paper Trading Module

## Overview

The `baet.paper` module provides a simulated trading environment that runs continuously without connecting to live exchanges. It's designed to test strategies safely before risking real capital.

## Components

### 1. PaperPortfolio (`portfolio.py`)

Manages simulated positions and cash balance.

**Key Features:**
- Track cash, positions, and trade history
- Calculate total portfolio value with current market prices
- Record all trades for analysis
- Maintain equity curve for performance tracking

**Usage:**
```python
from baet.paper.portfolio import PaperPortfolio

portfolio = PaperPortfolio(initial_balance=10_000.0)

# Buy assets
portfolio.buy(symbol="BTCUSDT", units=0.5, price=20_000.0, fee=10.0)

# Sell assets
portfolio.sell(symbol="BTCUSDT", units=0.5, price=21_000.0, fee=10.0)

# Get current value
total_value = portfolio.get_total_value({"BTCUSDT": 21_000.0})

# Get summary
summary = portfolio.get_summary()
```

### 2. PaperOrderSimulator (`order_simulator.py`)

Simulates realistic order execution with slippage and fees.

**Key Features:**
- Configurable fee rates and slippage
- Realistic fill price calculation
- Support for both buy and sell orders

**Usage:**
```python
from baet.paper.order_simulator import PaperOrderSimulator

simulator = PaperOrderSimulator(
    fee_rate=0.001,      # 0.1% fee
    slippage_rate=0.0005  # 0.05% slippage
)

# Simulate a buy order
fill_price, units, fee = simulator.simulate_buy(price=20_000.0, units=0.5)

# Simulate a sell order
fill_price, proceeds, fee = simulator.simulate_sell(price=21_000.0, units=0.5)
```

### 3. PaperTradingEngine (`engine.py`)

Main event loop that runs continuously, fetching data, generating signals, and executing simulated trades.

**Key Features:**
- Configurable loop interval
- Error handling with consecutive error limits
- Integration with risk engine
- Real-time portfolio state updates
- Graceful start/stop functionality

**Usage:**
```python
from baet.paper.engine import PaperTradingEngine
from baet.config.models import Settings

settings = Settings()
engine = PaperTradingEngine(settings, risk_engine=my_risk_engine)

# Start the engine (runs in background)
engine.start()

# Check status
status = engine.get_status()

# Stop when done
engine.stop()
```

## Configuration

Paper trading is configured in `config/base.yaml` under the `paper:` section:

```yaml
paper:
  enabled: true
  initial_balance: 10000.0
  loop_interval_seconds: 60
  stop_on_error: false
  max_consecutive_errors: 10
  notification_webhook: ""
```

## Integration with Risk Engine

The paper trading engine can optionally integrate with the centralized risk engine:

```python
from baet.risk.engine import RiskEngine
from baet.paper.engine import PaperTradingEngine

risk_engine = RiskEngine(policy=my_policy)
engine = PaperTradingEngine(settings, risk_engine=risk_engine)
```

When a risk engine is provided:
- All signals are evaluated against risk checks before execution
- Risk metadata is attached to each trade
- Violations are logged but don't crash the engine

## Running Paper Trading

To run the paper trading loop:

```bash
python -m baet --mode paper
```

Or from Python:

```python
from baet.paper.engine import PaperTradingEngine
from baet.config.loader import load_config

settings = load_config("config/paper.yaml")
engine = PaperTradingEngine(settings)
engine.start()
```

## Testing

The paper trading module includes comprehensive tests in `tests/test_paper_trading.py`:

```bash
python -m pytest tests/test_paper_trading.py -v
```

## Milestone

This module fulfills **M4.2.a** - Paper Trading Loop Runs Continuously Without Crashing.

### Success Criteria:
- ✅ PaperPortfolio tracks positions and cash correctly
- ✅ PaperOrderSimulator applies realistic slippage and fees
- ✅ PaperTradingEngine runs in a continuous loop
- ✅ Engine handles errors gracefully without crashing
- ✅ Integration with risk engine (optional)
- ✅ 28 unit tests passing
