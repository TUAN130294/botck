# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MONITORING & OBSERVABILITY                                ║
║                    Metrics, Logging, Alerting                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Features:
- Prometheus metrics export
- Structured logging
- Error tracking (Sentry integration)
- Performance monitoring
- Trading activity tracking
"""

import os
import time
import logging
import functools
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import json

# ============================================
# STRUCTURED LOGGING
# ============================================

class StructuredLogger:
    """JSON structured logger for better observability"""
    
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Create console handler with JSON format
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(self._json_formatter())
            self.logger.addHandler(handler)
    
    def _json_formatter(self):
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                }
                
                if hasattr(record, 'extra'):
                    log_data.update(record.extra)
                
                if record.exc_info:
                    log_data['exception'] = self.formatException(record.exc_info)
                
                return json.dumps(log_data)
        
        return JsonFormatter()
    
    def info(self, message: str, **kwargs):
        self.logger.info(message, extra={'extra': kwargs})
    
    def error(self, message: str, **kwargs):
        self.logger.error(message, extra={'extra': kwargs})
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(message, extra={'extra': kwargs})
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(message, extra={'extra': kwargs})


# ============================================
# METRICS COLLECTOR
# ============================================

@dataclass
class MetricPoint:
    """Single metric data point"""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram


class MetricsCollector:
    """
    Collect and export metrics (Prometheus compatible)
    """
    
    def __init__(self):
        self.metrics: Dict[str, MetricPoint] = {}
        self.counters: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, list] = defaultdict(list)
        self._start_time = time.time()
    
    def gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric"""
        self.metrics[name] = MetricPoint(
            name=name,
            value=value,
            timestamp=datetime.now(),
            labels=labels or {},
            metric_type="gauge"
        )
    
    def counter(self, name: str, value: float = 1, labels: Dict[str, str] = None):
        """Increment a counter"""
        key = f"{name}_{labels}" if labels else name
        self.counters[key] += value
    
    def histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram observation"""
        key = f"{name}_{labels}" if labels else name
        self.histograms[key].append(value)
    
    def timer(self, name: str):
        """Context manager for timing operations"""
        return Timer(self, name)
    
    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        # Gauges
        for name, metric in self.metrics.items():
            labels_str = ','.join(f'{k}="{v}"' for k, v in metric.labels.items())
            if labels_str:
                lines.append(f"{name}{{{labels_str}}} {metric.value}")
            else:
                lines.append(f"{name} {metric.value}")
        
        # Counters
        for name, value in self.counters.items():
            lines.append(f"{name}_total {value}")
        
        # Histograms (simplified)
        for name, values in self.histograms.items():
            if values:
                import numpy as np
                lines.append(f"{name}_count {len(values)}")
                lines.append(f"{name}_sum {sum(values)}")
                lines.append(f"{name}_avg {np.mean(values):.4f}")
                lines.append(f"{name}_p50 {np.percentile(values, 50):.4f}")
                lines.append(f"{name}_p95 {np.percentile(values, 95):.4f}")
                lines.append(f"{name}_p99 {np.percentile(values, 99):.4f}")
        
        # Uptime
        lines.append(f"uptime_seconds {time.time() - self._start_time:.2f}")
        
        return '\n'.join(lines)
    
    def get_json(self) -> Dict:
        """Export metrics as JSON"""
        return {
            'gauges': {k: v.value for k, v in self.metrics.items()},
            'counters': dict(self.counters),
            'histograms': {k: {
                'count': len(v),
                'sum': sum(v) if v else 0,
                'avg': sum(v)/len(v) if v else 0
            } for k, v in self.histograms.items()},
            'uptime': time.time() - self._start_time
        }


class Timer:
    """Context manager for timing"""
    
    def __init__(self, collector: MetricsCollector, name: str):
        self.collector = collector
        self.name = name
        self.start = None
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        duration = time.time() - self.start
        self.collector.histogram(f"{self.name}_duration_seconds", duration)


# ============================================
# TRADING ACTIVITY TRACKER
# ============================================

@dataclass
class TradingEvent:
    """Single trading event"""
    event_type: str  # signal, order, fill, error
    symbol: str
    timestamp: datetime
    details: Dict[str, Any]
    user_id: str = ""


class TradingActivityTracker:
    """Track trading activity for monitoring and audit"""
    
    def __init__(self, max_events: int = 10000):
        self.events: list = []
        self.max_events = max_events
        self.metrics = MetricsCollector()
    
    def record_signal(self, symbol: str, action: str, confidence: float, 
                     source: str, user_id: str = ""):
        """Record a trading signal"""
        event = TradingEvent(
            event_type="signal",
            symbol=symbol,
            timestamp=datetime.now(),
            details={
                'action': action,
                'confidence': confidence,
                'source': source
            },
            user_id=user_id
        )
        self._add_event(event)
        
        # Update metrics
        self.metrics.counter(f"signals_{action.lower()}_total", labels={'symbol': symbol})
        self.metrics.gauge(f"signal_confidence_{symbol}", confidence)
    
    def record_order(self, symbol: str, side: str, quantity: int, 
                    price: float, order_type: str, user_id: str = ""):
        """Record an order placement"""
        event = TradingEvent(
            event_type="order",
            symbol=symbol,
            timestamp=datetime.now(),
            details={
                'side': side,
                'quantity': quantity,
                'price': price,
                'order_type': order_type,
                'value': quantity * price
            },
            user_id=user_id
        )
        self._add_event(event)
        
        self.metrics.counter(f"orders_{side.lower()}_total")
        self.metrics.histogram("order_value_vnd", quantity * price)
    
    def record_fill(self, symbol: str, side: str, quantity: int, 
                   price: float, pnl: float = 0, user_id: str = ""):
        """Record an order fill"""
        event = TradingEvent(
            event_type="fill",
            symbol=symbol,
            timestamp=datetime.now(),
            details={
                'side': side,
                'quantity': quantity,
                'price': price,
                'pnl': pnl
            },
            user_id=user_id
        )
        self._add_event(event)
        
        self.metrics.counter(f"fills_{side.lower()}_total")
        if pnl != 0:
            self.metrics.histogram("pnl_vnd", pnl)
    
    def record_error(self, symbol: str, error_type: str, 
                    message: str, user_id: str = ""):
        """Record an error"""
        event = TradingEvent(
            event_type="error",
            symbol=symbol,
            timestamp=datetime.now(),
            details={
                'error_type': error_type,
                'message': message
            },
            user_id=user_id
        )
        self._add_event(event)
        
        self.metrics.counter("errors_total", labels={'type': error_type})
    
    def _add_event(self, event: TradingEvent):
        """Add event with size limit"""
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def get_recent_events(self, limit: int = 100, 
                         event_type: str = None) -> list:
        """Get recent events"""
        events = self.events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]
    
    def get_summary(self) -> Dict:
        """Get activity summary"""
        from collections import Counter
        
        event_types = Counter(e.event_type for e in self.events)
        symbols = Counter(e.symbol for e in self.events)
        
        return {
            'total_events': len(self.events),
            'by_type': dict(event_types),
            'by_symbol': dict(symbols.most_common(10)),
            'metrics': self.metrics.get_json()
        }


# ============================================
# SENTRY INTEGRATION
# ============================================

def init_sentry(dsn: str = None):
    """Initialize Sentry for error tracking"""
    dsn = dsn or os.getenv('SENTRY_DSN')
    
    if not dsn:
        return False
    
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )
        return True
    except ImportError:
        logging.warning("sentry-sdk not installed")
        return False


# ============================================
# DECORATORS
# ============================================

def monitor(name: str = None, metrics: MetricsCollector = None):
    """Decorator to monitor function execution"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            metric_name = name or func.__name__
            collector = metrics or _global_metrics
            
            start = time.time()
            try:
                result = func(*args, **kwargs)
                collector.counter(f"{metric_name}_success_total")
                return result
            except Exception as e:
                collector.counter(f"{metric_name}_error_total")
                raise
            finally:
                duration = time.time() - start
                collector.histogram(f"{metric_name}_duration_seconds", duration)
        
        return wrapper
    return decorator


