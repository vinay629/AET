# BAET

> Binance Adaptive Ensemble Trader

## TL;DR

BAET is a local-first Python trading research project for Binance. The current branch is in a **stabilization phase**. The verified core is:

- config loading with `YAML + .env`
- Binance market-data normalization and storage
- feature pipeline foundations
- strategy contract and discovery
- portfolio backtesting
- strategy comparison reporting
- one authoritative Streamlit dashboard entrypoint for paper-mode logs

The repo also contains broader experimental modules for live trading, streaming, scout logic, database persistence, and extra dashboard variants, but those are **not part of the current stabilized core baseline**.

## Current Verified Status

The following checks are currently green for the stabilized core slice:

```bash
uv run pytest tests/test_config_core.py tests/test_data_core.py tests/test_strategy_core.py tests/test_backtest_core.py tests/test_dashboard_smoke.py
uv run ruff check src/baet/dashboard/app.py src/baet/dashboard/components.py src/baet/execution/backtest.py src/baet/strategies/baselines.py tests
uv run mypy tests/test_config_core.py tests/test_data_core.py tests/test_strategy_core.py tests/test_backtest_core.py tests/test_dashboard_smoke.py src/baet/dashboard/app.py
```

Current restored test baseline:

- config core tests
- data normalization tests
- strategy contract/discovery tests
- backtester smoke tests
- dashboard smoke tests

## What Is Stable Right Now

| Area | Status |
|---|---|
| Config loader | Verified |
| Data normalization | Verified |
| Candle validation | Verified |
| Strategy discovery | Verified |
| Order-intent backtest path | Verified |
| Dashboard entrypoint | Verified |
| Comparison/reporting foundations | Implemented, not fully revalidated in this sprint |

## What Is Not Yet Stable

These areas exist in the repo but are still outside the current stabilized quality baseline:

- live trading execution
- bridge trading
- streaming manager
- scout engine
- database persistence integration
- notification system
- legacy dashboard variants
- repo-wide strict typing across all modules

## Dashboard

The supported dashboard entrypoint for the stabilization branch is:

```bash
uv run python scripts/run_dashboard.py
```

The dashboard is paper-first and reads local log/output artifacts. It does not require live credentials to start.

Supported dashboard views:

- Overview
- Positions
- Trades
- Performance
- Logs

## Project Layout

```text
AET/
├── config/
├── src/baet/
│   ├── config/
│   ├── core/
│   ├── dashboard/
│   ├── data/
│   ├── execution/
│   ├── reporting/
│   ├── risk/
│   └── strategies/
├── tests/
├── scripts/
├── README.md
├── TODO.md
├── pyproject.toml
└── uv.lock
```

## Quick Start

```bash
uv sync --all-extras
uv run pytest tests/test_config_core.py tests/test_data_core.py tests/test_strategy_core.py tests/test_backtest_core.py tests/test_dashboard_smoke.py
uv run python scripts/run_dashboard.py
```

## Current Priority

The next priority is stabilization, not new features:

1. keep the restored core tests green
2. finish docs/status reconciliation
3. reduce typing debt in kept core modules
4. only then expand back into deferred modules

## Safety Note

Treat this branch as research and stabilization work. Do not assume live trading paths are production ready just because the code exists in the repo.
