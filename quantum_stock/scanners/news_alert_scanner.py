# -*- coding: utf-8 -*-
"""
News Alert Scanner
==================
Path B: News-based opportunity detection (INDEPENDENT from model)

Features:
- Monitor news 24/7 for all stocks
- Vietnamese keyword analysis
- Trigger agents IMMEDIATELY on CRITICAL/HIGH news
- NO model prediction check (faster response)
"""

import asyncio
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)


@dataclass
class NewsAlert:
    """News-based trading alert"""
    symbol: str
    timestamp: datetime

    # News content
    headline: str
    summary: str
    source: str

    # Sentiment
    sentiment: float  # -1 to 1
    sentiment_confidence: float  # 0-1

    # Alert level
    alert_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    urgency_score: float  # 0-1

    # Trading signal (derived from news)
    suggested_action: str  # BUY, SELL, HOLD
    rationale: List[str]

    # Optional fields
    url: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'headline': self.headline,
            'summary': self.summary,
            'source': self.source,
            'url': self.url,
            'sentiment': self.sentiment,
            'sentiment_confidence': self.sentiment_confidence,
            'alert_level': self.alert_level,
            'urgency_score': self.urgency_score,
            'suggested_action': self.suggested_action,
            'rationale': self.rationale
        }


class NewsAlertScanner:
    """
    Scanner chuyên monitor tin tức và trigger agents NGAY

    Path B logic:
    - Independent from model predictions
    - Faster response (no model inference)
    - Trigger on CRITICAL/HIGH news only
    - 24/7 monitoring (even outside market hours)
    """

    def __init__(
        self,
        scan_interval: int = 60,  # 1 minute (faster than model scanner)
        min_alert_level: str = "HIGH"  # CRITICAL or HIGH
    ):
        self.scan_interval = scan_interval
        self.min_alert_level = min_alert_level

        # Callbacks
        self.on_alert_callbacks: List[Callable] = []

        # State
        self.is_running = False
        self.last_scan: Optional[datetime] = None
        self.recent_alerts: Dict[str, List[NewsAlert]] = {}  # symbol -> alerts

        # Vietnamese keywords for sentiment analysis
        self.positive_keywords = [
            'tăng trưởng', 'lợi nhuận', 'tích cực', 'mở rộng',
            'đầu tư', 'hợp tác', 'thành công', 'cải thiện',
            'phát triển', 'doanh thu tăng', 'tăng vốn',
            'chấp thuận', 'phê duyệt', 'đột phá'
        ]

        self.negative_keywords = [
            'giảm', 'lỗ', 'thất bại', 'khó khăn',
            'rủi ro', 'sụt giảm', 'cảnh báo', 'điều tra',
            'vi phạm', 'kiện tụng', 'nợ xấu', 'phá sản',
            'bất ổn', 'sa thải', 'đình chỉ'
        ]

        self.critical_keywords = [
            'thâu tóm', 'sáp nhập', 'tăng vốn', 'chia cổ tức',
            'cổ phiếu thưởng', 'họp đại hội đồng cổ đông',
            'thay đổi lãnh đạo', 'phát hành riêng lẻ',
            'mua lại cổ phiếu', 'niêm yết'
        ]

    def add_alert_callback(self, callback: Callable):
        """Add callback for news alerts"""
        self.on_alert_callbacks.append(callback)

    async def start(self):
        """
        Start 24/7 news monitoring

        Logic: Scan xong → nghỉ min_interval → scan tiếp
        (Không overlap)
        """
        self.is_running = True
        self.min_rest_interval = 30  # Nghỉ tối thiểu 30s giữa các đợt (news cần nhanh hơn)

        logger.info(
            f"News alert scanner started (24/7 mode)\n"
            f"  - Mode: Sequential (scan xong mới scan tiếp)\n"
            f"  - Min rest between scans: {self.min_rest_interval}s\n"
            f"  - Min alert level: {self.min_alert_level}\n"
            f"  - Sources: VietStock RSS (4 feeds)"
        )

        while self.is_running:
            try:
                scan_start = datetime.now()

                # Scan news (blocking until complete)
                await self.scan_all_news()

                scan_duration = (datetime.now() - scan_start).total_seconds()
                logger.debug(f"News scan completed in {scan_duration:.1f}s")

                # Rest before next scan
                await asyncio.sleep(self.min_rest_interval)

            except Exception as e:
                logger.error(f"News scanner error: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop news scanner"""
        self.is_running = False
        logger.info("News alert scanner stopped")

    async def scan_all_news(self):
        """
        Scan news cho tất cả stocks

        Sources:
        1. RSS feeds (VnExpress, CafeF, etc.)
        2. APIs (if available)
        3. Web scraping (cached)

        For MVP: Simplified mock data
        """
        start_time = datetime.now()

        # TODO: Integrate real news sources
        # For now, return mock alerts for demonstration

        alerts = await self._fetch_news_from_sources()

        # Filter: Only CRITICAL/HIGH
        critical_alerts = [
            alert for alert in alerts
            if alert.alert_level in ['CRITICAL', 'HIGH']
        ]

        if critical_alerts:
            logger.info(f"Found {len(critical_alerts)} critical news alerts")

            for alert in critical_alerts:
                await self._notify_alert(alert)

        self.last_scan = datetime.now()

    async def _fetch_news_from_sources(self) -> List[NewsAlert]:
        """
        Fetch news from real RSS sources (CafeF, VietStock, VnExpress)

        Uses VNStockNewsFetcher to get live news with stock filtering
        """
        alerts = []

        try:
            # Import the real RSS fetcher
            from quantum_stock.news.rss_news_fetcher import get_news_fetcher

            fetcher = get_news_fetcher()

            # Fetch latest news (limit to 20 for performance)
            news_items = fetcher.fetch_all_feeds(max_items=20)

            logger.info(f"📰 Fetched {len(news_items)} news items from RSS feeds")

            for item in news_items:
                try:
                    # Convert to NewsAlert format
                    symbol = item.get('symbol', 'VNINDEX')

                    # Get sentiment score (RSS fetcher returns 0-1, we need -1 to 1)
                    news_sentiment = item.get('news_sentiment', 0.5)
                    sentiment = (news_sentiment - 0.5) * 2  # Convert to -1 to 1 scale

                    sentiment_confidence = item.get('confidence', 0.5)

                    # Check for critical keywords
                    headline = item.get('headline', '')
                    has_critical = any(kw in headline.lower() for kw in self.critical_keywords)

                    # Determine alert level
                    alert_level = self._determine_alert_level(
                        sentiment, sentiment_confidence, has_critical
                    )

                    # Determine action
                    if sentiment > 0.3:
                        suggested_action = "BUY"
                    elif sentiment < -0.3:
                        suggested_action = "SELL"
                    else:
                        suggested_action = "HOLD"

                    # Create rationale
                    rationale = []
                    if sentiment > 0:
                        rationale.append(f"Tin tích cực: {item.get('recommendation', '')}")
                    else:
                        rationale.append(f"Tin tiêu cực: {item.get('recommendation', '')}")
                    rationale.append(f"Nguồn: {item.get('source', 'Unknown')}")
                    rationale.append(f"Độ tin cậy: {sentiment_confidence*100:.0f}%")

                    # Parse timestamp
                    try:
                        timestamp = datetime.fromisoformat(item.get('timestamp', ''))
                    except:
                        timestamp = datetime.now()

                    alert = NewsAlert(
                        symbol=symbol,
                        timestamp=timestamp,
                        headline=headline,
                        summary=item.get('summary', headline),
                        source=item.get('source', 'RSS'),
                        url=item.get('url'),
                        sentiment=sentiment,
                        sentiment_confidence=sentiment_confidence,
                        alert_level=alert_level,
                        urgency_score=0.9 if alert_level == 'CRITICAL' else 0.7 if alert_level == 'HIGH' else 0.5,
                        suggested_action=suggested_action,
                        rationale=rationale
                    )

                    alerts.append(alert)

                except Exception as e:
                    logger.warning(f"Error parsing news item: {e}")
                    continue

        except ImportError as e:
            logger.warning(f"RSS fetcher not available: {e}")
        except Exception as e:
            logger.error(f"Error fetching news: {e}")

        return alerts

    def _analyze_sentiment(self, text: str) -> tuple[float, float]:
        """
        Analyze Vietnamese text sentiment

        Returns:
            (sentiment_score, confidence)
            sentiment: -1 (very negative) to 1 (very positive)
            confidence: 0 to 1
        """
        text_lower = text.lower()

        # Count keywords
        positive_count = sum(1 for kw in self.positive_keywords if kw in text_lower)
        negative_count = sum(1 for kw in self.negative_keywords if kw in text_lower)
        critical_count = sum(1 for kw in self.critical_keywords if kw in text_lower)

        total_keywords = positive_count + negative_count + critical_count

        if total_keywords == 0:
            return 0.0, 0.3  # Neutral, low confidence

        # Calculate sentiment
        if positive_count > negative_count:
            sentiment = 0.3 + (positive_count / total_keywords) * 0.7
        elif negative_count > positive_count:
            sentiment = -0.3 - (negative_count / total_keywords) * 0.7
        else:
            sentiment = 0.0

        # Confidence based on keyword density
        confidence = min(0.9, total_keywords / 10)

        return sentiment, confidence

    def _determine_alert_level(
        self,
        sentiment: float,
        confidence: float,
        has_critical_keywords: bool
    ) -> str:
        """
        Determine alert level

        CRITICAL: Immediate action required
        HIGH: Should review soon
        MEDIUM: Worth noting
        LOW: FYI
        """
        if has_critical_keywords and confidence > 0.7:
            return "CRITICAL"

        if abs(sentiment) > 0.6 and confidence > 0.6:
            return "HIGH"

        if abs(sentiment) > 0.4:
            return "MEDIUM"

        return "LOW"

    async def _notify_alert(self, alert: NewsAlert):
        """Notify all callbacks about news alert"""
        logger.info(
            f"📰 NEWS ALERT: {alert.symbol} [{alert.alert_level}]\n"
            f"   Headline: {alert.headline}\n"
            f"   Sentiment: {alert.sentiment:.2f} (confidence: {alert.sentiment_confidence:.2f})\n"
            f"   Action: {alert.suggested_action}"
        )

        for callback in self.on_alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    async def create_mock_alert(self, symbol: str, headline: str, is_positive: bool = True) -> NewsAlert:
        """
        Helper to create mock alerts for testing

        Args:
            symbol: Stock symbol
            headline: News headline
            is_positive: True for positive news, False for negative
        """
        sentiment = 0.75 if is_positive else -0.65
        sentiment_confidence = 0.8

        alert_level = "HIGH"
        if any(kw in headline.lower() for kw in self.critical_keywords):
            alert_level = "CRITICAL"

        suggested_action = "BUY" if is_positive else "SELL"

        rationale = []
        if is_positive:
            rationale = ["Positive news sentiment", "Market opportunity", "Growth potential"]
        else:
            rationale = ["Negative news impact", "Risk alert", "Potential downside"]

        return NewsAlert(
            symbol=symbol,
            timestamp=datetime.now(),
            headline=headline,
            summary=headline,  # Simplified
            source="Mock News",
            sentiment=sentiment,
            sentiment_confidence=sentiment_confidence,
            alert_level=alert_level,
            urgency_score=0.9 if alert_level == "CRITICAL" else 0.7,
            suggested_action=suggested_action,
            rationale=rationale
        )


# Example usage
if __name__ == "__main__":
    async def on_alert(alert: NewsAlert):
        print(f"Alert received: {alert.symbol} - {alert.headline}")
        print(f"  Level: {alert.alert_level}")
        print(f"  Action: {alert.suggested_action}")

    scanner = NewsAlertScanner()
    scanner.add_alert_callback(on_alert)

    # Test with mock alert
    async def test():
        mock_alert = await scanner.create_mock_alert(
            symbol="ACB",
            headline="ACB được chấp thuận tăng vốn điều lệ lên 50,000 tỷ",
            is_positive=True
        )
        await scanner._notify_alert(mock_alert)

    asyncio.run(test())
