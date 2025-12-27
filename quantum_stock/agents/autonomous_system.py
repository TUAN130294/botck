# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AUTONOMOUS MULTI-AGENT SYSTEM                             ║
║                    Self-Discovery, Communication, Decision Making            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Level 5 Agentic Architecture:
- Agents tự động phát hiện cơ hội
- Gửi tin nhắn cho các agent khác
- Chief Agent tổng hợp và đưa quyết định
- Real-time monitoring và communication
"""

import asyncio
import queue
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import random
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# MESSAGE TYPES
# ============================================

class MessageType(Enum):
    ALERT = "ALERT"           # Phát hiện cơ hội
    ANALYSIS = "ANALYSIS"     # Yêu cầu phân tích
    REPORT = "REPORT"         # Báo cáo kết quả
    VERDICT = "VERDICT"       # Quyết định cuối cùng
    QUESTION = "QUESTION"     # Hỏi ý kiến
    ANSWER = "ANSWER"         # Trả lời
    COMMAND = "COMMAND"       # Lệnh từ Chief
    STATUS = "STATUS"         # Cập nhật trạng thái


class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class AgentMessage:
    """Message between agents"""
    id: str
    sender: str
    recipient: str  # "*" for broadcast
    msg_type: MessageType
    content: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    reply_to: str = None  # ID of message being replied to
    
    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.sender} → {self.recipient}: {self.msg_type.value}"


@dataclass
class AgentDecision:
    """Agent's analysis decision"""
    agent_name: str
    symbol: str
    action: str  # BUY, SELL, HOLD, WATCH
    confidence: float
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================
# MESSAGE BUS
# ============================================

class MessageBus:
    """
    Central message bus for agent communication
    
    Like a chat room where agents can send messages
    """
    
    def __init__(self):
        self.messages: List[AgentMessage] = []
        self.subscribers: Dict[str, List[Callable]] = {}
        self.message_queue = queue.Queue()
        self._counter = 0
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []  # UI callbacks
    
    def generate_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"MSG_{datetime.now().strftime('%H%M%S')}_{self._counter}"
    
    def publish(self, message: AgentMessage):
        """Publish a message to the bus"""
        message.id = self.generate_id()
        self.messages.append(message)
        self.message_queue.put(message)
        
        # Notify subscribers
        if message.recipient == "*":
            # Broadcast
            for agent_name, callbacks in self.subscribers.items():
                if agent_name != message.sender:
                    for callback in callbacks:
                        try:
                            callback(message)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
        elif message.recipient in self.subscribers:
            for callback in self.subscribers[message.recipient]:
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
        
        # UI callbacks
        for callback in self._callbacks:
            try:
                callback(message)
            except:
                pass
        
        logger.info(f"📨 {message}")
    
    def subscribe(self, agent_name: str, callback: Callable):
        """Subscribe an agent to receive messages"""
        if agent_name not in self.subscribers:
            self.subscribers[agent_name] = []
        self.subscribers[agent_name].append(callback)
    
    def on_message(self, callback: Callable):
        """Register UI callback for all messages"""
        self._callbacks.append(callback)
    
    def get_history(self, limit: int = 100) -> List[AgentMessage]:
        """Get message history"""
        return self.messages[-limit:]
    
    def get_messages_for(self, agent_name: str, limit: int = 50) -> List[AgentMessage]:
        """Get messages for a specific agent"""
        return [
            m for m in self.messages[-limit:]
            if m.recipient == agent_name or m.recipient == "*" or m.sender == agent_name
        ]


# ============================================
# BASE AUTONOMOUS AGENT
# ============================================

