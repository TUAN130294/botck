#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backtest SIMPLE Models (15 features)
=====================================
Backtest VN30 models trained with 15 features
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
import torch

# Import SIMPLE enhanced features (15 features)
sys.path.insert(0, str(Path(__file__).parent))
from enhanced_features_simple import calculate_vn_market_features_simple, normalize_features_simple

# VN Market Transaction Costs
COMMISSION_BUY = 0.0015   # 0.15% commission on buy
COMMISSION_SELL = 0.0015  # 0.15% commission on sell
SELLING_TAX = 0.001       # 0.1% tax on sell only
SLIPPAGE = 0.001          # 0.1% slippage estimate

# VN30 stocks
VN30 = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
    'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SSI', 'STB', 'TCB', 'TPB',
    'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE', 'BCG'
]

def simple_backtest(
    symbol: str,
    model_path: Path,
    data_path: Path,
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31",
    initial_capital: float = 100_000_000  # 100M VND
):
    """
    Simple backtesting strategy with 15 features:
    - Buy when model predicts positive return for T+3
    - Sell after holding period (T+3 to T+7)
    - Respect T+2.5 settlement
    """

    print(f"\n{'='*70}")
    print(f"BACKTESTING {symbol} (SIMPLE)")
    print(f"{'='*70}")

    try:
        # Load model
        from quantum_stock.models.stockformer import StockformerPredictor

        checkpoint = torch.load(model_path, map_location='cpu')

        # Get feature dim from checkpoint
        feature_dim = checkpoint.get('feature_dim', 15)

        # SIMPLE model config (must match training)
        model = StockformerPredictor(
            input_size=feature_dim,
            d_model=64,        # Smaller model
            n_heads=8,
            n_layers=2,        # Fewer layers
            d_ff=128,
            dropout=0.5,
            forecast_horizon=5
        )
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()

        print(f"[OK] Model loaded: {model_path.name}")
        print(f"   Val loss: {checkpoint['val_loss']:.6f}")
        print(f"   Features: {feature_dim}")

    except Exception as e:
        print(f"[FAIL] Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return None

    try:
        # Load data
        df = pd.read_parquet(data_path)
        df['date'] = pd.to_datetime(df['date'])

        # Filter date range
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

        if len(df) < 100:
            print(f"[WARN] Not enough data: {len(df)} days")
            return None

        print(f"[OK] Data loaded: {len(df)} days")
        print(f"   Period: {df['date'].min().date()} to {df['date'].max().date()}")

    except Exception as e:
        print(f"[FAIL] Failed to load data: {e}")
        return None

    # Prepare SIMPLE enhanced features (15 features like training)
    try:
        # Load VN-Index for market context
        vn_index = pd.read_parquet('data/historical/VNINDEX.parquet')
        vn_index = vn_index.set_index('date')
    except:
        vn_index = None

    # Calculate SIMPLE enhanced features
    df_features = calculate_vn_market_features_simple(df, vn_index)
    df_normalized, scaler = normalize_features_simple(df_features, method='robust')

    # Select feature columns (same as training)
    exclude_cols = ['date', 'day_of_week', 'day_of_month', 'month',
                    'tet_season', 'symbol', 'time', 'ticker']
    feature_cols = [col for col in df_normalized.columns
                   if col not in exclude_cols
                   and pd.api.types.is_numeric_dtype(df_normalized[col])]

    features_array = df_normalized[feature_cols].values.astype(np.float32)
    close_prices = df['close'].values
    dates = df['date'].values

    print(f"[OK] SIMPLE features prepared: {len(feature_cols)} features")

    # Simulate trading
    seq_len = 60
    forecast_len = 5
    settlement_days = 3  # T+2.5

    capital = initial_capital
    position = None  # Current position (if any)
    trades = []
    equity_curve = [capital]

    print(f"\n[BACKTESTING]")
    print(f"  Initial capital: {capital:,.0f} VND")
    print(f"  Sequence length: {seq_len}")
    print(f"  Settlement days: {settlement_days}")

    # Walk through data
    for i in range(seq_len, len(close_prices) - forecast_len - settlement_days):
        current_date = dates[i]

        # Check if we have a position
        if position is not None:
            # Check if we should exit
            hold_days = int((current_date - position['entry_date']) / np.timedelta64(1, 'D'))

            # Exit after T+3 to T+7 (settlement compliant)
            if hold_days >= settlement_days:
                gross_exit_price = close_prices[i]
                
                # Calculate net prices with transaction costs
                entry_cost = position['entry_price'] * (1 + COMMISSION_BUY + SLIPPAGE)
                exit_net = gross_exit_price * (1 - COMMISSION_SELL - SELLING_TAX - SLIPPAGE)
                
                # Calculate P&L with costs
                pnl = (exit_net - entry_cost) / entry_cost
                capital *= (1 + pnl)

                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': current_date,
                    'entry_price': position['entry_price'],
                    'exit_price': gross_exit_price,
                    'pnl_pct': pnl * 100,
                    'hold_days': hold_days,
                    'costs_pct': (COMMISSION_BUY + COMMISSION_SELL + SELLING_TAX + SLIPPAGE * 2) * 100
                })

                position = None

        else:
            # No position, check if we should enter
            # Get sequence (60 days x 15 features)
            seq_features = features_array[i-seq_len:i]

            # Prepare input: (batch=1, seq_len=60, features=15)
            input_tensor = torch.FloatTensor(seq_features).unsqueeze(0)

            # Predict
            with torch.no_grad():
                prediction, _ = model(input_tensor)  # model returns (price_forecast, volatility_forecast)
                prediction = prediction.squeeze().numpy()

            # Trading logic: Buy if T+3 prediction is positive
            t3_prediction = prediction[0]  # First prediction is for T+3

            if t3_prediction > 0.001:  # Threshold: > 0.1% predicted gain (lowered from 0.3%)
                # Enter position
                position = {
                    'entry_date': current_date,
                    'entry_price': close_prices[i]
                }

        equity_curve.append(capital)

    # Close any remaining position
    if position is not None:
        exit_price = close_prices[-1]
        pnl = (exit_price - position['entry_price']) / position['entry_price']
        capital *= (1 + pnl)

        trades.append({
            'entry_date': position['entry_date'],
            'exit_date': dates[-1],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'pnl_pct': pnl * 100,
            'hold_days': int((dates[-1] - position['entry_date']) / np.timedelta64(1, 'D'))
        })

    # Calculate metrics
    if not trades:
        print(f"\n[WARN] No trades executed")
        return None

    trades_df = pd.DataFrame(trades)

    # Performance metrics
    total_return = (capital - initial_capital) / initial_capital
    num_trades = len(trades)
    winning_trades = len(trades_df[trades_df['pnl_pct'] > 0])
    win_rate = winning_trades / num_trades if num_trades > 0 else 0

    # Calculate Sharpe ratio
    returns = trades_df['pnl_pct'].values / 100
    sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    # Max drawdown
    equity_curve = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - running_max) / running_max
    max_drawdown = drawdown.min()

    # Print results
    print(f"\n{'='*70}")
    print(f"RESULTS - {symbol}")
    print(f"{'='*70}")
    print(f"Total Return:     {total_return*100:>10.2f}%")
    print(f"Sharpe Ratio:     {sharpe_ratio:>10.2f}")
    print(f"Win Rate:         {win_rate*100:>10.1f}%")
    print(f"Max Drawdown:     {max_drawdown*100:>10.2f}%")
    print(f"Total Trades:     {num_trades:>10}")
    print(f"Winning Trades:   {winning_trades:>10}")
    print(f"Final Capital:    {capital:>10,.0f} VND")

    # Check PASS criteria (Updated to Sharpe>1.5 AND Win>50%)
    passed = sharpe_ratio > 1.5 and win_rate > 0.50
    print(f"\nPASSED: {'YES [PASS]' if passed else 'NO [FAIL]'} (Sharpe>1.5 AND Win>50%)")
    print(f"{'='*70}")

    return {
        'symbol': symbol,
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'win_rate': win_rate,
        'max_drawdown': max_drawdown,
        'total_trades': num_trades,
        'passed': passed
    }


