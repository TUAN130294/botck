"""
Quantum Stock Platform v4.0
Vietnamese Stock Investment Tool with Multi-Agent Architecture
"""

__version__ = "4.0.0"
__author__ = "Quantum Stock Team"

from .agents import AgentCoordinator, ChiefAgent, BullAgent, BearAgent, AnalystAgent, RiskDoctor
from .core import QuantumEngine, BacktestEngine, MonteCarloSimulator, KellyCriterion

__all__ = [
    'AgentCoordinator',
    'ChiefAgent',
    'BullAgent',
    'BearAgent',
    'AnalystAgent',
    'RiskDoctor',
    'QuantumEngine',
    'BacktestEngine',
    'MonteCarloSimulator',
    'KellyCriterion'
]
