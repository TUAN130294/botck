"""
Conversational AI Quant Analyst - Natural Language Interface
Enables natural language queries for stock analysis
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
import re
import os


class QueryIntent(Enum):
    """Detected intents from user queries"""
    ANALYZE_STOCK = "ANALYZE_STOCK"
    GET_RECOMMENDATION = "GET_RECOMMENDATION"
    CHECK_PORTFOLIO = "CHECK_PORTFOLIO"
    RUN_BACKTEST = "RUN_BACKTEST"
    MONTE_CARLO = "MONTE_CARLO"
    COMPARE_STOCKS = "COMPARE_STOCKS"
    GET_MARKET_STATUS = "GET_MARKET_STATUS"
    GET_SECTOR_PERFORMANCE = "GET_SECTOR_PERFORMANCE"
    CHECK_ALERTS = "CHECK_ALERTS"
    SET_ALERT = "SET_ALERT"
    EXPLAIN_INDICATOR = "EXPLAIN_INDICATOR"
    GET_SMART_MONEY = "GET_SMART_MONEY"
    FIND_OPPORTUNITIES = "FIND_OPPORTUNITIES"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    UNKNOWN = "UNKNOWN"


@dataclass
class QueryResult:
    """Result from processing a natural language query"""
    intent: QueryIntent
    entities: Dict[str, Any]
    confidence: float
    response_text: str
    data: Optional[Dict[str, Any]] = None
    charts: List[Dict[str, Any]] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'intent': self.intent.value,
            'entities': self.entities,
            'confidence': self.confidence,
            'response_text': self.response_text,
            'data': self.data,
            'charts': self.charts,
            'suggested_actions': self.suggested_actions,
            'timestamp': self.timestamp.isoformat()
        }


class ConversationalQuant:
    """
    Natural language interface for the quant trading system.
    Processes user queries and returns structured responses.
    """
    
    # Vietnamese stock symbols pattern
    VN_STOCK_PATTERN = r'\b([A-Z]{3})\b'
    
    # Intent patterns (Vietnamese + English)
    INTENT_PATTERNS = {
        QueryIntent.ANALYZE_STOCK: [
            r'phân tích.*?([A-Z]{3})',
            r'analyze.*?([A-Z]{3})',
            r'đánh giá.*?([A-Z]{3})',
            r'xem.*?([A-Z]{3})',
            r'([A-Z]{3}).*?như thế nào',
            r'([A-Z]{3}).*?thế nào',
            r'view stock.*?([A-Z]{3})',
        ],
        QueryIntent.GET_RECOMMENDATION: [
            r'nên mua.*?([A-Z]{3})',
            r'should i buy.*?([A-Z]{3})',
            r'khuyến nghị.*?([A-Z]{3})',
            r'([A-Z]{3}).*?mua được không',
            r'recommend.*?([A-Z]{3})',
            r'([A-Z]{3}).*?có nên mua',
        ],
        QueryIntent.CHECK_PORTFOLIO: [
            r'danh mục',
            r'portfolio',
            r'đang hold',
            r'đang nắm',
            r'my stocks',
            r'tài khoản',
        ],
        QueryIntent.RUN_BACKTEST: [
            r'backtest.*?([A-Z]{3})',
            r'test chiến lược.*?([A-Z]{3})',
            r'kiểm tra.*?([A-Z]{3})',
            r'([A-Z]{3}).*?backtest',
        ],
        QueryIntent.MONTE_CARLO: [
            r'monte carlo.*?([A-Z]{3})',
            r'mô phỏng.*?([A-Z]{3})',
            r'simulation.*?([A-Z]{3})',
            r'dự báo.*?([A-Z]{3})',
            r'forecast.*?([A-Z]{3})',
        ],
        QueryIntent.COMPARE_STOCKS: [
            r'so sánh.*?([A-Z]{3}).*?([A-Z]{3})',
            r'compare.*?([A-Z]{3}).*?([A-Z]{3})',
            r'([A-Z]{3}).*?vs.*?([A-Z]{3})',
            r'([A-Z]{3}).*?so với.*?([A-Z]{3})',
        ],
        QueryIntent.GET_MARKET_STATUS: [
            r'thị trường',
            r'vn.?index',
            r'market',
            r'thị trường hôm nay',
            r'market today',
        ],
        QueryIntent.GET_SECTOR_PERFORMANCE: [
            r'ngành.*?(\w+)',
            r'sector.*?(\w+)',
            r'lĩnh vực',
            r'nhóm cổ phiếu',
        ],
        QueryIntent.CHECK_ALERTS: [
            r'cảnh báo',
            r'alerts?',
            r'thông báo',
            r'notifications?',
        ],
        QueryIntent.SET_ALERT: [
            r'đặt cảnh báo.*?([A-Z]{3})',
            r'set alert.*?([A-Z]{3})',
            r'báo.*?khi.*?([A-Z]{3})',
            r'notify.*?when.*?([A-Z]{3})',
        ],
        QueryIntent.EXPLAIN_INDICATOR: [
            r'giải thích.*?(rsi|macd|bollinger|ema|sma|adx)',
            r'explain.*?(rsi|macd|bollinger|ema|sma|adx)',
            r'(rsi|macd|bollinger|ema|sma|adx).*?là gì',
            r'what is.*?(rsi|macd|bollinger|ema|sma|adx)',
        ],
        QueryIntent.GET_SMART_MONEY: [
            r'dòng tiền',
            r'smart money',
            r'khối ngoại',
            r'foreign flow',
            r'tiền vào',
            r'tiền ra',
            r'institutional',
        ],
        QueryIntent.FIND_OPPORTUNITIES: [
            r'cơ hội',
            r'opportunities',
            r'tìm mã',
            r'gợi ý',
            r'scan',
            r'screening',
            r'tìm cổ phiếu',
        ],
        QueryIntent.RISK_ASSESSMENT: [
            r'rủi ro.*?([A-Z]{3})',
            r'risk.*?([A-Z]{3})',
            r'([A-Z]{3}).*?an toàn',
            r'([A-Z]{3}).*?safe',
        ],
    }
    
    # Indicator explanations
    INDICATOR_EXPLANATIONS = {
        'rsi': {
            'name': 'RSI (Relative Strength Index)',
            'description': 'Chỉ báo động lượng đo sức mạnh tương đối của giá.',
            'interpretation': {
                'overbought': 'RSI > 70: Quá mua, có thể điều chỉnh',
                'oversold': 'RSI < 30: Quá bán, có thể hồi phục',
                'neutral': 'RSI 30-70: Vùng trung lập'
            },
            'best_for': 'Xác định điểm đảo chiều ngắn hạn'
        },
        'macd': {
            'name': 'MACD (Moving Average Convergence Divergence)',
            'description': 'Chỉ báo xu hướng theo dõi đà tăng/giảm.',
            'interpretation': {
                'bullish': 'MACD cắt lên Signal Line: Tín hiệu mua',
                'bearish': 'MACD cắt xuống Signal Line: Tín hiệu bán',
                'histogram': 'Histogram dương tăng: Đà tăng mạnh'
            },
            'best_for': 'Xác định xu hướng và điểm vào/ra'
        },
        'bollinger': {
            'name': 'Bollinger Bands',
            'description': 'Dải biến động dựa trên độ lệch chuẩn.',
            'interpretation': {
                'upper_touch': 'Chạm dải trên: Có thể quá mua',
                'lower_touch': 'Chạm dải dưới: Có thể quá bán',
                'squeeze': 'Dải hẹp: Sắp có biến động lớn'
            },
            'best_for': 'Xác định biến động và điểm breakout'
        },
        'ema': {
            'name': 'EMA (Exponential Moving Average)',
            'description': 'Đường trung bình động phản ứng nhanh với giá.',
            'interpretation': {
                'above': 'Giá trên EMA: Xu hướng tăng',
                'below': 'Giá dưới EMA: Xu hướng giảm',
                'crossover': 'EMA ngắn cắt EMA dài: Tín hiệu vào/ra'
            },
            'best_for': 'Xác định xu hướng và hỗ trợ/kháng cự động'
        },
        'sma': {
            'name': 'SMA (Simple Moving Average)',
            'description': 'Đường trung bình động đơn giản.',
            'interpretation': {
                'sma_200': 'SMA200: Xu hướng dài hạn',
                'sma_50': 'SMA50: Xu hướng trung hạn',
                'golden_cross': 'SMA50 cắt lên SMA200: Golden Cross (tín hiệu mạnh)'
            },
            'best_for': 'Xác định xu hướng dài hạn'
        },
        'adx': {
            'name': 'ADX (Average Directional Index)',
            'description': 'Đo sức mạnh xu hướng (không phải hướng).',
            'interpretation': {
                'strong': 'ADX > 25: Xu hướng mạnh',
                'weak': 'ADX < 20: Xu hướng yếu/Sideway',
                'rising': 'ADX tăng: Xu hướng đang mạnh lên'
            },
            'best_for': 'Đánh giá sức mạnh xu hướng'
        }
    }
    
    def __init__(self, agent_coordinator=None, quantum_engine=None):
        self.agent_coordinator = agent_coordinator
        self.quantum_engine = quantum_engine
        self.conversation_history: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
    
    def process_query(self, query: str) -> QueryResult:
        """
        Process a natural language query and return structured result.
        
        Args:
            query: User's natural language query
            
        Returns:
            QueryResult with response
        """
        query_lower = query.lower().strip()
        
        # Detect intent and extract entities
        intent, entities, confidence = self._detect_intent(query_lower)
        
        # Process based on intent
        if intent == QueryIntent.ANALYZE_STOCK:
            return self._handle_analyze_stock(entities, confidence)
        
        elif intent == QueryIntent.GET_RECOMMENDATION:
            return self._handle_get_recommendation(entities, confidence)
        
        elif intent == QueryIntent.CHECK_PORTFOLIO:
            return self._handle_check_portfolio(confidence)
        
        elif intent == QueryIntent.RUN_BACKTEST:
            return self._handle_backtest(entities, confidence)
        
        elif intent == QueryIntent.MONTE_CARLO:
            return self._handle_monte_carlo(entities, confidence)
        
        elif intent == QueryIntent.COMPARE_STOCKS:
            return self._handle_compare_stocks(entities, confidence)
        
        elif intent == QueryIntent.GET_MARKET_STATUS:
            return self._handle_market_status(confidence)
        
        elif intent == QueryIntent.GET_SECTOR_PERFORMANCE:
            return self._handle_sector_performance(entities, confidence)
        
        elif intent == QueryIntent.EXPLAIN_INDICATOR:
            return self._handle_explain_indicator(entities, confidence)
        
        elif intent == QueryIntent.GET_SMART_MONEY:
            return self._handle_smart_money(entities, confidence)
        
        elif intent == QueryIntent.FIND_OPPORTUNITIES:
            return self._handle_find_opportunities(confidence)
        
        elif intent == QueryIntent.RISK_ASSESSMENT:
            return self._handle_risk_assessment(entities, confidence)
        
        else:
            return self._handle_unknown(query, confidence)
    
    def _detect_intent(self, query: str) -> tuple:
        """Detect intent and extract entities from query"""
        best_intent = QueryIntent.UNKNOWN
        best_confidence = 0.0
        entities = {}
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    confidence = 0.8 + (0.1 * len(match.groups()))
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_intent = intent
                        
                        # Extract entities from match groups
                        groups = match.groups()
                        if groups:
                            if len(groups) == 1:
                                entities['symbol'] = groups[0].upper()
                            elif len(groups) == 2:
                                entities['symbol1'] = groups[0].upper()
                                entities['symbol2'] = groups[1].upper()
        
        # Also try to extract any stock symbols mentioned
        stock_matches = re.findall(self.VN_STOCK_PATTERN, query.upper())
        if stock_matches and 'symbol' not in entities:
            entities['symbols'] = stock_matches
            if len(stock_matches) == 1:
                entities['symbol'] = stock_matches[0]
        
        return best_intent, entities, min(best_confidence, 0.95)
    
    def _handle_analyze_stock(self, entities: Dict[str, Any], 
                               confidence: float) -> QueryResult:
        """Handle stock analysis request"""
        symbol = entities.get('symbol', '')
        
        if not symbol:
            return QueryResult(
                intent=QueryIntent.ANALYZE_STOCK,
                entities=entities,
                confidence=confidence,
                response_text="Xin vui lòng cho biết mã cổ phiếu bạn muốn phân tích.",
                suggested_actions=["Nhập mã cổ phiếu VD: HPG, VNM, FPT"]
            )
        
        response = f"""
