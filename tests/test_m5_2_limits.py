"""Tests for M5.2 risk limit validation."""

import pytest

from baet.config.models import M5Point2RiskLimits
from baet.risk.m5_2_limits import M5Point2RiskTracker


@pytest.fixture
def risk_limits():
    """Create default M5.2 risk limits."""
    return M5Point2RiskLimits(
        enabled=True,
        daily_loss_limit=10.0,
        single_position_loss_limit=5.0,
        consecutive_loss_limit=3,
        max_concurrent_positions=2,
        max_daily_trades=5,
    )


@pytest.fixture
def tracker(risk_limits):
    """Create risk tracker with default limits."""
    return M5Point2RiskTracker(limits=risk_limits)


class TestM5Point2RiskTracker:
    """Test M5.2 risk tracking functionality."""

    def test_tracker_initialization(self, tracker):
        """Test tracker initializes properly."""
        assert tracker.daily_realized_pl == 0.0
        assert tracker.daily_trades == 0
        assert tracker.consecutive_losses == 0
        assert tracker.concurrent_positions == 0
        assert not tracker.emergency_stop_triggered

    def test_can_trade_initial(self, tracker):
        """Test can trade when fresh."""
        can_trade, reason = tracker.check_can_trade()
        assert can_trade is True
        assert reason is None

    def test_reset_daily(self, tracker):
        """Test daily reset."""
        tracker.daily_realized_pl = -5.0
        tracker.daily_trades = 3
        tracker.consecutive_losses = 2
        tracker.position_pls = {"pos_1": -2.0}

        tracker.reset_daily()

        assert tracker.daily_realized_pl == 0.0
        assert tracker.daily_trades == 0
        assert tracker.consecutive_losses == 0
        assert len(tracker.position_pls) == 0

    def test_daily_loss_limit_breach(self, tracker):
        """Test daily loss limit enforcement."""
        tracker.daily_realized_pl = -10.1

        can_trade, reason = tracker.check_can_trade()
        assert can_trade is False
        assert "DAILY_LOSS_LIMIT" in reason
        assert tracker.emergency_stop_triggered  # Should trigger emergency stop

    def test_daily_loss_limit_at_edge(self, tracker):
        """Test at boundary of daily loss limit."""
        tracker.daily_realized_pl = -10.0

        can_trade, reason = tracker.check_can_trade()
        assert can_trade is False  # Exactly at limit is still a breach

    def test_single_position_loss_limit(self, tracker):
        """Test single position loss limit."""
        tracker.on_trade_executed("pos_1", 0.1, 42000.0)
        tracker.on_position_closed("pos_1", 41000.0, 42000.0, 0.1)

        # Loss is -100, which exceeds the -5 single position limit
        assert tracker.daily_realized_pl == -100.0
        assert tracker.emergency_stop_triggered

    def test_consecutive_loss_limit(self, tracker):
        """Test consecutive loss limit."""
        # First loss
        tracker.on_trade_executed("pos_1", 0.1, 42000.0)
        tracker.on_position_closed("pos_1", 41000.0, 42000.0, 0.1)  # Loss
        assert tracker.consecutive_losses == 1

        # Second loss
        tracker.on_trade_executed("pos_2", 0.1, 42000.0)
        tracker.on_position_closed("pos_2", 41000.0, 42000.0, 0.1)  # Loss
        assert tracker.consecutive_losses == 2

        # Third loss - should trigger limit AND emergency stop
        tracker.on_trade_executed("pos_3", 0.1, 42000.0)
        tracker.on_position_closed("pos_3", 41000.0, 42000.0, 0.1)  # Loss
        assert tracker.consecutive_losses == 3
        assert tracker.emergency_stop_triggered  # Should be triggered

        # Now can_trade should be False
        can_trade, reason = tracker.check_can_trade()
        assert can_trade is False
        # Reason will be EMERGENCY_STOP_ACTIVE since that's checked first
        assert reason is not None

    def test_consecutive_loss_reset_on_win(self, tracker):
        """Test consecutive loss counter resets on winning trade."""
        # Loss
        tracker.on_trade_executed("pos_1", 0.1, 42000.0)
        tracker.on_position_closed("pos_1", 41000.0, 42000.0, 0.1)
        assert tracker.consecutive_losses == 1

        # Win
        tracker.on_trade_executed("pos_2", 0.1, 42000.0)
        tracker.on_position_closed("pos_2", 43000.0, 42000.0, 0.1)  # Win
        assert tracker.consecutive_losses == 0

    def test_max_daily_trades_limit(self, tracker):
        """Test max daily trades limit."""
        for i in range(5):
            tracker.on_trade_executed(f"pos_{i}", 0.1, 42000.0)
            tracker.concurrent_positions = i + 1

        assert tracker.daily_trades == 5

        can_trade, reason = tracker.check_can_trade()
        assert can_trade is False
        assert "DAILY_TRADE_LIMIT" in reason

    def test_max_concurrent_positions_limit(self, tracker):
        """Test max concurrent positions limit."""
        tracker.on_trade_executed("pos_1", 0.1, 42000.0)
        assert tracker.concurrent_positions == 1

        can_trade, reason = tracker.check_can_trade()
        assert can_trade is True

        tracker.on_trade_executed("pos_2", 0.1, 42000.0)
        assert tracker.concurrent_positions == 2

        # Now at limit, can't trade more
        can_trade, reason = tracker.check_can_trade()
        assert can_trade is False
        assert "CONCURRENT_POSITIONS" in reason

    def test_emergency_stop_triggered(self, tracker):
        """Test emergency stop blocks trades."""
        tracker.emergency_stop_triggered = True

        can_trade, reason = tracker.check_can_trade()
        assert can_trade is False
        assert "EMERGENCY_STOP" in reason

    def test_trigger_emergency_stop(self, tracker):
        """Test manual emergency stop trigger."""
        tracker.trigger_emergency_stop("MANUAL_STOP")

        assert tracker.emergency_stop_triggered
        assert "MANUAL_STOP" in tracker.last_breach_reason

    def test_reset_emergency_stop(self, tracker):
        """Test resetting emergency stop."""
        tracker.trigger_emergency_stop("TEST")
        assert tracker.emergency_stop_triggered

        tracker.reset_emergency_stop()
        assert not tracker.emergency_stop_triggered

    def test_position_update_stop_loss(self, tracker):
        """Test position update with stop-loss hit."""
        should_close, reason = tracker.on_position_updated("pos_1", -5.1)

        assert should_close is True
        assert "STOP_LOSS_HIT" in reason or "LOSS_LIMIT" in reason
        assert tracker.emergency_stop_triggered

    def test_position_update_no_stop_loss(self, tracker):
        """Test position update without stop-loss."""
        should_close, reason = tracker.on_position_updated("pos_1", -2.0)

        assert should_close is False

    def test_get_status(self, tracker):
        """Test getting current status."""
        tracker.daily_trades = 2
        tracker.daily_realized_pl = -5.0
        tracker.consecutive_losses = 1

        status = tracker.get_status()

        assert status["can_trade"] is True
        assert status["daily_trades"] == 2
        assert status["daily_realized_pl"] == -5.0
        assert status["consecutive_losses"] == 1
        assert status["daily_loss_remaining"] == 5.0

    def test_get_breaches_empty(self, tracker):
        """Test getting breaches when none."""
        breaches = tracker.get_breaches()
        assert len(breaches) == 0

    def test_get_breaches_multiple(self, tracker):
        """Test getting multiple breaches."""
        tracker.daily_realized_pl = -11.0
        tracker.consecutive_losses = 3
        tracker.daily_trades = 5

        breaches = tracker.get_breaches()

        assert len(breaches) >= 2
        assert any("Daily loss" in b for b in breaches)
        assert any("Consecutive" in b for b in breaches)

    def test_m5_2_risk_limits_model(self):
        """Test M5.2RiskLimits Pydantic model."""
        limits = M5Point2RiskLimits(
            enabled=True,
            daily_loss_limit=10.0,
            single_position_loss_limit=5.0,
        )

        assert limits.enabled is True
        assert limits.daily_loss_limit == 10.0
        assert limits.emergency_stop_on_breach is True

    def test_position_closure_under_limit(self, tracker):
        """Test position closure without triggering loss limit."""
        tracker.on_trade_executed("pos_1", 1.0, 42000.0)
        tracker.on_position_closed("pos_1", 41000.0, 42000.0, 1.0)

        # Loss is -1000, exceeds single position limit
        # But consecutive_losses should be 1
        assert tracker.consecutive_losses == 1
        assert tracker.daily_realized_pl == -1000.0

    def test_concurrent_positions_tracking(self, tracker):
        """Test concurrent position tracking."""
        assert tracker.concurrent_positions == 0

        tracker.on_trade_executed("pos_1", 0.1, 42000.0)
        assert tracker.concurrent_positions == 1

        tracker.on_trade_executed("pos_2", 0.1, 42000.0)
        assert tracker.concurrent_positions == 2

        tracker.on_position_closed("pos_1", 43000.0, 42000.0, 0.1)
        assert tracker.concurrent_positions == 1

        tracker.on_position_closed("pos_2", 43000.0, 42000.0, 0.1)
        assert tracker.concurrent_positions == 0

    def test_daily_trade_counting(self, tracker):
        """Test daily trade count."""
        assert tracker.daily_trades == 0

        for i in range(3):
            tracker.on_trade_executed(f"pos_{i}", 0.1, 42000.0)
            assert tracker.daily_trades == i + 1

    def test_emergency_stop_on_breach_disabled(self):
        """Test emergency stop can be disabled."""
        limits = M5Point2RiskLimits(emergency_stop_on_breach=False)
        tracker = M5Point2RiskTracker(limits=limits)

        tracker.daily_realized_pl = -11.0
        can_trade, reason = tracker.check_can_trade()

        # Should still block trading but not trigger auto emergency stop
        assert can_trade is False
        assert not tracker.emergency_stop_triggered
