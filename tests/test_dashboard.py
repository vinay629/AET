"""Tests for M4.3.b Streamlit Dashboard."""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from baet.dashboard.data_loader import (
    calculate_daily_summary,
    calculate_performance_metrics,
    find_latest_log_file,
    load_equity_curve,
    load_latest_state,
    load_recent_trades,
    parse_log_file,
)

# ========== Test Data Loader ==========


class TestFindLatestLogFile:
    """Tests for find_latest_log_file."""

    def test_no_directory(self, tmp_path):
        """Test when log directory doesn't exist."""
        result = find_latest_log_file(str(tmp_path / "nonexistent"))
        assert result is None

    def test_empty_directory(self, tmp_path):
        """Test with empty log directory."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        result = find_latest_log_file(str(log_dir))
        assert result is None

    def test_with_log_files(self, tmp_path):
        """Test finding the latest log file."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Create some log files
        (log_dir / "paper_trading_2024-01-01.log").write_text("test\n")
        (log_dir / "paper_trading_2024-01-15.log").write_text("test\n")

        result = find_latest_log_file(str(log_dir))
        assert result is not None
        assert "2024-01-15" in str(result)


class TestParseLogFile:
    """Tests for parse_log_file."""

    def test_no_file(self, tmp_path):
        """Test parsing non-existent file."""
        result = parse_log_file(tmp_path / "nonexistent.log")
        assert result == []

    def test_valid_json_lines(self, tmp_path):
        """Test parsing valid JSON lines."""
        log_file = tmp_path / "test.log"
        log_file.write_text(
            '{"timestamp": "2024-01-01T00:00:00", "type": "ENGINE_EVENT"}\n'
            '{"timestamp": "2024-01-01T00:01:00", "type": "SIGNAL_RECEIVED"}\n'
        )

        result = parse_log_file(log_file)
        assert len(result) == 2
        assert result[0]["type"] == "ENGINE_EVENT"
        assert result[1]["type"] == "SIGNAL_RECEIVED"

    def test_invalid_lines(self, tmp_path):
        """Test parsing with some invalid lines."""
        log_file = tmp_path / "test.log"
        log_file.write_text('{"valid": "json"}\ninvalid line\n{"also": "valid"}\n')

        result = parse_log_file(log_file)
        assert len(result) == 2

    def test_max_entries(self, tmp_path):
        """Test max_entries parameter."""
        log_file = tmp_path / "test.log"
        content = ""
        for i in range(100):
            content += f'{{"line": {i}}}\n'
        log_file.write_text(content)

        result = parse_log_file(log_file, max_entries=10)
        assert len(result) == 10


class TestLoadLatestState:
    """Tests for load_latest_state."""

    def test_no_logs(self, tmp_path):
        """Test with no log files."""
        result = load_latest_state(str(tmp_path))
        assert result == {}

    def test_with_portfolio_update(self, tmp_path):
        """Test loading state from portfolio update."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        log_file = log_dir / "paper_trading_2024-01-01.log"
        log_file.write_text(
            '{"timestamp": "2024-01-01T00:00:00", "type": "PORTFOLIO_UPDATE", '
            '"action": "BUY", "cash": 9000.0, "total_value": 19000.0, '
            '"positions": {"BTCUSDT": {"units": 0.5, "avg_price": 20000.0}}}\n'
        )

        result = load_latest_state(str(log_dir))
        assert "cash" in result
        assert result["cash"] == 9000.0
        assert result["total_value"] == 19000.0


class TestLoadRecentTrades:
    """Tests for load_recent_trades."""

    def test_no_logs(self, tmp_path):
        """Test with no log files."""
        result = load_recent_trades(str(tmp_path))
        assert result == []

    def test_with_trades(self, tmp_path):
        """Test loading recent trades."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        log_file = log_dir / "paper_trading_2024-01-01.log"
        content = ""
        for i in range(10):
            content += (
                f'{{"timestamp": "2024-01-01T00:{i:02d}:00", '
                f'"type": "PORTFOLIO_UPDATE", "action": "BUY", '
                f'"symbol": "BTCUSDT", "cash": {9000 - i * 100}.0, '
                f'"total_value": {19000 + i * 100}.0}}\n'
            )
        log_file.write_text(content)

        result = load_recent_trades(str(log_dir), limit=5)
        assert len(result) <= 5
        assert all(t["action"] == "BUY" for t in result)


