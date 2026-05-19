---
description: "Use when about to modify any existing file. Requires reading and understanding the file's full context before making edits to prevent hallucinated refactors and unintended side effects."
---

# Read Before Edit

Before modifying **any** existing file, you must read and understand it. Never edit code you haven't read.

## Rules

1. **Read the full file** — not just the target function or section. Understand imports, exports, surrounding functions, and module-level state.
2. **Understand the architecture** — identify which module this file belongs to, what it exports, and what depends on it. Check for:
   - Shared state or global variables
   - Interface contracts (abstract base classes, protocols, type aliases)
   - Side effects (logging, caching, event emission)
3. **Check for existing tests** — locate and read tests for the file before changing behavior.
4. **Verify your edit is minimal** — change only what is necessary for the task. Do not reformat, rename, or restructure unrelated code.
5. **Never overwrite unrelated logic** — if a file contains multiple concerns, edit only the concern relevant to the task.

## Anti-Patterns

- Editing a function based on its signature alone without reading its body.
- Changing imports without checking all usages in the file.
- Refactoring a module without understanding its consumers.
- Applying a pattern from one file to another without verifying it fits the context.
