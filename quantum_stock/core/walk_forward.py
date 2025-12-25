"""
Walk-Forward Optimization Module
Prevents overfitting by testing on out-of-sample data
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class WFOResult:
    """Walk-Forward Optimization Results"""
    strategy_name: str
    symbol: str
    num_folds: int

    # Aggregate metrics
    total_return_pct: float = 0.0
    avg_return_per_fold: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0

    # Robustness metrics
    consistency_score: float = 0.0  # % of profitable folds
    robustness_ratio: float = 0.0  # Out-of-sample / In-sample performance
    degradation_ratio: float = 0.0  # Performance degradation IS to OOS

    # Overfitting metrics
    pbo: float = 0.0  # Probability of Backtest Overfitting
    deflated_sharpe: float = 0.0

    # Per-fold results
    fold_results: List[Dict] = field(default_factory=list)

    # Best parameters across folds
    stable_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'num_folds': self.num_folds,
            'total_return_pct': self.total_return_pct,
            'sharpe_ratio': self.sharpe_ratio,
            'win_rate': self.win_rate,
            'consistency_score': self.consistency_score,
            'robustness_ratio': self.robustness_ratio,
            'pbo': self.pbo,
            'fold_results': self.fold_results
        }

    def get_summary(self) -> str:
        return f"""
WALK-FORWARD OPTIMIZATION RESULTS
{'='*50}
Strategy: {self.strategy_name}
Symbol: {self.symbol}
Folds: {self.num_folds}

Performance:
  - Total Return: {self.total_return_pct:.1f}%
  - Avg Return/Fold: {self.avg_return_per_fold:.1f}%
  - Sharpe Ratio: {self.sharpe_ratio:.2f}
  - Win Rate: {self.win_rate:.1f}%

Robustness:
  - Consistency: {self.consistency_score:.0f}% of folds profitable
  - Robustness Ratio: {self.robustness_ratio:.2f}
  - Degradation: {self.degradation_ratio:.1f}%

Overfitting Risk:
  - PBO: {self.pbo:.1f}% (lower is better)
  - Deflated Sharpe: {self.deflated_sharpe:.2f}