🔍 **Phân tích cổ phiếu {symbol}**

Đang thực hiện phân tích đa chiều...

📊 **Agents đang phân tích:**
- 🐂 Bull Advisor: Đánh giá cơ hội tăng giá
- 🐻 Bear Advisor: Đánh giá rủi ro giảm giá
- 📈 Alex Analyst: Phân tích kỹ thuật
- 🏥 Risk Doctor: Đánh giá rủi ro

⏳ Vui lòng đợi trong giây lát...
"""
        
        return QueryResult(
            intent=QueryIntent.ANALYZE_STOCK,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            data={'symbol': symbol, 'action': 'analyze'},
            suggested_actions=[
                f"Xem backtest {symbol}",
                f"Monte Carlo {symbol}",
                f"So sánh {symbol} với VN30"
            ]
        )
    
    def _handle_get_recommendation(self, entities: Dict[str, Any], 
                                    confidence: float) -> QueryResult:
        """Handle recommendation request"""
        symbol = entities.get('symbol', '')
        
        if not symbol:
            return QueryResult(
                intent=QueryIntent.GET_RECOMMENDATION,
                entities=entities,
                confidence=confidence,
                response_text="Mã cổ phiếu nào bạn đang cân nhắc mua?",
                suggested_actions=["Nhập mã cổ phiếu để nhận khuyến nghị"]
            )
        
        response = f"""
