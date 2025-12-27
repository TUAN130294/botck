#!/usr/bin/env python3
"""
Quick Test - Autonomous System
===============================
Test nhanh các components trước khi chạy full system

Run: python test_autonomous_quick.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

# Configure simple logger
logger.remove()
logger.add(sys.stdout, format="<level>{level: <8}</level> | {message}", level="INFO")


async def test_model_scanner():
    """Test 1: Model Prediction Scanner"""
    logger.info("=" * 60)
    logger.info("TEST 1: Model Prediction Scanner")
    logger.info("=" * 60)

    try:
        from quantum_stock.scanners.model_prediction_scanner import ModelPredictionScanner

        scanner = ModelPredictionScanner(scan_interval=1)

        # Test callback
        opportunities_found = []

        async def on_opportunity(pred):
            opportunities_found.append(pred)
            logger.success(
                f"✅ Opportunity: {pred.symbol} | "
                f"Return: {pred.expected_return_5d*100:.1f}% | "
                f"Confidence: {pred.confidence:.2f}"
            )

        scanner.add_opportunity_callback(on_opportunity)

        # Run one scan
        logger.info("Running single scan...")
        await scanner.scan_all_stocks()

        logger.info(f"Found {len(opportunities_found)} opportunities")
        logger.success("TEST 1: PASSED ✅\n")

        return len(opportunities_found) > 0

    except Exception as e:
        logger.error(f"TEST 1: FAILED ❌ - {e}\n")
        return False


async def test_news_scanner():
    """Test 2: News Alert Scanner"""
    logger.info("=" * 60)
    logger.info("TEST 2: News Alert Scanner")
    logger.info("=" * 60)

    try:
        from quantum_stock.scanners.news_alert_scanner import NewsAlertScanner

        scanner = NewsAlertScanner(scan_interval=1)

        # Create mock alert
        mock_alert = await scanner.create_mock_alert(
            symbol="ACB",
            headline="ACB được chấp thuận tăng vốn 50,000 tỷ",
            is_positive=True
        )

        logger.info(f"Mock alert created: {mock_alert.symbol}")
        logger.info(f"  Headline: {mock_alert.headline}")
        logger.info(f"  Sentiment: {mock_alert.sentiment:.2f}")
        logger.info(f"  Level: {mock_alert.alert_level}")

        logger.success("TEST 2: PASSED ✅\n")
        return True

    except Exception as e:
        logger.error(f"TEST 2: FAILED ❌ - {e}\n")
        return False


async def test_exit_scheduler():
    """Test 3: Position Exit Scheduler"""
    logger.info("=" * 60)
    logger.info("TEST 3: Position Exit Scheduler")
    logger.info("=" * 60)

    try:
        from quantum_stock.autonomous.position_exit_scheduler import (
            PositionExitScheduler,
            Position
        )
        from datetime import datetime, timedelta

        scheduler = PositionExitScheduler(check_interval=1)

        # Test callback
        exits = []

        async def on_exit(position, reason):
            exits.append((position.symbol, reason))
            logger.success(
                f"✅ Exit: {position.symbol} | "
                f"Reason: {reason} | "
                f"P&L: {position.unrealized_pnl_pct*100:+.2f}%"
            )

        scheduler.add_exit_callback(on_exit)

        # Add test position
        test_position = Position(
            symbol="TEST",
            quantity=100,
            avg_price=100,
            entry_date=datetime.now() - timedelta(days=3),  # T+3 (can sell)
            take_profit_pct=0.15,
            trailing_stop_pct=0.05,
            stop_loss_pct=-0.05
        )

        # Simulate price increase to trigger take profit
        test_position.current_price = 116  # +16% > +15% take profit
        test_position.update_price(116)

        scheduler.add_position(test_position)

        # Check once
        await scheduler.check_all_positions()

        logger.info(f"Exits triggered: {len(exits)}")
        logger.success("TEST 3: PASSED ✅\n")

        return len(exits) > 0

    except Exception as e:
        logger.error(f"TEST 3: FAILED ❌ - {e}\n")
        return False


async def test_orchestrator():
    """Test 4: Autonomous Orchestrator"""
    logger.info("=" * 60)
    logger.info("TEST 4: Autonomous Orchestrator")
    logger.info("=" * 60)

    try:
        from quantum_stock.autonomous.orchestrator import AutonomousOrchestrator

        orchestrator = AutonomousOrchestrator(
            paper_trading=True,
            initial_balance=100_000_000
        )

        logger.info(f"Orchestrator created")
        logger.info(f"  Paper trading: {orchestrator.paper_trading}")
        logger.info(f"  Initial balance: {orchestrator.broker.get_balance():,.0f} VND")

        status = orchestrator.get_status()
        logger.info(f"  Status: {status}")

        logger.success("TEST 4: PASSED ✅\n")
        return True

    except Exception as e:
        logger.error(f"TEST 4: FAILED ❌ - {e}\n")
        return False


async def check_prerequisites():
    """Check prerequisites"""
    logger.info("=" * 60)
    logger.info("CHECKING PREREQUISITES")
    logger.info("=" * 60)

    issues = []

    # Check models
    model_dir = Path("models")
    if not model_dir.exists():
        issues.append("❌ models/ directory not found")
    else:
        model_files = list(model_dir.glob("*_stockformer_simple_best.pt"))
        if len(model_files) < 8:
            issues.append(f"⚠️  Only {len(model_files)} models found (need 8+)")
        else:
            logger.success(f"✅ {len(model_files)} models found")

    # Check PASSED_STOCKS
    passed_file = Path("PASSED_STOCKS.txt")
    if not passed_file.exists():
        issues.append("❌ PASSED_STOCKS.txt not found")
    else:
        with open(passed_file) as f:
            stocks = [l.strip() for l in f if l.strip() and not l.startswith('#')]
        if len(stocks) < 8:
            issues.append(f"⚠️  Only {len(stocks)} PASSED stocks")
        else:
            logger.success(f"✅ {len(stocks)} PASSED stocks: {', '.join(stocks)}")

    # Check data
    data_dir = Path("data/historical")
    if not data_dir.exists():
        issues.append("❌ data/historical/ directory not found")
    else:
        data_files = list(data_dir.glob("*.parquet"))
        if len(data_files) < 8:
            issues.append(f"⚠️  Only {len(data_files)} data files")
        else:
            logger.success(f"✅ {len(data_files)} data files found")

    # Check dependencies
    try:
        import fastapi
        import uvicorn
        import websockets
        logger.success("✅ Web dependencies installed")
    except ImportError as e:
        issues.append(f"❌ Missing dependency: {e.name}")

    if issues:
        logger.warning("\nISSUES FOUND:")
        for issue in issues:
            logger.warning(f"  {issue}")
        logger.warning("\nFix these before running full system")
        return False
    else:
        logger.success("\n✅ ALL PREREQUISITES OK\n")
        return True


async def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("╔═══════════════════════════════════════════════════════════╗")
    logger.info("║     AUTONOMOUS TRADING SYSTEM - QUICK TEST               ║")
    logger.info("╚═══════════════════════════════════════════════════════════╝")
    logger.info("\n")

    # Check prerequisites first
    prereq_ok = await check_prerequisites()

    if not prereq_ok:
        logger.error("\n❌ Prerequisites check failed")
        logger.error("Please fix the issues above before running tests\n")
        return

    # Run tests
    results = {}

    results['scanner'] = await test_model_scanner()
    results['news'] = await test_news_scanner()
    results['exit'] = await test_exit_scheduler()
    results['orchestrator'] = await test_orchestrator()

    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    all_passed = all(results.values())

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name.upper():20s}: {status}")

    logger.info("")

    if all_passed:
        logger.success("╔═══════════════════════════════════════════════════════════╗")
        logger.success("║  🎉 ALL TESTS PASSED - READY TO RUN!                     ║")
        logger.success("╚═══════════════════════════════════════════════════════════╝")
        logger.info("")
        logger.info("Run the system:")
        logger.info("  python run_autonomous_paper_trading.py")
        logger.info("")
        logger.info("Then open:")
        logger.info("  http://localhost:8000/autonomous")
        logger.info("")
    else:
        logger.error("╔═══════════════════════════════════════════════════════════╗")
        logger.error("║  ❌ SOME TESTS FAILED - FIX BEFORE RUNNING                ║")
        logger.error("╚═══════════════════════════════════════════════════════════╝")
        logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
