# -*- coding: utf-8 -*-
"""
Walk-Forward Backtesting Engine for VN-QUANT
=============================================
Professional backtesting with out-of-sample validation.

Features:
- Walk-forward optimization
- Monte Carlo simulation
- Overfitting detection
- Risk metrics calculation
- Trade-by-trade analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    initial_capital: float = 100_000_000  # 100M VND
    commission: float = 0.0015  # 0.15%
    slippage: float = 0.001  # 0.1%
    tax: float = 0.001  # 0.1% on sells

    # Walk-forward parameters
    train_window: int = 180  # 6 months
    test_window: int = 30  # 1 month
    step_size: int = 30  # Roll forward 1 month

    # Risk parameters
    max_position_pct: float = 0.15
    max_positions: int = 10
    stop_loss_pct: float = 0.07
    take_profit_pct: float = 0.15


@dataclass
class Trade:
    """Single trade record"""
    symbol: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    quantity: int = 0
    direction: str = "LONG"  # LONG or SHORT

    # P&L
    pnl: float = 0.0
    pnl_pct: float = 0.0

    # Fees
    commission_entry: float = 0.0
    commission_exit: float = 0.0
    tax: float = 0.0
    total_fees: float = 0.0

    # Metadata
    signal_strength: float = 0.0
    strategy: str = ""


@dataclass
class BacktestResult:
    """Backtest results"""
    # Equity curve
    equity_curve: pd.Series

    # Trades
    trades: List[Trade]

    # Metrics
    total_return: float
    annual_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    expectancy: float

    # Risk metrics
    value_at_risk_95: float  # 95% VaR
    conditional_var_95: float  # 95% CVaR
    calmar_ratio: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_holding_days: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Performance per year
    yearly_returns: Dict[int, float] = field(default_factory=dict)

    # Monte Carlo stats
    monte_carlo_sharpe: Optional[float] = None
    monte_carlo_confidence: Optional[float] = None


class BacktestEngine:
    """
    Walk-forward backtesting engine

    Process:
    1. Split data into train/test windows
    2. Train strategy on train window
    3. Test on test window (out-of-sample)
    4. Roll forward and repeat
    5. Aggregate results
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run_backtest(
        self,
        data: pd.DataFrame,
        strategy_func: Callable,
        symbol: str = ""
    ) -> BacktestResult:
        """
        Run walk-forward backtest

        Args:
            data: OHLCV dataframe
            strategy_func: Function that generates signals
            symbol: Stock symbol

        Returns:
            BacktestResult
        """
        logger.info(f"Starting backtest for {symbol}")

        # Initialize
        trades = []
        equity = [self.config.initial_capital]
        current_capital = self.config.initial_capital
        positions = {}  # symbol -> Trade

        # Walk-forward loop
        for train_start, train_end, test_start, test_end in self._walk_forward_windows(data):
            # Train strategy on train window
            train_data = data.loc[train_start:train_end]
            test_data = data.loc[test_start:test_end]

            logger.info(f"Train: {train_start} to {train_end}, Test: {test_start} to {test_end}")

            # Train (this would optimize strategy parameters)
            strategy_params = self._train_strategy(train_data, strategy_func)

            # Test (generate signals and execute)
            for date, row in test_data.iterrows():
                # Generate signal
                signal = strategy_func(test_data.loc[:date], **strategy_params)

                # Check current positions
                for sym, trade in list(positions.items()):
                    # Update P&L
                    trade.pnl = (row['close'] - trade.entry_price) * trade.quantity
                    trade.pnl_pct = (row['close'] / trade.entry_price - 1) * 100

                    # Check stop loss / take profit
                    if trade.pnl_pct <= -self.config.stop_loss_pct * 100:
                        # Stop loss
                        self._close_position(trade, date, row['close'], "STOP_LOSS")
                        trades.append(trade)
                        del positions[sym]

                    elif trade.pnl_pct >= self.config.take_profit_pct * 100:
                        # Take profit
                        self._close_position(trade, date, row['close'], "TAKE_PROFIT")
                        trades.append(trade)
                        del positions[sym]

                # Process new signal
                if signal == "BUY" and symbol not in positions and len(positions) < self.config.max_positions:
                    # Open long position
                    position_size = current_capital * self.config.max_position_pct
                    quantity = int(position_size / row['close'] / 100) * 100  # Round to lot size

                    if quantity > 0:
                        trade = Trade(
                            symbol=symbol,
                            entry_date=date,
                            entry_price=row['close'],
                            quantity=quantity,
                            direction="LONG"
                        )

                        # Calculate fees
                        trade.commission_entry = trade.entry_price * trade.quantity * self.config.commission
                        trade.total_fees = trade.commission_entry

                        positions[symbol] = trade

                elif signal == "SELL" and symbol in positions:
                    # Close position
                    trade = positions[symbol]
                    self._close_position(trade, date, row['close'], "SIGNAL")
                    trades.append(trade)
                    del positions[symbol]

                # Update equity
                unrealized_pnl = sum(t.pnl for t in positions.values())
                realized_pnl = sum(t.pnl for t in trades)
                current_equity = self.config.initial_capital + realized_pnl + unrealized_pnl

                equity.append(current_equity)

        # Close remaining positions at end
        last_date = data.index[-1]
        last_price = data.iloc[-1]['close']

        for trade in positions.values():
            self._close_position(trade, last_date, last_price, "END")
            trades.append(trade)

        # Calculate metrics
        equity_curve = pd.Series(equity, index=data.index[:len(equity)])
        result = self._calculate_metrics(equity_curve, trades)

        logger.info(f"Backtest complete: Return={result.total_return:.2%}, Sharpe={result.sharpe_ratio:.2f}")

        return result

    def _walk_forward_windows(
        self,
        data: pd.DataFrame
    ) -> List[Tuple[datetime, datetime, datetime, datetime]]:
        """Generate walk-forward windows"""
        windows = []

        start_date = data.index[0]
        end_date = data.index[-1]

        current_date = start_date

        while current_date + timedelta(days=self.config.train_window + self.config.test_window) <= end_date:
            train_start = current_date
            train_end = current_date + timedelta(days=self.config.train_window)
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=self.config.test_window)

            windows.append((train_start, train_end, test_start, test_end))

            current_date += timedelta(days=self.config.step_size)

        return windows

    def _train_strategy(
        self,
        data: pd.DataFrame,
        strategy_func: Callable
    ) -> Dict:
        """Train strategy (optimize parameters)"""
        # For now, return default params
        # TODO: Implement hyperparameter optimization
        return {}

    def _close_position(
        self,
        trade: Trade,
        exit_date: datetime,
        exit_price: float,
        reason: str
    ):
        """Close a position"""
        trade.exit_date = exit_date
        trade.exit_price = exit_price

        # Calculate P&L
        trade.pnl = (exit_price - trade.entry_price) * trade.quantity

        # Fees
        trade.commission_exit = exit_price * trade.quantity * self.config.commission
        trade.tax = exit_price * trade.quantity * self.config.tax
        trade.total_fees = trade.commission_entry + trade.commission_exit + trade.tax

        # Net P&L
        trade.pnl -= trade.total_fees
        trade.pnl_pct = trade.pnl / (trade.entry_price * trade.quantity) * 100

    def _calculate_metrics(
        self,
        equity_curve: pd.Series,
        trades: List[Trade]
    ) -> BacktestResult:
        """Calculate performance metrics"""

        # Returns
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100

        # Annual return
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        annual_return = ((equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (365 / days) - 1) * 100

        # Daily returns
        returns = equity_curve.pct_change().dropna()

        # Sharpe ratio (annualized)
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0

        # Sortino ratio (only downside volatility)
        downside = returns[returns < 0]
        sortino = (returns.mean() / downside.std()) * np.sqrt(252) if len(downside) > 0 else 0

        # Max drawdown
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax * 100
        max_dd = drawdown.min()

        # Max DD duration
        dd_duration = self._max_drawdown_duration(drawdown)

        # Trade statistics
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]

        win_rate = len(winning_trades) / len(trades) * 100 if len(trades) > 0 else 0

        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0

        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        expectancy = (win_rate / 100) * avg_win + ((100 - win_rate) / 100) * avg_loss

        # VaR and CVaR
        var_95 = np.percentile(returns, 5) * equity_curve.iloc[-1]
        cvar_95 = returns[returns <= np.percentile(returns, 5)].mean() * equity_curve.iloc[-1]

        # Calmar ratio
        calmar = annual_return / abs(max_dd) if max_dd != 0 else 0

        # Holding days
        holding_days = [
            (t.exit_date - t.entry_date).days
            for t in trades if t.exit_date
        ]
        avg_holding = np.mean(holding_days) if holding_days else 0

        # Consecutive wins/losses
        max_consec_wins = self._max_consecutive(trades, win=True)
        max_consec_losses = self._max_consecutive(trades, win=False)

        # Yearly returns
        yearly = equity_curve.resample('Y').last().pct_change() * 100
        yearly_returns = yearly.to_dict()

        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades,
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_duration=dd_duration,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            expectancy=expectancy,
            value_at_risk_95=var_95,
            conditional_var_95=cvar_95,
            calmar_ratio=calmar,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_holding_days=avg_holding,
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            yearly_returns=yearly_returns
        )

    def _max_drawdown_duration(self, drawdown: pd.Series) -> int:
        """Calculate max drawdown duration in days"""
        is_dd = drawdown < 0
        dd_periods = (is_dd != is_dd.shift()).cumsum()
        durations = drawdown.groupby(dd_periods).count()
        return durations.max() if len(durations) > 0 else 0

    def _max_consecutive(self, trades: List[Trade], win: bool) -> int:
        """Calculate max consecutive wins or losses"""
        current_streak = 0
        max_streak = 0

        for trade in trades:
            if (win and trade.pnl > 0) or (not win and trade.pnl < 0):
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        return max_streak


