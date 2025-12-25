"""
Quantum Core AI Engine
Central orchestration of all analysis components
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from .backtest_engine import (
    BacktestEngine, BacktestResult, Strategy,
    MACrossoverStrategy, RSIReversalStrategy, MACDStrategy, BollingerBreakoutStrategy
)
from .monte_carlo import MonteCarloSimulator, SimulationResult
from .kelly_criterion import KellyCriterion, PositionSizeResult
from .walk_forward import WalkForwardOptimizer, WFOResult


@dataclass
class QuantumAnalysis:
    """Comprehensive analysis result from Quantum Core"""
    symbol: str
    timestamp: datetime
    current_price: float

    # Backtest results
    backtest_result: Optional[BacktestResult] = None
    strategy_comparison: Optional[pd.DataFrame] = None

    # Monte Carlo simulation
    monte_carlo: Optional[SimulationResult] = None

    # Position sizing
    kelly_result: Optional[PositionSizeResult] = None

    # Walk-forward validation
    wfo_result: Optional[WFOResult] = None

    # Combined signals
    technical_score: float = 50.0
    risk_score: int = 50
    confidence: float = 50.0

    # Entry/Exit levels
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward_ratio: float = 0.0

    # Recommendation
    signal: str = "HOLD"  # BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL
    recommendation: str = ""

    # AI interpretation
    ai_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'current_price': self.current_price,
            'technical_score': self.technical_score,
            'risk_score': self.risk_score,
            'confidence': self.confidence,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'risk_reward_ratio': self.risk_reward_ratio,
            'signal': self.signal,
            'recommendation': self.recommendation,
            'backtest': self.backtest_result.to_dict() if self.backtest_result else None,
            'monte_carlo': self.monte_carlo.to_dict() if self.monte_carlo else None,
            'kelly': self.kelly_result.to_dict() if self.kelly_result else None,
            'wfo': self.wfo_result.to_dict() if self.wfo_result else None
        }


class QuantumEngine:
    """
    Quantum Core AI - Main analysis engine
    Combines backtesting, Monte Carlo, Kelly criterion, and walk-forward analysis
    """

    def __init__(self, portfolio_value: float = 100000000,
                 commission_rate: float = 0.0015):
        """
        Args:
            portfolio_value: Portfolio value in VND
            commission_rate: Commission rate per trade
        """
        self.portfolio_value = portfolio_value
        self.commission_rate = commission_rate

        # Initialize components
        self.backtest_engine = BacktestEngine(
            initial_capital=portfolio_value,
            commission_rate=commission_rate
        )
        self.monte_carlo = MonteCarloSimulator(num_simulations=10000)
        self.kelly = KellyCriterion(portfolio_value=portfolio_value)
        self.wfo = WalkForwardOptimizer(self.backtest_engine)

        # Available strategies
        self.strategies = {
            'MA_CROSSOVER': MACrossoverStrategy,
            'RSI_REVERSAL': RSIReversalStrategy,
            'MACD': MACDStrategy,
            'BB_BREAKOUT': BollingerBreakoutStrategy
        }

        # Default parameter grids
        self.param_grids = {
            'MA_CROSSOVER': {
                'fast_period': [5, 10, 20],
                'slow_period': [20, 50, 100]
            },
            'RSI_REVERSAL': {
                'period': [7, 14, 21],
                'oversold': [25, 30, 35],
                'overbought': [65, 70, 75]
            },
            'MACD': {
                'fast': [8, 12, 16],
                'slow': [21, 26, 30],
                'signal': [7, 9, 12]
            },
            'BB_BREAKOUT': {
                'period': [15, 20, 25],
                'std_dev': [1.5, 2.0, 2.5]
            }
        }

    def set_portfolio_value(self, value: float):
        """Update portfolio value"""
        self.portfolio_value = value
        self.backtest_engine.initial_capital = value
        self.kelly.portfolio_value = value

    async def full_analysis(self, df: pd.DataFrame, symbol: str,
                           strategy_type: str = "MA_CROSSOVER",
                           forecast_days: int = 10,
                           leverage: float = 1.0,
                           run_wfo: bool = True) -> QuantumAnalysis:
        """
        Run comprehensive analysis on a stock

        Args:
            df: Historical OHLCV data
            symbol: Stock symbol
            strategy_type: Strategy to analyze
            forecast_days: Days to forecast in Monte Carlo
            leverage: Trading leverage
            run_wfo: Whether to run walk-forward optimization

        Returns:
            QuantumAnalysis with all results
        """
        current_price = df['close'].iloc[-1]

        result = QuantumAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=current_price
        )

        # 1. Run backtest with default parameters
        strategy_class = self.strategies.get(strategy_type)
        if strategy_class:
            strategy = strategy_class()
            result.backtest_result = self.backtest_engine.run(df, strategy, symbol)

        # 2. Compare all strategies
        all_strategies = [
            MACrossoverStrategy(10, 50),
            RSIReversalStrategy(14, 30, 70),
            MACDStrategy(12, 26, 9),
            BollingerBreakoutStrategy(20, 2.0)
        ]
        result.strategy_comparison = self.backtest_engine.compare_strategies(
            df, all_strategies, symbol
        )

        # 3. Monte Carlo simulation
        result.monte_carlo = self.monte_carlo.simulate(
            df, symbol, forecast_days, leverage,
            strategy_name=f"Long {leverage}x"
        )

        # 4. Calculate entry/exit levels
        atr = self._calculate_atr(df)
        result.entry_price = current_price
        result.stop_loss = current_price - (2 * atr)
        result.take_profit = current_price + (3 * atr)

        if current_price > result.stop_loss:
            result.risk_reward_ratio = (result.take_profit - current_price) / (current_price - result.stop_loss)
        else:
            result.risk_reward_ratio = 0

        # 5. Kelly criterion
        win_rate = result.backtest_result.win_rate / 100 if result.backtest_result else 0.5
        result.kelly_result = self.kelly.calculate(
            entry_price=result.entry_price,
            stop_loss=result.stop_loss,
            take_profit=result.take_profit,
            win_rate=win_rate
        )

        # 6. Walk-forward optimization (optional, computationally intensive)
        if run_wfo and strategy_class and len(df) > 200:
            param_grid = self.param_grids.get(strategy_type, {})
            if param_grid:
                result.wfo_result = self.wfo.optimize(
                    df, strategy_class, param_grid, symbol, num_folds=3
                )

        # 7. Calculate combined scores
        result.technical_score = self._calculate_technical_score(df, result.backtest_result)
        result.risk_score = result.monte_carlo.risk_score if result.monte_carlo else 50
        result.confidence = self._calculate_confidence(result)

        # 8. Generate signal and recommendation
        result.signal = self._generate_signal(result)
        result.recommendation = self._generate_recommendation(result)
        result.ai_summary = self._generate_ai_summary(result)

        return result

    def quick_backtest(self, df: pd.DataFrame, symbol: str,
                       strategy_type: str = "MA_CROSSOVER",
                       **strategy_params) -> BacktestResult:
        """Quick backtest with a single strategy"""
        strategy_class = self.strategies.get(strategy_type)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {strategy_type}")

        strategy = strategy_class(**strategy_params) if strategy_params else strategy_class()
        return self.backtest_engine.run(df, strategy, symbol)

    def optimize_strategy(self, df: pd.DataFrame, symbol: str,
                         strategy_type: str = "MA_CROSSOVER",
                         metric: str = "sharpe_ratio") -> Tuple[Dict, BacktestResult]:
        """Optimize strategy parameters"""
        strategy_class = self.strategies.get(strategy_type)
        param_grid = self.param_grids.get(strategy_type, {})

        if not strategy_class or not param_grid:
            raise ValueError(f"Cannot optimize strategy: {strategy_type}")

        return self.backtest_engine.optimize_parameters(
            df, strategy_class, param_grid, symbol, metric
        )

    def run_monte_carlo(self, df: pd.DataFrame, symbol: str,
                       days: int = 10, leverage: float = 1.0,
                       simulations: int = 10000) -> SimulationResult:
        """Run Monte Carlo simulation"""
        self.monte_carlo.num_simulations = simulations
        return self.monte_carlo.simulate(df, symbol, days, leverage)

    def calculate_position_size(self, entry: float, stop_loss: float,
                               take_profit: float, win_rate: float = None) -> PositionSizeResult:
        """Calculate optimal position size"""
        return self.kelly.calculate(entry, stop_loss, take_profit, win_rate)

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]

        return atr

    def _calculate_technical_score(self, df: pd.DataFrame,
                                  backtest: BacktestResult = None) -> float:
        """Calculate technical score 0-100"""
        score = 50

        # Price vs EMA20
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        if df['close'].iloc[-1] > ema20:
            score += 10
        else:
            score -= 10

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        if rsi < 30:
            score += 20  # Oversold
        elif rsi > 70:
            score -= 20  # Overbought
        elif 40 <= rsi <= 60:
            score += 5  # Neutral

        # Backtest performance
        if backtest:
            if backtest.sharpe_ratio > 1:
                score += 15
            elif backtest.sharpe_ratio > 0.5:
                score += 10
            elif backtest.sharpe_ratio < 0:
                score -= 15

            if backtest.profit_factor > 1.5:
                score += 10
            elif backtest.profit_factor < 1:
                score -= 10

        return max(0, min(100, score))

    def _calculate_confidence(self, result: QuantumAnalysis) -> float:
        """Calculate overall confidence score"""
        scores = []

        # Technical score contribution
        scores.append(result.technical_score)

        # Monte Carlo contribution
        if result.monte_carlo:
            scores.append(result.monte_carlo.prob_profit)

        # Backtest contribution
        if result.backtest_result:
            scores.append(min(100, result.backtest_result.sharpe_ratio * 30 + 50))

        # WFO contribution
        if result.wfo_result:
            scores.append(result.wfo_result.consistency_score)

        return np.mean(scores) if scores else 50

    def _generate_signal(self, result: QuantumAnalysis) -> str:
        """Generate trading signal"""
        if result.confidence >= 75 and result.risk_score < 40:
            return "STRONG_BUY"
        elif result.confidence >= 60 and result.risk_score < 50:
            return "BUY"
        elif result.confidence <= 30 or result.risk_score >= 70:
            return "SELL"
        elif result.confidence <= 40 and result.risk_score >= 60:
            return "STRONG_SELL"
        else:
            return "HOLD"

    def _generate_recommendation(self, result: QuantumAnalysis) -> str:
        """Generate recommendation text"""
        if result.signal in ["STRONG_BUY", "BUY"]:
            action = "NÊN MỞ VỊ THẾ" if result.signal == "STRONG_BUY" else "CÓ THỂ MỞ VỊ THẾ"
            return f"""