class TestLoadEquityCurve:
    """Tests for load_equity_curve."""

    def test_no_logs(self, tmp_path):
        """Test with no log files."""
        result = load_equity_curve(str(tmp_path))
        assert result.empty

    def test_with_data(self, tmp_path):
        """Test loading equity curve data."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        log_file = log_dir / "paper_trading_2024-01-01.log"
        content = ""
        for i in range(10):
            content += (
                f'{{"timestamp": "2024-01-01T00:{i:02d}:00", '
                f'"type": "PORTFOLIO_UPDATE", "cash": {9000 - i * 100}.0, '
                f'"total_value": {19000 + i * 100}.0}}\n'
            )
        log_file.write_text(content)

        result = load_equity_curve(str(log_dir))
        assert not result.empty
        assert "timestamp" in result.columns
        assert "total_value" in result.columns


class TestCalculateDailySummary:
    """Tests for calculate_daily_summary."""

    def test_no_logs(self, tmp_path):
        """Test with no log files."""
        result = calculate_daily_summary(str(tmp_path), date="2024-01-01")
        assert result == {}

    def test_with_data(self, tmp_path):
        """Test calculating daily summary."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        log_file = log_dir / "paper_trading_2024-01-01.log"
        content = ""
        # Add some portfolio updates
        content += (
            '{"timestamp": "2024-01-01T00:00:00", "type": "PORTFOLIO_UPDATE", '
            '"action": "BUY", "cash": 9000.0, "total_value": 19000.0}\n'
        )
        content += (
            '{"timestamp": "2024-01-01T12:00:00", "type": "PORTFOLIO_UPDATE", '
            '"action": "SELL", "cash": 11000.0, "total_value": 21000.0}\n'
        )
        # Add some signals
        content += (
            '{"timestamp": "2024-01-01T00:05:00", "type": "SIGNAL_RECEIVED", "symbol": "BTCUSDT"}\n'
        )
        log_file.write_text(content)

        result = calculate_daily_summary(str(log_dir), date="2024-01-01")
        assert "date" in result
        assert result["date"] == "2024-01-01"
        assert "start_value" in result
        assert "end_value" in result
        assert "daily_pnl" in result
        assert "trade_count" in result
        assert result["trade_count"] == 2


class TestCalculatePerformanceMetrics:
    """Tests for calculate_performance_metrics."""

    def test_no_data(self, tmp_path):
        """Test with no data."""
        result = calculate_performance_metrics(str(tmp_path))
        assert result == {}

    def test_with_equity_curve(self, tmp_path):
        """Test calculating performance metrics."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        log_file = log_dir / "paper_trading_2024-01-01.log"
        content = ""
        # Create equity curve with some variation
        for i in range(20):
            value = 10000 + i * 100 + (i % 3 - 1) * 50
            content += (
                f'{{"timestamp": "2024-01-01T{i:02d}:00:00", '
                f'"type": "PORTFOLIO_UPDATE", "total_value": {value}.0}}\n'
            )
        log_file.write_text(content)

        result = calculate_performance_metrics(str(log_dir))
        assert "sharpe_ratio" in result
        assert "sortino_ratio" in result
        assert "max_drawdown" in result
        assert "total_return" in result


# ========== Test Dashboard Components ==========

# Note: Testing Streamlit components requires mocking Streamlit
# These are more integration tests than unit tests


def test_imports():
    """Test that all dashboard modules can be imported."""
    try:
        # Test data_loader imports
        from baet.dashboard.data_loader import (
            find_latest_log_file,
            load_latest_state,
            load_recent_trades,
        )

        # Test components import (only if streamlit available)
        try:
            from baet.dashboard import components

            assert hasattr(components, "render_portfolio_overview")
        except ImportError:
            pass  # Streamlit not available
        assert True
    except ImportError as e:
        pytest.fail(f"Import error: {e}")


def test_dashboard_module_structure():
    """Test that dashboard module has proper structure."""
    from baet.dashboard import __all__

    # Should have some exports (may be empty if streamlit not available)
    assert isinstance(__all__, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
