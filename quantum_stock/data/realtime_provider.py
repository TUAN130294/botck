# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    REALTIME DATA PROVIDER                                    ║
║                    WebSocket Integration for Vietnam Stock Market            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Features:
- VCI API for historical data
- SSI iBoard WebSocket for realtime prices
- FireAnt integration for tick data
- Data caching and management
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from threading import Thread, Lock
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# DATA MODELS
# ============================================

@dataclass
class TickData:
    """Single tick data point"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    side: str = "UNKNOWN"  # BUY/SELL/UNKNOWN
    change: float = 0.0
    change_pct: float = 0.0


@dataclass
class QuoteData:
    """Real-time quote data"""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    high: float
    low: float
    open: float
    close: float
    timestamp: datetime
    bid_volume: int = 0
    ask_volume: int = 0


@dataclass
class OrderBookLevel:
    """Single order book level"""
    price: float
    volume: int
    count: int = 1


@dataclass 
class OrderBook:
    """Full order book"""
    symbol: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime


# ============================================
# ABSTRACT DATA PROVIDER
# ============================================

class DataProvider(ABC):
    """Abstract base class for data providers"""
    
    @abstractmethod
    def get_historical(self, symbol: str, start: str, end: str, interval: str = '1D') -> pd.DataFrame:
        """Get historical OHLCV data"""
        pass
    
    @abstractmethod
    def get_realtime_quote(self, symbol: str) -> Optional[QuoteData]:
        """Get current quote"""
        pass
    
    @abstractmethod
    def subscribe(self, symbols: List[str], callback: Callable[[TickData], None]):
        """Subscribe to realtime updates"""
        pass
    
    @abstractmethod
    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from updates"""
        pass


# ============================================
# VCI DATA PROVIDER (Historical)
# ============================================

class VCIDataProvider(DataProvider):
    """
    VCI Data Provider - Primary source for Vietnam stock data
    Uses vnstock library with VCI source
    """
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 60  # seconds
        self._lock = Lock()
    
    def get_historical(self, symbol: str, start: str, end: str, interval: str = '1D') -> pd.DataFrame:
        """
        Get historical OHLCV data from VCI
        
        Args:
            symbol: Stock symbol (e.g., 'HPG', 'VNM')
            start: Start date 'YYYY-MM-DD'
            end: End date 'YYYY-MM-DD'
            interval: '1D' for daily (only supported currently)
        """
        try:
            from vnstock import Vnstock
            
            stock = Vnstock().stock(symbol=symbol.upper(), source='VCI')
            df = stock.quote.history(start=start, end=end)
            
            if df is None or df.empty:
                logger.warning(f"No data for {symbol}")
                return pd.DataFrame()
            
            # Standardize columns
            df = self._standardize_columns(df)
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names"""
        mapping = {
            'time': 'Date', 'open': 'Open', 'high': 'High',
            'low': 'Low', 'close': 'Close', 'volume': 'Volume'
        }
        
        for old, new in mapping.items():
            if old in df.columns:
                df = df.rename(columns={old: new})
        
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.set_index('Date')
        
        return df.sort_index()
    
    def get_realtime_quote(self, symbol: str) -> Optional[QuoteData]:
        """Get current quote from VCI (pseudo-realtime)"""
        try:
            from vnstock import Vnstock
            
            # Check cache
            cache_key = f"quote_{symbol}"
            with self._lock:
                if cache_key in self.cache:
                    cached = self.cache[cache_key]
                    if time.time() - cached['time'] < self.cache_ttl:
                        return cached['data']
            
            # Fetch latest data
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            
            stock = Vnstock().stock(symbol=symbol.upper(), source='VCI')
            df = stock.quote.history(start=start, end=end)
            
            if df is None or df.empty:
                return None
            
            last_row = df.iloc[-1]
            prev_close = df.iloc[-2]['close'] if len(df) > 1 else last_row['open']
            
            quote = QuoteData(
                symbol=symbol,
                bid=last_row['close'] * 0.999,  # Estimated
                ask=last_row['close'] * 1.001,
                last=last_row['close'],
                volume=int(last_row['volume']),
                high=last_row['high'],
                low=last_row['low'],
                open=last_row['open'],
                close=last_row['close'],
                timestamp=datetime.now()
            )
            
            # Cache result
            with self._lock:
                self.cache[cache_key] = {'data': quote, 'time': time.time()}
            
            return quote
            
        except Exception as e:
            logger.error(f"Error getting quote {symbol}: {e}")
            return None
    
    def subscribe(self, symbols: List[str], callback: Callable[[TickData], None]):
        """VCI doesn't support realtime, use polling instead"""
        logger.warning("VCI doesn't support WebSocket. Use SSI or FireAnt for realtime.")
    
    def unsubscribe(self, symbols: List[str]):
        pass
    
    def get_intraday(self, symbol: str, date: str = None) -> pd.DataFrame:
        """Get intraday data if available"""
        try:
            from vnstock import Vnstock
            
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            stock = Vnstock().stock(symbol=symbol.upper(), source='VCI')
            # Try to get intraday data
            df = stock.quote.intraday(symbol=symbol)
            return df if df is not None else pd.DataFrame()
            
        except Exception as e:
            logger.warning(f"Intraday data not available for {symbol}: {e}")
            return pd.DataFrame()


