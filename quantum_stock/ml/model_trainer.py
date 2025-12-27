# -*- coding: utf-8 -*-
"""
ML Model Training Pipeline for VN-QUANT
========================================
Train and persist all ML models.

Models:
- Stockformer (Transformer)
- MADDPG (8 agents)
- Agent weight optimization
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import pickle
import json

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class ModelTrainer:
    """
    Centralized model training pipeline

    Features:
    - Train/validate/test split
    - Model persistence
    - Performance tracking
    - Hyperparameter tuning
    """

    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True, parents=True)

        self.training_history = []

    def train_stockformer(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame,
        symbol: str,
        epochs: int = 100,
        batch_size: int = 32
    ):
        """
        Train Stockformer model

        Args:
            train_data: Training OHLCV data
            val_data: Validation data
            symbol: Stock symbol
            epochs: Training epochs
            batch_size: Batch size
        """
        if not TORCH_AVAILABLE:
            logger.error("PyTorch not available, cannot train Stockformer")
            return None

        logger.info(f"Training Stockformer for {symbol}")

        # Import model
        from quantum_stock.models.stockformer import StockformerModel

        # Initialize
        model = StockformerModel(
            input_size=50,
            d_model=128,
            n_heads=8,
            n_layers=4
        )

        # Prepare data
        train_loader = self._prepare_stockformer_data(train_data, batch_size)
        val_loader = self._prepare_stockformer_data(val_data, batch_size)

        # Train
        optimizer = optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.MSELoss()

        best_val_loss = float('inf')

        for epoch in range(epochs):
            # Training
            model.train()
            train_loss = 0.0

            for batch in train_loader:
                X, y = batch

                optimizer.zero_grad()
                pred = model(X)
                loss = criterion(pred, y)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            # Validation
            model.eval()
            val_loss = 0.0

            with torch.no_grad():
                for batch in val_loader:
                    X, y = batch
                    pred = model(X)
                    loss = criterion(pred, y)
                    val_loss += loss.item()

            train_loss /= len(train_loader)
            val_loss /= len(val_loader)

            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}: train_loss={train_loss:.4f}, val_loss={val_loss:.4f}")

            # Save best model
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                self._save_model(model, f"stockformer_{symbol}")

        logger.info(f"Training complete. Best val_loss: {best_val_loss:.4f}")

        return model

    def train_maddpg(
        self,
        replay_buffer: List,
        num_agents: int = 8,
        episodes: int = 1000
    ):
        """
        Train MADDPG agents

        Args:
            replay_buffer: Experience replay buffer
            num_agents: Number of agents
            episodes: Training episodes
        """
        logger.info(f"Training MADDPG with {num_agents} agents")

        from quantum_stock.rl.maddpg_trader import MADDPGTrader

        trader = MADDPGTrader(num_agents=num_agents)

        for episode in range(episodes):
            # Sample batch from replay buffer
            batch = self._sample_replay_buffer(replay_buffer, batch_size=64)

            # Train all agents
            losses = trader.train_step(batch)

            if episode % 100 == 0:
                avg_loss = np.mean([l for l in losses.values()])
                logger.info(f"Episode {episode}: avg_loss={avg_loss:.4f}")

        # Save trained models
        self._save_model(trader, "maddpg_trader")

        return trader

    def optimize_agent_weights(
        self,
        historical_signals: pd.DataFrame,
        actual_outcomes: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Optimize agent voting weights based on historical accuracy

        Args:
            historical_signals: Agent predictions
            actual_outcomes: Actual price movements

        Returns:
            Optimized weights dict
        """
        logger.info("Optimizing agent weights")

        # Calculate accuracy per agent
        agents = historical_signals['agent_name'].unique()

        weights = {}

        for agent in agents:
            agent_signals = historical_signals[
                historical_signals['agent_name'] == agent
            ]

            # Join with outcomes
            merged = agent_signals.merge(
                actual_outcomes,
                left_on='signal_id',
                right_index=True
            )

            # Calculate accuracy
            correct = (
                (merged['signal'] == 'BUY') & (merged['return'] > 0) |
                (merged['signal'] == 'SELL') & (merged['return'] < 0)
            ).sum()

            accuracy = correct / len(merged) if len(merged) > 0 else 0.5

            # Weight = accuracy with min/max bounds
            weight = max(0.5, min(2.0, accuracy / 0.5))

            weights[agent] = weight

            logger.info(f"{agent}: accuracy={accuracy:.2%}, weight={weight:.2f}")

        # Save weights
        self._save_weights(weights, "agent_weights")

        return weights

    def _prepare_stockformer_data(
        self,
        df: pd.DataFrame,
        batch_size: int
    ) -> DataLoader:
        """Prepare data for Stockformer"""
        # Create sequences
        X, y = [], []

        for i in range(60, len(df) - 5):
            # Last 60 days as input
            X.append(df.iloc[i-60:i].values)
            # Next 5 days close as target
            y.append(df.iloc[i:i+5]['close'].values)

        X = torch.FloatTensor(X)
        y = torch.FloatTensor(y)

        dataset = torch.utils.data.TensorDataset(X, y)
        return DataLoader(dataset, batch_size=batch_size, shuffle=True)

    def _sample_replay_buffer(
        self,
        buffer: List,
        batch_size: int
    ) -> List:
        """Sample from replay buffer"""
        indices = np.random.choice(len(buffer), batch_size, replace=False)
        return [buffer[i] for i in indices]

    def _save_model(self, model, name: str):
        """Save model to disk"""
        path = self.model_dir / f"{name}.pkl"

        with open(path, 'wb') as f:
            pickle.dump(model, f)

        logger.info(f"Model saved: {path}")

    def _save_weights(self, weights: Dict, name: str):
        """Save weights to JSON"""
        path = self.model_dir / f"{name}.json"

        with open(path, 'w') as f:
            json.dump(weights, f, indent=2)

        logger.info(f"Weights saved: {path}")

    def load_model(self, name: str):
        """Load model from disk"""
        path = self.model_dir / f"{name}.pkl"

        if not path.exists():
            logger.warning(f"Model not found: {path}")
            return None

        with open(path, 'rb') as f:
            model = pickle.load(f)

        logger.info(f"Model loaded: {path}")
        return model

    def load_weights(self, name: str) -> Dict[str, float]:
        """Load weights from JSON"""
        path = self.model_dir / f"{name}.json"

        if not path.exists():
            logger.warning(f"Weights not found: {path}")
            return {}

        with open(path, 'r') as f:
            weights = json.load(f)

        logger.info(f"Weights loaded: {path}")
        return weights


# Global trainer instance
_trainer: Optional[ModelTrainer] = None


def get_trainer() -> ModelTrainer:
    """Get global trainer instance"""
    global _trainer
    if _trainer is None:
        _trainer = ModelTrainer()
    return _trainer


__all__ = ["ModelTrainer", "get_trainer"]
