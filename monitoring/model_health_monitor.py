"""
Model Health Monitoring System
================================
Tự động phát hiện khi nào cần retrain, đổi strategy, hoặc thay đổi approach
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path


class ModelHealthMonitor:
    """
    Monitor model performance và alert khi có vấn đề

    Signals to watch:
    1. Performance Degradation (Sharpe drops)
    2. Prediction Accuracy Decay
    3. Market Regime Change
    4. Strategy Ineffectiveness
    """

    def __init__(self, alert_thresholds=None):
        self.thresholds = alert_thresholds or {
            'sharpe_drop_pct': 0.30,        # Alert nếu Sharpe giảm >30%
            'win_rate_drop_pct': 0.15,       # Alert nếu win rate giảm >15%
            'consecutive_losses': 5,         # Alert nếu thua 5 lệnh liên tiếp
            'drawdown_pct': 0.15,            # Alert nếu DD >15%
            'prediction_error_increase': 0.50,  # Alert nếu error tăng >50%
        }

        self.alerts = []

    def check_performance_degradation(self, recent_trades, baseline_sharpe):
        """
        Kiểm tra performance có giảm không

        Returns:
            dict: {degraded: bool, current_sharpe: float, reason: str}
        """
        if len(recent_trades) < 10:
            return {'degraded': False, 'reason': 'Not enough trades'}

        # Calculate recent Sharpe (last 20 trades)
        recent = recent_trades.tail(20)
        returns = recent['pnl_pct'].values / 100

        if returns.std() == 0:
            current_sharpe = 0
        else:
            avg_hold = recent['hold_days'].mean()
            current_sharpe = returns.mean() / returns.std() * np.sqrt(252 / avg_hold)

        # Check degradation
        sharpe_drop = (baseline_sharpe - current_sharpe) / baseline_sharpe

        if sharpe_drop > self.thresholds['sharpe_drop_pct']:
            return {
                'degraded': True,
                'current_sharpe': current_sharpe,
                'baseline_sharpe': baseline_sharpe,
                'drop_pct': sharpe_drop * 100,
                'reason': f'Sharpe dropped {sharpe_drop*100:.1f}% (from {baseline_sharpe:.2f} to {current_sharpe:.2f})'
            }

        return {'degraded': False, 'current_sharpe': current_sharpe}

    def check_win_rate_decline(self, recent_trades, baseline_win_rate):
        """Kiểm tra win rate có giảm không"""

        if len(recent_trades) < 10:
            return {'declined': False}

        recent = recent_trades.tail(20)
        current_win_rate = (recent['pnl_pct'] > 0).mean()

        win_rate_drop = (baseline_win_rate - current_win_rate) / baseline_win_rate

        if win_rate_drop > self.thresholds['win_rate_drop_pct']:
            return {
                'declined': True,
                'current_win_rate': current_win_rate,
                'baseline_win_rate': baseline_win_rate,
                'drop_pct': win_rate_drop * 100,
                'reason': f'Win rate dropped {win_rate_drop*100:.1f}% (from {baseline_win_rate*100:.1f}% to {current_win_rate*100:.1f}%)'
            }

        return {'declined': False, 'current_win_rate': current_win_rate}

    def check_consecutive_losses(self, recent_trades):
        """Kiểm tra chuỗi thua liên tiếp"""

        if len(recent_trades) == 0:
            return {'alert': False}

        # Count consecutive losses
        consecutive = 0
        max_consecutive = 0

        for pnl in recent_trades['pnl_pct'].values[::-1]:  # Reverse (newest first)
            if pnl < 0:
                consecutive += 1
                max_consecutive = max(max_consecutive, consecutive)
            else:
                break

        if consecutive >= self.thresholds['consecutive_losses']:
            return {
                'alert': True,
                'consecutive_losses': consecutive,
                'reason': f'{consecutive} consecutive losses - possible market regime change'
            }

        return {'alert': False, 'consecutive_losses': consecutive}

    def check_prediction_accuracy(self, predictions, actuals):
        """
        Kiểm tra prediction accuracy có giảm không

        Args:
            predictions: Model predictions cho T+3
            actuals: Actual returns ở T+3
        """

        if len(predictions) < 20:
            return {'degraded': False}

        # Recent accuracy (last 20 predictions)
        recent_preds = predictions[-20:]
        recent_actuals = actuals[-20:]

        # Directional accuracy (predict up vs actual up)
        direction_correct = (
            (recent_preds > 0) == (recent_actuals > 0)
        ).mean()

        # MAE (Mean Absolute Error)
        mae = np.abs(recent_preds - recent_actuals).mean()

        # Compare with baseline (first 50 predictions)
        if len(predictions) > 50:
            baseline_preds = predictions[:50]
            baseline_actuals = actuals[:50]
            baseline_mae = np.abs(baseline_preds - baseline_actuals).mean()

            error_increase = (mae - baseline_mae) / baseline_mae

            if error_increase > self.thresholds['prediction_error_increase']:
                return {
                    'degraded': True,
                    'current_mae': mae,
                    'baseline_mae': baseline_mae,
                    'error_increase_pct': error_increase * 100,
                    'direction_accuracy': direction_correct,
                    'reason': f'Prediction error increased {error_increase*100:.1f}%'
                }

        return {
            'degraded': False,
            'direction_accuracy': direction_correct,
            'mae': mae
        }

    def detect_market_regime_change(self, vn_index_data):
        """
        Phát hiện thị trường có thay đổi regime không

        Regimes:
        - Bull: Uptrend + Low volatility
        - Bear: Downtrend + Low volatility
        - High Vol: High volatility (any trend)
        - Sideways: No trend + Low volatility
        """

        if len(vn_index_data) < 200:
            return {'regime': 'unknown', 'changed': False}

        # Calculate indicators
        close = vn_index_data['close']

        sma_50 = close.rolling(50).mean().iloc[-1]
        sma_200 = close.rolling(200).mean().iloc[-1]
        current_price = close.iloc[-1]

        # Volatility (20-day rolling std of returns)
        returns = close.pct_change()
        vol_20 = returns.rolling(20).std().iloc[-1]
        vol_60 = returns.rolling(60).std().mean()  # Longer-term avg

        # Trend strength
        trend_strength = abs(sma_50 - sma_200) / sma_200

        # Classify regime
        high_vol_threshold = 0.02  # 2% daily vol
        trend_threshold = 0.05      # 5% difference

        if vol_20 > high_vol_threshold:
            current_regime = 'high_vol'
        elif current_price > sma_50 > sma_200 and trend_strength > trend_threshold:
            current_regime = 'bull'
        elif current_price < sma_50 < sma_200 and trend_strength > trend_threshold:
            current_regime = 'bear'
        else:
            current_regime = 'sideways'

        # Check if changed (load previous regime)
        regime_file = Path('monitoring/current_regime.json')
        previous_regime = 'unknown'

        if regime_file.exists():
            with open(regime_file) as f:
                data = json.load(f)
                previous_regime = data.get('regime', 'unknown')

        # Save current regime
        regime_file.parent.mkdir(exist_ok=True)
        with open(regime_file, 'w') as f:
            json.dump({
                'regime': current_regime,
                'timestamp': datetime.now().isoformat(),
                'sma_50': float(sma_50),
                'sma_200': float(sma_200),
                'volatility': float(vol_20)
            }, f, indent=2)

        changed = (current_regime != previous_regime) and (previous_regime != 'unknown')

        return {
            'regime': current_regime,
            'previous_regime': previous_regime,
            'changed': changed,
            'volatility': vol_20,
            'trend_strength': trend_strength,
            'reason': f'Market regime: {previous_regime} → {current_regime}' if changed else None
        }

    def check_strategy_effectiveness(self, trades_by_strategy):
        """
        Kiểm tra từng strategy có còn hiệu quả không

        Args:
            trades_by_strategy: dict {strategy_name: trades_df}
        """

        ineffective_strategies = []

        for strategy, trades in trades_by_strategy.items():
            if len(trades) < 10:
                continue

            recent = trades.tail(20)

            # Win rate
            win_rate = (recent['pnl_pct'] > 0).mean()

            # Average return
            avg_return = recent['pnl_pct'].mean()

            # Sharpe
            returns = recent['pnl_pct'].values / 100
            if returns.std() > 0:
                sharpe = returns.mean() / returns.std() * np.sqrt(252 / recent['hold_days'].mean())
            else:
                sharpe = 0

            # Check if ineffective
            if sharpe < 0.3 or win_rate < 0.40 or avg_return < 0:
                ineffective_strategies.append({
                    'strategy': strategy,
                    'sharpe': sharpe,
                    'win_rate': win_rate,
                    'avg_return': avg_return,
                    'recent_trades': len(recent),
                    'reason': f'Strategy "{strategy}" underperforming (Sharpe: {sharpe:.2f}, Win Rate: {win_rate*100:.1f}%)'
                })

        return {
            'has_ineffective': len(ineffective_strategies) > 0,
            'ineffective_strategies': ineffective_strategies
        }

    def comprehensive_health_check(self,
                                   symbol,
                                   recent_trades,
                                   baseline_metrics,
                                   predictions=None,
                                   actuals=None,
                                   vn_index_data=None):
        """
        Tổng hợp tất cả checks

        Returns:
            dict: {
                'overall_health': 'healthy' | 'warning' | 'critical',
                'alerts': [...],
                'recommendations': [...]
            }
        """

        alerts = []
        recommendations = []

        # 1. Performance degradation
        perf_check = self.check_performance_degradation(
            recent_trades,
            baseline_metrics.get('sharpe', 1.0)
        )
        if perf_check.get('degraded'):
            alerts.append({
                'severity': 'high',
                'type': 'performance_degradation',
                'message': perf_check['reason']
            })
            recommendations.append('RETRAIN model with recent data')

        # 2. Win rate decline
        win_rate_check = self.check_win_rate_decline(
            recent_trades,
            baseline_metrics.get('win_rate', 0.50)
        )
        if win_rate_check.get('declined'):
            alerts.append({
                'severity': 'medium',
                'type': 'win_rate_decline',
                'message': win_rate_check['reason']
            })
            recommendations.append('INCREASE entry threshold to filter low-quality signals')

        # 3. Consecutive losses
        loss_check = self.check_consecutive_losses(recent_trades)
        if loss_check.get('alert'):
            alerts.append({
                'severity': 'high',
                'type': 'consecutive_losses',
                'message': loss_check['reason']
            })
            recommendations.append('STOP trading this stock temporarily - possible regime change')

        # 4. Prediction accuracy (if provided)
        if predictions is not None and actuals is not None:
            pred_check = self.check_prediction_accuracy(predictions, actuals)
            if pred_check.get('degraded'):
                alerts.append({
                    'severity': 'high',
                    'type': 'prediction_degradation',
                    'message': pred_check['reason']
                })
                recommendations.append('RETRAIN urgently - model losing predictive power')

        # 5. Market regime change (if provided)
        if vn_index_data is not None:
            regime_check = self.detect_market_regime_change(vn_index_data)
            if regime_check.get('changed'):
                alerts.append({
                    'severity': 'medium',
                    'type': 'regime_change',
                    'message': regime_check['reason']
                })
                recommendations.append(f'SWITCH strategy to {regime_check["regime"]}-optimized approach')

        # Overall health assessment
        if len([a for a in alerts if a['severity'] == 'high']) >= 2:
            overall_health = 'critical'
        elif len(alerts) >= 2:
            overall_health = 'warning'
        elif len(alerts) >= 1:
            overall_health = 'warning'
        else:
            overall_health = 'healthy'

        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'overall_health': overall_health,
            'alerts': alerts,
            'recommendations': list(set(recommendations)),  # Deduplicate
            'metrics': {
                'current_sharpe': perf_check.get('current_sharpe'),
                'current_win_rate': win_rate_check.get('current_win_rate'),
                'consecutive_losses': loss_check.get('consecutive_losses', 0),
            }
        }


def generate_health_report(health_checks):
    """Generate human-readable report"""

    print("="*70)
    print("MODEL HEALTH REPORT")
    print("="*70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Group by health status
    critical = [c for c in health_checks if c['overall_health'] == 'critical']
    warning = [c for c in health_checks if c['overall_health'] == 'warning']
    healthy = [c for c in health_checks if c['overall_health'] == 'healthy']

    print(f"SUMMARY:")
    print(f"  Critical: {len(critical)} stocks")
    print(f"  Warning:  {len(warning)} stocks")
    print(f"  Healthy:  {len(healthy)} stocks")
    print()

    # Critical stocks (need immediate action)
    if critical:
        print("="*70)
        print("CRITICAL - IMMEDIATE ACTION REQUIRED")
        print("="*70)

        for check in critical:
            print(f"\n{check['symbol']}:")
            print(f"  Alerts:")
            for alert in check['alerts']:
                print(f"    [{alert['severity'].upper()}] {alert['message']}")

            print(f"  Recommendations:")
            for rec in check['recommendations']:
                print(f"    → {rec}")

    # Warning stocks
    if warning:
        print("\n" + "="*70)
        print("WARNING - MONITOR CLOSELY")
        print("="*70)

        for check in warning:
            print(f"\n{check['symbol']}:")
            for alert in check['alerts']:
                print(f"  [{alert['severity'].upper()}] {alert['message']}")

    print("\n" + "="*70)


if __name__ == "__main__":
    # Example usage
    monitor = ModelHealthMonitor()

    # Simulate trades data
    trades = pd.DataFrame({
        'pnl_pct': [-2, -1.5, -1, 1, -2, -1, 0.5, -1.5, -2, -1],  # Losing streak
        'hold_days': [3, 3, 4, 3, 3, 4, 3, 3, 4, 3]
    })

    baseline = {
        'sharpe': 1.5,
        'win_rate': 0.55
    }

    # Run health check
    health = monitor.comprehensive_health_check(
        symbol='FPT',
        recent_trades=trades,
        baseline_metrics=baseline
    )

    generate_health_report([health])