class AutonomousAgent(ABC):
    """
    Base class for autonomous agents
    
    Each agent can:
    - Monitor market data
    - Detect opportunities
    - Send messages to other agents
    - Respond to requests
    """
    
    def __init__(self, name: str, emoji: str, bus: MessageBus):
        self.name = name
        self.emoji = emoji
        self.bus = bus
        self.running = False
        self._thread: Optional[threading.Thread] = None
        
        # Subscribe to messages
        bus.subscribe(name, self.on_message)
    
    def send_message(self, recipient: str, msg_type: MessageType, 
                     content: Dict, priority: MessagePriority = MessagePriority.NORMAL,
                     reply_to: str = None):
        """Send a message to another agent"""
        message = AgentMessage(
            id="",
            sender=self.name,
            recipient=recipient,
            msg_type=msg_type,
            content=content,
            priority=priority,
            reply_to=reply_to
        )
        self.bus.publish(message)
    
    def broadcast(self, msg_type: MessageType, content: Dict,
                  priority: MessagePriority = MessagePriority.NORMAL):
        """Broadcast message to all agents"""
        self.send_message("*", msg_type, content, priority)
    
    @abstractmethod
    def on_message(self, message: AgentMessage):
        """Handle incoming message"""
        pass
    
    @abstractmethod
    async def monitor_loop(self):
        """Main monitoring loop"""
        pass
    
    def start(self):
        """Start agent's monitoring loop"""
        self.running = True
        self._thread = threading.Thread(target=self._run_loop)
        self._thread.daemon = True
        self._thread.start()
        logger.info(f"🚀 {self.emoji} {self.name} started")
    
    def stop(self):
        """Stop agent"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info(f"🛑 {self.name} stopped")
    
    def _run_loop(self):
        """Run the async monitoring loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.monitor_loop())


# ============================================
# SCOUT AGENT (Radar/Phát hiện)
# ============================================

class ScoutAgent(AutonomousAgent):
    """
    🔭 Scout Agent - Phát hiện cơ hội
    
    - Quét thị trường liên tục
    - Phát hiện biến động giá, volume
    - Gửi ALERT cho các agent khác
    """
    
    def __init__(self, bus: MessageBus, watchlist: List[str] = None):
        super().__init__("Scout", "🔭", bus)
        self.watchlist = watchlist or ["HPG", "VNM", "FPT", "VCB", "MWG", "TCB"]
        self.last_prices: Dict[str, float] = {}
        self.scan_interval = 5  # seconds
    
    async def monitor_loop(self):
        """Continuously scan for opportunities"""
        while self.running:
            await asyncio.sleep(self.scan_interval)
            
            for symbol in self.watchlist:
                alert = self._check_symbol(symbol)
                if alert:
                    # Phát hiện cơ hội - broadcast cho team
                    self.broadcast(
                        MessageType.ALERT,
                        alert,
                        MessagePriority.HIGH
                    )
    
    def _check_symbol(self, symbol: str) -> Optional[Dict]:
        """Check a symbol for opportunities"""
        # Simulate price data (replace with real data)
        current_price = self.last_prices.get(symbol, 50000) * (1 + random.uniform(-0.03, 0.03))
        prev_price = self.last_prices.get(symbol, current_price)
        self.last_prices[symbol] = current_price
        
        change = (current_price - prev_price) / prev_price * 100
        
        # Detect significant move
        if abs(change) > 1.5:
            direction = "tăng" if change > 0 else "giảm"
            return {
                'symbol': symbol,
                'price': current_price,
                'change': change,
                'direction': direction,
                'message': f"🚨 {symbol} đang {direction}, giá hiện tại {current_price:,.0f} ({change:+.2f}%)"
            }
        
        return None
    
    def on_message(self, message: AgentMessage):
        """Handle requests from other agents"""
        if message.msg_type == MessageType.COMMAND:
            if message.content.get('action') == 'add_symbol':
                symbol = message.content.get('symbol')
                if symbol and symbol not in self.watchlist:
                    self.watchlist.append(symbol)
                    self.send_message(
                        message.sender,
                        MessageType.STATUS,
                        {'message': f"Đã thêm {symbol} vào watchlist"}
                    )


# ============================================
# ANALYST AGENT (Alex)
# ============================================

