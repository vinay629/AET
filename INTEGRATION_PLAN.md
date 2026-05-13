# BAET × binance-trade-bot Integration Plan

## Reference: https://github.com/ccxt/binance-trade-bot.git

This document outlines features and patterns from the reference repository that can improve BAET.

---

## Key Features to Integrate

### 1. Multi-Coin Support with Bridge Trading
**Reference**: The bot trades across a configurable list of coins using a bridge currency (USDT).

**Current BAET state**: Only supports BTCUSDT and ETHUSDT pairs directly.

**Integration**:
- Support arbitrary coin pairs via bridge currency (e.g., BTC → USDT → ETH)
- Dynamic pair discovery from Binance exchange info
- Configurable supported coin list

### 2. Scout Algorithm (Ratio-Based Trading)
**Reference**: The bot monitors ratios between coin prices and trades when ratios diverge from historical norms.

**Current BAET state**: Uses strategy signals but doesn't track cross-coin ratios.

**Integration**:
- Implement scout module that tracks coin-to-coin ratios over time
- Configurable scout multiplier (threshold for triggering trades)
- Scout history with automatic pruning

### 3. SQLite Database for Trade History
**Reference**: Uses SQLAlchemy + SQLite to persist trades, scout history, coin values, and current state.

**Current BAET state**: Uses JSON logging and Parquet files.

**Integration**:
- Add SQLite database for trade state persistence
- Models: Coin, Pair, Trade, ScoutHistory, CoinValue, CurrentCoin
- Automatic database migration from old formats

### 4. WebSocket Streaming
**Reference**: Uses Binance WebSocket streams for real-time price updates instead of polling.

**Current BAET state**: Polls REST API for market data.

**Integration**:
- WebSocket-based price streaming for lower latency
- Automatic reconnection on disconnect
- Order status updates via WebSocket

### 5. Strategy Plugin System
**Reference**: Strategies are loaded dynamically from files matching `*_strategy.py` pattern.

**Current BAET state**: Strategies are defined as classes in the strategies module.

**Integration**:
- Dynamic strategy discovery and loading
- Standardized strategy interface (scout method, update_values method)
- Support for user-defined strategies without modifying core code

### 6. BNB Fee Discount Handling
**Reference**: Automatically detects and uses BNB for fee payment (25% discount).

**Current BAET state**: Fixed fee rate in config.

**Integration**:
- Auto-detect BNB fee payment status
- Check BNB balance before trading
- Apply 25% fee discount when BNB is available

### 7. Order Management with Timeouts
**Reference**: Configurable buy/sell timeouts with automatic cancellation and retry.

**Current BAET state**: Basic order execution without timeout handling.

**Integration**:
- Configurable order timeouts (buy_timeout, sell_timeout)
- Automatic order cancellation on timeout
- Partial fill handling

### 8. Notification System (Apprise)
**Reference**: Supports Telegram, Discord, Slack, and 50+ notification services.

**Current BAET state**: No notification system.

**Integration**:
- Apprise integration for multi-channel notifications
- Notify on trades, errors, and status changes
- Configurable notification rules

### 9. Docker Deployment
**Reference**: Full Docker + docker-compose setup for easy deployment.

**Current BAET state**: No Docker support.

**Integration**:
- Dockerfile for containerized deployment
- docker-compose with bot + SQLite browser
- Heroku/DigitalOcean quick deploy configs

### 10. Backtesting Module
**Reference**: Standalone `backtest.py` for testing strategies on historical data.

**Current BAET state**: Backtesting exists but could be enhanced.

**Integration**:
- Standalone backtest script
- Compare multiple strategies side-by-side
- Support different time periods and parameters

---

## Architecture Comparison

| Component | Reference Bot | BAET Current | Integration Priority |
|---|---|---|---|
| Exchange API | python-binance | python-binance | ✅ Already aligned |
| Data Storage | SQLite (SQLAlchemy) | Parquet + JSON | 🔶 Add SQLite layer |
| Config | .cfg file + env vars | YAML + .env | ✅ Already better |
| Strategies | Plugin system | Class-based | 🔶 Add plugin loader |
| Trading Logic | Scout ratio-based | Signal ensemble | 🔶 Combine both |
| Multi-coin | Bridge trading | Single pair | 🔶 Add bridge support |
| Streaming | WebSocket | REST polling | 🔶 Add WebSocket |
| Notifications | Apprise | None | 🔶 Add Apprise |
| Deployment | Docker + Heroku | Local only | 🔶 Add Docker |
| Risk Engine | Basic limits | Advanced engine | ✅ BAET is better |
| Dashboard | None (Telegram bot) | Streamlit | ✅ BAET is better |
| ML Strategies | None | Random Forest | ✅ BAET is better |
| Regime Detection | None | Full system | ✅ BAET is better |

---

## Implementation Phases

### Phase A: Database Layer
- Add SQLAlchemy models (Coin, Pair, Trade, ScoutHistory, CoinValue)
- Create database manager with session handling
- Migrate existing trade logs to SQLite

### Phase B: Scout Algorithm
- Implement ratio tracking between coin pairs
- Add scout history with configurable pruning
- Integrate with existing strategy ensemble

### Phase C: WebSocket Streaming
- Add Binance WebSocket manager for price streaming
- Implement order status tracking via WebSocket
- Add automatic reconnection logic

### Phase D: Multi-Coin Bridge Trading
- Implement bridge currency trading logic
- Add dynamic pair discovery
- Support configurable coin lists

### Phase E: Order Management
- Add order timeout handling
- Implement partial fill management
- Add BNB fee discount detection

### Phase F: Notifications & Deployment
- Add Apprise notification system
- Create Dockerfile and docker-compose.yml
- Add notification configuration

---

## File Structure (After Integration)

```
AET/
├── config/
│   ├── base.yaml
│   ├── dev.yaml
│   ├── paper.yaml
│   └── live.yaml
├── src/baet/
│   ├── config/          # Settings, loader
│   ├── core/            # Brain, detectors, enums
│   ├── dashboard/       # Streamlit UI
│   ├── data/            # Ingestion, storage, features
│   ├── database/        # NEW: SQLite models and manager
│   ├── execution/       # Backtest, live client
│   ├── live/            # Live trading
│   ├── paper/           # Paper trading
│   ├── plugins/         # Strategy plugins
│   ├── regimes/         # Regime detection
│   ├── reporting/       # Reports, audit trail
│   ├── risk/            # Risk engine
│   ├── scout/           # NEW: Scout ratio algorithm
│   ├── strategies/      # Strategy implementations
│   └── streaming/       # NEW: WebSocket manager
├── scripts/
│   ├── backtest.py      # Enhanced backtest
│   ├── run_bot.py       # Main bot entry point
│   └── ...
├── Dockerfile           # NEW
├── docker-compose.yml   # NEW
├── .env.example
├── pyproject.toml
└── requirements.txt
```
