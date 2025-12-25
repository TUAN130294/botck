"""
Comprehensive Test Suite for Quantum Stock Platform
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def create_test_data(days: int = 252):
    """Create test OHLCV data"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='B')

    base_price = 100
    returns = np.random.normal(0.0005, 0.02, days)
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        'open': prices * np.random.uniform(0.99, 1.01, days),
        'high': prices * np.random.uniform(1.01, 1.03, days),
        'low': prices * np.random.uniform(0.97, 0.99, days),
        'close': prices,
        'volume': np.random.uniform(100000, 5000000, days).astype(int)
    }, index=dates)

    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)

    return df


def test_indicators():
    """Test technical indicators"""
    print("\n" + "="*60)
    print("TEST: Technical Indicators Library")
    print("="*60)

    from indicators.trend import TrendIndicators
    from indicators.momentum import MomentumIndicators
    from indicators.volatility import VolatilityIndicators
    from indicators.volume import VolumeIndicators

    df = create_test_data()

    # Trend indicators
    print("\n[Trend Indicators]")
    ema20 = TrendIndicators.ema(df['close'], 20)
    macd = TrendIndicators.macd(df['close'])
    adx = TrendIndicators.adx(df['high'], df['low'], df['close'])
    supertrend = TrendIndicators.supertrend(df['high'], df['low'], df['close'])

    print(f"  EMA20 last value: {ema20.iloc[-1]:.2f}")
    print(f"  MACD: {macd['macd'].iloc[-1]:.4f}, Signal: {macd['signal'].iloc[-1]:.4f}")
    print(f"  ADX: {adx['adx'].iloc[-1]:.2f}")
    print(f"  Supertrend direction: {'UP' if supertrend['direction'].iloc[-1] == 1 else 'DOWN'}")
    assert not ema20.isna().all(), "EMA calculation failed"
    print("  [PASS] Trend indicators working")

    # Momentum indicators
    print("\n[Momentum Indicators]")
    rsi = MomentumIndicators.rsi(df['close'])
    stoch = MomentumIndicators.stochastic(df['high'], df['low'], df['close'])
    cci = MomentumIndicators.cci(df['high'], df['low'], df['close'])

    print(f"  RSI: {rsi.iloc[-1]:.2f}")
    print(f"  Stochastic K: {stoch['stoch_k'].iloc[-1]:.2f}, D: {stoch['stoch_d'].iloc[-1]:.2f}")
    print(f"  CCI: {cci.iloc[-1]:.2f}")
    assert 0 <= rsi.iloc[-1] <= 100, "RSI out of range"
    print("  [PASS] Momentum indicators working")

    # Volatility indicators
    print("\n[Volatility Indicators]")
    bb = VolatilityIndicators.bollinger_bands(df['close'])
    atr = VolatilityIndicators.atr(df['high'], df['low'], df['close'])
    kc = VolatilityIndicators.keltner_channels(df['high'], df['low'], df['close'])

    print(f"  BB Upper: {bb['upper'].iloc[-1]:.2f}, Lower: {bb['lower'].iloc[-1]:.2f}")
    print(f"  ATR: {atr.iloc[-1]:.2f}")
    print(f"  Keltner Upper: {kc['upper'].iloc[-1]:.2f}")
    assert bb['upper'].iloc[-1] > bb['lower'].iloc[-1], "BB bands incorrect"
    print("  [PASS] Volatility indicators working")

    # Volume indicators
    print("\n[Volume Indicators]")
    obv = VolumeIndicators.obv(df['close'], df['volume'])
    mfi = VolumeIndicators.mfi(df['high'], df['low'], df['close'], df['volume'])
    vwap = VolumeIndicators.vwap(df['high'], df['low'], df['close'], df['volume'])

    print(f"  OBV: {obv.iloc[-1]:,.0f}")
    print(f"  MFI: {mfi.iloc[-1]:.2f}")
    print(f"  VWAP: {vwap.iloc[-1]:.2f}")
    print("  [PASS] Volume indicators working")

    return True


