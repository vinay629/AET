# BAET

## TL;DR
BAET is a local-first Python trading platform scaffold for Binance research, paper trading, and tightly controlled live trading.

## Current Status
Stage 0 is implemented:
- project structure is defined
- config system is in place
- setup docs exist
- testing baseline exists

Stage 1 foundation is also implemented:
- Binance market-data ingestion interfaces exist
- Parquet storage is configured
- feature generation pipeline exists
- portfolio-aware backtester exists
- baseline reporting helpers exist

Strategy library and live trading are still intentionally deferred.
Dashboarding is planned with Streamlit once the project reaches the paper trading stage.

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
3. Run the test baseline:
```bash
uv run pytest
```

## Stage 1 Capabilities
- normalized Binance kline ingestion
- Parquet-based raw and processed data storage
- deterministic feature generation
- portfolio-aware baseline backtesting
- baseline summaries for ingestion, data quality, features, and backtests

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

## CI/CD TODO
- Add GitHub Actions workflows for branch and pull-request validation.
- Run `uv run pytest` on every push and PR to keep the test baseline green.
- Add linting and type checks (`ruff`, `mypy`) for the Python package.
- Validate configuration files and environment setup before deployment.
- Optional: add dependency lockfile validation and vulnerability scanning.

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
