# BAET — Stabilization TODO

## TL;DR

This branch is in **stabilization mode**. The goal is to restore one trustworthy core path before expanding further.

## Now

### 1. Keep the restored core green
- [x] Choose one authoritative dashboard entrypoint
- [x] Restore minimal core test collection
- [x] Add dashboard smoke coverage
- [x] Revalidate config, data, strategy, backtest, and dashboard core tests
- [x] Fix broken smoke tests, add missing endpoints, create all four test files
- [ ] Keep the same core checks green after each cleanup pass

### 2. Reconcile status with reality
- [x] Rewrite `README.md` to reflect verified status only
- [x] Update verified-commands in `README.md` and `GUIDE.md` with real file paths
- [x] Deprecate legacy `app.py` → `app_old.py` stub
- [ ] Full docs/usage runthrough to catch any remaining stale references
- [ ] Stop using old milestone assumptions from the earlier branch state

## Next

### 3. Reduce kept-core typing debt
- [ ] Clean `src/baet/config/models.py`
- [ ] Clean `src/baet/config/loader.py`
- [ ] Clean `src/baet/data/binance.py`
- [ ] Clean `src/baet/data/pipeline.py`
- [ ] Clean `src/baet/dashboard/data_loader.py`
- [ ] Clean `src/baet/dashboard/components.py` enough for broader mypy coverage
- [ ] Clean `src/baet/reporting/comparison.py`
- [ ] Clean `src/baet/strategies/baselines.py`

### 4. Decide deferred-module policy
- [ ] Keep deferred modules excluded temporarily and document that choice
- [ ] Or promote one deferred subsystem at a time back into the stabilized core

## Later

### 5. Re-expand safely
- [ ] Reintroduce paper-engine verification beyond smoke level
- [ ] Revalidate comparison/reporting end-to-end
- [ ] Reassess regime, ensemble, and ML modules
- [ ] Reassess live execution path only after paper path is stable
- [ ] Reassess database, scout, streaming, and notifications one subsystem at a time

## Current Verified Commands

```bash
# Full core test suite (all 5 files must exist and pass)
uv run pytest tests/test_config_core.py tests/test_data_core.py tests/test_strategy_core.py tests/test_backtest_core.py tests/test_dashboard_smoke.py

# Ruff — core modules only (configuration/data/strategies/execution)
uv run ruff check src/baet/config src/baet/data src/baet/strategies src/baet/execution src/baet/core src/baet/dashboard/web tests

# MyPy — core modules only (configuration/data/strategies/execution/dashboard)
uv run mypy tests/test_config_core.py tests/test_data_core.py tests/test_strategy_core.py tests/test_backtest_core.py tests/test_dashboard_smoke.py src/baet/dashboard/web/api_server.py
```

## Deferred For Now

- live trading
- bridge trader
- streaming manager
- scout engine
- notifier
- legacy dashboard variants
- repo-wide strict typing
