# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    LLM-POWERED AUTONOMOUS AGENTS                             ║
║                    Real AI Decision Making with Gemini/OpenAI               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Agents thực sự "suy nghĩ" bằng AI, không phải rule-based
"""

import os
import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# LLM CLIENT
# ============================================

class LLMClient:
    """
    Universal LLM Client supporting multiple providers
    
    Supported:
    - Gemini (via key4u.shop or Google AI Studio)
    - OpenAI / OpenAI-compatible APIs
    - Claude (Anthropic)
    """
    
    def __init__(self, 
                 api_key: str = None,
                 base_url: str = None,
                 model: str = None,
                 provider: str = "gemini"):
        """
        Initialize LLM client
        
        Args:
            api_key: API key (or from env: LLM_API_KEY)
            base_url: Base URL (or from env: LLM_BASE_URL)
            model: Model name (or from env: LLM_MODEL)
            provider: "gemini", "openai", "claude"
        """
        self.api_key = api_key or os.getenv('LLM_API_KEY', '')
        self.provider = provider
        
        # Default configurations per provider
        if provider == "gemini":
            self.base_url = base_url or os.getenv('LLM_BASE_URL', 'https://api.key4u.shop/v1')
            self.model = model or os.getenv('LLM_MODEL', 'gemini-3-flash-preview')
        elif provider == "openai":
            self.base_url = base_url or os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
            self.model = model or os.getenv('LLM_MODEL', 'gpt-4o-mini')
        elif provider == "claude":
            self.base_url = base_url or os.getenv('LLM_BASE_URL', 'https://api.anthropic.com/v1')
            self.model = model or os.getenv('LLM_MODEL', 'claude-3-haiku-20240307')
        else:
            self.base_url = base_url or 'https://api.key4u.shop/v1'
            self.model = model or 'gemini-2.0-flash-exp'
        
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        logger.info(f"LLM Client initialized: {self.provider} @ {self.base_url}")
    
    async def chat(self, messages: List[Dict], 
                   temperature: float = 0.7,
                   max_tokens: int = 1000) -> str:
        """
        Send chat completion request
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            temperature: Creativity (0-1)
            max_tokens: Max response length
        
        Returns:
            Response text
        """
        if not self.api_key:
            logger.warning("No API key configured, using mock response")
            return self._mock_response(messages)
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
                
                url = f"{self.base_url}/chat/completions"
                
                async with session.post(url, json=payload, headers=self.headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error = await response.text()
                        logger.error(f"LLM API error: {response.status} - {error}")
                        return self._mock_response(messages)
                        
        except asyncio.TimeoutError:
            logger.error("LLM API timeout")
            return self._mock_response(messages)
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            return self._mock_response(messages)
    
    def _mock_response(self, messages: List[Dict]) -> str:
        """Fallback mock response when API unavailable"""
        last_msg = messages[-1]['content'] if messages else ""
        
        if "phân tích" in last_msg.lower() or "analyze" in last_msg.lower():
            return "Dựa trên phân tích kỹ thuật, RSI đang ở vùng trung tính (50-55), MACD cho tín hiệu neutral. Khuyến nghị: WATCH với confidence 65%."
        elif "mua" in last_msg.lower() or "buy" in last_msg.lower():
            return "Cổ phiếu có tiềm năng tăng ngắn hạn. Momentum tích cực nhưng cần xác nhận thêm từ volume. Khuyến nghị: BUY với confidence 70%."
        elif "bán" in last_msg.lower() or "sell" in last_msg.lower():
            return "Có dấu hiệu điều chỉnh. RSI overbought. Khuyến nghị: SELL một phần với confidence 60%."
        else:
            return "Thị trường đang trong giai đoạn tích lũy. Cần theo dõi thêm."


# ============================================
# AI-POWERED AGENTS
# ============================================

@dataclass
class AgentPersonality:
    """Agent's personality and role"""
    name: str
    emoji: str
    role: str
    system_prompt: str
    bias: str  # bullish, bearish, neutral


