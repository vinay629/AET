---
description: "Use when editing any file. Enforces the smallest safe change that solves the problem. Avoids unrelated formatting, rewrites, import reshuffling, and touching unaffected code."
---

# Minimal Diff

Make the **smallest change** that correctly solves the problem. Every line in the diff should be justified by the task.

## Rules

1. **Change only what the task requires.** If the task is to fix a bug in one function, do not rewrite neighboring functions.

2. **No unrelated formatting.** Do not reformat lines you didn't change. Do not run formatters on files you only partially edited. (The pre-commit hook handles formatting.)

3. **No import reshuffling.** Do not reorder, remove, or add imports unless the task requires it (e.g., you added a new dependency or removed the last usage of an import).

4. **No renaming without reason.** Do not rename variables, functions, or modules unless the task explicitly asks for it or the name is misleading.

5. **No touching unaffected code.** If a file contains 10 classes and you only need to change one, the diff should only touch that class.

6. **Preserve line count.** If you can fix a bug by changing one line, don't rewrite the entire function.

## Anti-Patterns

- "While I was here, I also reformatted the file."
- "I cleaned up the imports" (when the task was a bug fix).
- "I renamed `x` to `feature_vector` for clarity" (not requested, adds noise).
- Rewriting a 5-line function as a 20-line function when the fix was a one-line change.
- Adding type annotations to a file that has none, when the task was unrelated.
