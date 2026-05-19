---
description: "Use when writing or modifying ML, data, or backtest code. Enforces prevention of target leakage, train/test contamination, temporal integrity violations, and data snooping. Critical for research validity."
---

# Research Code Safety

Financial ML code has failure modes that silently invalidate all results. Guard against them.

## Temporal Integrity

1. **Never use future data.** A feature at time `t` must only use data available at or before `t`. Never reference `t+1` or later.
2. **Respect event ordering.** In backtests, process events in chronological order. Do not sort, shuffle, or reorder events unless the task explicitly requires it.
3. **Use purged cross-validation.** For time-series CV, always use `baet.ml.purged_cv.PurgedKFold` (or `EmbargoCV` / `CombinatorialPurgedCV`). Never use standard `sklearn.model_selection.KFold` — it leaks information through overlapping labels.
4. **Embargo periods.** When splitting data, add an embargo gap between train and test sets to prevent leakage from overlapping return windows.

## Train/Test Isolation

5. **Never fit on test data.** Scalers, encoders, feature selectors, and any stateful transformer must be fit **only** on training data, then applied to test data.
6. **No peeking at test labels.** Do not use test-set labels for feature engineering, hyperparameter tuning, or model selection.
7. **Separate feature and label computation.** Features and labels must be computed independently. A feature must not incorporate information from the label (even indirectly).

## Target Leakage

8. **Audit for leakage.** Before trusting any backtest result, run `baet.ml.leakage.LeakageDetector.check_all()` on the features and labels.
9. **Watch for "too good" results.** If a backtest shows >80% accuracy or Sharpe >5, suspect leakage. Investigate before celebrating.
10. **Label horizon alignment.** Ensure labels are computed over the correct forward-looking window and do not overlap with feature computation windows.

## Data Snooping

11. **No in-sample optimization on full history.** Hyperparameter tuning must use only training data. Do not optimize on the full dataset and then report it as a backtest result.
12. **Document all data assumptions.** Comment on: data frequency, lookback windows, warm-up periods, survivorship bias handling, and any filtering applied.

## Backtest Realism

13. **Use `baet.core.backtest_realism`** for slippage, fees, and market impact. Do not report frictionless backtest results as realistic.
14. **Account for capacity.** A strategy that works with 10k USDT may not work with 1M USDT. Consider market impact.
15. **Report uncertainty.** Include confidence intervals, walk-forward results, or at minimum out-of-sample performance. Do not report a single in-sample number.

## Anti-Patterns

- Using `df.shift(-1)` to create a feature (this is future data).
- Computing a rolling statistic on the full dataset before splitting.
- Tuning hyperparameters on the test set and calling it a "validation result."
- Reporting a single backtest equity curve without out-of-sample verification.
- Ignoring the `LeakageReport` when it flags issues.
