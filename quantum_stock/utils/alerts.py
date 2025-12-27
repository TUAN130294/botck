# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ADVANCED ALERT SYSTEM                                     ║
║                    Price, Indicator, Pattern, Volume Alerts                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

P2 Implementation - Enhanced alert system for VN-QUANT
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# ENUMS & DATA MODELS
# ============================================

class AlertType(Enum):
    PRICE = "price"
    RSI = "rsi"
    MACD = "macd"
    VOLUME = "volume"
    PATTERN = "pattern"
    NEWS = "news"
    CUSTOM = "custom"


class AlertCondition(Enum):
    ABOVE = ">"
    BELOW = "<"
    EQUALS = "="
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    PERCENT_CHANGE = "pct_change"


class AlertPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AlertConfig:
    """Alert configuration"""
    id: str
    symbol: str
    alert_type: AlertType
    condition: AlertCondition
    value: float
    priority: AlertPriority = AlertPriority.MEDIUM
    cooldown_minutes: int = 60
    enabled: bool = True
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    user_id: str = ""


@dataclass  
class AlertEvent:
    """Triggered alert event"""
    alert_id: str
    symbol: str
    alert_type: AlertType
    message: str
    current_value: float
    trigger_value: float
    priority: AlertPriority
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


# ============================================
# ALERT HANDLERS
# ============================================

class AlertHandler(ABC):
    """Abstract alert handler"""
    
    @abstractmethod
    async def send(self, event: AlertEvent) -> bool:
        """Send alert notification"""
        pass


class TelegramAlertHandler(AlertHandler):
    """Send alerts via Telegram"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
    
    async def send(self, event: AlertEvent) -> bool:
        try:
            import aiohttp
            
            # Priority emoji
            priority_emoji = {
                AlertPriority.LOW: "ℹ️",
                AlertPriority.MEDIUM: "⚠️",
                AlertPriority.HIGH: "🔔",
                AlertPriority.CRITICAL: "🚨"
            }
            
            message = f"""
{priority_emoji.get(event.priority, '📢')} **ALERT: {event.symbol}**

📊 Type: {event.alert_type.value.upper()}
💰 Current: {event.current_value:,.2f}
🎯 Trigger: {event.trigger_value:,.2f}
📝 {event.message}
⏰ {event.timestamp.strftime('%H:%M:%S')}
"""
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                }) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")
            return False


class WebSocketAlertHandler(AlertHandler):
    """Send alerts via WebSocket to frontend"""
    
    def __init__(self, broadcast_func: Callable = None):
        self.broadcast = broadcast_func
        self.clients: List = []
    
    async def send(self, event: AlertEvent) -> bool:
        try:
            payload = {
                'type': 'alert',
                'data': {
                    'alert_id': event.alert_id,
                    'symbol': event.symbol,
                    'alert_type': event.alert_type.value,
                    'message': event.message,
                    'current_value': event.current_value,
                    'trigger_value': event.trigger_value,
                    'priority': event.priority.value,
                    'timestamp': event.timestamp.isoformat()
                }
            }
            
            if self.broadcast:
                await self.broadcast(payload)
            
            return True
        except Exception as e:
            logger.error(f"WebSocket alert failed: {e}")
            return False


class EmailAlertHandler(AlertHandler):
    """Send alerts via Email"""
    
    def __init__(self, smtp_host: str, smtp_port: int, 
                 username: str, password: str, from_email: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
    
    async def send(self, event: AlertEvent) -> bool:
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            subject = f"[VN-QUANT Alert] {event.symbol}: {event.alert_type.value}"
            body = f"""
Stock Alert Triggered

Symbol: {event.symbol}
Type: {event.alert_type.value}
Current Value: {event.current_value}
Trigger Value: {event.trigger_value}

Message: {event.message}

