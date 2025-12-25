"""
Bull Agent - The Optimistic Advisor
Focuses on bullish signals and opportunities
"""

from typing import Dict, Any
from .base_agent import BaseAgent, AgentSignal, StockData, SignalType, MessageType


class BullAgent(BaseAgent):
    """
    Bull Advisor - Looks for bullish opportunities
    Focuses on upside potential, growth signals, and buying opportunities.
    """

    def __init__(self):
        super().__init__(
            name="Bull",
            emoji="🐂",
            role="Bullish Perspective & Opportunity Finder",
            weight=1.0
        )

    def get_perspective(self) -> str:
        return "Tìm kiếm cơ hội tăng giá, momentum tích cực, và điểm vào lệnh thuận lợi"

    async def analyze(self, stock_data: StockData, context: Dict[str, Any] = None) -> AgentSignal:
        """
        Analyze from bullish perspective - looking for buy opportunities
        """
        context = context or {}

        # Initialize scoring factors
        factors = {
            'trend_alignment': 50,
            'momentum_strength': 50,
            'volume_confirmation': 50,
            'support_resistance': 50,
            'fundamental_score': 50,
            'sentiment_score': 50
        }

        reasoning_parts = []

        # 1. Trend Analysis (EMA alignment)
        ema20 = stock_data.indicators.get('ema20', stock_data.current_price)
        ema50 = stock_data.indicators.get('ema50', stock_data.current_price)
        price = stock_data.current_price

        if price > ema20 > ema50:
            factors['trend_alignment'] = 85
            reasoning_parts.append("Xu hướng tăng mạnh: Price > EMA20 > EMA50")
        elif price > ema20:
            factors['trend_alignment'] = 70
            reasoning_parts.append("Xu hướng tăng: Price > EMA20")
        elif price > ema50:
            factors['trend_alignment'] = 60
            reasoning_parts.append("Xu hướng trung tính-tăng")
        else:
            factors['trend_alignment'] = 30
            reasoning_parts.append("Xu hướng giảm nhưng có thể reversal")

        # 2. Momentum Analysis (RSI)
        rsi = stock_data.indicators.get('rsi', 50)

        if 30 <= rsi <= 50:
            factors['momentum_strength'] = 80
            reasoning_parts.append(f"RSI={rsi:.1f}: Oversold đang hồi phục - CƠ HỘI MUA")
        elif 50 < rsi <= 70:
            factors['momentum_strength'] = 75
            reasoning_parts.append(f"RSI={rsi:.1f}: Momentum tích cực")
        elif rsi < 30:
            factors['momentum_strength'] = 90
            reasoning_parts.append(f"RSI={rsi:.1f}: Quá bán MẠNH - Cơ hội mua tuyệt vời!")
        else:
            factors['momentum_strength'] = 40
            reasoning_parts.append(f"RSI={rsi:.1f}: Quá mua - Cẩn thận")

        # 3. MACD Analysis
        macd = stock_data.indicators.get('macd', 0)
        macd_signal = stock_data.indicators.get('macd_signal', 0)
        macd_hist = stock_data.indicators.get('macd_hist', 0)

        if macd > macd_signal and macd_hist > 0:
            factors['momentum_strength'] = min(90, factors['momentum_strength'] + 15)
            reasoning_parts.append("MACD bullish crossover!")
        elif macd > macd_signal:
            factors['momentum_strength'] = min(85, factors['momentum_strength'] + 10)
            reasoning_parts.append("MACD turning bullish")

        # 4. Volume Analysis
        volume = stock_data.volume
        avg_volume = stock_data.indicators.get('avg_volume', volume)

        if volume > avg_volume * 1.5 and stock_data.change_percent > 0:
            factors['volume_confirmation'] = 85
            reasoning_parts.append(f"Volume đột biến +{(volume/avg_volume-1)*100:.0f}% với giá tăng - BULLISH!")
        elif volume > avg_volume:
            factors['volume_confirmation'] = 70
            reasoning_parts.append("Volume trên trung bình")
        else:
            factors['volume_confirmation'] = 50
            reasoning_parts.append("Volume bình thường")

        # 5. Support/Resistance - Looking for support bounces
        support = stock_data.indicators.get('support', price * 0.95)
        resistance = stock_data.indicators.get('resistance', price * 1.05)

        distance_to_support = (price - support) / price * 100
        distance_to_resistance = (resistance - price) / price * 100

        if distance_to_support < 2:
            factors['support_resistance'] = 85
            reasoning_parts.append(f"Gần support ({support:.2f}) - Điểm mua tốt!")
        elif distance_to_resistance > 5:
            factors['support_resistance'] = 75
            reasoning_parts.append(f"Room tăng đến resistance: {distance_to_resistance:.1f}%")
        else:
            factors['support_resistance'] = 60

        # 6. Daily Change - Momentum confirmation
        change = stock_data.change_percent
        if change > 2:
            factors['sentiment_score'] = 80
            reasoning_parts.append(f"Tăng mạnh hôm nay +{change:.2f}%!")
        elif change > 0:
            factors['sentiment_score'] = 65
            reasoning_parts.append(f"Phiên xanh +{change:.2f}%")
        elif change > -2:
            factors['sentiment_score'] = 50
            reasoning_parts.append("Điều chỉnh nhẹ - Có thể tích lũy")
        else:
            factors['sentiment_score'] = 35
            reasoning_parts.append("Giảm mạnh - Chờ đợi stabilize")

        # 7. Fundamental bias (Bull always sees opportunity)
        pe = stock_data.fundamentals.get('pe', 15)
        if pe and pe < 15:
            factors['fundamental_score'] = 80
            reasoning_parts.append(f"P/E={pe:.1f} hấp dẫn!")
        elif pe and pe < 25:
            factors['fundamental_score'] = 65
            reasoning_parts.append(f"P/E={pe:.1f} hợp lý")
        else:
            factors['fundamental_score'] = 50

        # Calculate final confidence
        confidence = self._calculate_confidence(factors)

        # Bull adds optimistic bias (+5-10%)
        bull_bias = min(100, confidence + 8)

        # Determine signal with bullish tilt
        if bull_bias >= 65:
            signal_type = SignalType.BUY
            if bull_bias >= 80:
                signal_type = SignalType.STRONG_BUY
        elif bull_bias >= 50:
            signal_type = SignalType.HOLD
        else:
            signal_type = SignalType.WATCH

        # Generate bullish message
        message = self._generate_bullish_message(stock_data.symbol, signal_type, bull_bias, reasoning_parts)
        self.emit_message(message, MessageType.ANALYSIS, bull_bias)

        # Calculate targets (Bull aims higher)
        atr = stock_data.indicators.get('atr', price * 0.02)
        take_profit = price + (3.5 * atr)  # Bull aims for bigger gains
        stop_loss = price - (1.5 * atr)    # Tighter stop (optimistic on upside)

        self.last_signal = AgentSignal(
            signal_type=signal_type,
            confidence=round(bull_bias, 1),
            price_target=take_profit,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=round((take_profit - price) / (price - stop_loss), 2) if stop_loss < price else None,
            reasoning=" | ".join(reasoning_parts[:4]),
            metadata={'factors': factors, 'perspective': 'bullish'}
        )

        return self.last_signal

    def _generate_bullish_message(self, symbol: str, signal: SignalType,
                                  confidence: float, reasons: list) -> str:
        """Generate an optimistic message in Vietnamese"""

        if signal == SignalType.STRONG_BUY:
            intro = f"Nhìn momentum thế này, tôi thấy cơ hội! Nên MUA thôi team!"
        elif signal == SignalType.BUY:
            intro = f"Tín hiệu tích cực cho {symbol}! Có thể cân nhắc vào lệnh."
        elif signal == SignalType.HOLD:
            intro = f"{symbol} đang tích lũy, chờ breakout để vào."
        else:
            intro = f"{symbol} chưa rõ trend, nhưng có thể có cơ hội sớm."

        top_reasons = " ".join(reasons[:2])
        return f"{intro} {top_reasons}"
