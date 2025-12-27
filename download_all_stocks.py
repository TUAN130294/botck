# -*- coding: utf-8 -*-
"""
VN-QUANT Download Toàn Sàn
==========================
Download tất cả 1730+ mã cổ phiếu Việt Nam

Usage:
  python download_all_stocks.py           # Download tất cả (3 năm)
  python download_all_stocks.py --update  # Chỉ cập nhật data mới
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from vnstock import Vnstock
    VNSTOCK_AVAILABLE = True
except ImportError:
    VNSTOCK_AVAILABLE = False
    print("❌ vnstock not installed")

DATA_DIR = Path(__file__).parent / "data" / "historical"


def get_all_symbols():
    """Get all stock symbols from VCI"""
    if not VNSTOCK_AVAILABLE:
        return []
    
    try:
        stock = Vnstock().stock(symbol='VNM', source='VCI')
        df = stock.listing.all_symbols()
        if df is not None and 'symbol' in df.columns:
            return df['symbol'].tolist()
    except Exception as e:
        print(f"Error: {e}")
    
    return []


def download_stock(symbol: str, years: int = 3) -> bool:
    """Download data for a single stock"""
    try:
        filepath = DATA_DIR / f"{symbol}.parquet"
        
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        end = datetime.now()
        start = end - timedelta(days=years*365)
        
        df = stock.quote.history(
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d')
        )
        
        if df is not None and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            if 'time' in df.columns:
                df = df.rename(columns={'time': 'date'})
            df['symbol'] = symbol
            df.to_parquet(filepath, index=False)
            return True
    except:
        pass
    return False


def main():
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     VN-QUANT TOÀN SÀN DOWNLOADER                         ║
║     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                                       ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get all symbols
    print("📋 Lấy danh sách toàn sàn...")
    symbols = get_all_symbols()
    
    if not symbols:
        print("❌ Không thể lấy danh sách")
        return
    
    print(f"✅ Tìm thấy {len(symbols)} mã cổ phiếu")
    
    # Check already downloaded
    existing = set(f.stem for f in DATA_DIR.glob("*.parquet"))
    remaining = [s for s in symbols if s not in existing]
    
    print(f"📦 Đã có: {len(existing)} mã")
    print(f"📥 Cần tải thêm: {len(remaining)} mã")
    
    if len(remaining) == 0:
        print("✅ Đã đủ data toàn sàn!")
        return
    
    # Download remaining
    success = 0
    failed = 0
    
    for i, symbol in enumerate(remaining):
        if download_stock(symbol, years=3):
            success += 1
            mark = "✓"
        else:
            failed += 1
            mark = "✗"
        
        if (i + 1) % 50 == 0:
            print(f"   [{i+1}/{len(remaining)}] {symbol} {mark} | OK: {success}, Fail: {failed}")
        
        time.sleep(0.3)  # Rate limit
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     ✅ DOWNLOAD HOÀN TẤT                                  ║
╚══════════════════════════════════════════════════════════╝
    Thành công: {success}
    Thất bại: {failed}
    Tổng mã: {len(existing) + success}
    """)
    
    # Save summary
    summary = {
        "updated_at": datetime.now().isoformat(),
        "total_files": len(list(DATA_DIR.glob("*.parquet"))),
        "total_symbols_available": len(symbols)
    }
    with open(DATA_DIR / "data_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