TÍN HIỆU TÍCH CỰC: {action}

Entry: {result.entry_price:,.0f}
Stop Loss: {result.stop_loss:,.0f} ({(result.entry_price - result.stop_loss) / result.entry_price * 100:.1f}%)
Take Profit: {result.take_profit:,.0f} ({(result.take_profit - result.entry_price) / result.entry_price * 100:.1f}%)
R:R Ratio: 1:{result.risk_reward_ratio:.1f}

Position Size: {result.kelly_result.recommended_shares if result.kelly_result else 0:,} cổ
Max Risk: {int(result.kelly_result.max_loss_amount) if result.kelly_result else 0:,} VND
"""
        elif result.signal in ["STRONG_SELL", "SELL"]:
            return f"⚠️ TÍN HIỆU TIÊU CỰC - Không nên mở vị thế mới. Risk Score: {result.risk_score}/100"
        else:
            return f"TRUNG LẬP - Chờ đợi tín hiệu rõ ràng hơn. Confidence: {result.confidence:.0f}%"

    def _generate_ai_summary(self, result: QuantumAnalysis) -> str:
        """Generate AI summary"""
        parts = []

        # Backtest insight
        if result.backtest_result:
            bt = result.backtest_result
            parts.append(f"Backtest {bt.strategy_name}: Lợi nhuận {bt.total_return_pct:.1f}%, "
                        f"Sharpe {bt.sharpe_ratio:.2f}, MaxDD {bt.max_drawdown_pct:.1f}%")

        # Monte Carlo insight
        if result.monte_carlo:
            mc = result.monte_carlo
            parts.append(f"Monte Carlo T+{mc.forecast_days}: Xác suất lời {mc.prob_profit:.0f}%, "
                        f"VaR 95%: {mc.var_95:.1f}%")

        # WFO insight
        if result.wfo_result:
            wfo = result.wfo_result
            robustness = "ROBUST" if wfo.consistency_score >= 70 else "WEAK"
            parts.append(f"Walk-Forward: {robustness} (Consistency {wfo.consistency_score:.0f}%)")

        # Kelly insight
        if result.kelly_result:
            k = result.kelly_result
            parts.append(f"Kelly khuyến nghị: {k.recommended_fraction*100:.1f}% NAV "
                        f"({k.recommended_shares:,} cổ)")

        return "\n".join(parts)

    def get_strategy_list(self) -> List[str]:
        """Get list of available strategies"""
        return list(self.strategies.keys())

    def get_param_grid(self, strategy_type: str) -> Dict[str, List]:
        """Get parameter grid for a strategy"""
        return self.param_grids.get(strategy_type, {})
