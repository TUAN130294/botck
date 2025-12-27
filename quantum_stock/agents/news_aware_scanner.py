# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NEWS-AWARE AUTO SCANNER                                   ║
║                    News + Technical Analysis for Vietnam Market              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Đặc thù thị trường Việt Nam:
- Rất nhạy cảm với tin tức
- News-driven market
- Scan tin tức TRƯỚC khi giá biến động

Features:
- Real-time news monitoring
- Sentiment analysis (Vietnamese keywords)
- Technical + News combined signals
- Pre-movement detection
"""

import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import json

try:
    from ..news.sentiment import (
        NewsTradingEngine, NewsArticle, SentimentAnalyzer,
        SentimentResult, NewsSignal
    )
except ImportError:
    NewsTradingEngine = None
    NewsArticle = None
    SentimentAnalyzer = None


@dataclass
class NewsAwareScanResult:
    """Scan result combining technical + news"""
    symbol: str
    timestamp: datetime

    # Technical
    price: float
    change_pct: float
    rsi: float
    macd_signal: str
    volume_ratio: float
    trend: str

    # News
    news_sentiment: float  # -1 to 1
    news_confidence: float
    news_count: int
    recent_headlines: List[str] = field(default_factory=list)

    # Combined Signal
    final_signal: str  # STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL
    signal_strength: float  # 0-1
    reasoning: str

    # Alert priority
    alert_level: str  # CRITICAL, HIGH, MEDIUM, LOW

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'change_pct': self.change_pct,
            'rsi': self.rsi,
            'macd_signal': self.macd_signal,
            'volume_ratio': self.volume_ratio,
            'trend': self.trend,
            'news_sentiment': self.news_sentiment,
            'news_confidence': self.news_confidence,
            'news_count': self.news_count,
            'recent_headlines': self.recent_headlines,
            'final_signal': self.final_signal,
            'signal_strength': self.signal_strength,
            'reasoning': self.reasoning,
            'alert_level': self.alert_level
        }


class NewsAwareScanner:
    """
    Auto Scanner tích hợp Tin tức

    Ưu điểm so với scanner thông thường:
    - Phát hiện TIN TỨC TRƯỚC → Dự đoán biến động GIÁ SAU
    - Kết hợp cả Technical và Fundamental (news)
    - Phù hợp với thị trường VN (news-driven)
    """

    def __init__(self,
                 data_dir: str = "data/historical",
                 scan_interval: int = 300,  # 5 minutes
                 news_check_interval: int = 180,  # 3 minutes (check news more frequently!)
                 min_signal_score: float = 2.0):

        self.data_dir = Path(data_dir)
        self.scan_interval = scan_interval
        self.news_check_interval = news_check_interval
        self.min_signal_score = min_signal_score

        # News engine
        self.news_engine = None
        if NewsTradingEngine:
            self.news_engine = NewsTradingEngine()

        # Callbacks
        self.signal_callbacks: List[Callable] = []
        self.news_callbacks: List[Callable] = []

        # State
        self.is_running = False
        self.last_news_check = None
        self.news_cache: Dict[str, List[NewsArticle]] = {}
        self.sentiment_cache: Dict[str, SentimentResult] = {}

        # Vietnam market hours: 9:00-11:30, 13:00-14:45
        self.market_hours = [
            (9, 0, 11, 30),
            (13, 0, 14, 45)
        ]

    def add_signal_callback(self, callback: Callable):
        """Add callback for trading signals"""
        self.signal_callbacks.append(callback)

    def add_news_callback(self, callback: Callable):
        """Add callback for news alerts"""
        self.news_callbacks.append(callback)

    def is_market_open(self) -> bool:
        """Check if Vietnam market is open"""
        now = datetime.now()

        # Only weekdays
        if now.weekday() >= 5:  # Saturday, Sunday
            return False

        hour = now.hour
        minute = now.minute

        for start_h, start_m, end_h, end_m in self.market_hours:
            if (hour > start_h or (hour == start_h and minute >= start_m)) and \
               (hour < end_h or (hour == end_h and minute <= end_m)):
                return True

        return False

    async def start(self):
        """Start news-aware scanning"""
        if self.is_running:
            print("⚠️ Scanner already running")
            return

        self.is_running = True
        print(f"🚀 News-Aware Scanner Started")
        print(f"   📰 News check: Every {self.news_check_interval // 60} minutes")
        print(f"   📊 Technical scan: Every {self.scan_interval // 60} minutes")

        # Start both loops
        await asyncio.gather(
            self._news_monitoring_loop(),
            self._technical_scanning_loop()
        )

    def stop(self):
        """Stop scanner"""
        self.is_running = False
        print("🛑 Scanner stopped")

    async def _news_monitoring_loop(self):
        """Monitor news continuously"""
        while self.is_running:
            try:
                # Check news more frequently than technical scan
                await self._check_news()
                await asyncio.sleep(self.news_check_interval)

            except Exception as e:
                print(f"❌ News monitoring error: {e}")
                await asyncio.sleep(60)

    async def _technical_scanning_loop(self):
        """Technical scanning loop"""
        while self.is_running:
            try:
                # Only scan during market hours (or outside for preparation)
                await self._perform_scan()
                await asyncio.sleep(self.scan_interval)

            except Exception as e:
                print(f"❌ Technical scan error: {e}")
                await asyncio.sleep(60)

    async def _check_news(self):
        """Check for new news articles"""
        if not self.news_engine:
            return

        self.last_news_check = datetime.now()

        try:
            # Fetch recent news (last 1 hour)
            articles = await self.news_engine.fetch_all_news(hours=1)

            if not articles:
                return

            print(f"\n📰 NEWS CHECK: {len(articles)} articles found")

            # Group by symbol
            news_by_symbol: Dict[str, List[NewsArticle]] = {}
            for article in articles:
                for symbol in article.symbols:
                    if symbol not in news_by_symbol:
                        news_by_symbol[symbol] = []
                    news_by_symbol[symbol].append(article)

            # Analyze sentiment for each symbol
            analyzer = SentimentAnalyzer()

            for symbol, symbol_articles in news_by_symbol.items():
                # Analyze sentiment
                sentiments = []
                for article in symbol_articles:
                    sentiment = analyzer.analyze(article, symbol)
                    sentiments.append(sentiment)

                # Calculate aggregate
                if sentiments:
                    avg_sentiment = sum(s.sentiment_score for s in sentiments) / len(sentiments)
                    avg_confidence = sum(s.confidence for s in sentiments) / len(sentiments)

                    # Cache sentiment
                    self.sentiment_cache[symbol] = SentimentResult(
                        article_id="aggregate",
                        symbol=symbol,
                        sentiment_score=avg_sentiment,
                        sentiment_level=sentiments[0].sentiment_level,
                        confidence=avg_confidence,
                        keywords=[kw for s in sentiments for kw in s.keywords],
                        summary=f"{len(sentiments)} articles analyzed"
                    )

                    # Alert on strong sentiment
                    if abs(avg_sentiment) > 0.5 and avg_confidence > 0.6:
                        direction = "📈 POSITIVE" if avg_sentiment > 0 else "📉 NEGATIVE"
                        print(f"   🔥 {symbol}: {direction} news (score: {avg_sentiment:.2f}, confidence: {avg_confidence:.2f})")
                        print(f"      Latest: {symbol_articles[0].title[:80]}")

                        # Trigger news callbacks
                        for callback in self.news_callbacks:
                            try:
                                await callback({
                                    'symbol': symbol,
                                    'sentiment': avg_sentiment,
                                    'confidence': avg_confidence,
                                    'articles': symbol_articles
                                })
                            except Exception as e:
                                print(f"      ❌ News callback error: {e}")

            # Cache news
            self.news_cache = news_by_symbol

        except Exception as e:
            print(f"❌ News check error: {e}")

    async def _perform_scan(self):
        """Perform full technical + news scan"""
        print(f"\n{'='*70}")
        print(f"🔍 FULL SCAN: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")

        # Get all parquet files
        parquet_files = list(self.data_dir.glob("*.parquet"))

        if not parquet_files:
            print("⚠️ No data files found")
            return

        results = []

        # Scan in batches
        batch_size = 50
        for i in range(0, len(parquet_files), batch_size):
            batch = parquet_files[i:i+batch_size]

            for file_path in batch:
                symbol = file_path.stem.upper()

                try:
                    result = await self._scan_symbol(symbol, file_path)
                    if result:
                        results.append(result)

                        # Trigger callbacks for strong signals
                        if result.signal_strength >= 0.7:
                            for callback in self.signal_callbacks:
                                try:
                                    await callback(result)
                                except Exception as e:
                                    print(f"   ❌ Callback error: {e}")

                except Exception as e:
                    print(f"   ❌ Error scanning {symbol}: {e}")

        # Summary
        strong_signals = [r for r in results if r.signal_strength >= 0.7]
        critical_alerts = [r for r in results if r.alert_level == "CRITICAL"]

        print(f"\n📊 SCAN SUMMARY:")
        print(f"   Total scanned: {len(results)}")
        print(f"   Strong signals: {len(strong_signals)}")
        print(f"   Critical alerts: {len(critical_alerts)}")

        if critical_alerts:
            print(f"\n🚨 CRITICAL ALERTS:")
            for alert in critical_alerts[:5]:
                print(f"   {alert.symbol}: {alert.final_signal} ({alert.signal_strength:.0%}) - {alert.reasoning}")

        return results

    async def _scan_symbol(self, symbol: str, file_path: Path) -> Optional[NewsAwareScanResult]:
        """Scan single symbol with news + technical"""
        try:
            # Load data
            df = pd.read_parquet(file_path)

            if df.empty or len(df) < 50:
                return None

            # Standardize columns
            df.columns = [c.lower() for c in df.columns]

            # Calculate technical indicators
            tech_indicators = self._calculate_technical(df)

            # Get news sentiment (from cache if available)
            news_sentiment = 0.0
            news_confidence = 0.0
            news_count = 0
            headlines = []

            if symbol in self.sentiment_cache:
                sentiment = self.sentiment_cache[symbol]
                news_sentiment = sentiment.sentiment_score
                news_confidence = sentiment.confidence

            if symbol in self.news_cache:
                news_count = len(self.news_cache[symbol])
                headlines = [a.title for a in self.news_cache[symbol][:3]]

            # Combined analysis
            final_signal, strength, reasoning, alert_level = self._combined_analysis(
                tech_indicators, news_sentiment, news_confidence, news_count
            )

            return NewsAwareScanResult(
                symbol=symbol,
                timestamp=datetime.now(),
                price=tech_indicators['price'],
                change_pct=tech_indicators['change_pct'],
                rsi=tech_indicators['rsi'],
                macd_signal=tech_indicators['macd_signal'],
                volume_ratio=tech_indicators['volume_ratio'],
                trend=tech_indicators['trend'],
                news_sentiment=news_sentiment,
                news_confidence=news_confidence,
                news_count=news_count,
                recent_headlines=headlines,
                final_signal=final_signal,
                signal_strength=strength,
                reasoning=reasoning,
                alert_level=alert_level
            )

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            return None

    def _calculate_technical(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators"""
        close = df['close'].values
        volume = df['volume'].values if 'volume' in df.columns else np.ones(len(close))

        # Current values
        price = close[-1]
        prev_price = close[-2] if len(close) > 1 else price
        change_pct = (price - prev_price) / prev_price * 100

        # RSI
        delta = pd.Series(close).diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1] if len(rsi) > 0 and not pd.isna(rsi.iloc[-1]) else 50

        # MACD
        exp1 = pd.Series(close).ewm(span=12).mean()
        exp2 = pd.Series(close).ewm(span=26).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9).mean()

        macd_val = macd.iloc[-1] if len(macd) > 0 and not pd.isna(macd.iloc[-1]) else 0
        signal_val = signal.iloc[-1] if len(signal) > 0 and not pd.isna(signal.iloc[-1]) else 0

        macd_signal = "BULLISH" if macd_val > signal_val else "BEARISH"

        # Volume
        avg_vol = pd.Series(volume).rolling(20).mean().iloc[-1] if len(volume) > 20 else volume[-1]
        volume_ratio = volume[-1] / avg_vol if avg_vol > 0 else 1

        # Trend
        sma20 = pd.Series(close).rolling(20).mean().iloc[-1] if len(close) > 20 else price
        sma50 = pd.Series(close).rolling(50).mean().iloc[-1] if len(close) > 50 else price

        if price > sma20 > sma50:
            trend = "UPTREND"
        elif price < sma20 < sma50:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        return {
            'price': price,
            'change_pct': change_pct,
            'rsi': current_rsi,
            'macd_signal': macd_signal,
            'volume_ratio': volume_ratio,
            'trend': trend
        }

    def _combined_analysis(self, tech: Dict, news_sentiment: float,
                          news_confidence: float, news_count: int) -> tuple:
        """
        Combine technical + news for final signal

        Returns: (signal, strength, reasoning, alert_level)
        """
        # Technical score (-3 to +3)
        tech_score = 0

        # RSI
        if tech['rsi'] < 30:
            tech_score += 1
        elif tech['rsi'] > 70:
            tech_score -= 1

        # MACD
        if tech['macd_signal'] == "BULLISH":
            tech_score += 1
        else:
            tech_score -= 1

        # Trend
        if tech['trend'] == "UPTREND":
            tech_score += 1
        elif tech['trend'] == "DOWNTREND":
            tech_score -= 1

        # Volume
        if tech['volume_ratio'] > 2:
            tech_score += 0.5 if tech['change_pct'] > 0 else -0.5

        # News score (-3 to +3) - WEIGHTED MORE for VN market!
        news_score = news_sentiment * 3 * news_confidence if news_count > 0 else 0

        # Combined score
        # News gets 60% weight, Technical 40% (news-driven market!)
        combined_score = news_score * 0.6 + tech_score * 0.4

        # Determine signal
        if combined_score >= 2:
            signal = "STRONG_BUY"
            strength = min(combined_score / 3, 1.0)
        elif combined_score >= 1:
            signal = "BUY"
            strength = min(combined_score / 2, 0.8)
        elif combined_score <= -2:
            signal = "STRONG_SELL"
            strength = min(abs(combined_score) / 3, 1.0)
        elif combined_score <= -1:
            signal = "SELL"
            strength = min(abs(combined_score) / 2, 0.8)
        else:
            signal = "HOLD"
            strength = 0.5

        # Reasoning
        reasons = []
        if news_count > 0:
            sentiment_word = "tích cực" if news_sentiment > 0 else "tiêu cực" if news_sentiment < 0 else "trung lập"
            reasons.append(f"Tin tức {sentiment_word} ({news_count} bài)")

        if tech['rsi'] < 30:
            reasons.append(f"RSI quá bán ({tech['rsi']:.0f})")
        elif tech['rsi'] > 70:
            reasons.append(f"RSI quá mua ({tech['rsi']:.0f})")

        if tech['volume_ratio'] > 2:
            reasons.append(f"Volume tăng đột biến ({tech['volume_ratio']:.1f}x)")

        reasons.append(f"Xu hướng {tech['trend'].lower()}")

        reasoning = " | ".join(reasons[:3])

        # Alert level
        if strength >= 0.8:
            alert_level = "CRITICAL"
        elif strength >= 0.7:
            alert_level = "HIGH"
        elif strength >= 0.6:
            alert_level = "MEDIUM"
        else:
            alert_level = "LOW"

        return signal, strength, reasoning, alert_level

    def get_top_signals(self, limit: int = 10, signal_type: str = None) -> List[NewsAwareScanResult]:
        """Get top signals (would need to store results)"""
        # This would return cached results sorted by strength
        pass


# Global instance
_news_aware_scanner: Optional[NewsAwareScanner] = None


def get_news_aware_scanner(**kwargs) -> NewsAwareScanner:
    """Get or create global scanner"""
    global _news_aware_scanner
    if _news_aware_scanner is None:
        _news_aware_scanner = NewsAwareScanner(**kwargs)
    return _news_aware_scanner


# Testing
async def test_scanner():
    """Test news-aware scanner"""
    print("Testing News-Aware Scanner...")
    print("="*70)

    scanner = NewsAwareScanner(
        data_dir="data/historical",
        scan_interval=300,
        news_check_interval=180
    )

    # Test callbacks
    async def on_signal(result):
        print(f"📊 Signal: {result.symbol} - {result.final_signal} ({result.signal_strength:.0%})")
        print(f"   {result.reasoning}")

    async def on_news(news_data):
        print(f"📰 News Alert: {news_data['symbol']}")
        print(f"   Sentiment: {news_data['sentiment']:.2f}")
        print(f"   Articles: {len(news_data['articles'])}")

    scanner.add_signal_callback(on_signal)
    scanner.add_news_callback(on_news)

    print("Scanner configured. Ready to start!")


if __name__ == "__main__":
    asyncio.run(test_scanner())