class AnalystAgent(AutonomousAgent):
    """
    📊 Analyst Agent (Alex) - Phân tích kỹ thuật
    
    - Nhận alert từ Scout
    - Phân tích indicators
    - Báo cáo kết quả cho Chief
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("Alex", "📊", bus)
        self.pending_analyses = []
    
    async def monitor_loop(self):
        """Process pending analyses"""
        while self.running:
            await asyncio.sleep(1)
            
            # Process any pending work
            while self.pending_analyses:
                task = self.pending_analyses.pop(0)
                result = self._analyze(task)
                
                # Send report to Chief
                self.send_message(
                    "Chief",
                    MessageType.REPORT,
                    result,
                    MessagePriority.HIGH
                )
    
    def _analyze(self, data: Dict) -> Dict:
        """Perform technical analysis"""
        symbol = data.get('symbol', 'N/A')
        price = data.get('price', 0)
        change = data.get('change', 0)
        
        # Simulated analysis (replace with real indicators)
        rsi = random.uniform(30, 70)
        macd = random.uniform(-1, 1)
        volume_ratio = random.uniform(0.5, 2.0)
        
        # Determine signal
        if change > 0 and rsi < 70 and macd > 0:
            signal = "BULLISH"
            confidence = min(0.9, 0.5 + abs(change) / 10 + (70 - rsi) / 100)
        elif change < 0 and rsi > 30 and macd < 0:
            signal = "BEARISH"
            confidence = min(0.9, 0.5 + abs(change) / 10)
        else:
            signal = "NEUTRAL"
            confidence = 0.5
        
        return {
            'symbol': symbol,
            'price': price,
            'signal': signal,
            'confidence': confidence,
            'indicators': {
                'rsi': rsi,
                'macd': macd,
                'volume_ratio': volume_ratio
            },
            'message': f"Báo cáo Chief! {symbol} đang {signal.lower()}, giá hiện tại {price:,.0f} ({change:+.2f}%). Confidence {confidence:.0%}."
        }
    
    def on_message(self, message: AgentMessage):
        """Handle incoming messages"""
        if message.msg_type == MessageType.ALERT:
            # Received alert from Scout - add to analysis queue
            self.pending_analyses.append(message.content)
            
            # Acknowledge
            self.broadcast(
                MessageType.STATUS,
                {'message': f"📊 Đã nhận alert về {message.content.get('symbol')}, đang phân tích..."}
            )
        
        elif message.msg_type == MessageType.ANALYSIS:
            # Direct analysis request
            self.pending_analyses.append(message.content)


# ============================================
# BULL AGENT
# ============================================

class BullAgent(AutonomousAgent):
    """
    🐂 Bull Agent - Tìm cơ hội mua
    
    - Lạc quan về thị trường
    - Tìm điểm mua tốt
    - Phản hồi với quan điểm bullish
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("Bull", "🐂", bus)
    
    async def monitor_loop(self):
        while self.running:
            await asyncio.sleep(10)
    
    def on_message(self, message: AgentMessage):
        if message.msg_type == MessageType.ALERT:
            symbol = message.content.get('symbol')
            change = message.content.get('change', 0)
            
            if change > 0:
                # Bullish on positive momentum
                asyncio.create_task(self._delayed_response(symbol, change))
    
    async def _delayed_response(self, symbol: str, change: float):
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        confidence = min(0.9, 0.6 + abs(change) / 10)
        
        self.broadcast(
            MessageType.REPORT,
            {
                'symbol': symbol,
                'action': 'BUY',
                'confidence': confidence,
                'message': f"🐂 Nhìn momentum thế này, tôi thấy cơ hội! Nên MUA thôi team!"
            },
            MessagePriority.NORMAL
        )


# ============================================
# BEAR AGENT
# ============================================

