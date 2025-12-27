"""
Simple Training Pipeline - 15 Features
=======================================
Train models with ONLY 15 best features (vs 40)

Simpler model to avoid overfitting:
- 15 features (vs 40)
- d_model=64 (vs 128)
- n_layers=2 (vs 4)
- dropout=0.5 (vs 0.3)

Usage:
    # Single stock
    python train_simple.py --symbol FPT --gpu

    # Multiple stocks
    python train_simple.py --symbols FPT,ACB,MBB --gpu

    # All VN30
    python train_simple.py --vn30 --gpu
"""

import sys
import argparse
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import SIMPLE enhanced features
sys.path.insert(0, str(Path(__file__).parent))
from enhanced_features_simple import calculate_vn_market_features_simple, normalize_features_simple

# Import existing modules
from quantum_stock.models.stockformer import StockformerPredictor
from quantum_stock.ml.vietnam_data_prep import VietnamSettlementDataPrep


def load_and_prepare_data(symbol):
    """
    Load data and prepare SIMPLE features (15 features)

    Returns:
        X_train, y_train, X_val, y_val, feature_dim
    """

    # Load stock data
    data_file = Path(f'data/historical/{symbol}.parquet')
    if not data_file.exists():
        raise FileNotFoundError(f"No data for {symbol}")

    df = pd.read_parquet(data_file)
    df = df.sort_values('date').reset_index(drop=True)

    logger.info(f"Loaded {len(df)} days for {symbol}")
    logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")

    # Load VN-Index for market context
    try:
        vn_index = pd.read_parquet('data/historical/VNINDEX.parquet')
        vn_index = vn_index.set_index('date')
    except:
        logger.warning("VN-Index data not found, using None")
        vn_index = None

    # Calculate SIMPLE enhanced features (15 features)
    logger.info("Calculating 15 SIMPLE enhanced features...")
    df_features = calculate_vn_market_features_simple(df, vn_index)

    # Normalize
    df_normalized, scaler = normalize_features_simple(df_features, method='robust')

    # Select feature columns (exclude date, categorical, and string columns)
    exclude_cols = ['date', 'day_of_week', 'day_of_month', 'month',
                    'tet_season', 'symbol', 'time', 'ticker']
    feature_cols = [col for col in df_normalized.columns
                   if col not in exclude_cols
                   and pd.api.types.is_numeric_dtype(df_normalized[col])]

    features_array = df_normalized[feature_cols].values.astype(np.float32)
    feature_dim = len(feature_cols)

    logger.info(f"Using {feature_dim} features: {feature_cols}")

    # Create sequences
    logger.info("Creating sequences...")
    seq_len = 60
    pred_horizon = 5  # T+3 to T+7

    X_sequences = []
    y_sequences = []

    for i in range(seq_len, len(df) - pred_horizon - 3):  # -3 for T+3 offset
        # Input sequence
        seq_features = features_array[i-seq_len:i]

        # Target: returns for T+3 to T+7
        future_prices = df['close'].iloc[i+3:i+3+pred_horizon].values
        current_price = df['close'].iloc[i]

        if current_price > 0 and len(future_prices) == pred_horizon:
            future_returns = (future_prices - current_price) / current_price
            X_sequences.append(seq_features)
            y_sequences.append(future_returns)

    # Convert to arrays (explicit float32)
    X = np.array(X_sequences, dtype=np.float32)
    y = np.array(y_sequences, dtype=np.float32)

    logger.info(f"Created {len(X)} sequences")
    logger.info(f"X shape: {X.shape}, y shape: {y.shape}")

    # Train/val split (80/20)
    split_idx = int(len(X) * 0.8)

    X_train = X[:split_idx]
    y_train = y[:split_idx]
    X_val = X[split_idx:]
    y_val = y[split_idx:]

    logger.info(f"Train: {len(X_train)} samples")
    logger.info(f"Val: {len(X_val)} samples")

    return X_train, y_train, X_val, y_val, feature_dim


