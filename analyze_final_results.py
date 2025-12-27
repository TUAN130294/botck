#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analyze final results and identify PASSED stocks"""

import pandas as pd
from pathlib import Path
import glob

# Find latest backtest results
backtest_files = sorted(glob.glob('backtest_results_simple_*.csv'))
if not backtest_files:
    print("No backtest results found!")
    exit(1)

latest_backtest = backtest_files[-1]
print(f"Loading: {latest_backtest}")

df = pd.read_csv(latest_backtest)

# Filter PASSED stocks (Sharpe > 1.5 AND Win > 50%)
passed = df[(df['sharpe_ratio'] > 1.5) & (df['win_rate'] > 0.50)].copy()
passed = passed.sort_values('sharpe_ratio', ascending=False)

print("\n" + "="*80)
print(f"FINAL RESULTS - PASSED STOCKS")
print("="*80)
print(f"\nTotal stocks backtested: {len(df)}")
print(f"PASSED stocks: {len(passed)} ({len(passed)/len(df)*100:.1f}%)")

if len(passed) > 0:
    print(f"\nTop 20 PASSED stocks:")
    print("-"*80)
    print(f"{'Symbol':<8} {'Sharpe':>8} {'Return':>10} {'Win%':>8} {'Trades':>8}")
    print("-"*80)
    for i, row in passed.head(20).iterrows():
        print(f"{row['symbol']:<8} {row['sharpe_ratio']:>8.2f} {row['total_return']:>9.2f}% {row['win_rate']*100:>7.1f}% {row['num_trades']:>8.0f}")

    # Save PASSED stocks list
    with open('PASSED_STOCKS.txt', 'w') as f:
        for symbol in passed['symbol']:
            f.write(f"{symbol}\n")

    print(f"\n✓ Saved PASSED stocks to: PASSED_STOCKS.txt")

    # Statistics
    print(f"\n" + "="*80)
    print("PORTFOLIO STATISTICS")
    print("="*80)
    print(f"Average Sharpe:    {passed['sharpe_ratio'].mean():>8.2f}")
    print(f"Average Return:    {passed['total_return'].mean():>7.2f}%/year")
    print(f"Average Win Rate:  {passed['win_rate'].mean()*100:>7.1f}%")
    print(f"Total trades:      {passed['num_trades'].sum():>8.0f}")

    # By sector (if available)
    print(f"\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print(f"1. Review PASSED_STOCKS.txt ({len(passed)} stocks)")
    print(f"2. Setup paper trading with top 10-15 stocks")
    print(f"3. Start with smallest positions first")
    print(f"4. Monitor daily and adjust")

else:
    print("\n✗ No stocks passed criteria (Sharpe>1.5 AND Win>50%)!")
    print("Consider:")
    print("  - Lowering threshold")
    print("  - Training more stocks")
    print("  - Checking data quality")

print("\n" + "="*80)
print("ANALYSIS COMPLETE!")
print("="*80)
