# -*- coding: utf-8 -*-
"""
Database Connection Manager for VN-QUANT
=========================================
Production-grade database connection handling with pooling.

Features:
- Connection pooling
- Auto-reconnect
- Health checks
- Migration support
- Session management
"""

from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from contextlib import contextmanager
from typing import Optional, Dict, Any
import time
from loguru import logger

from .models import Base, create_all_tables


class DatabaseManager:
    """
    Database connection manager with pooling and health checks

    Usage:
        db_manager = DatabaseManager(database_url)
        with db_manager.get_session() as session:
            # ... use session ...
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False
    ):
        """
        Initialize database manager

        Args:
            database_url: SQLAlchemy database URL
            pool_size: Number of connections in pool
            max_overflow: Max connections beyond pool_size
            pool_timeout: Timeout for getting connection (seconds)
            pool_recycle: Recycle connections after N seconds
            echo: Log all SQL statements
        """
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow

        # Create engine with connection pooling
        self.engine = create_engine(
            database_url,
            poolclass=pool.QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Test connections before using
            echo=echo,
            connect_args={
                "connect_timeout": 10,
                "options": "-c timezone=utc"
            } if "postgresql" in database_url else {}
        )

        # Setup event listeners
        self._setup_event_listeners()

        # Create session factory
        session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )

        # Thread-safe session
        self.Session = scoped_session(session_factory)

        logger.info(f"Database manager initialized: {self._safe_url()}")

    def _safe_url(self) -> str:
        """Get URL with hidden password"""
        parts = self.database_url.split("@")
        if len(parts) == 2:
            return f"***@{parts[1]}"
        return "***"

    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners"""

        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            logger.debug("Database connection established")

        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            logger.debug("Connection checked out from pool")

        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            logger.debug("Connection returned to pool")

    @contextmanager
    def get_session(self) -> Session:
        """
        Get database session context manager

        Usage:
            with db_manager.get_session() as session:
                # ... use session ...
                session.commit()

        Automatically handles:
        - Session creation
        - Commit on success
        - Rollback on error
        - Session cleanup
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def create_tables(self):
        """Create all tables"""
        try:
            create_all_tables(self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise

    def drop_tables(self):
        """Drop all tables (use with caution!)"""
        try:
            Base.metadata.drop_all(self.engine)
            logger.warning("All database tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop tables: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """
        Check database health

        Returns:
            Dict with health status
        """
        start_time = time.time()

        try:
            with self.get_session() as session:
                # Simple query to test connection
                session.execute("SELECT 1")

            latency_ms = (time.time() - start_time) * 1000

            pool_status = self.engine.pool.status()

            return {
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "pool_size": self.pool_size,
                "pool_status": pool_status,
                "url": self._safe_url()
            }

        except OperationalError as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "url": self._safe_url()
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": self._safe_url()
            }

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        try:
            pool = self.engine.pool
            return {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "max_overflow": self.max_overflow,
                "pool_size": self.pool_size
            }
        except Exception as e:
            logger.error(f"Failed to get pool stats: {e}")
            return {}

    def close(self):
        """Close all connections and dispose engine"""
        try:
            self.Session.remove()
            self.engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")


class DatabaseRepository:
    """
    Base repository class for database operations

    Provides common CRUD operations
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    @contextmanager
    def session_scope(self):
        """Session scope context manager"""
        with self.db_manager.get_session() as session:
            yield session

    def create(self, obj):
        """Create object"""
        with self.session_scope() as session:
            session.add(obj)
            session.flush()
            session.refresh(obj)
            return obj

    def bulk_create(self, objects: list):
        """Bulk create objects"""
        with self.session_scope() as session:
            session.bulk_save_objects(objects)
            return len(objects)

    def get_by_id(self, model, obj_id):
        """Get object by ID"""
        with self.session_scope() as session:
            return session.query(model).filter(model.id == obj_id).first()

    def get_all(self, model, limit: int = 100, offset: int = 0):
        """Get all objects with pagination"""
        with self.session_scope() as session:
            return session.query(model).limit(limit).offset(offset).all()

    def update(self, obj):
        """Update object"""
        with self.session_scope() as session:
            session.merge(obj)
            return obj

    def delete(self, obj):
        """Delete object"""
        with self.session_scope() as session:
            session.delete(obj)

    def count(self, model):
        """Count objects"""
        with self.session_scope() as session:
            return session.query(model).count()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def init_database(
    database_url: str,
    create_tables: bool = False,
    **kwargs
) -> DatabaseManager:
    """
    Initialize global database manager

    Args:
        database_url: Database connection URL
        create_tables: Whether to create tables
        **kwargs: Additional arguments for DatabaseManager

    Returns:
        DatabaseManager instance
    """
    global _db_manager

    _db_manager = DatabaseManager(database_url, **kwargs)

    if create_tables:
        _db_manager.create_tables()

    return _db_manager


def get_db_manager() -> DatabaseManager:
    """
    Get global database manager

    Returns:
        DatabaseManager instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db_manager


def get_db_session():
    """Get database session (for dependency injection)"""
    db_manager = get_db_manager()
    return db_manager.get_session()


__all__ = [
    "DatabaseManager",
    "DatabaseRepository",
    "init_database",
    "get_db_manager",
    "get_db_session"
]
