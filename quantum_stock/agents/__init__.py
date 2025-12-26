"""
Multi-Agent System for Stock Analysis
Agentic Architecture v4.0
"""

from .base_agent import BaseAgent, AgentSignal, AgentMessage
from .chief_agent import ChiefAgent
from .bull_agent import BullAgent
from .bear_agent import BearAgent
from .analyst_agent import AnalystAgent
from .risk_doctor import RiskDoctor
from .agent_coordinator import AgentCoordinator

__all__ = [
    'BaseAgent',
    'AgentSignal',
    'AgentMessage',
    'ChiefAgent',
    'BullAgent',
    'BearAgent',
    'AnalystAgent',
    'RiskDoctor',
    'AgentCoordinator'
]
