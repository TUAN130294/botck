# -*- coding: utf-8 -*-
"""
VN-QUANT Data Auto Updater
==========================
- Download all stocks from HOSE, HNX, UPCOM (~1600+ symbols)
- Schedule daily update at 5:30 PM after market close
- Incremental update - only fetch new data

Author: VN-QUANT Team
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import time
import schedule
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from vnstock import Vnstock
    VNSTOCK_AVAILABLE = True
except ImportError:
    VNSTOCK_AVAILABLE = False
    print("⚠️ vnstock not installed. Run: pip install vnstock")

# Directories
DATA_DIR = Path(__file__).parent / "data" / "historical"
LOG_DIR = Path(__file__).parent / "logs"


def ensure_dirs():
    """Create necessary directories"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_all_stock_symbols() -> dict:
    """
    Get ALL stock symbols from Vietnamese exchanges
    Returns dict with exchange as key and list of symbols as value
    """
    if not VNSTOCK_AVAILABLE:
        print("❌ vnstock not available")
        return {}
    
    try:
        stock = Vnstock().stock(symbol='VNM', source='VCI')
        
        # Get listing from all exchanges
        all_stocks = stock.listing.all_symbols()
        
        if all_stocks is not None and not all_stocks.empty:
            # Group by exchange
            result = {
                'HOSE': [],
                'HNX': [],
                'UPCOM': []
            }
            
            for _, row in all_stocks.iterrows():
                symbol = row.get('symbol', row.get('ticker', ''))
                exchange = row.get('exchange', row.get('organ_type', 'UNKNOWN'))
                
                if symbol:
                    if 'HO' in str(exchange).upper() or exchange == 'HOSE':
                        result['HOSE'].append(symbol)
                    elif 'HN' in str(exchange).upper() or exchange == 'HNX':
                        result['HNX'].append(symbol)
                    elif 'UP' in str(exchange).upper() or exchange == 'UPCOM':
                        result['UPCOM'].append(symbol)
            
            return result
    except Exception as e:
        print(f"Error getting stock list: {e}")
    
    return {}


def download_single_stock(symbol: str, years: int = 3, update_only: bool = False) -> bool:
    """
    Download or update data for a single stock
    
    Args:
        symbol: Stock ticker
        years: Years of history (for new downloads)
        update_only: If True, only download new data since last update
    
    Returns:
        bool: Success status
    """
    if not VNSTOCK_AVAILABLE:
        return False
    
    try:
        filepath = DATA_DIR / f"{symbol}.parquet"
        csv_path = DATA_DIR / f"{symbol}.csv"
        
        # Check if we're doing incremental update
        if update_only and (filepath.exists() or csv_path.exists()):
            # Load existing data
            if filepath.exists():
                existing = pd.read_parquet(filepath)
            else:
                existing = pd.read_csv(csv_path, parse_dates=['date'])
            
            # Get last date
            if 'date' in existing.columns:
                last_date = pd.to_datetime(existing['date']).max()
                start_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
        else:
            start_date = (datetime.now() - timedelta(days=years*365)).strftime('%Y-%m-%d')
            existing = None
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Skip if start > end (already up to date)
        if start_date >= end_date:
            return True
        
        # Fetch new data
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        df = stock.quote.history(start=start_date, end=end_date)
        
        if df is not None and not df.empty:
            # Normalize columns
            df.columns = [c.lower() for c in df.columns]
            if 'time' in df.columns:
                df = df.rename(columns={'time': 'date'})
            df['symbol'] = symbol
            
            # Merge with existing if update
            if existing is not None and not existing.empty:
                existing.columns = [c.lower() for c in existing.columns]
                df = pd.concat([existing, df], ignore_index=True)
                df = df.drop_duplicates(subset=['date'], keep='last')
            
            # Save
            df.to_parquet(filepath, index=False)
            return True
            
    except Exception as e:
        pass  # Silently fail for individual stocks
    
    return False


