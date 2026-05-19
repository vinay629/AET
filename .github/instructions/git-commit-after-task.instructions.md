---
description: "Use when finishing any coding task, feature, fix, or modification. Enforces creating a clean git commit only after work is complete, coherent, and validated. Covers commit preconditions, message format, staging rules, and exceptions."
---

# Git Commit After Task Completion

After completing a coding task, create a git commit **if and only if** the work is in a stable and validated state. Do not commit broken, partial, or experimental work.

## Commit Preconditions

Before committing, verify **all** of the following:

1. **Review changes** — run `git status` and `git diff` to inspect every staged and unstaged file.
2. **Implementation is complete** — no unfinished placeholders, stubs, or `TODO`/`FIXME`/`WIP` markers left in changed files.
3. **No debugging artifacts** — no `print()` statements, `breakpoint()` calls, or commented-out debug code accidentally left behind.
4. **No secrets or credentials** — no `.env` files, API keys, tokens, or credential files are staged.
5. **Only task-relevant files** — unrelated changes, build artifacts, logs, and generated files are excluded.

## Validation Gate

Run relevant validation **before** committing. At minimum:

- **Tests** — run the test suite (`uv run pytest`) or at least tests covering the changed modules.
- **Lint** — run `ruff check .` to catch style and correctness issues.
- **Format** — run `ruff format --check .` to ensure consistent formatting.
- **Type check** — run `mypy src/` if the project uses type hints (check for `pyproject.toml` mypy config).

**Do not commit if validation is failing and unresolved.** Fix the issues first, or explicitly note why a known failure is acceptable.

## Commit Message Rules

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use When |
|--------|----------|
| `feat:` | New feature or capability |
| `fix:` | Bug fix |
| `refactor:` | Code restructuring without behavior change |
| `perf:` | Performance improvement |
| `test:` | Adding or updating tests |
| `docs:` | Documentation changes |
| `chore:` | Maintenance, config, or tooling changes |

### Format

```
type(scope): short imperative summary
```

- Subject line: imperative mood, ≤72 characters, no trailing period.
- For non-trivial changes, include a body explaining **what** changed and **why**.

### Example

```
feat(brain): add adaptive threshold for signal confirmation

Adds a dynamic threshold that adjusts based on recent volatility,
reducing false signals during low-volume periods.
```

## Staging Rules

- Stage only files directly related to the task.
- Prefer small, logical commits over large mixed commits. Separate refactors, features, tests, and formatting into distinct commits.
- If unrelated changes exist in the working tree, stage selectively (`git add -p` or specific files) rather than using `git add .`.

## Exceptions — Do Not Commit When

- The user explicitly says not to (e.g., "don't commit yet", "WIP").
- The task is exploratory or experimental.
- The repository is intentionally mid-refactor.
- Validation is failing and unresolved.
- You are unsure whether the change is complete or correct.
