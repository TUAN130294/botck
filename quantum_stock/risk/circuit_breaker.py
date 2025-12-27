# -*- coding: utf-8 -*-
"""
Circuit Breaker System - Level 4 Agentic AI
============================================
Automated risk management with multi-level circuit breakers.

Levels:
- Level 0 (Normal): Full trading capacity
- Level 1 (Caution): Daily loss > 3% → Reduce position 50%
- Level 2 (Halt): Daily loss > 5% → Stop all trading
- Level 3 (Emergency): Drawdown > 10% → Liquidate + Alert

Features:
- Real-time P/L monitoring
- Auto position reduction
- Agent rollback on poor performance
- Human escalation for emergencies
"""

import time
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Callable
from pathlib import Path
import threading


class CircuitBreakerLevel(IntEnum):
    NORMAL = 0
    CAUTION = 1
    HALT = 2
    EMERGENCY = 3


@dataclass
class Position:
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    pnl: float = 0.0
    pnl_percent: float = 0.0
    
    def update_pnl(self, current_price: float):
        self.current_price = current_price
        self.pnl = (current_price - self.entry_price) * self.quantity
        self.pnl_percent = (current_price / self.entry_price - 1) * 100


@dataclass
class CircuitBreakerState:
    level: CircuitBreakerLevel = CircuitBreakerLevel.NORMAL
    daily_pnl: float = 0.0
    daily_pnl_percent: float = 0.0
    max_drawdown: float = 0.0
    peak_portfolio_value: float = 0.0
    current_portfolio_value: float = 0.0
    position_multiplier: float = 1.0
    last_trigger_time: Optional[datetime] = None
    trigger_count_today: int = 0
    is_trading_allowed: bool = True
    message: str = "System operating normally"