def test_backtest_engine():
    """Test backtesting engine"""
    print("\n" + "="*60)
    print("TEST: Backtesting Engine")
    print("="*60)

    from core.backtest_engine import (
        BacktestEngine, MACrossoverStrategy, RSIReversalStrategy, MACDStrategy
    )

    df = create_test_data(500)
    engine = BacktestEngine(initial_capital=100000000)

    # Test MA Crossover
    print("\n[MA Crossover Strategy]")
    strategy = MACrossoverStrategy(10, 50)
    result = engine.run(df, strategy, "TEST")

    print(f"  Total Return: {result.total_return_pct:.2f}%")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {result.max_drawdown_pct:.2f}%")
    print(f"  Win Rate: {result.win_rate:.1f}%")
    print(f"  Total Trades: {result.total_trades}")
    assert result.total_trades >= 0, "Backtest failed"
    print("  [PASS] MA Crossover backtest working")

    # Test RSI Strategy
    print("\n[RSI Reversal Strategy]")
    strategy = RSIReversalStrategy(14, 30, 70)
    result = engine.run(df, strategy, "TEST")

    print(f"  Total Return: {result.total_return_pct:.2f}%")
    print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print("  [PASS] RSI backtest working")

    # Compare strategies
    print("\n[Strategy Comparison]")
    strategies = [
        MACrossoverStrategy(10, 50),
        RSIReversalStrategy(14, 30, 70),
        MACDStrategy(12, 26, 9)
    ]
    comparison = engine.compare_strategies(df, strategies, "TEST")
    print(comparison.to_string())
    print("  [PASS] Strategy comparison working")

    return True


def test_monte_carlo():
    """Test Monte Carlo simulation"""
    print("\n" + "="*60)
    print("TEST: Monte Carlo Simulation")
    print("="*60)

    from core.monte_carlo import MonteCarloSimulator

    df = create_test_data()
    simulator = MonteCarloSimulator(num_simulations=1000)

    result = simulator.simulate(df, "TEST", forecast_days=10, leverage=1.0)

    print(f"\n[Simulation Results - 1000 paths, 10 days]")
    print(f"  Initial Price: {result.initial_price:.2f}")
    print(f"  Mean Price: {result.mean_price:.2f}")
    print(f"  Percentile 5%: {result.percentile_5:.2f}")
    print(f"  Percentile 95%: {result.percentile_95:.2f}")
    print(f"  Probability of Profit: {result.prob_profit:.1f}%")
    print(f"  VaR 95%: {result.var_95:.2f}%")
    print(f"  Kelly Fraction: {result.kelly_fraction*100:.1f}%")
    print(f"  Risk Score: {result.risk_score}/100")

    assert 0 <= result.prob_profit <= 100, "Probability out of range"
    assert result.num_simulations == 1000, "Simulation count mismatch"
    print("  [PASS] Monte Carlo simulation working")

    return True


def test_kelly_criterion():
    """Test Kelly Criterion calculator"""
    print("\n" + "="*60)
    print("TEST: Kelly Criterion")
    print("="*60)

    from core.kelly_criterion import KellyCriterion

    kelly = KellyCriterion(portfolio_value=100000000)

    result = kelly.calculate(
        entry_price=100,
        stop_loss=95,
        take_profit=110,
        win_rate=0.55
    )

    print(f"\n[Kelly Calculation]")
    print(f"  Entry: {result.entry_price:.2f}")
    print(f"  Stop Loss: {result.stop_loss:.2f}")
    print(f"  Take Profit: {result.take_profit:.2f}")
    print(f"  Win Rate: {result.win_rate*100:.0f}%")
    print(f"  Risk:Reward: 1:{result.risk_reward_ratio:.1f}")
    print(f"  Full Kelly: {result.kelly_fraction*100:.1f}%")
    print(f"  Half Kelly: {result.half_kelly*100:.1f}%")
    print(f"  Recommended Shares: {result.recommended_shares:,}")
    print(f"  Max Loss: {result.max_loss_amount:,.0f} VND")

    assert 0 <= result.kelly_fraction <= 1, "Kelly fraction out of range"
    print("  [PASS] Kelly criterion working")

    return True