def run_monte_carlo_simulation(
    backtest_result: BacktestResult,
    num_simulations: int = 1000
) -> Dict:
    """
    Run Monte Carlo simulation on backtest results

    Randomly reorder trades to test robustness
    """
    trades = backtest_result.trades
    initial_capital = backtest_result.equity_curve.iloc[0]

    sharpe_ratios = []
    final_returns = []

    for _ in range(num_simulations):
        # Shuffle trades
        shuffled = trades.copy()
        np.random.shuffle(shuffled)

        # Simulate equity curve
        equity = initial_capital
        equities = [equity]

        for trade in shuffled:
            equity += trade.pnl
            equities.append(equity)

        equity_series = pd.Series(equities)
        returns = equity_series.pct_change().dropna()

        # Calculate metrics
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        final_return = (equity / initial_capital - 1) * 100

        sharpe_ratios.append(sharpe)
        final_returns.append(final_return)

    return {
        "mean_sharpe": np.mean(sharpe_ratios),
        "std_sharpe": np.std(sharpe_ratios),
        "mean_return": np.mean(final_returns),
        "std_return": np.std(final_returns),
        "5th_percentile_return": np.percentile(final_returns, 5),
        "95th_percentile_return": np.percentile(final_returns, 95)
    }


__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "Trade",
    "run_monte_carlo_simulation"
]