💡 **Khuyến nghị cho {symbol}**

🎖 **Kết luận của Chief AI:**
_Đang tổng hợp từ tất cả agents..._

📋 **Rating tổng hợp:**
- Điểm kỹ thuật: Đang tính...
- Điểm rủi ro: Đang tính...
- Độ tin cậy: Đang tính...

⚡ Pro tip: Luôn sử dụng stop-loss và không đầu tư quá 5% danh mục vào một mã.
"""
        
        return QueryResult(
            intent=QueryIntent.GET_RECOMMENDATION,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            data={'symbol': symbol, 'action': 'recommend'},
            suggested_actions=[
                f"Phân tích chi tiết {symbol}",
                f"Kiểm tra rủi ro {symbol}",
                "Xem các mã tương tự"
            ]
        )
    
    def _handle_check_portfolio(self, confidence: float) -> QueryResult:
        """Handle portfolio check request"""
        response = """
📊 **Danh mục đầu tư của bạn**

💼 **HOLD (Đang nắm giữ):**
_Đang tải dữ liệu..._

⏳ **PENDING (Chờ khớp):**
_Đang tải dữ liệu..._

👁 **WATCH (Theo dõi):**
_Đang tải dữ liệu..._

📈 **Tổng quan P&L:**
_Đang tính toán..._
"""
        
        return QueryResult(
            intent=QueryIntent.CHECK_PORTFOLIO,
            entities={},
            confidence=confidence,
            response_text=response.strip(),
            data={'action': 'get_portfolio'},
            suggested_actions=[
                "Phân tích danh mục",
                "Tối ưu hóa portfolio",
                "Kiểm tra rủi ro tổng thể"
            ]
        )
    
    def _handle_backtest(self, entities: Dict[str, Any], 
                          confidence: float) -> QueryResult:
        """Handle backtest request"""
        symbol = entities.get('symbol', '')
        
        response = f"""
