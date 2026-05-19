"""Tests for research governance and shadow deployment."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from baet.research.governance import (
    ResearchGovernance,
    ExperimentPhase,
    ExperimentRecord,
    HypothesisRecord,
    ValidationMethod,
)
from baet.research.shadow import (
    ShadowDeploymentManager,
    ShadowStatus,
)


class TestResearchGovernance:
    def test_register_hypothesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(
                text="Mean reversion works in low-vol regimes",
                predicted_direction="positive",
                predicted_magnitude="medium",
            )
            assert h.hypothesis_id is not None
            assert h.status == "active"

    def test_create_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(text="Test hypothesis")
            exp = gov.create_experiment(
                name="test_exp",
                hypothesis_id=h.hypothesis_id,
                researcher="test_user",
                strategy_family="mean_reversion",
                symbols=["BTCUSDT"],
            )
            assert exp.experiment_id is not None
            assert exp.phase == ExperimentPhase.RESEARCH
            assert exp.strategy_family == "mean_reversion"

    def test_transition_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(text="Test")
            exp = gov.create_experiment(name="test", hypothesis_id=h.hypothesis_id)

            gov.transition_phase(exp.experiment_id, ExperimentPhase.PAPER, "Passed research")
            updated = gov._experiments[exp.experiment_id]
            assert updated.phase == ExperimentPhase.PAPER
            assert len(updated.phase_history) == 2

    def test_record_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(text="Test")
            exp = gov.create_experiment(name="test", hypothesis_id=h.hypothesis_id)

            result = gov.record_results(
                exp.experiment_id,
                train_sharpe=1.5,
                test_sharpe=1.2,
                deflated_sharpe=0.8,
                pbo=0.3,
                white_reality_check_p=0.03,
                max_drawdown_pct=15.0,
                total_trades=100,
                validation_methods=[ValidationMethod.WALK_FORWARD],
            )
            assert result.test_sharpe == 1.2
            assert result.is_statistically_significant is True

    def test_frozen_experiment_cannot_be_modified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(text="Test")
            exp = gov.create_experiment(name="test", hypothesis_id=h.hypothesis_id)
            gov.record_results(exp.experiment_id, test_sharpe=1.0)
            gov.transition_phase(exp.experiment_id, ExperimentPhase.FROZEN, "Archived")

            with pytest.raises(ValueError, match="frozen"):
                gov.record_results(exp.experiment_id, test_sharpe=2.0)

    def test_effective_trials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(text="Test")

            # Create 5 experiments in same family with same dataset
            for i in range(5):
                exp = gov.create_experiment(
                    name=f"exp_{i}",
                    hypothesis_id=h.hypothesis_id,
                    strategy_family="test_family",
                )
                gov.record_results(
                    exp.experiment_id,
                    test_sharpe=1.0,
                    dataset_hash="same_dataset",
                )

            # Last experiment should have effective_trials = 5
            exps = list(gov._experiments.values())
            assert exps[-1].effective_trials == 5

    def test_governance_checks_warn_on_overfitting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(text="Test")
            exp = gov.create_experiment(name="test", hypothesis_id=h.hypothesis_id)

            # Record results with large gap between test and deflated Sharpe
            result = gov.record_results(
                exp.experiment_id,
                train_sharpe=3.0,
                test_sharpe=2.5,
                deflated_sharpe=0.2,  # Much lower → overfitting
                pbo=0.8,              # High PBO
                white_reality_check_p=0.15,
                validation_methods=[],  # No validation method
            )
            # Should have warnings but not fail
            assert result.test_sharpe == 2.5

    def test_strategy_family_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(text="Test")

            for i in range(3):
                exp = gov.create_experiment(
                    name=f"exp_{i}",
                    hypothesis_id=h.hypothesis_id,
                    strategy_family="momentum",
                )
                gov.record_results(
                    exp.experiment_id,
                    test_sharpe=0.5 + i * 0.3,
                    deflated_sharpe=0.3 + i * 0.2,
                    pbo=0.3,
                    white_reality_check_p=0.05,
                )

            summary = gov.get_strategy_family_summary("momentum")
            assert summary["total_experiments"] == 3
            assert abs(summary["best_test_sharpe"] - 1.1) < 0.01

    def test_research_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = ResearchGovernance(Path(tmp))
            h = gov.register_hypothesis(text="Test")

            for i in range(3):
                exp = gov.create_experiment(
                    name=f"exp_{i}",
                    hypothesis_id=h.hypothesis_id,
                    strategy_family=f"family_{i}",
                )

            dashboard = gov.get_research_dashboard()
            assert dashboard["total_experiments"] == 3
            assert len(dashboard["strategy_families"]) == 3

    def test_effective_sharpe_adjustment(self) -> None:
        """Effective Sharpe should decrease with more trials."""
        exp = ExperimentRecord(test_sharpe=1.5, effective_trials=1)
        assert abs(exp.effective_sharpe - 1.5) < 0.01

        exp.effective_trials = 10
        assert exp.effective_sharpe < 1.5

        exp.effective_trials = 100
        assert exp.effective_sharpe < 1.5  # Should be lower than raw
        assert exp.effective_sharpe > 0    # But still positive


class TestShadowDeployment:
    def test_create_deployment(self) -> None:
        mgr = ShadowDeploymentManager()
        dep = mgr.create_deployment(
            experiment_id="exp-123",
            strategy_name="test_strategy",
        )
        assert dep.deployment_id is not None
        assert dep.status == ShadowStatus.PENDING

    def test_start_and_record(self) -> None:
        mgr = ShadowDeploymentManager()
        dep = mgr.create_deployment(experiment_id="exp-1", strategy_name="test")
        mgr.start(dep.deployment_id)

        # Record some bars
        for i in range(100):
            mgr.record_bar(
                dep.deployment_id,
                prediction=0.5,
                confidence=0.7,
                actual_return=0.01,
                expected_fill_price=50000,
                actual_fill_price=50010,
                latency_ms=50,
                features={"f1": 0.5},
            )

        updated = mgr.get_deployment(dep.deployment_id)
        assert updated.n_bars == 100
        assert updated.metrics.n_predictions == 100
        assert updated.metrics.avg_slippage_bps > 0

    def test_evaluation_pass(self) -> None:
        mgr = ShadowDeploymentManager()
        dep = mgr.create_deployment(
            experiment_id="exp-1",
            strategy_name="good_strategy",
        )
        # Set permissive thresholds for testing
        dep.min_shadow_bars = 50
        dep.max_slippage_bps = 20.0
        dep.max_latency_ms = 100.0
        dep.min_paper_sharpe = 0.0
        mgr.start(dep.deployment_id)

        # Record good results
        np.random.seed(42)
        for i in range(100):
            mgr.record_bar(
                dep.deployment_id,
                prediction=0.5,
                confidence=0.7,
                actual_return=0.005,
                expected_fill_price=50000,
                actual_fill_price=50003,
                latency_ms=30,
                features={"f1": 0.5},
            )

        result = mgr.evaluate(dep.deployment_id)
        assert result["all_passed"] is True

    def test_evaluation_fail(self) -> None:
        mgr = ShadowDeploymentManager()
        dep = mgr.create_deployment(
            experiment_id="exp-1",
            strategy_name="bad_strategy",
            min_shadow_bars=50,
        )
        mgr.start(dep.deployment_id)

        # Record poor results (high slippage, low accuracy)
        np.random.seed(42)
        for i in range(100):
            mgr.record_bar(
                dep.deployment_id,
                prediction=0.5 if i % 2 == 0 else -0.5,
                confidence=0.9,
                actual_return=-0.01,  # Always wrong
                expected_fill_price=50000,
                actual_fill_price=50100,  # High slippage
                latency_ms=600,  # High latency
                features={"f1": 0.5},
            )

        result = mgr.evaluate(dep.deployment_id)
        assert result["all_passed"] is False

    def test_promote_passed_deployment(self) -> None:
        mgr = ShadowDeploymentManager()
        dep = mgr.create_deployment(experiment_id="exp-1", strategy_name="test")
        dep.status = ShadowStatus.PASSED

        mgr.promote(dep.deployment_id)
        assert dep.status == ShadowStatus.PROMOTED

    def test_cannot_promote_failed(self) -> None:
        mgr = ShadowDeploymentManager()
        dep = mgr.create_deployment(experiment_id="exp-1", strategy_name="test")
        dep.status = ShadowStatus.FAILED

        with pytest.raises(ValueError, match="not passed"):
            mgr.promote(dep.deployment_id)

    def test_reject_deployment(self) -> None:
        mgr = ShadowDeploymentManager()
        dep = mgr.create_deployment(experiment_id="exp-1", strategy_name="test")
        mgr.start(dep.deployment_id)

        mgr.reject(dep.deployment_id, "Too much slippage")
        assert dep.status == ShadowStatus.REJECTED

    def test_list_deployments(self) -> None:
        mgr = ShadowDeploymentManager()
        for i in range(3):
            mgr.create_deployment(experiment_id=f"exp-{i}", strategy_name=f"strat_{i}")

        all_deps = mgr.list_deployments()
        assert len(all_deps) == 3

        pending = mgr.list_deployments(status=ShadowStatus.PENDING)
        assert len(pending) == 3
