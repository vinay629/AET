"""Tests for reconciliation engine."""

from __future__ import annotations

from decimal import Decimal

import pytest

from baet.core.reconcile import (
    DriftSeverity,
    DriftType,
    ReconciliationEngine,
)


class TestReconciliationEngine:
    def test_consistent_state(self) -> None:
        engine = ReconciliationEngine()
        report = engine.reconcile(
            internal_balances={"BTC": Decimal("1.0"), "USDT": Decimal("5000")},
            exchange_balances={"BTC": Decimal("1.0"), "USDT": Decimal("5000")},
            internal_orders=[],
            exchange_orders=[],
        )
        assert report.is_consistent
        assert not report.should_halt
        assert len(report.drifts) == 0

    def test_balance_drift_warning(self) -> None:
        engine = ReconciliationEngine()
        report = engine.reconcile(
            internal_balances={"BTC": Decimal("1.0")},
            exchange_balances={"BTC": Decimal("1.05")},  # 5% drift
            internal_orders=[],
            exchange_orders=[],
        )
        assert not report.is_consistent
        assert report.warning_count > 0

    def test_balance_drift_critical(self) -> None:
        engine = ReconciliationEngine()
        report = engine.reconcile(
            internal_balances={"BTC": Decimal("1.0")},
            exchange_balances={"BTC": Decimal("2.0")},  # 100% drift
            internal_orders=[],
            exchange_orders=[],
        )
        assert report.critical_count > 0
        assert report.should_halt

    def test_stale_order_detection(self) -> None:
        engine = ReconciliationEngine()
        internal_orders = [
            {"exchange_order_id": "order1", "symbol": "BTCUSDT", "status": "open"},
        ]
        exchange_orders = []  # Exchange doesn't have it
        report = engine.reconcile(
            internal_balances={},
            exchange_balances={},
            internal_orders=internal_orders,
            exchange_orders=exchange_orders,
        )
        stale_drifts = [d for d in report.drifts if d.drift_type == DriftType.STALE_ORDER]
        assert len(stale_drifts) == 1

    def test_unknown_order_critical(self) -> None:
        engine = ReconciliationEngine()
        exchange_orders = [
            {"exchange_order_id": "unknown1", "symbol": "BTCUSDT", "status": "open"},
        ]
        report = engine.reconcile(
            internal_balances={},
            exchange_balances={},
            internal_orders=[],
            exchange_orders=exchange_orders,
        )
        unknown_drifts = [d for d in report.drifts if d.drift_type == DriftType.UNKNOWN_ORDER]
        assert len(unknown_drifts) == 1
        assert unknown_drifts[0].severity == DriftSeverity.CRITICAL

    def test_consecutive_failures_trigger_halt(self) -> None:
        engine = ReconciliationEngine()
        # Three consecutive failures with warnings
        for _ in range(3):
            report = engine.reconcile(
                internal_balances={"BTC": Decimal("1.0")},
                exchange_balances={"BTC": Decimal("1.05")},
                internal_orders=[],
                exchange_orders=[],
            )
        assert report.should_halt
        assert "consecutive" in report.halt_reason.lower()

    def test_summary(self) -> None:
        engine = ReconciliationEngine()
        report = engine.reconcile(
            internal_balances={"BTC": Decimal("1.0")},
            exchange_balances={"BTC": Decimal("2.0")},
            internal_orders=[],
            exchange_orders=[],
        )
        summary = report.summary()
        assert "is_consistent" in summary
        assert "critical" in summary
        assert "drift_types" in summary
