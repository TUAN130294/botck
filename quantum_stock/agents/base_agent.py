"""
Base Agent Class for Multi-Agent Stock Analysis System
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import uuid


class SignalType(Enum):
    """Signal types for trading decisions"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    WATCH = "WATCH"
    MIXED = "MIXED"


class Sentiment(Enum):
    """Market sentiment classification"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


class MessageType(Enum):
    """Agent message types"""
    ANALYSIS = "ANALYSIS"
    ALERT = "ALERT"
    RECOMMENDATION = "RECOMMENDATION"
    WARNING = "WARNING"
    INFO = "INFO"
    SUCCESS = "SUCCESS"


@dataclass
class AgentSignal:
    """Standardized signal output from agents"""
    signal_type: SignalType
    confidence: float  # 0-100
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'signal_type': self.signal_type.value,
            'confidence': self.confidence,
            'price_target': self.price_target,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'risk_reward_ratio': self.risk_reward_ratio,
            'reasoning': self.reasoning,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class AgentMessage:
    """Message format for agent communication"""
    agent_name: str
    agent_emoji: str
    message_type: MessageType
    content: str
    confidence: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent_name': self.agent_name,
            'agent_emoji': self.agent_emoji,
            'message_type': self.message_type.value,
            'content': self.content,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'message_id': self.message_id
        }

    def format_display(self) -> str:
        """Format for terminal/chat display"""
        conf_str = f" Confidence {self.confidence}%." if self.confidence else ""
        return f"{self.agent_emoji} {self.agent_name}: {self.content}{conf_str}"


@dataclass
class StockData:
    """Stock data container for analysis"""
    symbol: str
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: int
    change_percent: float
    historical_data: Optional[Any] = None  # DataFrame
    indicators: Dict[str, float] = field(default_factory=dict)
    fundamentals: Dict[str, Any] = field(default_factory=dict)
    news_sentiment: Optional[float] = None
    sector: str = ""
    market_cap: float = 0


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents in the system.
    Each agent provides a unique perspective on stock analysis.
    """

    def __init__(self, name: str, emoji: str, role: str, weight: float = 1.0):
        self.name = name
        self.emoji = emoji
        self.role = role
        self.weight = weight  # Weight in consensus calculation
        self.messages: List[AgentMessage] = []
        self.last_signal: Optional[AgentSignal] = None
        self.is_online = True

    @abstractmethod
    async def analyze(self, stock_data: StockData, context: Dict[str, Any] = None) -> AgentSignal:
        """
        Analyze stock data and return a signal.
        Must be implemented by each agent.
        """
        pass

    @abstractmethod
    def get_perspective(self) -> str:
        """Return the agent's analytical perspective/bias"""
        pass

    def emit_message(self, content: str, msg_type: MessageType = MessageType.ANALYSIS,
                     confidence: Optional[float] = None) -> AgentMessage:
        """Create and store a message from this agent"""
        message = AgentMessage(
            agent_name=self.name,
            agent_emoji=self.emoji,
            message_type=msg_type,
            content=content,
            confidence=confidence
        )
        self.messages.append(message)
        return message

    def clear_messages(self):
        """Clear message history"""
        self.messages = []

    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            'name': self.name,
            'emoji': self.emoji,
            'role': self.role,
            'weight': self.weight,
            'is_online': self.is_online,
            'message_count': len(self.messages),
            'last_signal': self.last_signal.to_dict() if self.last_signal else None
        }

    def _calculate_confidence(self, factors: Dict[str, float]) -> float:
        """
        Calculate confidence score based on multiple factors.
        Each factor should be 0-100.
        """
        if not factors:
            return 50.0

        weights = {
            'trend_alignment': 0.25,
            'momentum_strength': 0.20,
            'volume_confirmation': 0.15,
            'support_resistance': 0.15,
            'fundamental_score': 0.15,
            'sentiment_score': 0.10
        }

        total_weight = 0
        weighted_sum = 0

        for factor, value in factors.items():
            weight = weights.get(factor, 0.1)
            weighted_sum += value * weight
            total_weight += weight

        if total_weight == 0:
            return 50.0

        return min(100, max(0, weighted_sum / total_weight))

    def _determine_signal(self, score: float) -> SignalType:
        """Determine signal type based on score (0-100)"""
        if score >= 80:
            return SignalType.STRONG_BUY
        elif score >= 60:
            return SignalType.BUY
        elif score >= 40:
            return SignalType.HOLD
        elif score >= 20:
            return SignalType.SELL
        else:
            return SignalType.STRONG_SELL
