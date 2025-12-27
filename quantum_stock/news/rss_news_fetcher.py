# -*- coding: utf-8 -*-
"""
RSS News Fetcher for Vietnamese Stock Market
=============================================
Fetches real news from CafeF, VnExpress, VietStock RSS feeds
"""

import feedparser
import re
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VNStockNewsFetcher:
    """Fetch and parse Vietnamese stock market news from RSS feeds"""

    # RSS feed URLs - SPECIALIZED FOR STOCKS ONLY
    RSS_FEEDS = {
        # VietStock - Stock-specific feeds
        'VietStock_Stocks': 'https://vietstock.vn/830/chung-khoan/co-phieu.rss',
        'VietStock_Insider': 'https://vietstock.vn/739/chung-khoan/giao-dich-noi-bo.rss',
        'VietStock_Business': 'https://vietstock.vn/737/doanh-nghiep/hoat-dong-kinh-doanh.rss',
        'VietStock_Dividends': 'https://vietstock.vn/738/doanh-nghiep/co-tuc.rss',

        # CafeF - Stock market feed
        'CafeF_Stocks': 'https://cafef.vn/thi-truong-chung-khoan.chn.rss',

        # VnExpress - Stock section only (if available)
        'VnExpress_Stocks': 'https://vnexpress.net/rss/chung-khoan.rss',
    }

    # Stock-related keywords to filter news (Vietnamese)
    STOCK_RELATED_KEYWORDS = [
        'cổ phiếu', 'chứng khoán', 'niêm yết', 'thị trường', 'giao dịch',
        'cổ tức', 'vn-index', 'hnx', 'hose', 'upcom', 'hđqt', 'đhđcđ',
        'nội bộ', 'blue chip', 'midcap', 'smallcap', 'penny',
        'khối lượng', 'thanh khoản', 'giá cổ phiếu', 'mã cổ phiếu'
    ]

    # Common Vietnamese stock symbols (for keyword matching)
    STOCK_KEYWORDS = [
        'VCB', 'VHM', 'VIC', 'HPG', 'VNM', 'VPB', 'GAS', 'MSN', 'MWG', 'TCB',
        'BID', 'CTG', 'ACB', 'FPT', 'SSI', 'VRE', 'HDB', 'POW', 'PLX', 'STB',
        'MBB', 'VJC', 'VIB', 'GVR', 'PDR', 'NVL', 'TPB', 'BCM', 'SAB', 'PNJ',
    ]

    # Sentiment keywords (Vietnamese)
    BULLISH_KEYWORDS = [
        'tăng', 'tích cực', 'lợi nhuận', 'tăng trưởng', 'phát triển', 'mở rộng',
        'khả quan', 'lạc quan', 'thành công', 'đầu tư', 'hợp tác', 'ký kết',
        'mua', 'nâng', 'cao', 'dương', 'vượt', 'đột phá', 'tiến bộ'
    ]

    BEARISH_KEYWORDS = [
        'giảm', 'sụt giảm', 'tiêu cực', 'lỗ', 'rủi ro', 'lo ngại', 'khó khăn',
        'suy giảm', 'thận trọng', 'cảnh báo', 'bán', 'hạ', 'thấp', 'âm',
        'giảm sút', 'yếu', 'mất', 'thiệt hại', 'vấn đề'
    ]

    def __init__(self):
        self.cache = {}
        self.last_fetch = None

    def fetch_all_feeds(self, max_items: int = 20) -> List[Dict]:
        """Fetch news from all RSS feeds"""
        all_news = []

        for source, feed_url in self.RSS_FEEDS.items():
            try:
                news_items = self._fetch_feed(source, feed_url, max_items)
                all_news.extend(news_items)
                logger.info(f"✅ Fetched {len(news_items)} items from {source}")
            except Exception as e:
                logger.error(f"❌ Failed to fetch {source}: {e}")
                continue

        # Sort by publish date (newest first)
        all_news.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        return all_news[:max_items]

    def _fetch_feed(self, source: str, feed_url: str, max_items: int = 10) -> List[Dict]:
        """Fetch news from a single RSS feed"""
        news_items = []

        try:
            # Parse RSS feed
            feed = feedparser.parse(feed_url)

            if not feed.entries:
                logger.warning(f"No entries found in {source}")
                return []

            # Process each entry
            for entry in feed.entries[:max_items]:
                news_item = self._parse_entry(entry, source)
                if news_item:
                    news_items.append(news_item)

        except Exception as e:
            logger.error(f"Error parsing {source}: {e}")

        return news_items

    def _parse_entry(self, entry, source: str) -> Optional[Dict]:
        """Parse a single RSS entry"""
        try:
            # Extract basic info
            title = entry.get('title', '').strip()
            summary = entry.get('summary', entry.get('description', '')).strip()
            link = entry.get('link', '')

            # Remove HTML tags from summary
            summary = re.sub(r'<[^>]+>', '', summary)
            summary = summary[:300]  # Limit length

            # ===== STRICT FILTER: Stock-related news only =====
            full_text = (title + ' ' + summary).lower()

            # Check 1: Must have stock symbols OR stock-related keywords
            has_stock_symbol = self._has_stock_symbols(full_text)
            has_stock_keywords = self._has_stock_keywords(full_text)

            if not (has_stock_symbol or has_stock_keywords):
                # Skip non-stock news (like "giá bạc", "mì ăn liền", etc.)
                logger.debug(f"Skipping non-stock news: {title[:50]}")
                return None

            # Parse publish date
            published = entry.get('published', entry.get('updated', ''))
            try:
                pub_date = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
            except:
                pub_date = datetime.now()

            # Extract stock symbols mentioned
            symbols = self._extract_symbols(title + ' ' + summary)

            # Analyze sentiment
            sentiment_score = self._analyze_sentiment(title + ' ' + summary)
            sentiment = 'bullish' if sentiment_score > 0.6 else 'bearish' if sentiment_score < 0.4 else 'neutral'

            # Calculate confidence based on keyword matches
            confidence = self._calculate_confidence(title, summary, symbols)

            # Generate recommendation
            recommendation = 'MUA' if sentiment == 'bullish' else 'BÁN' if sentiment == 'bearish' else 'GIỮ'

            return {
                'symbol': symbols[0] if symbols else 'VNINDEX',
                'headline': title,
                'summary': summary,
                'news_summary': f"{title[:150]}...",
                'technical_summary': f"Tin tức từ {source} - Phân tích sentiment tự động",
                'recommendation': recommendation,
                'sentiment': sentiment,
                'news_sentiment': sentiment_score,
                'confidence': confidence,
                'priority': 'HIGH' if symbols and sentiment != 'neutral' else 'MEDIUM',
                'type': 'NEWS_ALERT',
                'timestamp': pub_date.isoformat(),
                'source': source,
                'url': link,
                'related_symbols': symbols
            }

        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return None

    def _has_stock_symbols(self, text: str) -> bool:
        """Check if text contains any stock symbols"""
        text_upper = text.upper()
        for symbol in self.STOCK_KEYWORDS:
            pattern = r'\b' + symbol + r'\b'
            if re.search(pattern, text_upper):
                return True
        return False

    def _has_stock_keywords(self, text: str) -> bool:
        """Check if text contains stock-related keywords"""
        text_lower = text.lower()
        for keyword in self.STOCK_RELATED_KEYWORDS:
            if keyword in text_lower:
                return True
        return False

    def _extract_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from text"""
        symbols = []
        text_upper = text.upper()

        for symbol in self.STOCK_KEYWORDS:
            # Look for symbol as whole word
            pattern = r'\b' + symbol + r'\b'
            if re.search(pattern, text_upper):
                symbols.append(symbol)

        return symbols

    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment score (0.0 = bearish, 1.0 = bullish)"""
        text_lower = text.lower()

        bullish_count = sum(1 for word in self.BULLISH_KEYWORDS if word in text_lower)
        bearish_count = sum(1 for word in self.BEARISH_KEYWORDS if word in text_lower)

        total_count = bullish_count + bearish_count

        if total_count == 0:
            return 0.5  # Neutral

        # Calculate score (0.0 to 1.0)
        score = bullish_count / total_count

        # Normalize to range 0.2-0.8 (more realistic)
        score = 0.2 + (score * 0.6)

        return round(score, 2)

    def _calculate_confidence(self, title: str, summary: str, symbols: List[str]) -> float:
        """Calculate confidence score based on content quality"""
        confidence = 0.5  # Base confidence

        # Boost if specific symbols mentioned
        if symbols:
            confidence += 0.2

        # Boost if title is detailed (longer)
        if len(title) > 50:
            confidence += 0.1

        # Boost if summary is substantial
        if len(summary) > 100:
            confidence += 0.15

        # Cap at 0.95
        confidence = min(confidence, 0.95)

        return round(confidence, 2)

    def get_alerts_for_symbols(self, symbols: List[str], limit: int = 10) -> List[Dict]:
        """Get news alerts filtered by specific symbols"""
        all_news = self.fetch_all_feeds(max_items=50)

        # Filter by symbols
        filtered = [
            news for news in all_news
            if news.get('symbol') in symbols or
               any(sym in news.get('related_symbols', []) for sym in symbols)
        ]

        return filtered[:limit]


# Singleton instance
_fetcher = None

def get_news_fetcher() -> VNStockNewsFetcher:
    """Get singleton news fetcher instance"""
    global _fetcher
    if _fetcher is None:
        _fetcher = VNStockNewsFetcher()
    return _fetcher


# Test function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("TESTING RSS NEWS FETCHER")
    print("=" * 60)

    fetcher = VNStockNewsFetcher()

    print("\n📰 Fetching news from all sources...")
    news = fetcher.fetch_all_feeds(max_items=10)

    print(f"\n✅ Found {len(news)} news items\n")

    for i, item in enumerate(news[:5], 1):
        print(f"\n{i}. {item['headline'][:80]}")
        print(f"   Symbol: {item['symbol']}")
        print(f"   Source: {item['source']}")
        print(f"   Sentiment: {item['sentiment']} ({item['news_sentiment']:.2f})")
        print(f"   Recommendation: {item['recommendation']}")
        print(f"   URL: {item['url'][:60]}...")
        print(f"   Summary: {item['summary'][:100]}...")

    print("\n" + "=" * 60)
