"""
Multi-Agent System for Stock Analysis
Agentic Architecture v5.0 - Level 3/4/5 Support
"""

from .base_agent import BaseAgent, AgentSignal, AgentMessage
from .chief_agent import ChiefAgent
from .bull_agent import BullAgent
from .bear_agent import BearAgent
from .analyst_agent import AnalystAgent
from .risk_doctor import RiskDoctor
from .agent_coordinator import AgentCoordinator

# New Agentic L3-L5 Agents
try:
    from .sentiment_agent import SentimentAgent
    from .flow_agent import FlowAgent
    from .execution_agent import ExecutionAgent, Order, OrderStatus, OrderSide, OrderType
except ImportError:
    pass  # Optional agents

# Agentic Level 3-4-5 Components
from .memory_system import AgentMemorySystem, Memory, MemoryType, get_memory_system
from .market_regime_detector import MarketRegimeDetector, MarketRegime, VolatilityRegime
from .conversational_quant import ConversationalQuant, QueryIntent, QueryResult

# Performance Tracking (L5)
try:
    from .performance_tracker import AgentPerformanceTracker, AdaptiveWeightOptimizer, AgentMetrics
except ImportError:
    pass

__all__ = [
    # Base
    'BaseAgent',
    'AgentSignal',
    'AgentMessage',
    # Core Agents (L2)
    'ChiefAgent',
    'BullAgent',
    'BearAgent',
    'AnalystAgent',
    'RiskDoctor',
    'AgentCoordinator',
    # New Agents (L3-L5)
    'SentimentAgent',
    'FlowAgent',
    'ExecutionAgent',
    # Execution Types
    'Order',
    'OrderStatus',
    'OrderSide',
    'OrderType'
]
