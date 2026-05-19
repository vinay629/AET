# BAET Code Constitution

You are the gatekeeper for this repository. Code that violates these rules MUST be rejected.

## 1. Tech Stack & Versions
- **Language:** Python 3.13+
- **Package Manager:** uv
- **Framework:** FastAPI (dashboard), Click (CLI)
- **Data:** pandas, numpy, scikit-learn
- **Testing:** pytest with coverage gates (80% global, 90% research modules)
- **Linting:** ruff (lint + format)
- **Type Checking:** mypy (strict mode)

## 2. Banned Practices (Instant Rejection)
- **NO `print()` statements.** Use `logger = logging.getLogger(__name__)` per module.
- **NO `from module import *`.** All imports must be explicit.
- **NO `SELECT *` or untyped dicts.** All data structures must have explicit types.
- **NO hardcoded credentials.** All secrets via `process.env` or `.env` (never committed).
- **NO `sklearn.model_selection.KFold`.** Use `baet.ml.purged_cv.PurgedKFold` for all CV.
- **NO `shift(-1)` in features.** Features at time `t` must only use data ≤ `t`.
- **NO commits to `main`.** All work on feature branches.
- **NO committing `.env`, `*.pkl`, `*.pt`, `*.csv`, `*.parquet`, `__pycache__/`.**

## 3. Import Architecture (Layer Map)
```
Layer 0: config, data          ← foundation, no internal deps
Layer 1: ml                    ← leakage, CV, labels, monitoring
Layer 2: core                  ← events, orders, state, clock, health
Layer 3: risk                  ← risk policies, position sizing
Layer 4: execution             ← backtest engine, cost model
Layer 5: strategies, research  ← signal generation, experiments
Layer 6: dashboard, cli        ← entry points only
```
**Rule:** A module may only import from its own layer or lower. Never upward.
**Exceptions:** config/data (read-only), core/events, core/enums, core/models, core/structured_log, core/health, core/clock, core/invariants (shared utilities).

## 4. Error Handling Protocol
All errors must use custom exception classes. Never raise bare `Exception`.

**BAD:**
```python
raise Exception("order failed")
```

**GOOD:**
```python
raise OrderLifecycleError(f"Order {order_id} failed: {reason}")
```

## 5. File Structure & Naming
- **Modules:** lowercase, no underscores unless needed (`feature_store.py`)
- **Classes:** PascalCase (`LeakageDetector`, `PortfolioState`)
- **Functions:** snake_case, verb phrases (`check_all`, `submit_order`)
- **Constants:** UPPER_SNAKE (`SIGNAL_COLUMNS`, `MAX_RETRIES`)
- **Private:** leading underscore (`_current_trace_id`)
- **Enums:** `StrEnum` with lowercase values (`class AppMode(StrEnum): DEV = "dev"`)
- **Dataclasses:** `frozen=True` for value objects
- **`__init__.py`:** Must define `__all__` with explicit symbol list

## 6. Typing Rules
- `from __future__ import annotations` at the top of every module
- `from collections.abc import Mapping, Sequence` (not `typing.Mapping`)
- `X | None` syntax (not `Optional[X]`)
- `StrEnum` from `enum` for string enums
- Return type annotations on all public functions

## 7. Testing Requirements
- Every new module must have a corresponding `tests/test_<module>.py`
- Tests must use `from __future__ import annotations`
- ML tests must verify both positive and negative cases
- Research code tests must include leakage detection validation
- Coverage: 80% global minimum, 90% for `src/baet/ml` and `src/baet/core`

## 8. Commit Rules
- Conventional commits only: `feat:`, `fix:`, `refactor:`, `perf:`, `test:`, `docs:`, `chore:`
- Subject line: imperative mood, ≤72 characters, no trailing period
- Body for non-trivial changes: explain what and why
- Atomic commits: one logical change per commit
- Never commit secrets, artifacts, logs, or generated files