# ============================================
# SSI WEBSOCKET PROVIDER (Realtime)
# ============================================

class SSIWebSocketProvider(DataProvider):
    """
    SSI iBoard WebSocket Provider for realtime data
    
    Note: Requires SSI account for API access
    WebSocket URL: wss://iboard.ssi.com.vn/realtime
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws = None
        self.connected = False
        self.callbacks: Dict[str, List[Callable]] = {}
        self.quotes: Dict[str, QuoteData] = {}
        self._running = False
        self._thread = None
        self._vci = VCIDataProvider()  # Fallback for historical
    
    def get_historical(self, symbol: str, start: str, end: str, interval: str = '1D') -> pd.DataFrame:
        """Use VCI for historical data"""
        return self._vci.get_historical(symbol, start, end, interval)
    
    def get_realtime_quote(self, symbol: str) -> Optional[QuoteData]:
        """Get cached realtime quote"""
        return self.quotes.get(symbol)
    
    def connect(self):
        """Connect to SSI WebSocket"""
        try:
            import websocket
            
            ws_url = "wss://iboard.ssi.com.vn/realtime"
            
            def on_message(ws, message):
                self._handle_message(message)
            
            def on_error(ws, error):
                logger.error(f"SSI WebSocket error: {error}")
            
            def on_close(ws, close_status, close_msg):
                logger.info("SSI WebSocket closed")
                self.connected = False
            
            def on_open(ws):
                logger.info("SSI WebSocket connected")
                self.connected = True
                # Authenticate if needed
                if self.api_key:
                    auth_msg = {
                        "action": "auth",
                        "key": self.api_key
                    }
                    ws.send(json.dumps(auth_msg))
            
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            self._running = True
            self._thread = Thread(target=self.ws.run_forever, daemon=True)
            self._thread.start()
            
            return True
            
        except ImportError:
            logger.error("websocket-client not installed. Run: pip install websocket-client")
            return False
        except Exception as e:
            logger.error(f"Failed to connect SSI WebSocket: {e}")
            return False
    
    def disconnect(self):
        """Disconnect WebSocket"""
        self._running = False
        if self.ws:
            self.ws.close()
        self.connected = False
    
    def subscribe(self, symbols: List[str], callback: Callable[[TickData], None]):
        """Subscribe to realtime updates for symbols"""
        if not self.connected:
            self.connect()
        
        for symbol in symbols:
            if symbol not in self.callbacks:
                self.callbacks[symbol] = []
            self.callbacks[symbol].append(callback)
        
        # Send subscribe message
        if self.ws and self.connected:
            sub_msg = {
                "action": "subscribe",
                "symbols": [s.upper() for s in symbols]
            }
            self.ws.send(json.dumps(sub_msg))
    
    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols"""
        for symbol in symbols:
            self.callbacks.pop(symbol, None)
        
        if self.ws and self.connected:
            unsub_msg = {
                "action": "unsubscribe",
                "symbols": [s.upper() for s in symbols]
            }
            self.ws.send(json.dumps(unsub_msg))
    
    def _handle_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            if 'symbol' in data:
                symbol = data['symbol']
                
                # Update quote
                quote = QuoteData(
                    symbol=symbol,
                    bid=data.get('bid', 0),
                    ask=data.get('ask', 0),
                    last=data.get('last', data.get('price', 0)),
                    volume=data.get('volume', 0),
                    high=data.get('high', 0),
                    low=data.get('low', 0),
                    open=data.get('open', 0),
                    close=data.get('close', 0),
                    timestamp=datetime.now(),
                    bid_volume=data.get('bidVol', 0),
                    ask_volume=data.get('askVol', 0)
                )
                self.quotes[symbol] = quote
                
                # Create tick
                tick = TickData(
                    symbol=symbol,
                    price=quote.last,
                    volume=data.get('matchVol', 0),
                    timestamp=datetime.now(),
                    side=data.get('side', 'UNKNOWN'),
                    change=data.get('change', 0),
                    change_pct=data.get('changePct', 0)
                )
                
                # Notify callbacks
                if symbol in self.callbacks:
                    for callback in self.callbacks[symbol]:
                        try:
                            callback(tick)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                            
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Error handling message: {e}")


