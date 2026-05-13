# BAET

## TL;DR
BAET is a local-first Python trading platform scaffold for Binance research, paper trading, and tightly controlled live trading.

## Current Status
Stages 0 through 5.1b are implemented:
- project structure, config system, setup docs, testing baseline (Stage 0)
- Binance market-data ingestion, Parquet storage, feature generation, portfolio-aware backtester, baseline reporting (Stage 1)
- Strategy contracts, 7 baseline strategies, comparison reporting (Stage 2)
- Regime detection, static/adaptive ensemble, ML strategy integration, intelligence stack validation (Stage 3)
- Centralized risk engine, paper trading loop, structured logging, Streamlit dashboard, observation mode (Stage 4)
- Live readiness controls, live execution path with testnet support (Stage 5.1)

**Test Status**: 203 passed, 3 failed (1 config validation, 2 paper trading `pd` import)

## Repository Layout
- `config/` — YAML configuration definitions and environment modes
- `data/` — data storage and processing targets (mostly ignored for raw/processed/outputs)
- `docs/` — implementation plans and guides
- `logs/` — runtime logs, paper/logging artifacts
- `scripts/` — automation, validation, monitoring, and quick helpers
- `src/` — main Python package code for BAET
- `tests/` — automated test suite
- `.env.example` — template for local secret configuration
- `pyproject.toml` / `requirements.txt` — dependency and packaging metadata
- `uv.lock` — lockfile for reproducible dependencies
- `test_*.py` root scripts — manual test/debug entrypoints
- `test_output.txt` — sample or temporary output file

## Quick Start
1. Install dependencies:
```bash
uv sync --all-extras
```
2. Copy the example secrets file:
```bash
copy .env.example .env
```
3. Install pre-commit hooks:
```bash
pip install pre-commit
pre-commit install
```
4. Run the test baseline:
```bash
uv run pytest
```

## Key Capabilities
- normalized Binance kline ingestion
- Parquet-based raw and processed data storage
- deterministic feature generation
- portfolio-aware baseline backtesting
- 7 baseline strategies (buy_and_hold, sma_crossover, rsi_mean_reversion, bollinger_bands, ema_crossover, breakout_momentum, adx_trend_filter)
- regime detection (trending, ranging, high/low volatility)
- static and adaptive ensemble decision layer
- ML strategy (Random Forest classifier)
- centralized risk engine with position sizing, drawdown protection, kill-switch
- paper trading engine with continuous loop
- structured JSON decision logging
- Streamlit dashboard with 5 tabs
- live execution client with testnet support
- baseline summaries and strategy comparison reports

## Modes
- `dev`: local development defaults
- `paper`: simulated trading configuration
- `live`: live trading configuration, disabled by default

## Config Model
Config precedence is:
1. `config/base.yaml`
2. `config/<mode>.yaml`
3. environment variables loaded from `.env`

Secrets such as Binance API credentials stay in `.env` and must never be committed.

## Developer Notes
- Local artifacts are ignored by `.gitignore`, including `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `logs/`, `data/raw/`, and `data/processed/`.
- Root-level helper scripts like `test_app.py`, `test_simple.py`, `test_minimal.py`, `test_testnet_simple.py`, and `test_observation_mode.py` are intended for manual debugging and not required for package distribution.
- Keep `.env` out of version control and use `.env.example` as the shared template.

## CI/CD
- CI/CD plan documented in `CI-CD_PLAN.md` with GitHub Actions workflows
- Quick start guide in `docs/CI_CD_QUICK_START.md`
- Pre-commit hooks configured for local quality enforcement
- Planned workflows: test.yml, e2e-tests.yml, build.yml, paper-trading.yml, rollback.yml

## Repo Tracking
- durable planning lives in repo markdown files
- active execution tracking should use GitHub issues

Suggested labels:
- `stage-0`
- `stage-1`
- `infra`
- `data`
- `strategy`
- `risk`
- `paper`
- `live`
- `blocked`
