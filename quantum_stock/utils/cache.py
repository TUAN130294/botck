# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    REDIS CACHING LAYER                                       ║
║                    High-performance data caching for VN-QUANT               ║
╚══════════════════════════════════════════════════════════════════════════════╝

P0 Implementation - Caching layer for performance optimization
"""

import json
import pickle
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed. Run: pip install redis")


# ============================================
# CACHE BACKENDS
# ============================================

class CacheBackend:
    """Abstract cache backend"""
    
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError
    
    def set(self, key: str, value: Any, ttl: int = 300):
        raise NotImplementedError
    
    def delete(self, key: str):
        raise NotImplementedError
    
    def exists(self, key: str) -> bool:
        raise NotImplementedError
    
    def clear(self):
        raise NotImplementedError


class MemoryCache(CacheBackend):
    """
    In-memory cache backend
    Fallback when Redis is not available
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if entry['expires'] > datetime.now():
                return entry['value']
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        self._cache[key] = {
            'value': value,
            'expires': datetime.now() + timedelta(seconds=ttl)
        }
    
    def delete(self, key: str):
        if key in self._cache:
            del self._cache[key]
    
    def exists(self, key: str) -> bool:
        if key in self._cache:
            if self._cache[key]['expires'] > datetime.now():
                return True
            del self._cache[key]
        return False
    
    def clear(self):
        self._cache.clear()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'type': 'memory',
            'keys': len(self._cache),
            'memory_bytes': sum(
                len(pickle.dumps(v)) for v in self._cache.values()
            )
        }


class RedisCache(CacheBackend):
    """
    Redis cache backend
    High-performance distributed caching
    """
    
    def __init__(self, host: str = 'localhost', port: int = 6379, 
                 db: int = 0, password: str = None, prefix: str = 'vnquant:'):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not installed")
        
        self._client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False
        )
        self._prefix = prefix
        
        # Test connection
        try:
            self._client.ping()
            logger.info(f"Redis connected: {host}:{port}")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    def _key(self, key: str) -> str:
        """Add prefix to key"""
        return f"{self._prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        try:
            data = self._client.get(self._key(key))
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        try:
            data = pickle.dumps(value)
            self._client.setex(self._key(key), ttl, data)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    def delete(self, key: str):
        try:
            self._client.delete(self._key(key))
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
    
    def exists(self, key: str) -> bool:
        try:
            return bool(self._client.exists(self._key(key)))
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    def clear(self):
        """Clear all keys with prefix"""
        try:
            keys = self._client.keys(f"{self._prefix}*")
            if keys:
                self._client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
    
    def get_stats(self) -> Dict:
        """Get Redis statistics"""
        try:
            info = self._client.info('memory')
            keys = self._client.keys(f"{self._prefix}*")
            return {
                'type': 'redis',
                'keys': len(keys),
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': self._client.info('clients').get('connected_clients', 0)
            }
        except Exception as e:
            return {'type': 'redis', 'error': str(e)}


# ============================================
# CACHE MANAGER
# ============================================

class CacheManager:
    """
    Unified Cache Manager
    
    Features:
    - Automatic backend selection (Redis or Memory)
    - TTL management
    - DataFrame caching
    - Decorator support
    - Statistics tracking
    """
    
    def __init__(self, redis_url: str = None, fallback_to_memory: bool = True):
        self.backend: CacheBackend = None
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0
        }
        
        # Try Redis first
        if redis_url or REDIS_AVAILABLE:
            try:
                import os
                redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                
                # Parse URL
                if redis_url.startswith('redis://'):
                    parts = redis_url.replace('redis://', '').split('/')
                    host_port = parts[0].split(':')
                    host = host_port[0]
                    port = int(host_port[1]) if len(host_port) > 1 else 6379
                    db = int(parts[1]) if len(parts) > 1 else 0
                    
                    self.backend = RedisCache(host=host, port=port, db=db)
                    logger.info("Using Redis cache backend")
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
        
        # Fallback to memory cache
        if self.backend is None and fallback_to_memory:
            self.backend = MemoryCache()
            logger.info("Using in-memory cache backend")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        value = self.backend.get(key)
        if value is not None:
            self.stats['hits'] += 1
        else:
            self.stats['misses'] += 1
        return value
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Set value in cache"""
        self.backend.set(key, value, ttl)
        self.stats['sets'] += 1
    
    def delete(self, key: str):
        """Delete key from cache"""
        self.backend.delete(key)
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        return self.backend.exists(key)
    
    def clear(self):
        """Clear all cached data"""
        self.backend.clear()
    
    def get_dataframe(self, key: str) -> Optional[pd.DataFrame]:
        """Get DataFrame from cache"""
        data = self.get(key)
        if data is not None and isinstance(data, dict):
            return pd.DataFrame.from_dict(data, orient='split')
        return data if isinstance(data, pd.DataFrame) else None
    
    def set_dataframe(self, key: str, df: pd.DataFrame, ttl: int = 300):
        """Cache a DataFrame"""
        self.set(key, df.to_dict(orient='split'), ttl)
    
    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: int = 300) -> Any:
        """Get from cache or compute and cache"""
        value = self.get(key)
        if value is not None:
            return value
        
        value = factory()
        self.set(key, value, ttl)
        return value
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        backend_stats = self.backend.get_stats()
        hit_rate = self.stats['hits'] / (self.stats['hits'] + self.stats['misses']) \
            if (self.stats['hits'] + self.stats['misses']) > 0 else 0
        
        return {
            **self.stats,
            'hit_rate': f"{hit_rate:.2%}",
            'backend': backend_stats
        }


# ============================================
# CACHING DECORATORS
# ============================================

# Global cache instance
_cache: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Get or create global cache instance"""
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache


