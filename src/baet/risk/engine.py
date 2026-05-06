"""Centralized risk engine for BAET trading platform."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from baet.core.models import RegimeLabel
from baet.risk.checks import RiskCheckResult, RiskViolation
from baet.risk.policy import RiskPolicy


class RiskEngine:
    """
    Centralized risk engine that ALL trade signals must pass through.
    
    This engine:
    - Runs pre-trade risk checks
    - Can override strategy decisions (reject or modify)
    - Provides detailed reasons for decisions
    - Tracks portfolio state for risk calculations
    """
    
    def __init__(self, policy: RiskPolicy):
        self.policy = policy
        self.portfolio_state: dict[str, object] = {
            'total_equity': 10000.0,
            'available_cash': 10000.0,
            'total_exposure': 0.0,
            'positions': {},  # symbol -> position info
            'daily_pnl': 0.0,
            'daily_start_equity': 10000.0,
            'peak_equity': 10000.0,
            'consecutive_losses': 0,
            'last_trade_time': None,
        }
        self.kill_switch_active = False
        self.kill_switch_time: Optional[datetime] = None
    
    def evaluate_signal(
        self,
        signal: dict[str, object],
        regime: Optional[RegimeLabel] = None,
    ) -> RiskCheckResult:
        """
        Evaluate a trade signal against all risk rules.
        
        Args:
            signal: Dict with keys: action, target_position, confidence, 
                   strategy_name, symbol, size_hint, timestamp
            regime: Current market regime (optional)
            
        Returns:
            RiskCheckResult with approved/rejected status and reasons
        """
        # Check kill-switch first (emergency override)
        if self.kill_switch_active:
            return RiskCheckResult.reject(
                action=signal.get('action', 'HOLD'),
                reasons=["Kill-switch is active - all trades blocked"],
                violations=[RiskViolation(
                    rule="kill_switch",
                    severity="kill_switch",
                    message="Kill-switch triggered - trading halted",
                )]
            )
        
        # Run all risk checks
        all_violations = []
        adjusted_size = signal.get('size_hint', 0.1)
        adjusted_action = signal.get('action', 'HOLD')
        
        # 1. Check emergency conditions
        emergency_result = self._check_emergency_conditions()
        if not emergency_result.approved:
            return emergency_result
        
        # 2. Check strategy risk
        strategy_result = self._check_strategy_risk(signal)
        if not strategy_result.approved:
            return strategy_result
        
        # 3. Check position sizing
        sizing_result = self._check_position_sizing(signal, adjusted_size)
        if not sizing_result.approved:
            return sizing_result
        if sizing_result.adjusted_size is not None:
            adjusted_size = sizing_result.adjusted_size
        
        # 4. Check drawdown protection
        drawdown_result = self._check_drawdown(signal)
        if not drawdown_result.approved:
            return drawdown_result
        
        # 5. Check regime-based risk
        if regime:
            regime_result = self._check_regime_risk(signal, regime)
            if not regime_result.approved:
                return regime_result
            if regime_result.adjusted_size is not None:
                adjusted_size = regime_result.adjusted_size
        
        # 6. Check portfolio risk
        portfolio_result = self._check_portfolio_risk(signal)
        if not portfolio_result.approved:
            return portfolio_result
        
        # All checks passed - build approval result
        reasons = ["All risk checks passed"]
        if adjusted_size != signal.get('size_hint', 0.1):
            reasons.append(f"Position size adjusted to {adjusted_size:.4f}")
        
        return RiskCheckResult.approve(
            action=signal.get('action', 'HOLD'),
            size=adjusted_size,
            reasons=reasons
        )
    
    def _check_position_sizing(
        self, signal: dict, current_size: float
    ) -> RiskCheckResult:
        """Check position sizing rules."""
        violations = []
        adjusted_size = current_size
        
        # Check max position size
        if adjusted_size > self.policy.position_sizing.max_position_size:
            adjusted_size = self.policy.position_sizing.max_position_size
            violations.append(RiskViolation(
                rule="max_position_size",
                severity="warning",
                message=f"Position size reduced to max: {adjusted_size}",
                current_value=current_size,
                threshold_value=self.policy.position_sizing.max_position_size,
            ))
        
        # Check min position size
        if adjusted_size < self.policy.position_sizing.min_position_size:
            return RiskCheckResult.reject(
                action=signal.get('action', 'HOLD'),
                reasons=[f"Position size {current_size} below minimum {self.policy.position_sizing.min_position_size}"],
                violations=[RiskViolation(
                    rule="min_position_size",
                    severity="critical",
                    message="Position size too small (dust)",
                    current_value=current_size,
                    threshold_value=self.policy.position_sizing.min_position_size,
                )]
            )
        
        # Check max risk per trade
        risk_amount = adjusted_size * self.portfolio_state['total_equity']
        max_risk_amount = self.policy.position_sizing.max_risk_per_trade * self.portfolio_state['total_equity']
        
        if risk_amount > max_risk_amount:
            adjusted_size = max_risk_amount / self.portfolio_state['total_equity']
            violations.append(RiskViolation(
                rule="max_risk_per_trade",
                severity="warning",
                message=f"Position size reduced due to risk limit",
                current_value=risk_amount,
                threshold_value=max_risk_amount,
            ))
        
        if violations:
            reasons = [v.message for v in violations]
            return RiskCheckResult.modify(
                action=signal.get('action', 'HOLD'),
                original_size=current_size,
                modified_size=adjusted_size,
                reasons=reasons,
            )
        
        return RiskCheckResult.approve(
            action=signal.get('action', 'HOLD'),
            size=adjusted_size,
            reasons=["Position sizing OK"]
        )
    
    def _check_drawdown(self, signal: dict) -> RiskCheckResult:
        """Check drawdown protection rules."""
        current_equity = self.portfolio_state['total_equity']
        peak_equity = self.portfolio_state['peak_equity']
        
        if peak_equity <= 0:
            return RiskCheckResult.approve(
                action=signal.get('action', 'HOLD'),
                reasons=["No drawdown data yet"]
            )
        
        current_drawdown = (current_equity - peak_equity) / peak_equity
        
        # Check kill-switch drawdown
        if current_drawdown < -self.policy.drawdown.kill_switch_drawdown:
            self.kill_switch_active = True
            self.kill_switch_time = datetime.now()
            return RiskCheckResult.reject(
                action=signal.get('action', 'HOLD'),
                reasons=[f"Kill-switch triggered: drawdown {current_drawdown:.2%} exceeds {self.policy.drawdown.kill_switch_drawdown:.2%}"],
                violations=[RiskViolation(
                    rule="kill_switch_drawdown",
                    severity="kill_switch",
                    message="Kill-switch drawdown exceeded",
                    current_value=current_drawdown,
                    threshold_value=-self.policy.drawdown.kill_switch_drawdown,
                )]
            )
        
        # Check max portfolio drawdown
        if current_drawdown < -self.policy.drawdown.max_portfolio_drawdown:
            return RiskCheckResult.reject(
                action=signal.get('action', 'HOLD'),
                reasons=[f"Max drawdown exceeded: {current_drawdown:.2%}"],
                violations=[RiskViolation(
                    rule="max_portfolio_drawdown",
                    severity="critical",
                    message="Portfolio drawdown limit exceeded",
                    current_value=current_drawdown,
                    threshold_value=-self.policy.drawdown.max_portfolio_drawdown,
                )]
            )
        
        # Check daily loss limit
        daily_loss = self.portfolio_state['daily_pnl']
        if daily_loss < -self.policy.drawdown.max_daily_loss * self.portfolio_state['total_equity']:
            return RiskCheckResult.reject(
                action=signal.get('action', 'HOLD'),
                reasons=[f"Daily loss limit exceeded: {daily_loss:.2f}"],
                violations=[RiskViolation(
                    rule="max_daily_loss",
                    severity="critical",
                    message="Daily loss limit exceeded",
                    current_value=daily_loss,
                    threshold_value=-self.policy.drawdown.max_daily_loss * self.portfolio_state['total_equity'],
                )]
            )
        
        return RiskCheckResult.approve(
            action=signal.get('action', 'HOLD'),
            reasons=["Drawdown within limits"]
        )
    
    def _check_regime_risk(self, signal: dict, regime: RegimeLabel) -> RiskCheckResult:
        """Check regime-based risk adjustments."""
        regime_str = regime.value if isinstance(regime, RegimeLabel) else str(regime)
        max_exposure = self.policy.get_max_exposure_for_regime(regime_str)
        
        current_exposure = self.portfolio_state['total_exposure'] / self.portfolio_state['total_equity']
        
        if current_exposure >= max_exposure:
            return RiskCheckResult.reject(
                action=signal.get('action', 'HOLD'),
                reasons=[f"Exposure {current_exposure:.2%} exceeds regime limit {max_exposure:.2%} for {regime_str}"],
                violations=[RiskViolation(
                    rule="regime_max_exposure",
                    severity="warning",
                    message=f"Regime-based exposure limit reached",
                    current_value=current_exposure,
                    threshold_value=max_exposure,
                    symbol=signal.get('symbol'),
                )]
            )
        
        return RiskCheckResult.approve(
            action=signal.get('action', 'HOLD'),
            reasons=[f"Regime {regime_str}: exposure OK"]
        )
    
    def _check_strategy_risk(self, signal: dict) -> RiskCheckResult:
        """Check per-strategy risk rules."""
        strategy_name = signal.get('strategy_name', '')
        
        # Check if strategy is blacklisted
        if not self.policy.is_strategy_enabled(strategy_name):
            return RiskCheckResult.reject(
                action=signal.get('action', 'HOLD'),
                reasons=[f"Strategy {strategy_name} is not enabled or is blacklisted"],
                violations=[RiskViolation(
                    rule="strategy_blacklist",
                    severity="critical",
                    message=f"Strategy {strategy_name} not allowed",
                    strategy_name=strategy_name,
                )]
            )
        
        # Check strategy-specific allocation limit
        if strategy_name in self.policy.strategy.max_strategy_allocation:
            max_alloc = self.policy.strategy.max_strategy_allocation[strategy_name]
            # This would need historical allocation tracking
            # For now, just pass
            pass
        
        return RiskCheckResult.approve(
            action=signal.get('action', 'HOLD'),
            reasons=[f"Strategy {strategy_name} approved"]
        )
    
    def _check_portfolio_risk(self, signal: dict) -> RiskCheckResult:
        """Check portfolio-level risk rules."""
        symbol = signal.get('symbol', '')
        
        # Check max total exposure
        if self.portfolio_state['total_exposure'] >= self.policy.portfolio.max_total_exposure * self.portfolio_state['total_equity']:
            return RiskCheckResult.reject(
                action=signal.get('action', 'HOLD'),
                reasons=["Total portfolio exposure limit reached"],
                violations=[RiskViolation(
                    rule="max_total_exposure",
                    severity="warning",
                    message="Portfolio exposure limit reached",
                )]
            )
        
        # Check max concentration (single symbol)
        if symbol and symbol in self.portfolio_state['positions']:
            symbol_exposure = self.portfolio_state['positions'][symbol].get('exposure', 0)
            if symbol_exposure >= self.policy.portfolio.max_concentration * self.portfolio_state['total_equity']:
                return RiskCheckResult.reject(
                    action=signal.get('action', 'HOLD'),
                    reasons=[f"Concentration limit reached for {symbol}"],
                    violations=[RiskViolation(
                        rule="max_concentration",
                        severity="warning",
                        message=f"Too much exposure to {symbol}",
                        current_value=symbol_exposure,
                        threshold_value=self.policy.portfolio.max_concentration * self.portfolio_state['total_equity'],
                        symbol=symbol,
                    )]
                )
        
        # Check max active positions
        if len(self.portfolio_state['positions']) >= self.policy.portfolio.max_active_positions:
            if signal.get('action') == 'BUY' and symbol not in self.portfolio_state['positions']:
                return RiskCheckResult.reject(
                    action=signal.get('action', 'HOLD'),
                    reasons=[f"Max active positions ({self.policy.portfolio.max_active_positions}) reached"],
                    violations=[RiskViolation(
                        rule="max_active_positions",
                        severity="warning",
                        message="Too many active positions",
                    )]
                )
        
        return RiskCheckResult.approve(
            action=signal.get('action', 'HOLD'),
            reasons=["Portfolio risk OK"]
        )
    
    def _check_emergency_conditions(self) -> RiskCheckResult:
        """Check emergency kill-switch conditions."""
        if not self.policy.emergency.kill_switch_enabled:
            return RiskCheckResult.approve(
                action='HOLD',
                reasons=["Kill-switch disabled"]
            )
        
        # Check if in cooldown period
        if self.kill_switch_active and self.kill_switch_time:
            cooldown_end = self.kill_switch_time + timedelta(hours=self.policy.emergency.cooldown_period_hours)
            if datetime.now() < cooldown_end and self.policy.emergency.require_manual_reset:
                return RiskCheckResult.reject(
                    action='HOLD',
                    reasons=[f"Kill-switch cooldown active until {cooldown_end}"],
                    violations=[RiskViolation(
                        rule="kill_switch_cooldown",
                        severity="kill_switch",
                        message="In cooldown period",
                    )]
                )
        
        return RiskCheckResult.approve(
            action='HOLD',
            reasons=["No emergency conditions"]
        )
    
    def update_portfolio_state(self, equity: float, positions: dict, daily_pnl: float) -> None:
        """Update portfolio state for risk calculations."""
        self.portfolio_state['total_equity'] = equity
        self.portfolio_state['available_cash'] = equity - self.portfolio_state['total_exposure']
        self.portfolio_state['daily_pnl'] = daily_pnl
        
        if equity > self.portfolio_state['peak_equity']:
            self.portfolio_state['peak_equity'] = equity
        
        # Recalculate total exposure from positions
        total_exposure = sum(pos.get('exposure', 0) for pos in positions.values())
        self.portfolio_state['total_exposure'] = total_exposure
        self.portfolio_state['positions'] = positions
    
    def reset_kill_switch(self) -> bool:
        """Manually reset the kill-switch (if allowed by policy)."""
        if self.policy.emergency.require_manual_reset:
            self.kill_switch_active = False
            self.kill_switch_time = None
            return True
        return False
