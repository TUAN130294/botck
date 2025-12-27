# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    WEBSOCKET DATA FEEDS                                      ║
║                    SSI iBoard + FireAnt Real-time Integration               ║
╚══════════════════════════════════════════════════════════════════════════════╝

P0 Implementation - Real-time data pipeline for Vietnam stock market
"""

import asyncio
import json
import logging
import time
import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from threading import Thread, Lock
from queue import Queue
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import websocket libraries
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets not installed. Run: pip install websockets")

try:
    import websocket
    WEBSOCKET_CLIENT_AVAILABLE = True
except ImportError:
    WEBSOCKET_CLIENT_AVAILABLE = False


# ============================================
# DATA MODELS
# ============================================

@dataclass
class MarketTick:
    """Single market tick"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    side: str = "UNKNOWN"
    change: float = 0.0
    change_pct: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    bid_vol: int = 0
    ask_vol: int = 0
    total_vol: int = 0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    ref: float = 0.0
    ceil: float = 0.0
    floor: float = 0.0


@dataclass
class OrderBookEntry:
    """Order book entry"""
    price: float
    volume: int
    order_count: int = 1


@dataclass
class OrderBook:
    """Full order book"""
    symbol: str
    bids: List[OrderBookEntry] = field(default_factory=list)
    asks: List[OrderBookEntry] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================
# ABSTRACT FEED
# ============================================

class DataFeed(ABC):
    """Abstract base class for data feeds"""
    
    def __init__(self):
        self.connected = False
        self.callbacks: Dict[str, List[Callable]] = {}
        self.ticks: Dict[str, MarketTick] = {}
        self.orderbooks: Dict[str, OrderBook] = {}
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to data source"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from data source"""
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str]):
        """Subscribe to symbols"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols"""
        pass
    
    def on_tick(self, callback: Callable[[MarketTick], None]):
        """Register tick callback"""
        if 'tick' not in self.callbacks:
            self.callbacks['tick'] = []
        self.callbacks['tick'].append(callback)
    
    def on_orderbook(self, callback: Callable[[OrderBook], None]):
        """Register orderbook callback"""
        if 'orderbook' not in self.callbacks:
            self.callbacks['orderbook'] = []
        self.callbacks['orderbook'].append(callback)
    
    def _notify_tick(self, tick: MarketTick):
        """Notify all tick callbacks"""
        self.ticks[tick.symbol] = tick
        for callback in self.callbacks.get('tick', []):
            try:
                callback(tick)
            except Exception as e:
                logger.error(f"Tick callback error: {e}")
    
    def _notify_orderbook(self, ob: OrderBook):
        """Notify all orderbook callbacks"""
        self.orderbooks[ob.symbol] = ob
        for callback in self.callbacks.get('orderbook', []):
            try:
                callback(ob)
            except Exception as e:
                logger.error(f"Orderbook callback error: {e}")


# ============================================
# SSI iBOARD WEBSOCKET
# ============================================

