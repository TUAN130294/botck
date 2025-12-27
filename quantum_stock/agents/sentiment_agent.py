# -*- coding: utf-8 -*-
"""
Sentiment Agent - Agentic Level 3
Analyzes news and social sentiment for Vietnamese stocks

Features:
- News sentiment analysis
- Social media monitoring
- Self-reflection and calibration
- Memory of past predictions
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .base_agent import BaseAgent, AgentSignal, AgentMessage


@dataclass
class SentimentData:
    """Sentiment analysis data"""
    source: str
    headline: str
    sentiment_score: float  # -1 to 1
    confidence: float
    timestamp: datetime
    symbols: List[str]
    keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'headline': self.headline,
            'sentiment': self.sentiment_score,
            'confidence': self.confidence,
            'timestamp': str(self.timestamp),
            'symbols': self.symbols,
            'keywords': self.keywords
        }


class SentimentAgent(BaseAgent):
    """
    Sentiment Analysis Agent - Level 3 Agentic
    
    Responsibilities:
    - Analyze news sentiment
    - Track social media buzz
    - Self-calibrate based on past accuracy
    - Provide sentiment-based signals
    """
    
    def __init__(self):
        super().__init__(
            name="SENTIMENT_SCOUT",
            role="Sentiment Analyst",
            description="Analyzes news and social sentiment for Vietnamese stocks",
            weight=0.9
        )
        
        # Memory for self-reflection
        self.prediction_history: List[Dict] = []
        self.accuracy_score: float = 0.7  # Initial calibration
        
        # Vietnamese sentiment keywords
        self.bullish_keywords = [
            'tăng mạnh', 'đột phá', 'lợi nhuận kỷ lục', 'tích cực', 'triển vọng',
            'khuyến nghị mua', 'outperform', 'mua vào', 'tăng trưởng', 'bùng nổ',
            'vượt kỳ vọng', 'cổ tức cao', 'hợp đồng lớn', 'M&A', 'IPO thành công'
        ]
        
        self.bearish_keywords = [
            'giảm mạnh', 'lo ngại', 'rủi ro', 'thua lỗ', 'cảnh báo',
            'khuyến nghị bán', 'underperform', 'bán ra', 'suy giảm', 'khó khăn',
            'nợ xấu', 'kiểm toán', 'thanh tra', 'điều tra', 'phá sản'
        ]
        
        # Source credibility weights
        self.source_weights = {
            'VNDirect': 0.9,
            'SSI': 0.9,
            'VietStock': 0.85,
            'CafeF': 0.8,
            'VnExpress': 0.75,
            'Tuoi Tre': 0.7,
            'Unknown': 0.5
        }
    
    async def analyze(self, stock_data: Any, context: Dict[str, Any] = None) -> AgentSignal:
        """Analyze sentiment for given stock"""
        symbol = stock_data.symbol if hasattr(stock_data, 'symbol') else 'UNKNOWN'
        
        # Get news from context
        news_items = context.get('news', []) if context else []
        
        # Analyze sentiment
        sentiment_scores = []
        messages = []
        
        for news in news_items:
            sentiment = self._analyze_headline(news)
            if sentiment:
                # Apply source credibility weight
                source = news.get('source', 'Unknown')
                credibility = self.source_weights.get(source, 0.5)
                weighted_sentiment = sentiment * credibility
                sentiment_scores.append(weighted_sentiment)
                
                if abs(sentiment) > 0.3:
                    direction = "tích cực" if sentiment > 0 else "tiêu cực"
                    messages.append(f"📰 {source}: {news.get('title', '')[:50]}... ({direction})")
        
        # Calculate overall sentiment
        if sentiment_scores:
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            sentiment_std = (sum((s - avg_sentiment)**2 for s in sentiment_scores) / len(sentiment_scores)) ** 0.5
        else:
            avg_sentiment = 0.0
            sentiment_std = 0.5
        
        # Self-calibrate confidence based on past accuracy
        base_confidence = 0.5 + abs(avg_sentiment) * 0.3
        calibrated_confidence = base_confidence * self.accuracy_score
        
        # Generate signal
        if abs(avg_sentiment) < 0.15:
            signal = "NEUTRAL"
            reasoning = f"Tin tức {symbol} không có xu hướng rõ ràng"
        elif avg_sentiment > 0.15:
            signal = "LONG"
            reasoning = f"Sentiment tích cực cho {symbol} từ {len(sentiment_scores)} nguồn tin"
        else:
            signal = "SHORT"
            reasoning = f"Sentiment tiêu cực cho {symbol} cần thận trọng"
        
        # Add recent news to reasoning
        if messages:
            reasoning += "\n\nTin nổi bật:\n" + "\n".join(messages[:3])
        
        # Store prediction for future calibration
        self._store_prediction(symbol, avg_sentiment, signal)
        
        return AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=calibrated_confidence,
            entry_price=stock_data.close if hasattr(stock_data, 'close') else 0,
            stop_loss=None,
            take_profit=None,
            reasoning=reasoning,
            key_factors=[
                f"Sentiment Score: {avg_sentiment:.2f}",
                f"News Count: {len(sentiment_scores)}",
                f"Sentiment Volatility: {sentiment_std:.2f}",
                f"Model Accuracy: {self.accuracy_score:.0%}"
            ],
            timestamp=datetime.now()
        )
    
    def _analyze_headline(self, news: Dict) -> Optional[float]:
        """Analyze sentiment of a single news headline"""
        title = news.get('title', '').lower()
        content = news.get('content', '').lower()
        text = title + ' ' + content
        
        if not text.strip():
            return None
        
        bullish_count = sum(1 for kw in self.bullish_keywords if kw in text)
        bearish_count = sum(1 for kw in self.bearish_keywords if kw in text)
        
        total = bullish_count + bearish_count
        if total == 0:
            return 0.0
        
        sentiment = (bullish_count - bearish_count) / total
        return sentiment
    
    def _store_prediction(self, symbol: str, sentiment: float, signal: str):
        """Store prediction for future calibration"""
        self.prediction_history.append({
            'symbol': symbol,
            'sentiment': sentiment,
            'signal': signal,
            'timestamp': datetime.now()
        })
        
        # Keep only last 100 predictions
        if len(self.prediction_history) > 100:
            self.prediction_history = self.prediction_history[-100:]
    
    def calibrate_accuracy(self, actual_outcomes: List[Dict]):
        """
        Self-reflection: Update accuracy based on actual outcomes
        
        Args:
            actual_outcomes: List of {symbol, predicted_signal, actual_return}
        """
        if not actual_outcomes:
            return
        
        correct = 0
        for outcome in actual_outcomes:
            predicted = outcome.get('predicted_signal')
            actual_return = outcome.get('actual_return', 0)
            
            if predicted == 'LONG' and actual_return > 0:
                correct += 1
            elif predicted == 'SHORT' and actual_return < 0:
                correct += 1
            elif predicted == 'NEUTRAL' and abs(actual_return) < 0.02:
                correct += 1
        
        new_accuracy = correct / len(actual_outcomes)
        
        # Exponential moving average for accuracy
        self.accuracy_score = 0.7 * self.accuracy_score + 0.3 * new_accuracy
        
        self.add_message(AgentMessage(
            agent_name=self.name,
            message_type="CALIBRATION",
            content=f"Updated accuracy: {self.accuracy_score:.0%}",
            data={'new_accuracy': new_accuracy, 'sample_size': len(actual_outcomes)}
        ))
    
    async def respond_to_debate(self, topic: str, previous_rounds: List) -> str:
        """Participate in multi-agent debate"""
        # Summarize sentiment perspective
        response = f"[{self.name}] Từ góc độ sentiment: "
        
        if self.last_signal:
            if self.last_signal.signal == 'LONG':
                response += f"Tin tức tích cực với confidence {self.last_signal.confidence:.0%}. "
            elif self.last_signal.signal == 'SHORT':
                response += f"Cảnh báo sentiment tiêu cực. "
            else:
                response += "Không có tín hiệu rõ ràng từ tin tức. "
        
        # Consider other agents' opinions
        if previous_rounds:
            last_round = previous_rounds[-1]
            bullish_count = sum(1 for r in last_round if 'LONG' in r or 'BUY' in r)
            bearish_count = sum(1 for r in last_round if 'SHORT' in r or 'SELL' in r)
            
            if bullish_count > bearish_count:
                response += "Đồng ý với đa số agents về xu hướng tích cực."
            elif bearish_count > bullish_count:
                response += "Đồng ý với quan điểm thận trọng của team."
        
        return response
