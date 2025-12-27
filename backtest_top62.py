#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backtest TOP 62 Stocks
======================
Backtest all trained TOP 62 models
"""

import subprocess
from datetime import datetime

def backtest_top62():
    """Run backtest on TOP 62 stocks"""

    print("="*80)
    print("BACKTESTING TOP 62 STOCKS")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Run backtest
    result = subprocess.run(
        ['python', 'backtest_simple.py'],
        capture_output=False,
        text=True
    )

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    return result.returncode == 0

if __name__ == '__main__':
    success = backtest_top62()
    if success:
        print("\n✓ Backtest completed successfully!")
        print("\nNext steps:")
        print("1. Review backtest_results_simple_*.csv")
        print("2. Check PASSED stocks (Sharpe>1.5 AND Win>50%)")
        print("3. Start paper trading with top stocks")
    else:
        print("\n✗ Backtest failed!")
