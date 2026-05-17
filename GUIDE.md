# BAET — User Guide

> **Binance Adaptive Ensemble Trader** — a local-first Python trading research platform.

This guide walks you through installing, configuring, and using BAET for data ingestion, backtesting, paper trading, and live monitoring.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Quick Start](#quick-start)
5. [CLI Commands](#cli-commands)
6. [Running the Dashboard](#running-the-dashboard)
7. [Backtesting](#backtesting)
8. [Paper Trading](#paper-trading)
9. [Live Trading](#live-trading)
10. [Running Tests](#running-tests)
11. [Project Architecture](#project-architecture)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
- **Binance API keys** — required for data ingestion and live/paper trading
  - Create keys at [Binance](https://www.binance.com/en/my/settings/api-management) or [Binance US](https://www.binance.us/en/settings/api-management)
  - For live trading, use **testnet** keys first: [Binance Testnet](https://testnet.binance.vision/)

---

## Installation

### 1. Clone the Repository

```bash
git clone <repo-url>
cd AET
```

### 2. Install Dependencies with uv

```bash
uv sync --all-extras
```

This installs all core dependencies plus optional extras (`research`, `dashboard`, `monitoring`, `websocket`, `notifications`).

### 3. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Required for data ingestion and paper/live trading
BAET_BINANCE_API_KEY=your_api_key_here
BAET_BINANCE_API_SECRET=your_api_secret_here

# Optional: separate keys for live trading (falls back to above if not set)
BAET_LIVE_BINANCE_API_KEY=your_live_api_key_here
BAET_LIVE_BINANCE_API_SECRET=your_live_api_secret_here

# Optional: override the default mode (dev, paper, live)
BAET_MODE=paper

# Optional: override log level
BAET_LOG_LEVEL=INFO
```

### 4. Verify Installation

```bash
uv run baet validate
```

You should see `✅ All checks passed` (or warnings about missing API keys if you haven't set them yet).

---

## Configuration

BAET uses a **layered YAML + .env** configuration system.

### Config Files

| File | Purpose |
|---|---|
| `config/base.yaml` | Default settings for all modes |
| `config/dev.yaml` | Development overrides (debug logging, no trading) |
| `config/paper.yaml` | Paper trading mode (simulated orders, real market data) |
| `config/live.yaml` | Live trading mode (real orders on Binance testnet) |

### How Layering Works

1. `base.yaml` is loaded first.
2. The mode-specific file (e.g., `paper.yaml`) is merged on top.
3. Environment variables from `.env` fill in secrets.

The active mode is determined by (in priority order):
1. The `mode` argument passed to `load_settings()`
2. The `BAET_MODE` environment variable
3. The `app.mode` value in `base.yaml` (default: `dev`)

### Key Configuration Sections

```yaml
# config/base.yaml — key sections

app:
  name: baet
  mode: dev                # dev | paper | live
  logging_level: INFO

market:
  symbols:
    - BTCUSDT
    - ETHUSDT
  timeframes:
    - 1h
    - 4h

paper:
  enabled: true
  initial_balance: 10000.0
  loop_interval_seconds: 60

live:
  enabled: false
  testnet: true            # ALWAYS keep true until you explicitly go live

binance:
  rest_base_url: https://api.binance.us
  websocket_base_url: wss://stream.binance.us:9443/ws
  historical_limit: 1000
  request_timeout_seconds: 30

risk:
  max_risk_per_trade: 0.01       # 1% max risk per trade
  max_portfolio_exposure: 0.20   # 20% max portfolio exposure

backtest:
  initial_cash: 10000.0
  fee_rate: 0.001                # 0.1% trading fee
  slippage_rate: 0.0005          # 0.05% slippage
  execution_price: next_open     # close | next_open
  allocation_per_signal: 0.5     # 50% of capital per signal

dashboard:
  enabled: true
  port: 8501
  theme: light
  auto_refresh: true
  refresh_interval_seconds: 30
```

### Switching Modes

**Via environment variable:**
```bash
BAET_MODE=paper uv run baet status
```

**Via config file:**
Edit `config/base.yaml` and change `app.mode: paper`.

---

## Quick Start

Get from zero to a running paper trade in 4 steps:

```bash
# 1. Install
uv sync --all-extras

# 2. Configure (edit .env with your API keys)
cp .env.example .env
# ... edit .env with your keys ...

# 3. Validate
uv run baet validate

# 4. Check status
uv run baet status
```

---

## CLI Commands

The CLI is available through the `baet` entry point:

```bash
uv run baet --help
```

### Global Options

| Option | Description |
|---|---|
| `-c, --config PATH` | Path to a custom config file |
| `-v, --verbose` | Enable debug-level logging |

### `baet ingest` — Download Historical Data

Downloads candle data from Binance and saves it locally as Parquet files.

```bash
# Default: 30 days of 1h data for BTCUSDT and ETHUSDT
uv run baet ingest

# Custom symbols and timeframe
uv run baet ingest --symbols SOLUSDT --symbols ADAUSDT --timeframe 4h --days 90

# Short form
uv run baet ingest -s SOLUSDT -s ADAUSDT -t 4h -d 90
```

**Options:**

| Option | Default | Description |
|---|---|
| `-s, --symbols` | BTCUSDT, ETHUSDT | Trading pairs to ingest (repeatable) |
| `-d, --days` | 30 | Number of days of history |
| `-t, --timeframe` | 1h | Candle interval (1m, 5m, 15m, 1h, 4h, 1d) |

**Output:** Parquet files saved to `data/raw/<symbol>/<timeframe>/`.

### `baet backtest` — Run Strategy Backtest

Runs a strategy against historical data and produces performance artifacts.

```bash
# Default backtest (buy-and-hold on default symbols)
uv run baet backtest

# Specific strategy and date range
uv run baet backtest --strategy sma_crossover --start 2024-01-01 --end 2024-06-01

# Specific symbols
uv run baet backtest -s BTCUSDT -s ETHUSDT --start 2024-01-01
```

**Options:**

| Option | Default | Description |
|---|---|
| `-s, --strategy` | sma_crossover | Strategy to backtest |
| `--start` | 2024-01-01 | Start date (YYYY-MM-DD) |
| `--end` | 2024-06-01 | End date (YYYY-MM-DD) |
| `-sym, --symbols` | (from config) | Symbols to include (repeatable) |

**Output:** Results saved to `data/results/backtests/` and `data/results/summaries/`.

### `baet paper-trade` — Start Paper Trading

Starts the paper trading engine that runs a continuous loop: fetch data → generate signals → simulate trades.

```bash
# Run with defaults from config
uv run baet paper-trade

# Run for a specific duration
uv run baet paper-trade --duration 7

# Dry run (no trades executed)
uv run baet paper-trade --dry-run
```

**Options:**

| Option | Default | Description |
|---|---|
| `-d, --duration` | None (run until stopped) | Duration in days |
| `--dry-run` | false | Run without executing trades |

**Stopping:** Press `Ctrl+C` to stop gracefully.

### `baet status` — System Status

Displays current configuration, risk limits, notification status, and audit trail info.

```bash
uv run baet status
```

Output includes:
- App name, mode, and version
- Configured symbols and paper balance
- Live trading status and testnet flag
- M5.2 risk limits (daily loss, position loss, consecutive losses)
- Notification channel status (Telegram, Discord)
- Audit trail file count and latest file

### `baet validate` — Validate Configuration

Checks that all directories exist, credentials are present, and risk limits are sane.

```bash
uv run baet validate
```

Reports:
- ❌ **Errors** — missing credentials, invalid risk limits (causes exit code 1)
- ⚠️ **Warnings** — missing directories, mainnet without explicit opt-in
- ✅ **Pass** — all checks green

---

## Running the Dashboard

The dashboard is a **Flask + HTML/JS/CSS** web application for real-time monitoring of paper trading activity. It consists of a Flask REST API server (`api_server.py`) serving a single-page frontend with Chart.js visualizations.

### Launch

**One-click launch** (auto-opens browser):

```bash
# From the project root — opens browser automatically after 2 seconds
uv run python scripts/run_dashboard.py
```

Or use the platform scripts for true double-click launching:

| Platform | File | How |
|---|---|---|
| Windows (CMD) | `run_dashboard.bat` | Double-click in Explorer |
| Windows (PowerShell) | `run_dashboard.ps1` | Right-click → "Run with PowerShell" |
| Any (uv) | `uv run python scripts/run_dashboard.py` | Terminal |

The browser opens automatically to **http://localhost:8501**.

### Dashboard Sections

The single-page dashboard includes:

| Section | Description |
|---|---|
| **Status Strip** | Mode, status, equity, daily P&L, position count, AI signal, risk level |
| **Market Chart** | Interactive OHLCV candlestick chart with symbol/timeframe selectors |
| **Equity Curve** | Portfolio value over time with area fill |
| **Portfolio Overview** | Cash, total value, total return, positions value |
| **Performance Metrics** | Sharpe/Sortino ratios, max drawdown, win rate, volatility, AI score |
| **Positions Table** | Open positions with units, avg/current price, market value, P&L |
| **Recent Trades** | Trade history with action, symbol, cash after, value after |
| **Logs** | Recent log entries with timestamp, type, and message |

### Dashboard Configuration

The dashboard reads from the `dashboard:` section in `config/base.yaml`:

```yaml
dashboard:
  enabled: true
  port: 8501
  theme: "dark"
  auto_refresh: true
  refresh_interval_seconds: 30
  max_recent_trades: 50
  max_log_entries: 100
```

Override the port via environment variable:
```bash
BAET_DASHBOARD_PORT=8502 uv run python scripts/run_dashboard.py
```

### Data Source

The dashboard reads JSONL log files from `logs/paper/`. Each line is a JSON event:

- `PORTFOLIO_UPDATE` — balance, equity, and position updates
- `TRADE` — trade execution events
- `ORDER_FILLED` — order fill notifications
- `RISK_ACTION` — risk management actions

### API Endpoints

The Flask server exposes these REST endpoints:

| Endpoint | Description |
|---|---|
| `GET /` | Main dashboard HTML page |
| `GET /api/status` | System status, equity, daily P&L |
| `GET /api/portfolio` | Current portfolio state |
| `GET /api/equity` | Equity curve data |
| `GET /api/trades` | Recent trades |
| `GET /api/positions` | Open positions with P&L |
| `GET /api/logs` | Recent log entries |
| `GET /api/performance` | Sharpe, Sortino, drawdown, win rate |
| `GET /api/ohlcv/<symbol>` | OHLCV candle data |
| `GET /api/ai-signal` | Latest AI signal and score |
| `GET /api/symbols` | Available trading symbols |
| `GET /api/daily-summary` | Daily P&L summary |

---

## Backtesting

### How It Works

1. **Data** is loaded from local Parquet storage (populated by `baet ingest`).
2. **Signals** are generated by the selected strategy.
3. The **backtest engine** simulates execution with configurable fees and slippage.
4. **Artifacts** (equity curve, trade list, summary) are saved to `data/results/`.

### Running a Backtest

```bash
# Basic backtest
uv run baet backtest --strategy sma_crossover --start 2024-01-01 --end 2024-06-01

# With specific symbols
uv run baet backtest -s BTCUSDT --start 2024-01-01 --end 2024-12-31
```

### Backtest Configuration

Edit `config/backtest:` or override in a custom config:

```yaml
backtest:
  initial_cash: 10000.0
  fee_rate: 0.001          # 0.1% per trade
  slippage_rate: 0.0005    # 0.05% slippage
  execution_price: next_open  # Use next open price for fills
  allocation_per_signal: 0.5  # Allocate 50% of capital per signal
```

### Available Strategies

| Strategy | Module | Description |
|---|---|---|
| `buy_and_hold` | `strategies/baselines.py` | Simple buy-and-hold baseline |
| `sma_crossover` | `strategies/baselines.py` | Simple moving average crossover |

Add new strategies in `src/baet/strategies/` — they must implement the strategy contract defined in `src/baet/strategies/contracts.py`.

---

## Paper Trading

Paper trading runs a **continuous loop** using real market data but simulated orders.

### Starting Paper Trading

```bash
# Ensure paper mode is active
BAET_MODE=paper uv run baet paper-trade

# Or use the observation script (with simulation mode)
uv run python scripts/start_observation.py
```

### Paper Trading Loop

```
┌──────────────────────┐
│  Fetch market data   │ ← Binance API (real-time)
├──────────────────────┤
│  Generate signals    │ ← Strategy module
├──────────────────────┤
│  Risk evaluation     │ ← Risk engine
├──────────────────────┤
│  Simulate execution  │ ← Order simulator (fees + slippage)
├──────────────────────┤
│  Update portfolio    │ ← Paper portfolio
├──────────────────────┤
│  Log results         │ → logs/paper/*.jsonl
└──────────────────────┘
        │
        ▼
   Wait for loop_interval_seconds
        │
        └──→ Repeat
```

### Paper Trading Configuration

```yaml
paper:
  enabled: true
  initial_balance: 10000.0
  loop_interval_seconds: 60    # Check every 60 seconds
  stop_on_error: false
  max_consecutive_errors: 10
  notification_webhook: ""     # Optional alert webhook
```

### Output

- **Logs:** `logs/paper/paper_trading_YYYY-MM-DD.jsonl`
- **Dashboard:** View real-time results at http://localhost:8501

---

## Live Trading

> ⚠️ **WARNING:** Live trading involves real financial risk. Always test thoroughly in paper mode first.

### Enabling Live Trading

1. **Get testnet API keys** from [Binance Testnet](https://testnet.binance.vision/)
2. **Set credentials** in `.env`:
   ```
   BAET_LIVE_BINANCE_API_KEY=your_testnet_key
   BAET_LIVE_BINANCE_API_SECRET=your_testnet_secret
   ```
3. **Enable in config** (`config/live.yaml`):
   ```yaml
   live:
     enabled: true
     testnet: true          # Keep true for testnet
     require_explicit_confirmation: true
   ```
4. **Validate:**
   ```bash
   BAET_MODE=live uv run baet validate
   ```

### M5.2 Risk Limits

The live trading config includes strict M5.2 risk limits:

```yaml
live:
  max_position_size_usdt: 25.0
  max_daily_loss_usdt: 10.0
  max_concurrent_positions: 2
  min_order_interval_seconds: 300
  max_single_loss_usdt: 5.0
  max_consecutive_losses: 3
  max_daily_trades: 5
```

### Safety Features

- **Testnet by default** — `testnet: true` in `config/live.yaml`
- **Explicit confirmation required** — `require_explicit_confirmation: true`
- **Emergency stop file** — create `EMERGENCY_STOP.txt` in the project root to halt trading
- **M5.2 circuit breakers** — automatic stop on daily loss, consecutive losses, or position limits

---

## Running Tests

BAET uses **pytest** with the following test markers:

| Marker | Description |
|---|---|
| `unit` | Fast unit tests |
| `integration` | Moderate-speed integration tests |
| `e2e` | Slow end-to-end tests |
| `skip_ci` | Skip in CI environment |

### Run the Stabilized Core Test Suite

```bash
# Recommended: run the verified core tests
uv run pytest tests/test_config_core.py tests/test_data_core.py tests/test_strategy_core.py tests/test_backtest_core.py tests/test_dashboard_smoke.py
```

### Run All Tests

```bash
uv run pytest
```

### Run by Marker

```bash
# Unit tests only
uv run pytest -m unit

# Exclude slow tests
uv run pytest -m "not e2e"
```

### Linting and Type Checking

```bash
# Ruff linter — core verified modules only
uv run ruff check src/baet/config src/baet/data src/baet/strategies src/baet/execution src/baet/core src/baet/dashboard/web tests

# MyPy type checker — core modules and tests
uv run mypy tests/test_config_core.py tests/test_data_core.py tests/test_strategy_core.py tests/test_backtest_core.py tests/test_dashboard_smoke.py src/baet/dashboard/web/api_server.py
```

---

## Project Architecture

```
AET/
├── config/                  # YAML configuration files
│   ├── base.yaml            # Default settings
│   ├── dev.yaml             # Development overrides
│   ├── paper.yaml           # Paper trading mode
│   └── live.yaml            # Live trading mode
├── src/baet/
│   ├── __main__.py          # Module entry point
│   ├── cli.py               # Click CLI commands
│   ├── config/              # Config loading and validation
│   │   ├── loader.py        # YAML + .env loader with mode merging
│   │   └── models.py        # Pydantic settings models
│   ├── core/                # Core domain models and enums
│   ├── data/                # Data ingestion and storage
│   │   ├── binance.py       # Binance API client
│   │   ├── ingestion.py     # Historical data downloader
│   │   ├── storage.py       # Parquet-based data store
│   │   ├── pipeline.py      # Feature pipeline
│   │   ├── features.py      # Feature engineering
│   │   ├── validation.py    # Data validation
│   │   └── schemas.py       # Data schemas
│   ├── dashboard/           # Flask + HTML/JS/CSS dashboard
│   │   ├── app.py           # Legacy Streamlit app (kept for reference)
│   │   ├── components.py    # Dashboard UI components
│   │   ├── data_loader.py   # Log file reader
│   │   └── web/             # New web dashboard
│   │       ├── api_server.py    # Flask REST API server
│   │       ├── index.html       # Main dashboard page
│   │       ├── styles.css       # Dark terminal theme
│   │       └── dashboard.js     # Chart.js frontend logic
│   ├── execution/           # Trade execution
│   │   └── backtest.py      # Portfolio backtest engine
│   ├── paper/               # Paper trading engine
│   │   ├── engine.py        # Main paper trading loop
│   │   ├── portfolio.py     # Simulated portfolio
│   │   ├── order_simulator.py  # Order execution simulator
│   │   ├── simulation.py    # Simulation mode for observation
│   │   └── logging.py       # Paper trading logger
│   ├── risk/                # Risk management
│   │   ├── engine.py        # Risk evaluation engine
│   │   ├── policy.py        # Risk policy models
│   │   ├── checks.py        # Individual risk checks
│   │   ├── m5_2_limits.py   # M5.2 circuit breaker limits
│   │   └── integration.py   # Risk integration layer
│   ├── strategies/          # Trading strategies
│   │   ├── contracts.py     # Strategy interface contract
│   │   ├── baselines.py     # Baseline strategies (buy-and-hold, SMA)
│   │   ├── discovery.py     # Strategy discovery
│   │   └── adapters.py      # Strategy adapters
│   ├── reporting/           # Performance reporting
│   │   ├── comparison.py    # Strategy comparison
│   │   ├── summaries.py     # Performance summaries
│   │   ├── audit_trail.py   # Audit trail logging
│   │   └── workflows.py     # Reporting workflows
│   ├── plugins/             # Strategy plugins
│   │   ├── technical.py     # Technical analysis plugin
│   │   ├── markov.py        # Markov chain plugin
│   │   └── ml_scoring.py    # ML scoring plugin
│   ├── regimes/             # Market regime detection
│   │   ├── detectors.py     # Regime detectors
│   │   ├── discovery.py     # Regime discovery
│   │   └── contracts.py     # Regime contracts
│   └── notifications.py     # Notification system
├── tests/                   # Test suite
├── scripts/                 # Utility scripts
│   ├── run_dashboard.py     # Dashboard launcher
│   └── start_observation.py # Paper trading observation
├── data/                    # Data storage (created at runtime)
│   ├── raw/                 # Raw Parquet files
│   ├── processed/           # Processed features
│   └── results/             # Backtest results
├── logs/                    # Log files
│   ├── audit/               # Audit trail logs
│   └── paper/               # Paper trading logs
├── pyproject.toml           # Project config and dependencies
├── .env                     # Environment variables (not in git)
└── .env.example             # Example environment file
```

### Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Binance API │────▶│  Data Ingest │────▶│   Storage   │
│  (REST/WS)   │     │  (binance.py)│     │  (Parquet)  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                                                 ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Backtest   │◀────│   Feature    │◀────│  Pipeline   │
│   Engine     │     │   Pipeline   │     │             │
└──────┬──────┘     └──────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Strategies  │────▶│  Risk Engine │────▶│  Execution  │
│  (signals)   │     │  (evaluate)  │     │  (paper/    │
└─────────────┘     └──────────────┘     │   live)     │
                                         └──────┬──────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │  Reporting  │
                                         │  & Dashboard│
                                         └─────────────┘
```

---

## Troubleshooting

### Common Issues

**`❌ Failed to load config`**
- Check that `config/base.yaml` exists and is valid YAML
- Ensure the `BAET_MODE` value matches an existing config file (`dev.yaml`, `paper.yaml`, `live.yaml`)

**`❌ Ingestion failed`**
- Verify your Binance API keys in `.env`
- Check network connectivity to `api.binance.us`
- Ensure the API key has "Enable Reading" permission

**`⚠️ Raw data directory does not exist`**
- Run `uv run baet validate` — it will tell you which directories are missing
- Create them manually or run an ingestion first (they are created automatically)

**Dashboard shows no data**
- Ensure paper trading has been running and producing logs in `logs/paper/`
- Check that the dashboard is reading from the correct log directory

**Tests fail**
- Ensure you're running from the project root (`D:\project\AET`)
- Verify all dependencies are installed: `uv sync --all-extras`
- Check that test data fixtures exist in `tests/`

### Getting Help

```bash
# CLI help
uv run baet --help
uv run baet ingest --help
uv run baet backtest --help
uv run baet paper-trade --help

# Validate your setup
uv run baet validate

# Check system status
uv run baet status
```
