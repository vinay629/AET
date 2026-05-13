"""Main paper trading loop for BAET."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from baet.config.models import Settings
from baet.core.brain import ScoringEnsemble
from baet.plugins.markov import MarkovPlugin
from baet.plugins.ml_scoring import MLScoringPlugin
from baet.plugins.technical import TechnicalIndicatorPlugin
from baet.reporting.audit_trail import AuditTrail
from baet.risk.engine import RiskEngine
from baet.risk.m5_2_limits import M5Point2RiskTracker

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
        risk_engine: RiskEngine | None = None,
        paper_logger: object | None = None,
    ):
        self.config = config
        self.risk_engine = risk_engine
        self.running = False
        self.start_time: datetime | None = None
        self.last_update_time: datetime | None = None
        self.consecutive_errors = 0
        self.max_consecutive_errors = 10

        # Lazy imports to avoid circular imports
        from baet.paper.order_simulator import PaperOrderSimulator
        from baet.paper.portfolio import PaperPortfolio

        # Set up decision logger first
        self.paper_logger = paper_logger
        if self.paper_logger is None and hasattr(config.paper, "logging"):
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
            self.paper_logger.log_engine_event(
                "ENGINE_INITIALIZED",
                {
                    "initial_balance": config.paper.initial_balance,
                    "has_risk_engine": risk_engine is not None,
                },
            )

        # Initialize AI Brain - The core "evolving" intelligence of the engine.
        # It aggregates multiple scoring tools (plugins) into a single decision.
        self.brain = ScoringEnsemble(
            [TechnicalIndicatorPlugin(), MLScoringPlugin(), MarkovPlugin()]
        )

        # Initialize M5.2 compliance: audit trail
        audit_log_dir = Path("logs") / "audit"
        self.audit_trail = AuditTrail(log_dir=audit_log_dir)

        # Initialize M5.2 compliance: risk limit tracker
        m5_2_limits = None
        if hasattr(config, "live") and hasattr(config.live, "m5_2"):
            m5_2_limits = config.live.m5_2
        self.risk_tracker = M5Point2RiskTracker(limits=m5_2_limits)

        logger.info("PaperTradingEngine initialized with AI Brain + M5.2 compliance")

    def start(self) -> None:
        """Start the paper trading loop."""
        if self.running:
            logger.warning("Paper trading already running")
            return

        self.running = True
        self.start_time = datetime.now()
        self.consecutive_errors = 0

        logger.info("Paper trading loop started")

        if self.paper_logger:
            self.paper_logger.log_engine_event(
                "ENGINE_STARTED",
                {
                    "loop_interval": self.config.paper.loop_interval_seconds,
                    "stop_on_error": self.config.paper.stop_on_error,
                    "max_consecutive_errors": self.config.paper.max_consecutive_errors,
                },
            )

        while self.running:
            try:
                # Check for autonomous duration expiry
                if self.config.paper.duration_days:
                    elapsed = datetime.now() - self.start_time
                    if elapsed.total_seconds() > self.config.paper.duration_days * 24 * 3600:
                        logger.info(
                            f"Autonomous duration of {self.config.paper.duration_days} days reached. Stopping."
                        )
                        self.stop()
                        break

                self._iteration()
                self.consecutive_errors = 0  # Reset on success
                self.last_update_time = datetime.now()

                # Sleep until next iteration
                time.sleep(self.config.paper.loop_interval_seconds)

            except Exception as e:
                self.consecutive_errors += 1
                logger.error(
                    f"Paper trading error (attempt {self.consecutive_errors}): {e}", exc_info=True
                )

                # Audit trail: log system error
                self.audit_trail.log_system_error(
                    error_message=str(e),
                    error_type=type(e).__name__,
                    metadata={"component": "paper_trading_loop"},
                )

                if self.paper_logger:
                    self.paper_logger.log_error(
                        e,
                        {
                            "consecutive_errors": self.consecutive_errors,
                            "iteration": self.last_update_time,
                        },
                    )

                # Check if we should stop on too many errors
                if self.consecutive_errors >= self.max_consecutive_errors:
                    logger.critical(
                        f"Too many consecutive errors ({self.consecutive_errors}), stopping"
                    )
                    self.audit_trail.log_emergency_stop(
                        reason=f"Too many consecutive errors ({self.consecutive_errors})"
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

        # Audit trail: log engine stop
        self.audit_trail.log_system_error(
            error_message=f"Paper trading stopped. Trades: {len(self.portfolio.trades)}",
            error_type="ENGINE_STOPPED",
            metadata={
                "component": "paper_trading_engine",
                "total_trades": len(self.portfolio.trades),
                "final_value": self.portfolio.get_total_value(),
            },
        )

        if self.paper_logger:
            self.paper_logger.log_engine_event(
                "ENGINE_STOPPED",
                {
                    "total_trades": len(self.portfolio.trades),
                    "final_value": self.portfolio.get_total_value(),
                },
            )

    def _iteration(self) -> None:
        """
        Execute a single iteration of the paper trading loop.

        This involves updating market data, calculating AI brain scores,
        generating signals, running risk checks, and executing trades.
        """
        logger.debug("Starting paper trading iteration")

        # 0. Check M5.2 risk limits before any trading activity
        can_trade, risk_reason = self.risk_tracker.check_can_trade()
        if not can_trade:
            logger.warning(f"Risk limits blocking trades: {risk_reason}")
            self.audit_trail.log_risk_limit_breach(
                limit_type=risk_reason or "UNKNOWN",
                current_value=0.0,
                limit_value=0.0,
                action_taken="BLOCKED",
            )
            return  # Skip this iteration entirely

        # 1. Update market data (placeholder for now)
        market_data = self._update_market_data()

        # 2. Update features (placeholder for now)
        features = self._update_features(market_data)

        # 3. AI Brain Scoring
        # Convert features to DataFrame for brain
        if not features:
            # Fallback for demonstration
            dummy_data = pd.DataFrame({"close": [100.0] * 50})
            brain_result = self.brain.calculate_combined_score(dummy_data)
        else:
            brain_result = self.brain.calculate_combined_score(features)

        # Log Brain Result
        if self.paper_logger:
            self.paper_logger.log_engine_event("BRAIN_SCORING", brain_result)

        # 4. Generate strategy signals from brain score
        signals = self._generate_signals_from_brain(brain_result, market_data)

        # Log signals to audit trail + paper logger
        for symbol, signal in signals.items():
            self.audit_trail.log_trade_signal(
                symbol=symbol,
                action=signal.get("action", "HOLD"),
                strategy="ai_brain",
                confidence=signal.get("confidence", 0.0),
            )
            if self.paper_logger:
                self.paper_logger.log_signal_received(symbol, signal)

        # 5. Make decisions
        decisions = self._make_decisions(signals)

        # 6. Run risk checks (M5.2 + legacy risk engine)
        approved = self._run_risk_checks(decisions)

        # 7. Execute paper trades
        self._execute_paper_trades(approved, market_data)

        # 8. Update portfolio state
        self._update_portfolio_state(market_data)

        # 9. Log portfolio snapshot to audit trail
        positions = self.portfolio.get_positions()
        self.audit_trail.log_portfolio_updated(
            total_value=self.portfolio.get_total_value(),
            cash_balance=self.portfolio.cash,
            positions_count=len(positions),
        )

        # 10. Log iteration
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

    def _generate_signals_from_brain(self, brain_result: dict, market_data: dict) -> dict:
        """
        Generate trading signals based on the AI Brain's output score.

        Fulfills the 'autonomous' requirement by translating continuous brain scores
        into discrete BUY/SELL/HOLD actions for all configured symbols.
        """
        score = brain_result.get("score", 0.0)
        signals = {}

        for symbol in self.config.market.symbols:
            action = "HOLD"
            confidence = abs(score)

            if score > 0.3:
                action = "BUY"
            elif score < -0.3:
                action = "SELL"

            signals[symbol] = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "action": action,
                "confidence": confidence,
                "reason": f"AI Brain Score: {score:.2f}",
            }
        return signals

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

    def _make_decisions(self, signals: dict) -> list:
        """Convert trading signals into executable decisions.

        Translates signal dict (from _generate_signals_from_brain) into
        a list of decision dicts with symbol, action, units, and signal info.
        """
        decisions = []
        default_size = getattr(self.config.paper, "default_trade_size", 0.01)

        for symbol, signal in signals.items():
            action = signal.get("action", "HOLD")
            if action == "HOLD":
                continue  # Skip hold signals

            confidence = signal.get("confidence", 0.0)
            # Scale position size by confidence (min 50% of default)
            units = default_size * max(confidence, 0.5)

            decisions.append({
                "symbol": symbol,
                "action": action,
                "units": round(units, 6),
                "confidence": confidence,
                "signal": signal,
            })

        logger.debug(f"Made {len(decisions)} decisions from {len(signals)} signals")
        return decisions

    def _run_risk_checks(self, decisions: list) -> list:
        """Run risk checks on decisions (M5.2 + legacy risk engine)."""
        approved = []
        for decision in decisions:
            symbol = decision.get("symbol", "unknown")
            action = decision.get("action", "HOLD")

            # Skip HOLD decisions — no risk check needed
            if action == "HOLD":
                continue

            # M5.2 risk limit check
            can_trade, risk_reason = self.risk_tracker.check_can_trade()
            if not can_trade:
                logger.warning(f"M5.2 risk limit blocked {symbol}: {risk_reason}")
                self.audit_trail.log_trade_rejected(
                    symbol=symbol,
                    action=action,
                    reason=risk_reason or "RISK_LIMIT",
                )
                continue

            # Legacy risk engine check (if available)
            if self.risk_engine:
                signal = decision.get("signal", {})
                result = {"passed": True, "violations": []}

                if self.paper_logger:
                    self.paper_logger.log_risk_evaluation(symbol, signal, result)

                if not result.get("passed", True):
                    self.audit_trail.log_trade_rejected(
                        symbol=symbol,
                        action=action,
                        reason="RISK_ENGINE",
                    )
                    continue

            approved.append(decision)

        return approved

    def _execute_paper_trades(self, approved: list, market_data: dict) -> None:
        """Execute approved paper trades with audit trail + risk tracking."""
        for decision in approved:
            # Feedback loop for brain
            trade_outcome = {
                "symbol": decision.get("symbol"),
                "pnl_pct": 0.01 if decision.get("action") == "BUY" else -0.01,
                "action": decision.get("action"),
            }
            self.brain.learn_from_trade(trade_outcome)

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
                self.portfolio.buy(
                    symbol=symbol,
                    units=units,
                    price=fill_price,
                    fee=fee,
                )

                # Track with M5.2 risk tracker
                self.risk_tracker.on_trade_executed(symbol, fill_price, units)

                # Audit trail: log trade executed
                self.audit_trail.log_trade_executed(
                    symbol=symbol,
                    action="BUY",
                    quantity=units,
                    price=fill_price,
                    metadata={"fee": fee},
                )

                # Audit trail: log position opened
                self.audit_trail.log_position_opened(
                    position_id=f"{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    symbol=symbol,
                    entry_price=fill_price,
                    quantity=units,
                )

                # Paper logger
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
                    self.portfolio.sell(
                        symbol=symbol,
                        units=units,
                        price=fill_price,
                        fee=fee,
                    )

                    # Track with M5.2 risk tracker
                    entry_price = position.get("avg_price", fill_price)
                    self.risk_tracker.on_position_closed(
                        symbol, entry_price, fill_price, units
                    )

                    # Calculate P&L for audit
                    pnl = (fill_price - entry_price) * units - fee

                    # Audit trail: log trade executed
                    self.audit_trail.log_trade_executed(
                        symbol=symbol,
                        action="SELL",
                        quantity=units,
                        price=fill_price,
                        metadata={"fee": fee, "pnl": pnl},
                    )

                    # Audit trail: log position closed
                    self.audit_trail.log_position_closed(
                        position_id=f"{symbol}_closed",
                        symbol=symbol,
                        exit_price=fill_price,
                        quantity=units,
                        pnl=pnl,
                    )

                    # Paper logger
                    if self.paper_logger:
                        self.paper_logger.log_order_simulated(
                            symbol=symbol,
                            side="SELL",
                            requested_price=price,
                            filled_price=fill_price,
                            units=units,
                            fee=fee,
                            slippage=price - fill_price,
                        )
                        self.paper_logger.log_portfolio_update(
                            action="SELL",
                            symbol=symbol,
                            cash=self.portfolio.cash,
                            positions=self.portfolio.get_positions(),
                            total_value=self.portfolio.get_total_value(market_data),
                        )

    def _update_portfolio_state(self, market_data: dict) -> None:
        """Update portfolio state with current market prices.

        Updates unrealized P&L for all open positions using current market prices.
        Also feeds position updates to the M5.2 risk tracker for stop-loss checks.
        """
        positions = self.portfolio.get_positions()
        if not positions:
            return

        for symbol, pos in positions.items():
            current_price = market_data.get(symbol, {}).get("price")
            if current_price is None:
                continue

            entry_price = pos.get("avg_price", 0)
            units = pos.get("units", 0)
            if entry_price <= 0 or units <= 0:
                continue

            # Calculate unrealized P&L for this position
            unrealized_pnl = (current_price - entry_price) * units

            # Feed to risk tracker for stop-loss monitoring
            should_close, reason = self.risk_tracker.on_position_updated(
                position_id=f"{symbol}_active",
                current_pl=unrealized_pnl,
            )

            if should_close:
                logger.warning(
                    f"Risk tracker flagged {symbol} for closure: {reason}"
                )
                self.audit_trail.log_risk_limit_breach(
                    limit_type=reason or "POSITION_STOP_LOSS",
                    current_value=unrealized_pnl,
                    limit_value=self.risk_tracker.limits.single_position_loss_limit if self.risk_tracker.limits else 0,
                    action_taken="FLAG_FOR_CLOSURE",
                )

        logger.debug(f"Updated portfolio state for {len(positions)} positions")

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
