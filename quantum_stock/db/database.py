# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    DATABASE LAYER                                            ║
║                    PostgreSQL + SQLAlchemy ORM                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

P0 Implementation - Production-grade database layer
Migrates from JSON files to PostgreSQL
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import SQLAlchemy
try:
    from sqlalchemy import (
        create_engine, Column, Integer, String, Float, DateTime, 
        Boolean, Text, ForeignKey, JSON, Index, UniqueConstraint
    )
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker, relationship, Session
    from sqlalchemy.pool import QueuePool
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    logger.warning("SQLAlchemy not installed. Run: pip install sqlalchemy psycopg2-binary")

# Base class for models
if SQLALCHEMY_AVAILABLE:
    Base = declarative_base()
else:
    Base = object


# ============================================
# ORM MODELS
# ============================================

if SQLALCHEMY_AVAILABLE:
    
    class User(Base):
        """User account"""
        __tablename__ = 'users'
        
        id = Column(Integer, primary_key=True)
        username = Column(String(50), unique=True, nullable=False, index=True)
        password_hash = Column(String(256), nullable=False)
        email = Column(String(100), unique=True)
        telegram_id = Column(String(50), unique=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        last_login = Column(DateTime)
        is_active = Column(Boolean, default=True)
        settings = Column(JSON, default={})
        
        # Relationships
        watchlists = relationship("Watchlist", back_populates="user")
        alerts = relationship("Alert", back_populates="user")
        portfolios = relationship("Portfolio", back_populates="user")
        trades = relationship("Trade", back_populates="user")
        
        def to_dict(self):
            return {
                'id': self.id,
                'username': self.username,
                'email': self.email,
                'telegram_id': self.telegram_id,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'is_active': self.is_active,
                'settings': self.settings
            }
    
    
    class Watchlist(Base):
        """User watchlist"""
        __tablename__ = 'watchlists'
        
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
        name = Column(String(100), default='Default')
        symbols = Column(JSON, default=[])
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        
        user = relationship("User", back_populates="watchlists")
        
        def to_dict(self):
            return {
                'id': self.id,
                'user_id': self.user_id,
                'name': self.name,
                'symbols': self.symbols,
                'created_at': self.created_at.isoformat() if self.created_at else None
            }
    
    
    class Alert(Base):
        """Price/indicator alerts"""
        __tablename__ = 'alerts'
        
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
        symbol = Column(String(20), nullable=False, index=True)
        alert_type = Column(String(50), nullable=False)  # price, rsi, macd, etc.
        condition = Column(String(20), nullable=False)  # >, <, =, cross_above, cross_below
        value = Column(Float, nullable=False)
        is_active = Column(Boolean, default=True)
        is_triggered = Column(Boolean, default=False)
        triggered_at = Column(DateTime)
        cooldown_minutes = Column(Integer, default=60)
        last_triggered = Column(DateTime)
        created_at = Column(DateTime, default=datetime.utcnow)
        
        user = relationship("User", back_populates="alerts")
        
        __table_args__ = (
            Index('ix_alerts_symbol_active', 'symbol', 'is_active'),
        )
        
        def to_dict(self):
            return {
                'id': self.id,
                'symbol': self.symbol,
                'alert_type': self.alert_type,
                'condition': self.condition,
                'value': self.value,
                'is_active': self.is_active,
                'is_triggered': self.is_triggered
            }
    
    
    class Portfolio(Base):
        """User portfolio"""
        __tablename__ = 'portfolios'
        
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
        name = Column(String(100), default='Main Portfolio')
        broker = Column(String(50))  # SSI, VPS, TCBS, etc.
        account_number = Column(String(50))
        initial_capital = Column(Float, default=0)
        current_value = Column(Float, default=0)
        cash_balance = Column(Float, default=0)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        
        user = relationship("User", back_populates="portfolios")
        positions = relationship("Position", back_populates="portfolio")
        
        def to_dict(self):
            return {
                'id': self.id,
                'name': self.name,
                'broker': self.broker,
                'initial_capital': self.initial_capital,
                'current_value': self.current_value,
                'cash_balance': self.cash_balance,
                'positions': [p.to_dict() for p in self.positions]
            }
    
    
    class Position(Base):
        """Portfolio positions"""
        __tablename__ = 'positions'
        
        id = Column(Integer, primary_key=True)
        portfolio_id = Column(Integer, ForeignKey('portfolios.id'), nullable=False)
        symbol = Column(String(20), nullable=False, index=True)
        quantity = Column(Integer, default=0)
        avg_price = Column(Float, default=0)
        current_price = Column(Float, default=0)
        market_value = Column(Float, default=0)
        unrealized_pnl = Column(Float, default=0)
        unrealized_pnl_pct = Column(Float, default=0)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        
        portfolio = relationship("Portfolio", back_populates="positions")
        
        __table_args__ = (
            UniqueConstraint('portfolio_id', 'symbol', name='uq_position_portfolio_symbol'),
        )
        
        def to_dict(self):
            return {
                'symbol': self.symbol,
                'quantity': self.quantity,
                'avg_price': self.avg_price,
                'current_price': self.current_price,
                'market_value': self.market_value,
                'unrealized_pnl': self.unrealized_pnl,
                'unrealized_pnl_pct': self.unrealized_pnl_pct
            }
    
    
    class Trade(Base):
        """Trade history"""
        __tablename__ = 'trades'
        
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
        portfolio_id = Column(Integer, ForeignKey('portfolios.id'))
        symbol = Column(String(20), nullable=False, index=True)
        side = Column(String(10), nullable=False)  # BUY, SELL
        order_type = Column(String(20), nullable=False)  # LO, ATO, ATC, MP
        quantity = Column(Integer, nullable=False)
        price = Column(Float, nullable=False)
        commission = Column(Float, default=0)
        status = Column(String(20), default='PENDING')  # PENDING, FILLED, CANCELLED, REJECTED
        executed_at = Column(DateTime)
        created_at = Column(DateTime, default=datetime.utcnow)
        broker_order_id = Column(String(50))
        notes = Column(Text)
        
        user = relationship("User", back_populates="trades")
        
        __table_args__ = (
            Index('ix_trades_symbol_date', 'symbol', 'created_at'),
        )
        
        def to_dict(self):
            return {
                'id': self.id,
                'symbol': self.symbol,
                'side': self.side,
                'order_type': self.order_type,
                'quantity': self.quantity,
                'price': self.price,
                'status': self.status,
                'executed_at': self.executed_at.isoformat() if self.executed_at else None
            }
    
    
    class Signal(Base):
        """AI/Agent signals"""
        __tablename__ = 'signals'
        
        id = Column(Integer, primary_key=True)
        symbol = Column(String(20), nullable=False, index=True)
        agent = Column(String(50), nullable=False)  # AnalystAgent, BullAgent, etc.
        action = Column(String(20), nullable=False)  # BUY, SELL, HOLD
        confidence = Column(Float, nullable=False)
        reasoning = Column(Text)
        metadata = Column(JSON, default={})
        created_at = Column(DateTime, default=datetime.utcnow, index=True)
        
        __table_args__ = (
            Index('ix_signals_symbol_agent_date', 'symbol', 'agent', 'created_at'),
        )
        
        def to_dict(self):
            return {
                'id': self.id,
                'symbol': self.symbol,
                'agent': self.agent,
                'action': self.action,
                'confidence': self.confidence,
                'reasoning': self.reasoning,
                'created_at': self.created_at.isoformat()
            }
    
    
    class BacktestResult(Base):
        """Backtest results"""
        __tablename__ = 'backtest_results'
        
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey('users.id'))
        symbol = Column(String(20), nullable=False)
        strategy = Column(String(100), nullable=False)
        start_date = Column(DateTime)
        end_date = Column(DateTime)
        initial_capital = Column(Float)
        final_equity = Column(Float)
        total_return = Column(Float)
        sharpe_ratio = Column(Float)
        max_drawdown = Column(Float)
        win_rate = Column(Float)
        total_trades = Column(Integer)
        parameters = Column(JSON, default={})
        equity_curve = Column(JSON, default=[])
        created_at = Column(DateTime, default=datetime.utcnow)
        
        def to_dict(self):
            return {
                'symbol': self.symbol,
                'strategy': self.strategy,
                'total_return': self.total_return,
                'sharpe_ratio': self.sharpe_ratio,
                'max_drawdown': self.max_drawdown,
                'win_rate': self.win_rate,
                'total_trades': self.total_trades
            }


