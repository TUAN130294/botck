"""
Quantum Core Engine - Advanced Analysis and Simulation
Agentic Level 3-4-5 Support
"""

from .quantum_engine import QuantumEngine
from .backtest_engine import BacktestEngine, BacktestResult, Strategy
from .monte_carlo import MonteCarloSimulator, SimulationResult
from .kelly_criterion import KellyCriterion, PositionSizeResult
from .walk_forward import WalkForwardOptimizer, WFOResult

# Agentic Level 4-5 Components
from .forecasting import (
    ForecastingEngine, ForecastResult, ModelType,
    ARIMAForecaster, ProphetForecaster, LSTMForecaster,
    GBMForecaster, EnsembleForecaster
)
from .broker_api import (
    BrokerAPI, PaperTradingBroker, BrokerFactory,
    Order, Position, AccountInfo,
    OrderSide, OrderType, OrderStatus
)

# Portfolio Optimization (P2)
try:
    from .portfolio_optimizer import (
        PortfolioOptimizer, OptimizationResult,
        PortfolioRiskAnalyzer
    )
except ImportError:
    pass

# Execution Engine (P1)
try:
    from .execution_engine import (
        ExecutionEngine, OrderManager, PositionManager,
        RiskController, TradingSignal
    )
except ImportError:
    pass

__all__ = [
    # Core Engine
    'QuantumEngine',
    # Backtesting
    'BacktestEngine',
    'BacktestResult',
    'Strategy',
    # Monte Carlo
    'MonteCarloSimulator',
    'SimulationResult',
    # Kelly Criterion
    'KellyCriterion',
    'PositionSizeResult',
    # Walk Forward
    'WalkForwardOptimizer',
    'WFOResult',
    # Forecasting (L4)
    'ForecastingEngine',
    'ForecastResult',
    'ModelType',
    'ARIMAForecaster',
    'ProphetForecaster',
    'LSTMForecaster',
    'GBMForecaster',
    'EnsembleForecaster',
    # Broker API (L5)
    'BrokerAPI',
    'PaperTradingBroker',
    'BrokerFactory',
    'Order',
    'Position',
    'AccountInfo',
    'OrderSide',
    'OrderType',
    'OrderStatus'
]