class SSIWebSocketFeed(DataFeed):
    """
    SSI iBoard WebSocket Feed
    
    WebSocket URL: wss://iboard.ssi.com.vn/realtime
    
    Features:
    - Real-time price updates
    - Order book depth
    - Trade notifications
    
    Requires: SSI trading account with API access
    """
    
    WS_URL = "wss://iboard.ssi.com.vn/realtime"
    REST_URL = "https://iboard-api.ssi.com.vn/v2/stock"
    
    def __init__(self, consumer_id: str = None, consumer_secret: str = None):
        super().__init__()
        self.consumer_id = consumer_id
        self.consumer_secret = consumer_secret
        self.ws = None
        self._running = False
        self._subscribed_symbols: List[str] = []
        self._reconnect_attempts = 0
        self._max_reconnects = 5
    
    async def connect(self) -> bool:
        """Connect to SSI iBoard WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not available")
            return False
        
        try:
            # Build authentication headers if provided
            headers = {}
            if self.consumer_id and self.consumer_secret:
                timestamp = str(int(time.time() * 1000))
                signature = self._generate_signature(timestamp)
                headers = {
                    'X-Consumer-Id': self.consumer_id,
                    'X-Timestamp': timestamp,
                    'X-Signature': signature
                }
            
            self.ws = await websockets.connect(
                self.WS_URL,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            
            self.connected = True
            self._running = True
            self._reconnect_attempts = 0
            
            # Start message handler
            asyncio.create_task(self._message_handler())
            
            logger.info("SSI WebSocket connected")
            return True
            
        except Exception as e:
            logger.error(f"SSI WebSocket connection failed: {e}")
            return False
    
    def _generate_signature(self, timestamp: str) -> str:
        """Generate HMAC signature for authentication"""
        message = f"{self.consumer_id}{timestamp}"
        signature = hmac.new(
            self.consumer_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def disconnect(self):
        """Disconnect from SSI WebSocket"""
        self._running = False
        if self.ws:
            await self.ws.close()
        self.connected = False
        logger.info("SSI WebSocket disconnected")
    
    async def subscribe(self, symbols: List[str]):
        """Subscribe to symbols"""
        if not self.connected:
            await self.connect()
        
        for symbol in symbols:
            if symbol not in self._subscribed_symbols:
                self._subscribed_symbols.append(symbol.upper())
        
        # Send subscription message
        sub_msg = {
            "action": "subscribe",
            "stocks": [s.upper() for s in symbols]
        }
        
        await self.ws.send(json.dumps(sub_msg))
        logger.info(f"Subscribed to: {symbols}")
    
    async def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols"""
        for symbol in symbols:
            if symbol.upper() in self._subscribed_symbols:
                self._subscribed_symbols.remove(symbol.upper())
        
        unsub_msg = {
            "action": "unsubscribe",
            "stocks": [s.upper() for s in symbols]
        }
        
        await self.ws.send(json.dumps(unsub_msg))
        logger.info(f"Unsubscribed from: {symbols}")
    
    async def _message_handler(self):
        """Handle incoming WebSocket messages"""
        while self._running:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                
                if 'stock' in data or 'symbol' in data:
                    self._handle_price_update(data)
                elif 'bids' in data or 'asks' in data:
                    self._handle_orderbook_update(data)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("SSI WebSocket connection closed")
                await self._reconnect()
            except Exception as e:
                logger.error(f"Message handler error: {e}")
    
    def _handle_price_update(self, data: Dict):
        """Handle price update message"""
        try:
            symbol = data.get('stock') or data.get('symbol', '')
            
            tick = MarketTick(
                symbol=symbol,
                price=float(data.get('lastPrice', data.get('price', 0))),
                volume=int(data.get('matchVolume', data.get('volume', 0))),
                timestamp=datetime.now(),
                side=data.get('side', 'UNKNOWN'),
                change=float(data.get('change', 0)),
                change_pct=float(data.get('changePct', data.get('changePercent', 0))),
                bid=float(data.get('bid1', data.get('bestBid', 0))),
                ask=float(data.get('ask1', data.get('bestAsk', 0))),
                bid_vol=int(data.get('bidVol1', 0)),
                ask_vol=int(data.get('askVol1', 0)),
                total_vol=int(data.get('totalVolume', data.get('accumulatedVolume', 0))),
                high=float(data.get('high', 0)),
                low=float(data.get('low', 0)),
                open=float(data.get('open', 0)),
                ref=float(data.get('ref', data.get('refPrice', 0))),
                ceil=float(data.get('ceiling', data.get('ceilPrice', 0))),
                floor=float(data.get('floor', data.get('floorPrice', 0)))
            )
            
            self._notify_tick(tick)
            
        except Exception as e:
            logger.error(f"Error parsing price update: {e}")
    
    def _handle_orderbook_update(self, data: Dict):
        """Handle order book update message"""
        try:
            symbol = data.get('stock') or data.get('symbol', '')
            
            bids = []
            asks = []
            
            # Parse bid levels (up to 10 levels)
            for i in range(1, 11):
                bid_price = data.get(f'bid{i}')
                bid_vol = data.get(f'bidVol{i}')
                if bid_price and bid_vol:
                    bids.append(OrderBookEntry(
                        price=float(bid_price),
                        volume=int(bid_vol)
                    ))
                
                ask_price = data.get(f'ask{i}')
                ask_vol = data.get(f'askVol{i}')
                if ask_price and ask_vol:
                    asks.append(OrderBookEntry(
                        price=float(ask_price),
                        volume=int(ask_vol)
                    ))
            
            ob = OrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.now()
            )
            
            self._notify_orderbook(ob)
            
        except Exception as e:
            logger.error(f"Error parsing orderbook: {e}")
    
    async def _reconnect(self):
        """Attempt to reconnect"""
        if self._reconnect_attempts >= self._max_reconnects:
            logger.error("Max reconnection attempts reached")
            return
        
        self._reconnect_attempts += 1
        wait_time = min(2 ** self._reconnect_attempts, 60)
        
        logger.info(f"Reconnecting in {wait_time}s (attempt {self._reconnect_attempts})")
        await asyncio.sleep(wait_time)
        
        if await self.connect():
            # Resubscribe to symbols
            if self._subscribed_symbols:
                await self.subscribe(self._subscribed_symbols)


# ============================================
# FIREANT WEBSOCKET
# ============================================

