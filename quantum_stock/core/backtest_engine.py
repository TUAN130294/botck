"""
Advanced Backtesting Engine
Supports multiple strategies, walk-forward optimization, and comprehensive metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import warnings
warnings.filterwarnings('ignore')


class StrategyType(Enum):
    """Pre-built strategy types"""
    MA_CROSSOVER = "MA_CROSSOVER"
    RSI_REVERSAL = "RSI_REVERSAL"
    MACD_SIGNAL = "MACD_SIGNAL"
    BOLLINGER_BREAKOUT = "BOLLINGER_BREAKOUT"
    VWAP_BOUNCE = "VWAP_BOUNCE"
    COMBINED = "COMBINED"
    CUSTOM = "CUSTOM"


@dataclass
class Trade:
    """Single trade record"""
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    shares: int = 100
    side: str = "LONG"  # LONG or SHORT
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    exit_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def close(self, exit_date: datetime, exit_price: float, reason: str = ""):
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = reason

        if self.side == "LONG":
            self.pnl = (exit_price - self.entry_price) * self.shares
            self.pnl_pct = ((exit_price / self.entry_price) - 1) * 100
        else:
            self.pnl = (self.entry_price - exit_price) * self.shares
            self.pnl_pct = ((self.entry_price / exit_price) - 1) * 100

        self.holding_days = (exit_date - self.entry_date).days


@dataclass
class BacktestResult:
    """Comprehensive backtest results"""
    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime

    # Performance metrics
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0

    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_holding_days: float = 0.0

    # Advanced metrics
    expectancy: float = 0.0
    recovery_factor: float = 0.0
    ulcer_index: float = 0.0
    sqn: float = 0.0  # System Quality Number

    # Overfitting metrics
    psr: float = 0.0  # Probabilistic Sharpe Ratio
    dsr: float = 0.0  # Deflated Sharpe Ratio

    # Data
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    returns_series: List[float] = field(default_factory=list)

    # Configuration
    initial_capital: float = 100000000  # 100M VND
    commission_rate: float = 0.0015  # 0.15%
    slippage: float = 0.001  # 0.1%

    def to_dict(self) -> Dict[str, Any]:
        return {
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'total_return': self.total_return,
            'total_return_pct': self.total_return_pct,
            'annualized_return': self.annualized_return,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'volatility': self.volatility,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'expectancy': self.expectancy,
            'sqn': self.sqn,
            'psr': self.psr
        }

    def get_summary(self) -> str:
        """Get human-readable summary"""
        return f"""
Kết quả Backtest: {self.strategy_name} trên {self.symbol}
{'='*50}
Lợi nhuận: {self.total_return_pct:.1f}% | MaxDD: {self.max_drawdown_pct:.1f}%
Sharpe: {self.sharpe_ratio:.2f} | Sortino: {self.sortino_ratio:.2f}
Win Rate: {self.win_rate:.1f}% | Profit Factor: {self.profit_factor:.2f}
Số lệnh: {self.total_trades} | Thắng: {self.winning_trades} | Thua: {self.losing_trades}
SQN: {self.sqn:.2f} | Expectancy: {self.expectancy:,.0f} VND
{'='*50}
"""


class Strategy:
    """Base strategy class"""

    def __init__(self, name: str, strategy_type: StrategyType, params: Dict[str, Any] = None):
        self.name = name
        self.strategy_type = strategy_type
        self.params = params or {}

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate buy/sell signals. Returns DataFrame with 'signal' column."""
        raise NotImplementedError


class MACrossoverStrategy(Strategy):
    """Moving Average Crossover Strategy"""

    def __init__(self, fast_period: int = 10, slow_period: int = 50):
        super().__init__(
            name=f"MA_CROSSOVER({fast_period},{slow_period})",
            strategy_type=StrategyType.MA_CROSSOVER,
            params={'fast_period': fast_period, 'slow_period': slow_period}
        )
        self.fast_period = fast_period
        self.slow_period = slow_period

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Calculate MAs
        df['ma_fast'] = df['close'].ewm(span=self.fast_period, adjust=False).mean()
        df['ma_slow'] = df['close'].ewm(span=self.slow_period, adjust=False).mean()

        # Generate signals
        df['signal'] = 0
        df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1  # Buy
        df.loc[df['ma_fast'] < df['ma_slow'], 'signal'] = -1  # Sell

        # Only signal on crossover
        df['signal_change'] = df['signal'].diff()
        df['trade_signal'] = 0
        df.loc[df['signal_change'] == 2, 'trade_signal'] = 1  # Buy signal
        df.loc[df['signal_change'] == -2, 'trade_signal'] = -1  # Sell signal

        return df


