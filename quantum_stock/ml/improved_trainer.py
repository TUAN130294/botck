# -*- coding: utf-8 -*-
"""
Improved Model Trainer with Vietnam T+2.5 Settlement
======================================================
Enhanced training pipeline with:
- T+2.5 settlement-aware data preparation
- Learning rate scheduling
- Early stopping with patience
- Gradient clipping
- Better logging and checkpointing
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

# Fallback logging
try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available")

from quantum_stock.ml.vietnam_data_prep import VietnamSettlementDataPrep


class ImprovedModelTrainer:
    """
    Enhanced model trainer with production best practices
    """

    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True, parents=True)

    def train_stockformer_improved(
        self,
        train_data: Tuple[np.ndarray, np.ndarray],
        val_data: Tuple[np.ndarray, np.ndarray],
        symbol: str,
        epochs: int = 100,
        batch_size: int = 64,
        learning_rate: float = 0.001,
        weight_decay: float = 1e-5,
        patience: int = 20,
        lr_patience: int = 10
    ) -> Tuple[any, Dict]:
        """
        Train Stockformer với improvements:
        - LR scheduling (ReduceLROnPlateau)
        - Early stopping
        - Gradient clipping
        - Better checkpointing

        Args:
            train_data: (X_train, y_train) - Already prepared with T+2.5
            val_data: (X_val, y_val)
            symbol: Stock symbol
            epochs: Max epochs (will early stop)
            batch_size: Batch size
            learning_rate: Initial LR
            weight_decay: L2 regularization
            patience: Early stopping patience
            lr_patience: LR scheduler patience

        Returns:
            model: Trained model
            history: Training history dict
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for Stockformer training")

        logger.info(f"[IMPROVED TRAINING] Stockformer - {symbol}")
        logger.info(f"  Config: epochs={epochs}, batch_size={batch_size}, lr={learning_rate}")
        logger.info(f"  Regularization: weight_decay={weight_decay}")
        logger.info(f"  Early stopping: patience={patience}")

        # Import model
        from quantum_stock.models.stockformer import StockformerPredictor

        X_train, y_train = train_data
        X_val, y_val = val_data

        logger.info(f"  Train: {X_train.shape[0]} samples")
        logger.info(f"  Val:   {X_val.shape[0]} samples")

        # Convert to PyTorch tensors
        X_train_t = torch.FloatTensor(X_train)
        y_train_t = torch.FloatTensor(y_train)
        X_val_t = torch.FloatTensor(X_val)
        y_val_t = torch.FloatTensor(y_val)

        # Create data loaders
        train_dataset = TensorDataset(X_train_t, y_train_t)
        val_dataset = TensorDataset(X_val_t, y_val_t)

        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            drop_last=False
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False
        )

        # Initialize model
        input_size = X_train.shape[2]  # Number of features
        forecast_horizon = y_train.shape[1]  # Forecast length

        model = StockformerPredictor(
            input_size=input_size,
            d_model=128,
            n_heads=8,
            n_layers=4,
            forecast_horizon=forecast_horizon,
            dropout=0.3  # Increased from 0.1
        )

        # Optimizer with weight decay (L2 regularization)
        optimizer = optim.Adam(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )

        # LR Scheduler: Reduce on plateau
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode='min',
            factor=0.5,
            patience=lr_patience,
            min_lr=1e-6
        )

        # Loss function
        criterion = nn.MSELoss()

        # Training state
        best_val_loss = float('inf')
        patience_counter = 0
        train_losses = []
        val_losses = []
        lr_history = []

        logger.info("\n[START TRAINING]")

        for epoch in range(epochs):
            # === TRAINING ===
            model.train()
            epoch_train_loss = 0.0

            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()

                # Forward pass
                predictions, _ = model(batch_X)
                loss = criterion(predictions, batch_y)

                # Backward pass
                loss.backward()

                # Gradient clipping (prevent exploding gradients)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

                # Update weights
                optimizer.step()

                epoch_train_loss += loss.item()

            train_loss = epoch_train_loss / len(train_loader)
            train_losses.append(train_loss)

            # === VALIDATION ===
            model.eval()
            epoch_val_loss = 0.0

            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    predictions, _ = model(batch_X)
                    loss = criterion(predictions, batch_y)
                    epoch_val_loss += loss.item()

            val_loss = epoch_val_loss / len(val_loader)
            val_losses.append(val_loss)

            # === LR SCHEDULING ===
            scheduler.step(val_loss)
            current_lr = optimizer.param_groups[0]['lr']
            lr_history.append(current_lr)

            # === EARLY STOPPING CHECK ===
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0

                # Save best model
                checkpoint_path = self.model_dir / f"{symbol}_stockformer_best.pt"
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'train_loss': train_loss,
                    'val_loss': val_loss,
                    'lr': current_lr,
                    'config': {
                        'input_size': input_size,
                        'forecast_horizon': forecast_horizon,
                        'd_model': 128,
                        'n_heads': 8,
                        'n_layers': 4,
                        'dropout': 0.3
                    }
                }, checkpoint_path)

                logger.info(f"[Epoch {epoch:3d}] NEW BEST! Val Loss: {val_loss:.6f}")

            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"\n[EARLY STOPPING] at epoch {epoch}")
                    logger.info(f"  Best val loss: {best_val_loss:.6f}")
                    logger.info(f"  No improvement for {patience} epochs")
                    break

            # === LOGGING ===
            if epoch % 5 == 0 or patience_counter == patience - 5:
                logger.info(
                    f"[Epoch {epoch:3d}] "
                    f"Train: {train_loss:.6f} | "
                    f"Val: {val_loss:.6f} | "
                    f"LR: {current_lr:.2e} | "
                    f"Patience: {patience_counter}/{patience}"
                )

        # === TRAINING COMPLETE ===
        logger.info("\n[TRAINING COMPLETE]")
        logger.info(f"  Total epochs: {len(train_losses)}")
        logger.info(f"  Best val loss: {best_val_loss:.6f}")
        logger.info(f"  Final LR: {lr_history[-1]:.2e}")

        # Load best model
        checkpoint = torch.load(self.model_dir / f"{symbol}_stockformer_best.pt")
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()

        # Save training history
        history = {
            'train_losses': train_losses,
            'val_losses': val_losses,
            'lr_history': lr_history,
            'best_val_loss': float(best_val_loss),
            'total_epochs': len(train_losses),
            'early_stopped': patience_counter >= patience,
            'timestamp': datetime.now().isoformat()
        }

        history_path = self.model_dir / f"{symbol}_training_history.json"
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)

        logger.info(f"  Saved history to {history_path}")

        return model, history

    def prepare_data_with_t25_settlement(
        self,
        df: pd.DataFrame,
        symbol: str,
        seq_len: int = 60,
        forecast_len: int = 5,
        train_split: float = 0.8
    ) -> Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray]]:
        """
        Prepare training data with Vietnam T+2.5 settlement

        Args:
            df: DataFrame with OHLCV data
            symbol: Stock symbol
            seq_len: Lookback window
            forecast_len: Forecast horizon
            train_split: Train/val split ratio

        Returns:
            (X_train, y_train), (X_val, y_val)
        """
        logger.info(f"[DATA PREP] Vietnam T+2.5 Settlement for {symbol}")

        prep = VietnamSettlementDataPrep(
            seq_len=seq_len,
            forecast_len=forecast_len
        )

        X, y, metadata_df = prep.create_training_data_with_features(
            df,
            price_col='close',
            volume_col='volume',
            sentiment_col=None  # Can add if available
        )

        # Validate
        prep.validate_settlement_alignment(df, X, y)

        # Split
        split_idx = int(len(X) * train_split)

        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        logger.info(f"  Total samples: {len(X)}")
        logger.info(f"  Train: {len(X_train)} ({train_split*100:.0f}%)")
        logger.info(f"  Val:   {len(X_val)} ({(1-train_split)*100:.0f}%)")

        return (X_train, y_train), (X_val, y_val)


