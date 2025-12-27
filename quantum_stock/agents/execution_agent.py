# -*- coding: utf-8 -*-
"""
Execution Agent - Agentic Level 5
Handles order execution with human oversight

Features:
- Order generation from signals
- Risk pre-checks
- Human approval workflow
- Execution monitoring
- Post-trade analysis
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio

from .base_agent import BaseAgent, AgentSignal


class OrderStatus(Enum):
    PENDING = "PENDING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass
class Order:
    """Trading order"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float]
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    filled_quantity: int = 0
    filled_price: float = 0.0
    commission: float = 0.0
    reason: str = ""
    source_signal: Optional[AgentSignal] = None
    
    def to_dict(self) -> Dict:
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'status': self.status.value,
            'created_at': str(self.created_at),
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'commission': self.commission,
            'reason': self.reason
        }


@dataclass
class ExecutionMetrics:
    """Execution quality metrics"""
    total_orders: int = 0
    filled_orders: int = 0
    rejected_orders: int = 0
    avg_slippage: float = 0.0
    avg_fill_time_seconds: float = 0.0
    total_commission: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'total_orders': self.total_orders,
            'filled_orders': self.filled_orders,
            'rejected_orders': self.rejected_orders,
            'fill_rate': self.filled_orders / self.total_orders if self.total_orders > 0 else 0,
            'avg_slippage': self.avg_slippage,
            'avg_fill_time': self.avg_fill_time_seconds,
            'total_commission': self.total_commission
        }


