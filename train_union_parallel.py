#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Train UNION(TOP62+VN100) Liquidity Stocks - PARALLEL GPU VERSION
====================================================
Train multiple stocks in parallel using GPU (RTX 5070 Ti)
Much faster than sequential training!
"""

import subprocess
import pandas as pd
from datetime import datetime
from pathlib import Path
import concurrent.futures
import time

def train_single_stock(symbol, index, total):
    """Train a single stock"""
    print(f"\n[{index}/{total}] Starting {symbol}...")

    start_time = time.time()

    try:
        # Run training with GPU
        result = subprocess.run(
            ['python', 'train_simple.py', '--symbol', symbol, '--epochs', '100', '--gpu'],
            capture_output=True,
            text=True,
            timeout=600  # 10 min timeout per stock
        )

        elapsed = time.time() - start_time

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

            print(f"[{index}/{total}] [OK] {symbol} DONE - Val loss: {val_loss:.6f if val_loss else 'N/A'} ({elapsed:.1f}s)")

            return {
                'symbol': symbol,
                'status': 'SUCCESS',
                'val_loss': val_loss,
                'time_seconds': elapsed
            }
        else:
            print(f"[{index}/{total}] [FAILED] {symbol} FAILED ({elapsed:.1f}s)")
            print(f"Error: {result.stderr[:200]}")

            return {
                'symbol': symbol,
                'status': 'FAILED',
                'val_loss': None,
                'time_seconds': elapsed
            }

    except subprocess.TimeoutExpired:
        print(f"[{index}/{total}] [TIMEOUT] {symbol} TIMEOUT (>10 min)")
        return {
            'symbol': symbol,
            'status': 'TIMEOUT',
            'val_loss': None,
            'time_seconds': 600
        }

    except Exception as e:
        print(f"[{index}/{total}] [ERROR] {symbol} ERROR: {str(e)}")
        return {
            'symbol': symbol,
            'status': 'ERROR',
            'val_loss': None,
            'time_seconds': 0
        }

def train_union_parallel(max_workers=4):
    """Train all UNION(TOP62+VN100) stocks in parallel

    Args:
        max_workers: Number of parallel training processes (default: 4)
                    RTX 5070 Ti has 16GB VRAM, can handle 4-6 parallel trainings
    """

    print("="*80)
    print("TRAINING UNION(TOP62+VN100) LIQUIDITY STOCKS - PARALLEL GPU MODE")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"GPU: NVIDIA GeForce RTX 5070 Ti")
    print(f"Parallel workers: {max_workers}")
    print("="*80)
    print()

    # Load symbol list
    symbols_file = 'union_top62_vn100.txt'
    with open(symbols_file, 'r') as f:
        symbols = [line.strip() for line in f if line.strip()]

    print(f"Total stocks to train: {len(symbols)}\n")

    # Training with parallel execution
    results = []
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(train_single_stock, symbol, i+1, len(symbols)): symbol
            for i, symbol in enumerate(symbols)
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)

    total_time = time.time() - start_time

    # Summary
    print("\n" + "="*80)
    print("TRAINING COMPLETE")
    print("="*80)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total time: {total_time/60:.1f} minutes ({total_time:.0f} seconds)")

    success_count = len([r for r in results if r['status'] == 'SUCCESS'])
    failed_count = len([r for r in results if r['status'] != 'SUCCESS'])

    print(f"\nTotal: {len(symbols)}")
    print(f"Success: {success_count} ({success_count/len(symbols)*100:.1f}%)")
    print(f"Failed: {failed_count}")

    if failed_count > 0:
        failed_symbols = [r['symbol'] for r in results if r['status'] != 'SUCCESS']
        print(f"\nFailed stocks: {', '.join(failed_symbols)}")

    # Average time per stock
    successful_times = [r['time_seconds'] for r in results if r['status'] == 'SUCCESS' and r['time_seconds'] > 0]
    if successful_times:
        avg_time = sum(successful_times) / len(successful_times)
        print(f"\nAverage time per stock: {avg_time:.1f} seconds")
        print(f"Speedup vs sequential: {len(symbols)*avg_time/total_time:.1f}x")

    # Save results
    results_df = pd.DataFrame(results)
    output_file = f"training_results_union_parallel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    results_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\nResults saved to: {output_file}")

    # Check models
    models_dir = Path('models')
    trained_models = list(models_dir.glob('*_stockformer_simple_best.pt'))
    print(f"\nTotal models in models/ directory: {len(trained_models)}")

    return results

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Train UNION(TOP62+VN100) stocks in parallel')
    parser.add_argument('--workers', type=int, default=4,
                        help='Number of parallel workers (default: 4, max recommended: 6 for RTX 5070 Ti)')

    args = parser.parse_args()

    # RTX 5070 Ti has 16GB VRAM, can handle 4-6 parallel trainings
    # Each training uses ~2-3GB VRAM
    max_workers = min(args.workers, 6)  # Cap at 6 to avoid OOM

    print(f"Using {max_workers} parallel workers")
    print("Note: If you see CUDA OOM errors, reduce --workers")
    print()

    results = train_union_parallel(max_workers=max_workers)