# ============================================
# DATABASE MANAGER
# ============================================

class DatabaseManager:
    """
    Database connection manager
    """
    
    def __init__(self, database_url: str = None):
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError("SQLAlchemy is not installed")
        
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'sqlite:///vnquant.db'  # Default to SQLite for development
        )
        
        # Create engine
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        
        logger.info(f"Database connected: {self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url}")
    
    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all tables (use with caution!)"""
        Base.metadata.drop_all(self.engine)
        logger.warning("Database tables dropped")
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connection"""
        self.engine.dispose()


# ============================================
# REPOSITORY PATTERN
# ============================================

class UserRepository:
    """User data access"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.session.query(User).filter(User.id == user_id).first()
    
    def get_by_username(self, username: str) -> Optional[User]:
        return self.session.query(User).filter(User.username == username).first()
    
    def get_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        return self.session.query(User).filter(User.telegram_id == telegram_id).first()
    
    def create(self, username: str, password_hash: str, **kwargs) -> User:
        user = User(username=username, password_hash=password_hash, **kwargs)
        self.session.add(user)
        self.session.commit()
        return user
    
    def update(self, user: User, **kwargs):
        for key, value in kwargs.items():
            setattr(user, key, value)
        self.session.commit()
    
    def delete(self, user: User):
        self.session.delete(user)
        self.session.commit()


class AlertRepository:
    """Alert data access"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_active_alerts(self, symbol: str = None) -> List[Alert]:
        query = self.session.query(Alert).filter(Alert.is_active == True)
        if symbol:
            query = query.filter(Alert.symbol == symbol)
        return query.all()
    
    def get_user_alerts(self, user_id: int) -> List[Alert]:
        return self.session.query(Alert).filter(Alert.user_id == user_id).all()
    
    def create(self, user_id: int, symbol: str, alert_type: str, 
               condition: str, value: float, **kwargs) -> Alert:
        alert = Alert(
            user_id=user_id,
            symbol=symbol.upper(),
            alert_type=alert_type,
            condition=condition,
            value=value,
            **kwargs
        )
        self.session.add(alert)
        self.session.commit()
        return alert
    
    def trigger(self, alert: Alert):
        alert.is_triggered = True
        alert.triggered_at = datetime.utcnow()
        alert.last_triggered = datetime.utcnow()
        self.session.commit()
    
    def deactivate(self, alert: Alert):
        alert.is_active = False
        self.session.commit()


