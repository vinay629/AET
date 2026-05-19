---
description: "Use when staging and committing changes. Enforces small, logical, atomic commits over large mixed commits. Separate refactors, features, tests, formatting, and config changes into distinct commits."
---

# Atomic Commits

Each commit should represent a **single logical change**. Keep commits small, focused, and independently revertible.

## Rules

1. **One concern per commit** — do not mix unrelated changes in a single commit.
2. **Separate by type:**
   - Refactors → their own commit(s)
   - New features → their own commit(s)
   - Tests → separate from implementation (or paired if TDD-style)
   - Formatting/lint fixes → isolated commit, never mixed with logic changes
   - Config/dependency changes → isolated commit
3. **Stage selectively** — use `git add -p` or specific file paths. Avoid `git add .` unless every changed file belongs to the same logical change.
4. **Each commit should pass validation independently** — don't create a commit that depends on a later commit to pass tests.

## When to Split

| Situation | Action |
|-----------|--------|
| Changed 3+ unrelated modules | Split into per-module commits |
| Refactored + added feature | Two commits: refactor first, feature second |
| Fixed lint while implementing | Two commits: lint fix first, feature second |
| Added tests for existing code | Separate commit from any behavior changes |

## When to Combine

| Situation | Action |
|-----------|--------|
| Small feature + its tests in same module | Single commit is fine |
| Rename that touches many files but is mechanical | Single commit |
| Fix that requires simultaneous changes in 2 tightly coupled files | Single commit |
