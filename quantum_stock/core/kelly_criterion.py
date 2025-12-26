"""
Kelly Criterion Module for Optimal Position Sizing
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PositionSizeResult:
    """Position sizing calculation result"""
    kelly_fraction: float  # Full Kelly
    half_kelly: float  # Conservative approach
    quarter_kelly: float  # Very conservative

    # Dollar amounts (based on portfolio)
    kelly_amount: float
    half_kelly_amount: float
    quarter_kelly_amount: float

    # Shares (based on entry price)
    kelly_shares: int
    half_kelly_shares: int
    quarter_kelly_shares: int

    # Input parameters
    portfolio_value: float
    entry_price: float
    stop_loss: float
    take_profit: float
    win_rate: float
    win_loss_ratio: float

    # Risk metrics
    risk_per_trade: float
    risk_pct: float
    reward_pct: float
    risk_reward_ratio: float

    # Recommendations
    recommended_fraction: float
    recommended_amount: float
    recommended_shares: int
    max_loss_amount: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'kelly_fraction': self.kelly_fraction,
            'half_kelly': self.half_kelly,
            'quarter_kelly': self.quarter_kelly,
            'kelly_amount': self.kelly_amount,
            'half_kelly_amount': self.half_kelly_amount,
            'recommended_fraction': self.recommended_fraction,
            'recommended_shares': self.recommended_shares,
            'win_rate': self.win_rate,
            'risk_reward_ratio': self.risk_reward_ratio,
            'max_loss_amount': self.max_loss_amount
        }

    def get_summary(self) -> str:
        return f"""
CÔNG THỨC KELLY (Tối ưu vốn)
{'='*40}
Kelly Fraction: {self.kelly_fraction*100:.1f}%
Half Kelly (Khuyến nghị): {self.half_kelly*100:.1f}%

Với Portfolio {self.portfolio_value:,.0f} VND:
  - Full Kelly: {self.kelly_amount:,.0f} VND ({self.kelly_shares:,} cổ)
  - Half Kelly: {self.half_kelly_amount:,.0f} VND ({self.half_kelly_shares:,} cổ)

Thông số giao dịch:
  - Entry: {self.entry_price:,.0f}
  - Stop Loss: {self.stop_loss:,.0f} ({self.risk_pct:.1f}%)
  - Take Profit: {self.take_profit:,.0f} ({self.reward_pct:.1f}%)
  - R:R Ratio: 1:{self.risk_reward_ratio:.1f}

