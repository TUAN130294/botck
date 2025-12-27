# -*- coding: utf-8 -*-
"""
Real-time Market Data Provider
================================
Provides current stock prices from multiple sources:
1. FIREANT API (free, no auth required)
2. Historical data fallback
3. Cached prices

Features:
- Auto-refresh prices every 60 seconds
- Cache to reduce API calls
- Fallback to historical data if API fails
- Support for VN stock symbols
"""

import asyncio
import aiohttp
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class RealtimeMarketData:
    """
    Real-time market data provider for Vietnam stocks

    Usage:
        provider = RealtimeMarketData()
        await provider.start()
        price = await provider.get_price('ACB')
        await provider.stop()
    """

    def __init__(self, cache_ttl: int = 60):
        """
        Initialize market data provider

        Args:
            cache_ttl: Cache time-to-live in seconds (default 60s)
        """
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = cache_ttl
        self.is_running = False
        self.session: Optional[aiohttp.ClientSession] = None

        # Fallback prices from recent data (updated manually)
        self.fallback_prices = {
            'ACB': 26.5, 'HDB': 32.8, 'VCB': 92.5, 'STB': 18.5,
            'SSI': 45.2, 'TPB': 39.5, 'TCB': 23.5, 'HPG': 27.8,
            'VHM': 54.5, 'VIC': 43.2, 'VNM': 78.5, 'MWG': 82.0,
            'FPT': 125.0, 'VJC': 155.0, 'GAS': 97.5, 'PLX': 38.5,
            'POW': 13.5, 'REE': 58.5, 'SAB': 198.0, 'VRE': 27.5
        }

    async def start(self):
        """Start the market data provider"""
        self.is_running = True
        self.session = aiohttp.ClientSession()
        logger.info("Real-time market data provider started")

        # Start background refresh task
        asyncio.create_task(self._refresh_loop())

    async def stop(self):
        """Stop the market data provider"""
        self.is_running = False
        if self.session:
            await self.session.close()
        logger.info("Real-time market data provider stopped")

    async def get_price(self, symbol: str) -> float:
        """
        Get current price for symbol

        Args:
            symbol: Stock symbol (e.g., 'ACB')

        Returns:
            Current price in thousands VND (e.g., 26.5 = 26,500 VND)
        """
        # Check cache first
        if symbol in self.cache:
            cached = self.cache[symbol]
            cache_age = (datetime.now() - cached['timestamp']).total_seconds()

            if cache_age < self.cache_ttl:
                return cached['price']

        # Fetch fresh price
        price = await self._fetch_price(symbol)

        # Update cache
        self.cache[symbol] = {
            'price': price,
            'timestamp': datetime.now()
        }

        return price

    async def _fetch_price(self, symbol: str) -> float:
        """
        Fetch price from API or fallback sources

        Priority:
        1. FIREANT API
        2. Historical data (latest close)
        3. Fallback prices (hardcoded)
        """
        # Try FIREANT API
        try:
            price = await self._fetch_from_fireant(symbol)
            if price:
                return price
        except Exception as e:
            logger.debug(f"FIREANT API failed for {symbol}: {e}")

        # Try historical data
        try:
            price = await self._fetch_from_historical(symbol)
            if price:
                return price
        except Exception as e:
            logger.debug(f"Historical data failed for {symbol}: {e}")

        # Fallback to hardcoded prices
        return self.fallback_prices.get(symbol, 30.0)

    async def _fetch_from_fireant(self, symbol: str) -> Optional[float]:
        """
        Fetch price from FIREANT API (free, no auth)

        API endpoint: https://restv2.fireant.vn/symbols/{symbol}/quote
        Returns price in VND, need to divide by 1000 for our format
        """
        if not self.session:
            return None

        url = f"https://restv2.fireant.vn/symbols/{symbol}/quote"

        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()

                    # Extract price from response
                    # FIREANT returns price in VND, we need thousands
                    price_vnd = data.get('lastPrice') or data.get('c') or data.get('closePrice')

                    if price_vnd:
                        price = price_vnd / 1000.0  # Convert to thousands
                        logger.debug(f"FIREANT: {symbol} = {price:.2f}k VND")
                        return price
        except Exception as e:
            logger.debug(f"FIREANT API error for {symbol}: {e}")

        return None

    async def _fetch_from_historical(self, symbol: str) -> Optional[float]:
        """
        Fetch latest price from historical data files

        Looks for: data/historical/{symbol}.parquet or data/{symbol}.csv
        """
        # Try parquet first
        parquet_file = Path(f"data/historical/{symbol}.parquet")
        if parquet_file.exists():
            try:
                df = pd.read_parquet(parquet_file)
                if len(df) > 0:
                    latest = df.iloc[-1]
                    price = latest['close']
                    # Convert to thousands if needed
                    if price > 1000:
                        price = price / 1000.0
                    logger.debug(f"Historical (parquet): {symbol} = {price:.2f}k VND")
                    return price
            except Exception as e:
                logger.debug(f"Error reading parquet for {symbol}: {e}")

        # Try CSV
        csv_file = Path(f"data/{symbol}.csv")
        if csv_file.exists():
            try:
                df = pd.read_csv(csv_file)
                if len(df) > 0:
                    latest = df.iloc[-1]
                    price = latest['close']
                    # Convert to thousands if needed
                    if price > 1000:
                        price = price / 1000.0
                    logger.debug(f"Historical (CSV): {symbol} = {price:.2f}k VND")
                    return price
            except Exception as e:
                logger.debug(f"Error reading CSV for {symbol}: {e}")

        return None

    async def _refresh_loop(self):
        """Background loop to refresh popular stocks"""
        popular_stocks = ['ACB', 'VCB', 'HPG', 'FPT', 'MWG', 'VHM', 'VIC', 'VNM']

        while self.is_running:
            try:
                # Refresh popular stocks
                for symbol in popular_stocks:
                    if not self.is_running:
                        break

                    try:
                        await self.get_price(symbol)
                        await asyncio.sleep(0.5)  # Throttle requests
                    except Exception as e:
                        logger.debug(f"Refresh error for {symbol}: {e}")

                # Wait before next refresh cycle
                await asyncio.sleep(60)  # Refresh every 60 seconds

            except Exception as e:
                logger.error(f"Refresh loop error: {e}")
                await asyncio.sleep(10)

    def get_cached_prices(self) -> Dict[str, float]:
        """Get all cached prices"""
        return {
            symbol: data['price']
            for symbol, data in self.cache.items()
        }

    async def get_orderbook(self, symbol: str) -> Dict:
        """
        Get order book (bid/ask) for symbol

        Note: FIREANT provides this, but for paper trading we'll use simple spread
        """
        price = await self.get_price(symbol)
        spread = price * 0.001  # 0.1% spread

        return {
            'bid': price - spread/2,
            'ask': price + spread/2,
            'last': price,
            'timestamp': datetime.now().isoformat()
        }


# Singleton instance
_market_data_instance: Optional[RealtimeMarketData] = None


def get_market_data() -> RealtimeMarketData:
    """Get singleton market data instance"""
    global _market_data_instance
    if _market_data_instance is None:
        _market_data_instance = RealtimeMarketData()
    return _market_data_instance


# Example usage
if __name__ == "__main__":
    async def test():
        provider = RealtimeMarketData()
        await provider.start()

        # Test get price
        for symbol in ['ACB', 'VCB', 'HPG', 'FPT']:
            price = await provider.get_price(symbol)
            print(f"{symbol}: {price:.2f}k VND")

        # Wait a bit to test refresh
        await asyncio.sleep(5)

        # Get cached prices
        cached = provider.get_cached_prices()
        print(f"\nCached prices: {cached}")

        await provider.stop()

    asyncio.run(test())