# Agent Personalities
AGENT_PERSONALITIES = {
    "Alex": AgentPersonality(
        name="Alex",
        emoji="📊",
        role="Technical Analyst",
        system_prompt="""Bạn là Alex, một chuyên gia phân tích kỹ thuật cho thị trường chứng khoán Việt Nam.
        
Nhiệm vụ:
- Phân tích các chỉ báo kỹ thuật: RSI, MACD, Bollinger Bands, Moving Averages
- Đánh giá xu hướng giá và volume
- Đưa ra khuyến nghị BUY/SELL/HOLD với confidence (%)

Phong cách:
- Dựa trên dữ liệu, không cảm tính
- Luôn đề cập đến các chỉ báo cụ thể
- Trả lời ngắn gọn, súc tích

Format trả lời:
"Báo cáo Chief! [SYMBOL] đang [tình trạng]. [Phân tích ngắn]. Confidence [X]%."
""",
        bias="neutral"
    ),
    
    "Bull": AgentPersonality(
        name="Bull",
        emoji="🐂",
        role="Bullish Advocate",
        system_prompt="""Bạn là Bull, một trader lạc quan chuyên tìm cơ hội mua.

Nhiệm vụ:
- Tìm điểm mua tốt
- Nhìn thấy cơ hội trong mọi tình huống
- Ủng hộ các vị thế long

Phong cách:
- Nhiệt tình, lạc quan
- Tập trung vào tiềm năng tăng giá
- Nói ngắn gọn, đầy năng lượng

Format trả lời:
"[Emoji] [Nhận xét ngắn về cơ hội mua]! Nên MUA thôi team!"
""",
        bias="bullish"
    ),
    
    "Bear": AgentPersonality(
        name="Bear",
        emoji="🐻",
        role="Risk Assessor",
        system_prompt="""Bạn là Bear, một nhà quản lý rủi ro thận trọng.

Nhiệm vụ:
- Cảnh báo rủi ro
- Tìm điểm yếu, vùng kháng cự
- Đề xuất bán hoặc giữ tiền mặt

Phong cách:
- Thận trọng, bảo thủ
- Tập trung vào downside risk
- Cảnh báo khi thấy nguy hiểm

Format trả lời:
"[Cảnh báo rủi ro ngắn gọn]. Cẩn thận team!"
""",
        bias="bearish"
    ),
    
    "Chief": AgentPersonality(
        name="Chief",
        emoji="👔",
        role="Decision Maker",
        system_prompt="""Bạn là Chief, người đưa ra quyết định cuối cùng.

Nhiệm vụ:
- Tổng hợp ý kiến từ Alex, Bull, Bear
- Cân nhắc risk/reward
- Đưa ra VERDICT cuối cùng

Phong cách:
- Điềm đạm, quyết đoán
- Cân bằng các quan điểm
- Ra quyết định rõ ràng

Format trả lời:
"🏛️ VERDICT: [SYMBOL] → [BUY/SELL/HOLD/WATCH]. [Lý do ngắn]. Confidence [X]%."
""",
        bias="neutral"
    )
}


class AIAgent:
    """
    AI-Powered Trading Agent
    
    Uses LLM for real decision making
    """
    
    def __init__(self, personality: AgentPersonality, llm_client: LLMClient):
        self.personality = personality
        self.llm = llm_client
        self.conversation_history: List[Dict] = []
    
    async def think(self, context: Dict) -> str:
        """
        Agent thinks about the market context and responds
        
        Args:
            context: Dict with market data, alerts, other agent opinions
        
        Returns:
            Agent's response/opinion
        """
        # Build prompt
        system_msg = self.personality.system_prompt
        
        user_msg = self._build_user_message(context)
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
        
        # Add conversation history for context
        messages.extend(self.conversation_history[-4:])  # Last 4 messages
        messages.append({"role": "user", "content": user_msg})
        
        # Get AI response
        response = await self.llm.chat(messages, temperature=0.7)
        
        # Save to history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        return response
    
    def _build_user_message(self, context: Dict) -> str:
        """Build user message from context"""
        symbol = context.get('symbol', 'N/A')
        price = context.get('price', 0)
        change = context.get('change', 0)
        
        msg = f"Phân tích mã {symbol}:\n"
        msg += f"- Giá hiện tại: {price:,.0f} VND\n"
        msg += f"- Thay đổi: {change:+.2f}%\n"
        
        if 'indicators' in context:
            msg += f"- RSI: {context['indicators'].get('rsi', 'N/A')}\n"
            msg += f"- MACD: {context['indicators'].get('macd', 'N/A')}\n"
        
        if 'other_opinions' in context:
            msg += "\nÝ kiến các agent khác:\n"
            for opinion in context['other_opinions']:
                msg += f"- {opinion}\n"
        
        msg += "\nBạn nghĩ sao?"
        
        return msg
    
    async def respond_to(self, message: str) -> str:
        """Respond to a direct message"""
        messages = [
            {"role": "system", "content": self.personality.system_prompt},
            {"role": "user", "content": message}
        ]
        
        return await self.llm.chat(messages)


# ============================================
# AI AGENT COORDINATOR
# ============================================