# ============================================
# GLOBAL INSTANCES
# ============================================

_global_metrics = MetricsCollector()
_global_logger = StructuredLogger("vnquant")
_global_tracker = TradingActivityTracker()


def get_metrics() -> MetricsCollector:
    return _global_metrics


def get_logger() -> StructuredLogger:
    return _global_logger


def get_tracker() -> TradingActivityTracker:
    return _global_tracker


# ============================================
# HEALTH CHECK ENDPOINT
# ============================================

def health_check() -> Dict:
    """System health check"""
    import psutil
    
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'system': {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent if os.name != 'nt' else 0
        },
        'metrics_summary': _global_metrics.get_json()
    }


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    print("Testing Monitoring Module...")
    
    # Test logger
    logger = StructuredLogger("test")
    logger.info("Test message", user="test_user", action="login")
    
    # Test metrics
    metrics = MetricsCollector()
    metrics.gauge("cpu_usage", 45.5)
    metrics.counter("requests_total")
    metrics.histogram("response_time", 0.125)
    
    with metrics.timer("database_query"):
        time.sleep(0.1)  # Simulate query
    
    print("\nPrometheus format:")
    print(metrics.get_prometheus_format())
    
    # Test tracker
    tracker = TradingActivityTracker()
    tracker.record_signal("HPG", "BUY", 0.85, "AnalystAgent")
    tracker.record_order("HPG", "BUY", 1000, 22500, "LO")
    tracker.record_fill("HPG", "BUY", 1000, 22500, 0)
    
    print("\nTrading Summary:")
    print(json.dumps(tracker.get_summary(), indent=2))
    
    print("\n✅ Monitoring module working!")
