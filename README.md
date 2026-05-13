# BAET — Binance Adaptive Ensemble Trader

> A local-first Python platform for researching, simulating, and running algorithmic trading strategies on Binance.

---

## What Is BAET?

BAET is a modular trading system that connects to the **Binance** cryptocurrency exchange. It can:

- **Ingest** real-time and historical market data (candlesticks, order books, trades)
- **Backtest** strategies against historical data with realistic fees and slippage
- **Paper trade** — run strategies in real-time with fake money on Binance's testnet
- **Live trade** — execute real orders on Binance (disabled by default, requires explicit opt-in)
- **Combine** multiple strategies using ensemble methods and regime detection
- **Monitor** everything through a Streamlit dashboard

It is designed to run **locally on your machine** — no cloud services required.

---

## Architecture Overview

```
Market Data (Binance API)
        │
        ▼
┌──────────────────┐
│  Data Ingestion  │  ← Fetches & stores klines in Parquet format
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Feature Pipeline │  ← Technical indicators, volatility, trend features
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Strategy Engine  │  ← 7+ strategies (SMA, RSI, Bollinger, ML, etc.)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Ensemble Layer   │  ← Static & adaptive weighting of strategy signals
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Risk Engine     │  ← Position sizing, drawdown limits, kill-switch
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Execution Layer  │  ← Paper trading loop or live order submission
└──────────────────┘
```

---

## What's Included

| Module | Description |
|---|---|
| **Data Ingestion** | Normalized Binance kline fetching with Parquet storage |
| **Feature Pipeline** | Deterministic technical indicators (returns, volatility, trend, volume) |
| **Strategies** | 7 baseline strategies: Buy & Hold, SMA Crossover, RSI Mean Reversion, Bollinger Bands, EMA Crossover, Breakout Momentum, ADX Trend Filter |
| **ML Strategy** | Random Forest classifier for signal generation |
| **Regime Detection** | Classifies market as trending, ranging, high/low volatility |
| **Ensemble Layer** | Static and adaptive weighting to combine strategy signals |
| **Risk Engine** | Position sizing, max exposure, drawdown protection, circuit breaker |
| **Paper Trading** | Continuous loop that simulates trades on Binance testnet |
| **Live Execution** | Real order submission with testnet support (opt-in only) |
| **Dashboard** | 5-tab Streamlit UI (Overview, Positions, Trades, Performance, Logs) |
| **Reporting** | Strategy comparison, Sharpe/Sortino/Calmar ratios, ranked summaries |

---

## Prerequisites

- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
- A **Binance account** (for API keys)
- A **Binance Testnet account** (for paper trading — free, no real money)

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/vinay629/AET.git
cd AET
```

### 2. Install Dependencies

```bash
uv sync --all-extras
```

This installs all required packages in an isolated virtual environment.

### 3. Set Up Your Environment

Copy the example environment file and fill in your Binance API credentials:

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
BAET_MODE=dev
BAET_LOG_LEVEL=INFO

# Binance Testnet credentials (for paper trading)
BAET_BINANCE_API_KEY=your_testnet_api_key_here
BAET_BINANCE_API_SECRET=your_testnet_api_secret_here

# Binance Live credentials (only needed for live trading)
BAET_LIVE_BINANCE_API_KEY=
BAET_LIVE_BINANCE_API_SECRET=
```

