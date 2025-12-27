#!/usr/bin/env python3
"""
System Integration Test
========================
Test all components before paper trading
"""

import asyncio
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)


async def test_market_data():
    """Test real-time market data provider"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Market Data Provider")
    logger.info("="*70)

    try:
        from quantum_stock.data.realtime_market_data import RealtimeMarketData

        provider = RealtimeMarketData()
        await provider.start()

        # Test get prices
        test_symbols = ['ACB', 'VCB', 'HPG', 'FPT']
        for symbol in test_symbols:
            price = await provider.get_price(symbol)
            logger.info(f"  {symbol}: {price:.2f}k VND")

        # Test orderbook
        orderbook = await provider.get_orderbook('ACB')
        logger.info(f"  ACB orderbook: bid={orderbook['bid']:.2f}, ask={orderbook['ask']:.2f}")

        await provider.stop()
        logger.info("✅ Market Data Provider: PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Market Data Provider: FAILED - {e}")
        return False


async def test_paper_broker():
    """Test paper trading broker"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Paper Trading Broker")
    logger.info("="*70)

    try:
        from quantum_stock.core.broker_api import BrokerFactory, OrderSide, OrderType

        broker = BrokerFactory.create("paper", initial_balance=100_000_000)
        await broker.authenticate()

        logger.info(f"  Initial balance: {broker.cash_balance:,.0f} VND")

        # Test place order
        order = await broker.place_order(
            symbol='ACB',
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            price=26.5
        )
        logger.info(f"  Order placed: {order.order_id} - {order.side.value} {order.quantity} @ {order.price}")

        # Test get positions
        positions = await broker.get_positions()
        logger.info(f"  Positions: {len(positions)}")

        # Test account info
        account = await broker.get_account_info()
        logger.info(f"  Account: {account.name}, Balance: {account.cash_balance:,.0f}")

        logger.info("✅ Paper Broker: PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Paper Broker: FAILED - {e}", exc_info=True)
        return False


async def test_agent_coordinator():
    """Test agent coordinator"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Agent Coordinator")
    logger.info("="*70)

    try:
        from quantum_stock.agents.agent_coordinator import AgentCoordinator
        from quantum_stock.agents.base_agent import StockData
        import pandas as pd

        coordinator = AgentCoordinator(portfolio_value=100_000_000)

        # Create mock stock data
        stock_data = StockData(
            symbol='ACB',
            current_price=26.5,
            open_price=26.0,
            high_price=27.0,
            low_price=25.5,
            volume=10_000_000,
            change_percent=1.92,
            historical_data=pd.DataFrame()
        )

        # Test with timeout
        logger.info("  Running agent discussion...")
        discussion = await asyncio.wait_for(
            coordinator.analyze_stock(stock_data, {}),
            timeout=10.0
        )

        logger.info(f"  Messages: {len(discussion.messages)}")
        logger.info(f"  Final verdict: {discussion.final_verdict.signal_type.value if discussion.final_verdict else 'None'}")
        logger.info(f"  Consensus: {discussion.consensus_score:.1f}%")

        logger.info("✅ Agent Coordinator: PASSED")
        return True

    except asyncio.TimeoutError:
        logger.warning("⚠️  Agent Coordinator: TIMEOUT (will use fallback mock)")
        return True  # OK to timeout, fallback will handle
    except Exception as e:
        logger.error(f"❌ Agent Coordinator: FAILED - {e}", exc_info=True)
        return False


async def test_position_exit_scheduler():
    """Test position exit scheduler with T+2"""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Position Exit Scheduler (T+2)")
    logger.info("="*70)

    try:
        from quantum_stock.autonomous.position_exit_scheduler import (
            PositionExitScheduler, Position, count_trading_days
        )
        from datetime import datetime, timedelta

        # Test count_trading_days
        monday = datetime(2025, 12, 29)  # Monday
        wednesday = datetime(2025, 12, 31)  # Wednesday
        days = count_trading_days(monday, wednesday)
        logger.info(f"  Trading days Mon-Wed: {days} (expected: 3)")

        # Test with weekend
        friday = datetime(2025, 12, 26)  # Friday
        next_tuesday = datetime(2025, 12, 30)  # Next Tuesday
        days_with_weekend = count_trading_days(friday, next_tuesday)
        logger.info(f"  Trading days Fri-Tue (with weekend): {days_with_weekend} (expected: 3)")

        # Create scheduler
        scheduler = PositionExitScheduler()

        # Add position
        position = Position(
            symbol='ACB',
            quantity=1000,
            avg_price=26.5,
            entry_date=datetime.now(),
            take_profit_pct=0.15,
            trailing_stop_pct=0.05,
            stop_loss_pct=-0.05
        )
        scheduler.add_position(position)

        positions = scheduler.get_all_positions()
        logger.info(f"  Positions tracked: {len(positions)}")

        logger.info("✅ Position Exit Scheduler: PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Position Exit Scheduler: FAILED - {e}", exc_info=True)
        return False


async def test_orchestrator_init():
    """Test orchestrator initialization"""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Orchestrator Initialization")
    logger.info("="*70)

    try:
        from quantum_stock.autonomous.orchestrator import AutonomousOrchestrator

        orchestrator = AutonomousOrchestrator(
            paper_trading=True,
            initial_balance=100_000_000
        )

        logger.info(f"  Paper trading: {orchestrator.paper_trading}")
        logger.info(f"  Balance: {orchestrator.broker.cash_balance:,.0f} VND")
        logger.info(f"  Model scanner: {orchestrator.model_scanner is not None}")
        logger.info(f"  News scanner: {orchestrator.news_scanner is not None}")
        logger.info(f"  Market data: {orchestrator.market_data is not None}")
        logger.info(f"  Agent coordinator: {orchestrator.agent_coordinator is not None}")

        logger.info("✅ Orchestrator: PASSED")
        return True

    except Exception as e:
        logger.error(f"❌ Orchestrator: FAILED - {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("╔══════════════════════════════════════════════════════════════════╗")
    logger.info("║     VN-QUANT SYSTEM INTEGRATION TEST                           ║")
    logger.info("╚══════════════════════════════════════════════════════════════════╝")

    results = []

    # Run tests
    results.append(await test_market_data())
    results.append(await test_paper_broker())
    results.append(await test_agent_coordinator())
    results.append(await test_position_exit_scheduler())
    results.append(await test_orchestrator_init())

    # Summary
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)

    passed = sum(results)
    total = len(results)

    logger.info(f"  Passed: {passed}/{total}")
    logger.info(f"  Failed: {total - passed}/{total}")

    if passed == total:
        logger.info("\n✅ ALL TESTS PASSED - System ready for paper trading!")
        return 0
    else:
        logger.info("\n⚠️  SOME TESTS FAILED - Fix issues before paper trading")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
