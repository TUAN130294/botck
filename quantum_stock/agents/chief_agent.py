"""
Chief Agent - The Orchestrator
Makes final trading decisions based on all agent inputs
"""

from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent, AgentSignal, StockData, SignalType, MessageType, Sentiment


class ChiefAgent(BaseAgent):
    """
    Chief AI - The decision maker that orchestrates all agents
    and provides final verdicts with weighted consensus.
    """

    def __init__(self):
        super().__init__(
            name="Chief",
            emoji="🎖",
            role="Orchestrator & Final Decision Maker",
            weight=1.5  # Chief has higher weight
        )
        self.agent_signals: Dict[str, AgentSignal] = {}
        self.verdict_history: List[Dict] = []

    def get_perspective(self) -> str:
        return "Balanced consensus-based decision making with risk awareness"

    async def analyze(self, stock_data: StockData, context: Dict[str, Any] = None) -> AgentSignal:
        """
        Analyze based on aggregated signals from all agents.
        Chief doesn't do primary analysis - it synthesizes other agents' work.
        """
        context = context or {}
        agent_signals = context.get('agent_signals', {})

        if not agent_signals:
            # No agent signals available, provide basic analysis
            return self._basic_analysis(stock_data)

        # Calculate weighted consensus
        verdict = self._calculate_verdict(agent_signals, stock_data)

        self.last_signal = verdict
        return verdict

    def _calculate_verdict(self, agent_signals: Dict[str, AgentSignal],
                          stock_data: StockData) -> AgentSignal:
        """Calculate final verdict based on all agent signals"""

        # Weight mapping for different agents
        agent_weights = {
            'Bull': 1.0,
            'Bear': 1.0,
            'Alex': 1.2,  # Technical analyst gets slightly more weight
            'RiskDoctor': 0.8  # Risk is advisory, not directional
        }

        # Aggregate scores
        total_weight = 0
        weighted_score = 0
        reasoning_parts = []

        for agent_name, signal in agent_signals.items():
            weight = agent_weights.get(agent_name, 1.0)

            # Convert signal type to score
            signal_scores = {
                SignalType.STRONG_BUY: 90,
                SignalType.BUY: 70,
                SignalType.HOLD: 50,
                SignalType.SELL: 30,
                SignalType.STRONG_SELL: 10,
                SignalType.WATCH: 50,
                SignalType.MIXED: 50
            }

            score = signal_scores.get(signal.signal_type, 50)
            confidence_adjusted = score * (signal.confidence / 100)

            weighted_score += confidence_adjusted * weight
            total_weight += weight

            reasoning_parts.append(f"{agent_name}: {signal.signal_type.value} ({signal.confidence}%)")

        if total_weight == 0:
            avg_score = 50
        else:
            avg_score = weighted_score / total_weight

        # Determine final signal
        final_signal = self._determine_signal(avg_score)

        # Check for conflicting signals
        has_conflict = self._detect_conflict(agent_signals)
        if has_conflict:
            final_signal = SignalType.MIXED
            self.emit_message(
                f"Phát hiện xung đột giữa các advisors. Khuyến nghị: WATCH và chờ đợi.",
                MessageType.WARNING
            )

        # Calculate entry/exit levels
        entry_price = stock_data.current_price
        atr = stock_data.indicators.get('atr', entry_price * 0.02)

        if final_signal in [SignalType.STRONG_BUY, SignalType.BUY]:
            stop_loss = entry_price - (2 * atr)
            take_profit = entry_price + (3 * atr)
            action = "BUY"
        elif final_signal in [SignalType.STRONG_SELL, SignalType.SELL]:
            stop_loss = entry_price + (2 * atr)
            take_profit = entry_price - (3 * atr)
            action = "SELL"
        else:
            stop_loss = None
            take_profit = None
            action = "WATCH"

        # Calculate risk/reward
        risk_reward = None
        if stop_loss and take_profit:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            risk_reward = reward / risk if risk > 0 else 0

        # Create verdict message
        verdict_text = self._create_verdict_text(
            stock_data.symbol, final_signal, avg_score, action
        )
        self.emit_message(verdict_text, MessageType.RECOMMENDATION, avg_score)

        return AgentSignal(
            signal_type=final_signal,
            confidence=round(avg_score, 1),
            price_target=take_profit,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=round(risk_reward, 2) if risk_reward else None,
            reasoning="; ".join(reasoning_parts),
            metadata={
                'agent_signals': {k: v.to_dict() for k, v in agent_signals.items()},
                'has_conflict': has_conflict,
                'action': action
            }
        )

    def _detect_conflict(self, agent_signals: Dict[str, AgentSignal]) -> bool:
        """Detect if there's significant conflict between agents"""
        bullish_count = 0
        bearish_count = 0

        for signal in agent_signals.values():
            if signal.signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                bullish_count += 1
            elif signal.signal_type in [SignalType.STRONG_SELL, SignalType.SELL]:
                bearish_count += 1

        # Conflict if both bullish and bearish signals with high confidence
        return bullish_count >= 1 and bearish_count >= 1

    def _create_verdict_text(self, symbol: str, signal: SignalType,
                            confidence: float, action: str) -> str:
        """Create human-readable verdict text"""
        signal_text_map = {
            SignalType.STRONG_BUY: "STRONG BUY - Tín hiệu mua mạnh",
            SignalType.BUY: "BUY - Nên mở vị thế Long",
            SignalType.HOLD: "HOLD - Giữ nguyên vị thế",
            SignalType.SELL: "SELL - Nên đóng vị thế",
            SignalType.STRONG_SELL: "STRONG SELL - Tín hiệu bán mạnh",
            SignalType.WATCH: "WATCH - Theo dõi và chờ đợi",
            SignalType.MIXED: "MIXED - Tín hiệu không rõ ràng"
        }

        signal_text = signal_text_map.get(signal, "UNKNOWN")
        return f"VERDICT: {symbol} → {signal_text}. Action: {action}. Confidence: {confidence:.1f}%"

    def _basic_analysis(self, stock_data: StockData) -> AgentSignal:
        """Provide basic analysis when no agent signals available"""
        # Simple technical check
        rsi = stock_data.indicators.get('rsi', 50)
        ema20 = stock_data.indicators.get('ema20', stock_data.current_price)

        score = 50
        if rsi < 30:
            score += 20  # Oversold
        elif rsi > 70:
            score -= 20  # Overbought

        if stock_data.current_price > ema20:
            score += 15
        else:
            score -= 15

        signal_type = self._determine_signal(score)

        self.emit_message(
            f"Phân tích cơ bản cho {stock_data.symbol}: RSI={rsi:.1f}, "
            f"Price vs EMA20: {'trên' if stock_data.current_price > ema20 else 'dưới'}",
            MessageType.ANALYSIS,
            score
        )

        return AgentSignal(
            signal_type=signal_type,
            confidence=score,
            reasoning="Basic analysis without full agent consensus"
        )

    def orchestrate_discussion(self, symbol: str, messages: List[Dict]) -> str:
        """
        Generate a team discussion narrative based on agent messages.
        Used for displaying in chat UI.
        """
        discussion = f"📊 **Team Discussion: {symbol}**\n\n"

        for msg in messages:
            discussion += f"{msg['agent_emoji']} **{msg['agent_name']}**: {msg['content']}\n\n"

        if self.last_signal:
            discussion += f"\n🎖 **VERDICT**: {self.last_signal.signal_type.value} "
            discussion += f"với confidence {self.last_signal.confidence}%"

        return discussion
