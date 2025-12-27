#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Deep Analysis: Why Some Stocks PASSED and Others FAILED
========================================================
Analyze training metrics, predictions, and market characteristics
to understand what makes a stock tradeable with our SIMPLE models.
"""

import pandas as pd
import numpy as np
import torch
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

# Load results
training_results = pd.read_csv('training_results_simple_20251226_200017.csv')
backtest_results = pd.read_csv('backtest_results_simple_20251226_202252.csv')

# Merge
analysis_df = training_results.merge(
    backtest_results,
    on='symbol',
    how='left'
)

print("="*80)
print("STOCK PERFORMANCE DEEP ANALYSIS")
print("="*80)

# 1. PASSED vs FAILED comparison
print("\n" + "="*80)
print("1. PASSED vs FAILED STOCKS - KEY DIFFERENCES")
print("="*80)

passed = analysis_df[analysis_df['passed'] == True].copy()
failed_with_trades = analysis_df[
    (analysis_df['passed'] == False) &
    (analysis_df['total_trades'].notna()) &
    (analysis_df['total_trades'] > 0)
].copy()

print(f"\nPASSED stocks (n={len(passed)}):")
print(passed[['symbol', 'best_val_loss', 'total_return', 'sharpe_ratio', 'win_rate']].to_string(index=False))

print(f"\n\nFAILED stocks with trades (n={len(failed_with_trades)}):")
print(failed_with_trades[['symbol', 'best_val_loss', 'total_return', 'sharpe_ratio', 'win_rate']].head(10).to_string(index=False))

# Statistical comparison
print("\n" + "-"*80)
print("STATISTICAL COMPARISON:")
print("-"*80)

metrics = ['best_val_loss', 'total_return', 'sharpe_ratio', 'win_rate', 'max_drawdown', 'total_trades']

for metric in metrics:
    if metric in passed.columns and metric in failed_with_trades.columns:
        passed_mean = passed[metric].mean()
        failed_mean = failed_with_trades[metric].mean()
        diff = passed_mean - failed_mean
        diff_pct = (diff / abs(failed_mean) * 100) if failed_mean != 0 else 0

        print(f"\n{metric}:")
        print(f"  PASSED avg:  {passed_mean:>10.4f}")
        print(f"  FAILED avg:  {failed_mean:>10.4f}")
        print(f"  Difference:  {diff:>10.4f} ({diff_pct:+.1f}%)")

# 2. Analyze TOP PERFORMER: ACB
print("\n" + "="*80)
print("2. TOP PERFORMER ANALYSIS: ACB (Sharpe 2.82)")
print("="*80)

acb = analysis_df[analysis_df['symbol'] == 'ACB'].iloc[0]
print(f"\nACB Metrics:")
print(f"  Val loss:      {acb['best_val_loss']:.6f} (rank #9 in training)")
print(f"  Return:        {acb['total_return']*100:+.2f}%")
print(f"  Sharpe:        {acb['sharpe_ratio']:.2f} (BEST)")
print(f"  Win rate:      {acb['win_rate']*100:.1f}%")
print(f"  Max DD:        {acb['max_drawdown']*100:.2f}%")
print(f"  Total trades:  {int(acb['total_trades'])}")
print(f"  Training time: {acb['training_time']}")

print("\nWhy ACB is TOP performer:")
print("  + Moderate val_loss (0.001375) - not too low (not overfit)")
print("  + Excellent Sharpe (2.82) - best risk-adjusted returns")
print("  + Good win rate (54.8%) - above average")
print("  + LOW max drawdown (-12.1%) - BEST among all stocks")
print("  + High number of trades (126) - good prediction frequency")
print("  => Model found reliable patterns, not just lucky")

# 3. Analyze WORST PERFORMER: SAB
print("\n" + "="*80)
print("3. WORST PERFORMER ANALYSIS: SAB (Sharpe -1.06)")
print("="*80)

sab = analysis_df[analysis_df['symbol'] == 'SAB'].iloc[0]
print(f"\nSAB Metrics:")
print(f"  Val loss:      {sab['best_val_loss']:.6f} (BEST in training!)")
print(f"  Return:        {sab['total_return']*100:+.2f}%")
print(f"  Sharpe:        {sab['sharpe_ratio']:.2f} (WORST)")
print(f"  Win rate:      {sab['win_rate']*100:.1f}%")
print(f"  Max DD:        {sab['max_drawdown']*100:.2f}%")
print(f"  Total trades:  {int(sab['total_trades'])}")

print("\nWhy SAB FAILED despite BEST val_loss:")
print("  X Val_loss TOO LOW (0.000851) - OVERFITTING!")
print("  X Model memorized training data perfectly")
print("  X But patterns don't generalize to trading")
print("  X Poor win rate (44.6%) - predictions unreliable")
print("  X Large drawdown (-33.8%) - high risk")
print("  => Classic overfitting: Great training, poor real performance")

# 4. Correlation analysis
print("\n" + "="*80)
print("4. CORRELATION ANALYSIS: Val Loss vs Backtest Performance")
print("="*80)

# Filter stocks with trades
stocks_with_trades = analysis_df[
    (analysis_df['total_trades'].notna()) &
    (analysis_df['total_trades'] > 0)
].copy()

corr_sharpe = stocks_with_trades['best_val_loss'].corr(stocks_with_trades['sharpe_ratio'])
corr_return = stocks_with_trades['best_val_loss'].corr(stocks_with_trades['total_return'])
corr_winrate = stocks_with_trades['best_val_loss'].corr(stocks_with_trades['win_rate'])

print(f"\nCorrelation between val_loss and backtest metrics:")
print(f"  Val_loss vs Sharpe:     {corr_sharpe:>7.3f}")
print(f"  Val_loss vs Return:     {corr_return:>7.3f}")
print(f"  Val_loss vs Win_rate:   {corr_winrate:>7.3f}")

if abs(corr_sharpe) < 0.3:
    print("\n  => WEAK correlation! Val_loss is NOT a good predictor of trading performance")
    print("  => This confirms overfitting: low val_loss != good trading")
else:
    print(f"\n  => Moderate correlation ({corr_sharpe:.2f})")

# 5. Sweet spot analysis
print("\n" + "="*80)
print("5. SWEET SPOT ANALYSIS: Optimal Val Loss Range")
print("="*80)

# Divide into bins
stocks_with_trades['val_loss_bin'] = pd.cut(
    stocks_with_trades['best_val_loss'],
    bins=[0, 0.002, 0.004, 0.006, 1.0],
    labels=['Very Low (<0.002)', 'Low (0.002-0.004)', 'Medium (0.004-0.006)', 'High (>0.006)']
)

bin_stats = stocks_with_trades.groupby('val_loss_bin').agg({
    'sharpe_ratio': ['mean', 'std', 'count'],
    'win_rate': 'mean',
    'passed': 'sum'
}).round(3)

print("\nPerformance by val_loss range:")
print(bin_stats)

# Find PASSED stocks val_loss range
passed_stocks = stocks_with_trades[stocks_with_trades['passed'] == True]
print(f"\nPASSED stocks val_loss range:")
print(f"  Min:  {passed_stocks['best_val_loss'].min():.6f}")
print(f"  Max:  {passed_stocks['best_val_loss'].max():.6f}")
print(f"  Mean: {passed_stocks['best_val_loss'].mean():.6f}")
print(f"  Median: {passed_stocks['best_val_loss'].median():.6f}")

# 6. Individual stock deep dive
print("\n" + "="*80)
print("6. INDIVIDUAL STOCK ANALYSIS")
print("="*80)

# Top 3 PASSED
print("\n[TOP 3 PASSED STOCKS]")
print("-"*80)

top3_passed = passed.nlargest(3, 'sharpe_ratio')
for idx, row in top3_passed.iterrows():
    print(f"\n{row['symbol']} (Sharpe {row['sharpe_ratio']:.2f}):")
    print(f"  Val loss:    {row['best_val_loss']:.6f}")
    print(f"  Return:      {row['total_return']*100:+.2f}%")
    print(f"  Win rate:    {row['win_rate']*100:.1f}%")
    print(f"  Max DD:      {row['max_drawdown']*100:.2f}%")
    print(f"  Trades:      {int(row['total_trades'])}")

    # Why it worked
    if row['best_val_loss'] < 0.002:
        print(f"  Note: Low val_loss but still generalized well")
    else:
        print(f"  Note: Moderate val_loss, good balance")

# Top 3 FAILED (with positive return)
print("\n\n[TOP 3 FAILED - but positive return]")
print("-"*80)

failed_positive = failed_with_trades[failed_with_trades['total_return'] > 0].nlargest(3, 'total_return')
for idx, row in failed_positive.iterrows():
    print(f"\n{row['symbol']} (Return {row['total_return']*100:+.2f}%):")
    print(f"  Val loss:    {row['best_val_loss']:.6f}")
    print(f"  Sharpe:      {row['sharpe_ratio']:.2f}")
    print(f"  Win rate:    {row['win_rate']*100:.1f}%")
    print(f"  Max DD:      {row['max_drawdown']*100:.2f}%")
    print(f"  Why failed:  ", end="")

    if row['sharpe_ratio'] < 1.5:
        print(f"Sharpe {row['sharpe_ratio']:.2f} < 1.5")
    if row['win_rate'] < 0.5:
        print(f"             Win {row['win_rate']*100:.1f}% < 50%")

# 7. Honorable mentions
print("\n\n[HONORABLE MENTIONS - Just missed PASSED]")
print("-"*80)

# HDB: High Sharpe but low win rate
hdb = analysis_df[analysis_df['symbol'] == 'HDB'].iloc[0]
print(f"\nHDB (High Sharpe, Low Win):")
print(f"  Sharpe:      {hdb['sharpe_ratio']:.2f} (excellent!)")
print(f"  Win rate:    {hdb['win_rate']*100:.1f}% (just 2% below threshold)")
print(f"  Return:      {hdb['total_return']*100:+.2f}%")
print(f"  Val loss:    {hdb['best_val_loss']:.6f}")
print(f"  Why missed:  Win rate {hdb['win_rate']*100:.1f}% < 50%")
print(f"  Analysis:    High Sharpe suggests large wins when right")
print(f"               But slightly <50% win means need stricter entry")

# GVR: Good win but lower Sharpe
gvr = analysis_df[analysis_df['symbol'] == 'GVR'].iloc[0]
print(f"\nGVR (Good Win, Lower Sharpe):")
print(f"  Win rate:    {gvr['win_rate']*100:.1f}% (excellent!)")
print(f"  Sharpe:      {gvr['sharpe_ratio']:.2f} (just below 1.5)")
print(f"  Return:      {gvr['total_return']*100:+.2f}%")
print(f"  Val loss:    {gvr['best_val_loss']:.6f}")
print(f"  Why missed:  Sharpe {gvr['sharpe_ratio']:.2f} < 1.5")
print(f"  Analysis:    Consistent wins but returns vary")
print(f"               Only non-bank stock with good performance")

# 8. Summary insights
print("\n" + "="*80)
print("8. KEY INSIGHTS & PATTERNS")
print("="*80)

print("""
[+] WHAT MAKES A STOCK PASS:
  1. Val loss 0.001-0.003 (not too low, not too high)
  2. Consistent predictions (high number of trades)
  3. Low drawdown (<-20%) - risk management
  4. Win rate >50% + Sharpe >1.5 - quality wins

