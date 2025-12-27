# -*- coding: utf-8 -*-
"""
Auto Scanner for VN-QUANT
==========================
Automated market scanning and signal distribution.

Features:
- Scan all stocks every N minutes
- Distribute signals to agents
- Priority-based processing
- WebSocket real-time updates
"""

import asyncio
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger


@dataclass
class ScanResult:
    """Scan result for a symbol"""
    symbol: str
    score: float
    signal: str  # BUY, SELL, HOLD
    indicators: Dict
    timestamp: datetime


class AutoScanner:
    """
    Automated market scanner

    Scans all stocks and distributes signals to agent pipeline
    """

    def __init__(
        self,
        data_dir: str = "data/historical",
        scan_interval: int = 300,  # 5 minutes
        min_score: float = 2.0
    ):
        self.data_dir = Path(data_dir)
        self.scan_interval = scan_interval
        self.min_score = min_score

        # Callbacks
        self.on_signal_callbacks: List[Callable] = []

        # State
        self.is_running = False
        self.last_scan: Optional[datetime] = None
        self.scan_results: Dict[str, ScanResult] = {}

    def add_signal_callback(self, callback: Callable):
        """Add callback for new signals"""
        self.on_signal_callbacks.append(callback)

    async def start(self):
        """Start auto scanner"""
        self.is_running = True
        logger.info(f"Auto scanner started (interval: {self.scan_interval}s)")

        while self.is_running:
            try:
                await self.scan_market()
                await asyncio.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Scanner error: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop auto scanner"""
        self.is_running = False
        logger.info("Auto scanner stopped")

    async def scan_market(self):
        """Scan entire market"""
        start_time = datetime.now()
        logger.info("Starting market scan...")

        # Get all stock files
        parquet_files = list(self.data_dir.glob("*.parquet"))
        logger.info(f"Scanning {len(parquet_files)} stocks")

        results = []

        # Scan in batches for performance
        batch_size = 50
        for i in range(0, len(parquet_files), batch_size):
            batch = parquet_files[i:i+batch_size]

            # Process batch
            batch_results = await asyncio.gather(
                *[self._scan_symbol(f.stem) for f in batch],
                return_exceptions=True
            )

            # Collect results
            for result in batch_results:
                if isinstance(result, ScanResult) and result.score >= self.min_score:
                    results.append(result)

        # Sort by score
        results.sort(key=lambda x: abs(x.score), reverse=True)

        # Store results
        self.scan_results = {r.symbol: r for r in results}
        self.last_scan = datetime.now()

        # Notify callbacks
        for result in results[:20]:  # Top 20
            for callback in self.on_signal_callbacks:
                try:
                    await callback(result)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Scan complete: {len(results)} signals in {duration:.1f}s "
            f"(Top: {results[0].symbol if results else 'N/A'})"
        )

    async def _scan_symbol(self, symbol: str) -> Optional[ScanResult]:
        """Scan single symbol"""
        try:
            # Load data
            file_path = self.data_dir / f"{symbol}.parquet"
            if not file_path.exists():
                return None

            df = pd.read_parquet(file_path)

            if len(df) < 30:
                return None

            # Get latest data
            latest = df.iloc[-1]
            last_30 = df.iloc[-30:]

            # Calculate indicators
            indicators = self._calculate_indicators(last_30)

            # Score signal
            score = self._calculate_score(indicators, latest)

            # Determine signal
            if score >= 2.5:
                signal = "STRONG_BUY"
            elif score >= 1.0:
                signal = "BUY"
            elif score <= -2.5:
                signal = "STRONG_SELL"
            elif score <= -1.0:
                signal = "SELL"
            else:
                signal = "HOLD"

            return ScanResult(
                symbol=symbol,
                score=score,
                signal=signal,
                indicators=indicators,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.debug(f"Error scanning {symbol}: {e}")
            return None

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators"""
        indicators = {}

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        indicators['rsi'] = 100 - (100 / (1 + rs.iloc[-1]))

        # MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        macd = ema_12 - ema_26
        signal_line = macd.ewm(span=9).mean()
        indicators['macd'] = macd.iloc[-1]
        indicators['macd_signal'] = signal_line.iloc[-1]
        indicators['macd_histogram'] = macd.iloc[-1] - signal_line.iloc[-1]

        # Moving averages
        indicators['sma_20'] = df['close'].rolling(20).mean().iloc[-1]
        indicators['ema_20'] = df['close'].ewm(span=20).mean().iloc[-1]

        # Volume
        indicators['volume_avg'] = df['volume'].rolling(20).mean().iloc[-1]
        indicators['volume_ratio'] = df['volume'].iloc[-1] / indicators['volume_avg']

        # Momentum
        indicators['roc_5'] = (df['close'].iloc[-1] / df['close'].iloc[-6] - 1) * 100
        indicators['roc_20'] = (df['close'].iloc[-1] / df['close'].iloc[-21] - 1) * 100

        # Current price
        indicators['current_price'] = df['close'].iloc[-1]

        return indicators

    def _calculate_score(self, indicators: Dict, latest: pd.Series) -> float:
        """Calculate signal score"""
        score = 0.0

        # RSI score
        rsi = indicators['rsi']
        if rsi < 30:
            score += 1.5  # Oversold
        elif rsi > 70:
            score -= 1.5  # Overbought
        elif 40 <= rsi <= 60:
            score += 0.5  # Neutral is good

        # MACD score
        macd_hist = indicators['macd_histogram']
        if macd_hist > 0 and indicators['macd'] > indicators['macd_signal']:
            score += 1.0  # Bullish
        elif macd_hist < 0 and indicators['macd'] < indicators['macd_signal']:
            score -= 1.0  # Bearish

        # Trend score (price vs MA)
        price = indicators['current_price']
        sma_20 = indicators['sma_20']

        if price > sma_20 * 1.02:
            score += 1.0  # Above MA
        elif price < sma_20 * 0.98:
            score -= 1.0  # Below MA

        # Volume score
        vol_ratio = indicators['volume_ratio']
        if vol_ratio > 1.5:
            score += 0.5  # High volume
        elif vol_ratio < 0.5:
            score -= 0.5  # Low volume

        # Momentum score
        roc_5 = indicators['roc_5']
        if roc_5 > 3:
            score += 1.0
        elif roc_5 < -3:
            score -= 1.0

        return score

    def get_top_signals(self, limit: int = 10, signal_type: Optional[str] = None) -> List[ScanResult]:
        """Get top signals"""
        results = list(self.scan_results.values())

        if signal_type:
            results = [r for r in results if r.signal == signal_type]

        results.sort(key=lambda x: abs(x.score), reverse=True)

        return results[:limit]


# Global scanner instance
_scanner: Optional[AutoScanner] = None


def get_auto_scanner(**kwargs) -> AutoScanner:
    """Get global auto scanner"""
    global _scanner
    if _scanner is None:
        _scanner = AutoScanner(**kwargs)
    return _scanner


__all__ = ["AutoScanner", "ScanResult", "get_auto_scanner"]