# Example usage
if __name__ == "__main__":
    logger.info("Improved Model Trainer - Test Run")

    # Generate sample data
    np.random.seed(42)
    n_days = 300

    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=n_days),
        'close': 50000 + np.cumsum(np.random.randn(n_days) * 500),
        'volume': np.random.randint(100000, 1000000, n_days),
        'open': 50000 + np.cumsum(np.random.randn(n_days) * 500),
        'high': 50000 + np.cumsum(np.random.randn(n_days) * 500),
        'low': 50000 + np.cumsum(np.random.randn(n_days) * 500)
    })

    trainer = ImprovedModelTrainer()

    # Prepare data with T+2.5
    train_data, val_data = trainer.prepare_data_with_t25_settlement(
        df,
        symbol="TEST",
        seq_len=60,
        forecast_len=5,
        train_split=0.8
    )

    if TORCH_AVAILABLE:
        # Train
        model, history = trainer.train_stockformer_improved(
            train_data,
            val_data,
            symbol="TEST",
            epochs=20,  # Short test
            batch_size=32,
            patience=10
        )

        logger.info("\n[TEST COMPLETE]")
        logger.info(f"  Final val loss: {history['best_val_loss']:.6f}")
        logger.info(f"  Epochs trained: {history['total_epochs']}")
    else:
        logger.warning("PyTorch not available, skipping training test")