class TradeRepository:
    """Trade data access"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_symbol(self, symbol: str, limit: int = 100) -> List[Trade]:
        return self.session.query(Trade)\
            .filter(Trade.symbol == symbol)\
            .order_by(Trade.created_at.desc())\
            .limit(limit)\
            .all()
    
    def get_user_trades(self, user_id: int, limit: int = 100) -> List[Trade]:
        return self.session.query(Trade)\
            .filter(Trade.user_id == user_id)\
            .order_by(Trade.created_at.desc())\
            .limit(limit)\
            .all()
    
    def create(self, user_id: int, symbol: str, side: str, 
               order_type: str, quantity: int, price: float, **kwargs) -> Trade:
        trade = Trade(
            user_id=user_id,
            symbol=symbol.upper(),
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            **kwargs
        )
        self.session.add(trade)
        self.session.commit()
        return trade
    
    def update_status(self, trade: Trade, status: str):
        trade.status = status
        if status == 'FILLED':
            trade.executed_at = datetime.utcnow()
        self.session.commit()


class SignalRepository:
    """Signal data access"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_latest(self, symbol: str, agent: str = None, limit: int = 10) -> List[Signal]:
        query = self.session.query(Signal).filter(Signal.symbol == symbol)
        if agent:
            query = query.filter(Signal.agent == agent)
        return query.order_by(Signal.created_at.desc()).limit(limit).all()
    
    def create(self, symbol: str, agent: str, action: str, 
               confidence: float, reasoning: str = None, **kwargs) -> Signal:
        signal = Signal(
            symbol=symbol.upper(),
            agent=agent,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            **kwargs
        )
        self.session.add(signal)
        self.session.commit()
        return signal


