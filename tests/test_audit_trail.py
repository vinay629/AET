"""Tests for M5.2 audit trail system."""

import json
import tempfile
from pathlib import Path

import pytest
from baet.reporting.audit_trail import (
    AuditEntry,
    AuditEventType,
    AuditTrail,
    RiskEvaluation,
    TradeSignal,
)


class TestAuditTrail:
    """Test audit trail functionality."""

    @pytest.fixture
    def audit_trail(self):
        """Create audit trail with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(log_dir=Path(tmpdir))
            yield trail
            # Cleanup: remove all handlers to release file locks
            trail.logger.handlers.clear()

    def test_audit_trail_initialization(self, audit_trail):
        """Test audit trail initializes properly."""
        assert audit_trail is not None
        assert audit_trail.log_dir.exists()
        assert len(audit_trail.entries) == 0

    def test_log_trade_signal(self, audit_trail):
        """Test logging a trade signal."""
        audit_trail.log_trade_signal(
            symbol="BTCUSDT",
            action="BUY",
            strategy="sma_crossover",
            confidence=0.85,
            price=42000.0,
            size=0.1,
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.TRADE_SIGNAL
        assert entry.symbol == "BTCUSDT"
        assert entry.action == "BUY"
        assert entry.signal is not None
        assert entry.signal.strategy == "sma_crossover"
        assert entry.signal.confidence == 0.85

    def test_log_risk_evaluation_approved(self, audit_trail):
        """Test logging approved risk evaluation."""
        audit_trail.log_risk_evaluation(
            symbol="BTCUSDT",
            action="BUY",
            approved=True,
            original_size=1.0,
            modified_size=1.0,
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.RISK_EVALUATION
        assert entry.risk_evaluation.approved is True
        assert len(entry.risk_evaluation.violations) == 0

    def test_log_risk_evaluation_rejected(self, audit_trail):
        """Test logging rejected risk evaluation."""
        audit_trail.log_risk_evaluation(
            symbol="BTCUSDT",
            action="BUY",
            approved=False,
            violations=["POSITION_SIZE_EXCEEDS_LIMIT", "DAILY_LOSS_LIMIT_BREACHED"],
            reason="Position size too large",
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.risk_evaluation.approved is False
        assert len(entry.risk_evaluation.violations) == 2
        assert entry.risk_evaluation.reason == "Position size too large"

    def test_log_trade_executed(self, audit_trail):
        """Test logging executed trade."""
        audit_trail.log_trade_executed(
            symbol="BTCUSDT",
            action="BUY",
            quantity=0.1,
            price=42000.0,
            position_id="pos_001",
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.TRADE_EXECUTED
        assert entry.quantity == 0.1
        assert entry.price == 42000.0
        assert entry.position_id == "pos_001"

    def test_log_trade_rejected(self, audit_trail):
        """Test logging rejected trade."""
        audit_trail.log_trade_rejected(
            symbol="BTCUSDT",
            action="BUY",
            reason="POSITION_SIZE_EXCEEDS_LIMIT",
            quantity=1.0,
            price=42000.0,
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.TRADE_REJECTED
        assert entry.reason == "POSITION_SIZE_EXCEEDS_LIMIT"

    def test_log_position_opened(self, audit_trail):
        """Test logging position opened."""
        audit_trail.log_position_opened(
            symbol="BTCUSDT",
            quantity=0.1,
            entry_price=42000.0,
            position_id="pos_001",
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.POSITION_OPENED
        assert entry.symbol == "BTCUSDT"
        assert entry.quantity == 0.1
        assert entry.position_id == "pos_001"

    def test_log_position_closed(self, audit_trail):
        """Test logging position closed."""
        audit_trail.log_position_closed(
            symbol="BTCUSDT",
            quantity=0.1,
            exit_price=43000.0,
            position_id="pos_001",
            entry_price=42000.0,
            p_l=100.0,
            reason="TAKE_PROFIT",
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.POSITION_CLOSED
        assert entry.p_l == 100.0
        assert entry.reason == "TAKE_PROFIT"

    def test_log_portfolio_updated(self, audit_trail):
        """Test logging portfolio update."""
        audit_trail.log_portfolio_updated(
            total_value=50100.0,
            cash_balance=50000.0,
            positions_count=1,
            daily_p_l=100.0,
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.PORTFOLIO_UPDATED
        assert entry.portfolio_value == 50100.0
        assert entry.cash_balance == 50000.0
        assert entry.p_l == 100.0

    def test_log_regime_detected(self, audit_trail):
        """Test logging regime detection."""
        audit_trail.log_regime_detected(regime="TRENDING", volatility=2.5, trend="UP")

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.REGIME_DETECTED
        assert entry.market_condition == "TRENDING"
        assert entry.volatility == 2.5

    def test_log_risk_limit_breach(self, audit_trail):
        """Test logging risk limit breach."""
        audit_trail.log_risk_limit_breach(
            limit_type="daily_loss",
            current_value=10.5,
            limit_value=10.0,
            action_taken="emergency_stop",
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.RISK_LIMIT_BREACH
        assert entry.metadata["limit_type"] == "daily_loss"
        assert entry.metadata["action_taken"] == "emergency_stop"

    def test_log_emergency_stop(self, audit_trail):
        """Test logging emergency stop."""
        audit_trail.log_emergency_stop(reason="MANUAL_STOP", metadata={"user": "admin"})

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.EMERGENCY_STOP
        assert entry.reason == "MANUAL_STOP"

    def test_log_system_error(self, audit_trail):
        """Test logging system error."""
        audit_trail.log_system_error(
            error_message="Connection lost",
            error_type="ConnectionError",
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.SYSTEM_ERROR
        assert entry.error_message == "Connection lost"

    def test_log_daily_summary(self, audit_trail):
        """Test logging daily summary."""
        audit_trail.log_daily_summary(
            total_trades=5,
            winning_trades=3,
            losing_trades=2,
            daily_p_l=150.0,
            daily_return=0.3,
        )

        assert len(audit_trail.entries) == 1
        entry = audit_trail.entries[0]
        assert entry.event_type == AuditEventType.DAILY_SUMMARY
        assert entry.metadata["total_trades"] == 5
        assert entry.metadata["win_rate"] == 60.0

    def test_get_entries_filter_by_type(self, audit_trail):
        """Test filtering entries by type."""
        audit_trail.log_trade_signal(
            symbol="BTCUSDT",
            action="BUY",
            strategy="sma_crossover",
            confidence=0.85,
        )
        audit_trail.log_trade_executed(symbol="BTCUSDT", action="BUY", quantity=0.1, price=42000.0)
        audit_trail.log_trade_executed(symbol="ETHUSDT", action="BUY", quantity=1.0, price=2200.0)

        signals = audit_trail.get_entries(event_type=AuditEventType.TRADE_SIGNAL)
        assert len(signals) == 1

        executed = audit_trail.get_entries(event_type=AuditEventType.TRADE_EXECUTED)
        assert len(executed) == 2

    def test_get_entries_filter_by_symbol(self, audit_trail):
        """Test filtering entries by symbol."""
        audit_trail.log_trade_executed(symbol="BTCUSDT", action="BUY", quantity=0.1, price=42000.0)
        audit_trail.log_trade_executed(symbol="ETHUSDT", action="BUY", quantity=1.0, price=2200.0)

        btc_entries = audit_trail.get_entries(symbol="BTCUSDT")
        assert len(btc_entries) == 1
        assert btc_entries[0].symbol == "BTCUSDT"

        eth_entries = audit_trail.get_entries(symbol="ETHUSDT")
        assert len(eth_entries) == 1
        assert eth_entries[0].symbol == "ETHUSDT"

    def test_export_to_json(self, audit_trail):
        """Test exporting audit trail to JSON."""
        audit_trail.log_trade_signal(
            symbol="BTCUSDT",
            action="BUY",
            strategy="sma_crossover",
            confidence=0.85,
        )
        audit_trail.log_trade_executed(symbol="BTCUSDT", action="BUY", quantity=0.1, price=42000.0)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = Path(f.name)

        try:
            audit_trail.export_to_json(filepath)
            assert filepath.exists()

            with open(filepath) as f:
                data = json.load(f)
            assert len(data) == 2
            assert data[0]["event_type"] == "trade_signal"
            assert data[1]["event_type"] == "trade_executed"
        finally:
            filepath.unlink()

    def test_export_to_jsonl(self, audit_trail):
        """Test exporting audit trail to JSONL."""
        audit_trail.log_trade_signal(
            symbol="BTCUSDT",
            action="BUY",
            strategy="sma_crossover",
            confidence=0.85,
        )
        audit_trail.log_trade_executed(symbol="BTCUSDT", action="BUY", quantity=0.1, price=42000.0)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            filepath = Path(f.name)

        try:
            audit_trail.export_to_jsonl(filepath)
            assert filepath.exists()

            lines = filepath.read_text().strip().split("\n")
            assert len(lines) == 2

            line1 = json.loads(lines[0])
            line2 = json.loads(lines[1])
            assert line1["event_type"] == "trade_signal"
            assert line2["event_type"] == "trade_executed"
        finally:
            filepath.unlink()

    def test_get_daily_report(self, audit_trail):
        """Test getting daily report summary."""
        audit_trail.log_trade_signal(
            symbol="BTCUSDT",
            action="BUY",
            strategy="sma_crossover",
            confidence=0.85,
        )
        audit_trail.log_trade_signal(
            symbol="ETHUSDT",
            action="BUY",
            strategy="rsi_mean_reversion",
            confidence=0.75,
        )
        audit_trail.log_trade_executed(symbol="BTCUSDT", action="BUY", quantity=0.1, price=42000.0)
        audit_trail.log_trade_rejected(
            symbol="ETHUSDT", action="SELL", reason="INSUFFICIENT_BALANCE"
        )

        report = audit_trail.get_daily_report()
        assert report["total_signals"] == 2
        assert report["total_executed"] == 1
        assert report["total_rejected"] == 1
        assert "BTCUSDT" in report["symbols_traded"]

    def test_audit_entry_model(self):
        """Test AuditEntry Pydantic model."""
        entry = AuditEntry(
            event_type=AuditEventType.TRADE_SIGNAL,
            symbol="BTCUSDT",
            action="BUY",
            price=42000.0,
        )

        assert entry.event_type == AuditEventType.TRADE_SIGNAL
        assert entry.symbol == "BTCUSDT"

        # Test serialization
        json_str = entry.model_dump_json()
        assert "BTCUSDT" in json_str
        assert "trade_signal" in json_str

    def test_risk_evaluation_model(self):
        """Test RiskEvaluation Pydantic model."""
        risk_eval = RiskEvaluation(
            approved=False,
            violations=["LIMIT_1", "LIMIT_2"],
            reason="Multiple violations",
        )

        assert risk_eval.approved is False
        assert len(risk_eval.violations) == 2

        json_str = risk_eval.model_dump_json()
        assert "LIMIT_1" in json_str

    def test_trade_signal_model(self):
        """Test TradeSignal Pydantic model."""
        signal = TradeSignal(
            symbol="BTCUSDT",
            action="BUY",
            strategy="sma_crossover",
            confidence=0.85,
            price=42000.0,
            size=0.1,
        )

        assert signal.symbol == "BTCUSDT"
        assert signal.confidence == 0.85

        json_str = signal.model_dump_json()
        assert "sma_crossover" in json_str
