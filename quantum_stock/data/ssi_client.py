# -*- coding: utf-8 -*-
"""
SSI iBoard API Client for VN-QUANT
===================================
Real-time market data from SSI Securities.

API Documentation: https://apidocs.ssi.com.vn/

Features:
- Real-time stock prices
- Order book data
- Historical data
- Market statistics
- Index data
- Auto reconnect
- Rate limiting
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger


class MarketID(Enum):
    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCOM"


@dataclass
class SSITickData:
    """Real-time tick data from SSI"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime

    # Price levels
    ceiling: float
    floor: float
    reference: float

    # OHLC
    open: float
    high: float
    low: float
    close: float

    # Volume
    total_volume: int
    total_value: float

    # Change
    change: float
    change_pct: float

    # Bid/Ask
    best_bid: float
    best_ask: float
    best_bid_volume: int
    best_ask_volume: int


@dataclass
class SSIOrderBook:
    """Order book from SSI"""
    symbol: str
    timestamp: datetime

    # Bids (price, volume)
    bids: List[tuple]  # [(price, volume), ...]

    # Asks (price, volume)
    asks: List[tuple]  # [(price, volume), ...]


class SSIClient:
    """
    SSI iBoard API Client

    Usage:
        async with SSIClient(api_key, secret_key) as client:
            tick = await client.get_tick_data("VCB")
            orderbook = await client.get_orderbook("VCB")
    """

    BASE_URL = "https://iboard-api.ssi.com.vn"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_per_second: int = 10
    ):
        """
        Initialize SSI client

        Args:
            api_key: SSI API key
            secret_key: SSI secret key
            timeout: Request timeout in seconds
            max_retries: Max retry attempts
            rate_limit_per_second: Max requests per second
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.timeout = timeout
        self.max_retries = max_retries

        # Rate limiting
        self.rate_limit = rate_limit_per_second
        self.request_times: List[float] = []

        # Session
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Connect and authenticate"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        await self._authenticate()
        logger.info("SSI Client connected")

    async def close(self):
        """Close connection"""
        if self.session:
            await self.session.close()
        logger.info("SSI Client closed")

    async def _authenticate(self):
        """
        Authenticate with SSI API

        Get access token for subsequent requests
        """
        url = f"{self.BASE_URL}/auth/login"

        payload = {
            "consumerID": self.api_key,
            "consumerSecret": self.secret_key
        }

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get("data", {}).get("accessToken")

                    # Token expires in 1 hour (3600 seconds)
                    self.token_expiry = datetime.now() + timedelta(hours=1)

                    logger.info("SSI authentication successful")
                else:
                    error = await response.text()
                    raise Exception(f"SSI auth failed: {response.status} - {error}")

        except Exception as e:
            logger.error(f"SSI authentication error: {e}")
            raise

    async def _ensure_authenticated(self):
        """Ensure token is valid, refresh if needed"""
        if not self.access_token or datetime.now() >= self.token_expiry:
            await self._authenticate()

    async def _rate_limit(self):
        """Enforce rate limiting"""
        now = time.time()

        # Remove requests older than 1 second
        self.request_times = [t for t in self.request_times if now - t < 1.0]

        # Check if we're at the limit
        if len(self.request_times) >= self.rate_limit:
            sleep_time = 1.0 - (now - self.request_times[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.request_times.append(now)

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict:
        """
        Make authenticated request

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            Response data as dict
        """
        await self._ensure_authenticated()
        await self._rate_limit()

        url = f"{self.BASE_URL}{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        for attempt in range(self.max_retries):
            try:
                async with self.session.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401:
                        # Token expired, re-authenticate
                        await self._authenticate()
                        continue
                    else:
                        error = await response.text()
                        logger.error(f"SSI API error: {response.status} - {error}")

                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            continue
                        else:
                            raise Exception(f"SSI API failed: {response.status}")

            except asyncio.TimeoutError:
                logger.warning(f"SSI request timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

            except Exception as e:
                logger.error(f"SSI request error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    # ====================================
    # MARKET DATA METHODS
    # ====================================

    async def get_tick_data(self, symbol: str) -> SSITickData:
        """
        Get real-time tick data for symbol

        Args:
            symbol: Stock symbol (e.g., "VCB")

        Returns:
            SSITickData object
        """
        endpoint = f"/statistics/v2/dailyStockPrice"
        params = {"market": "ALL", "symbol": symbol}

        data = await self._request("GET", endpoint, params=params)

        # Parse response
        item = data.get("data", [{}])[0]

        return SSITickData(
            symbol=symbol,
            price=item.get("lastPrice", 0),
            volume=item.get("lastVolume", 0),
            timestamp=datetime.now(),
            ceiling=item.get("ceiling", 0),
            floor=item.get("floor", 0),
            reference=item.get("reference", 0),
            open=item.get("open", 0),
            high=item.get("high", 0),
            low=item.get("low", 0),
            close=item.get("lastPrice", 0),
            total_volume=item.get("totalVolume", 0),
            total_value=item.get("totalValue", 0),
            change=item.get("change", 0),
            change_pct=item.get("changePc", 0),
            best_bid=item.get("bestBid", 0),
            best_ask=item.get("bestAsk", 0),
            best_bid_volume=item.get("bestBidVol", 0),
            best_ask_volume=item.get("bestAskVol", 0)
        )

    async def get_orderbook(self, symbol: str, depth: int = 10) -> SSIOrderBook:
        """
        Get order book for symbol

        Args:
            symbol: Stock symbol
            depth: Order book depth (max 10)

        Returns:
            SSIOrderBook object
        """
        endpoint = f"/market/orderBook"
        params = {"symbol": symbol}

        data = await self._request("GET", endpoint, params=params)

        # Parse order book
        ob_data = data.get("data", {})

        # Parse bids (sorted high to low)
        bids = []
        for i in range(1, min(depth + 1, 11)):
            price = ob_data.get(f"bid{i}Price")
            volume = ob_data.get(f"bid{i}Volume")
            if price and volume:
                bids.append((price, volume))

        # Parse asks (sorted low to high)
        asks = []
        for i in range(1, min(depth + 1, 11)):
            price = ob_data.get(f"ask{i}Price")
            volume = ob_data.get(f"ask{i}Volume")
            if price and volume:
                asks.append((price, volume))

        return SSIOrderBook(
            symbol=symbol,
            timestamp=datetime.now(),
            bids=bids,
            asks=asks
        )

    async def get_historical_data(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        resolution: str = "D"
    ) -> List[Dict]:
        """
        Get historical OHLCV data

        Args:
            symbol: Stock symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            resolution: D (daily), W (weekly), M (monthly)

        Returns:
            List of OHLCV dicts
        """
        endpoint = f"/market/barChart"
        params = {
            "symbol": symbol,
            "from": from_date,
            "to": to_date,
            "resolution": resolution
        }

        data = await self._request("GET", endpoint, params=params)

        return data.get("data", [])

    async def get_index_data(self, index: str = "VNINDEX") -> Dict:
        """
        Get index data (VNINDEX, VN30, HNX, etc.)

        Args:
            index: Index name

        Returns:
            Index data dict
        """
        endpoint = f"/statistics/v2/dailyIndex"
        params = {"market": "ALL", "index": index}

        data = await self._request("GET", endpoint, params=params)

        return data.get("data", [{}])[0]

    async def get_market_stats(self) -> Dict:
        """
        Get overall market statistics

        Returns:
            Market stats dict
        """
        endpoint = f"/statistics/v2/marketStats"

        data = await self._request("GET", endpoint)

        return data.get("data", {})

    async def search_symbols(self, query: str) -> List[Dict]:
        """
        Search for symbols

        Args:
            query: Search query

        Returns:
            List of matching symbols
        """
        endpoint = f"/market/searchSymbol"
        params = {"query": query}

        data = await self._request("GET", endpoint, params=params)

        return data.get("data", [])


# Convenience function
async def get_ssi_client(api_key: str, secret_key: str) -> SSIClient:
    """Get connected SSI client"""
    client = SSIClient(api_key, secret_key)
    await client.connect()
    return client


__all__ = [
    "SSIClient",
    "SSITickData",
    "SSIOrderBook",
    "MarketID",
    "get_ssi_client"
]