class BearAgent(AutonomousAgent):
    """
    🐻 Bear Agent - Cảnh báo rủi ro
    
    - Thận trọng với thị trường
    - Cảnh báo overbought
    - Đề xuất bán/hold
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("Bear", "🐻", bus)
    
    async def monitor_loop(self):
        while self.running:
            await asyncio.sleep(10)
    
    def on_message(self, message: AgentMessage):
        if message.msg_type == MessageType.ALERT:
            symbol = message.content.get('symbol')
            change = message.content.get('change', 0)
            
            if change < -1 or change > 5:  # Warn on drops or extreme rises
                asyncio.create_task(self._delayed_response(symbol, change))
    
    async def _delayed_response(self, symbol: str, change: float):
        await asyncio.sleep(random.uniform(0.5, 2))
        
        if change < 0:
            message = f"🐻 Cẩn thận team! {symbol} đang yếu, có thể còn giảm tiếp."
            action = "SELL"
        else:
            message = f"🐻 Tăng quá nóng rồi, có thể điều chỉnh. Nên chốt lời một phần."
            action = "HOLD"
        
        self.broadcast(
            MessageType.REPORT,
            {
                'symbol': symbol,
                'action': action,
                'confidence': 0.6,
                'message': message
            },
            MessagePriority.NORMAL
        )


# ============================================
# RISK DOCTOR AGENT
# ============================================

class RiskDoctorAgent(AutonomousAgent):
    """
    🏥 Risk Doctor - Đánh giá rủi ro
    
    - Tính VaR, position size
    - Cảnh báo rủi ro cao
    - Đề xuất stop-loss
    """
    
    def __init__(self, bus: MessageBus, portfolio_value: float = 100_000_000):
        super().__init__("RiskDoc", "🏥", bus)
        self.portfolio_value = portfolio_value
        self.max_risk_per_trade = 0.02  # 2%
    
    async def monitor_loop(self):
        while self.running:
            await asyncio.sleep(10)
    
    def on_message(self, message: AgentMessage):
        if message.msg_type == MessageType.QUESTION:
            if message.content.get('topic') == 'position_size':
                self._calculate_position(message)
        
        elif message.msg_type == MessageType.REPORT:
            # Check risk on any trading recommendation
            if message.content.get('action') in ['BUY', 'SELL']:
                self._assess_risk(message.content)
    
    def _assess_risk(self, data: Dict):
        symbol = data.get('symbol')
        action = data.get('action')
        
        # Calculate risk metrics
        max_position = self.portfolio_value * self.max_risk_per_trade
        suggested_stop = 5  # 5% stop loss
        
        self.send_message(
            "Chief",
            MessageType.REPORT,
            {
                'symbol': symbol,
                'risk_assessment': 'ACCEPTABLE',
                'max_position': max_position,
                'stop_loss': suggested_stop,
                'message': f"🏥 Risk check OK. Max position: {max_position/1e6:.1f}M, Stoploss: {suggested_stop}%"
            },
            MessagePriority.NORMAL
        )
    
    def _calculate_position(self, message: AgentMessage):
        """Calculate optimal position size"""
        symbol = message.content.get('symbol')
        price = message.content.get('price', 50000)
        
        max_value = self.portfolio_value * self.max_risk_per_trade
        quantity = int(max_value / price / 100) * 100
        
        self.send_message(
            message.sender,
            MessageType.ANSWER,
            {
                'symbol': symbol,
                'quantity': quantity,
                'value': quantity * price,
                'message': f"Khuyến nghị mua {quantity:,} cổ ({quantity * price / 1e6:.1f}M)"
            },
            reply_to=message.id
        )


# ============================================
# CHIEF AGENT (Decision Maker)
# ============================================

class ChiefAgent(AutonomousAgent):
    """
    👔 Chief Agent - Tổng hợp và quyết định
    
    - Nhận báo cáo từ tất cả agents
    - Tổng hợp các quan điểm
    - Đưa ra quyết định cuối cùng (VERDICT)
    - Điều phối team
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("Chief", "👔", bus)
        self.pending_reports: Dict[str, List[Dict]] = {}  # symbol -> reports
        self.decision_threshold = 3  # Need 3 reports to decide
        self.decision_timeout = 5  # seconds
    
    async def monitor_loop(self):
        """Periodically check for pending decisions"""
        while self.running:
            await asyncio.sleep(2)
            
            # Check if any symbol has enough reports
            for symbol, reports in list(self.pending_reports.items()):
                if len(reports) >= self.decision_threshold:
                    verdict = self._make_decision(symbol, reports)
                    
                    # Broadcast verdict
                    self.broadcast(
                        MessageType.VERDICT,
                        verdict,
                        MessagePriority.URGENT
                    )
                    
                    # Clear processed reports
                    del self.pending_reports[symbol]
    
    def _make_decision(self, symbol: str, reports: List[Dict]) -> Dict:
        """Aggregate reports and make final decision"""
        buy_votes = 0
        sell_votes = 0
        hold_votes = 0
        total_confidence = 0
        
        messages = []
        
        for report in reports:
            action = report.get('action', report.get('signal', 'HOLD')).upper()
            confidence = report.get('confidence', 0.5)
            
            if action in ['BUY', 'BULLISH']:
                buy_votes += confidence
            elif action in ['SELL', 'BEARISH']:
                sell_votes += confidence
            else:
                hold_votes += confidence
            
            total_confidence += confidence
            if 'message' in report:
                messages.append(report['message'])
        
        # Determine verdict
        if buy_votes > sell_votes and buy_votes > hold_votes:
            verdict = "BUY"
            confidence = buy_votes / total_confidence
        elif sell_votes > buy_votes and sell_votes > hold_votes:
            verdict = "SELL"
            confidence = sell_votes / total_confidence
        else:
            verdict = "WATCH"
            confidence = hold_votes / total_confidence if hold_votes > 0 else 0.5
        
        return {
            'symbol': symbol,
            'verdict': verdict,
            'confidence': confidence,
            'votes': {
                'buy': buy_votes,
                'sell': sell_votes,
                'hold': hold_votes
            },
            'reports_count': len(reports),
            'message': f"🏛️ VERDICT: {symbol} → {verdict}. Action: {verdict}. Local verdict: {'mixed' if abs(buy_votes - sell_votes) < 0.3 else 'clear'} based on advisor confidence scores"
        }
    
    def on_message(self, message: AgentMessage):
        """Collect reports from other agents"""
        if message.msg_type in [MessageType.REPORT, MessageType.ANALYSIS]:
            symbol = message.content.get('symbol')
            if symbol:
                if symbol not in self.pending_reports:
                    self.pending_reports[symbol] = []
                    
                    # Initiate team discussion
                    self.broadcast(
                        MessageType.STATUS,
                        {'message': f"👔 Team, hôm nay chúng ta phân tích {symbol}. Alex, báo cáo technical đi!"}
                    )
                
                self.pending_reports[symbol].append(message.content)