> **Get testnet keys**: Visit [https://testnet.binance.vision](https://testnet.binance.vision), log in, and create an API key under Account → API Management.

### 4. Install Pre-commit Hooks (Recommended)

```bash
pip install pre-commit
pre-commit install
```

This runs code quality checks (linting, formatting, type checking) automatically before each commit.

### 5. Run Tests

```bash
uv run pytest
```

### 6. Launch the Dashboard

```bash
uv run python scripts/run_dashboard.py
```

Then open your browser to `http://localhost:8501`.

---

## Running Modes

BAET supports three modes, configured via `BAET_MODE` in `.env` or `config/<mode>.yaml`:

| Mode | Description | Risk Level |
|---|---|---|
| `dev` | Local development, no trading | None |
| `paper` | Simulated trading on Binance testnet | None (fake money) |
| `live` | Real orders on Binance | **Real money at risk** |

### Start Paper Trading

```bash
BAET_MODE=paper uv run python -m baet
```

### Start Live Trading (⚠️ Use with Caution)

Live trading is **disabled by default**. To enable:

1. Set `BAET_MODE=live` in `.env`
2. Add your live Binance API keys to `.env`
3. Set `live.enabled: true` in `config/live.yaml`
4. Run:

```bash
BAET_MODE=live uv run python -m baet
```

---

## Configuration

Configuration is layered (later sources override earlier ones):

```
config/base.yaml          ← Default values
  ↓ overridden by
config/<mode>.yaml        ← Mode-specific values (dev/paper/live)
  ↓ overridden by
.env environment variables ← Secrets and overrides
```

### Key Config Files

| File | Purpose |
|---|---|
| `config/base.yaml` | Default settings for all modes |
| `config/dev.yaml` | Development mode defaults |
| `config/paper.yaml` | Paper trading settings (testnet, initial balance) |
| `config/live.yaml` | Live trading settings (safety limits, order controls) |

### Example: Paper Trading Config

```yaml
# config/paper.yaml
paper:
  enabled: true
  initial_balance: 10000.0
  loop_interval_seconds: 60
  timeframe: "1h"
  stop_on_error: false
  max_consecutive_errors: 10
```

---

## Project Structure

```
AET/
├── config/              # YAML configuration files (base, dev, paper, live)
├── src/baet/            # Main Python package
│   ├── config/          # Settings models and loader
│   ├── core/            # Brain, detectors, enums, plugins system
│   ├── dashboard/       # Streamlit dashboard (5 tabs)
│   ├── data/            # Binance ingestion, Parquet storage, feature pipeline
│   ├── execution/       # Backtest engine, live client
│   ├── live/            # Live trading execution
│   ├── paper/           # Paper trading engine, portfolio, order simulator
│   ├── plugins/         # Strategy plugins (technical, ML, Markov)
│   ├── regimes/         # Market regime detection
│   ├── reporting/       # Comparison reports, audit trail
│   ├── risk/            # Risk engine, position sizing, kill-switch
│   └── strategies/      # Strategy implementations
├── scripts/             # Utility scripts (dashboard, monitoring, validation)
├── data/                # Data storage (raw, processed, results) — gitignored
├── logs/                # Runtime logs — gitignored
├── .env.example         # Template for API keys and settings
├── pyproject.toml       # Project metadata and dependencies
├── requirements.txt     # Flat dependency list
└── uv.lock              # Reproducible dependency lockfile
```

---

## Key Commands

```bash
# Install dependencies
uv sync --all-extras

# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src/baet --cov-report=term-missing

# Start paper trading
BAET_MODE=paper uv run python -m baet

# Start the dashboard
uv run python scripts/run_dashboard.py

# Validate paper trading results
uv run python scripts/validate_paper_trading.py

# Monitor paper trading in real-time
uv run python scripts/monitor_paper_trading.py

# Run strategy comparison
uv run python scripts/run_strategy_comparison.py

# Check code formatting
uv run ruff format src/

# Lint code
uv run ruff check src/ --fix

# Type check
uv run mypy src/ --strict
```

---

## Safety Features

BAET is designed with multiple layers of protection:

- **Paper trading first** — always validate strategies with fake money before going live
- **Risk engine** — enforces position size limits, max exposure, and drawdown protection
- **Kill-switch** — automatic stop when consecutive errors exceed a threshold
- **Live mode disabled by default** — requires explicit opt-in via config
- **Testnet support** — Binance testnet for safe live-data testing
- **Structured logging** — every decision, signal, and trade is logged in JSON format

---

## Dependencies

| Package | Purpose |
|---|---|
| pandas | Data manipulation |
| numpy | Numerical computing |
| pyarrow | Parquet file storage |
| pydantic | Settings validation |
| pyyaml | YAML config parsing |
| scikit-learn | ML strategy (Random Forest) |
| streamlit | Dashboard UI |
| plotly | Interactive charts |
| python-dotenv | Environment variable loading |
| psutil | System monitoring |

Dev tools: `pytest`, `ruff`, `mypy`, `bandit`, `pre-commit`

---

## Contributing

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and ensure tests pass: `uv run pytest`
3. Code quality checks run automatically on commit (pre-commit hooks)
4. Push and open a Pull Request

---

## License

This project is for educational and research purposes. Use at your own risk. Always test thoroughly with paper trading before using real capital.