def train_model(symbol, device='cpu', epochs=100, batch_size=32):
    """
    Train SIMPLE model for one symbol

    Model config:
    - d_model=64 (vs 128)
    - n_layers=2 (vs 4)
    - dropout=0.5 (vs 0.3)
    """

    logger.info(f"\n{'='*60}")
    logger.info(f"Training SIMPLE model for {symbol}")
    logger.info(f"{'='*60}")

    # Load and prepare data
    try:
        X_train, y_train, X_val, y_val, feature_dim = load_and_prepare_data(symbol)
    except Exception as e:
        logger.error(f"Failed to load data for {symbol}: {e}")
        return None

    # SIMPLE model configuration (smaller to avoid overfitting)
    model_config = {
        'd_model': 64,        # Reduced from 128
        'n_heads': 8,         # Keep same (64/8=8 dimension per head)
        'n_layers': 2,        # Reduced from 4
        'dim_feedforward': 128,  # Reduced from 256
        'dropout': 0.5,       # Increased from 0.3
        'pred_horizon': 5
    }

    logger.info(f"Model config: {model_config}")

    # Create model
    model = StockformerPredictor(
        input_size=feature_dim,
        d_model=model_config['d_model'],
        n_heads=model_config['n_heads'],
        n_layers=model_config['n_layers'],
        d_ff=model_config['dim_feedforward'],
        forecast_horizon=model_config['pred_horizon'],
        dropout=model_config['dropout']
    ).to(device)

    logger.info(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Loss and optimizer
    criterion = nn.MSELoss()
    optimizer = optim.AdamW(
        model.parameters(),
        lr=0.001,
        weight_decay=1e-4  # Increased from 1e-5 for more regularization
    )

    # Learning rate scheduler
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode='min',
        factor=0.5,
        patience=10
    )

    # Convert to tensors
    X_train_t = torch.FloatTensor(X_train).to(device)
    y_train_t = torch.FloatTensor(y_train).to(device)
    X_val_t = torch.FloatTensor(X_val).to(device)
    y_val_t = torch.FloatTensor(y_val).to(device)

    # Training loop
    best_val_loss = float('inf')
    patience_counter = 0
    patience = 20

    train_losses = []
    val_losses = []

    logger.info("\nStarting training...")
    start_time = datetime.now()

    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0
        n_batches = 0

        for i in range(0, len(X_train_t), batch_size):
            batch_X = X_train_t[i:i+batch_size]
            batch_y = y_train_t[i:i+batch_size]

            optimizer.zero_grad()
            output, _ = model(batch_X)  # model returns (price_forecast, volatility_forecast)
            loss = criterion(output, batch_y)
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()

            train_loss += loss.item()
            n_batches += 1

        train_loss /= n_batches
        train_losses.append(train_loss)

        # Validation
        model.eval()
        with torch.no_grad():
            val_output, _ = model(X_val_t)  # model returns (price_forecast, volatility_forecast)
            val_loss = criterion(val_output, y_val_t).item()
            val_losses.append(val_loss)

        # Learning rate scheduling
        scheduler.step(val_loss)

        # Log progress
        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch+1}/{epochs} - Train: {train_loss:.6f}, Val: {val_loss:.6f}")

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0

            # Save best model
            model_path = Path('models') / f'{symbol}_stockformer_simple_best.pt'
            model_path.parent.mkdir(exist_ok=True)

            torch.save({
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'epoch': epoch,
                'val_loss': val_loss,
                'train_loss': train_loss,
                'model_config': model_config,
                'feature_dim': feature_dim
            }, model_path)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

    elapsed = datetime.now() - start_time
    logger.info(f"\nTraining completed in {elapsed}")
    logger.info(f"Best val loss: {best_val_loss:.6f}")
    logger.info(f"Model saved to: {model_path}")

    return {
        'symbol': symbol,
        'best_val_loss': best_val_loss,
        'final_train_loss': train_losses[-1],
        'epochs_trained': len(train_losses),
        'model_path': str(model_path),
        'feature_dim': feature_dim,
        'training_time': str(elapsed)
    }