# ============================================
# AGENT COORDINATOR
# ============================================

class AutonomousAgentSystem:
    """
    Coordinator for the entire autonomous agent system
    
    Manages all agents and the message bus
    """
    
    def __init__(self, watchlist: List[str] = None):
        self.bus = MessageBus()
        self.agents: Dict[str, AutonomousAgent] = {}
        
        # Create agents
        self.agents['Scout'] = ScoutAgent(self.bus, watchlist)
        self.agents['Alex'] = AnalystAgent(self.bus)
        self.agents['Bull'] = BullAgent(self.bus)
        self.agents['Bear'] = BearAgent(self.bus)
        self.agents['RiskDoc'] = RiskDoctorAgent(self.bus)
        self.agents['Chief'] = ChiefAgent(self.bus)
        
        self.running = False
    
    def start(self):
        """Start all agents"""
        self.running = True
        for agent in self.agents.values():
            agent.start()
        logger.info("🚀 Autonomous Agent System started!")
    
    def stop(self):
        """Stop all agents"""
        self.running = False
        for agent in self.agents.values():
            agent.stop()
        logger.info("🛑 Autonomous Agent System stopped")
    
    def get_messages(self, limit: int = 50) -> List[AgentMessage]:
        """Get recent messages"""
        return self.bus.get_history(limit)
    
    def on_message(self, callback: Callable):
        """Register callback for new messages"""
        self.bus.on_message(callback)
    
    def inject_alert(self, symbol: str, price: float, change: float):
        """Manually inject an alert for testing"""
        message = AgentMessage(
            id="",
            sender="System",
            recipient="*",
            msg_type=MessageType.ALERT,
            content={
                'symbol': symbol,
                'price': price,
                'change': change,
                'direction': 'tăng' if change > 0 else 'giảm',
                'message': f"🚨 {symbol} đang {'tăng' if change > 0 else 'giảm'}, giá {price:,.0f} ({change:+.2f}%)"
            },
            priority=MessagePriority.HIGH
        )
        self.bus.publish(message)


# ============================================
# TESTING
# ============================================

async def test_autonomous_system():
    """Test the autonomous agent system"""
    print("=" * 60)
    print("🤖 AUTONOMOUS MULTI-AGENT SYSTEM TEST")
    print("=" * 60)
    
    # Create system
    system = AutonomousAgentSystem(watchlist=['HPG', 'MWG', 'VNM'])
    
    messages = []
    
    def on_message(msg: AgentMessage):
        emoji_map = {
            'Scout': '🔭',
            'Alex': '📊',
            'Bull': '🐂',
            'Bear': '🐻',
            'RiskDoc': '🏥',
            'Chief': '👔',
            'System': '⚙️'
        }
        emoji = emoji_map.get(msg.sender, '🤖')
        print(f"{msg.timestamp.strftime('%H:%M:%S')} {emoji} {msg.sender}: {msg.content.get('message', str(msg.content))}")
        messages.append(msg)
    
    system.on_message(on_message)
    
    # Start system
    system.start()
    
    print("\n📡 System started. Injecting test alert...\n")
    await asyncio.sleep(2)
    
    # Inject a test alert
    system.inject_alert("MWG", 88000, 2.5)
    
    # Wait for agents to process
    print("\n⏳ Waiting for agents to analyze...\n")
    await asyncio.sleep(10)
    
    # Show final verdict
    print("\n" + "=" * 60)
    print("📋 MESSAGE LOG:")
    print("=" * 60)
    for msg in messages:
        print(f"  {msg}")
    
    # Stop
    system.stop()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_autonomous_system())