class FireAntWebSocketFeed(DataFeed):
    """
    FireAnt WebSocket Feed for tick data
    
    Features:
    - Tick-by-tick data
    - High-frequency updates
    - All exchanges (HSX, HNX, UPCOM)
    
    Requires: FireAnt Pro subscription
    """
    
    WS_URL = "wss://restv2.fireant.vn/socket"
    
    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key
        self.ws = None
        self._running = False
        self._subscribed_symbols: List[str] = []
    
    async def connect(self) -> bool:
        """Connect to FireAnt WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not available")
            return False
        
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f"Bearer {self.api_key}"
            
            self.ws = await websockets.connect(
                self.WS_URL,
                extra_headers=headers
            )
            
            self.connected = True
            self._running = True
            
            # Start message handler
            asyncio.create_task(self._message_handler())
            
            logger.info("FireAnt WebSocket connected")
            return True
            
        except Exception as e:
            logger.error(f"FireAnt connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from FireAnt"""
        self._running = False
        if self.ws:
            await self.ws.close()
        self.connected = False
        logger.info("FireAnt WebSocket disconnected")
    
    async def subscribe(self, symbols: List[str]):
        """Subscribe to symbols for tick data"""
        if not self.connected:
            await self.connect()
        
        for symbol in symbols:
            if symbol not in self._subscribed_symbols:
                self._subscribed_symbols.append(symbol.upper())
        
        for symbol in symbols:
            sub_msg = {
                "op": "subscribe",
                "channel": f"tick:{symbol.upper()}"
            }
            await self.ws.send(json.dumps(sub_msg))
        
        logger.info(f"FireAnt subscribed to: {symbols}")
    
    async def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols"""
        for symbol in symbols:
            if symbol.upper() in self._subscribed_symbols:
                self._subscribed_symbols.remove(symbol.upper())
            
            unsub_msg = {
                "op": "unsubscribe",
                "channel": f"tick:{symbol.upper()}"
            }
            await self.ws.send(json.dumps(unsub_msg))
        
        logger.info(f"FireAnt unsubscribed from: {symbols}")
    
    async def _message_handler(self):
        """Handle incoming messages"""
        while self._running:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                
                if data.get('channel', '').startswith('tick:'):
                    self._handle_tick(data)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("FireAnt connection closed")
                break
            except Exception as e:
                logger.error(f"FireAnt message error: {e}")
    
    def _handle_tick(self, data: Dict):
        """Handle tick message"""
        try:
            payload = data.get('data', data)
            symbol = data.get('channel', '').replace('tick:', '')
            
            tick = MarketTick(
                symbol=symbol,
                price=float(payload.get('price', 0)),
                volume=int(payload.get('volume', 0)),
                timestamp=datetime.fromtimestamp(
                    payload.get('time', time.time()) / 1000
                ),
                side=payload.get('side', 'UNKNOWN'),
                change=float(payload.get('change', 0)),
                change_pct=float(payload.get('changePercent', 0))
            )
            
            self._notify_tick(tick)
            
        except Exception as e:
            logger.error(f"FireAnt tick error: {e}")


# ============================================
# UNIFIED FEED MANAGER
# ============================================

class FeedManager:
    """
    Unified Feed Manager
    
    Manages multiple data feeds with failover
    """
    
    def __init__(self):
        self.feeds: Dict[str, DataFeed] = {}
        self.primary_feed: Optional[DataFeed] = None
        self.tick_queue: Queue = Queue()
        self.orderbook_queue: Queue = Queue()
        self._callbacks: Dict[str, List[Callable]] = {}
    
    def add_feed(self, name: str, feed: DataFeed, primary: bool = False):
        """Add a data feed"""
        self.feeds[name] = feed
        
        # Register callbacks
        feed.on_tick(lambda tick: self.tick_queue.put(tick))
        feed.on_orderbook(lambda ob: self.orderbook_queue.put(ob))
        
        if primary:
            self.primary_feed = feed
    
    async def connect_all(self):
        """Connect all feeds"""
        for name, feed in self.feeds.items():
            success = await feed.connect()
            logger.info(f"Feed '{name}' connected: {success}")
    
    async def disconnect_all(self):
        """Disconnect all feeds"""
        for name, feed in self.feeds.items():
            await feed.disconnect()
    
    async def subscribe_all(self, symbols: List[str]):
        """Subscribe to symbols on all feeds"""
        for name, feed in self.feeds.items():
            await feed.subscribe(symbols)
    
    def get_latest_tick(self, symbol: str) -> Optional[MarketTick]:
        """Get latest tick for symbol from any connected feed"""
        for feed in self.feeds.values():
            if symbol in feed.ticks:
                return feed.ticks[symbol]
        return None
    
    def get_orderbook(self, symbol: str) -> Optional[OrderBook]:
        """Get latest orderbook for symbol"""
        for feed in self.feeds.values():
            if symbol in feed.orderbooks:
                return feed.orderbooks[symbol]
        return None
    
    def on_tick(self, callback: Callable[[MarketTick], None]):
        """Register global tick callback"""
        if 'tick' not in self._callbacks:
            self._callbacks['tick'] = []
        self._callbacks['tick'].append(callback)
    
    def process_queue(self, max_items: int = 100):
        """Process tick queue"""
        processed = 0
        while not self.tick_queue.empty() and processed < max_items:
            tick = self.tick_queue.get_nowait()
            for callback in self._callbacks.get('tick', []):
                try:
                    callback(tick)
                except Exception as e:
                    logger.error(f"Tick callback error: {e}")
            processed += 1
        return processed


# ============================================
# SIMULATED FEED (For testing)
# ============================================

class SimulatedFeed(DataFeed):
    """
    Simulated data feed for testing
    Generates random price movements
    """
    
    def __init__(self, symbols: List[str] = None):
        super().__init__()
        self.symbols = symbols or ['HPG', 'VNM', 'FPT', 'VCB']
        self._running = False
        self._task = None
        self._base_prices: Dict[str, float] = {}
    
    async def connect(self) -> bool:
        """Start simulation"""
        import random
        
        # Initialize base prices
        for symbol in self.symbols:
            self._base_prices[symbol] = random.uniform(20, 100)
        
        self.connected = True
        self._running = True
        self._task = asyncio.create_task(self._generate_ticks())
        
        logger.info("Simulated feed connected")
        return True
    
    async def disconnect(self):
        """Stop simulation"""
        self._running = False
        if self._task:
            self._task.cancel()
        self.connected = False
        logger.info("Simulated feed disconnected")
    
    async def subscribe(self, symbols: List[str]):
        """Subscribe to symbols"""
        for symbol in symbols:
            if symbol not in self.symbols:
                self.symbols.append(symbol)
                import random
                self._base_prices[symbol] = random.uniform(20, 100)
    
    async def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from symbols"""
        for symbol in symbols:
            if symbol in self.symbols:
                self.symbols.remove(symbol)
    
    async def _generate_ticks(self):
        """Generate simulated ticks"""
        import random
        
        while self._running:
            try:
                for symbol in self.symbols:
                    # Random price movement
                    base = self._base_prices[symbol]
                    change_pct = random.gauss(0, 0.002)  # 0.2% std dev
                    new_price = base * (1 + change_pct)
                    self._base_prices[symbol] = new_price
                    
                    tick = MarketTick(
                        symbol=symbol,
                        price=round(new_price, 2),
                        volume=random.randint(100, 10000) * 100,
                        timestamp=datetime.now(),
                        side='BUY' if change_pct > 0 else 'SELL',
                        change=round(new_price - base, 2),
                        change_pct=round(change_pct * 100, 2),
                        bid=round(new_price * 0.999, 2),
                        ask=round(new_price * 1.001, 2),
                        bid_vol=random.randint(1000, 50000),
                        ask_vol=random.randint(1000, 50000)
                    )
                    
                    self._notify_tick(tick)
                
                await asyncio.sleep(1)  # 1 tick per second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulation error: {e}")


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def create_ssi_feed(consumer_id: str = None, consumer_secret: str = None) -> SSIWebSocketFeed:
    """Create SSI WebSocket feed"""
    import os
    consumer_id = consumer_id or os.getenv('SSI_CONSUMER_ID')
    consumer_secret = consumer_secret or os.getenv('SSI_CONSUMER_SECRET')
    return SSIWebSocketFeed(consumer_id, consumer_secret)