🔬 **Backtest {symbol if symbol else 'chiến lược'}**

⚙️ **Chiến lược có sẵn:**
1. MA Crossover (Golden Cross)
2. RSI Reversal
3. MACD Signal
4. Bollinger Breakout

📅 **Khoảng thời gian mặc định:** 1 năm

_Chọn chiến lược hoặc nhập tham số tùy chỉnh..._
"""
        
        return QueryResult(
            intent=QueryIntent.RUN_BACKTEST,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            data={'symbol': symbol, 'action': 'backtest'},
            suggested_actions=[
                "Backtest MA Crossover",
                "Backtest RSI Reversal",
                "So sánh tất cả chiến lược"
            ]
        )
    
    def _handle_monte_carlo(self, entities: Dict[str, Any], 
                             confidence: float) -> QueryResult:
        """Handle Monte Carlo simulation request"""
        symbol = entities.get('symbol', '')
        
        response = f"""
🎲 **Monte Carlo Simulation {symbol if symbol else ''}**

📊 **Mô phỏng 10,000 kịch bản**

📈 **Output sẽ bao gồm:**
- Phân phối giá dự kiến (10 ngày)
- Xác suất lãi/lỗ
- VaR 95%, 99%
- CVaR (Expected Shortfall)
- Khuyến nghị position size (Kelly)

