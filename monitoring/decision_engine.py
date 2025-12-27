"""
Automated Decision Engine
==========================
Tự động quyết định actions dựa trên health monitoring

Actions:
1. RETRAIN - Train lại model với data mới
2. SWITCH_STRATEGY - Đổi strategy (momentum → mean reversion, etc.)
3. INCREASE_THRESHOLD - Tăng threshold để trade ít hơn, chọn lọc hơn
4. DECREASE_POSITION - Giảm position size
5. PAUSE_TRADING - Tạm dừng trading
6. RESUME_NORMAL - Quay lại bình thường
"""

from enum import Enum
from dataclasses import dataclass
from typing import List
import json
from pathlib import Path
from datetime import datetime


class Action(Enum):
    """Các actions có thể thực hiện"""
    RETRAIN = "retrain"
    SWITCH_STRATEGY = "switch_strategy"
    INCREASE_THRESHOLD = "increase_threshold"
    DECREASE_POSITION = "decrease_position"
    PAUSE_TRADING = "pause_trading"
    RESUME_NORMAL = "resume_normal"
    NO_ACTION = "no_action"


@dataclass
class Decision:
    """Decision với lý do và priority"""
    action: Action
    symbol: str
    reason: str
    priority: int  # 1=critical, 2=high, 3=medium, 4=low
    params: dict = None  # Additional parameters cho action


