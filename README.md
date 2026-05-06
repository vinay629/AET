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
