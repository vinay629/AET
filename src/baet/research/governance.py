"""Research governance layer for BAET.

Prevents silent p-hacking and research contamination by tracking:
- Who ran what experiment, when, and why
- Hypothesis lineage (what was being tested)
- Dataset and feature whitelist usage
- Validation method compliance
- Experiment freeze/archive status
- Effective trials count (multiple testing correction)

This is the difference between a research platform and a collection of notebooks.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class ExperimentPhase(StrEnum):
    IDEA = "idea"
    RESEARCH = "research"
    SANDBOX = "sandbox"
    PAPER = "paper"
    SHADOW = "shadow"
    CAPITALIZED = "capitalized"
    DEGRADED = "degraded"
    RETIRED = "retired"
    FROZEN = "frozen"  # Archived, not to be modified


class ValidationMethod(StrEnum):
    WALK_FORWARD = "walk_forward"
    PURGED_CV = "purged_cv"
    CSCV = "cscv"
    BOOTSTRAP = "bootstrap"
    MONTE_CARLO = "monte_carlo"


@dataclass
class HypothesisRecord:
    """A formal hypothesis being tested."""

    hypothesis_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    text: str = ""  # Human-readable hypothesis
    predicted_direction: str = ""  # "positive", "negative", "neutral"
    predicted_magnitude: str = ""  # "small", "medium", "large"
    required_evidence: str = ""  # What would falsify this
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: str = "active"  # active, confirmed, rejected, ambiguous


@dataclass
class ExperimentRecord:
    """Full governance record for a research experiment."""

    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = ""
    researcher: str = ""
    hypothesis_id: str = ""

    # Lineage
    parent_experiment_id: str = ""  # Derived from another experiment
    strategy_family: str = ""  # Group related strategies
    dataset_hash: str = ""
    feature_set_hash: str = ""

    # Configuration
    symbols: list[str] = field(default_factory=list)
    timeframes: list[str] = field(default_factory=list)
    validation_methods: list[str] = field(default_factory=list)

    # Phase tracking
    phase: ExperimentPhase = ExperimentPhase.IDEA
    phase_history: list[dict[str, str]] = field(default_factory=list)

    # Results
    train_sharpe: float = 0.0
    test_sharpe: float = 0.0
    deflated_sharpe: float = 0.0
    pbo: float = 0.0  # Probability of backtest overfitting
    white_reality_check_p: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    effective_trials: int = 1  # Adjusted for multiple testing

    # Governance
    is_frozen: bool = False
    freeze_reason: str = ""
    dataset_reuse_count: int = 0  # How many times this dataset was used
    validation_set_reuse_count: int = 0
    feature_whitelist_violations: list[str] = field(default_factory=list)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = ""

    # Notes
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def is_statistically_significant(self) -> bool:
        """Check if results survive multiple testing correction."""
        return self.deflated_sharpe > 0.5 and self.white_reality_check_p < 0.05 and self.pbo < 0.5

    @property
    def effective_sharpe(self) -> float:
        """Sharpe adjusted for effective number of trials."""
        if self.effective_trials <= 1:
            return self.test_sharpe
        # Bonferroni-like adjustment
        import math

        penalty = math.log(self.effective_trials) / self.effective_trials
        return self.test_sharpe * (1 - penalty)

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d["phase"] = self.phase.value
        d["is_statistically_significant"] = self.is_statistically_significant
        d["effective_sharpe"] = self.effective_sharpe
        return d


class ResearchGovernance:
    """
    Governance layer that tracks all research activity.

    Prevents:
    - Silent p-hacking (running many tests, reporting only best)
    - Validation set reuse (overfitting to test set)
    - Post-hoc narrative fitting (changing hypothesis after seeing results)
    - Research contamination (using future knowledge)
    """

    def __init__(self, governance_dir: Path) -> None:
        self.governance_dir = governance_dir
        self.governance_dir.mkdir(parents=True, exist_ok=True)
        self._experiments: dict[str, ExperimentRecord] = {}
        self._hypotheses: dict[str, HypothesisRecord] = {}

    def register_hypothesis(
        self,
        text: str,
        predicted_direction: str = "",
        predicted_magnitude: str = "",
        required_evidence: str = "",
    ) -> HypothesisRecord:
        """Register a formal hypothesis before testing."""
        record = HypothesisRecord(
            text=text,
            predicted_direction=predicted_direction,
            predicted_magnitude=predicted_magnitude,
            required_evidence=required_evidence,
        )
        self._hypotheses[record.hypothesis_id] = record
        logger.info(f"Hypothesis registered: {record.hypothesis_id} — {text[:80]}")
        return record

    def create_experiment(
        self,
        name: str,
        hypothesis_id: str,
        researcher: str = "",
        parent_experiment_id: str = "",
        strategy_family: str = "",
        symbols: list[str] | None = None,
        timeframes: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> ExperimentRecord:
        """Create a new experiment with full lineage tracking."""
        record = ExperimentRecord(
            name=name,
            hypothesis_id=hypothesis_id,
            researcher=researcher,
            parent_experiment_id=parent_experiment_id,
            strategy_family=strategy_family,
            symbols=symbols or [],
            timeframes=timeframes or [],
            tags=tags or [],
            phase=ExperimentPhase.RESEARCH,
            phase_history=[
                {
                    "phase": ExperimentPhase.RESEARCH.value,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            ],
        )

        # Track dataset reuse
        if record.dataset_hash:
            reuse_count = sum(
                1 for e in self._experiments.values() if e.dataset_hash == record.dataset_hash
            )
            record.dataset_reuse_count = reuse_count

        self._experiments[record.experiment_id] = record
        self._save_experiment(record)

        logger.info(
            f"Experiment created: {record.experiment_id} ({name}) " f"[{record.phase.value}]"
        )
        return record

    def transition_phase(
        self,
        experiment_id: str,
        new_phase: ExperimentPhase,
        reason: str = "",
    ) -> None:
        """Transition an experiment to a new phase."""
        exp = self._experiments.get(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        old_phase = exp.phase
        exp.phase = new_phase
        exp.updated_at = datetime.now(UTC).isoformat()
        exp.phase_history.append(
            {
                "phase": new_phase.value,
                "timestamp": exp.updated_at,
                "reason": reason,
            }
        )

        if new_phase in (ExperimentPhase.RETIRED, ExperimentPhase.FROZEN):
            exp.is_frozen = True
            exp.freeze_reason = reason
            exp.completed_at = exp.updated_at

        self._save_experiment(exp)
        logger.info(
            f"Experiment {experiment_id}: {old_phase.value} → {new_phase.value}"
            f"{' (' + reason + ')' if reason else ''}"
        )

    def record_results(
        self,
        experiment_id: str,
        train_sharpe: float = 0.0,
        test_sharpe: float = 0.0,
        deflated_sharpe: float = 0.0,
        pbo: float = 0.0,
        white_reality_check_p: float = 0.0,
        max_drawdown_pct: float = 0.0,
        total_trades: int = 0,
        dataset_hash: str = "",
        feature_set_hash: str = "",
        validation_methods: list[str] | None = None,
    ) -> ExperimentRecord:
        """Record experiment results with governance checks."""
        exp = self._experiments.get(experiment_id)
        if exp is None:
            raise ValueError(f"Experiment not found: {experiment_id}")

        if exp.is_frozen:
            raise ValueError(
                f"Experiment {experiment_id} is frozen ({exp.freeze_reason}). "
                f"Cannot modify results."
            )

        exp.train_sharpe = train_sharpe
        exp.test_sharpe = test_sharpe
        exp.deflated_sharpe = deflated_sharpe
        exp.pbo = pbo
        exp.white_reality_check_p = white_reality_check_p
        exp.max_drawdown_pct = max_drawdown_pct
        exp.total_trades = total_trades
        exp.dataset_hash = dataset_hash
        exp.feature_set_hash = feature_set_hash
        exp.validation_methods = validation_methods or []
        exp.updated_at = datetime.now(UTC).isoformat()

        # Compute effective trials
        exp.effective_trials = self._compute_effective_trials(exp)

        # Governance checks
        warnings = self._run_governance_checks(exp)
        if warnings:
            for w in warnings:
                logger.warning(f"Governance warning for {experiment_id}: {w}")

        self._save_experiment(exp)
        return exp

    def _compute_effective_trials(self, exp: ExperimentRecord) -> int:
        """
        Compute effective number of trials for multiple testing correction.

        Counts experiments in the same strategy family that used
        overlapping datasets or features.
        """
        count = 1  # This experiment
        for other in self._experiments.values():
            if other.experiment_id == exp.experiment_id:
                continue
            if other.strategy_family == exp.strategy_family:
                # Same family → likely correlated tests
                if (
                    other.dataset_hash == exp.dataset_hash
                    or other.feature_set_hash == exp.feature_set_hash
                ):
                    count += 1
        return count

    def _run_governance_checks(self, exp: ExperimentRecord) -> list[str]:
        """Run governance checks and return warnings."""
        warnings = []

        # Check dataset reuse
        if exp.dataset_reuse_count > 5:
            warnings.append(
                f"Dataset reused {exp.dataset_reuse_count} times. "
                f"Risk of overfitting to test set."
            )

        # Check validation method
        if not exp.validation_methods:
            warnings.append("No validation method recorded.")

        if ValidationMethod.WALK_FORWARD not in exp.validation_methods:
            warnings.append("Walk-forward validation not used.")

        # Check statistical significance
        if exp.deflated_sharpe < 0.5 and exp.test_sharpe > 1.0:
            warnings.append(
                f"Large gap between test Sharpe ({exp.test_sharpe:.2f}) "
                f"and deflated Sharpe ({exp.deflated_sharpe:.2f}). "
                f"Likely overfitting."
            )

        if exp.pbo > 0.5:
            warnings.append(f"PBO = {exp.pbo:.2f} — high probability of backtest overfitting.")

        if exp.white_reality_check_p > 0.1:
            warnings.append(
                f"White's Reality Check p = {exp.white_reality_check_p:.3f} — "
                f"strategy may not be statistically significant."
            )

        # Check effective trials
        if exp.effective_trials > 10:
            warnings.append(
                f"Effective trials = {exp.effective_trials}. "
                f"Sharpe may be inflated by multiple testing."
            )

        return warnings

    def get_strategy_family_summary(
        self,
        family: str,
    ) -> dict[str, Any]:
        """Get summary statistics for a strategy family."""
        family_exps = [e for e in self._experiments.values() if e.strategy_family == family]

        if not family_exps:
            return {"family": family, "count": 0}

        completed = [e for e in family_exps if e.test_sharpe != 0]
        significant = [e for e in completed if e.is_statistically_significant]

        return {
            "family": family,
            "total_experiments": len(family_exps),
            "completed": len(completed),
            "statistically_significant": len(significant),
            "best_test_sharpe": max((e.test_sharpe for e in completed), default=0),
            "best_deflated_sharpe": max((e.deflated_sharpe for e in completed), default=0),
            "avg_pbo": np.mean([e.pbo for e in completed]) if completed else 0,
            "total_effective_trials": sum(e.effective_trials for e in family_exps),
            "phases": {
                phase.value: sum(1 for e in family_exps if e.phase == phase)
                for phase in ExperimentPhase
            },
        }

    def get_research_dashboard(self) -> dict[str, Any]:
        """Get overall research governance dashboard."""
        all_exps = list(self._experiments.values())
        completed = [e for e in all_exps if e.test_sharpe != 0]
        significant = [e for e in completed if e.is_statistically_significant]

        families = set(e.strategy_family for e in all_exps if e.strategy_family)

        return {
            "total_experiments": len(all_exps),
            "completed": len(completed),
            "statistically_significant": len(significant),
            "significance_rate": len(significant) / len(completed) if completed else 0,
            "strategy_families": list(families),
            "total_effective_trials": sum(e.effective_trials for e in all_exps),
            "phase_distribution": {
                phase.value: sum(1 for e in all_exps if e.phase == phase)
                for phase in ExperimentPhase
            },
            "families": {family: self.get_strategy_family_summary(family) for family in families},
        }

    def _save_experiment(self, exp: ExperimentRecord) -> None:
        """Save experiment record to disk."""
        exp_dir = self.governance_dir / exp.experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        with (exp_dir / "record.json").open("w") as f:
            json.dump(exp.to_dict(), f, indent=2, default=str)

    def load_experiment(self, experiment_id: str) -> ExperimentRecord | None:
        """Load experiment from disk."""
        exp_dir = self.governance_dir / experiment_id
        record_path = exp_dir / "record.json"
        if not record_path.exists():
            return None
        with record_path.open("r") as f:
            data = json.load(f)
        # Reconstruct from dict
        data["phase"] = ExperimentPhase(data["phase"])
        return ExperimentRecord(
            **{k: v for k, v in data.items() if k in ExperimentRecord.__dataclass_fields__}
        )
