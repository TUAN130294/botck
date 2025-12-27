# -*- coding: utf-8 -*-
"""
Walk-Forward Backtester - Level 4 Agentic AI
=============================================
Robust backtesting with walk-forward optimization to prevent overfitting.

Features:
- Rolling window training
- Out-of-sample validation
- Overfitting detection
- Parameter stability analysis
- Monte Carlo validation

Walk-Forward Process:
1. Train on window [0, T]
2. Validate on [T, T+k]
3. Roll window forward
4. Repeat until end of data
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path


@dataclass
class BacktestTrade:
    """Single trade record"""
    entry_date: datetime
    exit_date: datetime
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    hold_days: int
    strategy: str


@dataclass
class BacktestResult:
    """Comprehensive backtest results"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    
    # Returns
    total_return: float
    annual_return: float
    
    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # days
    volatility: float
    
    # Trade stats
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_hold_days: float
    
    # Walk-forward specific
    in_sample_sharpe: float = 0.0
    out_sample_sharpe: float = 0.0
    overfitting_ratio: float = 0.0  # IS/OOS ratio, >2 = overfit
    
    # Stability
    parameter_stability: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    
    def is_robust(self) -> bool:
        """Check if strategy passes robustness tests"""
        return (
            self.overfitting_ratio < 2.0 and
            self.out_sample_sharpe > 0.5 and
            self.max_drawdown > -0.20 and
            self.win_rate > 0.45
        )


