# BAET — Next Steps TODO

## Current Branch: feature/phase1-foundation-setup

---

## 🔴 Critical (Do First)

### 1. Merge feature branch to main
- [ ] Create PR from feature/phase1-foundation-setup to main
- [ ] Review all changes
- [ ] Merge to main

### 2. Wire up new modules to main trading loop
- [ ] Integrate DatabaseManager into paper trading engine (src/baet/paper/engine.py)
- [ ] Integrate ScoutEngine with existing strategy ensemble (src/baet/core/brain.py)
- [ ] Integrate StreamManager for real-time price feeds in paper/live trading
- [ ] Integrate BridgeTrader into live execution path (src/baet/live/execution.py)
- [ ] Add Notifier calls at key events (trade executed, error, status change)

### 3. Create comprehensive test suite
- [ ] Tests for DatabaseManager (CRUD, session handling, migration)
- [ ] Tests for ScoutEngine (ratio calculation, decision logic)
- [ ] Tests for StreamManager (WebSocket connection, REST fallback)
- [ ] Tests for BridgeTrader (order execution, timeout, retry)
- [ ] Tests for Notifier (channel configuration, message formatting)
- [ ] Integration tests: scout -> risk engine -> execution pipeline
- [ ] Integration tests: database persistence across trading sessions

---

## 🟡 Important (Do Next)

### 4. Enhance CLI (src/baet/cli.py)
- [ ] Add 'baet scout' command — run scout analysis only
- [ ] Add 'baet db init' command — initialize database
- [ ] Add 'baet db migrate' command — migrate old state files
- [ ] Add 'baet status' command — show current coin, balance, open trades
- [ ] Add 'baet trade history' command — show recent trades from database
- [ ] Add 'baet backtest' command — run backtesting from CLI

### 5. Improve paper trading engine
- [ ] Use DatabaseManager for trade persistence instead of JSON logs
- [ ] Use StreamManager for price data instead of REST polling
- [ ] Add scout-based trading alongside existing strategy signals
- [ ] Add bridge trading support (multi-coin) to paper trading
- [ ] Add order timeout and retry logic from BridgeTrader

### 6. Improve live trading engine
- [ ] Add BridgeTrader integration for multi-coin live trading
- [ ] Add StreamManager for real-time price feeds
- [ ] Add BNB fee discount detection
- [ ] Add order timeout handling with cancellation
- [ ] Add database persistence for live trades

### 7. Enhance dashboard
- [ ] Add scout ratio visualization tab
- [ ] Add trade history from SQLite database
- [ ] Add multi-coin portfolio view
- [ ] Add real-time price ticker via WebSocket
- [ ] Add notification configuration UI

---

## 🟢 Nice to Have (Do Later)

### 8. Add more strategies from reference bot
- [ ] Implement default_strategy.py (ratio reversion)
- [ ] Implement multiple_coins_strategy.py (multi-coin rotation)
- [ ] Add strategy comparison in backtesting

### 9. Improve backtesting
- [ ] Add multi-coin backtesting support
- [ ] Add scout algorithm backtesting
- [ ] Add bridge trade simulation
- [ ] Generate comparison reports across strategies

### 10. Add notification integrations
- [ ] Telegram bot setup guide
- [ ] Discord webhook configuration
- [ ] Email notifications via SMTP
- [ ] Custom notification rules

### 11. Docker improvements
- [ ] Add health check to Dockerfile
- [ ] Add volume persistence for database
- [ ] Add environment variable configuration for all settings
- [ ] Test docker-compose end-to-end

### 12. Documentation
- [ ] Add docstrings to all new modules
- [ ] Create architecture diagram
- [ ] Add API reference for new modules
- [ ] Create user guide for scout trading
- [ ] Create deployment guide (Docker, local, cloud)

---

## Module Status

| Module | Created | Wired Up | Tested |
|---|---|---|---|
| database/models.py | Yes | No | No |
| database/manager.py | Yes | No | No |
| scout/engine.py | Yes | No | No |
| streaming/manager.py | Yes | No | No |
| execution/bridge_trader.py | Yes | No | No |
| reporting/notifier.py | Yes | No | No |
| config/ | Yes | Yes | Yes |
| core/ | Yes | Yes | Yes |
| dashboard/ | Yes | Yes | Yes |
| data/ | Yes | Yes | Yes |
| execution/backtest.py | Yes | Yes | Yes |
| live/ | Yes | Yes | Yes |
| paper/ | Yes | Yes | Yes |
| plugins/ | Yes | Yes | Yes |
| regimes/ | Yes | Yes | Yes |
| reporting/ | Yes | Yes | Yes |
| risk/ | Yes | Yes | Yes |
| strategies/ | Yes | Yes | Yes |

---

## Suggested Order

1. Merge to main
2. Wire up DatabaseManager
3. Wire up StreamManager
4. Wire up ScoutEngine
5. Wire up BridgeTrader
6. Wire up Notifier
7. Write tests
8. Enhance CLI
9. Enhance dashboard
10. Docker testing