# ============================================
# UNIFIED DATA MANAGER
# ============================================

class DataManager:
    """
    Unified Data Manager
    Combines multiple data sources with automatic fallback
    """
    
    def __init__(self):
        self.vci = VCIDataProvider()
        self.ssi = None  # Lazy init
        self.cache: Dict[str, pd.DataFrame] = {}
        self.subscribers: Dict[str, List[Callable]] = {}
    
    def get_historical(self, symbol: str, days: int = 365) -> pd.DataFrame:
        """Get historical data with caching"""
        cache_key = f"{symbol}_{days}"
        
        # Check cache
        if cache_key in self.cache:
            cached_df = self.cache[cache_key]
            # Check if data is recent enough
            if len(cached_df) > 0:
                last_date = cached_df.index[-1]
                if (datetime.now() - pd.Timestamp(last_date)).days < 1:
                    return cached_df
        
        # Fetch fresh data
        end = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        df = self.vci.get_historical(symbol, start, end)
        
        if not df.empty:
            self.cache[cache_key] = df
        
        return df
    
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """Get current quote"""
        # Try SSI first if connected
        if self.ssi and self.ssi.connected:
            quote = self.ssi.get_realtime_quote(symbol)
            if quote:
                return quote
        
        # Fall back to VCI
        return self.vci.get_realtime_quote(symbol)
    
    def get_multiple_historical(self, symbols: List[str], days: int = 365) -> Dict[str, pd.DataFrame]:
        """Get historical data for multiple symbols"""
        result = {}
        for symbol in symbols:
            df = self.get_historical(symbol, days)
            if not df.empty:
                result[symbol] = df
        return result
    
    def subscribe_realtime(self, symbols: List[str], callback: Callable[[TickData], None]):
        """Subscribe to realtime updates"""
        if self.ssi is None:
            self.ssi = SSIWebSocketProvider()
        
        self.ssi.subscribe(symbols, callback)
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

# Global instance
_data_manager: Optional[DataManager] = None

def get_data_manager() -> DataManager:
    """Get or create global data manager"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager


def fetch_stock_data(symbol: str, days: int = 365) -> pd.DataFrame:
    """Convenience function to fetch stock data"""
    return get_data_manager().get_historical(symbol, days)


def fetch_multiple_stocks(symbols: List[str], days: int = 365) -> Dict[str, pd.DataFrame]:
    """Fetch data for multiple stocks"""
    return get_data_manager().get_multiple_historical(symbols, days)


def get_current_price(symbol: str) -> Optional[float]:
    """Get current price for a symbol"""
    quote = get_data_manager().get_quote(symbol)
    return quote.last if quote else None


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    print("Testing VCI Data Provider...")
    
    dm = DataManager()
    
    # Test historical data
    symbols = ['HPG', 'VNM', 'FPT']
    
    for symbol in symbols:
        df = dm.get_historical(symbol, days=180)
        if not df.empty:
            print(f"\n{symbol}: {len(df)} rows")
            print(f"  Date range: {df.index[0]} to {df.index[-1]}")
            print(f"  Last close: {df['Close'].iloc[-1]:,.2f}")
        else:
            print(f"\n{symbol}: No data")
    
    # Test quote
    for symbol in symbols:
        quote = dm.get_quote(symbol)
        if quote:
            print(f"\n{symbol} Quote:")
            print(f"  Last: {quote.last:,.2f}")
            print(f"  Volume: {quote.volume:,}")