def create_fireant_feed(api_key: str = None) -> FireAntWebSocketFeed:
    """Create FireAnt WebSocket feed"""
    import os
    api_key = api_key or os.getenv('FIREANT_API_KEY')
    return FireAntWebSocketFeed(api_key)


def create_test_feed() -> SimulatedFeed:
    """Create simulated feed for testing"""
    return SimulatedFeed()


# ============================================
# TESTING
# ============================================

async def test_simulated_feed():
    """Test simulated feed"""
    print("Testing Simulated Feed...")
    
    feed = SimulatedFeed(['HPG', 'VNM', 'FPT'])
    
    ticks_received = []
    feed.on_tick(lambda tick: ticks_received.append(tick))
    
    await feed.connect()
    await asyncio.sleep(3)  # Wait for 3 ticks
    await feed.disconnect()
    
    print(f"Received {len(ticks_received)} ticks")
    for tick in ticks_received[:5]:
        print(f"  {tick.symbol}: {tick.price:.2f} ({tick.change_pct:+.2f}%)")
    
    return len(ticks_received) > 0


if __name__ == "__main__":
    print("WebSocket Feeds Module")
    print("=" * 50)
    
    # Run test
    result = asyncio.run(test_simulated_feed())
    print(f"\nTest passed: {result}")
