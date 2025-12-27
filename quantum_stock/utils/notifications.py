# -*- coding: utf-8 -*-
"""
Notification System for VN-QUANT
=================================
Multi-channel alert system for trading signals and events.

Channels:
- Telegram
- Email
- Webhook
- Browser Push (future)
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from loguru import logger


class NotificationPriority(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NotificationType(Enum):
    SIGNAL = "SIGNAL"  # Trading signal
    TRADE = "TRADE"  # Trade executed
    RISK = "RISK"  # Risk alert
    SYSTEM = "SYSTEM"  # System status
    DAILY = "DAILY"  # Daily summary


@dataclass
class Notification:
    """Notification message"""
    type: NotificationType
    priority: NotificationPriority
    title: str
    message: str
    data: Dict = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.data is None:
            self.data = {}


class NotificationChannel:
    """Base class for notification channels"""

    async def send(self, notification: Notification) -> bool:
        """Send notification (to be implemented by subclasses)"""
        raise NotImplementedError


class TelegramChannel(NotificationChannel):
    """Telegram notification channel"""

    def __init__(self, bot_token: str, chat_ids: List[str]):
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, notification: Notification) -> bool:
        """Send via Telegram"""
        try:
            # Format message with emoji
            emoji = self._get_emoji(notification.type, notification.priority)
            text = f"{emoji} **{notification.title}**\n\n{notification.message}"

            # Add data if present
            if notification.data:
                text += "\n\n```\n"
                for key, value in notification.data.items():
                    text += f"{key}: {value}\n"
                text += "```"

            # Send to all chat IDs
            async with aiohttp.ClientSession() as session:
                for chat_id in self.chat_ids:
                    url = f"{self.base_url}/sendMessage"
                    payload = {
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "Markdown"
                    }

                    async with session.post(url, json=payload) as response:
                        if response.status != 200:
                            logger.error(f"Telegram send failed: {await response.text()}")
                            return False

            logger.info(f"Telegram notification sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    def _get_emoji(self, type: NotificationType, priority: NotificationPriority) -> str:
        """Get appropriate emoji"""
        if priority == NotificationPriority.CRITICAL:
            return "🚨"
        elif priority == NotificationPriority.HIGH:
            return "⚠️"
        elif type == NotificationType.SIGNAL:
            return "📊"
        elif type == NotificationType.TRADE:
            return "💰"
        elif type == NotificationType.RISK:
            return "⚠️"
        elif type == NotificationType.SYSTEM:
            return "🔧"
        else:
            return "ℹ️"


class EmailChannel(NotificationChannel):
    """Email notification channel"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: List[str]
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails

    async def send(self, notification: Notification) -> bool:
        """Send via Email"""
        try:
            import aiosmtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ", ".join(self.to_emails)
            msg['Subject'] = f"[VN-QUANT] {notification.title}"

            # HTML body
            body = f"""
            <html>
            <body>
                <h2>{notification.title}</h2>
                <p>{notification.message}</p>

                {self._format_data_html(notification.data) if notification.data else ''}

                <hr>
                <p><small>Sent: {notification.timestamp.isoformat()}</small></p>
            </body>
            </html>
            """

            msg.attach(MIMEText(body, 'html'))

            # Send
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.username,
                password=self.password,
                use_tls=True
            )

            logger.info(f"Email notification sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"Email error: {e}")
            return False

    def _format_data_html(self, data: Dict) -> str:
        """Format data as HTML table"""
        html = "<table border='1' cellpadding='5'>"
        for key, value in data.items():
            html += f"<tr><td><b>{key}</b></td><td>{value}</td></tr>"
        html += "</table>"
        return html


class WebhookChannel(NotificationChannel):
    """Webhook notification channel"""

    def __init__(self, webhook_url: str, headers: Dict = None):
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}

    async def send(self, notification: Notification) -> bool:
        """Send via Webhook"""
        try:
            payload = {
                "type": notification.type.value,
                "priority": notification.priority.value,
                "title": notification.title,
                "message": notification.message,
                "data": notification.data,
                "timestamp": notification.timestamp.isoformat()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers
                ) as response:
                    if response.status not in (200, 201, 204):
                        logger.error(f"Webhook failed: {await response.text()}")
                        return False

            logger.info(f"Webhook notification sent: {notification.title}")
            return True

        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return False


