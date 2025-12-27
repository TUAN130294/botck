#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Train TOP 62 Liquidity Stocks
==============================
Train models for top 62 stocks by liquidity (80% market coverage)
"""

import subprocess
import pandas as pd
from datetime import datetime
from pathlib import Path

def train_top62_stocks():
    """Train all TOP 62 stocks"""

    print("="*80)
    print("TRAINING TOP 62 LIQUIDITY STOCKS")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load symbol list
    symbols_file = 'top_liquidity_symbols.txt'
    with open(symbols_file, 'r') as f:
        symbols = [line.strip() for line in f if line.strip()]

    print(f"Total stocks to train: {len(symbols)}\n")

    # Training results
    results = []
    failed = []

    for i, symbol in enumerate(symbols, 1):
        print(f"\n[{i}/{len(symbols)}] Training {symbol}...")
        print("-"*80)

        try:
            # Run training with GPU
            result = subprocess.run(
                ['python', 'train_simple.py', '--symbol', symbol, '--epochs', '100', '--gpu'],
                capture_output=True,
                text=True,
                timeout=600  # 10 min timeout per stock
            )

            if result.returncode == 0:
                # Parse output for val_loss
                output_lines = result.stdout.split('\n')
                val_loss = None
                for line in output_lines:
                    if 'Best val_loss' in line:
                        try:
                            val_loss = float(line.split(':')[-1].strip())
                        except:
                            pass

                results.append({
                    'symbol': symbol,
                    'status': 'SUCCESS',
                    'val_loss': val_loss if val_loss else 'N/A'
                })
                print(f"[SUCCESS] {symbol} - Val loss: {val_loss if val_loss else 'N/A'}")
            else:
                failed.append(symbol)
                results.append({
                    'symbol': symbol,
                    'status': 'FAILED',
                    'val_loss': None
                })
                print(f"[FAILED] {symbol}")
                print(f"Error: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            failed.append(symbol)
            results.append({
                'symbol': symbol,
                'status': 'TIMEOUT',
                'val_loss': None
            })
            print(f"[TIMEOUT] {symbol} (>10 min)")

        except Exception as e:
            failed.append(symbol)
            results.append({
                'symbol': symbol,
                'status': 'ERROR',
                'val_loss': None
            })
            print(f"[ERROR] {symbol}: {str(e)}")

    # Summary
    print("\n" + "="*80)
    print("TRAINING COMPLETE")
    print("="*80)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nTotal: {len(symbols)}")
    print(f"Success: {len([r for r in results if r['status'] == 'SUCCESS'])}")
    print(f"Failed: {len(failed)}")

    if failed:
        print(f"\nFailed stocks: {', '.join(failed)}")

    # Save results
    results_df = pd.DataFrame(results)
    output_file = f"training_results_top62_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    results_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\nResults saved to: {output_file}")

    # Check models
    models_dir = Path('models')
    trained_models = list(models_dir.glob('*_stockformer_simple_best.pt'))
    print(f"\nTotal models in models/ directory: {len(trained_models)}")

    return results

if __name__ == '__main__':
    results = train_top62_stocks()
