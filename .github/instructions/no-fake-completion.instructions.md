---
description: "Use when reporting task completion or summarizing work done. Enforces honest, evidence-based completion claims. Never claim a task is complete unless files were actually modified, validation actually ran, and results were actually observed."
---

# Never Fake Completion

Never claim a task is complete unless you have **direct evidence** that the work succeeded.

## Rules

A task is complete **only when all** of the following are true:

1. **Files were actually modified** — you have the edit tool results confirming the changes were written.
2. **Validation actually ran** — you executed tests, lint, type checks, or other validation and observed the output.
3. **Results were actually observed** — you read the output of validation commands and confirmed they passed (or you explicitly document known, acceptable failures).
4. **No silent failures** — you did not ignore errors, suppress output, or skip validation steps.

## What to Do Instead

- If a test fails after your change, **report the failure** and either fix it or ask the user how to proceed.
- If you couldn't run validation (e.g., missing dependency), **state that explicitly** rather than assuming it would pass.
- If the change is partial, **say so**: "I've updated X but Y still needs work."
- If you're uncertain about correctness, **say so**: "I've made the change but recommend reviewing Z before committing."

## Anti-Patterns

- "The tests should pass now." → Run them and report actual results.
- "Everything looks good." → Provide evidence: which tests passed, what lint showed.
- "I've refactored the module." → Show what actually changed and verify nothing broke.
- Summarizing work as done when you only read files but didn't edit anything.