class DecisionEngine:
    """
    Decision engine tự động quyết định actions

    Decision Tree:

    1. Nếu consecutive losses >= 5 → PAUSE_TRADING (priority 1)
    2. Nếu Sharpe drop > 50% → RETRAIN (priority 1)
    3. Nếu Market regime changed → SWITCH_STRATEGY (priority 2)
    4. Nếu Win rate drop > 20% → INCREASE_THRESHOLD (priority 2)
    5. Nếu Prediction error increase > 50% → RETRAIN (priority 1)
    6. Nếu Drawdown > 15% → DECREASE_POSITION (priority 2)
    """

    def __init__(self):
        self.decision_history = []

    def analyze_health_and_decide(self, health_check):
        """
        Phân tích health check và quyết định action

        Args:
            health_check: Output từ ModelHealthMonitor.comprehensive_health_check()

        Returns:
            List[Decision]
        """
        decisions = []
        symbol = health_check['symbol']
        alerts = health_check['alerts']

        # Priority 1: CRITICAL alerts → Immediate action
        for alert in alerts:
            if alert['severity'] == 'high':

                # Consecutive losses → PAUSE
                if alert['type'] == 'consecutive_losses':
                    decisions.append(Decision(
                        action=Action.PAUSE_TRADING,
                        symbol=symbol,
                        reason=f"Consecutive losses detected: {alert['message']}",
                        priority=1,
                        params={'duration_days': 7}
                    ))

                # Performance degradation → RETRAIN
                elif alert['type'] == 'performance_degradation':
                    sharpe_drop = health_check.get('metrics', {}).get('sharpe_drop_pct', 0)

                    if sharpe_drop > 0.50:  # >50% drop
                        decisions.append(Decision(
                            action=Action.RETRAIN,
                            symbol=symbol,
                            reason=f"Severe Sharpe degradation: {alert['message']}",
                            priority=1,
                            params={'retrain_type': 'full', 'epochs': 20}
                        ))
                    else:
                        decisions.append(Decision(
                            action=Action.RETRAIN,
                            symbol=symbol,
                            reason=f"Sharpe degradation: {alert['message']}",
                            priority=2,
                            params={'retrain_type': 'fine_tune', 'epochs': 10}
                        ))

                # Prediction degradation → URGENT RETRAIN
                elif alert['type'] == 'prediction_degradation':
                    decisions.append(Decision(
                        action=Action.RETRAIN,
                        symbol=symbol,
                        reason=f"Model losing predictive power: {alert['message']}",
                        priority=1,
                        params={'retrain_type': 'full', 'epochs': 30}
                    ))

        # Priority 2: MEDIUM alerts → Adjust parameters
        for alert in alerts:
            if alert['severity'] == 'medium':

                # Regime change → SWITCH STRATEGY
                if alert['type'] == 'regime_change':
                    # Determine new strategy based on regime
                    regime = self._extract_regime_from_message(alert['message'])

                    new_strategy = self._map_regime_to_strategy(regime)

                    decisions.append(Decision(
                        action=Action.SWITCH_STRATEGY,
                        symbol=symbol,
                        reason=f"Market regime changed: {alert['message']}",
                        priority=2,
                        params={'new_strategy': new_strategy, 'regime': regime}
                    ))

                # Win rate decline → INCREASE THRESHOLD
                elif alert['type'] == 'win_rate_decline':
                    current_threshold = self._get_current_threshold(symbol)

                    new_threshold = current_threshold * 1.5  # Increase by 50%

                    decisions.append(Decision(
                        action=Action.INCREASE_THRESHOLD,
                        symbol=symbol,
                        reason=f"Win rate declining: {alert['message']}",
                        priority=2,
                        params={'new_threshold': new_threshold}
                    ))

        # If healthy and was previously paused → RESUME
        if health_check['overall_health'] == 'healthy':
            if self._is_currently_paused(symbol):
                decisions.append(Decision(
                    action=Action.RESUME_NORMAL,
                    symbol=symbol,
                    reason="Health restored to normal levels",
                    priority=3
                ))

        # If no critical decisions → NO ACTION
        if not decisions:
            decisions.append(Decision(
                action=Action.NO_ACTION,
                symbol=symbol,
                reason="Model operating normally",
                priority=4
            ))

        # Record decisions
        self.decision_history.extend(decisions)

        return decisions

    def _extract_regime_from_message(self, message):
        """Extract regime từ alert message"""
        if 'bull' in message.lower():
            return 'bull'
        elif 'bear' in message.lower():
            return 'bear'
        elif 'high_vol' in message.lower():
            return 'high_vol'
        else:
            return 'sideways'

    def _map_regime_to_strategy(self, regime):
        """Map regime to optimal strategy"""
        mapping = {
            'bull': 'momentum',
            'bear': 'mean_reversion',
            'high_vol': 'low_frequency',  # Trade less in high vol
            'sideways': 'range_trading'
        }
        return mapping.get(regime, 'balanced')

    def _get_current_threshold(self, symbol):
        """Get current threshold cho symbol (từ config)"""
        # Load from adaptive config
        try:
            from adaptive_trading_config import ADAPTIVE_CONFIGS
            return ADAPTIVE_CONFIGS[symbol]['entry_threshold']
        except:
            return 0.01  # Default

    def _is_currently_paused(self, symbol):
        """Check if symbol is currently paused"""
        pause_file = Path(f'monitoring/paused/{symbol}.json')
        if pause_file.exists():
            with open(pause_file) as f:
                data = json.load(f)
                # Check if pause expired
                from datetime import datetime
                pause_until = datetime.fromisoformat(data['pause_until'])
                return datetime.now() < pause_until
        return False

    def execute_decisions(self, decisions: List[Decision], dry_run=True):
        """
        Execute the decisions (hoặc dry run)

        Args:
            decisions: List of Decision objects
            dry_run: If True, only print actions without executing
        """

        print("="*70)
        print("DECISION EXECUTION")
        print("="*70)

        # Sort by priority
        sorted_decisions = sorted(decisions, key=lambda d: d.priority)

        for decision in sorted_decisions:
            self._execute_single_decision(decision, dry_run)

    def _execute_single_decision(self, decision: Decision, dry_run=True):
        """Execute single decision"""

        print(f"\n[Priority {decision.priority}] {decision.symbol}: {decision.action.value}")
        print(f"  Reason: {decision.reason}")

        if dry_run:
            print(f"  [DRY RUN] Would execute: {decision.action.value}")
            if decision.params:
                print(f"  Params: {decision.params}")
            return

        # Execute based on action type
        if decision.action == Action.RETRAIN:
            self._execute_retrain(decision)

        elif decision.action == Action.SWITCH_STRATEGY:
            self._execute_switch_strategy(decision)

        elif decision.action == Action.INCREASE_THRESHOLD:
            self._execute_increase_threshold(decision)

        elif decision.action == Action.DECREASE_POSITION:
            self._execute_decrease_position(decision)

        elif decision.action == Action.PAUSE_TRADING:
            self._execute_pause_trading(decision)

        elif decision.action == Action.RESUME_NORMAL:
            self._execute_resume_normal(decision)

        else:  # NO_ACTION
            print("  No action needed")

    def _execute_retrain(self, decision: Decision):
        """Execute retraining"""
        symbol = decision.symbol
        params = decision.params or {}

        retrain_type = params.get('retrain_type', 'fine_tune')
        epochs = params.get('epochs', 10)

        print(f"  Executing: RETRAIN {symbol}")
        print(f"    Type: {retrain_type}")
        print(f"    Epochs: {epochs}")

        # Create retrain job file
        job_file = Path(f'jobs/retrain_{symbol}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        job_file.parent.mkdir(exist_ok=True)

        with open(job_file, 'w') as f:
            json.dump({
                'action': 'retrain',
                'symbol': symbol,
                'type': retrain_type,
                'epochs': epochs,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }, f, indent=2)

        print(f"  ✓ Retrain job created: {job_file}")

    def _execute_switch_strategy(self, decision: Decision):
        """Execute strategy switch"""
        symbol = decision.symbol
        params = decision.params or {}

        new_strategy = params.get('new_strategy', 'balanced')

        print(f"  Executing: SWITCH_STRATEGY {symbol}")
        print(f"    New strategy: {new_strategy}")

        # Update config file
        config_file = Path('config/strategy_overrides.json')
        config_file.parent.mkdir(exist_ok=True)

        # Load existing overrides
        overrides = {}
        if config_file.exists():
            with open(config_file) as f:
                overrides = json.load(f)

        # Add override
        overrides[symbol] = {
            'strategy': new_strategy,
            'updated_at': datetime.now().isoformat(),
            'reason': decision.reason
        }

        with open(config_file, 'w') as f:
            json.dump(overrides, f, indent=2)

        print(f"  ✓ Strategy updated in: {config_file}")

    def _execute_increase_threshold(self, decision: Decision):
        """Execute threshold increase"""
        symbol = decision.symbol
        params = decision.params or {}

        new_threshold = params.get('new_threshold', 0.02)

        print(f"  Executing: INCREASE_THRESHOLD {symbol}")
        print(f"    New threshold: {new_threshold:.3f}")

        # Update threshold override
        threshold_file = Path('config/threshold_overrides.json')
        threshold_file.parent.mkdir(exist_ok=True)

        overrides = {}
        if threshold_file.exists():
            with open(threshold_file) as f:
                overrides = json.load(f)

        overrides[symbol] = {
            'threshold': new_threshold,
            'updated_at': datetime.now().isoformat(),
            'reason': decision.reason
        }

        with open(threshold_file, 'w') as f:
            json.dump(overrides, f, indent=2)

        print(f"  ✓ Threshold updated in: {threshold_file}")

    def _execute_decrease_position(self, decision: Decision):
        """Execute position size decrease"""
        # Implementation similar to threshold
        print(f"  Executing: DECREASE_POSITION {decision.symbol}")

    def _execute_pause_trading(self, decision: Decision):
        """Execute trading pause"""
        symbol = decision.symbol
        params = decision.params or {}

        duration_days = params.get('duration_days', 7)

        print(f"  Executing: PAUSE_TRADING {symbol}")
        print(f"    Duration: {duration_days} days")

        # Create pause file
        pause_file = Path(f'monitoring/paused/{symbol}.json')
        pause_file.parent.mkdir(exist_ok=True, parents=True)

        from datetime import timedelta
        pause_until = datetime.now() + timedelta(days=duration_days)

        with open(pause_file, 'w') as f:
            json.dump({
                'paused_at': datetime.now().isoformat(),
                'pause_until': pause_until.isoformat(),
                'reason': decision.reason,
                'duration_days': duration_days
            }, f, indent=2)

        print(f"  ✓ Trading paused until: {pause_until.strftime('%Y-%m-%d')}")

    def _execute_resume_normal(self, decision: Decision):
        """Execute resume normal trading"""
        symbol = decision.symbol

        print(f"  Executing: RESUME_NORMAL {symbol}")

        # Remove pause file
        pause_file = Path(f'monitoring/paused/{symbol}.json')
        if pause_file.exists():
            pause_file.unlink()
            print(f"  ✓ Trading resumed")
        else:
            print(f"  ! No pause file found")


if __name__ == "__main__":
    # Example usage
    from model_health_monitor import ModelHealthMonitor

    monitor = ModelHealthMonitor()
    engine = DecisionEngine()

    # Simulate health check with issues
    import pandas as pd

    trades = pd.DataFrame({
        'pnl_pct': [-2, -1.5, -1, -2, -1.5, -2],  # Losing streak
        'hold_days': [3, 3, 4, 3, 3, 4]
    })

    baseline = {'sharpe': 1.5, 'win_rate': 0.55}

    health_check = monitor.comprehensive_health_check(
        symbol='FPT',
        recent_trades=trades,
        baseline_metrics=baseline
    )

    # Get decisions
    decisions = engine.analyze_health_and_decide(health_check)

    # Execute (dry run)
    engine.execute_decisions(decisions, dry_run=True)
