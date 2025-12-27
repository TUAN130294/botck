#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AUTONOMOUS FULL PIPELINE - Train → Backtest → Analyze
======================================================
Chạy toàn bộ quy trình tự động:
1. Training 102 stocks (GPU parallel)
2. Backtest all models
3. Analyze và tạo PASSED_STOCKS.txt

Chạy xuyên đêm - không cần intervention!
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

def print_header(text):
    """In header đẹp"""
    print("\n" + "="*80)
    print(text.center(80))
    print("="*80 + "\n")

def print_step(step_num, title):
    """In step header"""
    print(f"\n{'-'*80}")
    print(f"STEP {step_num}: {title}")
    print(f"{'-'*80}\n")

def run_command(cmd, description, timeout=None):
    """Chạy command và báo kết quả"""
    print(f"> {description}...")
    print(f"  Command: {' '.join(cmd)}\n")

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,  # Show output in real-time
            text=True,
            timeout=timeout
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            print(f"\n[SUCCESS] {description} - THANH CONG ({elapsed/60:.1f} phut)")
            return True
        else:
            print(f"\n[FAILED] {description} - THAT BAI (exit code: {result.returncode})")
            return False

    except subprocess.TimeoutExpired:
        print(f"\n[TIMEOUT] {description} - TIMEOUT (>{timeout/60:.0f} phut)")
        return False
    except Exception as e:
        print(f"\n[ERROR] {description} - LOI: {str(e)}")
        return False

def check_file_exists(filepath, description):
    """Kiểm tra file có tồn tại không"""
    if Path(filepath).exists():
        print(f"[OK] {description}: {filepath}")
        return True
    else:
        print(f"[NOT FOUND] {description}: {filepath}")
        return False

def main():
    """Main execution pipeline"""

    print_header("AUTONOMOUS FULL PIPELINE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: FULLY AUTONOMOUS")
    print(f"Expected time: ~70 minutes")
    print(f"\nPipeline: Train (31m) -> Backtest (30m) -> Analyze (2m)")

    overall_start = time.time()

    # ============================================================================
    # STEP 1: Verify union file exists
    # ============================================================================
    print_step(1, "Verify Union File Exists")

    if not check_file_exists('union_top62_vn100.txt', 'Union stocks list'):
        print("\n[WARNING] Creating union file...")
        if not run_command(['python', 'create_union_list.py'],
                          'Create union list', timeout=60):
            print("\n[FAILED] FAILED to create union list. Aborting.")
            sys.exit(1)

    # Count stocks
    with open('union_top62_vn100.txt', 'r') as f:
        stocks = [line.strip() for line in f if line.strip()]
    print(f"[OK] Total stocks: {len(stocks)}")

    # ============================================================================
    # STEP 2: Training (30-40 minutes)
    # ============================================================================
    print_step(2, f"Training {len(stocks)} Stocks with GPU Parallel (4 workers)")
    print(f"Expected time: ~{len(stocks) * 75 / 4 / 60:.0f} minutes")
    print(f"GPU: RTX 5070 Ti (16GB VRAM)")

    if not run_command(['python', 'train_union_parallel.py'],
                      'GPU Parallel Training', timeout=3600):
        print("\n[FAILED] TRAINING FAILED. Aborting pipeline.")
        sys.exit(1)

    # Check models created
    models_dir = Path('models')
    if models_dir.exists():
        model_files = list(models_dir.glob('*.pt'))
        print(f"[OK] Models created: {len(model_files)}/{len(stocks)}")

        if len(model_files) < len(stocks) * 0.9:  # At least 90%
            print(f"[WARNING] Only {len(model_files)}/{len(stocks)} models created")
            response = input("Continue to backtest? (y/n): ")
            if response.lower() != 'y':
                sys.exit(1)

    # ============================================================================
    # STEP 3: Backtest (30 minutes)
    # ============================================================================
    print_step(3, f"Backtest All {len(stocks)} Models")
    print(f"Expected time: ~30 minutes")
    print(f"Period: 2024-01-01 to 2024-12-31")

    if not run_command(['python', 'backtest_simple.py'],
                      'Backtest All Models', timeout=2400):
        print("\n[FAILED] BACKTEST FAILED. Continuing to analysis anyway...")

    # ============================================================================
    # STEP 4: Analyze Results (1-2 minutes)
    # ============================================================================
    print_step(4, "Analyze Results & Generate PASSED_STOCKS.txt")
    print(f"Filter: Sharpe > 1.5 AND Win Rate > 50%")

    if not run_command(['python', 'analyze_final_results.py'],
                      'Analyze Results', timeout=120):
        print("\n[FAILED] ANALYSIS FAILED.")
        sys.exit(1)

    # ============================================================================
    # FINAL VALIDATION
    # ============================================================================
    print_header("FINAL VALIDATION")

    all_ok = True

    # Check PASSED_STOCKS.txt
    if check_file_exists('PASSED_STOCKS.txt', 'PASSED stocks list'):
        with open('PASSED_STOCKS.txt', 'r') as f:
            passed = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"  -> PASSED stocks: {len(passed)}")

        if len(passed) > 0:
            print(f"\nTop 5 PASSED stocks:")
            for i, stock in enumerate(passed[:5], 1):
                print(f"   {i}. {stock}")
    else:
        all_ok = False

    # Check training results
    import glob
    training_csvs = sorted(glob.glob('training_results_union_*.csv'))
    if training_csvs:
        check_file_exists(training_csvs[-1], 'Training results CSV')
    else:
        print("[NOT FOUND] Training results CSV not found")
        all_ok = False

    # Check backtest results
    backtest_csvs = sorted(glob.glob('backtest_results_simple_*.csv'))
    if backtest_csvs:
        check_file_exists(backtest_csvs[-1], 'Backtest results CSV')
    else:
        print("[NOT FOUND] Backtest results CSV not found")
        all_ok = False

    # ============================================================================
    # SUMMARY
    # ============================================================================
    overall_time = time.time() - overall_start

    print_header("PIPELINE COMPLETED")
    print(f"Total time: {overall_time/60:.1f} minutes")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if all_ok:
        print(f"\nALL CHECKS PASSED!")
        print(f"\nOutput files:")
        print(f"   1. PASSED_STOCKS.txt - {len(passed) if 'passed' in locals() else '?'} profitable stocks")
        print(f"   2. {training_csvs[-1] if training_csvs else 'training_results_union_*.csv'}")
        print(f"   3. {backtest_csvs[-1] if backtest_csvs else 'backtest_results_simple_*.csv'}")
        print(f"   4. models/*.pt - {len(model_files) if 'model_files' in locals() else '?'} model files")

        print(f"\nNEXT STEPS:")
        print(f"   1. Review PASSED_STOCKS.txt")
        print(f"   2. Analyze top stocks by Sharpe ratio")
        print(f"   3. Setup paper trading portfolio")
        print(f"   4. Begin paper trading with 8 stocks")

        return 0
    else:
        print(f"\nWARNING: Some checks failed. Review output above.")
        return 1

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nWARNING: Pipeline interrupted by user (Ctrl+C)")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nERROR: UNEXPECTED ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
