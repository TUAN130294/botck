#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Monitor Training Progress
"""
import os
import time
from pathlib import Path
from datetime import datetime

def count_models():
    models_dir = Path('models')
    if models_dir.exists():
        return len(list(models_dir.glob('*.pt')))
    return 0

def check_latest_csv(pattern):
    import glob
    csvs = sorted(glob.glob(pattern))
    if csvs:
        return csvs[-1]
    return None

def main():
    print("="*80)
    print("MONITORING PIPELINE PROGRESS".center(80))
    print("="*80)
    print(f"Started monitoring: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Press Ctrl+C to stop monitoring\n")

    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')

            print("="*80)
            print("PIPELINE PROGRESS MONITOR".center(80))
            print("="*80)
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            # Count models
            model_count = count_models()
            print(f"[MODELS] Trained models: {model_count}/102")

            if model_count > 0:
                progress = (model_count / 102) * 100
                bar_length = 50
                filled = int(bar_length * model_count / 102)
                bar = '=' * filled + '-' * (bar_length - filled)
                print(f"[PROGRESS] [{bar}] {progress:.1f}%")

            # Check training CSV
            training_csv = check_latest_csv('training_results_union_*.csv')
            if training_csv:
                print(f"\n[TRAINING CSV] {training_csv}")
            else:
                print(f"\n[TRAINING CSV] Not created yet")

            # Check backtest CSV
            backtest_csv = check_latest_csv('backtest_results_simple_*.csv')
            if backtest_csv:
                print(f"[BACKTEST CSV] {backtest_csv}")
            else:
                print(f"[BACKTEST CSV] Not created yet")

            # Check PASSED_STOCKS.txt
            if Path('PASSED_STOCKS.txt').exists():
                with open('PASSED_STOCKS.txt', 'r') as f:
                    passed = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                print(f"[PASSED STOCKS] {len(passed)} stocks")
            else:
                print(f"[PASSED STOCKS] Not created yet")

            print(f"\n{'='*80}")
            print("Refreshing in 10 seconds... (Ctrl+C to stop)")
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")

if __name__ == '__main__':
    main()
