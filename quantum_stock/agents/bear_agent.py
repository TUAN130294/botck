"""
Bear Agent - The Cautious Advisor
Focuses on risks, bearish signals, and protective measures
"""

from typing import Dict, Any
from .base_agent import BaseAgent, AgentSignal, StockData, SignalType, MessageType


class BearAgent(BaseAgent):
    """
    Bear Advisor - Looks for risks and bearish signals
    Focuses on downside protection, warning signs, and when to exit.
    """

    def __init__(self):
        super().__init__(
            name="Bear",
            emoji="🐻",
            role="Risk Warning & Bearish Analysis",
            weight=1.0
        )

    def get_perspective(self) -> str:
        return "Cảnh báo rủi ro, tìm tín hiệu bearish, và bảo vệ vốn"

    async def analyze(self, stock_data: StockData, context: Dict[str, Any] = None) -> AgentSignal:
        """
        Analyze from bearish perspective - looking for risks and sell signals
        """
        context = context or {}

        # Initialize scoring factors (inverted for bearish view)
        factors = {
            'trend_alignment': 50,
            'momentum_strength': 50,
            'volume_confirmation': 50,
            'support_resistance': 50,
            'fundamental_score': 50,
            'sentiment_score': 50
        }

        risk_warnings = []
        reasoning_parts = []

        # 1. Trend Analysis - Look for weakness
        ema20 = stock_data.indicators.get('ema20', stock_data.current_price)
        ema50 = stock_data.indicators.get('ema50', stock_data.current_price)
        price = stock_data.current_price

        if price < ema20 < ema50:
            factors['trend_alignment'] = 20  # Very bearish
            risk_warnings.append("⚠️ Death cross pattern: Price < EMA20 < EMA50")
            reasoning_parts.append("Xu hướng giảm mạnh")
        elif price < ema20:
            factors['trend_alignment'] = 35
            risk_warnings.append("Price dưới EMA20 - Xu hướng ngắn hạn yếu")
            reasoning_parts.append("Mất momentum ngắn hạn")
        elif price < ema50:
            factors['trend_alignment'] = 45
            reasoning_parts.append("Trend trung hạn yếu")
        else:
            factors['trend_alignment'] = 70
            reasoning_parts.append("Trend vẫn intact")

        # 2. RSI Analysis - Overbought danger
        rsi = stock_data.indicators.get('rsi', 50)

        if rsi > 70:
            factors['momentum_strength'] = 25
            risk_warnings.append(f"🔴 RSI={rsi:.1f} QUÁ MUA - Nguy cơ điều chỉnh cao!")
            reasoning_parts.append("Overbought nghiêm trọng")
        elif rsi > 60:
            factors['momentum_strength'] = 40
            risk_warnings.append(f"RSI={rsi:.1f} - Cẩn thận vùng quá mua")
            reasoning_parts.append("Tiến vào vùng quá mua")
        elif rsi < 30:
            factors['momentum_strength'] = 65  # Oversold can bounce
            reasoning_parts.append("Oversold - có thể bounce")
        else:
            factors['momentum_strength'] = 55
            reasoning_parts.append("RSI neutral")

        # 3. MACD Analysis - Bearish signals
        macd = stock_data.indicators.get('macd', 0)
        macd_signal = stock_data.indicators.get('macd_signal', 0)
        macd_hist = stock_data.indicators.get('macd_hist', 0)

        if macd < macd_signal and macd_hist < 0:
            factors['momentum_strength'] = max(20, factors['momentum_strength'] - 20)
            risk_warnings.append("MACD bearish crossover - Sell signal!")
            reasoning_parts.append("MACD bearish")
        elif macd < macd_signal:
            factors['momentum_strength'] = max(30, factors['momentum_strength'] - 10)
            reasoning_parts.append("MACD đang yếu")

        # 4. Volume Analysis - Distribution signs
        volume = stock_data.volume
        avg_volume = stock_data.indicators.get('avg_volume', volume)

        if volume > avg_volume * 1.5 and stock_data.change_percent < 0:
            factors['volume_confirmation'] = 25
            risk_warnings.append(f"🔴 Volume cao +{(volume/avg_volume-1)*100:.0f}% với giá GIẢM - Phân phối!")
            reasoning_parts.append("Distribution pattern")
        elif volume > avg_volume * 2:
            factors['volume_confirmation'] = 40
            risk_warnings.append("Volume đột biến - Biến động cao")
            reasoning_parts.append("High volatility")
        else:
            factors['volume_confirmation'] = 55

        # 5. Resistance Analysis - Ceiling danger
        resistance = stock_data.indicators.get('resistance', price * 1.05)
        support = stock_data.indicators.get('support', price * 0.95)

        distance_to_resistance = (resistance - price) / price * 100
        distance_to_support = (price - support) / price * 100

        if distance_to_resistance < 2:
            factors['support_resistance'] = 30
            risk_warnings.append(f"Sát resistance ({resistance:.2f}) - Khó breakout!")
            reasoning_parts.append("Resistance cản lên")
        elif distance_to_support < 2:
            factors['support_resistance'] = 35
            risk_warnings.append(f"⚠️ Gần support ({support:.2f}) - Nguy cơ breakdown!")
            reasoning_parts.append("Có thể breakdown support")
        else:
            factors['support_resistance'] = 55

        # 6. Price Change - Bearish momentum
        change = stock_data.change_percent

        if change < -3:
            factors['sentiment_score'] = 20
            risk_warnings.append(f"🔴 Giảm mạnh {change:.2f}% - Panic selling!")
            reasoning_parts.append("Sell-off mạnh")
        elif change < -1:
            factors['sentiment_score'] = 35
            risk_warnings.append(f"Phiên đỏ {change:.2f}%")
            reasoning_parts.append("Bearish session")
        elif change < 0:
            factors['sentiment_score'] = 45
            reasoning_parts.append("Nhẹ đỏ")
        else:
            factors['sentiment_score'] = 60
            reasoning_parts.append("Phiên xanh nhưng cần confirm")

        # 7. Valuation Warning
        pe = stock_data.fundamentals.get('pe', 15)
        if pe and pe > 30:
            factors['fundamental_score'] = 30
            risk_warnings.append(f"P/E={pe:.1f} QUÁ CAO - Định giá rủi ro!")
            reasoning_parts.append("Overvalued")
        elif pe and pe > 20:
            factors['fundamental_score'] = 45
            reasoning_parts.append(f"P/E={pe:.1f} hơi cao")
        else:
            factors['fundamental_score'] = 60

        # 8. Bollinger Bands - Squeeze warning
        bb_upper = stock_data.indicators.get('bb_upper', price * 1.02)
        bb_lower = stock_data.indicators.get('bb_lower', price * 0.98)

        if price > bb_upper:
            risk_warnings.append("Price trên BB upper - Overextended!")
            factors['momentum_strength'] = max(25, factors['momentum_strength'] - 10)

        # Calculate bearish confidence (higher = more bearish = lower buy score)
        raw_confidence = self._calculate_confidence(factors)

        # Invert for bearish perspective (low score = bearish)
        bearish_score = 100 - raw_confidence

        # Determine signal
        if bearish_score >= 70:
            signal_type = SignalType.STRONG_SELL
        elif bearish_score >= 55:
            signal_type = SignalType.SELL
        elif bearish_score >= 40:
            signal_type = SignalType.HOLD
        else:
            signal_type = SignalType.WATCH

        # Generate bearish message
        message = self._generate_bearish_message(
            stock_data.symbol, signal_type, bearish_score, risk_warnings, reasoning_parts
        )
        self.emit_message(message, MessageType.WARNING if risk_warnings else MessageType.ANALYSIS, bearish_score)

        # Calculate targets (Bear is conservative)
        atr = stock_data.indicators.get('atr', price * 0.02)
        stop_loss = price + (2 * atr)   # Stop for short
        take_profit = price - (2.5 * atr)  # Conservative target

        self.last_signal = AgentSignal(
            signal_type=signal_type,
            confidence=round(bearish_score, 1),
            price_target=take_profit,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=" | ".join(reasoning_parts[:4]),
            metadata={
                'factors': factors,
                'perspective': 'bearish',
                'risk_warnings': risk_warnings
            }
        )

        return self.last_signal

    def _generate_bearish_message(self, symbol: str, signal: SignalType,
                                  confidence: float, warnings: list,
                                  reasons: list) -> str:
        """Generate a cautious message in Vietnamese"""

        if signal == SignalType.STRONG_SELL:
            intro = f"⚠️ CẢNH BÁO {symbol}! Nhiều tín hiệu bearish - Nên thoát hoặc Short!"
        elif signal == SignalType.SELL:
            intro = f"Tôi thấy rủi ro với {symbol}. Cân nhắc chốt lời hoặc giảm vị thế."
        elif signal == SignalType.HOLD:
            intro = f"{symbol} có một số rủi ro cần theo dõi."
        else:
            intro = f"{symbol} tạm ổn nhưng luôn đề phòng."

        if warnings:
            warning_text = warnings[0] if warnings else ""
            return f"{intro} {warning_text}"
        else:
            return f"{intro} {reasons[0] if reasons else ''}"

    def get_risk_summary(self, stock_data: StockData) -> Dict[str, Any]:
        """Get a summary of all identified risks"""
        if not self.last_signal:
            return {'risks': [], 'risk_level': 'UNKNOWN'}

        warnings = self.last_signal.metadata.get('risk_warnings', [])
        risk_level = 'LOW'

        if len(warnings) >= 3:
            risk_level = 'HIGH'
        elif len(warnings) >= 1:
            risk_level = 'MEDIUM'

        return {
            'risks': warnings,
            'risk_level': risk_level,
            'bearish_score': self.last_signal.confidence
        }
