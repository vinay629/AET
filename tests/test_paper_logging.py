"""Tests for M4.3.a Paper Trading Logs Explain Decisions End-to-End."""

import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from baet.paper.logging import PaperTradingLogger, create_paper_logger_from_config
from baet.paper.portfolio import PaperPortfolio
from baet.paper.order_simulator import PaperOrderSimulator


def close_logger(logger):
    """Close logger handlers to release file locks (Windows)."""
    if logger and hasattr(logger, '_logger'):
        for handler in logger._logger.handlers:
            handler.close()
        logger._logger.handlers.clear()


# ========== Test PaperTradingLogger ==========

def test_logger_initialization():
    """Test PaperTradingLogger initializes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(
            log_dir=tmpdir,
            level="DEBUG",
            rotation="daily",
            max_files=5,
        )
        
        try:
            assert logger.log_dir == Path(tmpdir)
            assert logger.level == 10  # DEBUG
            assert logger.rotation == "daily"
            assert logger.max_files == 5
        finally:
            close_logger(logger)


def test_logger_creates_log_file():
    """Test that logger creates log file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        try:
            # Check that log file was created
            log_files = list(Path(tmpdir).glob("paper_trading_*.log"))
            assert len(log_files) >= 1
        finally:
            close_logger(logger)


def test_logger_log_signal():
    """Test logging a signal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        logger.log_signal_received(
            symbol="BTCUSDT",
            signal={"direction": "BUY", "strength": 0.8, "strategy": "sma_crossover"},
        )
        
        # Read log file and verify
        log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) >= 1
        
        # Parse the last line as JSON
        entry = json.loads(lines[-1])
        assert entry["type"] == "SIGNAL_RECEIVED"
        assert entry["symbol"] == "BTCUSDT"
        assert entry["signal"]["direction"] == "BUY"
        
        close_logger(logger)


def test_logger_log_risk_evaluation():
    """Test logging a risk evaluation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        logger.log_risk_evaluation(
            symbol="BTCUSDT",
            signal={"direction": "BUY"},
            result={"passed": True, "violations": []},
        )
        
        # Read log file and verify
        log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        entry = json.loads(lines[-1])
        assert entry["type"] == "RISK_EVALUATION"
        assert entry["result"]["passed"] == True
        
        close_logger(logger)


def test_logger_log_order_simulated():
    """Test logging an order simulation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        logger.log_order_simulated(
            symbol="BTCUSDT",
            side="BUY",
            requested_price=20000.0,
            filled_price=20010.0,
            units=0.5,
            fee=10.0,
            slippage=10.0,
        )
        
        # Read log file and verify
        log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        entry = json.loads(lines[-1])
        assert entry["type"] == "ORDER_SIMULATED"
        assert entry["side"] == "BUY"
        assert entry["filled_price"] == 20010.0
        
        close_logger(logger)


def test_logger_log_portfolio_update():
    """Test logging a portfolio update."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        logger.log_portfolio_update(
            action="BUY",
            symbol="BTCUSDT",
            cash=9000.0,
            positions={"BTCUSDT": {"units": 0.5, "avg_price": 20000.0}},
            total_value=19000.0,
        )
        
        # Read log file and verify
        log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        entry = json.loads(lines[-1])
        assert entry["type"] == "PORTFOLIO_UPDATE"
        assert entry["action"] == "BUY"
        assert entry["cash"] == 9000.0
        
        close_logger(logger)


def test_logger_log_engine_event():
    """Test logging an engine event."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        logger.log_engine_event("ENGINE_STARTED", {"loop_interval": 60})
        
        # Read log file and verify
        log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        entry = json.loads(lines[-1])
        assert entry["type"] == "ENGINE_EVENT"
        assert entry["event"] == "ENGINE_STARTED"
        
        close_logger(logger)


def test_logger_log_error():
    """Test logging an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            logger.log_error(e, context={"iteration": 1})
        
        # Read log file and verify
        log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Error should be logged as both JSON and Python logger
        assert len(lines) >= 1
        
        close_logger(logger)


def test_logger_disabled():
    """Test logger with logging disabled."""
    logger = create_paper_logger_from_config({"enabled": False})
    assert logger is None