def main():
    parser = argparse.ArgumentParser(description='Train SIMPLE models (15 features)')
    parser.add_argument('--symbol', type=str, help='Single symbol to train')
    parser.add_argument('--symbols', type=str, help='Comma-separated symbols')
    parser.add_argument('--vn30', action='store_true', help='Train all VN30')
    parser.add_argument('--gpu', action='store_true', help='Use GPU')
    parser.add_argument('--epochs', type=int, default=100, help='Max epochs')
    parser.add_argument('--batch_size', type=int, default=32, help='Batch size')

    args = parser.parse_args()

    # Device
    device = 'cuda' if args.gpu and torch.cuda.is_available() else 'cpu'
    logger.info(f"Using device: {device}")

    # Determine symbols
    if args.vn30:
        # VN30 list
        vn30_symbols = [
            'ACB', 'BCM', 'BCG', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB',
            'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SSI', 'STB', 'TCB',
            'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'
        ]
        symbols = vn30_symbols
    elif args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
    elif args.symbol:
        symbols = [args.symbol]
    else:
        logger.error("Please specify --symbol, --symbols, or --vn30")
        return

    logger.info(f"Training {len(symbols)} symbols: {symbols}")

    # Train all
    results = []
    overall_start = datetime.now()

    for i, symbol in enumerate(symbols, 1):
        logger.info(f"\n[{i}/{len(symbols)}] Training {symbol}...")

        try:
            result = train_model(
                symbol,
                device=device,
                epochs=args.epochs,
                batch_size=args.batch_size
            )

            if result:
                results.append(result)
                logger.info(f"✓ {symbol} completed - Val loss: {result['best_val_loss']:.6f}")
            else:
                logger.warning(f"✗ {symbol} failed")

        except Exception as e:
            logger.error(f"✗ {symbol} error: {e}")
            import traceback
            traceback.print_exc()

    overall_elapsed = datetime.now() - overall_start

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"TRAINING SUMMARY - SIMPLE Models (15 features)")
    logger.info(f"{'='*60}")
    logger.info(f"Total time: {overall_elapsed}")
    logger.info(f"Successful: {len(results)}/{len(symbols)}")

    if results:
        # Save results (skip if single symbol to avoid clutter)
        results_df = pd.DataFrame(results)
        results_file = None
        if len(symbols) > 1:  # Only save CSV if training multiple symbols
            results_file = f'training_results_simple_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            results_df.to_csv(results_file, index=False)

        logger.info(f"\nTop 10 by val_loss:")
        top_results = results_df.nsmallest(10, 'best_val_loss')
        for idx, row in top_results.iterrows():
            logger.info(f"  {row['symbol']}: {row['best_val_loss']:.6f}")

        # Quality metrics
        excellent = len(results_df[results_df['best_val_loss'] < 0.003])
        good = len(results_df[(results_df['best_val_loss'] >= 0.003) & (results_df['best_val_loss'] < 0.01)])
        acceptable = len(results_df[(results_df['best_val_loss'] >= 0.01) & (results_df['best_val_loss'] < 0.03)])
        poor = len(results_df[results_df['best_val_loss'] >= 0.03])

        logger.info(f"\nQuality breakdown:")
        logger.info(f"  EXCELLENT (<0.003): {excellent} ({excellent/len(results)*100:.1f}%)")
        logger.info(f"  GOOD (0.003-0.01): {good} ({good/len(results)*100:.1f}%)")
        logger.info(f"  ACCEPTABLE (0.01-0.03): {acceptable} ({acceptable/len(results)*100:.1f}%)")
        logger.info(f"  POOR (>0.03): {poor} ({poor/len(results)*100:.1f}%)")

        if results_file:
            logger.info(f"Results saved to: {results_file}")

        logger.info(f"\n{'='*60}")
        logger.info(f"Next step: Run backtest")
        logger.info(f"  python backtest_simple.py")
        logger.info(f"{'='*60}")


if __name__ == '__main__':
    main()