class NotificationManager:
    """
    Centralized notification manager

    Usage:
        manager = NotificationManager()
        manager.add_channel(TelegramChannel(...))
        await manager.notify(Notification(...))
    """

    def __init__(self):
        self.channels: List[NotificationChannel] = []
        self.filters: Dict[NotificationPriority, bool] = {
            NotificationPriority.LOW: True,
            NotificationPriority.MEDIUM: True,
            NotificationPriority.HIGH: True,
            NotificationPriority.CRITICAL: True
        }

    def add_channel(self, channel: NotificationChannel):
        """Add notification channel"""
        self.channels.append(channel)
        logger.info(f"Added notification channel: {channel.__class__.__name__}")

    def set_filter(self, priority: NotificationPriority, enabled: bool):
        """Enable/disable notifications by priority"""
        self.filters[priority] = enabled

    async def notify(self, notification: Notification) -> bool:
        """Send notification to all channels"""
        # Check filter
        if not self.filters.get(notification.priority, True):
            logger.debug(f"Notification filtered: {notification.title}")
            return False

        # Send to all channels
        tasks = [channel.send(notification) for channel in self.channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check if any succeeded
        success = any(r is True for r in results)

        if not success:
            logger.error(f"All notification channels failed for: {notification.title}")

        return success

    async def notify_signal(
        self,
        symbol: str,
        signal: str,
        confidence: float,
        price: float,
        reasoning: str = ""
    ):
        """Quick method for signal notifications"""
        notification = Notification(
            type=NotificationType.SIGNAL,
            priority=NotificationPriority.HIGH if confidence > 0.8 else NotificationPriority.MEDIUM,
            title=f"Signal: {signal} {symbol}",
            message=f"Confidence: {confidence:.0%}\nPrice: {price:,.0f} VND\n{reasoning}",
            data={
                "symbol": symbol,
                "signal": signal,
                "confidence": f"{confidence:.2%}",
                "price": f"{price:,.0f}"
            }
        )

        await self.notify(notification)

    async def notify_trade(
        self,
        symbol: str,
        action: str,
        quantity: int,
        price: float,
        pnl: Optional[float] = None
    ):
        """Quick method for trade notifications"""
        message = f"Action: {action}\nQuantity: {quantity}\nPrice: {price:,.0f} VND"

        if pnl is not None:
            message += f"\nP&L: {pnl:+,.0f} VND ({pnl/price/quantity*100:+.2f}%)"

        notification = Notification(
            type=NotificationType.TRADE,
            priority=NotificationPriority.HIGH,
            title=f"Trade: {action} {symbol}",
            message=message,
            data={
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "price": f"{price:,.0f}",
                "pnl": f"{pnl:+,.0f}" if pnl else "N/A"
            }
        )

        await self.notify(notification)

    async def notify_risk(
        self,
        level: str,
        message: str,
        portfolio_value: float,
        daily_pnl_pct: float
    ):
        """Quick method for risk notifications"""
        notification = Notification(
            type=NotificationType.RISK,
            priority=NotificationPriority.CRITICAL if level == "EMERGENCY" else NotificationPriority.HIGH,
            title=f"Risk Alert: {level}",
            message=message,
            data={
                "level": level,
                "portfolio_value": f"{portfolio_value:,.0f}",
                "daily_pnl": f"{daily_pnl_pct:+.2f}%"
            }
        )

        await self.notify(notification)

    async def notify_daily_summary(
        self,
        total_return: float,
        daily_return: float,
        num_trades: int,
        win_rate: float,
        portfolio_value: float
    ):
        """Quick method for daily summary"""
        notification = Notification(
            type=NotificationType.DAILY,
            priority=NotificationPriority.LOW,
            title="Daily Trading Summary",
            message=f"""
Portfolio Value: {portfolio_value:,.0f} VND
Daily Return: {daily_return:+.2f}%
Total Return: {total_return:+.2f}%
Trades Today: {num_trades}
Win Rate: {win_rate:.1f}%
            """,
            data={
                "portfolio_value": f"{portfolio_value:,.0f}",
                "daily_return": f"{daily_return:+.2f}%",
                "total_return": f"{total_return:+.2f}%",
                "trades": num_trades,
                "win_rate": f"{win_rate:.1f}%"
            }
        )

        await self.notify(notification)


# Global notification manager
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get global notification manager"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def setup_notifications(
    telegram_token: Optional[str] = None,
    telegram_chat_ids: Optional[List[str]] = None,
    email_config: Optional[Dict] = None,
    webhook_url: Optional[str] = None
) -> NotificationManager:
    """
    Setup notification system

    Args:
        telegram_token: Telegram bot token
        telegram_chat_ids: List of chat IDs
        email_config: Email configuration dict
        webhook_url: Webhook URL

    Returns:
        NotificationManager
    """
    manager = get_notification_manager()

    # Add Telegram channel
    if telegram_token and telegram_chat_ids:
        manager.add_channel(TelegramChannel(telegram_token, telegram_chat_ids))

    # Add Email channel
    if email_config:
        manager.add_channel(EmailChannel(**email_config))

    # Add Webhook channel
    if webhook_url:
        manager.add_channel(WebhookChannel(webhook_url))

    logger.info("Notification system setup complete")

    return manager


__all__ = [
    "NotificationManager",
    "Notification",
    "NotificationType",
    "NotificationPriority",
    "TelegramChannel",
    "EmailChannel",
    "WebhookChannel",
    "get_notification_manager",
    "setup_notifications"
]