⏳ Đang khởi chạy mô phỏng...
"""
        
        return QueryResult(
            intent=QueryIntent.MONTE_CARLO,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            data={'symbol': symbol, 'action': 'monte_carlo'},
            suggested_actions=[
                "Xem chi tiết VaR",
                "Tính Kelly Criterion",
                "Xem histogram phân phối"
            ]
        )
    
    def _handle_compare_stocks(self, entities: Dict[str, Any], 
                                confidence: float) -> QueryResult:
        """Handle stock comparison request"""
        symbol1 = entities.get('symbol1', '')
        symbol2 = entities.get('symbol2', '')
        
        if not symbol1 or not symbol2:
            symbols = entities.get('symbols', [])
            if len(symbols) >= 2:
                symbol1, symbol2 = symbols[0], symbols[1]
        
        response = f"""
⚖️ **So sánh {symbol1} vs {symbol2}**

📊 **Tiêu chí so sánh:**
- Hiệu suất (1M, 3M, 1Y)
- Volatility
- Sharpe Ratio
- Beta vs VN30
- P/E, P/B

_Đang tải dữ liệu so sánh..._
"""
        
        return QueryResult(
            intent=QueryIntent.COMPARE_STOCKS,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            data={'symbol1': symbol1, 'symbol2': symbol2, 'action': 'compare'},
            suggested_actions=[
                f"Phân tích {symbol1}",
                f"Phân tích {symbol2}",
                "So sánh với benchmark"
            ]
        )
    
    def _handle_market_status(self, confidence: float) -> QueryResult:
        """Handle market status request"""
        response = """
🌏 **Tình hình thị trường chứng khoán Việt Nam**

📈 **VN-Index:**
_Đang tải..._

📊 **VN30:**
_Đang tải..._

💹 **Thống kê phiên:**
- Tổng GTGD: ...
- Số mã tăng/giảm: ...
- Khối ngoại: ...

🔥 **Điểm nóng:**
_Đang cập nhật..._
"""
        
        return QueryResult(
            intent=QueryIntent.GET_MARKET_STATUS,
            entities={},
            confidence=confidence,
            response_text=response.strip(),
            data={'action': 'market_status'},
            suggested_actions=[
                "Xem dòng tiền",
                "Phân tích VN30",
                "Tìm cơ hội"
            ]
        )
    
    def _handle_sector_performance(self, entities: Dict[str, Any], 
                                    confidence: float) -> QueryResult:
        """Handle sector performance request"""
        response = """
🏭 **Hiệu suất theo ngành**

📊 **Top tăng:**
1. ...
2. ...
3. ...

📉 **Top giảm:**
1. ...
2. ...
3. ...

💰 **Dòng tiền vào ngành:**
_Đang phân tích..._
"""
        
        return QueryResult(
            intent=QueryIntent.GET_SECTOR_PERFORMANCE,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            data={'action': 'sector_performance'},
            suggested_actions=[
                "Xem chi tiết ngành Ngân hàng",
                "Xem chi tiết ngành Bất động sản",
                "So sánh ngành"
            ]
        )
    
    def _handle_explain_indicator(self, entities: Dict[str, Any], 
                                   confidence: float) -> QueryResult:
        """Handle indicator explanation request"""
        indicator = entities.get('symbol', '').lower()
        
        if indicator in self.INDICATOR_EXPLANATIONS:
            info = self.INDICATOR_EXPLANATIONS[indicator]
            response = f"""
📚 **{info['name']}**

📝 **Mô tả:** {info['description']}