def download_all_stocks(years: int = 3, update_only: bool = False):
    """
    Download data for ALL stocks on all exchanges
    
    Args:
        years: Years of history
        update_only: If True, only update existing files
    """
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     VN-QUANT TOÀN SÀN DATA DOWNLOADER                    ║
║     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                                       ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    ensure_dirs()
    
    # Get all symbols
    print("📋 Đang lấy danh sách toàn sàn...")
    all_symbols = get_all_stock_symbols()
    
    if not all_symbols:
        print("❌ Không thể lấy danh sách cổ phiếu")
        return
    
    total = sum(len(v) for v in all_symbols.values())
    print(f"✅ Tìm thấy {total} mã cổ phiếu:")
    for exchange, symbols in all_symbols.items():
        print(f"   - {exchange}: {len(symbols)} mã")
    
    # Download by exchange
    success_count = 0
    fail_count = 0
    progress = 0
    
    for exchange, symbols in all_symbols.items():
        print(f"\n📥 Đang tải {exchange}...")
        
        for i, symbol in enumerate(symbols):
            progress += 1
            
            if download_single_stock(symbol, years, update_only):
                success_count += 1
                status = "✓"
            else:
                fail_count += 1
                status = "✗"
            
            # Progress every 50 stocks
            if progress % 50 == 0:
                print(f"   [{progress}/{total}] {success_count} OK, {fail_count} failed")
            
            time.sleep(0.3)  # Rate limiting
    
    # Summary
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     ✅ DOWNLOAD HOÀN TẤT                                  ║
╠══════════════════════════════════════════════════════════╣
║  Tổng mã: {total:>4}                                         ║
║  Thành công: {success_count:>4}                                      ║
║  Thất bại: {fail_count:>4}                                        ║
║  Thời gian: {datetime.now().strftime('%H:%M:%S')}                                     ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Save summary
    save_data_summary()


def daily_update():
    """Daily update job - runs at 5:30 PM"""
    print(f"\n🕐 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Bắt đầu cập nhật dữ liệu hàng ngày...")
    
    # Update existing files only
    download_all_stocks(years=1, update_only=True)
    
    # Log
    log_file = LOG_DIR / f"update_{datetime.now().strftime('%Y%m%d')}.log"
    with open(log_file, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - Daily update completed\n")


def save_data_summary():
    """Save summary of all data files"""
    ensure_dirs()
    
    summary = {
        "generated_at": datetime.now().isoformat(),
        "data_directory": str(DATA_DIR),
        "statistics": {
            "total_files": 0,
            "total_size_mb": 0,
            "oldest_data": None,
            "newest_data": None
        },
        "files": []
    }
    
    for file in DATA_DIR.glob("*.parquet"):
        file_info = {
            "name": file.name,
            "size_mb": round(file.stat().st_size / (1024 * 1024), 2),
            "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat()
        }
        summary["files"].append(file_info)
        summary["statistics"]["total_files"] += 1
        summary["statistics"]["total_size_mb"] += file_info["size_mb"]
    
    summary["statistics"]["total_size_mb"] = round(summary["statistics"]["total_size_mb"], 2)
    
    # Save
    summary_path = DATA_DIR / "data_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"📊 Summary saved: {summary_path}")


def run_scheduler():
    """Run the scheduler in background"""
    # Schedule daily update at 5:30 PM (Vietnam time)
    schedule.every().day.at("17:30").do(daily_update)
    
    print("""
╔══════════════════════════════════════════════════════════╗
║     VN-QUANT AUTO UPDATER - SCHEDULER STARTED            ║
╠══════════════════════════════════════════════════════════╣
║  ⏰ Cập nhật tự động: 17:30 hàng ngày                     ║
║  📁 Data directory: data/historical/                      ║
║  📋 Log directory: logs/                                  ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    while True:
        schedule.run_pending()
        time.sleep(60)


def start_scheduler_background():
    """Start scheduler in a background thread"""
    thread = threading.Thread(target=run_scheduler, daemon=True)
    thread.start()
    return thread


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='VN-QUANT Data Manager')
    parser.add_argument('--full', action='store_true', help='Download full history for all stocks')
    parser.add_argument('--update', action='store_true', help='Incremental update only')
    parser.add_argument('--scheduler', action='store_true', help='Run scheduler for daily updates')
    parser.add_argument('--years', type=int, default=3, help='Years of history (default: 3)')
    
    args = parser.parse_args()
    
    if args.scheduler:
        run_scheduler()
    elif args.full:
        download_all_stocks(years=args.years, update_only=False)
    elif args.update:
        download_all_stocks(years=1, update_only=True)
    else:
        # Default: show help and current status
        print("""
VN-QUANT Data Manager
=====================

Usage:
  python data_auto_updater.py --full      # Download all stocks (3 years)
  python data_auto_updater.py --update    # Update existing data only
  python data_auto_updater.py --scheduler # Run auto-update scheduler
  
Options:
  --years N   Set years of history (default: 3)
        """)
        
        # Show current status
        if DATA_DIR.exists():
            files = list(DATA_DIR.glob("*.parquet"))
            print(f"\n📊 Current data: {len(files)} files in {DATA_DIR}")
        else:
            print(f"\n⚠️ No data found. Run with --full to download.")


if __name__ == "__main__":
    main()