class CircuitBreakerSystem:
    """
    Multi-Level Circuit Breaker for Trading Risk Management
    
    Thresholds:
    - CAUTION: Daily loss > 3% OR single position loss > 5%
    - HALT: Daily loss > 5% OR consecutive 3 losing trades
    - EMERGENCY: Drawdown > 10% OR system error
    
    Recovery:
    - Auto-recovery after cooling period (30 min for L1, 2h for L2)
    - Manual override required for L3
    """
    
    # Thresholds
    CAUTION_DAILY_LOSS = -0.03  # -3%
    HALT_DAILY_LOSS = -0.05    # -5%
    EMERGENCY_DRAWDOWN = -0.10  # -10%
    SINGLE_POSITION_LOSS = -0.05  # -5%
    
    # Position Size Multipliers
    CAUTION_POSITION_MULT = 0.5
    HALT_POSITION_MULT = 0.0
    
    # Recovery Periods (seconds)
    CAUTION_COOLDOWN = 30 * 60      # 30 minutes
    HALT_COOLDOWN = 2 * 60 * 60     # 2 hours
    
    def __init__(
        self,
        initial_portfolio_value: float = 1_000_000_000,  # 1 billion VND
        state_file: Optional[str] = None
    ):
        self.initial_portfolio_value = initial_portfolio_value
        self.state = CircuitBreakerState(
            peak_portfolio_value=initial_portfolio_value,
            current_portfolio_value=initial_portfolio_value
        )
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Dict] = []
        self.alert_callbacks: List[Callable] = []
        self.state_file = state_file or "circuit_breaker_state.json"
        
        # Load previous state if exists
        self._load_state()
        
        # Start monitoring thread
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
    
    def register_alert_callback(self, callback: Callable):
        """Register callback for alerts (e.g., Telegram, Email)"""
        self.alert_callbacks.append(callback)
    
    def _send_alert(self, message: str, level: str = "INFO"):
        """Send alert to all registered callbacks"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "circuit_breaker_level": self.state.level.name
        }
        
        print(f"[CIRCUIT BREAKER {level}] {message}")
        
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"Alert callback error: {e}")
    
    def update_portfolio_value(self, new_value: float):
        """Update current portfolio value and check thresholds"""
        self.state.current_portfolio_value = new_value
        
        # Update peak (for drawdown calculation)
        if new_value > self.state.peak_portfolio_value:
            self.state.peak_portfolio_value = new_value
        
        # Calculate daily P/L
        self.state.daily_pnl = new_value - self.initial_portfolio_value
        self.state.daily_pnl_percent = self.state.daily_pnl / self.initial_portfolio_value
        
        # Calculate drawdown from peak
        if self.state.peak_portfolio_value > 0:
            drawdown = (new_value - self.state.peak_portfolio_value) / self.state.peak_portfolio_value
            self.state.max_drawdown = min(self.state.max_drawdown, drawdown)
        
        # Check thresholds
        self._check_thresholds()
    
    def update_position(self, symbol: str, quantity: int, entry_price: float, current_price: float):
        """Update or create position"""
        if symbol in self.positions:
            self.positions[symbol].quantity = quantity
            self.positions[symbol].update_pnl(current_price)
        else:
            pos = Position(symbol, quantity, entry_price, current_price)
            pos.update_pnl(current_price)
            self.positions[symbol] = pos
        
        # Check single position loss
        if self.positions[symbol].pnl_percent < self.SINGLE_POSITION_LOSS * 100:
            self._trigger_level(
                CircuitBreakerLevel.CAUTION,
                f"Single position {symbol} loss exceeds {self.SINGLE_POSITION_LOSS*100}%"
            )
    
    def record_trade(self, symbol: str, side: str, quantity: int, price: float, pnl: float):
        """Record completed trade"""
        self.trade_history.append({
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "pnl": pnl
        })
        
        # Check for consecutive losses
        recent_trades = self.trade_history[-3:]
        if len(recent_trades) >= 3:
            if all(t["pnl"] < 0 for t in recent_trades):
                self._trigger_level(
                    CircuitBreakerLevel.HALT,
                    "3 consecutive losing trades detected"
                )
    
    def _check_thresholds(self):
        """Check all thresholds and trigger appropriate level"""
        # Emergency: Drawdown > 10%
        if self.state.max_drawdown < self.EMERGENCY_DRAWDOWN:
            self._trigger_level(
                CircuitBreakerLevel.EMERGENCY,
                f"Max drawdown {self.state.max_drawdown*100:.2f}% exceeds {self.EMERGENCY_DRAWDOWN*100}%"
            )
            return
        
        # Halt: Daily loss > 5%
        if self.state.daily_pnl_percent < self.HALT_DAILY_LOSS:
            self._trigger_level(
                CircuitBreakerLevel.HALT,
                f"Daily loss {self.state.daily_pnl_percent*100:.2f}% exceeds {self.HALT_DAILY_LOSS*100}%"
            )
            return
        
        # Caution: Daily loss > 3%
        if self.state.daily_pnl_percent < self.CAUTION_DAILY_LOSS:
            self._trigger_level(
                CircuitBreakerLevel.CAUTION,
                f"Daily loss {self.state.daily_pnl_percent*100:.2f}% exceeds {self.CAUTION_DAILY_LOSS*100}%"
            )
            return
        
        # Recovery check
        self._check_recovery()
    
    def _trigger_level(self, level: CircuitBreakerLevel, reason: str):
        """Trigger circuit breaker level"""
        if level <= self.state.level:
            return  # Already at this level or higher
        
        self.state.level = level
        self.state.last_trigger_time = datetime.now()
        self.state.trigger_count_today += 1
        
        if level == CircuitBreakerLevel.CAUTION:
            self.state.position_multiplier = self.CAUTION_POSITION_MULT
            self.state.is_trading_allowed = True
            self.state.message = f"⚠️ CAUTION: {reason}. Position size reduced to 50%."
            self._send_alert(self.state.message, "WARNING")
            
        elif level == CircuitBreakerLevel.HALT:
            self.state.position_multiplier = self.HALT_POSITION_MULT
            self.state.is_trading_allowed = False
            self.state.message = f"🛑 HALT: {reason}. All trading stopped."
            self._send_alert(self.state.message, "CRITICAL")
            
        elif level == CircuitBreakerLevel.EMERGENCY:
            self.state.position_multiplier = 0.0
            self.state.is_trading_allowed = False
            self.state.message = f"🚨 EMERGENCY: {reason}. Liquidating positions. Human intervention required!"
            self._send_alert(self.state.message, "EMERGENCY")
            self._emergency_liquidation()
        
        self._save_state()
    
    def _check_recovery(self):
        """Check if we can recover from triggered state"""
        if self.state.level == CircuitBreakerLevel.NORMAL:
            return
        
        if self.state.last_trigger_time is None:
            return
        
        elapsed = (datetime.now() - self.state.last_trigger_time).total_seconds()
        
        # Level 1 recovery
        if self.state.level == CircuitBreakerLevel.CAUTION:
            if elapsed > self.CAUTION_COOLDOWN and self.state.daily_pnl_percent > self.CAUTION_DAILY_LOSS / 2:
                self._recover_to_normal("Cooldown period passed, P/L improved")
        
        # Level 2 recovery
        elif self.state.level == CircuitBreakerLevel.HALT:
            if elapsed > self.HALT_COOLDOWN and self.state.daily_pnl_percent > self.HALT_DAILY_LOSS / 2:
                # Don't go directly to normal, go to caution first
                self.state.level = CircuitBreakerLevel.CAUTION
                self.state.position_multiplier = self.CAUTION_POSITION_MULT
                self.state.is_trading_allowed = True
                self.state.message = "Recovering from HALT to CAUTION mode"
                self._send_alert(self.state.message, "INFO")
    
    def _recover_to_normal(self, reason: str):
        """Recover to normal operations"""
        self.state.level = CircuitBreakerLevel.NORMAL
        self.state.position_multiplier = 1.0
        self.state.is_trading_allowed = True
        self.state.message = f"✅ NORMAL: {reason}"
        self._send_alert(self.state.message, "INFO")
        self._save_state()
    
    def _emergency_liquidation(self):
        """Emergency liquidation of all positions"""
        self._send_alert("INITIATING EMERGENCY LIQUIDATION", "EMERGENCY")
        
        for symbol, pos in self.positions.items():
            self._send_alert(f"Liquidating {symbol}: {pos.quantity} shares at {pos.current_price}", "EMERGENCY")
            # In production: Execute market sell order
        
        # Mark positions as liquidated
        self.positions = {}
    
    def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                self._check_thresholds()
                time.sleep(60)  # Check every minute
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(60)
    
    def _save_state(self):
        """Save state to file"""
        try:
            state_dict = {
                "level": self.state.level.value,
                "daily_pnl": self.state.daily_pnl,
                "daily_pnl_percent": self.state.daily_pnl_percent,
                "max_drawdown": self.state.max_drawdown,
                "peak_portfolio_value": self.state.peak_portfolio_value,
                "current_portfolio_value": self.state.current_portfolio_value,
                "position_multiplier": self.state.position_multiplier,
                "is_trading_allowed": self.state.is_trading_allowed,
                "last_trigger_time": self.state.last_trigger_time.isoformat() if self.state.last_trigger_time else None,
                "trigger_count_today": self.state.trigger_count_today,
                "message": self.state.message
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_dict, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")
    
    def _load_state(self):
        """Load state from file"""
        try:
            if Path(self.state_file).exists():
                with open(self.state_file, 'r') as f:
                    state_dict = json.load(f)
                
                self.state.level = CircuitBreakerLevel(state_dict.get("level", 0))
                self.state.daily_pnl = state_dict.get("daily_pnl", 0.0)
                self.state.max_drawdown = state_dict.get("max_drawdown", 0.0)
                self.state.peak_portfolio_value = state_dict.get("peak_portfolio_value", self.initial_portfolio_value)
                self.state.position_multiplier = state_dict.get("position_multiplier", 1.0)
                self.state.is_trading_allowed = state_dict.get("is_trading_allowed", True)
                self.state.message = state_dict.get("message", "Loaded from state file")
                
        except Exception as e:
            print(f"Error loading state: {e}")
    
    def can_trade(self) -> bool:
        """Check if trading is allowed"""
        return self.state.is_trading_allowed
    
    def get_position_multiplier(self) -> float:
        """Get current position size multiplier"""
        return self.state.position_multiplier
    
    def get_status(self) -> Dict:
        """Get current circuit breaker status"""
        return {
            "level": self.state.level.name,
            "level_value": self.state.level.value,
            "daily_pnl": round(self.state.daily_pnl, 2),
            "daily_pnl_percent": round(self.state.daily_pnl_percent * 100, 2),
            "max_drawdown": round(self.state.max_drawdown * 100, 2),
            "position_multiplier": self.state.position_multiplier,
            "is_trading_allowed": self.state.is_trading_allowed,
            "message": self.state.message
        }
    
    def manual_reset(self, admin_key: str = "ADMIN_OVERRIDE"):
        """Manual reset (requires admin key)"""
        if admin_key != "ADMIN_OVERRIDE":
            return False
        
        self.state = CircuitBreakerState(
            peak_portfolio_value=self.state.current_portfolio_value,
            current_portfolio_value=self.state.current_portfolio_value
        )
        self._send_alert("Manual reset by administrator", "INFO")
        self._save_state()
        return True
    
    def stop(self):
        """Stop monitoring thread"""
        self._monitoring = False


# Singleton
_circuit_breaker = None

def get_circuit_breaker(initial_value: float = 1_000_000_000) -> CircuitBreakerSystem:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreakerSystem(initial_value)
    return _circuit_breaker


# Test
if __name__ == "__main__":
    cb = CircuitBreakerSystem(initial_portfolio_value=1_000_000_000)
    
    print("=== CIRCUIT BREAKER TEST ===")
    print(f"Initial Status: {cb.get_status()}")
    
    # Simulate 3% loss
    cb.update_portfolio_value(970_000_000)
    print(f"\nAfter 3% loss: {cb.get_status()}")
    
    # Simulate 5% loss
    cb.update_portfolio_value(950_000_000)
    print(f"\nAfter 5% loss: {cb.get_status()}")
    
    cb.stop()