Win Rate ước tính: {self.win_rate*100:.0f}%
Max Loss (với Kelly): {self.max_loss_amount:,.0f} VND
{'='*40}
"""


class KellyCriterion:
    """
    Kelly Criterion calculator for optimal position sizing
    """

    def __init__(self, portfolio_value: float = 100000000,
                 max_position_pct: float = 0.25,
                 max_risk_per_trade: float = 0.02):
        """
        Args:
            portfolio_value: Total portfolio value in VND
            max_position_pct: Maximum single position size (default 25%)
            max_risk_per_trade: Maximum risk per trade (default 2%)
        """
        self.portfolio_value = portfolio_value
        self.max_position_pct = max_position_pct
        self.max_risk_per_trade = max_risk_per_trade

    def calculate(self, entry_price: float, stop_loss: float, take_profit: float,
                 win_rate: float = None, historical_trades: List[Dict] = None) -> PositionSizeResult:
        """
        Calculate optimal position size using Kelly Criterion

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            win_rate: Estimated win rate (0-1). If None, calculated from historical_trades
            historical_trades: List of past trades with 'pnl' key

        Returns:
            PositionSizeResult with all calculations
        """
        # Calculate risk and reward percentages
        if entry_price > stop_loss:  # Long position
            risk_pct = (entry_price - stop_loss) / entry_price
            reward_pct = (take_profit - entry_price) / entry_price
        else:  # Short position
            risk_pct = (stop_loss - entry_price) / entry_price
            reward_pct = (entry_price - take_profit) / entry_price

        risk_reward_ratio = reward_pct / risk_pct if risk_pct > 0 else 0

        # Calculate win rate from historical trades if provided
        if win_rate is None and historical_trades:
            wins = sum(1 for t in historical_trades if t.get('pnl', 0) > 0)
            win_rate = wins / len(historical_trades) if historical_trades else 0.5
        elif win_rate is None:
            # Estimate based on R:R ratio
            win_rate = self._estimate_win_rate(risk_reward_ratio)

        # Kelly Formula: f* = (p * b - q) / b
        # where: p = win probability, q = loss probability (1-p), b = win/loss ratio
        p = win_rate
        q = 1 - p
        b = risk_reward_ratio

        if b > 0:
            kelly = (p * b - q) / b
        else:
            kelly = 0

        # Ensure kelly is within bounds
        kelly = max(0, min(kelly, 1))

        # Apply safety margins
        half_kelly = kelly * 0.5
        quarter_kelly = kelly * 0.25

        # Cap at maximum position size
        kelly = min(kelly, self.max_position_pct)
        half_kelly = min(half_kelly, self.max_position_pct)
        quarter_kelly = min(quarter_kelly, self.max_position_pct)

        # Calculate amounts
        kelly_amount = self.portfolio_value * kelly
        half_kelly_amount = self.portfolio_value * half_kelly
        quarter_kelly_amount = self.portfolio_value * quarter_kelly

        # Calculate shares
        kelly_shares = int(kelly_amount / entry_price) if entry_price > 0 else 0
        half_kelly_shares = int(half_kelly_amount / entry_price) if entry_price > 0 else 0
        quarter_kelly_shares = int(quarter_kelly_amount / entry_price) if entry_price > 0 else 0

        # Risk-based position sizing (alternative check)
        risk_based_position = self._calculate_risk_based_position(
            entry_price, stop_loss, self.max_risk_per_trade
        )

        # Recommended: minimum of Kelly and risk-based
        recommended_fraction = min(half_kelly, risk_based_position / self.portfolio_value)
        recommended_amount = self.portfolio_value * recommended_fraction
        recommended_shares = int(recommended_amount / entry_price) if entry_price > 0 else 0

        # Max loss calculation
        max_loss_amount = kelly_amount * risk_pct

        return PositionSizeResult(
            kelly_fraction=kelly,
            half_kelly=half_kelly,
            quarter_kelly=quarter_kelly,
            kelly_amount=kelly_amount,
            half_kelly_amount=half_kelly_amount,
            quarter_kelly_amount=quarter_kelly_amount,
            kelly_shares=kelly_shares,
            half_kelly_shares=half_kelly_shares,
            quarter_kelly_shares=quarter_kelly_shares,
            portfolio_value=self.portfolio_value,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            win_rate=win_rate,
            win_loss_ratio=risk_reward_ratio,
            risk_per_trade=risk_pct,
            risk_pct=risk_pct * 100,
            reward_pct=reward_pct * 100,
            risk_reward_ratio=risk_reward_ratio,
            recommended_fraction=recommended_fraction,
            recommended_amount=recommended_amount,
            recommended_shares=recommended_shares,
            max_loss_amount=max_loss_amount
        )

    def _estimate_win_rate(self, risk_reward_ratio: float) -> float:
        """
        Estimate win rate based on R:R ratio
        Higher R:R typically means lower win rate needed for profitability
        """
        # Approximate based on common trading statistics
        if risk_reward_ratio >= 3:
            return 0.35  # High R:R, lower win rate OK
        elif risk_reward_ratio >= 2:
            return 0.45
        elif risk_reward_ratio >= 1.5:
            return 0.50
        elif risk_reward_ratio >= 1:
            return 0.55
        else:
            return 0.60

    def _calculate_risk_based_position(self, entry_price: float, stop_loss: float,
                                       risk_pct: float) -> float:
        """
        Calculate position size based on fixed risk percentage
        """
        risk_amount = self.portfolio_value * risk_pct
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share > 0:
            shares = risk_amount / risk_per_share
            position_value = shares * entry_price
            return position_value
        return 0

    def calculate_from_backtest(self, backtest_result: Any) -> PositionSizeResult:
        """
        Calculate Kelly from backtest results

        Args:
            backtest_result: BacktestResult object
        """
        win_rate = backtest_result.win_rate / 100
        avg_win = backtest_result.avg_win
        avg_loss = abs(backtest_result.avg_loss) if backtest_result.avg_loss else 1

        # Use last trade's parameters or defaults
        if backtest_result.trades:
            last_trade = backtest_result.trades[-1]
            entry_price = last_trade.entry_price
            # Estimate SL/TP from average win/loss
            stop_loss = entry_price * (1 - abs(avg_loss / (entry_price * 100)))
            take_profit = entry_price * (1 + avg_win / (entry_price * 100))
        else:
            entry_price = 100
            stop_loss = 95
            take_profit = 110

        return self.calculate(
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            win_rate=win_rate
        )

    def optimal_leverage(self, win_rate: float, risk_reward_ratio: float,
                        max_leverage: float = 5.0) -> Dict[str, Any]:
        """
        Calculate optimal leverage using Kelly

        Args:
            win_rate: Historical win rate
            risk_reward_ratio: Average win / average loss
            max_leverage: Maximum allowed leverage

        Returns:
            Dict with optimal leverage and expected growth
        """
        # Kelly for leverage: f* = (p * b - q) / b
        p = win_rate
        q = 1 - p
        b = risk_reward_ratio

        if b > 0:
            optimal_f = (p * b - q) / b
        else:
            optimal_f = 0

        # Convert to leverage (assuming 100% position = 1x leverage)
        optimal_leverage = min(optimal_f * 2, max_leverage)  # Cap at max

        # Calculate expected growth rate (geometric mean)
        # G = p * ln(1 + f*b) + q * ln(1 - f)
        f = optimal_f
        if f > 0 and f < 1:
            expected_growth = p * np.log(1 + f * b) + q * np.log(1 - f)
        else:
            expected_growth = 0

        # Calculate risk of ruin (simplified)
        if optimal_f > 0:
            risk_of_ruin = ((1 - win_rate) / win_rate) ** (1 / optimal_f)
        else:
            risk_of_ruin = 1

        return {
            'optimal_fraction': optimal_f,
            'optimal_leverage': optimal_leverage,
            'half_kelly_leverage': optimal_leverage * 0.5,
            'expected_growth_rate': expected_growth * 100,
            'risk_of_ruin': min(1, risk_of_ruin) * 100,
            'recommendation': self._leverage_recommendation(optimal_leverage)
        }

    def _leverage_recommendation(self, leverage: float) -> str:
        if leverage <= 0:
            return "KHÔNG NÊN GIAO DỊCH - Edge âm"
        elif leverage < 1:
            return "Giao dịch với size nhỏ hơn 100% vốn"
        elif leverage < 1.5:
            return "Giao dịch với 100% vốn, không dùng margin"
        elif leverage < 2:
            return "Có thể dùng margin 1.5x nếu tự tin"
        elif leverage < 3:
            return "Margin 2x có thể chấp nhận với risk management"
        else:
            return f"Kelly gợi ý {leverage:.1f}x nhưng khuyên dùng tối đa 2-3x"

    def calculate_compound_growth(self, kelly_fraction: float, win_rate: float,
                                  risk_reward_ratio: float, num_trades: int) -> Dict[str, Any]:
        """
        Calculate expected compound growth over multiple trades

        Returns expected portfolio growth with Kelly betting
        """
        # Simulate compound growth
        simulations = 10000
        final_values = []

        for _ in range(simulations):
            portfolio = 1.0  # Start with 1 unit

            for _ in range(num_trades):
                # Random outcome based on win rate
                if np.random.random() < win_rate:
                    # Win: gain = fraction * R
                    portfolio *= (1 + kelly_fraction * risk_reward_ratio)
                else:
                    # Loss: lose fraction
                    portfolio *= (1 - kelly_fraction)

            final_values.append(portfolio)

        final_values = np.array(final_values)

        return {
            'median_growth': (np.median(final_values) - 1) * 100,
            'mean_growth': (np.mean(final_values) - 1) * 100,
            'percentile_5': (np.percentile(final_values, 5) - 1) * 100,
            'percentile_95': (np.percentile(final_values, 95) - 1) * 100,
            'prob_profit': np.mean(final_values > 1) * 100,
            'prob_double': np.mean(final_values > 2) * 100,
            'prob_ruin': np.mean(final_values < 0.1) * 100,  # 90%+ loss
            'num_trades': num_trades
        }
