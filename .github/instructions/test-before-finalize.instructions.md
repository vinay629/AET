---
description: "Use when completing any task that modifies code behavior. Requires running relevant tests before claiming work is done. Applies to bug fixes, new features, refactors, and configuration changes."
---

# Test Before Finalize

Before claiming any task is complete, run tests to verify your changes work and haven't broken existing behavior.

## Rules

1. **Run tests after every behavior change** — bug fixes, new features, refactors, and config changes all require test validation.
2. **Run the relevant scope:**
   - Changed a single module → run its specific test file: `uv run pytest tests/test_<module>.py -v`
   - Changed shared/core code → run the full suite: `uv run pytest -v`
   - Changed config or infrastructure → run integration tests if they exist
3. **Read the output** — don't just check the exit code. Look for:
   - Failures in tests you didn't expect to change
   - Warnings about deprecations or resource leaks
   - Slow tests that might indicate a performance regression
4. **Fix or report failures** — if a test fails after your change:
   - If the failure is expected (you changed the behavior), update the test.
   - If the failure is unexpected, fix the code or report it to the user.
   - Never ignore a failing test and claim the task is done.
5. **If no tests exist**, note that explicitly: "No tests exist for this module. Consider adding coverage."

## When Tests Are Not Applicable

Some changes don't need test runs:
- Documentation-only changes (`.md` files with no code changes)
- Comment or docstring updates
- `.gitignore` or config-only changes with no behavior impact
- Formatting/lint-only changes

Even for these, run lint/format checks to verify nothing broke.
