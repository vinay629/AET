# Folder Structure

## TL;DR
The repo is split into docs, config, source code, tests, and future data outputs so research and live concerns stay separated.

## Root Layout
- `config/`: YAML runtime configuration by mode (base, dev, paper, live)
- `src/baet/`: application package
- `tests/`: automated test suite (203 passing)
- `data/`: local market, feature, and results storage
- `logs/`: runtime logs (paper/, test_validation/)
- `docs/`: implementation plans, guides, and runbooks
- `scripts/`: automation, validation, monitoring, and launcher scripts
- `artifacts/`: generated outputs (if any)
- `models/`: trained model artifacts (if any)

## Package Boundaries
- `src/baet/core/`: shared enums, common models, and app-level primitives
- `src/baet/config/`: config loading and validation
- `src/baet/data/`: ingestion, storage, and feature pipeline entrypoints
- `src/baet/strategies/`: strategy interfaces, 7 baseline strategies, ensemble layer, ML strategy
- `src/baet/risk/`: centralized risk engine, risk policy models, integration helpers
- `src/baet/execution/`: backtest engine and portfolio backtester
- `src/baet/paper/`: paper trading engine, portfolio, order simulator, decision logger
- `src/baet/live/`: live execution client, live trading engine
- `src/baet/regimes/`: regime detection (VolatilityTrendRegimeDetector)
- `src/baet/reporting/`: metrics, reports, strategy comparison, intelligence stack validation
- `src/baet/dashboard/`: Streamlit dashboard (data loader, UI components, main app)
- `src/baet/plugins/`: plugin system for extensibility

## Ownership Rules
- risk rules must stay separate from strategy logic
- execution code must not own strategy decisions
- config loading must stay centralized
- raw data and derived outputs must never share folders
