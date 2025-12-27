# -*- coding: utf-8 -*-
"""
FIX CRITICAL ISSUES - VN QUANT TRADING SYSTEM
=============================================
Các fix cần thiết trước khi chạy paper trading

Chạy: python fixes/fix_critical_issues.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================
# FIX 1: VN Holiday Calendar 2025
# =============================================

VN_HOLIDAYS_2025 = [
    # Tết Dương lịch
    datetime(2025, 1, 1),
    
    # Tết Nguyên Đán (29/1 - 3/2)
    datetime(2025, 1, 28),
    datetime(2025, 1, 29),
    datetime(2025, 1, 30),
    datetime(2025, 1, 31),
    datetime(2025, 2, 1),
    datetime(2025, 2, 2),
    datetime(2025, 2, 3),
    
    # Giỗ Tổ Hùng Vương (10/3 âm = ~7/4/2025)
    datetime(2025, 4, 7),
    
    # Giải phóng miền Nam & Quốc tế Lao động
    datetime(2025, 4, 30),
    datetime(2025, 5, 1),
    
    # Quốc khánh
    datetime(2025, 9, 2),
    datetime(2025, 9, 3),
]


def count_trading_days_fixed(start_date: datetime, end_date: datetime) -> int:
    """
    Count trading days between two dates (excludes weekends AND VN holidays)
    
    Vietnam Stock Exchange (HOSE/HNX) operates Monday-Friday only.
    Also excludes VN public holidays.
    """
    holiday_dates = set(h.date() for h in VN_HOLIDAYS_2025)
    
    current = start_date.date()
    end = end_date.date()
    trading_days = 0

    while current <= end:
        is_weekend = current.weekday() >= 5  # Saturday = 5, Sunday = 6
        is_holiday = current in holiday_dates
        
        if not is_weekend and not is_holiday:
            trading_days += 1
        current += timedelta(days=1)

    return trading_days


def get_trading_date_minus_n(from_date: datetime, n: int) -> datetime:
    """Get date that is N trading days before from_date"""
    holiday_dates = set(h.date() for h in VN_HOLIDAYS_2025)
    
    current = from_date.date()
    trading_days = 0
    
    while trading_days < n:
        current -= timedelta(days=1)
        is_weekend = current.weekday() >= 5
        is_holiday = current in holiday_dates
        
        if not is_weekend and not is_holiday:
            trading_days += 1
    
    return datetime.combine(current, from_date.time())


# =============================================
# FIX 2: Real-time Price Fetcher using vnstock
# =============================================

async def real_price_fetcher(symbol: str) -> float:
    """
    Fetch real-time price from VCI/vnstock
    
    Args:
        symbol: Stock symbol (e.g., 'ACB', 'HPG')
    
    Returns:
        Current price in VND
    """
    try:
        from vnstock3 import Vnstock
        
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        df = stock.quote.history(start='2024-12-01', end=datetime.now().strftime('%Y-%m-%d'))
        
        if len(df) > 0:
            return float(df.iloc[-1]['close'])
        else:
            raise ValueError(f"No data for {symbol}")
            
    except Exception as e:
        print(f"❌ Price fetch error for {symbol}: {e}")
        
        # Fallback: Try from parquet file
        try:
            import pandas as pd
            parquet_path = Path(f"data/historical/{symbol}.parquet")
            if parquet_path.exists():
                df = pd.read_parquet(parquet_path)
                return float(df.iloc[-1]['close'])
        except:
            pass
        
        return 0.0


# =============================================
# FIX 3: Transaction Costs Calculator
# =============================================

class VNTransactionCosts:
    """Vietnam market transaction costs"""
    
    # Commission (broker fee)
    COMMISSION_BUY = 0.0015  # 0.15%
    COMMISSION_SELL = 0.0015  # 0.15%
    
    # Selling tax (only on sell)
    SELLING_TAX = 0.001  # 0.1%
    
    # Slippage estimate (market impact)
    SLIPPAGE = 0.002  # 0.2%
    
    @classmethod
    def calculate_buy_cost(cls, price: float, quantity: int) -> dict:
        """Calculate total cost for buying"""
        gross_value = price * quantity
        commission = gross_value * cls.COMMISSION_BUY
        slippage = gross_value * cls.SLIPPAGE
        
        total_cost = gross_value + commission + slippage
        
        return {
            'gross_value': gross_value,
            'commission': commission,
            'slippage': slippage,
            'total_cost': total_cost,
            'effective_price': total_cost / quantity
        }
    
    @classmethod
    def calculate_sell_proceeds(cls, price: float, quantity: int) -> dict:
        """Calculate net proceeds from selling"""
        gross_value = price * quantity
        commission = gross_value * cls.COMMISSION_SELL
        tax = gross_value * cls.SELLING_TAX
        slippage = gross_value * cls.SLIPPAGE
        
        net_proceeds = gross_value - commission - tax - slippage
        
        return {
            'gross_value': gross_value,
            'commission': commission,
            'tax': tax,
            'slippage': slippage,
            'net_proceeds': net_proceeds,
            'effective_price': net_proceeds / quantity
        }
    
    @classmethod
    def calculate_pnl(cls, buy_price: float, sell_price: float, quantity: int) -> dict:
        """Calculate profit/loss with all costs"""
        buy_costs = cls.calculate_buy_cost(buy_price, quantity)
        sell_proceeds = cls.calculate_sell_proceeds(sell_price, quantity)
        
        pnl = sell_proceeds['net_proceeds'] - buy_costs['total_cost']
        pnl_pct = pnl / buy_costs['total_cost']
        
        return {
            'buy_total': buy_costs['total_cost'],
            'sell_net': sell_proceeds['net_proceeds'],
            'pnl_vnd': pnl,
            'pnl_pct': pnl_pct,
            'total_fees': (buy_costs['commission'] + buy_costs['slippage'] + 
                          sell_proceeds['commission'] + sell_proceeds['tax'] + 
                          sell_proceeds['slippage'])
        }


# =============================================
# FIX 4: VN Price Step Validator
# =============================================

class VNPriceValidator:
    """Validate VN market price rules"""
    
    # HOSE price steps
    HOSE_STEPS = [
        (10000, 10),      # < 10,000 VND: 10 VND step
        (50000, 50),      # 10,000 - 49,950: 50 VND step
        (float('inf'), 100)  # >= 50,000: 100 VND step
    ]
    
    @classmethod
    def get_price_step(cls, price: float) -> int:
        """Get valid price step for given price"""
        for threshold, step in cls.HOSE_STEPS:
            if price < threshold:
                return step
        return 100
    
    @classmethod
    def is_valid_price(cls, price: float) -> bool:
        """Check if price follows VN market rules"""
        step = cls.get_price_step(price)
        return price % step == 0
    
    @classmethod
    def round_price(cls, price: float, direction: str = 'down') -> float:
        """Round price to valid step"""
        step = cls.get_price_step(price)
        
        if direction == 'down':
            return (price // step) * step
        else:  # up
            return ((price // step) + 1) * step
    
    @classmethod
    def is_valid_quantity(cls, quantity: int) -> bool:
        """Check if quantity is valid (multiple of 100)"""
        return quantity % 100 == 0
    
    @classmethod
    def round_quantity(cls, quantity: int, direction: str = 'down') -> int:
        """Round quantity to valid lot size"""
        if direction == 'down':
            return (quantity // 100) * 100
        else:  # up
            return ((quantity // 100) + 1) * 100


# =============================================
# FIX 5: Market Session Checker
# =============================================

class VNMarketSession:
    """Vietnam market session manager"""
    
    SESSIONS = {
        'PRE_OPEN': (('08:30', '09:00'), 'Preparation'),
        'ATO': (('09:00', '09:15'), 'Opening Auction'),
        'MORNING': (('09:15', '11:30'), 'Continuous Trading'),
        'BREAK': (('11:30', '13:00'), 'Lunch Break'),
        'AFTERNOON': (('13:00', '14:30'), 'Continuous Trading'),
        'ATC': (('14:30', '14:45'), 'Closing Auction'),
        'POST_CLOSE': (('14:45', '15:00'), 'Order Matching'),
        'CLOSED': (('15:00', '08:30'), 'Market Closed'),
    }
    
    @classmethod
    def get_current_session(cls) -> tuple:
        """Get current market session"""
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        
        # Check if weekend
        if now.weekday() >= 5:
            return 'WEEKEND', 'Market Closed (Weekend)'
        
        # Check if holiday
        if now.date() in [h.date() for h in VN_HOLIDAYS_2025]:
            return 'HOLIDAY', 'Market Closed (Holiday)'
        
        for session, ((start, end), desc) in cls.SESSIONS.items():
            if start <= current_time < end:
                return session, desc
        
        return 'CLOSED', 'Market Closed'
    
    @classmethod
    def can_trade(cls) -> tuple:
        """Check if trading is allowed now"""
        session, _ = cls.get_current_session()
        
        allowed = session in ['ATO', 'MORNING', 'AFTERNOON', 'ATC']
        order_types = []
        
        if session == 'ATO':
            order_types = ['ATO', 'LO']
        elif session in ['MORNING', 'AFTERNOON']:
            order_types = ['LO', 'MP', 'MAK', 'MOK', 'MTL']
        elif session == 'ATC':
            order_types = ['ATC', 'LO']
        
        return allowed, order_types
    
    @classmethod
    def time_until_next_session(cls, target_session: str) -> timedelta:
        """Calculate time until next target session"""
        now = datetime.now()
        
        if target_session not in cls.SESSIONS:
            raise ValueError(f"Unknown session: {target_session}")
        
        start_time, _ = cls.SESSIONS[target_session][0]
        start_hour, start_min = map(int, start_time.split(':'))
        
        target = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        
        if target <= now:
            # Next occurrence is tomorrow or later
            target += timedelta(days=1)
            
            # Skip weekends
            while target.weekday() >= 5:
                target += timedelta(days=1)
        
        return target - now


# =============================================
# TESTING
# =============================================

def test_fixes():
    """Test all fixes"""
    print("=" * 60)
    print("TESTING CRITICAL FIXES")
    print("=" * 60)
    
    # Test 1: Trading days
    print("\n📅 TEST 1: Trading Days Calculation")
    start = datetime(2025, 1, 27)  # Monday before Tết
    end = datetime(2025, 2, 5)     # Wednesday after Tết
    
    trading_days = count_trading_days_fixed(start, end)
    print(f"   From {start.date()} to {end.date()}: {trading_days} trading days")
    print(f"   (Expected: ~3 days, excluding Tết holidays)")
    
    # Test 2: Transaction costs
    print("\n💰 TEST 2: Transaction Costs")
    costs = VNTransactionCosts.calculate_pnl(
        buy_price=26500,
        sell_price=28000,
        quantity=1000
    )
    print(f"   Buy: 26,500 x 1000 = {costs['buy_total']:,.0f} VND (with fees)")
    print(f"   Sell: 28,000 x 1000 = {costs['sell_net']:,.0f} VND (after fees)")
    print(f"   PnL: {costs['pnl_vnd']:,.0f} VND ({costs['pnl_pct']*100:.2f}%)")
    print(f"   Total Fees: {costs['total_fees']:,.0f} VND")
    
    # Test 3: Price validation
    print("\n💲 TEST 3: Price Validation")
    test_prices = [9990, 10000, 25350, 50050]
    for price in test_prices:
        valid = VNPriceValidator.is_valid_price(price)
        step = VNPriceValidator.get_price_step(price)
        rounded = VNPriceValidator.round_price(price)
        print(f"   {price:,} VND: Valid={valid}, Step={step}, Rounded={rounded:,}")
    
    # Test 4: Market session
    print("\n⏰ TEST 4: Market Session")
    session, desc = VNMarketSession.get_current_session()
    can_trade, order_types = VNMarketSession.can_trade()
    print(f"   Current: {session} ({desc})")
    print(f"   Can Trade: {can_trade}")
    print(f"   Order Types: {order_types}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    test_fixes()
