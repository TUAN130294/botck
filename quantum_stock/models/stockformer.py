# -*- coding: utf-8 -*-
"""
Stockformer Predictor - Level 4 Agentic AI
===========================================
Transformer-based stock price prediction model.

Architecture:
- Input: 100 features (OHLCV + technical indicators)
- Transformer Encoder: 4 layers, 8 heads
- Output: 5-day price forecast

Features:
- Multi-head self-attention for pattern recognition
- Positional encoding for time sequence
- Ensemble of 3 models for robustness
- GPU acceleration when available

Reference: "Temporal Fusion Transformer" (Lim et al., 2021)
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

# Check for PyTorch availability
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch not installed. Run: pip install torch")


@dataclass
class PredictionResult:
    symbol: str
    current_price: float
    predictions: List[float]  # Next 5 days
    direction: str  # "UP", "DOWN", "SIDEWAYS"
    confidence: float
    expected_return: float  # Percentage
    volatility_forecast: float
    model_name: str = "Stockformer"


if TORCH_AVAILABLE:
    
    class PositionalEncoding(nn.Module):
        """Sinusoidal positional encoding for transformer"""
        
        def __init__(self, d_model: int, max_len: int = 500, dropout: float = 0.1):
            super().__init__()
            self.dropout = nn.Dropout(p=dropout)
            
            pe = torch.zeros(max_len, d_model)
            position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
            
            div_term = torch.exp(
                torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
            )
            
            pe[:, 0::2] = torch.sin(position * div_term)
            pe[:, 1::2] = torch.cos(position * div_term)
            
            pe = pe.unsqueeze(0)  # (1, max_len, d_model)
            self.register_buffer('pe', pe)
        
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """
            x: (batch, seq_len, d_model)
            """
            x = x + self.pe[:, :x.size(1), :]
            return self.dropout(x)
    
    
    class StockformerEncoder(nn.Module):
        """Transformer encoder for stock prediction"""
        
        def __init__(
            self,
            input_size: int = 50,
            d_model: int = 128,
            n_heads: int = 8,
            n_layers: int = 4,
            d_ff: int = 512,
            dropout: float = 0.1
        ):
            super().__init__()
            
            self.input_size = input_size
            self.d_model = d_model
            
            # Input projection
            self.input_projection = nn.Linear(input_size, d_model)
            
            # Positional encoding
            self.pos_encoder = PositionalEncoding(d_model, dropout=dropout)
            
            # Transformer encoder layers
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=n_heads,
                dim_feedforward=d_ff,
                dropout=dropout,
                activation='gelu',
                batch_first=True
            )
            
            self.transformer = nn.TransformerEncoder(
                encoder_layer,
                num_layers=n_layers,
                norm=nn.LayerNorm(d_model)
            )
            
            # Dropout
            self.dropout = nn.Dropout(dropout)
        
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """
            x: (batch, seq_len, input_size)
            returns: (batch, seq_len, d_model)
            """
            # Project input
            x = self.input_projection(x)
            
            # Add positional encoding
            x = self.pos_encoder(x)
            
            # Transformer encoding
            x = self.transformer(x)
            
            return x
    
    
    class StockformerPredictor(nn.Module):
        """
        Complete Stockformer model for price prediction
        
        Takes sequence of features → predicts next N days
        """
        
        def __init__(
            self,
            input_size: int = 50,
            d_model: int = 128,
            n_heads: int = 8,
            n_layers: int = 4,
            d_ff: int = 512,
            forecast_horizon: int = 5,
            dropout: float = 0.1
        ):
            super().__init__()
            
            self.forecast_horizon = forecast_horizon
            
            # Encoder
            self.encoder = StockformerEncoder(
                input_size=input_size,
                d_model=d_model,
                n_heads=n_heads,
                n_layers=n_layers,
                d_ff=d_ff,
                dropout=dropout
            )
            
            # Decoder head for multi-step forecast
            # IMPROVED: Added LayerNorm for better regularization
            self.decoder = nn.Sequential(
                nn.Linear(d_model, d_model * 2),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.LayerNorm(d_model * 2),  # Added
                nn.Linear(d_model * 2, d_model),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.LayerNorm(d_model),  # Added
                nn.Linear(d_model, forecast_horizon)
            )
            
            # Volatility head
            self.volatility_head = nn.Sequential(
                nn.Linear(d_model, d_model // 2),
                nn.GELU(),
                nn.Linear(d_model // 2, forecast_horizon),
                nn.Softplus()  # Ensure positive volatility
            )
        
        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            """
            x: (batch, seq_len, input_size)
            returns: 
                - price_forecast: (batch, forecast_horizon)
                - volatility_forecast: (batch, forecast_horizon)
            """
            # Encode
            encoded = self.encoder(x)  # (batch, seq_len, d_model)
            
            # Use last timestep as context
            context = encoded[:, -1, :]  # (batch, d_model)
            
            # Decode to forecasts
            price_forecast = self.decoder(context)
            volatility_forecast = self.volatility_head(context)
            
            return price_forecast, volatility_forecast
        
        def predict_returns(self, x: torch.Tensor) -> torch.Tensor:
            """Predict returns instead of prices"""
            price_forecast, _ = self.forward(x)
            return price_forecast


class StockformerEnsemble:
    """
    Ensemble of 3 Stockformer models for robust prediction
    
    Combines predictions from multiple models trained with different:
    - Random seeds
    - Dropout rates
    - Layer configurations
    """
    
    def __init__(
        self,
        input_size: int = 50,
        forecast_horizon: int = 5,
        n_models: int = 3,
        device: str = None
    ):
        self.input_size = input_size
        self.forecast_horizon = forecast_horizon
        self.n_models = n_models
        
        # Device selection
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        # Create models with slightly different configs
        self.models: List[StockformerPredictor] = []
        
        if TORCH_AVAILABLE:
            for i in range(n_models):
                model = StockformerPredictor(
                    input_size=input_size,
                    d_model=128,
                    n_heads=8,
                    n_layers=4 + i,  # Different depths
                    dropout=0.1 + 0.05 * i,  # Different dropout
                    forecast_horizon=forecast_horizon
                )
                model.to(self.device)
                self.models.append(model)
        
        self.is_trained = False
    
    def prepare_features(self, prices: np.ndarray, volumes: np.ndarray = None) -> np.ndarray:
        """
        Prepare feature matrix from raw price/volume data
        
        Features:
        - Normalized OHLCV
        - Returns at different lags
        - Moving averages
        - RSI, MACD components
        - Volatility features
        """
        n = len(prices)
        features = []
        
        # Returns
        returns = np.zeros(n)
        returns[1:] = np.diff(np.log(prices))
        features.append(returns)
        
        # Lagged returns
        for lag in [1, 2, 3, 5, 10, 20]:
            lagged = np.zeros(n)
            if lag < n:
                lagged[lag:] = returns[:-lag] if lag > 0 else returns
            features.append(lagged)
        
        # Moving averages (normalized)
        for window in [5, 10, 20, 50]:
            ma = np.zeros(n)
            for i in range(window-1, n):
                ma[i] = np.mean(prices[i-window+1:i+1])
            # Normalize: (price - ma) / price
            ma_norm = np.zeros(n)
            mask = prices > 0
            ma_norm[mask] = (prices[mask] - ma[mask]) / prices[mask]
            features.append(ma_norm)
        
        # Volatility (rolling std of returns)
        for window in [5, 10, 20]:
            vol = np.zeros(n)
            for i in range(window-1, n):
                vol[i] = np.std(returns[i-window+1:i+1])
            features.append(vol)
        
        # RSI
        rsi = self._calculate_rsi(prices)
        features.append(rsi / 100)  # Normalize to 0-1
        
        # MACD components
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        macd = ema12 - ema26
        signal = self._ema(macd, 9)
        macd_norm = np.zeros(n)
        mask = prices > 0
        macd_norm[mask] = macd[mask] / prices[mask]
        features.append(macd_norm)
        
        # Volume features (if available)
        if volumes is not None:
            vol_ma = np.zeros(n)
            for i in range(19, n):
                vol_ma[i] = np.mean(volumes[i-19:i+1])
            vol_ratio = np.ones(n)
            mask = vol_ma > 0
            vol_ratio[mask] = volumes[mask] / vol_ma[mask]
            features.append(np.clip(vol_ratio, 0, 5))
        
        # Stack features
        feature_matrix = np.column_stack(features)
        
        # Pad to input_size
        if feature_matrix.shape[1] < self.input_size:
            padding = np.zeros((n, self.input_size - feature_matrix.shape[1]))
            feature_matrix = np.hstack([feature_matrix, padding])
        elif feature_matrix.shape[1] > self.input_size:
            feature_matrix = feature_matrix[:, :self.input_size]
        
        # Handle NaN/Inf
        feature_matrix = np.nan_to_num(feature_matrix, nan=0.0, posinf=1.0, neginf=-1.0)
        
        return feature_matrix
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI indicator"""
        n = len(prices)
        rsi = np.full(n, 50.0)
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        for i in range(period, n):
            avg_gain = np.mean(gains[i-period:i])
            avg_loss = np.mean(losses[i-period:i])
            
            if avg_loss == 0:
                rsi[i] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA"""
        ema = np.zeros(len(data))
        ema[0] = data[0]
        multiplier = 2 / (period + 1)
        
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        
        return ema
    
    def predict(
        self,
        symbol: str,
        prices: np.ndarray,
        volumes: np.ndarray = None,
        seq_len: int = 60
    ) -> PredictionResult:
        """
        Make prediction for given symbol
        
        Args:
            symbol: Stock ticker
            prices: Historical close prices
            volumes: Historical volumes (optional)
            seq_len: Lookback window
        
        Returns:
            PredictionResult with forecasts
        """
        if not TORCH_AVAILABLE:
            return self._fallback_prediction(symbol, prices)
        
        # Prepare features
        features = self.prepare_features(prices, volumes)
        
        # Get last seq_len window
        if len(features) < seq_len:
            # Pad with zeros
            padding = np.zeros((seq_len - len(features), features.shape[1]))
            features = np.vstack([padding, features])
        else:
            features = features[-seq_len:]
        
        # Convert to tensor
        x = torch.FloatTensor(features).unsqueeze(0).to(self.device)
        
        # Ensemble prediction
        all_price_preds = []
        all_vol_preds = []
        
        for model in self.models:
            model.eval()
            with torch.no_grad():
                price_pred, vol_pred = model(x)
            all_price_preds.append(price_pred.cpu().numpy())
            all_vol_preds.append(vol_pred.cpu().numpy())
        
        # Average ensemble
        avg_returns = np.mean(all_price_preds, axis=0)[0]  # (forecast_horizon,)
        avg_vol = np.mean(all_vol_preds, axis=0)[0]
        
        # Convert returns to prices
        current_price = prices[-1]
        predicted_prices = []
        last_price = current_price
        
        for ret in avg_returns:
            next_price = last_price * (1 + ret)
            predicted_prices.append(float(next_price))
            last_price = next_price
        
        # Calculate metrics
        final_price = predicted_prices[-1]
        expected_return = (final_price / current_price - 1) * 100
        
        # Direction
        if expected_return > 1:
            direction = "UP"
        elif expected_return < -1:
            direction = "DOWN"
        else:
            direction = "SIDEWAYS"
        
        # Confidence based on volatility and ensemble agreement
        pred_std = np.std(all_price_preds)
        confidence = max(0.3, min(0.95, 1 - pred_std * 10))
        
        return PredictionResult(
            symbol=symbol,
            current_price=float(current_price),
            predictions=predicted_prices,
            direction=direction,
            confidence=float(confidence),
            expected_return=float(expected_return),
            volatility_forecast=float(np.mean(avg_vol)),
            model_name="Stockformer Ensemble"
        )
    
    def _fallback_prediction(self, symbol: str, prices: np.ndarray) -> PredictionResult:
        """Simple fallback when PyTorch not available"""
        current_price = prices[-1]
        
        # Simple linear extrapolation
        if len(prices) >= 20:
            recent_return = (prices[-1] / prices[-20] - 1) / 20
        else:
            recent_return = 0.001
        
        predictions = []
        last = current_price
        for i in range(5):
            next_p = last * (1 + recent_return)
            predictions.append(float(next_p))
            last = next_p
        
        expected_return = (predictions[-1] / current_price - 1) * 100
        
        return PredictionResult(
            symbol=symbol,
            current_price=float(current_price),
            predictions=predictions,
            direction="UP" if expected_return > 0 else "DOWN",
            confidence=0.5,
            expected_return=float(expected_return),
            volatility_forecast=0.02,
            model_name="Fallback Linear"
        )
    
    def save_models(self, path: str):
        """Save all models to disk"""
        if not TORCH_AVAILABLE:
            return
        
        for i, model in enumerate(self.models):
            torch.save(model.state_dict(), f"{path}/stockformer_{i}.pt")
    
    def load_models(self, path: str):
        """Load models from disk"""
        if not TORCH_AVAILABLE:
            return
        
        for i, model in enumerate(self.models):
            try:
                model.load_state_dict(torch.load(f"{path}/stockformer_{i}.pt"))
                model.eval()
            except:
                pass
        
        self.is_trained = True


# Singleton
_stockformer = None

def get_stockformer() -> StockformerEnsemble:
    global _stockformer
    if _stockformer is None:
        _stockformer = StockformerEnsemble()
    return _stockformer


# Test
if __name__ == "__main__":
    print(f"PyTorch available: {TORCH_AVAILABLE}")
    
    # Generate sample data
    np.random.seed(42)
    prices = 50000 * np.exp(np.cumsum(0.001 + 0.02 * np.random.randn(200)))
    volumes = np.random.randint(100000, 1000000, 200)
    
    sf = StockformerEnsemble(input_size=50, forecast_horizon=5)
    
    result = sf.predict("VNM", prices, volumes)
    
    print("\n=== STOCKFORMER PREDICTION ===")
    print(f"Symbol: {result.symbol}")
    print(f"Current Price: {result.current_price:,.0f} VND")
    print(f"Direction: {result.direction}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Expected Return: {result.expected_return:+.2f}%")
    print(f"Predictions: {[f'{p:,.0f}' for p in result.predictions]}")
    print(f"Model: {result.model_name}")
