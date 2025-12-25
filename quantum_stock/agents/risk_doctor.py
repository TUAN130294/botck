"""
Risk Doctor Agent - Risk Management Specialist
Evaluates risk, position sizing, and portfolio protection
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .base_agent import BaseAgent, AgentSignal, StockData, SignalType, MessageType


@dataclass
class RiskAssessment:
    """Comprehensive risk assessment"""
    risk_score: int  # 0-100 (0 = no risk, 100 = extreme risk)
    risk_level: str  # LOW, MEDIUM, HIGH, EXTREME
    max_position_pct: float  # Maximum recommended position size (% of NAV)
    kelly_fraction: float  # Kelly criterion position size
    stop_loss_pct: float  # Recommended stop loss percentage
    risk_reward_ratio: float
    warnings: List[str]
    recommendations: List[str]


class RiskDoctor(BaseAgent):
    """
    Risk Doctor - Specializes in risk management and position sizing
    Uses Kelly Criterion, volatility analysis, and portfolio theory.
    """

    def __init__(self, portfolio_value: float = 100000):
        super().__init__(
            name="Risk Doctor",
            emoji="🏥",
            role="Risk Management & Position Sizing",
            weight=0.8  # Advisory weight
        )
        self.portfolio_value = portfolio_value
        self.max_risk_per_trade = 0.02  # 2% max risk per trade
        self.max_position_size = 0.25  # 25% max single position

    def get_perspective(self) -> str:
        return "Quản lý rủi ro, tính toán size vị thế, và bảo vệ danh mục"

    def set_portfolio_value(self, value: float):
        """Update portfolio value for calculations"""
        self.portfolio_value = value

    async def analyze(self, stock_data: StockData, context: Dict[str, Any] = None) -> AgentSignal:
        """
        Analyze risk factors and provide risk-adjusted recommendations
        """
        context = context or {}

        # Perform comprehensive risk assessment
        assessment = self._assess_risk(stock_data, context)

        # Generate risk message
        message = self._generate_risk_message(stock_data.symbol, assessment)
        msg_type = MessageType.WARNING if assessment.risk_level in ['HIGH', 'EXTREME'] else MessageType.INFO
        self.emit_message(message, msg_type, 100 - assessment.risk_score)

        # Risk-adjusted signal
        if assessment.risk_level == 'EXTREME':
            signal_type = SignalType.STRONG_SELL
            confidence = 20
        elif assessment.risk_level == 'HIGH':
            signal_type = SignalType.SELL
            confidence = 35
        elif assessment.risk_level == 'MEDIUM':
            signal_type = SignalType.HOLD
            confidence = 55
        else:
            signal_type = SignalType.WATCH  # Low risk doesn't mean buy
            confidence = 70

        price = stock_data.current_price
        stop_loss = price * (1 - assessment.stop_loss_pct / 100)
        take_profit = price * (1 + assessment.stop_loss_pct * assessment.risk_reward_ratio / 100)

        self.last_signal = AgentSignal(
            signal_type=signal_type,
            confidence=confidence,
            price_target=take_profit,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=assessment.risk_reward_ratio,
            reasoning=f"Risk Score: {assessment.risk_score}/100 | Max Position: {assessment.max_position_pct:.1f}% | Kelly: {assessment.kelly_fraction*100:.1f}%",
            metadata={
                'risk_assessment': {
                    'risk_score': assessment.risk_score,
                    'risk_level': assessment.risk_level,
                    'max_position_pct': assessment.max_position_pct,
                    'kelly_fraction': assessment.kelly_fraction,
                    'stop_loss_pct': assessment.stop_loss_pct,
                    'risk_reward_ratio': assessment.risk_reward_ratio,
                    'warnings': assessment.warnings,
                    'recommendations': assessment.recommendations
                },
                'perspective': 'risk_management'
            }
        )

        return self.last_signal

    def _assess_risk(self, stock_data: StockData, context: Dict[str, Any]) -> RiskAssessment:
        """Comprehensive risk assessment"""
        warnings = []
        recommendations = []
        risk_factors = []

        price = stock_data.current_price

        # 1. Volatility Risk (ATR-based)
        atr = stock_data.indicators.get('atr', price * 0.02)
        atr_pct = (atr / price) * 100

        if atr_pct > 5:
            risk_factors.append(30)
            warnings.append(f"Độ biến động CAO: ATR={atr_pct:.1f}%")
        elif atr_pct > 3:
            risk_factors.append(20)
            warnings.append(f"Biến động trung bình-cao: ATR={atr_pct:.1f}%")
        else:
            risk_factors.append(10)

        # 2. RSI Extreme Risk
        rsi = stock_data.indicators.get('rsi', 50)
        if rsi > 80:
            risk_factors.append(25)
            warnings.append(f"RSI={rsi:.0f} - QUÁ MUA cực độ!")
        elif rsi > 70:
            risk_factors.append(15)
            warnings.append(f"RSI={rsi:.0f} - Vùng quá mua")
        elif rsi < 20:
            risk_factors.append(20)
            warnings.append(f"RSI={rsi:.0f} - QUÁ BÁN cực độ (có thể catch falling knife)")
        elif rsi < 30:
            risk_factors.append(10)
        else:
            risk_factors.append(5)

        # 3. Volume Risk
        volume = stock_data.volume
        avg_volume = stock_data.indicators.get('avg_volume', volume)

        if avg_volume > 0:
            vol_ratio = volume / avg_volume
            if vol_ratio > 3:
                risk_factors.append(20)
                warnings.append(f"Volume spike {vol_ratio:.1f}x - Có thể manipulation")
            elif vol_ratio < 0.3:
                risk_factors.append(15)
                warnings.append("Volume quá thấp - Thanh khoản kém")
            else:
                risk_factors.append(5)

        # 4. Price Position Risk (Distance from MA)
        ema20 = stock_data.indicators.get('ema20', price)
        distance_from_ema = abs(price - ema20) / ema20 * 100

        if distance_from_ema > 10:
            risk_factors.append(25)
            warnings.append(f"Giá xa EMA20 {distance_from_ema:.1f}% - Rủi ro mean reversion")
        elif distance_from_ema > 5:
            risk_factors.append(15)
        else:
            risk_factors.append(5)

        # 5. Bollinger Band Risk
        bb_upper = stock_data.indicators.get('bb_upper', price * 1.02)
        bb_lower = stock_data.indicators.get('bb_lower', price * 0.98)

        if price > bb_upper:
            risk_factors.append(20)
            warnings.append("Giá trên BB upper - Overextended")
        elif price < bb_lower:
            risk_factors.append(15)
            warnings.append("Giá dưới BB lower - Có thể breakdown")
        else:
            risk_factors.append(5)

        # 6. Trend Risk (Against trend = higher risk)
        ema50 = stock_data.indicators.get('ema50', price)
        if price < ema50 and stock_data.change_percent > 0:
            risk_factors.append(15)
            warnings.append("Mua trong downtrend - Rủi ro cao")
        elif price > ema50 and stock_data.change_percent < 0:
            risk_factors.append(10)

        # 7. Gap Risk
        gap_pct = abs(stock_data.open_price - stock_data.indicators.get('prev_close', stock_data.open_price)) / stock_data.open_price * 100
        if gap_pct > 3:
            risk_factors.append(20)
            warnings.append(f"Gap {gap_pct:.1f}% - Rủi ro overnight cao")

        # 8. Market Cap Risk (smaller = higher risk)
        market_cap = stock_data.fundamentals.get('market_cap', 0)
        if market_cap > 0:
            if market_cap < 1e12:  # < 1000 tỷ
                risk_factors.append(20)
                warnings.append("Vốn hóa nhỏ - Thanh khoản và manipulation risk")
            elif market_cap < 5e12:
                risk_factors.append(10)
            else:
                risk_factors.append(5)

        # Calculate total risk score
        risk_score = min(100, sum(risk_factors))

        # Determine risk level
        if risk_score >= 70:
            risk_level = 'EXTREME'
        elif risk_score >= 50:
            risk_level = 'HIGH'
        elif risk_score >= 30:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'

        # Calculate position sizing
        kelly_fraction = self._calculate_kelly(stock_data, context)
        max_position = self._calculate_max_position(risk_score, atr_pct)

        # Stop loss recommendation
        stop_loss_pct = max(atr_pct * 2, 3)  # At least 2x ATR or 3%
        stop_loss_pct = min(stop_loss_pct, 10)  # Cap at 10%

        # Risk/Reward recommendation
        target_rr = 2.0 if risk_level in ['LOW', 'MEDIUM'] else 3.0

        # Generate recommendations
        recommendations.append(f"Max position size: {max_position:.1f}% NAV")
        recommendations.append(f"Kelly fraction: {kelly_fraction*100:.1f}%")
        recommendations.append(f"Stop loss: -{stop_loss_pct:.1f}%")
        recommendations.append(f"Target R:R ratio: 1:{target_rr:.1f}")

        if risk_level == 'EXTREME':
            recommendations.append("⛔ KHÔNG NÊN VÀO LỆNH - Rủi ro quá cao!")
        elif risk_level == 'HIGH':
            recommendations.append("⚠️ Cân nhắc giảm 50% size hoặc chờ setup tốt hơn")
        elif risk_level == 'MEDIUM':
            recommendations.append("✅ Có thể vào lệnh với size được khuyến nghị")
        else:
            recommendations.append("✅ Risk profile tốt - Có thể vào full size")

        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            max_position_pct=max_position,
            kelly_fraction=kelly_fraction,
            stop_loss_pct=stop_loss_pct,
            risk_reward_ratio=target_rr,
            warnings=warnings,
            recommendations=recommendations
        )

    def _calculate_kelly(self, stock_data: StockData, context: Dict[str, Any]) -> float:
        """
        Calculate Kelly Criterion position size
        Kelly % = W - [(1-W) / R]
        W = Win probability
        R = Win/Loss ratio
        """
        # Estimate win probability from technical signals
        rsi = stock_data.indicators.get('rsi', 50)
        macd = stock_data.indicators.get('macd', 0)
        macd_signal = stock_data.indicators.get('macd_signal', 0)

        # Base win rate from historical or estimate
        win_rate = 0.50  # Base 50%

        # Adjust based on technicals
        if 30 <= rsi <= 50:
            win_rate += 0.10  # Oversold recovery
        elif 50 < rsi <= 70:
            win_rate += 0.05
        elif rsi > 70:
            win_rate -= 0.10  # Overbought

        if macd > macd_signal:
            win_rate += 0.08

        # Get from context if available
        backtest_win_rate = context.get('backtest_win_rate', win_rate)
        if backtest_win_rate:
            win_rate = (win_rate + backtest_win_rate) / 2

        # Win/Loss ratio (assume from ATR-based targets)
        win_loss_ratio = 2.0  # Default 2:1 R:R

        # Kelly formula
        kelly = win_rate - ((1 - win_rate) / win_loss_ratio)

        # Half Kelly for safety
        kelly = kelly * 0.5

        # Cap at reasonable levels
        kelly = max(0, min(kelly, 0.25))

        return kelly

    def _calculate_max_position(self, risk_score: int, atr_pct: float) -> float:
        """Calculate maximum position size based on risk"""
        # Base on risk score
        if risk_score >= 70:
            base_pct = 5
        elif risk_score >= 50:
            base_pct = 10
        elif risk_score >= 30:
            base_pct = 20
        else:
            base_pct = 25

        # Adjust for volatility
        if atr_pct > 5:
            base_pct *= 0.6
        elif atr_pct > 3:
            base_pct *= 0.8

        return min(base_pct, self.max_position_size * 100)

    def _generate_risk_message(self, symbol: str, assessment: RiskAssessment) -> str:
        """Generate risk assessment message"""
        emoji_map = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🟠',
            'EXTREME': '🔴'
        }

        emoji = emoji_map.get(assessment.risk_level, '⚪')
        warnings_text = assessment.warnings[0] if assessment.warnings else "Không có cảnh báo đặc biệt"

        return f"Điểm Rủi Ro {symbol}: {assessment.risk_score}/100 {emoji} ({assessment.risk_level}). {warnings_text}. Max position: {assessment.max_position_pct:.1f}% NAV."

    def calculate_position_value(self, entry_price: float, stop_loss: float,
                                 risk_pct: float = None) -> Dict[str, float]:
        """
        Calculate position size in VND based on risk parameters

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_pct: Risk percentage per trade (default: self.max_risk_per_trade)

        Returns:
            Dict with position details
        """
        if risk_pct is None:
            risk_pct = self.max_risk_per_trade

        # Risk amount in VND
        risk_amount = self.portfolio_value * risk_pct

        # Risk per share
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share == 0:
            return {
                'shares': 0,
                'position_value': 0,
                'risk_amount': risk_amount,
                'position_pct': 0
            }

        # Number of shares
        shares = int(risk_amount / risk_per_share)

        # Position value
        position_value = shares * entry_price

        # Position as percentage of portfolio
        position_pct = (position_value / self.portfolio_value) * 100

        return {
            'shares': shares,
            'position_value': position_value,
            'risk_amount': risk_amount,
            'position_pct': position_pct,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'risk_per_share': risk_per_share
        }

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get summary of last risk assessment"""
        if not self.last_signal:
            return {'status': 'No assessment available'}

        return self.last_signal.metadata.get('risk_assessment', {})
