# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NEWS SENTIMENT TRADING                                    ║
║                    News Aggregation, Sentiment Analysis, Signal Generation  ║
╚══════════════════════════════════════════════════════════════════════════════╝

P2 Implementation - News-based trading signals
"""

import asyncio
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# DATA MODELS
# ============================================

class SentimentLevel(Enum):
    VERY_POSITIVE = 2
    POSITIVE = 1
    NEUTRAL = 0
    NEGATIVE = -1
    VERY_NEGATIVE = -2


@dataclass
class NewsArticle:
    """News article"""
    id: str
    title: str
    content: str
    source: str
    published_at: datetime
    url: str = ""
    symbols: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)


@dataclass
class SentimentResult:
    """Sentiment analysis result"""
    article_id: str
    symbol: str
    sentiment_score: float  # -1 to 1
    sentiment_level: SentimentLevel
    confidence: float
    keywords: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class NewsSignal:
    """Trading signal from news"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float
    sentiment_score: float
    news_count: int
    reasoning: str
    articles: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)


# ============================================
# NEWS SOURCES
# ============================================

class NewsSource:
    """Abstract news source"""
    
    async def fetch_news(self, symbols: List[str] = None, 
                        hours: int = 24) -> List[NewsArticle]:
        raise NotImplementedError


