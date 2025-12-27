# -*- coding: utf-8 -*-
"""
Advanced Logging System for VN-QUANT
=====================================
Production-grade logging with loguru + structured logging

Features:
- JSON formatting for machine parsing
- Rotation by size and time
- Compression of old logs
- Separate files for errors
- Performance tracking
- Request ID tracking
- Sensitive data filtering
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
import contextvars

# Context variable for request/trade tracking
request_id_var = contextvars.ContextVar('request_id', default=None)
trade_id_var = contextvars.ContextVar('trade_id', default=None)


class VNQuantLogger:
    """
    Production-ready logging system for VN-QUANT

    Features:
    - Multiple output formats (console, JSON file, error file)
    - Automatic log rotation
    - Performance metrics
    - Trade tracking
    - Sensitive data filtering
    """

    def __init__(
        self,
        log_dir: str = "logs",
        level: str = "INFO",
        rotation: str = "100 MB",
        retention: str = "30 days",
        compression: str = "zip",
        enable_json: bool = True
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)
        self.level = level
        self.enable_json = enable_json

        # Remove default handler
        logger.remove()

        # Console handler with colorful output
        logger.add(
            sys.stderr,
            format=self._get_console_format(),
            level=level,
            colorize=True,
            backtrace=True,
            diagnose=True
        )

        # Main log file (all levels)
        logger.add(
            self.log_dir / "vnquant_{time:YYYY-MM-DD}.log",
            format=self._get_file_format(),
            level=level,
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
            backtrace=True,
            diagnose=True
        )

        # JSON log file for machine parsing
        if enable_json:
            logger.add(
                self.log_dir / "vnquant_{time:YYYY-MM-DD}.json",
                format="{message}",
                level=level,
                rotation=rotation,
                retention=retention,
                compression=compression,
                encoding="utf-8",
                serialize=False,  # We'll handle JSON ourselves
                filter=self._json_filter
            )

        # Error log file (ERROR and CRITICAL only)
        logger.add(
            self.log_dir / "errors_{time:YYYY-MM-DD}.log",
            format=self._get_file_format(),
            level="ERROR",
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
            backtrace=True,
            diagnose=True
        )

        # Trading log file (for trade-related events)
        logger.add(
            self.log_dir / "trading_{time:YYYY-MM-DD}.log",
            format=self._get_file_format(),
            level="INFO",
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
            filter=lambda record: "trade" in record["extra"]
        )

        # Performance log file
        logger.add(
            self.log_dir / "performance_{time:YYYY-MM-DD}.log",
            format=self._get_file_format(),
            level="INFO",
            rotation=rotation,
            retention=retention,
            compression=compression,
            encoding="utf-8",
            filter=lambda record: "performance" in record["extra"]
        )

        logger.info("VNQuantLogger initialized", extra={
            "log_dir": str(self.log_dir),
            "level": level,
            "json_enabled": enable_json
        })

    @staticmethod
    def _get_console_format() -> str:
        """Console format with colors and emojis"""
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    @staticmethod
    def _get_file_format() -> str:
        """File format without colors"""
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        )

    def _json_filter(self, record: Dict) -> bool:
        """Convert log record to JSON format"""
        # Build JSON log entry
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
            "extra": record["extra"]
        }

        # Add request/trade IDs if available
        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id

        trade_id = trade_id_var.get()
        if trade_id:
            log_entry["trade_id"] = trade_id

        # Add exception info if present
        if record["exception"]:
            log_entry["exception"] = {
                "type": record["exception"].type.__name__,
                "value": str(record["exception"].value),
                "traceback": record["exception"].traceback
            }

        # Filter sensitive data
        log_entry = self._filter_sensitive_data(log_entry)

        # Update record message with JSON
        record["message"] = json.dumps(log_entry, ensure_ascii=False, default=str)
        return True

    @staticmethod
    def _filter_sensitive_data(data: Dict) -> Dict:
        """Remove sensitive information from logs"""
        sensitive_keys = [
            "password", "token", "api_key", "secret",
            "authorization", "cookie", "session"
        ]

        def filter_dict(d: Dict) -> Dict:
            return {
                k: "***FILTERED***" if any(s in k.lower() for s in sensitive_keys) else v
                for k, v in d.items()
            }

        if "extra" in data and isinstance(data["extra"], dict):
            data["extra"] = filter_dict(data["extra"])

        return data


class TradingLogger:
    """
    Specialized logger for trading operations

    Usage:
        with TradingLogger.trade_context(order_id="ORD123", symbol="VCB"):
            logger.info("Placing order", extra={"trade": True})
    """

    @staticmethod
    def trade_context(order_id: str, symbol: str = None):
        """Context manager for trade logging"""
        class TradeContext:
            def __init__(self, order_id: str, symbol: str = None):
                self.order_id = order_id
                self.symbol = symbol
                self.start_time = None

            def __enter__(self):
                self.start_time = datetime.now()
                trade_id_var.set(self.order_id)
                logger.bind(trade=True, order_id=self.order_id, symbol=self.symbol)
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = (datetime.now() - self.start_time).total_seconds()
                logger.bind(
                    trade=True,
                    order_id=self.order_id,
                    duration_seconds=duration,
                    success=exc_type is None
                )
                trade_id_var.set(None)

        return TradeContext(order_id, symbol)

    @staticmethod
    def log_order(order_type: str, symbol: str, quantity: int, price: float, **kwargs):
        """Log order placement"""
        logger.info(
            f"Order {order_type}: {symbol} x{quantity} @ {price:,.0f}",
            extra={
                "trade": True,
                "order_type": order_type,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                **kwargs
            }
        )

    @staticmethod
    def log_fill(order_id: str, symbol: str, quantity: int, price: float, **kwargs):
        """Log order fill"""
        logger.info(
            f"Order filled: {order_id} - {symbol} x{quantity} @ {price:,.0f}",
            extra={
                "trade": True,
                "event": "fill",
                "order_id": order_id,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                **kwargs
            }
        )

    @staticmethod
    def log_rejection(order_id: str, symbol: str, reason: str, **kwargs):
        """Log order rejection"""
        logger.warning(
            f"Order rejected: {order_id} - {symbol}: {reason}",
            extra={
                "trade": True,
                "event": "rejection",
                "order_id": order_id,
                "symbol": symbol,
                "reason": reason,
                **kwargs
            }
        )


class PerformanceLogger:
    """
    Performance metrics logger

    Usage:
        with PerformanceLogger.measure("api_call"):
            # ... code to measure ...
    """

    @staticmethod
    def measure(operation: str, **kwargs):
        """Context manager for performance measurement"""
        class PerfContext:
            def __init__(self, operation: str, **kwargs):
                self.operation = operation
                self.kwargs = kwargs
                self.start_time = None

            def __enter__(self):
                self.start_time = datetime.now()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000
                logger.info(
                    f"Performance: {self.operation} took {duration_ms:.2f}ms",
                    extra={
                        "performance": True,
                        "operation": self.operation,
                        "duration_ms": duration_ms,
                        "success": exc_type is None,
                        **self.kwargs
                    }
                )

        return PerfContext(operation, **kwargs)


# Global logger instance
_global_logger: Optional[VNQuantLogger] = None


def setup_logger(
    log_dir: str = "logs",
    level: str = "INFO",
    **kwargs
) -> VNQuantLogger:
    """
    Setup global logger

    Args:
        log_dir: Directory for log files
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        **kwargs: Additional arguments for VNQuantLogger

    Returns:
        VNQuantLogger instance
    """
    global _global_logger
    _global_logger = VNQuantLogger(log_dir=log_dir, level=level, **kwargs)
    return _global_logger


def get_logger():
    """Get the global logger instance"""
    if _global_logger is None:
        setup_logger()
    return logger


# Convenience exports
__all__ = [
    "setup_logger",
    "get_logger",
    "logger",
    "TradingLogger",
    "PerformanceLogger",
    "VNQuantLogger"
]