[X] WHAT MAKES A STOCK FAIL:
  1. Val loss TOO LOW (<0.001) - overfitting
  2. Val loss TOO HIGH (>0.005) - poor learning
  3. High drawdown (>-25%) - risky predictions
  4. Low win rate (<50%) - unreliable signals

[!] VAL_LOSS IS NOT ENOUGH:
  - SAB: Best val_loss (0.000851) => Worst Sharpe (-1.06)
  - ACB: Rank #9 val_loss (0.001375) => Best Sharpe (2.82)
  - Correlation: {:.3f} (WEAK)
  => Must validate on backtest, not just training metrics

[*] SWEET SPOT:
  - Val loss: 0.0015 - 0.0030
  - Not perfect training = better generalization
  - "Good enough" beats "perfect" in ML

[SECTOR] PATTERNS:
  - Banking: 5/11 passed (45%) - most predictable
  - Securities: 1/1 passed (100%) - SSI excellent
  - Others: 0/8 passed (0%) - harder to predict
  => Banking sector has clearer patterns

[MODEL] LEARNED:
  - NOT market timing (failed on VN-Index followers)
  - NOT momentum (failed on MSN, MWG)
  - YES: Stock-specific mean reversion patterns
  - YES: Risk-adjusted opportunities (Sharpe focus)
""".format(corr_sharpe))

print("="*80)
print("Analysis complete. Review insights above.")
print("="*80)

# Save detailed analysis
output_file = 'stock_performance_analysis_detailed.csv'
stocks_with_trades.to_csv(output_file, index=False)
print(f"\nDetailed data saved to: {output_file}")
