# -*- coding: utf-8 -*-
"""
SQLAlchemy Database Models for VN-QUANT
========================================
Production-grade database schema for trading system.

Tables:
- orders: Order history
- positions: Position tracking
- trades: Executed trades
- agent_signals: Agent signal history
- portfolio_snapshots: Daily portfolio snapshots
- circuit_breaker_events: Risk events
- performance_metrics: Agent performance tracking
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Text, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

Base = declarative_base()


# ====================================
# ENUMS
# ====================================

class OrderType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    WAITING_SETTLE = "WAITING_SETTLE"


class SignalType(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class CircuitBreakerLevel(str, Enum):
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    HALT = "HALT"
    EMERGENCY = "EMERGENCY"


# ====================================
# MODELS
# ====================================

class Order(Base):
    """Order table - all order history"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(50), unique=True, nullable=False, index=True)

    # Order details
    order_type = Column(SQLEnum(OrderType), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)

    # Status
    status = Column(SQLEnum(OrderStatus), nullable=False, index=True)
    filled_quantity = Column(Integer, default=0)
    filled_price = Column(Float, nullable=True)

    # Fees & costs
    commission = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    total_fees = Column(Float, default=0.0)

    # Metadata
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    filled_at = Column(DateTime, nullable=True)

    # Strategy info
    strategy = Column(String(100), nullable=True)
    agent_name = Column(String(50), nullable=True)
    signal_id = Column(String(50), nullable=True)

    # Message/reason
    message = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_orders_symbol_status', 'symbol', 'status'),
        Index('idx_orders_created_at', 'created_at'),
    )


class Position(Base):
    """Position table - current and historical positions"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Position details
    symbol = Column(String(20), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    avg_price = Column(Float, nullable=False)

    # P&L
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, default=0.0)
    unrealized_pnl_pct = Column(Float, default=0.0)

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Metadata
    opened_at = Column(DateTime, default=datetime.now, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Settlement
    settlement_date = Column(DateTime, nullable=True)
    is_settled = Column(Boolean, default=False)

    __table_args__ = (
        Index('idx_positions_symbol_active', 'symbol', 'is_active'),
    )


class Trade(Base):
    """Trade table - executed trades with P&L"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(50), unique=True, nullable=False, index=True)

    # Trade details
    symbol = Column(String(20), nullable=False, index=True)
    order_id = Column(String(50), ForeignKey('orders.order_id'), nullable=False)

    # Entry/Exit
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=False)

    # P&L
    realized_pnl = Column(Float, default=0.0)
    realized_pnl_pct = Column(Float, default=0.0)

    # Fees
    total_fees = Column(Float, default=0.0)

    # Timing
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    holding_days = Column(Float, nullable=True)

    # Strategy
    strategy = Column(String(100), nullable=True)
    agent_name = Column(String(50), nullable=True)

    __table_args__ = (
        Index('idx_trades_symbol_entry', 'symbol', 'entry_time'),
    )


class AgentSignal(Base):
    """Agent signal history"""
    __tablename__ = "agent_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(50), unique=True, nullable=False, index=True)

    # Agent info
    agent_name = Column(String(50), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)

    # Signal details
    signal_type = Column(SQLEnum(SignalType), nullable=False)
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)

    # Context
    price_at_signal = Column(Float, nullable=False)

    # Outcome tracking
    outcome_price = Column(Float, nullable=True)
    outcome_pnl_pct = Column(Float, nullable=True)
    was_correct = Column(Boolean, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    evaluated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_signals_agent_symbol', 'agent_name', 'symbol'),
        Index('idx_signals_created_at', 'created_at'),
    )


class PortfolioSnapshot(Base):
    """Daily portfolio snapshots"""
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Portfolio metrics
    total_value = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False)

    # P&L
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    total_pnl_pct = Column(Float, default=0.0)

    # Risk metrics
    num_positions = Column(Integer, default=0)
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, nullable=True)

    # Timestamp
    snapshot_date = Column(DateTime, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)


class CircuitBreakerEvent(Base):
    """Circuit breaker events"""
    __tablename__ = "circuit_breaker_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Event details
    level = Column(SQLEnum(CircuitBreakerLevel), nullable=False)
    trigger_reason = Column(String(200), nullable=False)

    # Portfolio state
    portfolio_value = Column(Float, nullable=False)
    daily_pnl_pct = Column(Float, nullable=False)
    max_drawdown_pct = Column(Float, nullable=False)

    # Actions taken
    actions_taken = Column(Text, nullable=True)
    positions_closed = Column(Integer, default=0)

    # Timing
    triggered_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)

    # Resolution
    is_resolved = Column(Boolean, default=False)
    resolution_method = Column(String(100), nullable=True)


class AgentPerformance(Base):
    """Agent performance metrics (daily aggregation)"""
    __tablename__ = "agent_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Agent info
    agent_name = Column(String(50), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)

    # Signal metrics
    total_signals = Column(Integer, default=0)
    correct_signals = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)

    # Performance metrics
    total_return = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, nullable=True)
    max_drawdown = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)

    # Confidence metrics
    avg_confidence = Column(Float, default=0.0)

    # Metadata
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    __table_args__ = (
        UniqueConstraint('agent_name', 'date', name='uq_agent_date'),
        Index('idx_perf_agent_date', 'agent_name', 'date'),
    )


class DataQuality(Base):
    """Data quality metrics"""
    __tablename__ = "data_quality"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Data source
    source = Column(String(50), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)

    # Quality metrics
    completeness_pct = Column(Float, default=100.0)
    timeliness_seconds = Column(Float, nullable=True)
    accuracy_score = Column(Float, nullable=True)

    # Issues
    missing_fields = Column(Text, nullable=True)
    anomalies = Column(Text, nullable=True)

    # Timestamp
    checked_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('idx_quality_source_symbol', 'source', 'symbol'),
    )


class SystemLog(Base):
    """System audit log"""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Log details
    level = Column(String(20), nullable=False, index=True)
    component = Column(String(100), nullable=False, index=True)
    message = Column(Text, nullable=False)

    # Context
    user = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Additional data (JSON)
    extra_data = Column(Text, nullable=True)

    # Stack trace (for errors)
    stack_trace = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.now, nullable=False, index=True)

    __table_args__ = (
        Index('idx_logs_level_created', 'level', 'created_at'),
    )


# ====================================
# HELPER FUNCTIONS
# ====================================

def create_all_tables(engine):
    """Create all tables"""
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """Drop all tables (use with caution!)"""
    Base.metadata.drop_all(engine)


__all__ = [
    "Base",
    "Order",
    "Position",
    "Trade",
    "AgentSignal",
    "PortfolioSnapshot",
    "CircuitBreakerEvent",
    "AgentPerformance",
    "DataQuality",
    "SystemLog",
    "OrderType",
    "OrderStatus",
    "SignalType",
    "CircuitBreakerLevel",
    "create_all_tables",
    "drop_all_tables"
]
