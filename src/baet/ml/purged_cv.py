"""Purged cross-validation for financial ML.

Standard K-fold CV leaks information in time series because
overlapping labels share information.

Purged CV removes training samples whose labels overlap with test labels.
Embargo adds an additional gap after test to prevent leakage.

References:
- De Prado, "Advances in Financial Machine Learning" (2018)
- De Prado, "Machine Learning for Asset Managers" (2020)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CVFold:
    """A single cross-validation fold."""
    fold_index: int
    train_indices: np.ndarray
    test_indices: np.ndarray
    purged_count: int = 0
    embargo_count: int = 0


class PurgedKFold:
    """
    K-Fold CV with purging.

    For each fold, training samples whose labels overlap with test labels
    are removed (purged). This prevents information leakage through
    overlapping return windows.

    Args:
        n_splits: Number of folds.
        purge_gap: Number of bars to purge around test set.
        embargo_gap: Number of bars to embargo after test set.
    """

    def __init__(
        self,
        n_splits: int = 5,
        purge_gap: int = 0,
        embargo_gap: int = 0,
    ) -> None:
        self.n_splits = n_splits
        self.purge_gap = purge_gap
        self.embargo_gap = embargo_gap

    def split(
        self,
        n_samples: int,
        label_horizon: int = 1,
    ) -> list[CVFold]:
        """
        Generate purged train/test splits.

        Args:
            n_samples: Total number of samples.
            label_horizon: How many bars each label spans (for overlap detection).

        Returns:
            List of CVFold objects.
        """
        indices = np.arange(int(n_samples))
        fold_size = n_samples // self.n_splits
        folds = []

        for i in range(self.n_splits):
            # Test set
            test_start = i * fold_size
            test_end = min((i + 1) * fold_size, n_samples)
            test_indices = indices[test_start:test_end]

            if len(test_indices) == 0:
                continue

            # Purge zone: bars whose labels overlap with test labels
            # A label at bar t spans [t, t + label_horizon)
            # So we need to purge bars in [test_start - label_horizon, test_end + label_horizon)
            purge_start = max(0, test_start - label_horizon - self.purge_gap)
            purge_end = min(n_samples, test_end + label_horizon + self.purge_gap)

            # Embargo zone: additional gap after purge zone
            embargo_end = min(n_samples, purge_end + self.embargo_gap)

            # Train set: everything except purge zone and embargo zone
            train_mask = np.ones(n_samples, dtype=bool)
            train_mask[purge_start:embargo_end] = False
            train_indices = indices[train_mask]

            folds.append(CVFold(
                fold_index=i,
                train_indices=train_indices,
                test_indices=test_indices,
                purged_count=purge_end - purge_start - len(test_indices),
                embargo_count=embargo_end - test_end,
            ))

        return folds


class EmbargoCV:
    """
    Cross-validation with embargo periods.

    After each test fold, an embargo period is enforced where
    no training is allowed. This prevents forward-looking bias
    from overlapping features.

    Args:
        n_splits: Number of folds.
        embargo_pct: Fraction of training data to embargo (0.0 to 0.1).
    """

    def __init__(
        self,
        n_splits: int = 5,
        embargo_pct: float = 0.01,
    ) -> None:
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct

    def split(self, n_samples: int) -> list[CVFold]:
        """Generate embargo train/test splits."""
        indices = np.arange(n_samples)
        fold_size = n_samples // self.n_splits
        embargo_size = max(1, int(n_samples * self.embargo_pct))
        folds = []

        for i in range(self.n_splits):
            test_start = i * fold_size
            test_end = min((i + 1) * fold_size, n_samples)
            test_indices = indices[test_start:test_end]

            if len(test_indices) == 0:
                continue

            # Embargo: skip bars after test set
            embargo_end = min(n_samples, test_end + embargo_size)

            train_mask = np.ones(n_samples, dtype=bool)
            # Remove test and embargo from training
            if i < self.n_splits - 1:
                train_mask[test_start:embargo_end] = False
            else:
                train_mask[test_start:test_end] = False

            train_indices = indices[train_mask]

            folds.append(CVFold(
                fold_index=i,
                train_indices=train_indices,
                test_indices=test_indices,
                embargo_count=embargo_size,
            ))

        return folds


class CombinatorialPurgedCV:
    """
    Combinatorially Symmetric Cross-Validation (CSCV).

    Generates multiple train/test splits by combinatorially selecting
    which folds are in train vs test. This provides a distribution
    of out-of-sample performance estimates.

    Reference: De Prado (2018), Chapter 12.

    Args:
        n_splits: Number of folds (must be even for symmetry).
        n_test_folds: Number of folds to use as test in each combination.
    """

    def __init__(
        self,
        n_splits: int = 10,
        n_test_folds: int = 2,
        purge_gap: int = 0,
    ) -> None:
        if n_splits % 2 != 0:
            logger.warning(f"n_splits={n_splits} is odd — CSCV works best with even splits")
        self.n_splits = n_splits
        self.n_test_folds = n_test_folds
        self.purge_gap = purge_gap

    def split(
        self,
        n_samples: int,
        label_horizon: int = 1,
    ) -> list[CVFold]:
        """
        Generate combinatorial purged splits.

        For N folds and P test folds, generates C(N, P) combinations.
        Each combination uses P folds for test and N-P for training.
        """
        from itertools import combinations

        indices = np.arange(n_samples)
        fold_size = n_samples // self.n_splits

        # Create base folds
        base_folds = []
        for i in range(self.n_splits):
            start = i * fold_size
            end = min((i + 1) * fold_size, n_samples)
            base_folds.append(indices[start:end])

        # Generate combinations
        fold_indices = list(range(self.n_splits))
        combos = list(combinations(fold_indices, self.n_test_folds))

        cv_folds = []
        for combo_idx, test_fold_idxs in enumerate(combos):
            # Test indices: union of selected folds
            test_indices = np.concatenate([base_folds[i] for i in test_fold_idxs])

            # Train indices: all other folds, purged
            train_fold_idxs = [i for i in fold_indices if i not in test_fold_idxs]

            # Purge zone around test
            purge_mask = np.zeros(n_samples, dtype=bool)
            for fi in test_fold_idxs:
                start = fi * fold_size
                end = min((fi + 1) * fold_size, n_samples)
                purge_start = max(0, start - label_horizon - self.purge_gap)
                purge_end = min(n_samples, end + label_horizon + self.purge_gap)
                purge_mask[purge_start:purge_end] = True

            train_indices = []
            for fi in train_fold_idxs:
                fold_idx = base_folds[fi]
                # Remove purged indices
                clean = fold_idx[~purge_mask[fold_idx]]
                train_indices.append(clean)

            if train_indices:
                train_indices = np.concatenate(train_indices)
            else:
                train_indices = np.array([], dtype=int)

            cv_folds.append(CVFold(
                fold_index=combo_idx,
                train_indices=train_indices,
                test_indices=test_indices,
                purged_count=int(purge_mask.sum()) - len(test_indices),
            ))

        logger.info(
            f"CSCV generated {len(cv_folds)} combinations from "
            f"{self.n_splits} folds (test_folds={self.n_test_folds})"
        )
        return cv_folds
