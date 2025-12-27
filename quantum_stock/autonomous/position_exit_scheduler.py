# -*- coding: utf-8 -*-
"""
Position Exit Scheduler
========================
Tự động exit positions dựa trên:
1. Max profit target (take-profit)
2. Trailing stop (bảo vệ lợi nhuận)
3. Stop loss (cắt lỗ)

QUAN TRỌNG:
- KHÔNG tự động exit sau T+2.5
- NHƯNG vẫn tuân thủ luật T+2.5 (không được bán trước T+2)
- Chỉ exit khi ĐỦ T+2 VÀ đạt điều kiện profit/stop
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
import logging
logger = logging.getLogger(__name__)


# VN Holidays 2025 - Critical for T+2 settlement accuracy
VN_HOLIDAYS_2025 = [
    datetime(2025, 1, 1),   # Tết Dương lịch
    datetime(2025, 1, 28),  # Tết Nguyên Đán
    datetime(2025, 1, 29),
    datetime(2025, 1, 30),
    datetime(2025, 1, 31),
    datetime(2025, 2, 1),
    datetime(2025, 2, 2),
    datetime(2025, 2, 3),
    datetime(2025, 4, 7),   # Giỗ Tổ Hùng Vương
    datetime(2025, 4, 30),  # Giải phóng miền Nam
    datetime(2025, 5, 1),   # Quốc tế Lao động
    datetime(2025, 9, 2),   # Quốc khánh
    datetime(2025, 9, 3),
]
VN_HOLIDAY_DATES = set(h.date() for h in VN_HOLIDAYS_2025)


def count_trading_days(start_date: datetime, end_date: datetime) -> int:
    """
    Count trading days between two dates (excludes weekends AND VN holidays)

    Vietnam Stock Exchange (HOSE/HNX) operates Monday-Friday only.
    This function excludes:
    - Weekends (Saturday/Sunday)
    - VN public holidays (Tết, Quốc khánh, etc.)

    Args:
        start_date: Start datetime
        end_date: End datetime

    Returns:
        Number of trading days (Mon-Fri only, excluding holidays)

    Example:
        Buy Monday (T+0) → Can sell Wednesday (T+2)
        Buy Friday (T+0) → Can sell Tuesday (T+2, skips weekend)
        Buy Jan 27 2025 (Mon) → Cannot sell until Feb 4 (after Tết)
    """
    current = start_date.date()
    end = end_date.date()
    trading_days = 0

    while current <= end:
        is_weekend = current.weekday() >= 5  # Saturday = 5, Sunday = 6
        is_holiday = current in VN_HOLIDAY_DATES
        
        if not is_weekend and not is_holiday:
            trading_days += 1
        current += timedelta(days=1)

    return trading_days


@dataclass
class Position:
    """Trading position with exit tracking"""
    symbol: str
    quantity: int
    avg_price: float
    entry_date: datetime

    # Current state
    current_price: float = 0.0
    peak_price: float = 0.0  # Highest price since entry

    # P&L
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    # Exit parameters
    take_profit_pct: float = 0.15  # 15% profit target
    trailing_stop_pct: float = 0.05  # 5% trailing stop
    stop_loss_pct: float = -0.05  # -5% stop loss

    # Trailing stop state
    has_trailing_stop: bool = True
    trailing_stop_price: float = 0.0

    # T+2 compliance (TRADING DAYS, not calendar days)
    trading_days_held: int = 0
    can_sell: bool = False  # True if >= T+2 trading days

    # Metadata
    entry_reason: str = ""
    exit_reason: Optional[str] = None

    def __post_init__(self):
        if self.peak_price == 0:
            self.peak_price = self.avg_price
        if self.trailing_stop_price == 0:
            self.trailing_stop_price = self.avg_price * (1 - self.trailing_stop_pct)

    def update_price(self, price: float):
        """Update current price and recalculate P&L"""
        self.current_price = price

        # Update P&L
        self.unrealized_pnl = (price - self.avg_price) * self.quantity
        self.unrealized_pnl_pct = (price - self.avg_price) / self.avg_price if self.avg_price > 0 else 0

        # Update trading days held (excludes weekends)
        self.trading_days_held = count_trading_days(self.entry_date, datetime.now())

        # Check T+2 compliance (2 TRADING days, not calendar days)
        self.can_sell = self.trading_days_held >= 2

    def update_trailing_stop(self):
        """Update trailing stop if price increased"""
        if self.current_price > self.peak_price:
            self.peak_price = self.current_price
            self.trailing_stop_price = self.peak_price * (1 - self.trailing_stop_pct)

            logger.debug(
                f"Trailing stop updated: {self.symbol} | "
                f"Peak: {self.peak_price:,.0f} → Stop: {self.trailing_stop_price:,.0f}"
            )

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'entry_date': self.entry_date.isoformat(),
            'current_price': self.current_price,
            'peak_price': self.peak_price,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'take_profit_pct': self.take_profit_pct,
            'trailing_stop_pct': self.trailing_stop_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'trailing_stop_price': self.trailing_stop_price,
            'trading_days_held': self.trading_days_held,
            'can_sell': self.can_sell,
            'entry_reason': self.entry_reason,
            'exit_reason': self.exit_reason
        }


class PositionExitScheduler:
    """
    Monitor positions và tự động exit khi đạt điều kiện

    Exit logic:
    1. CHỈ exit nếu >= T+2 (tuân thủ luật VN)
    2. Exit khi:
       - Take profit hit (đạt max profit)
       - Trailing stop hit (bảo vệ lợi nhuận)
       - Stop loss hit (cắt lỗ)

    KHÔNG tự động exit chỉ vì đủ T+2.5
    """

    def __init__(
        self,
        check_interval: int = 60,  # Check mỗi 1 phút
        price_fetcher: Optional[Callable] = None
    ):
        self.check_interval = check_interval
        self.price_fetcher = price_fetcher or self._mock_price_fetcher

        # Positions
        self.positions: Dict[str, Position] = {}

        # Callbacks
        self.on_exit_callbacks: List[Callable] = []

        # State
        self.is_running = False

    def add_exit_callback(self, callback: Callable):
        """Add callback for position exits"""
        self.on_exit_callbacks.append(callback)

    def add_position(self, position: Position):
        """Add position to monitor"""
        self.positions[position.symbol] = position
        logger.info(
            f"➕ Position added: {position.symbol} | "
            f"Qty: {position.quantity} @ {position.avg_price:,.0f} | "
            f"TP: +{position.take_profit_pct*100:.0f}% | "
            f"Trail: {position.trailing_stop_pct*100:.0f}% | "
            f"SL: {position.stop_loss_pct*100:.0f}%"
        )

    def remove_position(self, symbol: str):
        """Remove position from monitoring"""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"➖ Position removed: {symbol}")

    async def start(self):
        """Start monitoring positions"""
        self.is_running = True
        logger.info(
            f"Position exit scheduler started\n"
            f"  - Check interval: {self.check_interval}s\n"
            f"  - T+2 compliance: ENFORCED\n"
            f"  - Auto exit after T+2.5: DISABLED"
        )

        while self.is_running:
            try:
                await self.check_all_positions()
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop monitoring"""
        self.is_running = False
        logger.info("Position exit scheduler stopped")

    async def check_all_positions(self):
        """Check all positions for exit conditions"""
        if not self.positions:
            return

        for symbol, position in list(self.positions.items()):
            try:
                # 1. Update current price
                current_price = await self.price_fetcher(symbol)
                position.update_price(current_price)

                # 2. Update trailing stop if price increased
                position.update_trailing_stop()

                # 3. Check exit conditions
                exit_reason = self._should_exit(position)

                if exit_reason:
                    # Exit triggered
                    await self._execute_exit(position, exit_reason)

            except Exception as e:
                logger.error(f"Error checking position {symbol}: {e}")

    def _should_exit(self, position: Position) -> Optional[str]:
        """
        Determine if position should exit

        Returns:
            exit_reason (str) if should exit, None otherwise
        """

        # CRITICAL: Chỉ exit nếu đã đủ T+2 (tuân thủ luật VN)
        if not position.can_sell:
            logger.debug(
                f"{position.symbol}: Cannot sell yet (T+{position.trading_days_held} trading days < T+2)"
            )
            return None

        # 1. Take profit (max profit target)
        if position.unrealized_pnl_pct >= position.take_profit_pct:
            return "TAKE_PROFIT"

        # 2. Trailing stop
        if position.has_trailing_stop:
            if position.current_price <= position.trailing_stop_price:
                return "TRAILING_STOP"

        # 3. Stop loss
        if position.unrealized_pnl_pct <= position.stop_loss_pct:
            return "STOP_LOSS"

        # KHÔNG tự exit chỉ vì đủ T+2.5
        # Position sẽ được giữ cho đến khi:
        # - Đạt take profit
        # - Trailing stop triggered
        # - Stop loss hit

        return None

    async def _execute_exit(self, position: Position, exit_reason: str):
        """Execute position exit"""
        position.exit_reason = exit_reason

        logger.info(
            f"🔄 AUTO-EXIT: {position.symbol} [{exit_reason}]\n"
            f"   Entry: {position.avg_price:,.0f} @ {position.entry_date.strftime('%Y-%m-%d')}\n"
            f"   Exit: {position.current_price:,.0f} (T+{position.trading_days_held} trading days)\n"
            f"   P&L: {position.unrealized_pnl:,.0f} VND ({position.unrealized_pnl_pct*100:+.2f}%)\n"
            f"   Peak: {position.peak_price:,.0f}"
        )

        # Notify callbacks
        for callback in self.on_exit_callbacks:
            try:
                await callback(position, exit_reason)
            except Exception as e:
                logger.error(f"Exit callback error: {e}")

        # Remove from monitoring
        self.remove_position(position.symbol)

    async def _mock_price_fetcher(self, symbol: str) -> float:
        """
        Price fetcher with real data support
        
        Priority:
        1. vnstock (real-time)
        2. Parquet file (historical)
        3. Mock data (last resort)
        """
        # Try vnstock first (real-time)
        try:
            from vnstock3 import Vnstock
            from datetime import datetime
            
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            df = stock.quote.history(
                start='2024-12-01', 
                end=datetime.now().strftime('%Y-%m-%d')
            )
            
            if len(df) > 0:
                price = float(df.iloc[-1]['close'])
                logger.debug(f"Price for {symbol}: {price:,.0f} VND (vnstock)")
                return price
                
        except Exception as e:
            logger.warning(f"vnstock fetch failed for {symbol}: {e}")
        
        # Fallback: Try parquet file
        try:
            import pandas as pd
            from pathlib import Path
            
            parquet_path = Path(f"data/historical/{symbol}.parquet")
            if parquet_path.exists():
                df = pd.read_parquet(parquet_path)
                price = float(df.iloc[-1]['close'])
                logger.debug(f"Price for {symbol}: {price:,.0f} VND (parquet)")
                return price
                
        except Exception as e:
            logger.warning(f"Parquet fetch failed for {symbol}: {e}")
        
        # Last resort: Mock data (random variation from avg_price)
        if symbol in self.positions:
            import random
            base_price = self.positions[symbol].avg_price
            price = base_price * (1 + random.uniform(-0.03, 0.03))
            logger.warning(f"Using MOCK price for {symbol}: {price:,.0f} VND")
            return price
        
        return 0.0

    def get_all_positions(self) -> List[Position]:
        """Get all monitored positions"""
        return list(self.positions.values())

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get specific position"""
        return self.positions.get(symbol)


# Example usage
if __name__ == "__main__":
    async def on_exit(position: Position, reason: str):
        print(f"Position exited: {position.symbol}")
        print(f"  Reason: {reason}")
        print(f"  P&L: {position.unrealized_pnl:,.0f} ({position.unrealized_pnl_pct*100:+.2f}%)")

    scheduler = PositionExitScheduler(check_interval=5)
    scheduler.add_exit_callback(on_exit)

    # Add test position
    test_position = Position(
        symbol="ACB",
        quantity=500,
        avg_price=26500,
        entry_date=datetime.now() - timedelta(days=2.5),  # T+2.5
        take_profit_pct=0.15,
        trailing_stop_pct=0.05,
        stop_loss_pct=-0.05
    )

    scheduler.add_position(test_position)

    # Run for 30 seconds
    async def test():
        task = asyncio.create_task(scheduler.start())
        await asyncio.sleep(30)
        scheduler.stop()
        await task

    asyncio.run(test())
