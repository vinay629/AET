## 2025-05-15 - [Backtest Performance Optimization]
**Learning:** Replacing `groupby().iterrows()` with `itertuples()` and manual grouping in Pandas provides a massive performance boost (7x+ in this case) because it avoids the overhead of creating a Series object for each row.
**Action:** Always prefer `itertuples()` or vectorization over `iterrows()` in hot loops. Ensure data is sorted if replacing `groupby(sort=True)`.

## 2025-05-15 - [Environment & Dependency Management]
**Learning:** Running `uv run` on a script that isn't fully compatible with the current environment can trigger a large sync/download in `uv.lock`, which might unintentionally modify the project's core dependencies.
**Action:** Be cautious with `uv run` and always verify `uv.lock` changes before committing. If a script triggers unwanted dependency changes, restore `uv.lock` and investigate the `pyproject.toml` requirements.
