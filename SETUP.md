# Setup Guide

## TL;DR
Use `uv` for environment management, YAML for runtime config, and `.env` for secrets.

## Prerequisites
- Python 3.13+
- `uv`

## Local Setup
1. Install dependencies:
```bash
uv sync --all-extras
```
2. Create local secrets file:
```bash
copy .env.example .env
```
3. Adjust config values if needed:
- `config/dev.yaml`
- `config/paper.yaml`
- `config/live.yaml`

## Common Commands
Install and lock environment:
```bash
uv sync --all-extras
```

Run tests:
```bash
uv run pytest
```

Run lint:
```bash
uv run ruff check .
```

Run type checks:
```bash
uv run mypy src
```

## Environment Rules
- use `dev` for local work
- use `paper` for simulated execution
- keep `live` disabled until later stages
- store secrets only in `.env`

## Data Convention
- `data/raw/` for raw downloaded market data
- `data/processed/` for derived datasets and features
- `data/results/` for backtests, reports, and evaluation outputs
- `logs/` for runtime logs
- `artifacts/` for generated assets
- `models/` for trained model outputs in later stages