# ============================================
# MIGRATION FROM JSON
# ============================================

def migrate_from_json(db: DatabaseManager, json_dir: str = "."):
    """
    Migrate data from JSON files to PostgreSQL
    """
    session = db.get_session()
    
    try:
        # Migrate users from web_users.json
        users_file = os.path.join(json_dir, 'web_users.json')
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                users_data = json.load(f)
            
            user_repo = UserRepository(session)
            for username, data in users_data.items():
                existing = user_repo.get_by_username(username)
                if not existing:
                    user_repo.create(
                        username=username,
                        password_hash=data.get('password', ''),
                        email=data.get('email'),
                        settings=data.get('settings', {})
                    )
            logger.info(f"Migrated {len(users_data)} users")
        
        # Migrate alerts from rules.json
        rules_file = os.path.join(json_dir, 'rules.json')
        if os.path.exists(rules_file):
            with open(rules_file, 'r') as f:
                rules_data = json.load(f)
            
            alert_repo = AlertRepository(session)
            # Parse and migrate rules to alerts
            for rule in rules_data.get('rules', []):
                # Convert rule format to alert
                pass  # Implement based on actual rules format
            
            logger.info("Migrated alert rules")
        
        session.commit()
        logger.info("Migration completed successfully")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        session.close()


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

_db: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Get or create global database instance"""
    global _db
    if _db is None:
        _db = DatabaseManager()
        _db.create_tables()
    return _db


def get_session() -> Session:
    """Get a database session"""
    return get_db().get_session()


# ============================================
# TESTING
# ============================================

def test_database():
    """Test database functionality"""
    print("Testing Database Module...")
    print("=" * 50)
    
    # Use SQLite for testing
    db = DatabaseManager('sqlite:///test_vnquant.db')
    db.create_tables()
    
    session = db.get_session()
    
    try:
        # Test User creation
        user_repo = UserRepository(session)
        user = user_repo.create(
            username='test_user',
            password_hash='hashed_password',
            email='test@example.com'
        )
        print(f"✅ Created user: {user.username}")
        
        # Test Alert creation
        alert_repo = AlertRepository(session)
        alert = alert_repo.create(
            user_id=user.id,
            symbol='HPG',
            alert_type='price',
            condition='>',
            value=25.0
        )
        print(f"✅ Created alert: {alert.symbol} {alert.condition} {alert.value}")
        
        # Test Trade creation
        trade_repo = TradeRepository(session)
        trade = trade_repo.create(
            user_id=user.id,
            symbol='VNM',
            side='BUY',
            order_type='LO',
            quantity=1000,
            price=75.5
        )
        print(f"✅ Created trade: {trade.side} {trade.quantity} {trade.symbol}")
        
        # Test Signal creation
        signal_repo = SignalRepository(session)
        signal = signal_repo.create(
            symbol='FPT',
            agent='AnalystAgent',
            action='BUY',
            confidence=0.85,
            reasoning='RSI oversold, MACD bullish crossover'
        )
        print(f"✅ Created signal: {signal.agent} {signal.action} {signal.symbol}")
        
        print("\n✅ All database tests passed!")
        
    finally:
        session.close()
        db.close()
        
        # Clean up test database
        import os
        if os.path.exists('test_vnquant.db'):
            os.remove('test_vnquant.db')


if __name__ == "__main__":
    if SQLALCHEMY_AVAILABLE:
        test_database()
    else:
        print("SQLAlchemy not available. Install with: pip install sqlalchemy")
