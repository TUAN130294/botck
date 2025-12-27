# -*- coding: utf-8 -*-
"""
Flow Agent - Agentic Level 3
Analyzes foreign and proprietary money flow for Vietnamese stocks

Features:
- Foreign investor flow tracking
- Proprietary trading analysis
- Institutional accumulation/distribution
- Block trade detection
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from .base_agent import BaseAgent, AgentSignal, AgentMessage


@dataclass
class FlowData:
    """Money flow data structure"""
    foreign_buy: float
    foreign_sell: float
    prop_buy: float
    prop_sell: float
    retail_buy: float
    retail_sell: float
    total_volume: float
    
    @property
    def foreign_net(self) -> float:
        return self.foreign_buy - self.foreign_sell
    
    @property
    def prop_net(self) -> float:
        return self.prop_buy - self.prop_sell
    
    @property
    def retail_net(self) -> float:
        return self.retail_buy - self.retail_sell
    
    @property
    def smart_money_net(self) -> float:
        return self.foreign_net + self.prop_net


class FlowAgent(BaseAgent):
    """
    Money Flow Analysis Agent - Level 3 Agentic
    
    Responsibilities:
    - Track foreign investor activity
    - Monitor proprietary trading
    - Identify accumulation/distribution
    - Detect unusual block trades
    """
    
    def __init__(self):
        super().__init__(
            name="FLOW_TRACKER",
            role="Money Flow Analyst",
            description="Tracks institutional money flow in Vietnamese market",
            weight=1.0
        )
        
        # Flow history for pattern detection
        self.flow_history: Dict[str, List[FlowData]] = {}
        
        # Thresholds for Vietnam market (in billion VND)
        self.large_foreign_threshold = 10  # 10 billion VND
        self.block_trade_threshold = 5
        
        # Historical accuracy
        self.accuracy_score = 0.75
    
    async def analyze(self, stock_data: Any, context: Dict[str, Any] = None) -> AgentSignal:
        """Analyze money flow for given stock"""
        symbol = stock_data.symbol if hasattr(stock_data, 'symbol') else 'UNKNOWN'
        
        # Extract flow data from context
        flow_context = context.get('flow', {}) if context else {}
        
        flow_data = FlowData(
            foreign_buy=flow_context.get('foreign_buy', 0),
            foreign_sell=flow_context.get('foreign_sell', 0),
            prop_buy=flow_context.get('prop_buy', 0),
            prop_sell=flow_context.get('prop_sell', 0),
            retail_buy=flow_context.get('retail_buy', 0),
            retail_sell=flow_context.get('retail_sell', 0),
            total_volume=flow_context.get('total_volume', 1)
        )
        
        # Store in history
        if symbol not in self.flow_history:
            self.flow_history[symbol] = []
        self.flow_history[symbol].append(flow_data)
        
        # Keep last 50 data points
        if len(self.flow_history[symbol]) > 50:
            self.flow_history[symbol] = self.flow_history[symbol][-50:]
        
        # Analyze flow patterns
        analysis = self._analyze_flow_pattern(symbol, flow_data)
        
        # Generate signal
        signal, confidence, reasoning = self._generate_signal(symbol, flow_data, analysis)
        
        current_price = stock_data.close if hasattr(stock_data, 'close') else 0
        
        return AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=confidence * self.accuracy_score,
            entry_price=current_price,
            stop_loss=None,
            take_profit=None,
            reasoning=reasoning,
            key_factors=[
                f"Foreign Net: {flow_data.foreign_net:,.0f}",
                f"Proprietary Net: {flow_data.prop_net:,.0f}",
                f"Smart Money: {flow_data.smart_money_net:,.0f}",
                f"Flow Trend: {analysis['trend']}"
            ],
            timestamp=datetime.now()
        )
    
    def _analyze_flow_pattern(self, symbol: str, current: FlowData) -> Dict:
        """Analyze flow pattern from history"""
        history = self.flow_history.get(symbol, [])
        
        if len(history) < 5:
            return {
                'trend': 'INSUFFICIENT_DATA',
                'accumulation': False,
                'distribution': False,
                'foreign_trend': 'NEUTRAL',
                'strength': 0.5
            }
        
        # Calculate recent averages
        recent_5 = history[-5:]
        recent_20 = history[-20:] if len(history) >= 20 else history
        
        avg_foreign_5 = sum(f.foreign_net for f in recent_5) / 5
        avg_foreign_20 = sum(f.foreign_net for f in recent_20) / len(recent_20)
        
        avg_smart_5 = sum(f.smart_money_net for f in recent_5) / 5
        avg_smart_20 = sum(f.smart_money_net for f in recent_20) / len(recent_20)
        
        # Determine trend
        if avg_smart_5 > avg_smart_20 * 1.2:
            trend = 'STRONG_INFLOW'
        elif avg_smart_5 > avg_smart_20:
            trend = 'INFLOW'
        elif avg_smart_5 < avg_smart_20 * 0.8:
            trend = 'STRONG_OUTFLOW'
        elif avg_smart_5 < avg_smart_20:
            trend = 'OUTFLOW'
        else:
            trend = 'NEUTRAL'
        
        # Check accumulation/distribution
        consecutive_buy = sum(1 for f in recent_5 if f.smart_money_net > 0)
        consecutive_sell = sum(1 for f in recent_5 if f.smart_money_net < 0)
        
        accumulation = consecutive_buy >= 4
        distribution = consecutive_sell >= 4
        
        # Foreign flow trend
        if avg_foreign_5 > self.large_foreign_threshold:
            foreign_trend = 'HEAVY_BUY'
        elif avg_foreign_5 > 0:
            foreign_trend = 'NET_BUY'
        elif avg_foreign_5 < -self.large_foreign_threshold:
            foreign_trend = 'HEAVY_SELL'
        elif avg_foreign_5 < 0:
            foreign_trend = 'NET_SELL'
        else:
            foreign_trend = 'NEUTRAL'
        
        # Calculate strength (0-1)
        if current.total_volume > 0:
            strength = abs(current.smart_money_net) / current.total_volume
        else:
            strength = 0.5
        
        return {
            'trend': trend,
            'accumulation': accumulation,
            'distribution': distribution,
            'foreign_trend': foreign_trend,
            'strength': min(1.0, strength)
        }
    
    def _generate_signal(self, symbol: str, flow: FlowData, analysis: Dict) -> tuple:
        """Generate trading signal from flow analysis"""
        trend = analysis['trend']
        foreign_trend = analysis['foreign_trend']
        
        # Build reasoning
        reasoning_parts = [f"Phân tích dòng tiền {symbol}:"]
        
        if flow.foreign_net > 0:
            reasoning_parts.append(f"✅ Khối ngoại mua ròng {flow.foreign_net:,.0f}")
        else:
            reasoning_parts.append(f"❌ Khối ngoại bán ròng {abs(flow.foreign_net):,.0f}")
        
        if flow.prop_net > 0:
            reasoning_parts.append(f"✅ Tự doanh mua ròng {flow.prop_net:,.0f}")
        else:
            reasoning_parts.append(f"❌ Tự doanh bán ròng {abs(flow.prop_net):,.0f}")
        
        # Determine signal
        if trend in ['STRONG_INFLOW', 'INFLOW'] and foreign_trend in ['HEAVY_BUY', 'NET_BUY']:
            signal = 'LONG'
            confidence = 0.7 + analysis['strength'] * 0.2
            reasoning_parts.append("🟢 Smart money tích lũy mạnh")
            
        elif trend in ['STRONG_OUTFLOW', 'OUTFLOW'] and foreign_trend in ['HEAVY_SELL', 'NET_SELL']:
            signal = 'SHORT'
            confidence = 0.7 + analysis['strength'] * 0.2
            reasoning_parts.append("🔴 Smart money phân phối")
            
        elif analysis['accumulation']:
            signal = 'LONG'
            confidence = 0.6 + analysis['strength'] * 0.15
            reasoning_parts.append("🟡 Có dấu hiệu tích lũy")
            
        elif analysis['distribution']:
            signal = 'SHORT'
            confidence = 0.6 + analysis['strength'] * 0.15
            reasoning_parts.append("🟡 Có dấu hiệu phân phối")
            
        else:
            signal = 'NEUTRAL'
            confidence = 0.4
            reasoning_parts.append("⚪ Chưa có xu hướng rõ ràng")
        
        reasoning = '\n'.join(reasoning_parts)
        
        return signal, confidence, reasoning
    
    async def respond_to_debate(self, topic: str, previous_rounds: List) -> str:
        """Participate in multi-agent debate"""
        response = f"[{self.name}] Từ góc độ dòng tiền: "
        
        if self.last_signal:
            if self.last_signal.signal == 'LONG':
                response += "Smart money đang tích lũy. "
            elif self.last_signal.signal == 'SHORT':
                response += "Cảnh báo dòng tiền rút mạnh. "
            else:
                response += "Dòng tiền chưa rõ xu hướng. "
        
        return response