def main():
    """Run backtest for all VN30 stocks"""

    print("\n" + "="*70)
    print("VN30 SIMPLE BACKTEST (15 Features)")
    print("="*70)
    print(f"Started at: {datetime.now()}")

    results = []

    for symbol in VN30:
        model_path = Path(f'models/{symbol}_stockformer_simple_best.pt')
        data_path = Path(f'data/historical/{symbol}.parquet')

        if not model_path.exists():
            print(f"\n[SKIP] {symbol} - Model not found")
            continue

        if not data_path.exists():
            print(f"\n[SKIP] {symbol} - Data not found")
            continue

        result = simple_backtest(symbol, model_path, data_path)

        if result:
            results.append(result)

    # Summary
    if results:
        results_df = pd.DataFrame(results)

        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = f'backtest_results_simple_{timestamp}.csv'
        results_df.to_csv(results_file, index=False)

        print("\n" + "="*70)
        print("BACKTEST SUMMARY - SIMPLE Models (15 Features)")
        print("="*70)

        # Overall stats
        passed = results_df[results_df['passed'] == True]
        print(f"\nPASSED: {len(passed)}/{len(results_df)} stocks ({len(passed)/len(results_df)*100:.1f}%)")

        # Stocks with trades
        with_trades = results_df[results_df['total_trades'] > 0]
        print(f"Stocks with trades: {len(with_trades)}/{len(results_df)}")

        if len(passed) > 0:
            print(f"\n[PASSED STOCKS] ({len(passed)}):")
            for _, row in passed.iterrows():
                print(f"  {row['symbol']}: Return={row['total_return']*100:.1f}%, "
                      f"Sharpe={row['sharpe_ratio']:.2f}, Win={row['win_rate']*100:.1f}%")

        if len(with_trades) > 0:
            print(f"\nTop 5 by Sharpe Ratio:")
            top5 = results_df.nlargest(5, 'sharpe_ratio')
            for _, row in top5.iterrows():
                status = "[PASS]" if row['passed'] else "[FAIL]"
                print(f"  {row['symbol']}: Sharpe={row['sharpe_ratio']:.2f}, "
                      f"Win={row['win_rate']*100:.1f}%, Trades={row['total_trades']} [{status}]")

            print(f"\nAverage metrics (stocks with trades):")
            print(f"  Return:      {with_trades['total_return'].mean()*100:.2f}%")
            print(f"  Sharpe:      {with_trades['sharpe_ratio'].mean():.2f}")
            print(f"  Win Rate:    {with_trades['win_rate'].mean()*100:.1f}%")
            print(f"  Max DD:      {with_trades['max_drawdown'].mean()*100:.2f}%")
            print(f"  Avg Trades:  {with_trades['total_trades'].mean():.0f}")

        print(f"\n{'='*70}")
        print(f"Results saved to: {results_file}")
        print(f"{'='*70}")

        # Comparison with 40-feature results
        print(f"\nCOMPARISON:")
        print(f"  40-feature models: 0/29 PASSED")
        print(f"  15-feature models: {len(passed)}/{len(results_df)} PASSED")
        if len(passed) > 0:
            print(f"  [SUCCESS] IMPROVEMENT: {len(passed)} stocks now PASSED!")
        else:
            print(f"  [WARNING] Still 0 PASSED - May need further simplification")


if __name__ == '__main__':
    main()