class CafeFNewsSource(NewsSource):
    """CafeF news source"""
    
    BASE_URL = "https://cafef.vn"
    
    async def fetch_news(self, symbols: List[str] = None,
                        hours: int = 24) -> List[NewsArticle]:
        """Fetch news from CafeF"""
        articles = []
        
        try:
            import aiohttp
            from bs4 import BeautifulSoup
            
            # Fetch main page or stock-specific pages
            urls = [f"{self.BASE_URL}/thi-truong-chung-khoan.chn"]
            
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    try:
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # Parse news items
                                for item in soup.select('.tlitem, .box-category-item'):
                                    title_elem = item.select_one('h3 a, .box-category-link-title')
                                    if title_elem:
                                        title = title_elem.get_text(strip=True)
                                        link = self.BASE_URL + title_elem.get('href', '')
                                        
                                        # Extract symbols from title
                                        extracted_symbols = self._extract_symbols(title)
                                        
                                        articles.append(NewsArticle(
                                            id=f"cafef_{hash(title) % 10000}",
                                            title=title,
                                            content="",
                                            source="CafeF",
                                            published_at=datetime.now(),
                                            url=link,
                                            symbols=extracted_symbols
                                        ))
                    except Exception as e:
                        logger.warning(f"Failed to fetch {url}: {e}")
                        continue
            
        except ImportError:
            logger.warning("aiohttp or beautifulsoup4 not installed")
        except Exception as e:
            logger.error(f"CafeF fetch error: {e}")
        
        # Filter by symbols if specified
        if symbols:
            articles = [a for a in articles if any(s in a.symbols for s in symbols)]
        
        return articles
    
    def _extract_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from text"""
        # Common VN stock symbol pattern: 3 uppercase letters
        pattern = r'\b([A-Z]{3})\b'
        matches = re.findall(pattern, text.upper())
        
        # Filter out common words that match pattern
        stopwords = {'THE', 'AND', 'FOR', 'VND', 'USD', 'VNA'}
        return [m for m in matches if m not in stopwords]


class VietStockNewsSource(NewsSource):
    """VietStock news source"""
    
    BASE_URL = "https://vietstock.vn"
    
    async def fetch_news(self, symbols: List[str] = None,
                        hours: int = 24) -> List[NewsArticle]:
        """Fetch news from VietStock"""
        articles = []
        
        try:
            import aiohttp
            from bs4 import BeautifulSoup
            
            urls = [f"{self.BASE_URL}/chung-khoan.htm"]
            
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    try:
                        async with session.get(url, timeout=10) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                for item in soup.select('.news-item'):
                                    title_elem = item.select_one('a.title')
                                    if title_elem:
                                        title = title_elem.get_text(strip=True)
                                        
                                        articles.append(NewsArticle(
                                            id=f"vs_{hash(title) % 10000}",
                                            title=title,
                                            content="",
                                            source="VietStock",
                                            published_at=datetime.now(),
                                            url=self.BASE_URL + title_elem.get('href', ''),
                                            symbols=self._extract_symbols(title)
                                        ))
                    except Exception as e:
                        logger.warning(f"VietStock fetch error: {e}")
                        continue
                        
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"VietStock error: {e}")
        
        return articles
    
    def _extract_symbols(self, text: str) -> List[str]:
        pattern = r'\b([A-Z]{3})\b'
        return re.findall(pattern, text.upper())


# ============================================
# SENTIMENT ANALYZER
# ============================================

class SentimentAnalyzer:
    """
    Analyze news sentiment
    
    Uses keyword-based analysis with optional LLM enhancement
    """
    
    # Vietnamese and English sentiment keywords
    POSITIVE_KEYWORDS = {
        # Vietnamese
        'tăng', 'tăng trưởng', 'lợi nhuận', 'đột phá', 'kỷ lục',
        'thắng lợi', 'khởi sắc', 'bứt phá', 'thành công', 'thuận lợi',
        'tích cực', 'lạc quan', 'triển vọng', 'cơ hội', 'mua vào',
        'đầu tư', 'phục hồi', 'khởi sắc', 'bền vững', 'ổn định',
        # English
        'up', 'gain', 'profit', 'growth', 'record', 'breakthrough',
        'bullish', 'optimistic', 'opportunity', 'buy', 'invest',
        'recover', 'surge', 'rally', 'advance', 'rise'
    }
    
    NEGATIVE_KEYWORDS = {
        # Vietnamese
        'giảm', 'sụt giảm', 'thua lỗ', 'khó khăn', 'suy thoái',
        'bán tháo', 'cảnh báo', 'rủi ro', 'tiêu cực', 'bi quan',
        'đóng cửa', 'phá sản', 'nợ xấu', 'thoái vốn', 'bán ra',
        'lo ngại', 'biến động', 'điều chỉnh', 'áp lực', 'sụp đổ',
        # English
        'down', 'loss', 'decline', 'crash', 'risk', 'warning',
        'bearish', 'pessimistic', 'sell', 'dump', 'plunge',
        'drop', 'fall', 'trouble', 'bankruptcy', 'debt'
    }
    
    STRONG_POSITIVE = {'đột phá', 'kỷ lục', 'bứt phá', 'surge', 'breakthrough', 'record'}
    STRONG_NEGATIVE = {'phá sản', 'sụp đổ', 'bán tháo', 'crash', 'bankruptcy', 'plunge'}
    
    def __init__(self, use_llm: bool = False, llm_api_key: str = None):
        self.use_llm = use_llm
        self.llm_api_key = llm_api_key
    
    def analyze(self, article: NewsArticle, symbol: str = None) -> SentimentResult:
        """Analyze sentiment of article"""
        text = f"{article.title} {article.content}".lower()
        
        # Count keyword matches
        positive_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
        negative_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)
        
        # Strong keywords have extra weight
        positive_count += sum(2 for kw in self.STRONG_POSITIVE if kw in text)
        negative_count += sum(2 for kw in self.STRONG_NEGATIVE if kw in text)
        
        # Calculate score (-1 to 1)
        total = positive_count + negative_count
        if total == 0:
            score = 0
            confidence = 0.3  # Low confidence for neutral
        else:
            score = (positive_count - negative_count) / total
            confidence = min(0.9, 0.4 + 0.1 * total)  # More keywords = higher confidence
        
        # Determine level
        if score >= 0.6:
            level = SentimentLevel.VERY_POSITIVE
        elif score >= 0.2:
            level = SentimentLevel.POSITIVE
        elif score <= -0.6:
            level = SentimentLevel.VERY_NEGATIVE
        elif score <= -0.2:
            level = SentimentLevel.NEGATIVE
        else:
            level = SentimentLevel.NEUTRAL
        
        # Extract matching keywords
        matched_keywords = []
        for kw in self.POSITIVE_KEYWORDS | self.NEGATIVE_KEYWORDS:
            if kw in text:
                matched_keywords.append(kw)
        
        return SentimentResult(
            article_id=article.id,
            symbol=symbol or (article.symbols[0] if article.symbols else ""),
            sentiment_score=score,
            sentiment_level=level,
            confidence=confidence,
            keywords=matched_keywords[:10],
            summary=article.title[:200]
        )
    
    async def analyze_with_llm(self, article: NewsArticle, 
                               symbol: str = None) -> SentimentResult:
        """Analyze sentiment using LLM (Gemini/OpenAI)"""
        if not self.llm_api_key:
            return self.analyze(article, symbol)
        
        try:
            import aiohttp
            
            prompt = f"""
            Analyze the sentiment of this Vietnamese stock market news article.
            
            Title: {article.title}
            Content: {article.content[:500] if article.content else 'N/A'}
            
            Return JSON:
            {{
                "sentiment_score": float (-1 to 1),
                "confidence": float (0 to 1),
                "summary": "one sentence summary",
                "keywords": ["key", "words"]
            }}
            """
            
            # Call Gemini or OpenAI API
            # Implementation depends on the API
            pass
            
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")
            return self.analyze(article, symbol)


# ============================================
# NEWS SIGNAL GENERATOR
# ============================================

class NewsSignalGenerator:
    """
    Generate trading signals from news sentiment
    """
    
    def __init__(self, sentiment_threshold: float = 0.3,
                 min_articles: int = 2,
                 min_confidence: float = 0.5):
        self.sentiment_threshold = sentiment_threshold
        self.min_articles = min_articles
        self.min_confidence = min_confidence
        self.analyzer = SentimentAnalyzer()
    
    def generate_signal(self, sentiments: List[SentimentResult]) -> Optional[NewsSignal]:
        """
        Generate trading signal from multiple sentiment results
        
        Args:
            sentiments: List of sentiment results for same symbol
        """
        if len(sentiments) < self.min_articles:
            return None
        
        symbol = sentiments[0].symbol
        
        # Calculate aggregate sentiment
        scores = [s.sentiment_score for s in sentiments]
        confidences = [s.confidence for s in sentiments]
        
        weighted_score = sum(s * c for s, c in zip(scores, confidences)) / sum(confidences)
        avg_confidence = sum(confidences) / len(confidences)
        
        if avg_confidence < self.min_confidence:
            return None
        
        # Determine action
        if weighted_score >= self.sentiment_threshold:
            action = "BUY"
            reasoning = f"Strong positive sentiment ({weighted_score:.2f}) from {len(sentiments)} articles"
        elif weighted_score <= -self.sentiment_threshold:
            action = "SELL"
            reasoning = f"Strong negative sentiment ({weighted_score:.2f}) from {len(sentiments)} articles"
        else:
            action = "HOLD"
            reasoning = f"Neutral sentiment ({weighted_score:.2f}) from {len(sentiments)} articles"
        
        return NewsSignal(
            symbol=symbol,
            action=action,
            confidence=avg_confidence,
            sentiment_score=weighted_score,
            news_count=len(sentiments),
            reasoning=reasoning,
            articles=[s.article_id for s in sentiments]
        )


# ============================================
# NEWS TRADING ENGINE
# ============================================

class NewsTradingEngine:
    """
    Real-time news trading engine
    
    Monitors news sources and generates trading signals
    """
    
    def __init__(self, watchlist: List[str] = None):
        self.watchlist = watchlist or []
        self.sources = [
            CafeFNewsSource(),
            VietStockNewsSource()
        ]
        self.analyzer = SentimentAnalyzer()
        self.signal_generator = NewsSignalGenerator()
        self.signals_history: List[NewsSignal] = []
        self._running = False
    
    def add_symbol(self, symbol: str):
        """Add symbol to watchlist"""
        if symbol.upper() not in self.watchlist:
            self.watchlist.append(symbol.upper())
    
    def remove_symbol(self, symbol: str):
        """Remove symbol from watchlist"""
        if symbol.upper() in self.watchlist:
            self.watchlist.remove(symbol.upper())
    
    async def fetch_all_news(self, hours: int = 24) -> List[NewsArticle]:
        """Fetch news from all sources"""
        all_articles = []
        
        for source in self.sources:
            try:
                articles = await source.fetch_news(self.watchlist, hours)
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"Source error: {e}")
        
        # Remove duplicates by title
        seen = set()
        unique = []
        for article in all_articles:
            if article.title not in seen:
                seen.add(article.title)
                unique.append(article)
        
        return unique
    
    async def analyze_news(self, hours: int = 24) -> Dict[str, List[NewsSignal]]:
        """
        Analyze recent news and generate signals
        
        Returns: Dict of symbol -> signals
        """
        articles = await self.fetch_all_news(hours)
        logger.info(f"Fetched {len(articles)} articles")
        
        # Analyze each article
        sentiments_by_symbol: Dict[str, List[SentimentResult]] = {}
        
        for article in articles:
            for symbol in article.symbols:
                if self.watchlist and symbol not in self.watchlist:
                    continue
                
                sentiment = self.analyzer.analyze(article, symbol)
                
                if symbol not in sentiments_by_symbol:
                    sentiments_by_symbol[symbol] = []
                sentiments_by_symbol[symbol].append(sentiment)
        
        # Generate signals
        signals: Dict[str, List[NewsSignal]] = {}
        
        for symbol, sentiments in sentiments_by_symbol.items():
            signal = self.signal_generator.generate_signal(sentiments)
            if signal:
                signals[symbol] = [signal]
                self.signals_history.append(signal)
        
        return signals
    
    async def run_monitoring(self, interval_minutes: int = 30):
        """Run continuous news monitoring"""
        self._running = True
        
        while self._running:
            try:
                signals = await self.analyze_news(hours=2)
                
                if signals:
                    logger.info(f"Generated signals: {list(signals.keys())}")
                    for symbol, signal_list in signals.items():
                        for signal in signal_list:
                            logger.info(
                                f"📰 {signal.symbol}: {signal.action} "
                                f"(sentiment: {signal.sentiment_score:.2f}, "
                                f"confidence: {signal.confidence:.2f})"
                            )
                
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(60)
    
    def stop(self):
        """Stop monitoring"""
        self._running = False
    
    def get_signals_history(self, symbol: str = None,
                           limit: int = 100) -> List[NewsSignal]:
        """Get signal history"""
        history = self.signals_history
        if symbol:
            history = [s for s in history if s.symbol == symbol]
        return history[-limit:]


# ============================================
# TESTING
# ============================================

async def test_news_trading():
    """Test news sentiment trading"""
    print("Testing News Sentiment Trading...")
    print("=" * 50)
    
    # Test sentiment analyzer
    analyzer = SentimentAnalyzer()
    
    test_articles = [
        NewsArticle(
            id="1",
            title="HPG lãi kỷ lục quý 4, cổ phiếu bứt phá mạnh",
            content="",
            source="CafeF",
            published_at=datetime.now(),
            symbols=["HPG"]
        ),
        NewsArticle(
            id="2",
            title="VNM giảm mạnh, nhà đầu tư lo ngại triển vọng",
            content="",
            source="VietStock",
            published_at=datetime.now(),
            symbols=["VNM"]
        ),
        NewsArticle(
            id="3",
            title="FPT ký hợp đồng lớn với đối tác Nhật Bản",
            content="",
            source="CafeF",
            published_at=datetime.now(),
            symbols=["FPT"]
        )
    ]
    
    print("\n📰 Sentiment Analysis:")
    for article in test_articles:
        result = analyzer.analyze(article)
        emoji = "🟢" if result.sentiment_score > 0 else "🔴" if result.sentiment_score < 0 else "⚪"
        print(f"   {emoji} {result.symbol}: {result.sentiment_score:.2f} ({result.sentiment_level.name})")
        print(f"      Keywords: {', '.join(result.keywords[:5])}")
    
    # Test signal generation
    print("\n📊 Signal Generation:")
    generator = NewsSignalGenerator(min_articles=1)  # Lower threshold for testing
    
    for article in test_articles:
        sentiment = analyzer.analyze(article)
        signal = generator.generate_signal([sentiment])
        if signal:
            print(f"   {signal.symbol}: {signal.action} (confidence: {signal.confidence:.2f})")
    
    # Test news engine (without actual fetching)
    print("\n🔍 News Trading Engine:")
    engine = NewsTradingEngine(watchlist=['HPG', 'VNM', 'FPT'])
    print(f"   Watchlist: {engine.watchlist}")
    print(f"   Sources: {len(engine.sources)}")
    
    print("\n✅ News Sentiment Trading tests completed!")


if __name__ == "__main__":
    asyncio.run(test_news_trading())