Time: {event.timestamp}
            """
            
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = self.username
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
            return False


class ConsoleAlertHandler(AlertHandler):
    """Print alerts to console (for debugging)"""
    
    async def send(self, event: AlertEvent) -> bool:
        priority_colors = {
            AlertPriority.LOW: "\033[94m",
            AlertPriority.MEDIUM: "\033[93m",
            AlertPriority.HIGH: "\033[91m",
            AlertPriority.CRITICAL: "\033[1;91m"
        }
        reset = "\033[0m"
        color = priority_colors.get(event.priority, "")
        
        print(f"{color}[ALERT] {event.symbol} - {event.message}{reset}")
        return True


# ============================================
# ALERT CHECKERS
# ============================================

class AlertChecker(ABC):
    """Abstract alert condition checker"""
    
    @abstractmethod
    def check(self, alert: AlertConfig, market_data: Dict) -> Optional[AlertEvent]:
        """Check if alert condition is met"""
        pass


class PriceAlertChecker(AlertChecker):
    """Check price-based alerts"""
    
    def check(self, alert: AlertConfig, market_data: Dict) -> Optional[AlertEvent]:
        if alert.alert_type != AlertType.PRICE:
            return None
        
        current_price = market_data.get('price', 0)
        prev_price = market_data.get('prev_price', current_price)
        
        triggered = False
        message = ""
        
        if alert.condition == AlertCondition.ABOVE:
            if current_price > alert.value:
                triggered = True
                message = f"Price above {alert.value:,.0f}"
        
        elif alert.condition == AlertCondition.BELOW:
            if current_price < alert.value:
                triggered = True
                message = f"Price below {alert.value:,.0f}"
        
        elif alert.condition == AlertCondition.CROSS_ABOVE:
            if prev_price <= alert.value < current_price:
                triggered = True
                message = f"Price crossed above {alert.value:,.0f}"
        
        elif alert.condition == AlertCondition.CROSS_BELOW:
            if prev_price >= alert.value > current_price:
                triggered = True
                message = f"Price crossed below {alert.value:,.0f}"
        
        elif alert.condition == AlertCondition.PERCENT_CHANGE:
            ref_price = market_data.get('ref_price', prev_price)
            pct_change = (current_price - ref_price) / ref_price * 100
            if abs(pct_change) >= abs(alert.value):
                triggered = True
                direction = "up" if pct_change > 0 else "down"
                message = f"Price moved {abs(pct_change):.2f}% {direction}"
        
        if triggered:
            return AlertEvent(
                alert_id=alert.id,
                symbol=alert.symbol,
                alert_type=alert.alert_type,
                message=message,
                current_value=current_price,
                trigger_value=alert.value,
                priority=alert.priority
            )
        
        return None


class IndicatorAlertChecker(AlertChecker):
    """Check indicator-based alerts (RSI, MACD, etc.)"""
    
    def check(self, alert: AlertConfig, market_data: Dict) -> Optional[AlertEvent]:
        if alert.alert_type not in [AlertType.RSI, AlertType.MACD]:
            return None
        
        indicator_name = alert.alert_type.value.lower()
        current_value = market_data.get(indicator_name, None)
        
        if current_value is None:
            return None
        
        triggered = False
        message = ""
        
        if alert.condition == AlertCondition.ABOVE:
            if current_value > alert.value:
                triggered = True
                message = f"{indicator_name.upper()} above {alert.value}"
        
        elif alert.condition == AlertCondition.BELOW:
            if current_value < alert.value:
                triggered = True
                message = f"{indicator_name.upper()} below {alert.value}"
        
        if triggered:
            return AlertEvent(
                alert_id=alert.id,
                symbol=alert.symbol,
                alert_type=alert.alert_type,
                message=message,
                current_value=current_value,
                trigger_value=alert.value,
                priority=alert.priority
            )
        
        return None


class VolumeAlertChecker(AlertChecker):
    """Check volume-based alerts"""
    
    def check(self, alert: AlertConfig, market_data: Dict) -> Optional[AlertEvent]:
        if alert.alert_type != AlertType.VOLUME:
            return None
        
        volume = market_data.get('volume', 0)
        avg_volume = market_data.get('avg_volume', volume)
        
        if avg_volume == 0:
            return None
        
        volume_ratio = volume / avg_volume
        
        triggered = False
        message = ""
        
        if alert.condition == AlertCondition.ABOVE:
            if volume_ratio > alert.value:
                triggered = True
                message = f"Volume {volume_ratio:.1f}x average"
        
        elif alert.condition == AlertCondition.PERCENT_CHANGE:
            if volume_ratio >= (1 + alert.value / 100):
                triggered = True
                message = f"Volume spike: {volume_ratio:.1f}x average"
        
        if triggered:
            return AlertEvent(
                alert_id=alert.id,
                symbol=alert.symbol,
                alert_type=alert.alert_type,
                message=message,
                current_value=volume,
                trigger_value=avg_volume * alert.value,
                priority=alert.priority
            )
        
        return None


class PatternAlertChecker(AlertChecker):
    """Check pattern-based alerts"""
    
    PATTERNS = [
        'double_top', 'double_bottom', 
        'head_shoulders', 'inverse_head_shoulders',
        'triangle', 'wedge', 'flag',
        'doji', 'hammer', 'engulfing'
    ]
    
    def check(self, alert: AlertConfig, market_data: Dict) -> Optional[AlertEvent]:
        if alert.alert_type != AlertType.PATTERN:
            return None
        
        pattern_name = alert.metadata.get('pattern', '')
        detected_patterns = market_data.get('patterns', [])
        
        if pattern_name in detected_patterns:
            return AlertEvent(
                alert_id=alert.id,
                symbol=alert.symbol,
                alert_type=alert.alert_type,
                message=f"Pattern detected: {pattern_name.replace('_', ' ').title()}",
                current_value=market_data.get('price', 0),
                trigger_value=0,
                priority=alert.priority
            )
        
        return None


# ============================================
# ALERT MANAGER
# ============================================

class AlertManager:
    """
    Central alert management system
    
    Features:
    - Multiple alert types
    - Multiple notification channels
    - Cooldown management
    - Alert history
    """
    
    def __init__(self):
        self.alerts: Dict[str, AlertConfig] = {}
        self.handlers: List[AlertHandler] = []
        self.checkers: List[AlertChecker] = [
            PriceAlertChecker(),
            IndicatorAlertChecker(),
            VolumeAlertChecker(),
            PatternAlertChecker()
        ]
        self.history: List[AlertEvent] = []
        self.last_triggered: Dict[str, datetime] = {}
        self.max_history = 1000
    
    def add_handler(self, handler: AlertHandler):
        """Add notification handler"""
        self.handlers.append(handler)
    
    def add_alert(self, alert: AlertConfig):
        """Add new alert"""
        self.alerts[alert.id] = alert
        logger.info(f"Alert added: {alert.id} for {alert.symbol}")
    
    def remove_alert(self, alert_id: str):
        """Remove alert"""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            logger.info(f"Alert removed: {alert_id}")
    
    def enable_alert(self, alert_id: str, enabled: bool = True):
        """Enable/disable alert"""
        if alert_id in self.alerts:
            self.alerts[alert_id].enabled = enabled
    
    def get_alerts(self, symbol: str = None) -> List[AlertConfig]:
        """Get alerts, optionally filtered by symbol"""
        alerts = list(self.alerts.values())
        if symbol:
            alerts = [a for a in alerts if a.symbol == symbol]
        return alerts
    
    async def check_alerts(self, market_data: Dict[str, Dict]):
        """
        Check all alerts against market data
        
        Args:
            market_data: Dict of symbol -> market data
                {'HPG': {'price': 25000, 'volume': 1000000, 'rsi': 45, ...}}
        """
        events = []
        
        for alert in self.alerts.values():
            if not alert.enabled:
                continue
            
            # Check cooldown
            if alert.id in self.last_triggered:
                elapsed = datetime.now() - self.last_triggered[alert.id]
                if elapsed < timedelta(minutes=alert.cooldown_minutes):
                    continue
            
            # Get market data for symbol
            symbol_data = market_data.get(alert.symbol, {})
            if not symbol_data:
                continue
            
            # Check with each checker
            for checker in self.checkers:
                event = checker.check(alert, symbol_data)
                if event:
                    events.append(event)
                    self.last_triggered[alert.id] = datetime.now()
                    break  # Only trigger once per alert
        
        # Send notifications
        for event in events:
            await self._send_alert(event)
        
        return events
    
    async def _send_alert(self, event: AlertEvent):
        """Send alert through all handlers"""
        # Add to history
        self.history.append(event)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        # Send through handlers
        for handler in self.handlers:
            try:
                await handler.send(event)
            except Exception as e:
                logger.error(f"Handler failed: {e}")
    
    def get_history(self, symbol: str = None, 
                    limit: int = 100) -> List[AlertEvent]:
        """Get alert history"""
        history = self.history
        if symbol:
            history = [h for h in history if h.symbol == symbol]
        return history[-limit:]


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def create_price_alert(symbol: str, condition: str, value: float,
                       priority: str = "MEDIUM") -> AlertConfig:
    """Create a price alert"""
    import uuid
    
    condition_map = {
        '>': AlertCondition.ABOVE,
        '<': AlertCondition.BELOW,
        'above': AlertCondition.ABOVE,
        'below': AlertCondition.BELOW,
        'cross_above': AlertCondition.CROSS_ABOVE,
        'cross_below': AlertCondition.CROSS_BELOW
    }
    
    priority_map = {
        'LOW': AlertPriority.LOW,
        'MEDIUM': AlertPriority.MEDIUM,
        'HIGH': AlertPriority.HIGH,
        'CRITICAL': AlertPriority.CRITICAL
    }
    
    return AlertConfig(
        id=str(uuid.uuid4())[:8],
        symbol=symbol.upper(),
        alert_type=AlertType.PRICE,
        condition=condition_map.get(condition, AlertCondition.ABOVE),
        value=value,
        priority=priority_map.get(priority.upper(), AlertPriority.MEDIUM)
    )


def create_rsi_alert(symbol: str, condition: str, value: float,
                     priority: str = "MEDIUM") -> AlertConfig:
    """Create RSI alert"""
    import uuid
    
    condition_map = {
        '>': AlertCondition.ABOVE,
        '<': AlertCondition.BELOW,
        'above': AlertCondition.ABOVE,
        'below': AlertCondition.BELOW
    }
    
    return AlertConfig(
        id=str(uuid.uuid4())[:8],
        symbol=symbol.upper(),
        alert_type=AlertType.RSI,
        condition=condition_map.get(condition, AlertCondition.ABOVE),
        value=value,
        priority=AlertPriority.MEDIUM
    )


def create_volume_alert(symbol: str, multiplier: float = 2.0,
                        priority: str = "HIGH") -> AlertConfig:
    """Create volume spike alert"""
    import uuid
    
    return AlertConfig(
        id=str(uuid.uuid4())[:8],
        symbol=symbol.upper(),
        alert_type=AlertType.VOLUME,
        condition=AlertCondition.ABOVE,
        value=multiplier,
        priority=AlertPriority.HIGH,
        metadata={'description': f'Volume {multiplier}x average'}
    )


# ============================================
# TESTING
# ============================================

async def test_alerts():
    """Test alert system"""
    print("Testing Alert System...")
    print("=" * 50)
    
    # Create manager
    manager = AlertManager()
    
    # Add console handler for testing
    manager.add_handler(ConsoleAlertHandler())
    
    # Create alerts
    price_alert = create_price_alert('HPG', '>', 25000, 'HIGH')
    rsi_alert = create_rsi_alert('VNM', '>', 70, 'MEDIUM')
    volume_alert = create_volume_alert('FPT', 2.0)
    
    manager.add_alert(price_alert)
    manager.add_alert(rsi_alert)
    manager.add_alert(volume_alert)
    
    print(f"\nCreated {len(manager.alerts)} alerts")
    
    # Simulate market data
    market_data = {
        'HPG': {'price': 26000, 'prev_price': 24500, 'rsi': 55},
        'VNM': {'price': 75000, 'rsi': 72},
        'FPT': {'price': 120000, 'volume': 3000000, 'avg_volume': 1000000}
    }
    
    # Check alerts
    events = await manager.check_alerts(market_data)
    
    print(f"\nTriggered {len(events)} alerts:")
    for event in events:
        print(f"  - {event.symbol}: {event.message}")
    
    print("\n✅ Alert system tests completed!")


if __name__ == "__main__":
    asyncio.run(test_alerts())
