#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Visualization: Val Loss vs Backtest Performance
================================================
Create charts showing relationship between training and backtest metrics
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 10

# Load data
training = pd.read_csv('training_results_simple_20251226_200017.csv')
backtest = pd.read_csv('backtest_results_simple_20251226_202252.csv')

# Merge
df = training.merge(backtest, on='symbol', how='left')

# Filter stocks with trades
df_trades = df[df['total_trades'].notna()].copy()

print(f"Creating visualizations for {len(df_trades)} stocks with trades...")

# Create figure with subplots
fig = plt.figure(figsize=(16, 12))

# 1. Val Loss vs Sharpe Ratio (main plot)
ax1 = plt.subplot(2, 3, 1)
colors = ['green' if p else 'red' for p in df_trades['passed']]
scatter = ax1.scatter(df_trades['best_val_loss'], df_trades['sharpe_ratio'],
                     c=colors, s=100, alpha=0.6, edgecolors='black')

# Annotate stocks
for _, row in df_trades.iterrows():
    if row['passed'] or abs(row['sharpe_ratio']) > 1.5:
        ax1.annotate(row['symbol'],
                    (row['best_val_loss'], row['sharpe_ratio']),
                    fontsize=8, ha='right')

ax1.axhline(y=1.5, color='orange', linestyle='--', label='Sharpe threshold (1.5)')
ax1.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
ax1.axvline(x=0.002, color='blue', linestyle='--', alpha=0.5, label='Sweet spot start')
ax1.axvline(x=0.004, color='blue', linestyle='--', alpha=0.5, label='Sweet spot end')

