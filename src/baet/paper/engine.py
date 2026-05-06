"""Main paper trading loop for BAET."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

from baet.config.models import Settings
from baet.risk.engine import RiskEngine

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """
    Main paper trading loop that runs continuously.
    
    Consumes live market data, evaluates strategies, and simulates trades
    without crashing or requiring manual intervention.
    """
    
    def __init__(
        self,
        config: Settings,
        risk_engine: Optional[RiskEngine] = None,
        paper_logger: Optional[object] = None,
    ):
        self.config = config
        self.risk_engine = risk_engine
        self.running = False
        self.last_update_time: Optional[datetime] = None
        self.consecutive_errors = 0
        self.max_consecutive_errors = 10
        
        # Lazy imports to avoid circular imports
        from baet.paper.portfolio import PaperPortfolio
        from baet.paper.order_simulator import PaperOrderSimulator
        
        # Set up decision logger first
        self.paper_logger = paper_logger
        if self.paper_logger is None and hasattr(config.paper, 'logging'):
            from baet.paper.logging import create_paper_logger_from_config
            self.paper_logger = create_paper_logger_from_config(config.paper.logging)
        
        self.portfolio = PaperPortfolio(
            initial_balance=config.paper.initial_balance,
            logger=self.paper_logger,
        )
        self.order_simulator = PaperOrderSimulator(
            fee_rate=config.backtest.fee_rate,
            slippage_rate=config.backtest.slippage_rate,
            logger=self.paper_logger,
        )
        
        if self.paper_logger:
            self.paper_logger.log_engine_event("ENGINE_INITIALIZED", {
                "initial_balance": config.paper.initial_balance,
                "has_risk_engine": risk_engine is not None,
            })
        
        logger.info("PaperTradingEngine initialized")
    
    def start(self) -> None:
        """Start the paper trading loop."""
        if self.running:
            logger.warning("Paper trading already running")
            return
        
        self.running = True
        self.consecutive_errors = 0
        
        logger.info("Paper trading loop started")
        
        if self.paper_logger:
            self.paper_logger.log_engine_event("ENGINE_STARTED", {
                "loop_interval": self.config.paper.loop_interval_seconds,
                "stop_on_error": self.config.paper.stop_on_error,
                "max_consecutive_errors": self.config.paper.max_consecutive_errors,
            })
        
        while self.running:
            try:
                self._iteration()
                self.consecutive_errors = 0  # Reset on success
                self.last_update_time = datetime.now()
                
                # Sleep until next iteration
                time.sleep(self.config.paper.loop_interval_seconds)
                
            except Exception as e:
                self.consecutive_errors += 1
                logger.error(
                    f"Paper trading error (attempt {self.consecutive_errors}): {e}",
                    exc_info=True
                )
                
                if self.paper_logger:
                    self.paper_logger.log_error(e, {
                        "consecutive_errors": self.consecutive_errors,
                        "iteration": self.last_update_time,
                    })
                
                # Check if we should stop on too many errors
                if self.consecutive_errors >= self.max_consecutive_errors:
                    logger.critical(
                        f"Too many consecutive errors ({self.consecutive_errors}), stopping"
                    )
                    self.stop()
                    break
                
                # Continue running unless configured to stop on error
                if self.config.paper.stop_on_error:
                    logger.error("Stopping due to stop_on_error=True")
                    self.stop()
                    raise
    
    def stop(self) -> None:
        """Stop the paper trading loop."""
        self.running = False
        logger.info("Paper trading loop stopped")
        
        if self.paper_logger:
            self.paper_logger.log_engine_event("ENGINE_STOPPED", {
                "total_trades": len(self.portfolio.trades),
                "final_value": self.portfolio.get_total_value(),
            })
    
    def _iteration(self) -> None:
        """Single iteration of the paper trading loop."""
        logger.debug("Starting paper trading iteration")
        
        # 1. Update market data (placeholder for now)
        market_data = self._update_market_data()
        
        # 2. Update features (placeholder for now)
        features = self._update_features(market_data)
        
        # 3. Generate strategy signals (placeholder for now)
        signals = self._generate_signals(features)
        
        # Log signals
        if self.paper_logger and signals:
            for symbol, signal in signals.items():
                self.paper_logger.log_signal_received(symbol, signal)
        
        # 4. Combine signals (if ensemble configured)
        combined = self._combine_signals(signals)
        
        # 5. Make decisions
        decisions = self._make_decisions(combined)
        
        # 6. Run risk checks (if risk engine available)
        approved = self._run_risk_checks(decisions)
        
        # 7. Execute paper trades
        self._execute_paper_trades(approved, market_data)
        
        # 8. Update portfolio state
        self._update_portfolio_state(market_data)
        
        # 9. Log iteration
        self._log_iteration()
        
        logger.debug("Paper trading iteration completed")
    
    def _update_market_data(self) -> dict:
        """Update market data from live source or simulation."""
        # TODO: Implement live data update from Binance
        # For now, return empty dict
        logger.debug("Updating market data (not implemented)")
        return {}
    
    def _update_features(self, market_data: dict) -> dict:
        """Update features based on market data."""
        # TODO: Implement feature updates
        logger.debug("Updating features (not implemented)")
        return {}
    
    def _generate_signals(self, features: dict) -> dict:
        """Generate signals from all configured strategies."""
        # TODO: Implement strategy signal generation
        logger.debug("Generating signals (not implemented)")
        return {}
    
    def _combine_signals(self, signals: dict) -> list:
        """Combine signals from multiple strategies."""
        # TODO: Implement ensemble combination
        logger.debug("Combining signals (not implemented)")
        return []
    
    def _make_decisions(self, combined: list) -> list:
        """Make trading decisions from combined signals."""
        # TODO: Implement decision making
        logger.debug("Making decisions (not implemented)")
        return []
    
    def _run_risk_checks(self, decisions: list) -> list:
        """Run risk checks on decisions."""
        if not self.risk_engine:
            return decisions  # No risk engine = no checks
        
        approved = []
        for decision in decisions:
            symbol = decision.get("symbol", "unknown")
            signal = decision.get("signal", {})
            
            # TODO: Implement actual risk checks
            # For now, just pass through
            result = {"passed": True, "violations": []}
            
            # Log risk evaluation
            if self.paper_logger:
                self.paper_logger.log_risk_evaluation(symbol, signal, result)
            
            if result.get("passed", True):
                approved.append(decision)
        
        return approved
    
    def _execute_paper_trades(self, approved: list, market_data: dict) -> None:
        """Execute approved paper trades."""
        for decision in approved:
            symbol = decision.get("symbol")
            action = decision.get("action", "HOLD")
            price = market_data.get(symbol, {}).get("price", 0)
            
            if action == "BUY" and price > 0:
                # Simulate buy order
                fill_price, units, fee = self.order_simulator.simulate_buy(
                    price=price,
                    units=decision.get("units", 0.1),
                )
                
                # Execute buy
                success = self.portfolio.buy(
                    symbol=symbol,
                    units=units,
                    price=fill_price,
                    fee=fee,
                )
                
                # Log order simulation
                if self.paper_logger:
                    self.paper_logger.log_order_simulated(
                        symbol=symbol,
                        side="BUY",
                        requested_price=price,
                        filled_price=fill_price,
                        units=units,
                        fee=fee,
                        slippage=fill_price - price,
                    )
                
                # Log portfolio update
                if self.paper_logger:
                    self.paper_logger.log_portfolio_update(
                        action="BUY",
                        symbol=symbol,
                        cash=self.portfolio.cash,
                        positions=self.portfolio.get_positions(),
                        total_value=self.portfolio.get_total_value(market_data),
                    )
            
            elif action == "SELL" and price > 0:
                # Simulate sell order
                position = self.portfolio.positions.get(symbol, {})
                units = position.get("units", 0)
                
                if units > 0:
                    fill_price, proceeds, fee = self.order_simulator.simulate_sell(
                        price=price,
                        units=units,
                    )
                    
                    # Execute sell
                    success = self.portfolio.sell(
                        symbol=symbol,
                        units=units,
                        price=fill_price,
                        fee=fee,
                    )
                    
                    # Log order simulation
                    if self.paper_logger:
                        self.paper_logger.log_order_simulated(
                            symbol=symbol,
                            side="SELL",
                            requested_price=price,
                            filled_price=fill_price,
                            units=units,
                            fee=fee,
                            slippage=price - fill_price,  # Sell slippage is negative
                        )
                    
                    # Log portfolio update
                    if self.paper_logger:
                        self.paper_logger.log_portfolio_update(
                            action="SELL",
                            symbol=symbol,
                            cash=self.portfolio.cash,
                            positions=self.portfolio.get_positions(),
                            total_value=self.portfolio.get_total_value(market_data),
                        )
    
    def _update_portfolio_state(self, market_data: dict) -> None:
        """Update portfolio state with current market prices."""
        # TODO: Implement portfolio state update
        logger.debug("Updating portfolio state (not implemented)")
        pass
    
    def _log_iteration(self) -> None:
        """Log iteration summary."""
        status = self.get_status()
        logger.info(
            f"Iteration: cash={status['cash']:.2f}, "
            f"positions={len(status['positions'])}, "
            f"value={status['portfolio_value']:.2f}"
        )
    
    def get_status(self) -> dict:
        """
        Get current paper trading status.
        
        Returns:
            Dict with current status information
        """
        return {
            "running": self.running,
            "portfolio_value": self.portfolio.get_total_value(),
            "cash": self.portfolio.cash,
            "positions": self.portfolio.get_positions(),
            "last_update": self.last_update_time,
            "consecutive_errors": self.consecutive_errors,
        }
    
    def get_summary(self) -> dict:
        """Get paper trading summary."""
        return self.portfolio.get_summary()