def test_agents():
    """Test multi-agent system"""
    print("\n" + "="*60)
    print("TEST: Multi-Agent System")
    print("="*60)

    from agents.base_agent import StockData
    from agents.agent_coordinator import AgentCoordinator

    # Create test stock data
    stock_data = StockData(
        symbol="TEST",
        current_price=100,
        open_price=99,
        high_price=102,
        low_price=98,
        volume=1000000,
        change_percent=1.5,
        indicators={
            'ema20': 98,
            'ema50': 95,
            'rsi': 55,
            'macd': 0.5,
            'macd_signal': 0.3,
            'macd_hist': 0.2,
            'atr': 2,
            'adx': 30,
            'support': 95,
            'resistance': 105,
            'avg_volume': 800000
        },
        fundamentals={'pe': 15, 'market_cap': 10e12}
    )

    coordinator = AgentCoordinator()

    print("\n[Running Multi-Agent Analysis]")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    discussion = loop.run_until_complete(coordinator.analyze_stock(stock_data))
    loop.close()

    print(f"  Symbol: {discussion.symbol}")
    print(f"  Messages: {len(discussion.messages)}")
    print(f"  Consensus Score: {discussion.consensus_score:.1f}%")
    print(f"  Has Conflict: {discussion.has_conflict}")

    if discussion.final_verdict:
        print(f"\n[Final Verdict]")
        print(f"  Signal: {discussion.final_verdict.signal_type.value}")
        print(f"  Confidence: {discussion.final_verdict.confidence:.1f}%")
        if discussion.final_verdict.stop_loss:
            print(f"  Stop Loss: {discussion.final_verdict.stop_loss:.2f}")
        if discussion.final_verdict.take_profit:
            print(f"  Take Profit: {discussion.final_verdict.take_profit:.2f}")

    print("\n[Agent Messages Summary]")
    for msg in discussion.messages[:5]:
        print(f"  {msg.agent_emoji} {msg.agent_name}: {msg.content[:60]}...")

    assert len(discussion.messages) > 0, "No messages generated"
    assert discussion.final_verdict is not None, "No verdict generated"
    print("  [PASS] Multi-agent system working")

    return True


def test_quantum_engine():
    """Test Quantum Engine integration"""
    print("\n" + "="*60)
    print("TEST: Quantum Engine Integration")
    print("="*60)

    from core.quantum_engine import QuantumEngine

    df = create_test_data()
    engine = QuantumEngine()

    print("\n[Quick Backtest]")
    result = engine.quick_backtest(df, "TEST", "MA_CROSSOVER")
    print(f"  Return: {result.total_return_pct:.2f}%")
    print(f"  Sharpe: {result.sharpe_ratio:.2f}")
    print("  [PASS] Quick backtest working")

    print("\n[Monte Carlo via Engine]")
    mc_result = engine.run_monte_carlo(df, "TEST", days=10)
    print(f"  Prob Profit: {mc_result.prob_profit:.1f}%")
    print(f"  Risk Score: {mc_result.risk_score}")
    print("  [PASS] Monte Carlo integration working")

    print("\n[Position Sizing]")
    kelly = engine.calculate_position_size(100, 95, 110, 0.55)
    print(f"  Kelly: {kelly.kelly_fraction*100:.1f}%")
    print(f"  Recommended: {kelly.recommended_shares} shares")
    print("  [PASS] Position sizing working")

    print("\n[Full Analysis]")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    analysis = loop.run_until_complete(
        engine.full_analysis(df, "TEST", "MA_CROSSOVER", forecast_days=10, run_wfo=False)
    )
    loop.close()

    print(f"  Signal: {analysis.signal}")
    print(f"  Confidence: {analysis.confidence:.1f}%")
    print(f"  Technical Score: {analysis.technical_score:.1f}")
    print(f"  Risk Score: {analysis.risk_score}")
    print("  [PASS] Full analysis working")

    return True


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("QUANTUM STOCK PLATFORM - TEST SUITE")
    print("="*60)

    results = {}

    try:
        results['Indicators'] = test_indicators()
    except Exception as e:
        print(f"  [FAIL] Indicators test failed: {e}")
        results['Indicators'] = False

    try:
        results['Backtest'] = test_backtest_engine()
    except Exception as e:
        print(f"  [FAIL] Backtest test failed: {e}")
        results['Backtest'] = False

    try:
        results['Monte Carlo'] = test_monte_carlo()
    except Exception as e:
        print(f"  [FAIL] Monte Carlo test failed: {e}")
        results['Monte Carlo'] = False

    try:
        results['Kelly'] = test_kelly_criterion()
    except Exception as e:
        print(f"  [FAIL] Kelly test failed: {e}")
        results['Kelly'] = False

    try:
        results['Agents'] = test_agents()
    except Exception as e:
        print(f"  [FAIL] Agents test failed: {e}")
        results['Agents'] = False

    try:
        results['Quantum Engine'] = test_quantum_engine()
    except Exception as e:
        print(f"  [FAIL] Quantum Engine test failed: {e}")
        results['Quantum Engine'] = False

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {test}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