Verdict: {self._get_verdict()}
{'='*50}
"""

    def _get_verdict(self) -> str:
        if self.pbo > 50:
            return "⚠️ HIGH OVERFITTING RISK - Chiến lược không robust"
        elif self.consistency_score < 50:
            return "⚠️ INCONSISTENT - Kết quả không ổn định"
        elif self.robustness_ratio < 0.5:
            return "⚠️ PERFORMANCE DEGRADATION - OOS kém hơn nhiều so với IS"
        elif self.sharpe_ratio > 1 and self.consistency_score >= 70:
            return "✅ ROBUST - Chiến lược có thể triển khai"
        else:
            return "🟡 MODERATE - Cần thêm đánh giá"


class WalkForwardOptimizer:
    """
    Walk-Forward Analysis for robust strategy validation
    """

    def __init__(self, backtest_engine):
        """
        Args:
            backtest_engine: BacktestEngine instance
        """
        self.backtest_engine = backtest_engine

    def optimize(self, df: pd.DataFrame, strategy_class: type,
                param_grid: Dict[str, List], symbol: str = "UNKNOWN",
                num_folds: int = 5, train_pct: float = 0.7,
                optimization_metric: str = "sharpe_ratio") -> WFOResult:
        """
        Run walk-forward optimization

        Args:
            df: Historical data with datetime index
            strategy_class: Strategy class to optimize
            param_grid: Parameter grid for optimization
            symbol: Stock symbol
            num_folds: Number of walk-forward folds
            train_pct: Percentage of each fold for training (in-sample)
            optimization_metric: Metric to optimize

        Returns:
            WFOResult with comprehensive analysis
        """
        # Split data into folds
        folds = self._create_folds(df, num_folds)

        fold_results = []
        is_metrics = []  # In-sample metrics
        oos_metrics = []  # Out-of-sample metrics
        all_params = []

        for i, (train_data, test_data) in enumerate(folds):
            # Phase 1: Optimize on training data (in-sample)
            best_params, is_result = self.backtest_engine.optimize_parameters(
                train_data, strategy_class, param_grid, symbol, optimization_metric
            )

            if not best_params or not is_result:
                continue

            # Phase 2: Test on out-of-sample data with best params
            strategy = strategy_class(**best_params)
            oos_result = self.backtest_engine.run(test_data, strategy, symbol)

            # Record results
            fold_results.append({
                'fold': i + 1,
                'train_start': str(train_data.index[0]),
                'train_end': str(train_data.index[-1]),
                'test_start': str(test_data.index[0]),
                'test_end': str(test_data.index[-1]),
                'best_params': best_params,
                'is_return': is_result.total_return_pct,
                'is_sharpe': is_result.sharpe_ratio,
                'oos_return': oos_result.total_return_pct,
                'oos_sharpe': oos_result.sharpe_ratio,
                'oos_win_rate': oos_result.win_rate,
                'oos_trades': oos_result.total_trades
            })

            is_metrics.append({
                'return': is_result.total_return_pct,
                'sharpe': is_result.sharpe_ratio
            })

            oos_metrics.append({
                'return': oos_result.total_return_pct,
                'sharpe': oos_result.sharpe_ratio,
                'win_rate': oos_result.win_rate
            })

            all_params.append(best_params)

        if not fold_results:
            return WFOResult(
                strategy_name=strategy_class.__name__,
                symbol=symbol,
                num_folds=num_folds
            )

        # Calculate aggregate metrics
        result = self._calculate_wfo_metrics(
            fold_results, is_metrics, oos_metrics, all_params,
            strategy_class.__name__, symbol, num_folds
        )

        return result

    def _create_folds(self, df: pd.DataFrame, num_folds: int,
                     train_pct: float = 0.7) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Create walk-forward folds with anchored training

        Each fold:
        - Training: Growing window from start
        - Testing: Fixed window after training
        """
        n = len(df)
        fold_size = n // num_folds
        folds = []

        for i in range(num_folds):
            # Anchored walk-forward: training always starts from beginning
            train_end = int(n * (0.5 + (i * 0.1)))  # Growing training window
            test_start = train_end
            test_end = min(test_start + fold_size, n)

            if test_end <= test_start:
                continue

            train_data = df.iloc[:train_end].copy()
            test_data = df.iloc[test_start:test_end].copy()

            if len(train_data) > 50 and len(test_data) > 10:  # Minimum data requirements
                folds.append((train_data, test_data))

        return folds

    def _calculate_wfo_metrics(self, fold_results: List[Dict],
                              is_metrics: List[Dict], oos_metrics: List[Dict],
                              all_params: List[Dict], strategy_name: str,
                              symbol: str, num_folds: int) -> WFOResult:
        """Calculate comprehensive WFO metrics"""

        result = WFOResult(
            strategy_name=strategy_name,
            symbol=symbol,
            num_folds=num_folds,
            fold_results=fold_results
        )

        # Aggregate OOS performance
        oos_returns = [m['return'] for m in oos_metrics]
        oos_sharpes = [m['sharpe'] for m in oos_metrics]
        oos_win_rates = [m.get('win_rate', 50) for m in oos_metrics]

        result.total_return_pct = sum(oos_returns)
        result.avg_return_per_fold = np.mean(oos_returns) if oos_returns else 0
        result.sharpe_ratio = np.mean(oos_sharpes) if oos_sharpes else 0
        result.win_rate = np.mean(oos_win_rates) if oos_win_rates else 0

        # Consistency Score: % of profitable OOS folds
        profitable_folds = sum(1 for r in oos_returns if r > 0)
        result.consistency_score = (profitable_folds / len(oos_returns) * 100) if oos_returns else 0

        # Robustness Ratio: OOS / IS performance
        is_returns = [m['return'] for m in is_metrics]
        avg_is = np.mean(is_returns) if is_returns else 1
        avg_oos = np.mean(oos_returns) if oos_returns else 0

        if avg_is != 0:
            result.robustness_ratio = avg_oos / avg_is
            result.degradation_ratio = (1 - result.robustness_ratio) * 100
        else:
            result.robustness_ratio = 0
            result.degradation_ratio = 100

        # Probability of Backtest Overfitting (PBO)
        # Simplified: % of folds where OOS < IS significantly
        overfit_folds = sum(1 for i in range(len(is_metrics))
                          if oos_metrics[i]['return'] < is_metrics[i]['return'] * 0.5)
        result.pbo = (overfit_folds / len(is_metrics) * 100) if is_metrics else 0

        # Deflated Sharpe Ratio
        # Adjust for multiple testing and variance
        if result.sharpe_ratio > 0 and len(oos_sharpes) > 1:
            sharpe_std = np.std(oos_sharpes)
            trials_penalty = np.sqrt(2 * np.log(len(all_params) * num_folds))
            result.deflated_sharpe = result.sharpe_ratio - trials_penalty * sharpe_std
        else:
            result.deflated_sharpe = result.sharpe_ratio

        # Find most stable parameters
        result.stable_params = self._find_stable_params(all_params)

        # Calculate profit factor from returns
        positive_returns = [r for r in oos_returns if r > 0]
        negative_returns = [abs(r) for r in oos_returns if r < 0]
        total_positive = sum(positive_returns) if positive_returns else 0
        total_negative = sum(negative_returns) if negative_returns else 1
        result.profit_factor = total_positive / total_negative if total_negative > 0 else 0

        return result

    def _find_stable_params(self, all_params: List[Dict]) -> Dict[str, Any]:
        """Find parameters that appear most frequently across folds"""
        if not all_params:
            return {}

        param_counts = {}
        for params in all_params:
            for key, value in params.items():
                if key not in param_counts:
                    param_counts[key] = {}
                value_str = str(value)
                param_counts[key][value_str] = param_counts[key].get(value_str, 0) + 1

        stable = {}
        for key, values in param_counts.items():
            most_common = max(values.items(), key=lambda x: x[1])
            stable[key] = eval(most_common[0]) if most_common[0].replace('.', '').isdigit() else most_common[0]

        return stable

    def combinatorial_purged_cv(self, df: pd.DataFrame, strategy_class: type,
                               param_grid: Dict[str, List], symbol: str = "UNKNOWN",
                               num_paths: int = 10, embargo_pct: float = 0.01) -> WFOResult:
        """
        Combinatorial Purged Cross-Validation (CPCV)
        More rigorous than standard WFO for detecting overfitting

        Args:
            df: Historical data
            strategy_class: Strategy class
            param_grid: Parameter grid
            symbol: Stock symbol
            num_paths: Number of test paths to generate
            embargo_pct: Percentage of data to embargo between train/test
        """
        n = len(df)
        embargo_size = int(n * embargo_pct)

        # Generate multiple random train/test splits
        path_results = []

        for path in range(num_paths):
            # Random split point
            split = np.random.randint(int(n * 0.3), int(n * 0.7))

            # Create purged train/test sets
            train_end = split - embargo_size
            test_start = split + embargo_size

            if train_end < 50 or (n - test_start) < 20:
                continue

            train_data = df.iloc[:train_end].copy()
            test_data = df.iloc[test_start:].copy()

            # Optimize on training
            best_params, is_result = self.backtest_engine.optimize_parameters(
                train_data, strategy_class, param_grid, symbol
            )

            if not best_params:
                continue

            # Test on OOS
            strategy = strategy_class(**best_params)
            oos_result = self.backtest_engine.run(test_data, strategy, symbol)

            path_results.append({
                'is_sharpe': is_result.sharpe_ratio if is_result else 0,
                'oos_sharpe': oos_result.sharpe_ratio,
                'is_return': is_result.total_return_pct if is_result else 0,
                'oos_return': oos_result.total_return_pct
            })

        if not path_results:
            return WFOResult(strategy_name=strategy_class.__name__, symbol=symbol, num_folds=num_paths)

        # Calculate CPCV metrics
        is_sharpes = [p['is_sharpe'] for p in path_results]
        oos_sharpes = [p['oos_sharpe'] for p in path_results]

        # PBO from CPCV
        overfit_count = sum(1 for i in range(len(path_results))
                          if oos_sharpes[i] < 0 and is_sharpes[i] > 0)
        pbo = overfit_count / len(path_results) * 100

        return WFOResult(
            strategy_name=strategy_class.__name__,
            symbol=symbol,
            num_folds=num_paths,
            sharpe_ratio=np.mean(oos_sharpes),
            total_return_pct=sum(p['oos_return'] for p in path_results),
            pbo=pbo,
            robustness_ratio=np.mean(oos_sharpes) / np.mean(is_sharpes) if np.mean(is_sharpes) != 0 else 0,
            consistency_score=sum(1 for s in oos_sharpes if s > 0) / len(oos_sharpes) * 100
        )