📊 **Cách đọc:**
"""
            for key, value in info['interpretation'].items():
                response += f"• {value}\n"
            
            response += f"\n💡 **Tốt nhất cho:** {info['best_for']}"
        else:
            response = "Xin chỉ rõ chỉ báo bạn muốn tìm hiểu (RSI, MACD, Bollinger, EMA, SMA, ADX)"
        
        return QueryResult(
            intent=QueryIntent.EXPLAIN_INDICATOR,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            suggested_actions=[
                "Giải thích RSI",
                "Giải thích MACD",
                "Giải thích Bollinger Bands"
            ]
        )
    
    def _handle_smart_money(self, entities: Dict[str, Any], 
                             confidence: float) -> QueryResult:
        """Handle smart money flow request"""
        response = """
💰 **Phân tích dòng tiền thông minh (Smart Money)**

🏦 **Khối ngoại:**
- Mua ròng: ...
- Bán ròng: ...
- Top mua: ...
- Top bán: ...

🏢 **Tự doanh:**
- Mua ròng: ...
- Bán ròng: ...

💹 **Tín hiệu:**
_Đang phân tích..._
"""
        
        return QueryResult(
            intent=QueryIntent.GET_SMART_MONEY,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            data={'action': 'smart_money'},
            suggested_actions=[
                "Xem chi tiết khối ngoại",
                "Lọc mã có tiền vào",
                "Xem biểu đồ Sankey"
            ]
        )
    
    def _handle_find_opportunities(self, confidence: float) -> QueryResult:
        """Handle opportunity finding request"""
        response = """
🔍 **Tìm kiếm cơ hội đầu tư**

📊 **Bộ lọc đang áp dụng:**
- Breakout với volume cao
- RSI thoát vùng quá bán
- MACD cắt lên
- Dòng tiền dương

🎯 **Kết quả:**
_Đang quét..._

⚡ **Top gợi ý:**
_Đang phân tích..._
"""
        
        return QueryResult(
            intent=QueryIntent.FIND_OPPORTUNITIES,
            entities={},
            confidence=confidence,
            response_text=response.strip(),
            data={'action': 'find_opportunities'},
            suggested_actions=[
                "Lọc theo volume",
                "Lọc breakout",
                "Lọc oversold bounce"
            ]
        )
    
    def _handle_risk_assessment(self, entities: Dict[str, Any], 
                                 confidence: float) -> QueryResult:
        """Handle risk assessment request"""
        symbol = entities.get('symbol', '')
        
        response = f"""
⚠️ **Đánh giá rủi ro {symbol if symbol else 'danh mục'}**

🏥 **Risk Doctor đang phân tích:**

📊 **Các chỉ số rủi ro:**
- Value at Risk (VaR): ...
- Maximum Drawdown: ...
- Volatility: ...
- Beta: ...

💊 **Khuyến nghị:**
_Đang tổng hợp..._
"""
        
        return QueryResult(
            intent=QueryIntent.RISK_ASSESSMENT,
            entities=entities,
            confidence=confidence,
            response_text=response.strip(),
            data={'symbol': symbol, 'action': 'risk_assessment'},
            suggested_actions=[
                "Xem VaR chi tiết",
                "Tính position size an toàn",
                "Monte Carlo rủi ro"
            ]
        )
    
    def _handle_unknown(self, query: str, confidence: float) -> QueryResult:
        """Handle unknown intent"""
        response = f"""
🤔 Tôi chưa hiểu rõ yêu cầu của bạn.

**Các câu hỏi tôi có thể trả lời:**

📊 **Phân tích:**
• "Phân tích HPG"
• "Nên mua VNM không?"
• "So sánh FPT và VNG"

📈 **Kỹ thuật:**
• "Backtest chiến lược MA Crossover"
• "Monte Carlo mô phỏng MWG"
• "Giải thích RSI là gì"

💰 **Thị trường:**
• "Thị trường hôm nay thế nào?"
• "Dòng tiền đang chảy vào đâu?"
• "Tìm cơ hội breakout"

📋 **Danh mục:**
• "Xem danh mục của tôi"
• "Kiểm tra rủi ro tổng thể"
"""
        
        return QueryResult(
            intent=QueryIntent.UNKNOWN,
            entities={},
            confidence=confidence,
            response_text=response.strip(),
            suggested_actions=[
                "Phân tích HPG",
                "Thị trường hôm nay",
                "Tìm cơ hội"
            ]
        )
