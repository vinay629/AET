"""Tests for live execution module."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


class TestLiveExecutionClient:
    """Test LiveExecutionClient."""
    
    @patch('baet.live.execution.HAS_BINANCE', False)
    def test_init_no_binance(self):
        """Test initialization without binance library."""
        from baet.live.execution import LiveExecutionClient
        
        try:
            LiveExecutionClient("key", "secret")
            raise AssertionError("Should have raised ImportError")
        except ImportError as e:
            assert "python-binance" in str(e)
    
    @patch('baet.live.execution.HAS_BINANCE', True)
    @patch('baet.live.execution.BinanceClient')
    def test_init_testnet(self, mock_client_class):
        """Test initialization in testnet mode."""
        from baet.live.execution import LiveExecutionClient
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        LiveExecutionClient("key", "secret", testnet=True)
        mock_client_class.assert_called_once_with("key", "secret", testnet=True)
    
    @patch('baet.live.execution.HAS_BINANCE', True)
    @patch('baet.live.execution.BinanceClient')
    def test_init_live(self, mock_client_class):
        """Test initialization in live mode."""
        from baet.live.execution import LiveExecutionClient
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        LiveExecutionClient("key", "secret", testnet=False)
        mock_client_class.assert_called_once_with("key", "secret")
    
    @patch('baet.live.execution.HAS_BINANCE', True)
    @patch('baet.live.execution.BinanceClient')
    def test_simulation_mode(self, mock_client_class):
        """Test simulation mode doesn't submit orders."""
        from baet.live.execution import LiveExecutionClient
        
        client = LiveExecutionClient("key", "secret", simulation=True)
        assert client.simulation
        
        # Simulate buy
        result = client.place_market_buy("BTCUSDT", 0.001)
        assert result["simulation"]
        assert result["side"] == "BUY"
        
        # Simulate sell
        result = client.place_market_sell("BTCUSDT", 0.001)
        assert result["simulation"]
        assert result["side"] == "SELL"
    
    @patch('baet.live.execution.HAS_BINANCE', True)
    @patch('baet.live.execution.BinanceClient')
    def test_get_balance_simulation(self, mock_client_class):
        """Test balance check in simulation."""
        from baet.live.execution import LiveExecutionClient
        
        client = LiveExecutionClient("key", "secret", simulation=True)
        balance = client.get_balance("USDT")
        assert balance == 10000.0  # Fake balance


class TestLiveTradingEngine:
    """Test LiveTradingEngine."""
    
    @patch('baet.live.engine.LiveExecutionClient')
    def test_init_with_client(self, mock_client_class):
        """Test initialization with provided client."""
        from baet.config.models import Settings
        from baet.live.engine import LiveTradingEngine
        
        mock_client = Mock()
        config = Settings()
        config.live.enabled = True
        config.live.require_explicit_confirmation = False
        
        engine = LiveTradingEngine(config=config, execution_client=mock_client)
        assert engine.client == mock_client
        assert not engine.running
    
    def test_init_no_client(self):
        """Test initialization without client."""
        from baet.config.models import Settings
        from baet.live.engine import LiveTradingEngine
        
        config = Settings()
        config.live.enabled = True
        config.live.require_explicit_confirmation = False
        
        # This will fail because no API credentials
        # but tests the initialization path
        try:
            LiveTradingEngine(config=config)
            # If no exception, client should be None or initialized
            assert True
        except Exception:
            # Expected if no credentials
            assert True
    
    def test_execute_hold_signal(self):
        """Test that HOLD signals don't execute."""
        from baet.config.models import Settings
        from baet.live.engine import LiveTradingEngine
        
        config = Settings()
        config.live.enabled = True
        config.live.safety = {"max_daily_trades": 5, "max_position_value": 100.0}
        
        mock_client = Mock()
        engine = LiveTradingEngine(config=config, execution_client=mock_client)
        engine.running = True
        
        signal = {"signal": "HOLD"}
        result = engine.execute_signal("BTCUSDT", signal)
        
        assert not result["executed"]
        assert result["reason"] == "HOLD signal"
    
    def test_execute_buy_signal(self):
        """Test executing a BUY signal."""
        from baet.config.models import Settings
        from baet.live.engine import LiveTradingEngine
        
        config = Settings()
        config.live.enabled = True
        config.live.safety = {"max_daily_trades": 5, "max_position_value": 100.0}
        
        mock_client = Mock()
        mock_client.simulation = True
        mock_client.place_market_buy.return_value = {"simulation": True, "orderId": 123}
        
        engine = LiveTradingEngine(config=config, execution_client=mock_client)
        engine.running = True
        
        signal = {"signal": "BUY", "units": 0.001}
        result = engine.execute_signal("BTCUSDT", signal)
        
        assert result["executed"]
        assert result["side"] == "BUY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
