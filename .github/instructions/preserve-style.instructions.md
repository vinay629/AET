---
description: "Use when writing or editing code. Enforces matching the repository's existing conventions for naming, typing, error handling, logging, and structure."
---

# Preserve Existing Style

Match the repository's existing conventions. Do not introduce new patterns when established ones exist.

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | lowercase, no underscores unless needed | `feature_store.py`, `exchange_adapter.py` |
| Classes | PascalCase, noun phrases | `LeakageDetector`, `PortfolioState` |
| Functions | snake_case, verb phrases | `check_all`, `submit_order` |
| Constants | UPPER_SNAKE (only true constants) | `SIGNAL_COLUMNS`, `MAX_RETRIES` |
| Private members | Leading underscore | `_current_trace_id` |
| Enums | StrEnum with lowercase values | `class AppMode(StrEnum): DEV = "dev"` |
| Dataclasses | PascalCase, frozen if immutable | `@dataclass(frozen=True)` |

## Typing Style

- Use `from __future__ import annotations` at the top of every module.
- Use `from collections.abc import Mapping, Sequence` (not `typing.Mapping`).
- Use `X | None` syntax (not `Optional[X]`) — Python 3.13+.
- Use `StrEnum` from `enum` for string enums.
- Add return type annotations to all public functions.

## Error Handling

- Use custom exception classes (e.g., `OrderLifecycleError`, `EventValidationError`).
- Raise with descriptive messages. Never raise bare `Exception`.
- Use `logger = logging.getLogger(__name__)` per module. Do not use root logger.
- Log at appropriate levels: `logger.info` for lifecycle, `logger.warning` for recoverable, `logger.error` for failures.

## Logging Style

- Use structured logging via `baet.core.structured_log.trace()` for decision paths.
- Include relevant context (symbol, side, trace_id) in log messages.
- Do not add `print()` statements. Ever.

## Data Classes

- Use `@dataclass(frozen=True)` for value objects and immutable data.
- Use `@dataclass` (mutable) only for builders or accumulators.
- Define `__all__` in every `__init__.py` with explicit symbol list.

## Imports

- Group: stdlib → third-party → local (`baet.*`).
- Use absolute imports (`from baet.core.events import Event`).
- Re-export from `__init__.py` using `__all__`.
- Use lazy imports (`__getattr__`) in `__init__.py` to avoid circular dependencies.
