# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    LIVE TRADING ENGINE                                       ║
║                    Real-time Order Execution & Position Management          ║
╚══════════════════════════════════════════════════════════════════════════════╝

Bridge between strategy signals and broker execution
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import queue
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# DATA MODELS  
# ============================================

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    LIMIT = "LO"
    MARKET = "MP"
    ATO = "ATO"
    ATC = "ATC"


class OrderStatus(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Trading order"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: float
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    filled_price: float = 0.0
    broker_order_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    message: str = ""


@dataclass
class Position:
    """Portfolio position"""
    symbol: str
    quantity: int
    avg_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    
    def update_price(self, price: float):
        """Update current price and P&L"""
        self.current_price = price
        self.unrealized_pnl = (price - self.avg_price) * self.quantity
        self.unrealized_pnl_pct = (price - self.avg_price) / self.avg_price if self.avg_price > 0 else 0


@dataclass
class TradingSignal:
    """Signal from strategy"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    quantity: int = 0
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================
# RISK CONTROLLER
# ============================================

class RiskController:
    """
    Pre-trade risk validation
    
    Enforces:
    - Position limits
    - Daily loss limits
    - Order size limits
    - VN market rules
    """
    
    def __init__(self, config: Dict = None):
        config = config or {}
        
        self.max_position_pct = config.get('max_position_pct', 0.20)  # 20% max per position
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 0.05)  # 5% daily loss limit
        self.max_order_value = config.get('max_order_value', 1_000_000_000)  # 1B VND
        self.min_order_value = config.get('min_order_value', 1_000_000)  # 1M VND
        
        self.daily_pnl = 0.0
        self.last_reset = datetime.now().date()
    
    def validate_order(self, order: Order, portfolio_value: float,
                       positions: Dict[str, Position]) -> tuple[bool, str]:
        """
        Validate order against risk rules
        
        Returns: (is_valid, reason)
        """
        # Reset daily P&L if new day
        if datetime.now().date() != self.last_reset:
            self.daily_pnl = 0.0
            self.last_reset = datetime.now().date()
        
        order_value = order.quantity * order.price
        
        # Check order value
        if order_value < self.min_order_value:
            return False, f"Order value {order_value:,.0f} below minimum {self.min_order_value:,.0f}"
        
        if order_value > self.max_order_value:
            return False, f"Order value {order_value:,.0f} exceeds maximum {self.max_order_value:,.0f}"
        
        # Check position limit
        if order.side == OrderSide.BUY:
            current_position_value = 0
            if order.symbol in positions:
                current_position_value = positions[order.symbol].quantity * positions[order.symbol].current_price
            
            new_position_value = current_position_value + order_value
            max_position_value = portfolio_value * self.max_position_pct
            
            if new_position_value > max_position_value:
                return False, f"Position would exceed {self.max_position_pct:.0%} limit"
        
        # Check daily loss limit
        max_daily_loss = portfolio_value * self.max_daily_loss_pct
        if -self.daily_pnl >= max_daily_loss:
            return False, f"Daily loss limit of {self.max_daily_loss_pct:.0%} reached"
        
        # VN market specific rules
        if order.quantity % 100 != 0:
            return False, f"Quantity must be multiple of 100 (lot size)"
        
        if order.price % 10 != 0:
            return False, f"Price must be multiple of 10 VND"
        
        return True, "OK"
    
    def update_pnl(self, pnl: float):
        """Update daily P&L"""
        self.daily_pnl += pnl


# ============================================
# ORDER MANAGER
# ============================================

class OrderManager:
    """
    Manage orders lifecycle
    """
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.pending_orders: queue.Queue = queue.Queue()
        self.callbacks: Dict[str, List[Callable]] = {}
        self._order_counter = 0
    
    def create_order(self, symbol: str, side: OrderSide, order_type: OrderType,
                     quantity: int, price: float) -> Order:
        """Create a new order"""
        self._order_counter += 1
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._order_counter}"
        
        order = Order(
            order_id=order_id,
            symbol=symbol.upper(),
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price
        )
        
        self.orders[order_id] = order
        self.pending_orders.put(order)
        
        logger.info(f"Order created: {order_id} {side.value} {quantity} {symbol} @ {price}")
        return order
    
    def update_order(self, order_id: str, status: OrderStatus,
                     filled_qty: int = 0, filled_price: float = 0.0,
                     message: str = ""):
        """Update order status"""
        if order_id not in self.orders:
            return
        
        order = self.orders[order_id]
        order.status = status
        order.filled_quantity = filled_qty
        order.filled_price = filled_price
        order.message = message
        order.updated_at = datetime.now()
        
        logger.info(f"Order updated: {order_id} -> {status.value}")
        
        # Notify callbacks
        for callback in self.callbacks.get('order_update', []):
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            logger.info(f"Order cancelled: {order_id}")
            return True
        
        return False
    
    def get_open_orders(self, symbol: str = None) -> List[Order]:
        """Get open orders"""
        open_statuses = [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL]
        orders = [o for o in self.orders.values() if o.status in open_statuses]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders
    
    def on_order_update(self, callback: Callable):
        """Register order update callback"""
        if 'order_update' not in self.callbacks:
            self.callbacks['order_update'] = []
        self.callbacks['order_update'].append(callback)


# ============================================
# POSITION MANAGER
# ============================================

class PositionManager:
    """
    Manage portfolio positions
    """
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.closed_pnl = 0.0
    
    def update_on_fill(self, order: Order):
        """Update positions when order is filled"""
        symbol = order.symbol
        
        if symbol not in self.positions:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=0,
                avg_price=0.0
            )
        
        pos = self.positions[symbol]
        
        if order.side == OrderSide.BUY:
            # Add to position
            total_qty = pos.quantity + order.filled_quantity
            total_value = pos.quantity * pos.avg_price + order.filled_quantity * order.filled_price
            
            pos.quantity = total_qty
            pos.avg_price = total_value / total_qty if total_qty > 0 else 0
            
        elif order.side == OrderSide.SELL:
            # Reduce position
            if order.filled_quantity <= pos.quantity:
                # Calculate realized P&L
                pnl = (order.filled_price - pos.avg_price) * order.filled_quantity
                self.closed_pnl += pnl
                
                pos.quantity -= order.filled_quantity
                
                if pos.quantity == 0:
                    del self.positions[symbol]
    
    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_price(price)
    
    def get_total_value(self) -> float:
        """Get total portfolio value"""
        return sum(p.quantity * p.current_price for p in self.positions.values())
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L"""
        return sum(p.unrealized_pnl for p in self.positions.values())
    
    def to_dataframe(self) -> 'pd.DataFrame':
        """Export positions to DataFrame"""
        import pandas as pd
        
        if not self.positions:
            return pd.DataFrame()
        
        data = []
        for symbol, pos in self.positions.items():
            data.append({
                'Symbol': symbol,
                'Quantity': pos.quantity,
                'Avg Price': pos.avg_price,
                'Current Price': pos.current_price,
                'Market Value': pos.quantity * pos.current_price,
                'Unrealized P&L': pos.unrealized_pnl,
                'Unrealized %': pos.unrealized_pnl_pct * 100
            })
        
        return pd.DataFrame(data)


# ============================================
# EXECUTION ENGINE
# ============================================

class ExecutionEngine:
    """
    Main execution engine
    
    Connects strategies -> risk -> broker
    """
    
    def __init__(self, broker=None, initial_capital: float = 100_000_000):
        self.broker = broker
        self.order_manager = OrderManager()
        self.position_manager = PositionManager()
        self.risk_controller = RiskController()
        
        self.cash_balance = initial_capital
        self.initial_capital = initial_capital
        
        self.signal_queue: queue.Queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    @property
    def portfolio_value(self) -> float:
        """Total portfolio value"""
        return self.cash_balance + self.position_manager.get_total_value()
    
    @property
    def total_return(self) -> float:
        """Total return percentage"""
        return (self.portfolio_value - self.initial_capital) / self.initial_capital
    
    def submit_signal(self, signal: TradingSignal):
        """Submit a trading signal for execution"""
        self.signal_queue.put(signal)
        logger.info(f"Signal submitted: {signal.action} {signal.symbol}")
    
    def process_signal(self, signal: TradingSignal) -> Optional[Order]:
        """Process a trading signal"""
        if signal.action == "HOLD":
            return None
        
        # Determine side
        side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
        
        # Calculate quantity if not specified
        quantity = signal.quantity
        if quantity == 0:
            if side == OrderSide.BUY:
                # Size based on confidence and available capital
                position_size = self.cash_balance * 0.1 * signal.confidence
                quantity = int(position_size / signal.price / 100) * 100
            else:
                # Sell existing position
                if signal.symbol in self.position_manager.positions:
                    quantity = self.position_manager.positions[signal.symbol].quantity
        
        if quantity <= 0:
            logger.warning(f"No valid quantity for signal: {signal}")
            return None
        
        # Create order
        order = self.order_manager.create_order(
            symbol=signal.symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=signal.price
        )
        
        # Risk validation
        is_valid, reason = self.risk_controller.validate_order(
            order, self.portfolio_value, self.position_manager.positions
        )
        
        if not is_valid:
            order.status = OrderStatus.REJECTED
            order.message = reason
            logger.warning(f"Order rejected: {reason}")
            return order
        
        # Submit to broker
        if self.broker:
            try:
                # Async broker call would go here
                pass
            except Exception as e:
                order.status = OrderStatus.REJECTED
                order.message = str(e)
                logger.error(f"Broker error: {e}")
                return order
        
        # Paper trading: simulate immediate fill
        self._simulate_fill(order)
        
        return order
    
    def _simulate_fill(self, order: Order):
        """Simulate order fill for paper trading"""
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = order.price
        
        # Update positions
        self.position_manager.update_on_fill(order)
        
        # Update cash
        trade_value = order.filled_quantity * order.filled_price
        commission = trade_value * 0.0015  # 0.15% commission
        
        if order.side == OrderSide.BUY:
            self.cash_balance -= (trade_value + commission)
        else:
            self.cash_balance += (trade_value - commission)
        
        logger.info(f"Order filled: {order.order_id} @ {order.filled_price}")
    
    def start(self):
        """Start execution engine"""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop)
        self._thread.daemon = True
        self._thread.start()
        logger.info("Execution engine started")
    
    def stop(self):
        """Stop execution engine"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Execution engine stopped")
    
    def _run_loop(self):
        """Main processing loop"""
        while self._running:
            try:
                signal = self.signal_queue.get(timeout=1)
                self.process_signal(signal)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Execution error: {e}")
    
    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            'running': self._running,
            'portfolio_value': self.portfolio_value,
            'cash_balance': self.cash_balance,
            'total_return': self.total_return,
            'positions': len(self.position_manager.positions),
            'open_orders': len(self.order_manager.get_open_orders()),
            'realized_pnl': self.position_manager.closed_pnl,
            'unrealized_pnl': self.position_manager.get_total_unrealized_pnl()
        }


# ============================================
# TESTING
# ============================================

def test_execution_engine():
    """Test execution engine"""
    print("Testing Execution Engine...")
    print("=" * 50)
    
    # Create engine
    engine = ExecutionEngine(initial_capital=100_000_000)
    
    # Submit signals
    signals = [
        TradingSignal(symbol="HPG", action="BUY", confidence=0.8, price=25000),
        TradingSignal(symbol="VNM", action="BUY", confidence=0.7, price=75000),
        TradingSignal(symbol="HPG", action="SELL", confidence=0.6, price=26000),
    ]
    
    for signal in signals:
        order = engine.process_signal(signal)
        if order:
            print(f"  {order.side.value} {order.quantity} {order.symbol} @ {order.price:,.0f} -> {order.status.value}")
    
    # Status
    status = engine.get_status()
    print(f"\n📊 Engine Status:")
    print(f"   Portfolio Value: {status['portfolio_value']:,.0f} VND")
    print(f"   Cash Balance: {status['cash_balance']:,.0f} VND")
    print(f"   Total Return: {status['total_return']:.2%}")
    print(f"   Realized P&L: {status['realized_pnl']:,.0f} VND")
    
    # Positions
    print(f"\n📈 Positions:")
    df = engine.position_manager.to_dataframe()
    if not df.empty:
        print(df.to_string(index=False))
    else:
        print("   No open positions")
    
    print("\n✅ Execution Engine tests completed!")


if __name__ == "__main__":
    test_execution_engine()
