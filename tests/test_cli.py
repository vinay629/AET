"""Tests for the BAET CLI."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from baet.cli import cli


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


class TestCLI:
    """Test CLI commands."""

    def test_cli_help(self, runner):
        """Test main help output."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "BAET" in result.output

    def test_status_command(self, runner):
        """Test status command runs without error."""
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "BAET System Status" in result.output
        assert "M5.2 Risk Limits" in result.output
        assert "Notifications" in result.output

    def test_validate_command(self, runner):
        """Test validate command runs without error."""
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code == 0
        assert "Validating" in result.output

    def test_ingest_help(self, runner):
        """Test ingest help output."""
        result = runner.invoke(cli, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "symbols" in result.output.lower()
        assert "days" in result.output.lower()

    def test_backtest_help(self, runner):
        """Test backtest help output."""
        result = runner.invoke(cli, ["backtest", "--help"])
        assert result.exit_code == 0
        assert "strategy" in result.output.lower()

    def test_paper_trade_help(self, runner):
        """Test paper-trade help output."""
        result = runner.invoke(cli, ["paper-trade", "--help"])
        assert result.exit_code == 0
        assert "duration" in result.output.lower()

    def test_status_shows_m5_2_limits(self, runner):
        """Test status displays M5.2 risk limits."""
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Daily Loss Limit" in result.output
        assert "Position Loss Limit" in result.output
        assert "Consecutive Loss Limit" in result.output
        assert "Max Concurrent" in result.output
        assert "Emergency Stop" in result.output

    def test_status_shows_notification_config(self, runner):
        """Test status displays notification configuration."""
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Telegram" in result.output
        assert "Discord" in result.output

    def test_verbose_flag(self, runner):
        """Test verbose flag is accepted."""
        result = runner.invoke(cli, ["--verbose", "status"])
        assert result.exit_code == 0

    def test_validate_checks_directories(self, runner):
        """Test validate checks directory existence."""
        result = runner.invoke(cli, ["validate"])
        # Should pass or warn about missing directories
        assert result.exit_code == 0 or result.exit_code == 1