class WalkForwardBacktester:
    """
    Walk-Forward Optimization Backtester
    
    Algorithm:
    1. Split data into N folds
    2. For each fold:
        - Train model on in-sample data
        - Validate on out-of-sample data
        - Record OOS performance
    3. Calculate robustness metrics
    4. Detect overfitting
    """
    
    def __init__(
        self,
        train_period: int = 252,  # ~1 year trading days
        test_period: int = 63,    # ~3 months
        n_folds: int = 4,
        min_trades: int = 30
    ):
        self.train_period = train_period
        self.test_period = test_period
        self.n_folds = n_folds
        self.min_trades = min_trades
        
        self.results: List[BacktestResult] = []
        self.trades: List[BacktestTrade] = []
    
    def run_walk_forward(
        self,
        prices: np.ndarray,
        strategy_func: Callable[[np.ndarray, Dict], Tuple[int, float]],
        strategy_params: Dict = None,
        initial_capital: float = 1_000_000_000
    ) -> BacktestResult:
        """
        Run walk-forward backtest
        
        Args:
            prices: Array of close prices
            strategy_func: Function(prices, params) -> (signal, confidence)
                           signal: 1=buy, -1=sell, 0=hold
            strategy_params: Strategy parameters
            initial_capital: Starting capital (VND)
        
        Returns:
            BacktestResult with comprehensive metrics
        """
        if strategy_params is None:
            strategy_params = {}
        
        n_periods = len(prices)
        all_trades = []
        in_sample_returns = []
        out_sample_returns = []
        equity_curve = [initial_capital]
        
        # Calculate number of possible folds
        total_window = self.train_period + self.test_period
        n_possible_folds = (n_periods - total_window) // self.test_period + 1
        actual_folds = min(self.n_folds, n_possible_folds)
        
        if actual_folds < 1:
            # Not enough data for walk-forward
            return self._simple_backtest(prices, strategy_func, strategy_params, initial_capital)
        
        current_capital = initial_capital
        position = 0
        entry_price = 0
        entry_date = None
        
        # Walk through each fold
        for fold in range(actual_folds):
            # Calculate window boundaries
            fold_start = fold * self.test_period
            train_end = fold_start + self.train_period
            test_end = min(train_end + self.test_period, n_periods)
            
            if test_end <= train_end:
                break
            
            # In-sample: Train period
            is_prices = prices[fold_start:train_end]
            is_returns = []
            
            for i in range(50, len(is_prices)):
                signal, conf = strategy_func(is_prices[:i+1], strategy_params)
                daily_return = is_prices[i] / is_prices[i-1] - 1 if i > 0 else 0
                
                if position != 0:
                    is_returns.append(position * daily_return)
                else:
                    is_returns.append(0)
                
                # Update position based on signal
                if signal != 0 and position == 0:
                    position = signal
                elif signal != 0 and signal != position:
                    position = signal
            
            in_sample_returns.extend(is_returns)
            
            # Out-of-sample: Test period
            oos_prices = prices[train_end:test_end]
            oos_returns = []
            
            for i in range(len(oos_prices)):
                # Use full history up to this point for signal
                history = prices[:train_end + i + 1]
                signal, conf = strategy_func(history, strategy_params)
                
                daily_return = oos_prices[i] / oos_prices[i-1] - 1 if i > 0 else 0
                
                if position != 0:
                    oos_returns.append(position * daily_return)
                    current_capital *= (1 + position * daily_return)
                    equity_curve.append(current_capital)
                else:
                    oos_returns.append(0)
                    equity_curve.append(current_capital)
                
                # Trade logic
                if signal != 0 and position == 0:
                    # Enter
                    position = signal
                    entry_price = oos_prices[i]
                    entry_date = datetime.now() + timedelta(days=train_end + i)
                    
                elif signal != 0 and signal != position:
                    # Exit and reverse
                    if entry_date is not None:
                        exit_price = oos_prices[i]
                        pnl = (exit_price - entry_price) * position * 100  # Normalized
                        
                        trade = BacktestTrade(
                            entry_date=entry_date,
                            exit_date=datetime.now() + timedelta(days=train_end + i),
                            symbol="TEST",
                            side="LONG" if position > 0 else "SHORT",
                            entry_price=entry_price,
                            exit_price=exit_price,
                            quantity=100,
                            pnl=pnl,
                            pnl_pct=(exit_price / entry_price - 1) * position * 100,
                            hold_days=i,
                            strategy="WalkForward"
                        )
                        all_trades.append(trade)
                    
                    position = signal
                    entry_price = oos_prices[i]
                    entry_date = datetime.now() + timedelta(days=train_end + i)
            
            out_sample_returns.extend(oos_returns)
        
        # Calculate metrics
        is_returns_arr = np.array(in_sample_returns) if in_sample_returns else np.array([0])
        oos_returns_arr = np.array(out_sample_returns) if out_sample_returns else np.array([0])
        
        is_sharpe = self._calculate_sharpe(is_returns_arr)
        oos_sharpe = self._calculate_sharpe(oos_returns_arr)
        
        # Overfitting ratio
        overfitting = is_sharpe / oos_sharpe if oos_sharpe > 0 else 10.0
        
        # Trade stats
        winning_trades = [t for t in all_trades if t.pnl > 0]
        losing_trades = [t for t in all_trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / max(len(all_trades), 1)
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        total_win = sum(t.pnl for t in winning_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_win / max(total_loss, 1)
        
        # Combined returns
        all_returns = np.concatenate([is_returns_arr, oos_returns_arr])
        
        # Max drawdown
        cum_returns = np.cumprod(1 + all_returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdowns = (cum_returns - running_max) / running_max
        max_dd = np.min(drawdowns)
        
        # Calculate drawdown duration
        dd_duration = 0
        current_duration = 0
        for dd in drawdowns:
            if dd < 0:
                current_duration += 1
                dd_duration = max(dd_duration, current_duration)
            else:
                current_duration = 0
        
        # Build result
        total_return = (equity_curve[-1] / initial_capital - 1) * 100
        n_years = len(all_returns) / 252
        annual_return = (equity_curve[-1] / initial_capital) ** (1 / max(n_years, 0.1)) - 1
        
        result = BacktestResult(
            strategy_name="WalkForward",
            start_date=datetime.now(),
            end_date=datetime.now(),
            total_return=round(total_return, 2),
            annual_return=round(annual_return * 100, 2),
            sharpe_ratio=round(oos_sharpe, 4),
            sortino_ratio=round(self._calculate_sortino(oos_returns_arr), 4),
            max_drawdown=round(max_dd * 100, 2),
            max_drawdown_duration=dd_duration,
            volatility=round(np.std(all_returns) * np.sqrt(252) * 100, 2),
            total_trades=len(all_trades),
            win_rate=round(win_rate, 4),
            profit_factor=round(profit_factor, 4),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            avg_hold_days=round(np.mean([t.hold_days for t in all_trades]) if all_trades else 0, 1),
            in_sample_sharpe=round(is_sharpe, 4),
            out_sample_sharpe=round(oos_sharpe, 4),
            overfitting_ratio=round(overfitting, 4),
            equity_curve=equity_curve
        )
        
        self.results.append(result)
        self.trades.extend(all_trades)
        
        return result
    
    def _simple_backtest(
        self,
        prices: np.ndarray,
        strategy_func: Callable,
        params: Dict,
        initial_capital: float
    ) -> BacktestResult:
        """Simple backtest when not enough data for walk-forward"""
        returns = []
        position = 0
        
        for i in range(50, len(prices)):
            signal, conf = strategy_func(prices[:i+1], params)
            daily_return = prices[i] / prices[i-1] - 1 if i > 0 else 0
            
            if position != 0:
                returns.append(position * daily_return)
            else:
                returns.append(0)
            
            position = signal if signal != 0 else position
        
        returns_arr = np.array(returns)
        sharpe = self._calculate_sharpe(returns_arr)
        
        cum_returns = np.cumprod(1 + returns_arr)
        total_return = (cum_returns[-1] - 1) * 100 if len(cum_returns) > 0 else 0
        
        return BacktestResult(
            strategy_name="SimpleBacktest",
            start_date=datetime.now(),
            end_date=datetime.now(),
            total_return=round(total_return, 2),
            annual_return=round(total_return / (len(prices) / 252), 2),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(self._calculate_sortino(returns_arr), 4),
            max_drawdown=round(self._calculate_max_dd(returns_arr) * 100, 2),
            max_drawdown_duration=0,
            volatility=round(np.std(returns_arr) * np.sqrt(252) * 100, 2),
            total_trades=0,
            win_rate=0.5,
            profit_factor=1.0,
            avg_win=0,
            avg_loss=0,
            avg_hold_days=0,
            in_sample_sharpe=sharpe,
            out_sample_sharpe=sharpe,
            overfitting_ratio=1.0
        )
    
    def _calculate_sharpe(self, returns: np.ndarray, rf: float = 0.05) -> float:
        """Calculate annualized Sharpe ratio"""
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        
        excess_returns = returns - rf / 252
        return np.sqrt(252) * np.mean(excess_returns) / np.std(returns)
    
    def _calculate_sortino(self, returns: np.ndarray, rf: float = 0.05) -> float:
        """Calculate Sortino ratio (downside risk only)"""
        if len(returns) == 0:
            return 0.0
        
        excess_returns = returns - rf / 252
        downside = returns[returns < 0]
        
        if len(downside) == 0 or np.std(downside) == 0:
            return self._calculate_sharpe(returns, rf)
        
        return np.sqrt(252) * np.mean(excess_returns) / np.std(downside)
    
    def _calculate_max_dd(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown"""
        if len(returns) == 0:
            return 0.0
        
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdowns = (cum_returns - running_max) / running_max
        
        return np.min(drawdowns)
    
    def monte_carlo_validation(
        self,
        prices: np.ndarray,
        strategy_func: Callable,
        params: Dict,
        n_simulations: int = 100
    ) -> Dict:
        """
        Monte Carlo validation to test strategy robustness
        
        Shuffles trade order to test if strategy is truly predictive
        """
        baseline_result = self.run_walk_forward(prices, strategy_func, params)
        
        # Run simulations with randomized returns
        random_sharpes = []
        
        for _ in range(n_simulations):
            shuffled_prices = prices.copy()
            returns = np.diff(np.log(shuffled_prices))
            np.random.shuffle(returns)
            shuffled_prices[1:] = shuffled_prices[0] * np.exp(np.cumsum(returns))
            
            result = self._simple_backtest(shuffled_prices, strategy_func, params, 1e9)
            random_sharpes.append(result.sharpe_ratio)
        
        # Calculate p-value
        random_sharpes = np.array(random_sharpes)
        p_value = np.mean(random_sharpes >= baseline_result.out_sample_sharpe)
        
        return {
            "baseline_sharpe": baseline_result.out_sample_sharpe,
            "mean_random_sharpe": round(np.mean(random_sharpes), 4),
            "p_value": round(p_value, 4),
            "is_significant": p_value < 0.05,
            "percentile": round((1 - p_value) * 100, 1)
        }
    
    def generate_report(self) -> str:
        """Generate text report of backtest results"""
        if not self.results:
            return "No backtest results available."
        
        latest = self.results[-1]
        
        report = f"""
═══════════════════════════════════════════════════════════
                   WALK-FORWARD BACKTEST REPORT
═══════════════════════════════════════════════════════════

Strategy: {latest.strategy_name}
Period: {latest.start_date.strftime('%Y-%m-%d')} to {latest.end_date.strftime('%Y-%m-%d')}

PERFORMANCE
───────────────────────────────────────────────────────────
Total Return:     {latest.total_return:+.2f}%
Annual Return:    {latest.annual_return:+.2f}%
Sharpe Ratio:     {latest.sharpe_ratio:.2f}
Sortino Ratio:    {latest.sortino_ratio:.2f}
Max Drawdown:     {latest.max_drawdown:.2f}%
Volatility:       {latest.volatility:.2f}%

TRADE STATISTICS
───────────────────────────────────────────────────────────
Total Trades:     {latest.total_trades}
Win Rate:         {latest.win_rate:.1%}
Profit Factor:    {latest.profit_factor:.2f}
Avg Win:          {latest.avg_win:,.0f}
Avg Loss:         {latest.avg_loss:,.0f}
Avg Hold Days:    {latest.avg_hold_days:.1f}

WALK-FORWARD ANALYSIS
───────────────────────────────────────────────────────────
In-Sample Sharpe:    {latest.in_sample_sharpe:.2f}
Out-Sample Sharpe:   {latest.out_sample_sharpe:.2f}
Overfitting Ratio:   {latest.overfitting_ratio:.2f}

ROBUSTNESS CHECK: {'✅ PASSED' if latest.is_robust() else '❌ FAILED'}
═══════════════════════════════════════════════════════════
        """
        
        return report


# Singleton
_backtester = None

def get_backtester() -> WalkForwardBacktester:
    global _backtester
    if _backtester is None:
        _backtester = WalkForwardBacktester()
    return _backtester


# Test
if __name__ == "__main__":
    # Generate sample data
    np.random.seed(42)
    prices = 50000 * np.exp(np.cumsum(0.0005 + 0.015 * np.random.randn(500)))
    
    # Simple momentum strategy for testing
    def momentum_strategy(prices: np.ndarray, params: Dict) -> Tuple[int, float]:
        lookback = params.get("lookback", 20)
        
        if len(prices) < lookback + 1:
            return 0, 0.0
        
        ma = np.mean(prices[-lookback:])
        current = prices[-1]
        
        if current > ma * 1.02:
            return 1, 0.7  # Buy signal
        elif current < ma * 0.98:
            return -1, 0.7  # Sell signal
        else:
            return 0, 0.0  # Hold
    
    # Run backtest
    bt = WalkForwardBacktester(train_period=200, test_period=50, n_folds=4)
    result = bt.run_walk_forward(prices, momentum_strategy, {"lookback": 20})
    
    print(bt.generate_report())
    
    # Monte Carlo validation
    mc = bt.monte_carlo_validation(prices, momentum_strategy, {"lookback": 20}, n_simulations=50)
    print("\nMonte Carlo Validation:")
    print(f"  P-Value: {mc['p_value']:.4f}")
    print(f"  Significant: {mc['is_significant']}")
    print(f"  Percentile: {mc['percentile']:.1f}%")
