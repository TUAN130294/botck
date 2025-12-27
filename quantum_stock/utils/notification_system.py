# -*- coding: utf-8 -*-
"""
Notification System for VN-QUANT
=================================
Multi-channel notification system.

Channels:
- Telegram
- Email
- Webhook
- Browser push
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from loguru import logger

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class NotificationLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Notification:
    """Notification message"""
    title: str
    message: str
    level: NotificationLevel
    timestamp: datetime = None
    data: Dict = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.data is None:
            self.data = {}


class TelegramNotifier:
    """Telegram notification channel"""

    def __init__(self, bot_token: str, chat_ids: List[str]):
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.bot = None

        if TELEGRAM_AVAILABLE and bot_token:
            self.bot = Bot(token=bot_token)

    async def send(self, notification: Notification):
        """Send Telegram message"""
        if not self.bot:
            logger.warning("Telegram bot not configured")
            return

        # Format message
        emoji = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.CRITICAL: "🚨"
        }

        message = f"{emoji[notification.level]} **{notification.title}**\n\n"
        message += f"{notification.message}\n\n"
        message += f"⏰ {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

        # Send to all chat IDs
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Telegram sent to {chat_id}")
            except Exception as e:
                logger.error(f"Telegram error: {e}")


class EmailNotifier:
    """Email notification channel"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: List[str]
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    async def send(self, notification: Notification):
        """Send email"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[VN-QUANT] {notification.title}"
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)

            # HTML body
            html = f"""
            <html>
            <body>
                <h2>{notification.title}</h2>
                <p>{notification.message}</p>
                <p><small>{notification.timestamp}</small></p>
            </body>
            </html>
            """

            msg.attach(MIMEText(html, 'html'))

            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            logger.info(f"Email sent to {self.to_addrs}")

        except Exception as e:
            logger.error(f"Email error: {e}")


class WebhookNotifier:
    """Webhook notification channel"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, notification: Notification):
        """Send webhook"""
        try:
            payload = {
                "title": notification.title,
                "message": notification.message,
                "level": notification.level.value,
                "timestamp": notification.timestamp.isoformat(),
                "data": notification.data
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info("Webhook sent successfully")
                    else:
                        logger.error(f"Webhook failed: {response.status}")

        except Exception as e:
            logger.error(f"Webhook error: {e}")


class NotificationManager:
    """
    Central notification manager

    Usage:
        manager = NotificationManager()
        manager.add_channel("telegram", telegram_notifier)
        await manager.notify("Trade Alert", "VCB filled at 95,000", level=NotificationLevel.INFO)
    """

    def __init__(self):
        self.channels: Dict[str, object] = {}
        self.filters: List[Callable] = []

    def add_channel(self, name: str, channel):
        """Add notification channel"""
        self.channels[name] = channel
        logger.info(f"Channel added: {name}")

    def remove_channel(self, name: str):
        """Remove notification channel"""
        if name in self.channels:
            del self.channels[name]
            logger.info(f"Channel removed: {name}")

    def add_filter(self, filter_func: Callable):
        """Add notification filter"""
        self.filters.append(filter_func)

    async def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        **kwargs
    ):
        """Send notification to all channels"""
        notification = Notification(
            title=title,
            message=message,
            level=level,
            data=kwargs
        )

        # Apply filters
        for filter_func in self.filters:
            if not filter_func(notification):
                logger.debug(f"Notification filtered: {title}")
                return

        # Send to all channels
        tasks = []
        for name, channel in self.channels.items():
            task = asyncio.create_task(channel.send(notification))
            tasks.append(task)

        # Wait for all
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # Convenience methods
    async def info(self, title: str, message: str, **kwargs):
        """Send INFO notification"""
        await self.notify(title, message, NotificationLevel.INFO, **kwargs)

    async def warning(self, title: str, message: str, **kwargs):
        """Send WARNING notification"""
        await self.notify(title, message, NotificationLevel.WARNING, **kwargs)

    async def critical(self, title: str, message: str, **kwargs):
        """Send CRITICAL notification"""
        await self.notify(title, message, NotificationLevel.CRITICAL, **kwargs)

    # Trading-specific notifications
    async def signal_alert(self, symbol: str, signal: str, confidence: float, **kwargs):
        """Alert for trading signal"""
        await self.notify(
            f"Signal: {symbol}",
            f"{signal} signal with {confidence:.0%} confidence",
            NotificationLevel.WARNING if confidence > 0.7 else NotificationLevel.INFO,
            symbol=symbol,
            signal=signal,
            confidence=confidence,
            **kwargs
        )

    async def order_filled(self, symbol: str, order_type: str, quantity: int, price: float, **kwargs):
        """Alert for order fill"""
        await self.info(
            f"Order Filled: {symbol}",
            f"{order_type} {quantity} @ {price:,.0f} VND",
            symbol=symbol,
            order_type=order_type,
            quantity=quantity,
            price=price,
            **kwargs
        )

    async def circuit_breaker(self, level: int, reason: str, **kwargs):
        """Alert for circuit breaker trigger"""
        await self.critical(
            f"Circuit Breaker Level {level}",
            f"Trading halted: {reason}",
            level=level,
            reason=reason,
            **kwargs
        )

    async def daily_summary(self, pnl: float, trades: int, win_rate: float, **kwargs):
        """Daily summary notification"""
        await self.info(
            "Daily Summary",
            f"P&L: {pnl:,.0f} VND | Trades: {trades} | Win Rate: {win_rate:.1%}",
            pnl=pnl,
            trades=trades,
            win_rate=win_rate,
            **kwargs
        )


# Global notification manager
_manager: Optional[NotificationManager] = None


def setup_notifications(
    telegram_token: Optional[str] = None,
    telegram_chat_ids: Optional[List[str]] = None,
    email_config: Optional[Dict] = None,
    webhook_url: Optional[str] = None
) -> NotificationManager:
    """
    Setup global notification manager

    Args:
        telegram_token: Telegram bot token
        telegram_chat_ids: List of chat IDs
        email_config: Email configuration dict
        webhook_url: Webhook URL

    Returns:
        NotificationManager instance
    """
    global _manager
    _manager = NotificationManager()

    # Add Telegram
    if telegram_token and telegram_chat_ids:
        telegram = TelegramNotifier(telegram_token, telegram_chat_ids)
        _manager.add_channel("telegram", telegram)

    # Add Email
    if email_config:
        email = EmailNotifier(**email_config)
        _manager.add_channel("email", email)

    # Add Webhook
    if webhook_url:
        webhook = WebhookNotifier(webhook_url)
        _manager.add_channel("webhook", webhook)

    return _manager


def get_notification_manager() -> NotificationManager:
    """Get global notification manager"""
    if _manager is None:
        return setup_notifications()
    return _manager


__all__ = [
    "NotificationManager",
    "NotificationLevel",
    "Notification",
    "TelegramNotifier",
    "EmailNotifier",
    "WebhookNotifier",
    "setup_notifications",
    "get_notification_manager"
]