def test_logger_from_config():
    """Test creating logger from config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "enabled": True,
            "level": "INFO",
            "directory": tmpdir,
            "rotation": "daily",
            "max_files": 10,
        }
        
        logger = create_paper_logger_from_config(config)
        
        try:
            assert logger is not None
            assert logger.level == 20  # INFO
        finally:
            close_logger(logger)


# ========== Test Integration with Portfolio ==========

def test_portfolio_with_logger():
    """Test that portfolio logs trades when logger is provided."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        portfolio = PaperPortfolio(initial_balance=20000.0, logger=logger)  # Enough balance
        
        result = portfolio.buy(symbol="BTCUSDT", units=0.5, price=20000.0, fee=10.0)
        assert result == True  # Buy should succeed
        
        # Check that trade was logged
        log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Should have portfolio update log (last entry should be PORTFOLIO_UPDATE)
        assert len(lines) >= 2  # At least init + update
        # Find the PORTFOLIO_UPDATE entry
        portfolio_updates = [json.loads(line) for line in lines if json.loads(line).get("type") == "PORTFOLIO_UPDATE"]
        assert len(portfolio_updates) >= 1
        
        close_logger(logger)
        
        close_logger(logger)


def test_portfolio_without_logger():
    """Test that portfolio works without logger."""
    portfolio = PaperPortfolio(initial_balance=20000.0, logger=None)
    
    result = portfolio.buy(symbol="BTCUSDT", units=0.5, price=20000.0, fee=10.0)
    
    assert result == True
    assert portfolio.cash < 20000.0


# ========== Test Integration with OrderSimulator ==========

def test_order_simulator_with_logger():
    """Test that order simulator logs when logger is provided."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        simulator = PaperOrderSimulator(fee_rate=0.001, slippage_rate=0.0005, logger=logger)
        
        fill_price, units, fee = simulator.simulate_buy(price=20000.0, units=0.5)
        
        # Check that simulation was logged
        log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Should have order simulated log
        assert len(lines) >= 1
        
        close_logger(logger)


def test_order_simulator_without_logger():
    """Test that order simulator works without logger."""
    simulator = PaperOrderSimulator(fee_rate=0.001, slippage_rate=0.0005, logger=None)
    
    fill_price, units, fee = simulator.simulate_buy(price=20000.0, units=0.5)
    
    assert fill_price > 20000.0  # Slippage increased price


# ========== Test Log Rotation ==========

def test_log_rotation():
    """Test that old log files are rotated."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(
            log_dir=tmpdir,
            rotation="daily",
            max_files=2,
        )
        
        try:
            # Create some fake old log files
            for i in range(5):
                old_file = Path(tmpdir) / f"paper_trading_2024-01-{i+1:02d}.log"
                old_file.write_text(f"Fake log {i}\n")
            
            # Trigger rotation check
            logger._rotate_logs()
            
            # Should only have max_files files
            log_files = list(Path(tmpdir).glob("paper_trading_*.log"))
            assert len(log_files) <= 2
        finally:
            close_logger(logger)


# ========== Edge Cases ==========

def test_logger_json_format():
    """Test that all log entries are valid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        try:
            # Log various entry types
            logger.log_signal_received("BTCUSDT", {"direction": "BUY"})
            logger.log_risk_evaluation("BTCUSDT", {}, {"passed": True})
            logger.log_engine_event("TEST")
            
            # Read log file and verify all lines are valid JSON
            log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
            with open(log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            json.loads(line)
                        except json.JSONDecodeError:
                            pytest.fail(f"Invalid JSON: {line}")
        finally:
            close_logger(logger)


def test_logger_timestamps():
    """Test that log entries have valid timestamps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = PaperTradingLogger(log_dir=tmpdir)
        
        try:
            logger.log_engine_event("TEST")
            
            # Read log file and verify timestamp
            log_file = list(Path(tmpdir).glob("paper_trading_*.log"))[0]
            with open(log_file, 'r') as f:
                line = f.readline()
            
            entry = json.loads(line)
            timestamp = entry.get("timestamp")
            
            assert timestamp is not None
            # Try to parse timestamp
            datetime.fromisoformat(timestamp)  # Should not raise
        finally:
            close_logger(logger)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
