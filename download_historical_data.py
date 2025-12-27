# -*- coding: utf-8 -*-
"""
Historical Data Downloader - 3 Year Data for Backtest
======================================================
Downloads historical stock data from VCI via vnstock for backtesting.

Supports:
- VN30 stocks (30 blue chips)
- Full VN-INDEX
- Custom symbol lists
- 3-year historical data
- Saves to Parquet/CSV for fast loading
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import time

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from vnstock import Vnstock
    VNSTOCK_AVAILABLE = True
except ImportError:
    VNSTOCK_AVAILABLE = False
    print("⚠️ vnstock not installed. Run: pip install vnstock")

# VN30 Components (as of 2024)
VN30_SYMBOLS = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
    'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SSB', 'SSI', 'STB', 'TCB',
    'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'
]

# Additional popular stocks
POPULAR_SYMBOLS = [
    'DGC', 'PNJ', 'REE', 'DXG', 'KDH', 'NLG', 'PDR', 'VCI', 'HCM', 'VND',
    'SHS', 'BSI', 'AGG', 'DPM', 'DCM', 'PVD', 'PVS', 'PVT', 'GMD', 'HAG'
]

# Data directory
DATA_DIR = Path(__file__).parent / "data" / "historical"


def ensure_data_dir():
    """Create data directory if not exists"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def download_stock_history(symbol: str, years: int = 3) -> pd.DataFrame:
    """
    Download historical data for a single stock
    
    Args:
        symbol: Stock ticker
        years: Number of years to download
    
    Returns:
        DataFrame with OHLCV data
    """
    if not VNSTOCK_AVAILABLE:
        print(f"⚠️ Cannot download {symbol}: vnstock not available")
        return pd.DataFrame()
    
    try:
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        end = datetime.now()
        start = end - timedelta(days=years * 365)
        
        df = stock.quote.history(
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d')
        )
        
        if df is not None and not df.empty:
            # Standardize column names
            df.columns = [c.lower() for c in df.columns]
            if 'time' in df.columns:
                df = df.rename(columns={'time': 'date'})
            
            # Add symbol column
            df['symbol'] = symbol
            
            # Ensure date is datetime
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            
            print(f"✅ {symbol}: {len(df)} records ({df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')})")
            return df
        else:
            print(f"❌ {symbol}: No data returned")
            return pd.DataFrame()
            
    except Exception as e:
        print(f"❌ {symbol}: Error - {str(e)[:50]}")
        return pd.DataFrame()


def download_all_vn30(years: int = 3) -> pd.DataFrame:
    """Download data for all VN30 stocks"""
    print(f"\n{'='*60}")
    print(f"📥 DOWNLOADING VN30 STOCKS ({years} YEARS)")
    print(f"{'='*60}\n")
    
    all_data = []
    
    for i, symbol in enumerate(VN30_SYMBOLS):
        print(f"[{i+1}/{len(VN30_SYMBOLS)}] ", end="")
        df = download_stock_history(symbol, years)
        if not df.empty:
            all_data.append(df)
        time.sleep(0.5)  # Rate limiting
    
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        print(f"\n✅ Total: {len(combined)} records for {len(all_data)} stocks")
        return combined
    
    return pd.DataFrame()


def download_index(index_symbol: str = 'VNINDEX', years: int = 3) -> pd.DataFrame:
    """Download index data"""
    print(f"\n📈 Downloading {index_symbol}...")
    return download_stock_history(index_symbol, years)


def save_to_parquet(df: pd.DataFrame, filename: str) -> str:
    """Save DataFrame to Parquet format (fast loading)"""
    ensure_data_dir()
    filepath = DATA_DIR / f"{filename}.parquet"
    
    try:
        df.to_parquet(filepath, index=False)
        size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"💾 Saved: {filepath} ({size_mb:.2f} MB)")
        return str(filepath)
    except Exception as e:
        # Fallback to CSV if Parquet fails
        csv_path = DATA_DIR / f"{filename}.csv"
        df.to_csv(csv_path, index=False)
        print(f"💾 Saved (CSV fallback): {csv_path}")
        return str(csv_path)


def save_to_csv(df: pd.DataFrame, filename: str) -> str:
    """Save DataFrame to CSV format"""
    ensure_data_dir()
    filepath = DATA_DIR / f"{filename}.csv"
    df.to_csv(filepath, index=False)
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"💾 Saved: {filepath} ({size_mb:.2f} MB)")
    return str(filepath)


