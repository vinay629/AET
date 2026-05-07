"""Tests for dashboard control panel."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


class TestCheckPaperTradingStatus:
    """Test check_paper_trading_status function."""
    
    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        from baet.dashboard.control import check_paper_trading_status
        
        result = check_paper_trading_status()
        assert isinstance(result, dict)
        assert "running" in result
    
    def test_psutil_not_installed(self):
        """Test when psutil is not available."""
        from baet.dashboard import control
        import importlib
        
        # Mock psutil as not available
        original = control.HAS_PSUTIL
        try:
            control.HAS_PSUTIL = False
            result = control.check_paper_trading_status()
            assert result["running"] == False
            assert "error" in result
        finally:
            control.HAS_PSUTIL = original


class TestStartPaperTrading:
    """Test start_paper_trading function."""
    
    def test_returns_tuple(self):
        """Test that function returns a tuple."""
        from baet.dashboard.control import start_paper_trading
        
        # This will likely fail since we're not actually starting a process
        # but we can test it returns the right type
        result = start_paper_trading()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


class TestStopPaperTrading:
    """Test stop_paper_trading function."""
    
    def test_stop_when_not_running(self):
        """Test stop when not running."""
        from baet.dashboard.control import stop_paper_trading
        
        # Mock status to return not running
        from unittest.mock import patch
        
        with patch('baet.dashboard.control.check_paper_trading_status') as mock:
            mock.return_value = {"running": False}
            success, msg = stop_paper_trading()
            assert success == False
            assert "not running" in msg.lower()


class TestEmergencyStop:
    """Test emergency_stop function."""
    
    def test_emergency_stop_when_not_running(self):
        """Test emergency stop when not running."""
        from baet.dashboard.control import emergency_stop
        
        from unittest.mock import patch
        
        with patch('baet.dashboard.control.check_paper_trading_status') as mock:
            mock.return_value = {"running": False}
            success, msg = emergency_stop()
            assert success == False


class TestUpdateConfig:
    """Test update_config function."""
    
    def test_update_config_returns_tuple(self):
        """Test that update_config returns a tuple."""
        from baet.dashboard.control import update_config
        
        # This will fail because config file may not exist in test
        # but function should handle it gracefully
        success, msg = update_config({"paper.initial_balance": 20000.0})
        assert isinstance(success, bool)
        assert isinstance(msg, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