ax1.set_xlabel('Val Loss (Training)')
ax1.set_ylabel('Sharpe Ratio (Backtest)')
ax1.set_title('Val Loss vs Sharpe Ratio\n(Green=PASSED, Red=FAILED)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Add correlation text
corr = df_trades['best_val_loss'].corr(df_trades['sharpe_ratio'])
ax1.text(0.05, 0.95, f'Correlation: {corr:.3f}',
         transform=ax1.transAxes, fontsize=10, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

# 2. Val Loss vs Return
ax2 = plt.subplot(2, 3, 2)
colors = ['green' if p else 'red' for p in df_trades['passed']]
ax2.scatter(df_trades['best_val_loss'], df_trades['total_return']*100,
           c=colors, s=100, alpha=0.6, edgecolors='black')

for _, row in df_trades.iterrows():
    if row['passed'] or row['total_return'] > 0.3:
        ax2.annotate(row['symbol'],
                    (row['best_val_loss'], row['total_return']*100),
                    fontsize=8, ha='right')

ax2.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
ax2.axvline(x=0.002, color='blue', linestyle='--', alpha=0.5)
ax2.axvline(x=0.004, color='blue', linestyle='--', alpha=0.5)
ax2.set_xlabel('Val Loss (Training)')
ax2.set_ylabel('Total Return (%)')
ax2.set_title('Val Loss vs Return')
ax2.grid(True, alpha=0.3)

corr = df_trades['best_val_loss'].corr(df_trades['total_return'])
ax2.text(0.05, 0.95, f'Correlation: {corr:.3f}',
         transform=ax2.transAxes, fontsize=10, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

# 3. Val Loss vs Win Rate
ax3 = plt.subplot(2, 3, 3)
colors = ['green' if p else 'red' for p in df_trades['passed']]
ax3.scatter(df_trades['best_val_loss'], df_trades['win_rate']*100,
           c=colors, s=100, alpha=0.6, edgecolors='black')

for _, row in df_trades.iterrows():
    if row['passed']:
        ax3.annotate(row['symbol'],
                    (row['best_val_loss'], row['win_rate']*100),
                    fontsize=8, ha='right')

ax3.axhline(y=50, color='orange', linestyle='--', label='Win threshold (50%)')
ax3.axvline(x=0.002, color='blue', linestyle='--', alpha=0.5)
ax3.axvline(x=0.004, color='blue', linestyle='--', alpha=0.5)
ax3.set_xlabel('Val Loss (Training)')
ax3.set_ylabel('Win Rate (%)')
ax3.set_title('Val Loss vs Win Rate')
ax3.legend()
ax3.grid(True, alpha=0.3)

corr = df_trades['best_val_loss'].corr(df_trades['win_rate'])
ax3.text(0.05, 0.95, f'Correlation: {corr:.3f}',
         transform=ax3.transAxes, fontsize=10, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

# 4. Val Loss Distribution by Pass Status
ax4 = plt.subplot(2, 3, 4)
passed = df_trades[df_trades['passed'] == True]['best_val_loss']
failed = df_trades[df_trades['passed'] == False]['best_val_loss']

bins = np.linspace(0, 0.009, 20)
ax4.hist(passed, bins=bins, alpha=0.7, color='green', label=f'PASSED (n={len(passed)})')
ax4.hist(failed, bins=bins, alpha=0.7, color='red', label=f'FAILED (n={len(failed)})')
ax4.axvline(x=0.002, color='blue', linestyle='--', alpha=0.5, label='Sweet spot')
ax4.axvline(x=0.004, color='blue', linestyle='--', alpha=0.5)
ax4.set_xlabel('Val Loss')
ax4.set_ylabel('Count')
ax4.set_title('Val Loss Distribution\n(PASSED vs FAILED)')
ax4.legend()
ax4.grid(True, alpha=0.3)

# 5. Sharpe by Val Loss Range
ax5 = plt.subplot(2, 3, 5)
df_trades['val_loss_bin'] = pd.cut(
    df_trades['best_val_loss'],
    bins=[0, 0.002, 0.004, 0.006, 1.0],
    labels=['<0.002', '0.002-0.004', '0.004-0.006', '>0.006']
)

bin_sharpe = df_trades.groupby('val_loss_bin')['sharpe_ratio'].mean()
bin_count = df_trades.groupby('val_loss_bin').size()

bars = ax5.bar(range(len(bin_sharpe)), bin_sharpe.values, alpha=0.7)
bars[1].set_color('green')  # Highlight sweet spot
ax5.axhline(y=1.5, color='orange', linestyle='--', label='Sharpe threshold')
ax5.set_xticks(range(len(bin_sharpe)))
ax5.set_xticklabels(bin_sharpe.index)
ax5.set_ylabel('Average Sharpe Ratio')
ax5.set_title('Average Sharpe by Val Loss Range')
ax5.legend()
ax5.grid(True, alpha=0.3)

# Add count labels
for i, (sharpe, count) in enumerate(zip(bin_sharpe.values, bin_count.values)):
    ax5.text(i, sharpe + 0.1, f'n={count}', ha='center', fontsize=8)

# 6. Pass Rate by Val Loss Range
ax6 = plt.subplot(2, 3, 6)
bin_passed = df_trades.groupby('val_loss_bin')['passed'].sum()
bin_total = df_trades.groupby('val_loss_bin').size()
pass_rate = (bin_passed / bin_total * 100).fillna(0)

bars = ax6.bar(range(len(pass_rate)), pass_rate.values, alpha=0.7)
bars[1].set_color('green')  # Highlight sweet spot
ax6.set_xticks(range(len(pass_rate)))
ax6.set_xticklabels(pass_rate.index)
ax6.set_ylabel('Pass Rate (%)')
ax6.set_title('Pass Rate by Val Loss Range')
ax6.grid(True, alpha=0.3)

# Add labels
for i, (rate, passed, total) in enumerate(zip(pass_rate.values, bin_passed.values, bin_total.values)):
    ax6.text(i, rate + 2, f'{int(passed)}/{int(total)}', ha='center', fontsize=8)

plt.tight_layout()

# Save figure
output_file = 'val_loss_vs_backtest_analysis.png'
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\nVisualization saved to: {output_file}")

# Create second figure: Individual stock comparison
fig2, axes = plt.subplots(2, 2, figsize=(14, 10))

# Rank comparison: Val Loss Rank vs Sharpe Rank
ax1 = axes[0, 0]
df_trades['val_loss_rank'] = df_trades['best_val_loss'].rank()
df_trades['sharpe_rank'] = df_trades['sharpe_ratio'].rank(ascending=False)

colors = ['green' if p else 'red' for p in df_trades['passed']]
ax1.scatter(df_trades['val_loss_rank'], df_trades['sharpe_rank'],
           c=colors, s=100, alpha=0.6, edgecolors='black')

# Annotate key stocks
key_stocks = ['ACB', 'SAB', 'VCB', 'SSI', 'STB', 'MBB']
for _, row in df_trades.iterrows():
    if row['symbol'] in key_stocks:
        ax1.annotate(row['symbol'],
                    (row['val_loss_rank'], row['sharpe_rank']),
                    fontsize=9, ha='right', fontweight='bold')

ax1.plot([1, 20], [1, 20], 'k--', alpha=0.3, label='Perfect correlation')
ax1.set_xlabel('Val Loss Rank (1=best training)')
ax1.set_ylabel('Sharpe Rank (1=best backtest)')
ax1.set_title('Rank Comparison: Training vs Backtest\n(If correlated, points would be on diagonal)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Top/Bottom performers
ax2 = axes[0, 1]
df_sorted = df_trades.sort_values('sharpe_ratio', ascending=False)
top_bottom = pd.concat([df_sorted.head(8), df_sorted.tail(4)])

y_pos = np.arange(len(top_bottom))
colors_bar = ['green' if s > 1.5 else 'orange' if s > 0 else 'red'
              for s in top_bottom['sharpe_ratio']]

ax2.barh(y_pos, top_bottom['sharpe_ratio'], color=colors_bar, alpha=0.7)
ax2.set_yticks(y_pos)
ax2.set_yticklabels([f"{row['symbol']} (vl:{row['best_val_loss']:.4f})"
                      for _, row in top_bottom.iterrows()], fontsize=8)
ax2.axvline(x=1.5, color='orange', linestyle='--', label='Threshold')
ax2.axvline(x=0, color='gray', linestyle='-', alpha=0.3)
ax2.set_xlabel('Sharpe Ratio')
ax2.set_title('Top/Bottom Performers\n(with their val_loss)')
ax2.legend()
ax2.grid(True, alpha=0.3, axis='x')

# Risk vs Return (with val_loss color coding)
ax3 = axes[1, 0]
scatter = ax3.scatter(df_trades['max_drawdown']*100, df_trades['total_return']*100,
                     c=df_trades['best_val_loss'], s=100, alpha=0.7,
                     cmap='RdYlGn_r', edgecolors='black')

for _, row in df_trades.iterrows():
    if row['passed']:
        ax3.annotate(row['symbol'],
                    (row['max_drawdown']*100, row['total_return']*100),
                    fontsize=8, ha='right', fontweight='bold')

ax3.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
ax3.axvline(x=-20, color='orange', linestyle='--', alpha=0.5, label='DD threshold')
ax3.set_xlabel('Max Drawdown (%)')
ax3.set_ylabel('Total Return (%)')
ax3.set_title('Risk vs Return\n(Color = Val Loss, darker = higher)')
ax3.legend()
ax3.grid(True, alpha=0.3)

cbar = plt.colorbar(scatter, ax=ax3)
cbar.set_label('Val Loss', rotation=270, labelpad=15)

# Training time vs Performance
ax4 = axes[1, 1]
df_trades['training_seconds'] = pd.to_timedelta(df_trades['training_time']).dt.total_seconds()
colors = ['green' if p else 'red' for p in df_trades['passed']]

ax4.scatter(df_trades['training_seconds'], df_trades['sharpe_ratio'],
           c=colors, s=100, alpha=0.6, edgecolors='black')

for _, row in df_trades.iterrows():
    if row['passed']:
        ax4.annotate(row['symbol'],
                    (row['training_seconds'], row['sharpe_ratio']),
                    fontsize=8, ha='right')

ax4.axhline(y=1.5, color='orange', linestyle='--', label='Sharpe threshold')
ax4.set_xlabel('Training Time (seconds)')
ax4.set_ylabel('Sharpe Ratio')
ax4.set_title('Training Time vs Performance\n(No correlation expected)')
ax4.legend()
ax4.grid(True, alpha=0.3)

corr = df_trades['training_seconds'].corr(df_trades['sharpe_ratio'])
ax4.text(0.05, 0.95, f'Correlation: {corr:.3f}',
         transform=ax4.transAxes, fontsize=10, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()

# Save second figure
output_file2 = 'stock_comparison_charts.png'
plt.savefig(output_file2, dpi=150, bbox_inches='tight')
print(f"Stock comparison saved to: {output_file2}")

# Print summary statistics
print("\n" + "="*80)
print("VISUALIZATION SUMMARY")
print("="*80)

print("\nKey Findings:")
print(f"1. Val Loss vs Sharpe correlation: {df_trades['best_val_loss'].corr(df_trades['sharpe_ratio']):.3f} (WEAK!)")
print(f"2. Val Loss vs Return correlation: {df_trades['best_val_loss'].corr(df_trades['total_return']):.3f} (WEAK!)")
print(f"3. Val Loss vs Win Rate correlation: {df_trades['best_val_loss'].corr(df_trades['win_rate']):.3f} (WEAK!)")

print("\nSweet Spot (0.002-0.004):")
sweet_spot = df_trades[(df_trades['best_val_loss'] >= 0.002) & (df_trades['best_val_loss'] <= 0.004)]
print(f"  Stocks in range: {len(sweet_spot)}")
print(f"  PASSED: {sweet_spot['passed'].sum()}/{len(sweet_spot)} ({sweet_spot['passed'].sum()/len(sweet_spot)*100:.1f}%)")
print(f"  Avg Sharpe: {sweet_spot['sharpe_ratio'].mean():.2f}")

print("\nToo Low (<0.002):")
too_low = df_trades[df_trades['best_val_loss'] < 0.002]
print(f"  Stocks in range: {len(too_low)}")
print(f"  PASSED: {too_low['passed'].sum()}/{len(too_low)} ({too_low['passed'].sum()/len(too_low)*100:.1f}%)")
print(f"  Avg Sharpe: {too_low['sharpe_ratio'].mean():.2f}")

print("\nExamples of Mismatch (Val Loss Rank vs Sharpe Rank):")
df_trades['rank_diff'] = abs(df_trades['val_loss_rank'] - df_trades['sharpe_rank'])
mismatches = df_trades.nlargest(5, 'rank_diff')[['symbol', 'best_val_loss', 'val_loss_rank', 'sharpe_ratio', 'sharpe_rank', 'rank_diff']]
print(mismatches.to_string(index=False))

print("\n" + "="*80)
print("Charts created successfully!")
print("="*80)

plt.show()
