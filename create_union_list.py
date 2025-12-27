#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Create Union of TOP 62 + VN100
===============================
"""

import pandas as pd
from pathlib import Path

# VN100 stocks (official list)
VN100 = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB',
    'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SSI', 'STB',
    'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB',
    'VRE', 'BCG', 'PDR',
    # Add more VN100 stocks
    'VCI', 'SHB', 'DIG', 'DGC', 'VND', 'CEO', 'DXG', 'NVL', 'KBC',
    'MSB', 'EIB', 'HCM', 'VCG', 'HAG', 'VIX', 'GEX', 'SHS', 'CII',
    'KDH', 'MBS', 'DBC', 'PVD', 'PVS', 'VSC', 'NKG', 'VCK', 'TCH',
    'EVF', 'PC1', 'CTD', 'VGC', 'REE', 'DHG', 'VCS', 'PNJ', 'PHR',
    'NT2', 'LPB', 'AGG', 'VPI', 'HSG', 'DCM', 'HT1', 'GMD', 'SBT',
    'HNG', 'IDC', 'PVT', 'VHC', 'DPM', 'BWE', 'PDN', 'VTB', 'PAN',
    'HT6', 'TLG', 'BFC', 'HDG', 'OCB', 'PTB', 'APH', 'TCL', 'HU1',
    'HTV', 'KOS', 'PGI', 'SCR'
]

# Load TOP 62
with open('top_liquidity_symbols.txt', 'r') as f:
    top62 = [line.strip() for line in f if line.strip()]

print("="*80)
print("CREATING UNION OF TOP 62 + VN100")
print("="*80)

print(f"\nTOP 62 stocks: {len(top62)}")
print(f"VN100 stocks: {len(VN100)}")

# Create union (remove duplicates)
union = sorted(list(set(top62 + VN100)))

print(f"\nUnion (unique): {len(union)} stocks")
print(f"Overlap: {len(top62) + len(VN100) - len(union)} stocks")

# Save to file
output_file = 'union_top62_vn100.txt'
with open(output_file, 'w') as f:
    for symbol in union:
        f.write(f"{symbol}\n")

print(f"\nSaved to: {output_file}")

# Show first 20
print(f"\nFirst 20 stocks:")
for i, symbol in enumerate(union[:20], 1):
    print(f"  {i:2d}. {symbol}")

print(f"\n... and {len(union) - 20} more")

# Verify data exists
data_dir = Path('data/historical')
missing = []
for symbol in union:
    if not (data_dir / f"{symbol}.parquet").exists():
        missing.append(symbol)

if missing:
    print(f"\nWARNING: Missing data for {len(missing)} stocks:")
    print(f"  {', '.join(missing)}")
else:
    print(f"\n✓ All {len(union)} stocks have data available")

print("\n" + "="*80)
print("READY TO TRAIN!")
print("="*80)
print(f"\nNext: python train_union_parallel.py --workers 4")
print(f"Expected time: ~{len(union) // 4 * 75 // 60} minutes")