def set_cache(cache: CacheManager):
    """Set global cache instance"""
    global _cache
    _cache = cache


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator to cache function results
    
    Usage:
        @cached(ttl=60)
        def expensive_function(symbol):
            return fetch_data(symbol)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


def cached_dataframe(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator specifically for DataFrame-returning functions
    
    Usage:
        @cached_dataframe(ttl=600)
        def get_historical_data(symbol, days):
            return fetch_ohlcv(symbol, days)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = f"df:{hashlib.md5(':'.join(key_parts).encode()).hexdigest()}"
            
            # Try cache
            result = cache.get_dataframe(cache_key)
            if result is not None:
                return result
            
            # Compute and cache
            result = func(*args, **kwargs)
            if isinstance(result, pd.DataFrame):
                cache.set_dataframe(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator


# ============================================
# MARKET DATA CACHE
# ============================================

class MarketDataCache:
    """
    Specialized cache for market data
    
    Features:
    - Price caching with short TTL
    - Historical data caching with long TTL
    - Automatic invalidation at market close
    """
    
    def __init__(self, cache: CacheManager = None):
        self.cache = cache or get_cache()
        self.price_ttl = 5  # 5 seconds for real-time prices
        self.historical_ttl = 3600  # 1 hour for historical data
        self.indicator_ttl = 300  # 5 minutes for indicators
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Get cached price"""
        return self.cache.get(f"price:{symbol}")
    
    def set_price(self, symbol: str, price: float):
        """Cache current price"""
        self.cache.set(f"price:{symbol}", price, self.price_ttl)
    
    def get_ohlcv(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        """Get cached OHLCV data"""
        return self.cache.get_dataframe(f"ohlcv:{symbol}:{days}")
    
    def set_ohlcv(self, symbol: str, days: int, df: pd.DataFrame):
        """Cache OHLCV data"""
        self.cache.set_dataframe(f"ohlcv:{symbol}:{days}", df, self.historical_ttl)
    
    def get_indicators(self, symbol: str, indicator_set: str) -> Optional[pd.DataFrame]:
        """Get cached indicators"""
        return self.cache.get_dataframe(f"ind:{symbol}:{indicator_set}")
    
    def set_indicators(self, symbol: str, indicator_set: str, df: pd.DataFrame):
        """Cache indicators"""
        self.cache.set_dataframe(f"ind:{symbol}:{indicator_set}", df, self.indicator_ttl)
    
    def invalidate_symbol(self, symbol: str):
        """Invalidate all cached data for a symbol"""
        # Note: This is a simplified version
        # In production, use pattern matching
        self.cache.delete(f"price:{symbol}")
        for days in [30, 90, 180, 365]:
            self.cache.delete(f"ohlcv:{symbol}:{days}")


# ============================================
# TESTING
# ============================================

def test_cache():
    """Test cache functionality"""
    print("Testing Cache Module...")
    print("=" * 50)
    
    # Test memory cache
    cache = CacheManager(fallback_to_memory=True)
    
    # Test basic operations
    cache.set("test_key", "test_value", ttl=60)
    assert cache.get("test_key") == "test_value"
    print("✅ Basic set/get passed")
    
    # Test DataFrame caching
    df = pd.DataFrame({
        'A': [1, 2, 3],
        'B': [4, 5, 6]
    })
    cache.set_dataframe("test_df", df, ttl=60)
    cached_df = cache.get_dataframe("test_df")
    assert cached_df is not None
    assert len(cached_df) == 3
    print("✅ DataFrame caching passed")
    
    # Test decorator
    @cached(ttl=60)
    def expensive_func(x):
        return x * 2
    
    result1 = expensive_func(5)
    result2 = expensive_func(5)  # Should be cached
    assert result1 == result2 == 10
    print("✅ Caching decorator passed")
    
    # Get stats
    stats = cache.get_stats()
    print(f"\nCache Stats:")
    print(f"  Hits: {stats['hits']}")
    print(f"  Misses: {stats['misses']}")
    print(f"  Hit Rate: {stats['hit_rate']}")
    
    print("\n✅ All cache tests passed!")


if __name__ == "__main__":
    test_cache()