class AIAgentCoordinator:
    """
    Coordinates AI-powered agents for market analysis
    
    Flow:
    1. Scout detects opportunity
    2. Alex analyzes technically
    3. Bull gives bullish view
    4. Bear gives bearish view
    5. Chief makes final decision
    """
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.llm = LLMClient(api_key=api_key, base_url=base_url, model=model)
        
        self.agents = {
            name: AIAgent(personality, self.llm)
            for name, personality in AGENT_PERSONALITIES.items()
        }
        
        self.conversation_log: List[Dict] = []
    
    async def analyze_symbol(self, symbol: str, price: float, change: float,
                             indicators: Dict = None) -> List[Dict]:
        """
        Full agent team analysis of a symbol
        
        Returns list of agent messages
        """
        self.conversation_log = []
        
        context = {
            'symbol': symbol,
            'price': price,
            'change': change,
            'indicators': indicators or {}
        }
        
        # Step 1: Alex analyzes
        alex_opinion = await self.agents['Alex'].think(context)
        self._log("Alex", "📊", alex_opinion, "SUCCESS")
        
        await asyncio.sleep(0.5)  # Simulate thinking time
        
        # Step 2: Bull gives opinion
        context['other_opinions'] = [f"Alex: {alex_opinion}"]
        bull_opinion = await self.agents['Bull'].think(context)
        self._log("Bull", "🐂", bull_opinion, "WARNING")
        
        await asyncio.sleep(0.5)
        
        # Step 3: Bear gives opinion
        context['other_opinions'].append(f"Bull: {bull_opinion}")
        bear_opinion = await self.agents['Bear'].think(context)
        self._log("Bear", "🐻", bear_opinion, "INFO")
        
        await asyncio.sleep(0.5)
        
        # Step 4: Chief makes decision
        context['other_opinions'] = [
            f"Alex: {alex_opinion}",
            f"Bull: {bull_opinion}",
            f"Bear: {bear_opinion}"
        ]
        chief_verdict = await self.agents['Chief'].think(context)
        self._log("Chief", "👔", chief_verdict, "SUCCESS")
        
        return self.conversation_log
    
    def _log(self, sender: str, emoji: str, content: str, msg_type: str):
        """Log a message"""
        self.conversation_log.append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'sender': sender,
            'emoji': emoji,
            'content': content,
            'type': msg_type
        })
        logger.info(f"{emoji} {sender}: {content}")
    
    async def ask_agent(self, agent_name: str, question: str) -> str:
        """Ask a specific agent a question"""
        if agent_name not in self.agents:
            return f"Agent {agent_name} not found"
        
        return await self.agents[agent_name].respond_to(question)


# ============================================
# CONFIGURATION
# ============================================

def configure_llm(api_key: str = None, 
                  base_url: str = "https://api.key4u.shop/v1",
                  model: str = "gemini-2.0-flash-exp") -> LLMClient:
    """
    Configure LLM client with API settings
    
    Example:
        client = configure_llm(api_key="your-key")
        
    Or set environment variables:
        LLM_API_KEY=your-key
        LLM_BASE_URL=https://api.key4u.shop/v1
        LLM_MODEL=gemini-2.0-flash-exp
    """
    return LLMClient(api_key=api_key, base_url=base_url, model=model)


# ============================================
# TESTING
# ============================================

async def test_ai_agents():
    """Test AI agents"""
    print("=" * 60)
    print("🤖 AI-POWERED AGENT SYSTEM TEST")
    print("=" * 60)
    
    # Check if API key is configured
    api_key = os.getenv('LLM_API_KEY', '')
    
    if not api_key:
        print("\n⚠️  No LLM_API_KEY set. Running in MOCK mode.")
        print("   To use real AI, set: LLM_API_KEY=your-api-key")
        print("   Supported: key4u.shop, OpenAI, Anthropic\n")
    
    # Create coordinator
    coordinator = AIAgentCoordinator()
    
    # Analyze a symbol
    print("📊 Analyzing MWG...\n")
    
    messages = await coordinator.analyze_symbol(
        symbol="MWG",
        price=88000,
        change=2.5,
        indicators={'rsi': 55, 'macd': 0.3}
    )
    
    print("\n" + "=" * 60)
    print("📝 CONVERSATION LOG:")
    print("=" * 60)
    
    for msg in messages:
        emoji = msg.get('emoji', '🤖')
        sender = msg.get('sender', 'Agent')
        content = msg.get('content', '')
        print(f"\n{msg['time']} {emoji} {sender}:")
        print(f"   {content[:200]}...")
    
    print("\n✅ Test complete!")
    
    if not api_key:
        print("\n💡 Để sử dụng AI thật:")
        print("   set LLM_API_KEY=your-key-from-key4u.shop")
        print("   python -c \"from quantum_stock.agents.llm_agents import test_ai_agents; import asyncio; asyncio.run(test_ai_agents())\"")


if __name__ == "__main__":
    asyncio.run(test_ai_agents())
