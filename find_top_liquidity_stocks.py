#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Find Top Liquidity Stocks
==========================
Identify stocks that account for 80% of market trading volume
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

def calculate_avg_liquidity(symbol, data_dir='data/historical'):
    """Calculate average liquidity for a stock"""
    try:
        # Skip indices and invalid symbols
        skip_symbols = ['VNINDEX', 'VN30', 'HNX', 'UPCOM', 'VN30F1M', 'VN30F2M',
                        'VN30_3Y', 'POPULAR_3Y', 'VN100', 'VNFIN', 'VNALL']

        # Skip if in skip list or contains underscore
        if symbol in skip_symbols or '_' in symbol:
            return None

        # Only accept 3-letter stocks and some valid 4-letter ones
        if len(symbol) > 4:
            return None

        data_file = Path(data_dir) / f"{symbol}.parquet"
        if not data_file.exists():
            return None

        df = pd.read_parquet(data_file)

        # Get last 6 months data
        if len(df) > 120:
            df = df.tail(120)

        # Calculate average daily volume
        avg_volume = df['volume'].mean()

        # Calculate average daily value (volume * close)
        avg_value = (df['volume'] * df['close']).mean()

        return {
            'symbol': symbol,
            'avg_volume': avg_volume,
            'avg_value': avg_value,
            'days': len(df)
        }
    except Exception as e:
        return None

def find_top_liquidity_stocks(data_dir='data/historical', target_pct=0.80):
    """Find stocks that account for target_pct of market volume"""

    print("="*80)
    print("FINDING TOP LIQUIDITY STOCKS")
    print("="*80)
    print(f"Target: Top stocks accounting for {target_pct*100:.0f}% of market volume\n")

    # Get all stock files
    data_path = Path(data_dir)
    stock_files = list(data_path.glob("*.parquet"))

    print(f"Total stocks available: {len(stock_files)}")
    print("Calculating liquidity metrics...\n")

    # Calculate liquidity for all stocks
    liquidity_data = []
    for i, stock_file in enumerate(stock_files, 1):
        symbol = stock_file.stem

        if i % 100 == 0:
            print(f"Processed {i}/{len(stock_files)} stocks...")

        result = calculate_avg_liquidity(symbol, data_dir)
        if result:
            liquidity_data.append(result)

    print(f"\nSuccessfully processed {len(liquidity_data)} stocks")

    # Create DataFrame
    df = pd.DataFrame(liquidity_data)

    # Sort by average value (volume * price)
    df = df.sort_values('avg_value', ascending=False).reset_index(drop=True)

    # Calculate cumulative percentage
    total_value = df['avg_value'].sum()
    df['value_pct'] = df['avg_value'] / total_value * 100
    df['cumulative_pct'] = df['value_pct'].cumsum()

    # Find stocks that account for target_pct
    top_stocks = df[df['cumulative_pct'] <= target_pct * 100]

    # Add one more stock to exceed the threshold
    if len(top_stocks) < len(df):
        top_stocks = df.iloc[:len(top_stocks) + 1]

    print("\n" + "="*80)
    print(f"TOP {len(top_stocks)} STOCKS (Accounting for {top_stocks['cumulative_pct'].iloc[-1]:.1f}% of market)")
    print("="*80)
    print(f"\n{'Rank':<6} {'Symbol':<8} {'Avg Volume':>15} {'Avg Value':>15} {'Value %':>10} {'Cum %':>10}")
    print("-"*80)

    for i, row in top_stocks.head(50).iterrows():
        print(f"{i+1:<6} {row['symbol']:<8} {row['avg_volume']:>15,.0f} "
              f"{row['avg_value']:>15,.0f} {row['value_pct']:>9.2f}% {row['cumulative_pct']:>9.2f}%")

    if len(top_stocks) > 50:
        print(f"\n... and {len(top_stocks) - 50} more stocks")

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total stocks analyzed:        {len(df):>10,}")
    print(f"Top stocks (80% coverage):    {len(top_stocks):>10,}")
    print(f"Actual coverage:              {top_stocks['cumulative_pct'].iloc[-1]:>9.2f}%")
    print(f"Average volume (top stocks):  {top_stocks['avg_volume'].mean():>10,.0f}")
    print(f"Average value (top stocks):   {top_stocks['avg_value'].mean():>10,.0f} VND")

    # Save results
    output_file = f"top_liquidity_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    top_stocks.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\nResults saved to: {output_file}")

    # Save symbol list for training
    symbols_file = "top_liquidity_symbols.txt"
    with open(symbols_file, 'w') as f:
        for symbol in top_stocks['symbol']:
            f.write(f"{symbol}\n")
    print(f"Symbol list saved to: {symbols_file}")

    # VN30 comparison
    vn30_stocks = ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB',
                   'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SSI', 'STB',
                   'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB',
                   'VRE', 'BCG', 'PDR']

    vn30_in_top = [s for s in vn30_stocks if s in top_stocks['symbol'].values]

    print("\n" + "="*80)
    print("VN30 COMPARISON")
    print("="*80)
    print(f"VN30 stocks in top liquidity: {len(vn30_in_top)}/30")
    print(f"Coverage: {len(vn30_in_top)/30*100:.1f}%")

    if len(vn30_in_top) < 30:
        missing = [s for s in vn30_stocks if s not in top_stocks['symbol'].values]
        print(f"\nMissing VN30 stocks: {', '.join(missing)}")

    return top_stocks

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Find top liquidity stocks')
    parser.add_argument('--target', type=float, default=0.80,
                        help='Target coverage percentage (default: 0.80 = 80%%)')
    parser.add_argument('--data-dir', type=str, default='data/historical',
                        help='Data directory (default: data/historical)')

    args = parser.parse_args()

    top_stocks = find_top_liquidity_stocks(
        data_dir=args.data_dir,
        target_pct=args.target
    )

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("1. Review top_liquidity_stocks_*.csv")
    print("2. Train models:")
    print("   python train_top_liquidity.py")
    print("3. Backtest:")
    print("   python backtest_simple.py --symbols-file top_liquidity_symbols.txt")
    print("\n")