class RSIReversalStrategy(Strategy):
    """RSI Mean Reversion Strategy"""

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(
            name=f"RSI_REVERSAL({period},{oversold},{overbought})",
            strategy_type=StrategyType.RSI_REVERSAL,
            params={'period': period, 'oversold': oversold, 'overbought': overbought}
        )
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Generate signals
        df['signal'] = 0
        df['trade_signal'] = 0

        # Buy when RSI crosses above oversold
        df.loc[(df['rsi'] > self.oversold) & (df['rsi'].shift(1) <= self.oversold), 'trade_signal'] = 1

        # Sell when RSI crosses below overbought
        df.loc[(df['rsi'] < self.overbought) & (df['rsi'].shift(1) >= self.overbought), 'trade_signal'] = -1

        return df


class MACDStrategy(Strategy):
    """MACD Signal Line Crossover"""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        super().__init__(
            name=f"MACD({fast},{slow},{signal})",
            strategy_type=StrategyType.MACD_SIGNAL,
            params={'fast': fast, 'slow': slow, 'signal': signal}
        )
        self.fast = fast
        self.slow = slow
        self.signal_period = signal

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Calculate MACD
        ema_fast = df['close'].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.slow, adjust=False).mean()
        df['macd'] = ema_fast - ema_slow
        df['macd_signal'] = df['macd'].ewm(span=self.signal_period, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # Generate signals
        df['trade_signal'] = 0
        df.loc[(df['macd'] > df['macd_signal']) &
               (df['macd'].shift(1) <= df['macd_signal'].shift(1)), 'trade_signal'] = 1
        df.loc[(df['macd'] < df['macd_signal']) &
               (df['macd'].shift(1) >= df['macd_signal'].shift(1)), 'trade_signal'] = -1

        return df


class BollingerBreakoutStrategy(Strategy):
    """Bollinger Bands Breakout Strategy"""

    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__(
            name=f"BB_BREAKOUT({period},{std_dev})",
            strategy_type=StrategyType.BOLLINGER_BREAKOUT,
            params={'period': period, 'std_dev': std_dev}
        )
        self.period = period
        self.std_dev = std_dev

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Calculate Bollinger Bands
        df['bb_mid'] = df['close'].rolling(window=self.period).mean()
        df['bb_std'] = df['close'].rolling(window=self.period).std()
        df['bb_upper'] = df['bb_mid'] + (df['bb_std'] * self.std_dev)
        df['bb_lower'] = df['bb_mid'] - (df['bb_std'] * self.std_dev)

        # Generate signals
        df['trade_signal'] = 0
        # Buy when price touches lower band
        df.loc[df['close'] <= df['bb_lower'], 'trade_signal'] = 1
        # Sell when price touches upper band
        df.loc[df['close'] >= df['bb_upper'], 'trade_signal'] = -1

        return df


class BacktestEngine:
    """
    Advanced Backtesting Engine with comprehensive metrics
    """

    def __init__(self, initial_capital: float = 100000000,
                 commission_rate: float = 0.0015,
                 slippage: float = 0.001):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.risk_free_rate = 0.05  # 5% annual risk-free rate (Vietnam)

    def run(self, df: pd.DataFrame, strategy: Strategy,
            symbol: str = "UNKNOWN",
            position_size: float = 1.0,
            stop_loss_pct: float = None,
            take_profit_pct: float = None) -> BacktestResult:
        """
        Run backtest on historical data

        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            strategy: Strategy instance
            symbol: Stock symbol
            position_size: Position size as fraction of capital (0-1)
            stop_loss_pct: Stop loss percentage (e.g., 0.05 for 5%)
            take_profit_pct: Take profit percentage
        """
        # Generate signals
        df = strategy.generate_signals(df)

        if 'trade_signal' not in df.columns:
            raise ValueError("Strategy must generate 'trade_signal' column")

        # Initialize tracking
        capital = self.initial_capital
        position = 0
        shares = 0
        entry_price = 0
        trades: List[Trade] = []
        equity_curve = [capital]
        current_trade = None

        # Iterate through data
        for i, row in df.iterrows():
            date = row.name if isinstance(row.name, datetime) else datetime.now()
            price = row['close']
            signal = row['trade_signal']

            # Check stop loss / take profit if in position
            if position != 0 and current_trade:
                if stop_loss_pct:
                    if position == 1:  # Long
                        sl_price = entry_price * (1 - stop_loss_pct)
                        if row['low'] <= sl_price:
                            exit_price = sl_price * (1 - self.slippage)
                            current_trade.close(date, exit_price, "STOP_LOSS")
                            trades.append(current_trade)
                            capital += current_trade.pnl - (exit_price * shares * self.commission_rate)
                            position = 0
                            shares = 0
                            current_trade = None
                            equity_curve.append(capital)
                            continue
                    else:  # Short
                        sl_price = entry_price * (1 + stop_loss_pct)
                        if row['high'] >= sl_price:
                            exit_price = sl_price * (1 + self.slippage)
                            current_trade.close(date, exit_price, "STOP_LOSS")
                            trades.append(current_trade)
                            capital += current_trade.pnl - (exit_price * shares * self.commission_rate)
                            position = 0
                            shares = 0
                            current_trade = None
                            equity_curve.append(capital)
                            continue

                if take_profit_pct:
                    if position == 1:  # Long
                        tp_price = entry_price * (1 + take_profit_pct)
                        if row['high'] >= tp_price:
                            exit_price = tp_price * (1 - self.slippage)
                            current_trade.close(date, exit_price, "TAKE_PROFIT")
                            trades.append(current_trade)
                            capital += current_trade.pnl - (exit_price * shares * self.commission_rate)
                            position = 0
                            shares = 0
                            current_trade = None
                            equity_curve.append(capital)
                            continue

            # Process signals
            if signal == 1 and position <= 0:  # Buy signal
                if position == -1:  # Close short first
                    exit_price = price * (1 + self.slippage)
                    current_trade.close(date, exit_price, "SIGNAL")
                    trades.append(current_trade)
                    capital += current_trade.pnl - (exit_price * shares * self.commission_rate)

                # Open long
                position_value = capital * position_size
                entry_price = price * (1 + self.slippage)
                shares = int(position_value / entry_price)
                if shares > 0:
                    position = 1
                    capital -= shares * entry_price * (1 + self.commission_rate)
                    current_trade = Trade(
                        entry_date=date,
                        entry_price=entry_price,
                        shares=shares,
                        side="LONG"
                    )

            elif signal == -1 and position >= 0:  # Sell signal
                if position == 1:  # Close long
                    exit_price = price * (1 - self.slippage)
                    current_trade.close(date, exit_price, "SIGNAL")
                    trades.append(current_trade)
                    capital += shares * exit_price * (1 - self.commission_rate)
                    position = 0
                    shares = 0
                    current_trade = None

            # Update equity curve
            if position == 1:
                equity = capital + (shares * price)
            elif position == -1:
                equity = capital + (shares * (entry_price - price))
            else:
                equity = capital
            equity_curve.append(equity)

        # Close any open position at end
        if current_trade and position != 0:
            final_price = df['close'].iloc[-1]
            current_trade.close(df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now(),
                              final_price, "END_OF_DATA")
            trades.append(current_trade)
            if position == 1:
                capital += shares * final_price * (1 - self.commission_rate)
            else:
                capital += shares * (entry_price - final_price) - (final_price * shares * self.commission_rate)

        # Calculate metrics
        result = self._calculate_metrics(
            trades=trades,
            equity_curve=equity_curve,
            strategy_name=strategy.name,
            symbol=symbol,
            start_date=df.index[0] if isinstance(df.index[0], datetime) else datetime.now(),
            end_date=df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now()
        )

        return result

    def _calculate_metrics(self, trades: List[Trade], equity_curve: List[float],
                          strategy_name: str, symbol: str,
                          start_date: datetime, end_date: datetime) -> BacktestResult:
        """Calculate comprehensive performance metrics"""

        result = BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            commission_rate=self.commission_rate,
            slippage=self.slippage,
            trades=trades,
            equity_curve=equity_curve
        )

        if not trades:
            return result

        # Basic returns
        final_equity = equity_curve[-1]
        result.total_return = final_equity - self.initial_capital
        result.total_return_pct = (result.total_return / self.initial_capital) * 100

        # Annualized return
        days = (end_date - start_date).days or 1
        years = days / 365
        if years > 0 and final_equity > 0:
            result.annualized_return = ((final_equity / self.initial_capital) ** (1/years) - 1) * 100

        # Drawdown calculation
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdown = equity_series - rolling_max
        drawdown_pct = (drawdown / rolling_max) * 100

        result.max_drawdown = abs(drawdown.min())
        result.max_drawdown_pct = abs(drawdown_pct.min())
        result.drawdown_curve = drawdown_pct.tolist()

        # Returns series
        returns = equity_series.pct_change().dropna()
        result.returns_series = returns.tolist()

        # Volatility (annualized)
        if len(returns) > 1:
            result.volatility = returns.std() * np.sqrt(252) * 100

        # Sharpe Ratio
        if result.volatility > 0:
            excess_return = result.annualized_return - (self.risk_free_rate * 100)
            result.sharpe_ratio = excess_return / result.volatility

        # Sortino Ratio (only downside volatility)
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 1:
            downside_vol = negative_returns.std() * np.sqrt(252) * 100
            if downside_vol > 0:
                result.sortino_ratio = (result.annualized_return - (self.risk_free_rate * 100)) / downside_vol

        # Calmar Ratio
        if result.max_drawdown_pct > 0:
            result.calmar_ratio = result.annualized_return / result.max_drawdown_pct

        # Trade statistics
        result.total_trades = len(trades)
        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = (result.winning_trades / result.total_trades * 100) if result.total_trades > 0 else 0

        if wins:
            result.avg_win = sum(wins) / len(wins)
            result.largest_win = max(wins)
        if losses:
            result.avg_loss = sum(losses) / len(losses)
            result.largest_loss = min(losses)

        # Profit Factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 1
        result.profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Expectancy
        if result.total_trades > 0:
            result.expectancy = sum(pnls) / result.total_trades

        # Average holding days
        holding_days = [t.holding_days for t in trades if t.holding_days > 0]
        if holding_days:
            result.avg_holding_days = sum(holding_days) / len(holding_days)

        # System Quality Number (SQN)
        if result.total_trades > 0 and len(pnls) > 1:
            pnl_std = np.std(pnls)
            if pnl_std > 0:
                result.sqn = (result.expectancy / pnl_std) * np.sqrt(result.total_trades)

        # Recovery Factor
        if result.max_drawdown > 0:
            result.recovery_factor = result.total_return / result.max_drawdown

        # Ulcer Index
        if len(drawdown_pct) > 0:
            result.ulcer_index = np.sqrt(np.mean(drawdown_pct ** 2))

        # Probabilistic Sharpe Ratio (simplified)
        if result.total_trades >= 30 and result.sharpe_ratio != 0:
            # Approximation of PSR
            skew = returns.skew() if len(returns) > 2 else 0
            kurt = returns.kurtosis() if len(returns) > 3 else 0
            sr_std = np.sqrt((1 + (0.5 * result.sharpe_ratio ** 2) - (skew * result.sharpe_ratio) +
                            ((kurt - 3) / 4 * result.sharpe_ratio ** 2)) / (result.total_trades - 1))
            if sr_std > 0:
                from scipy import stats
                result.psr = stats.norm.cdf(result.sharpe_ratio / sr_std) * 100

        return result

    def optimize_parameters(self, df: pd.DataFrame, strategy_class: type,
                           param_grid: Dict[str, List], symbol: str = "UNKNOWN",
                           metric: str = "sharpe_ratio") -> Tuple[Dict, BacktestResult]:
        """
        Grid search optimization for strategy parameters

        Args:
            df: Historical data
            strategy_class: Strategy class to optimize
            param_grid: Dict of parameter name -> list of values to test
            symbol: Stock symbol
            metric: Metric to optimize ('sharpe_ratio', 'total_return_pct', 'profit_factor')

        Returns:
            (best_params, best_result)
        """
        from itertools import product

        best_result = None
        best_params = None
        best_metric = float('-inf')

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for combination in product(*param_values):
            params = dict(zip(param_names, combination))

            try:
                strategy = strategy_class(**params)
                result = self.run(df, strategy, symbol)

                metric_value = getattr(result, metric, 0)
                if metric_value > best_metric:
                    best_metric = metric_value
                    best_result = result
                    best_params = params
            except Exception as e:
                continue

        return best_params, best_result

    def compare_strategies(self, df: pd.DataFrame, strategies: List[Strategy],
                          symbol: str = "UNKNOWN") -> pd.DataFrame:
        """Compare multiple strategies on same data"""
        results = []

        for strategy in strategies:
            try:
                result = self.run(df, strategy, symbol)
                results.append({
                    'Strategy': strategy.name,
                    'Return %': result.total_return_pct,
                    'MaxDD %': result.max_drawdown_pct,
                    'Sharpe': result.sharpe_ratio,
                    'Win Rate %': result.win_rate,
                    'Profit Factor': result.profit_factor,
                    'Trades': result.total_trades,
                    'SQN': result.sqn
                })
            except Exception as e:
                print(f"Error with {strategy.name}: {e}")

        return pd.DataFrame(results)
