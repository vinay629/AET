---
description: "Use when creating new modules, adding imports, or restructuring code. Enforces architectural layering and prevents cross-boundary violations, circular dependencies, and abstraction leaks."
---

# Architecture Boundaries

BAET has a strict layered architecture. Respect it.

## Layer Map (dependency order — outer depends on inner, never reverse)

```
cli / dashboard / live          ← entry points, no business logic
  └── strategies / research     ← strategy contracts, signal generation
        └── execution           ← backtest engine, cost model, paper trading
              └── risk          ← risk policies, position sizing, drawdown control
                    └── core    ← events, orders, state, clock, health, invariants
                          └── config / data   ← config models, data loading
                                └── ml        ← leakage, CV, labels, monitoring
```

## Rules

1. **Never import upward.** A module may only import from its own layer or layers below it.
   - `core` must never import from `risk`, `execution`, `strategies`, or `dashboard`.
   - `ml` must never import from `strategies`, `execution`, or `dashboard`.
   - `risk` must never import from `strategies` or `dashboard`.

2. **No circular imports.** If module A imports B, B must not import A. Use lazy imports (`__getattr__` in `__init__.py`) or dependency injection to break cycles.

3. **Do not bypass abstractions.** If a layer exposes a contract (e.g., `StrategyContract`, `RiskPolicy`), use it. Do not reach through layers to access internals.

4. **Extend, don't duplicate.** Before creating a new module or class, check whether an existing abstraction in the same layer can be extended. Prefer adding a new `RiskPolicy` subclass over creating a parallel risk system.

5. **Event-sourced core.** All state changes in `core` flow through `EventStore`. Do not mutate `PortfolioState` directly — emit events and let the state machine apply them.

6. **Config is read-only at runtime.** Configuration is loaded once via `baet.config` and passed down. Do not reload, mutate, or bypass config models after initialization.

## Anti-Patterns

- Importing `baet.strategies` from `baet.core`.
- Creating a new `utils.py` that mixes concerns from multiple layers.
- Adding business logic to `__init__.py` files (they should only re-export).
- Reaching into `baet.core.state` from `baet.execution` to mutate positions directly.
- Duplicating a `RiskPolicy` concept in `strategies` instead of composing with the risk layer.