class ExecutionAgent(BaseAgent):
    """
    Execution Agent - Level 5 Agentic Platform
    
    Responsibilities:
    - Convert signals to orders
    - Risk pre-checks
    - Manage human approval workflow
    - Monitor execution
    - Track execution quality
    """
    
    def __init__(
        self,
        auto_approval_limit: float = 10_000_000,  # 10M VND
        max_position_pct: float = 0.1,  # 10% of portfolio
        max_daily_trades: int = 20
    ):
        super().__init__(
            name="EXECUTOR",
            role="Order Execution Manager",
            description="Manages order execution with human oversight",
            weight=1.0
        )
        
        # Execution parameters
        self.auto_approval_limit = auto_approval_limit
        self.max_position_pct = max_position_pct
        self.max_daily_trades = max_daily_trades
        
        # Portfolio state
        self.portfolio_value: float = 100_000_000  # 100M VND default
        self.positions: Dict[str, int] = {}  # symbol -> shares
        self.cash: float = 100_000_000
        
        # Order management
        self.pending_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        self.daily_trades: int = 0
        self.last_trade_date: Optional[datetime] = None
        
        # Metrics
        self.metrics = ExecutionMetrics()
        
        # Callbacks for human approval
        self.approval_callbacks: Dict[str, asyncio.Future] = {}
    
    async def analyze(self, stock_data: Any, context: Dict[str, Any] = None) -> AgentSignal:
        """Not used - Execution agent responds to signals, not generates them"""
        return AgentSignal(
            agent_name=self.name,
            signal="NEUTRAL",
            confidence=0.0,
            entry_price=0,
            reasoning="Execution agent does not generate signals",
            key_factors=[],
            timestamp=datetime.now()
        )
    
    async def execute_signal(
        self,
        signal: AgentSignal,
        current_price: float,
        broker: Any = None
    ) -> Order:
        """
        Convert signal to order and execute
        
        Args:
            signal: Trading signal from agents
            current_price: Current market price
            broker: Broker interface (optional, for paper trading if None)
            
        Returns:
            Order object
        """
        # Reset daily counter if new day
        today = datetime.now().date()
        if self.last_trade_date != today:
            self.daily_trades = 0
            self.last_trade_date = today
        
        # Create order from signal
        order = self._create_order(signal, current_price)
        
        # Risk pre-checks
        risk_check = self._risk_precheck(order)
        if not risk_check['passed']:
            order.status = OrderStatus.REJECTED
            order.reason = risk_check['reason']
            self.order_history.append(order)
            self.metrics.rejected_orders += 1
            return order
        
        # Check if human approval needed
        order_value = order.quantity * (order.price or current_price)
        if order_value > self.auto_approval_limit:
            order.status = OrderStatus.AWAITING_APPROVAL
            self.pending_orders[order.order_id] = order
            
            # Wait for human approval (with timeout)
            try:
                approved = await self._wait_for_approval(order.order_id, timeout=60)
                if not approved:
                    order.status = OrderStatus.REJECTED
                    order.reason = "Human approval timeout or rejected"
                    return order
            except asyncio.TimeoutError:
                order.status = OrderStatus.REJECTED
                order.reason = "Approval timeout"
                return order
        
        order.status = OrderStatus.APPROVED
        order.approved_at = datetime.now()
        
        # Execute order
        if broker:
            result = await self._execute_with_broker(order, broker)
        else:
            result = await self._paper_execute(order, current_price)
        
        return result
    
    def _create_order(self, signal: AgentSignal, current_price: float) -> Order:
        """Create order from signal"""
        import uuid
        
        # Determine side
        if signal.signal in ['LONG', 'BUY']:
            side = OrderSide.BUY
        elif signal.signal in ['SHORT', 'SELL']:
            side = OrderSide.SELL
        else:
            side = OrderSide.BUY  # Default
        
        # Calculate position size using Kelly or fixed
        position_value = self.portfolio_value * self.max_position_pct * signal.confidence
        quantity = int(position_value / current_price / 100) * 100  # Round to lot
        
        # Determine order type
        if signal.entry_price and abs(signal.entry_price - current_price) / current_price > 0.01:
            order_type = OrderType.LIMIT
            price = signal.entry_price
        else:
            order_type = OrderType.MARKET
            price = None
        
        return Order(
            order_id=str(uuid.uuid4())[:8],
            symbol=signal.key_factors[0].split(':')[0] if signal.key_factors else 'UNKNOWN',
            side=side,
            order_type=order_type,
            quantity=max(100, quantity),  # Minimum lot
            price=price,
            stop_price=signal.stop_loss,
            source_signal=signal
        )
    
    def _risk_precheck(self, order: Order) -> Dict:
        """Pre-trade risk checks"""
        checks = []
        
        # 1. Daily trade limit
        if self.daily_trades >= self.max_daily_trades:
            return {'passed': False, 'reason': 'Daily trade limit reached'}
        
        # 2. Position size limit
        order_value = order.quantity * (order.price or 1000)  # Estimate
        if order_value > self.portfolio_value * self.max_position_pct * 1.5:
            return {'passed': False, 'reason': 'Position size exceeds limit'}
        
        # 3. Cash availability for buy orders
        if order.side == OrderSide.BUY:
            if order_value > self.cash:
                return {'passed': False, 'reason': 'Insufficient cash'}
        
        # 4. Position availability for sell orders
        if order.side == OrderSide.SELL:
            current_position = self.positions.get(order.symbol, 0)
            if order.quantity > current_position:
                return {'passed': False, 'reason': 'Insufficient shares to sell'}
        
        return {'passed': True, 'reason': ''}
    
    async def _wait_for_approval(self, order_id: str, timeout: int = 60) -> bool:
        """Wait for human approval"""
        future = asyncio.get_event_loop().create_future()
        self.approval_callbacks[order_id] = future
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        finally:
            self.approval_callbacks.pop(order_id, None)
    
    def approve_order(self, order_id: str, approved: bool = True):
        """Human approval callback"""
        if order_id in self.approval_callbacks:
            self.approval_callbacks[order_id].set_result(approved)
        
        if order_id in self.pending_orders:
            order = self.pending_orders[order_id]
            if approved:
                order.status = OrderStatus.APPROVED
                order.approved_at = datetime.now()
            else:
                order.status = OrderStatus.REJECTED
                order.reason = "Human rejected"
    
    async def _paper_execute(self, order: Order, current_price: float) -> Order:
        """Paper trading execution"""
        order.status = OrderStatus.EXECUTING
        
        # Simulate slippage
        slippage_pct = 0.001  # 0.1%
        if order.side == OrderSide.BUY:
            fill_price = current_price * (1 + slippage_pct)
        else:
            fill_price = current_price * (1 - slippage_pct)
        
        # Simulate partial fills for large orders
        if order.quantity > 10000:
            fill_rate = 0.9  # 90% fill
        else:
            fill_rate = 1.0
        
        filled_qty = int(order.quantity * fill_rate)
        
        # Update order
        order.filled_quantity = filled_qty
        order.filled_price = fill_price
        order.commission = filled_qty * fill_price * 0.0015  # 0.15% commission
        order.executed_at = datetime.now()
        order.status = OrderStatus.FILLED if fill_rate == 1.0 else OrderStatus.PARTIAL
        
        # Update positions
        if order.side == OrderSide.BUY:
            self.positions[order.symbol] = self.positions.get(order.symbol, 0) + filled_qty
            self.cash -= filled_qty * fill_price + order.commission
        else:
            self.positions[order.symbol] = self.positions.get(order.symbol, 0) - filled_qty
            self.cash += filled_qty * fill_price - order.commission
        
        # Update metrics
        self.metrics.total_orders += 1
        self.metrics.filled_orders += 1
        self.metrics.total_commission += order.commission
        self.daily_trades += 1
        
        # Save to history
        self.order_history.append(order)
        
        return order
    
    async def _execute_with_broker(self, order: Order, broker: Any) -> Order:
        """Execute with real broker API"""
        try:
            result = await broker.place_order(
                symbol=order.symbol,
                side=order.side.value,
                order_type=order.order_type.value,
                quantity=order.quantity,
                price=order.price,
                stop_price=order.stop_price
            )
            
            order.filled_quantity = result.get('filled_quantity', 0)
            order.filled_price = result.get('filled_price', 0)
            order.commission = result.get('commission', 0)
            order.executed_at = datetime.now()
            
            if order.filled_quantity == order.quantity:
                order.status = OrderStatus.FILLED
            elif order.filled_quantity > 0:
                order.status = OrderStatus.PARTIAL
            else:
                order.status = OrderStatus.FAILED
                order.reason = result.get('error', 'Unknown error')
            
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.reason = str(e)
        
        self.order_history.append(order)
        return order
    
    def get_open_positions(self) -> Dict[str, int]:
        """Get current open positions"""
        return {k: v for k, v in self.positions.items() if v != 0}
    
    def get_pending_orders(self) -> List[Order]:
        """Get orders awaiting approval"""
        return [o for o in self.pending_orders.values() 
                if o.status == OrderStatus.AWAITING_APPROVAL]
    
    def get_execution_metrics(self) -> ExecutionMetrics:
        """Get execution quality metrics"""
        return self.metrics
    
    def set_portfolio_value(self, value: float):
        """Update portfolio value"""
        self.portfolio_value = value
    
    def set_cash(self, cash: float):
        """Update available cash"""
        self.cash = cash
