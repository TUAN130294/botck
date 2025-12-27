# Database Module
try:
    from .database import (
        DatabaseManager,
        get_db,
        get_session,
        User,
        Watchlist,
        Alert,
        Portfolio,
        Position,
        Trade,
        Signal,
        BacktestResult,
        UserRepository,
        AlertRepository,
        TradeRepository,
        SignalRepository,
        migrate_from_json
    )
    
    __all__ = [
        'DatabaseManager',
        'get_db',
        'get_session',
        'User',
        'Watchlist', 
        'Alert',
        'Portfolio',
        'Position',
        'Trade',
        'Signal',
        'BacktestResult',
        'UserRepository',
        'AlertRepository',
        'TradeRepository',
        'SignalRepository',
        'migrate_from_json'
    ]
except ImportError:
    # SQLAlchemy not available
    __all__ = []