def load_historical_data(filename: str) -> pd.DataFrame:
    """Load historical data from file"""
    parquet_path = DATA_DIR / f"{filename}.parquet"
    csv_path = DATA_DIR / f"{filename}.csv"
    
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    elif csv_path.exists():
        return pd.read_csv(csv_path, parse_dates=['date'])
    else:
        print(f"❌ File not found: {filename}")
        return pd.DataFrame()


def get_stock_data(symbol: str, days: int = 90) -> pd.DataFrame:
    """
    Get stock data - first try local cache, then download
    """
    # Try to load from local cache
    cache_file = DATA_DIR / f"{symbol.upper()}.parquet"
    csv_file = DATA_DIR / f"{symbol.upper()}.csv"
    
    if cache_file.exists():
        df = pd.read_parquet(cache_file)
        # Filter to requested days
        if 'date' in df.columns:
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df['date'] >= cutoff]
        return df
    elif csv_file.exists():
        df = pd.read_csv(csv_file, parse_dates=['date'])
        if 'date' in df.columns:
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df['date'] >= cutoff]
        return df
    
    # Download if not cached
    return download_stock_history(symbol, years=1)


def generate_data_summary() -> dict:
    """Generate summary of downloaded data"""
    ensure_data_dir()
    
    summary = {
        "generated_at": datetime.now().isoformat(),
        "data_directory": str(DATA_DIR),
        "files": []
    }
    
    for file in DATA_DIR.glob("*"):
        if file.is_file():
            summary["files"].append({
                "name": file.name,
                "size_mb": round(file.stat().st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(file.stat().st_mtime).isoformat()
            })
    
    # Save summary
    summary_path = DATA_DIR / "data_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    return summary


def main():
    """Main download function"""
    print("""
╔══════════════════════════════════════════════════════════╗
║     VN-QUANT HISTORICAL DATA DOWNLOADER                  ║
║     Preparing 3-Year Data for Walk-Forward Backtest      ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    if not VNSTOCK_AVAILABLE:
        print("❌ vnstock is not installed. Please run:")
        print("   pip install vnstock")
        return
    
    years = 3
    
    # 1. Download VN-INDEX
    print("\n" + "="*60)
    print("STEP 1: Downloading VN-INDEX")
    print("="*60)
    vnindex = download_index('VNINDEX', years)
    if not vnindex.empty:
        save_to_parquet(vnindex, 'VNINDEX')
    
    # 2. Download VN30 stocks
    print("\n" + "="*60)
    print("STEP 2: Downloading VN30 Stocks")
    print("="*60)
    vn30_data = download_all_vn30(years)
    if not vn30_data.empty:
        save_to_parquet(vn30_data, 'VN30_3Y')
        
        # Also save individual stock files
        for symbol in vn30_data['symbol'].unique():
            stock_df = vn30_data[vn30_data['symbol'] == symbol]
            save_to_parquet(stock_df, symbol)
    
    # 3. Download additional popular stocks
    print("\n" + "="*60)
    print("STEP 3: Downloading Popular Stocks")
    print("="*60)
    popular_data = []
    for i, symbol in enumerate(POPULAR_SYMBOLS):
        if symbol not in VN30_SYMBOLS:
            print(f"[{i+1}/{len(POPULAR_SYMBOLS)}] ", end="")
            df = download_stock_history(symbol, years)
            if not df.empty:
                popular_data.append(df)
                save_to_parquet(df, symbol)
            time.sleep(0.5)
    
    if popular_data:
        combined = pd.concat(popular_data, ignore_index=True)
        save_to_parquet(combined, 'POPULAR_3Y')
    
    # 4. Generate summary
    print("\n" + "="*60)
    print("STEP 4: Generating Data Summary")
    print("="*60)
    summary = generate_data_summary()
    
    print(f"\n📁 Data saved to: {DATA_DIR}")
    print(f"📊 Total files: {len(summary['files'])}")
    
    total_size = sum(f['size_mb'] for f in summary['files'])
    print(f"💾 Total size: {total_size:.2f} MB")
    
    print("""
╔══════════════════════════════════════════════════════════╗
║     ✅ DATA DOWNLOAD COMPLETE                            ║
║     Ready for Walk-Forward Backtest!                     ║
╚══════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    main()
