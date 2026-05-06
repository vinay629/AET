# Folder Structure

## TL;DR
The repo is split into docs, config, source code, tests, and future data outputs so research and live concerns stay separated.

## Root Layout
- `config/`: YAML runtime configuration by mode
- `src/baet/`: application package
- `tests/`: baseline tests
- `data/`: local market, feature, and results storage
- `logs/`: runtime logs
- `artifacts/`: generated outputs
- `models/`: trained model artifacts

## Package Boundaries
- `src/baet/core/`: shared enums, common models, and app-level primitives
- `src/baet/config/`: config loading and validation
- `src/baet/data/`: ingestion, storage, and feature pipeline entrypoints
- `src/baet/strategies/`: strategy interfaces and future implementations
- `src/baet/risk/`: central risk rules and policy hooks
- `src/baet/execution/`: paper and live execution adapters
- `src/baet/reporting/`: metrics, reports, and summaries

## Ownership Rules
- risk rules must stay separate from strategy logic
- execution code must not own strategy decisions
- config loading must stay centralized
- raw data and derived outputs must never share folders
