# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ML MODEL TRAINING PIPELINE                                ║
║                    Automated Training & Hyperparameter Tuning               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Features:
- Automated model training (ARIMA, Prophet, LSTM)
- Hyperparameter tuning with Optuna
- Model versioning and persistence
- Feature engineering
- Model evaluation and comparison
"""

import os
import json
import pickle
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# DATA CLASSES
# ============================================

@dataclass
class ModelMetadata:
    """Metadata for trained model"""
    model_id: str
    model_type: str
    symbol: str
    trained_at: datetime
    data_start: str
    data_end: str
    train_size: int
    metrics: Dict[str, float]
    hyperparameters: Dict[str, Any]
    feature_columns: List[str] = field(default_factory=list)
    version: str = "1.0"
    
    def to_dict(self) -> Dict:
        return {
            'model_id': self.model_id,
            'model_type': self.model_type,
            'symbol': self.symbol,
            'trained_at': self.trained_at.isoformat(),
            'data_start': self.data_start,
            'data_end': self.data_end,
            'train_size': self.train_size,
            'metrics': self.metrics,
            'hyperparameters': self.hyperparameters,
            'feature_columns': self.feature_columns,
            'version': self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ModelMetadata':
        data['trained_at'] = datetime.fromisoformat(data['trained_at'])
        return cls(**data)


@dataclass
class TrainingResult:
    """Result from model training"""
    success: bool
    model: Any
    metadata: ModelMetadata
    train_metrics: Dict[str, float]
    validation_metrics: Dict[str, float]
    error_message: str = ""


# ============================================
# FEATURE ENGINEERING
# ============================================

class FeatureEngineer:
    """
    Create features for ML models from OHLCV data
    """
    
    @staticmethod
    def create_features(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
        """
        Create comprehensive feature set
        
        Features:
        - Price-based: returns, log returns, high-low range
        - Technical: MA, EMA, RSI, MACD, BB
        - Volume: OBV, volume ratio
        - Lag features: past N days returns
        """
        feat = df.copy()
        
        # Basic price features
        feat['returns'] = feat['Close'].pct_change()
        feat['log_returns'] = np.log(feat['Close'] / feat['Close'].shift(1))
        feat['range'] = (feat['High'] - feat['Low']) / feat['Close']
        feat['body'] = (feat['Close'] - feat['Open']) / feat['Open']
        
        # Trend features
        for period in [5, 10, 20, 50]:
            feat[f'sma_{period}'] = feat['Close'].rolling(period).mean()
            feat[f'ema_{period}'] = feat['Close'].ewm(span=period).mean()
            feat[f'price_to_sma_{period}'] = feat['Close'] / feat[f'sma_{period}']
        
        # Momentum features
        feat['rsi'] = FeatureEngineer._calculate_rsi(feat['Close'], 14)
        feat['macd'], feat['macd_signal'] = FeatureEngineer._calculate_macd(feat['Close'])
        feat['macd_hist'] = feat['macd'] - feat['macd_signal']
        
        # Volatility features
        feat['atr'] = FeatureEngineer._calculate_atr(feat, 14)
        feat['bb_width'] = FeatureEngineer._calculate_bb_width(feat['Close'], 20)
        
        # Volume features
        feat['volume_ratio'] = feat['Volume'] / feat['Volume'].rolling(20).mean()
        feat['obv'] = (np.sign(feat['returns']) * feat['Volume']).cumsum()
        
        # Lag features
        for lag in range(1, lookback + 1):
            feat[f'return_lag_{lag}'] = feat['returns'].shift(lag)
        
        # Target variable (next day return)
        feat['target'] = feat['returns'].shift(-1)
        
        return feat.dropna()
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def _calculate_macd(prices: pd.Series) -> Tuple[pd.Series, pd.Series]:
        ema12 = prices.ewm(span=12).mean()
        ema26 = prices.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        return macd, signal
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()
    
    @staticmethod
    def _calculate_bb_width(prices: pd.Series, period: int = 20) -> pd.Series:
        sma = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        return (4 * std) / sma


# ============================================
# MODEL TRAINERS
# ============================================

class BaseModelTrainer:
    """Base class for model trainers"""
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
    
    def train(self, df: pd.DataFrame, symbol: str, **kwargs) -> TrainingResult:
        raise NotImplementedError
    
    def save_model(self, model: Any, metadata: ModelMetadata) -> str:
        """Save model and metadata"""
        model_path = self.model_dir / f"{metadata.model_id}.pkl"
        meta_path = self.model_dir / f"{metadata.model_id}_meta.json"
        
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        with open(meta_path, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
        
        logger.info(f"Model saved: {model_path}")
        return str(model_path)
    
    def load_model(self, model_id: str) -> Tuple[Any, ModelMetadata]:
        """Load model and metadata"""
        model_path = self.model_dir / f"{model_id}.pkl"
        meta_path = self.model_dir / f"{model_id}_meta.json"
        
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        with open(meta_path, 'r') as f:
            metadata = ModelMetadata.from_dict(json.load(f))
        
        return model, metadata


class GradientBoostingTrainer(BaseModelTrainer):
    """
    Gradient Boosting model trainer (XGBoost/LightGBM compatible)
    Uses sklearn's GradientBoostingRegressor as fallback
    """
    
    def train(self, df: pd.DataFrame, symbol: str, 
              tune_hyperparameters: bool = True,
              n_trials: int = 50,
              **kwargs) -> TrainingResult:
        """
        Train Gradient Boosting model
        
        Args:
            df: OHLCV DataFrame
            symbol: Stock symbol
            tune_hyperparameters: Whether to use Optuna for tuning
            n_trials: Number of Optuna trials
        """
        try:
            # Create features
            feat_df = FeatureEngineer.create_features(df)
            
            # Split train/validation
            train_size = int(len(feat_df) * 0.8)
            train = feat_df.iloc[:train_size]
            val = feat_df.iloc[train_size:]
            
            # Feature columns (exclude target)
            feature_cols = [c for c in feat_df.columns if c not in ['target', 'Open', 'High', 'Low', 'Close', 'Volume']]
            
            X_train = train[feature_cols].values
            y_train = train['target'].values
            X_val = val[feature_cols].values
            y_val = val['target'].values
            
            # Get best hyperparameters
            if tune_hyperparameters:
                best_params = self._tune_hyperparameters(X_train, y_train, n_trials)
            else:
                best_params = {
                    'n_estimators': 100,
                    'max_depth': 5,
                    'learning_rate': 0.1,
                    'min_samples_split': 5
                }
            
            # Train model
            from sklearn.ensemble import GradientBoostingRegressor
            
            model = GradientBoostingRegressor(**best_params, random_state=42)
            model.fit(X_train, y_train)
            
            # Evaluate
            train_preds = model.predict(X_train)
            val_preds = model.predict(X_val)
            
            train_metrics = self._calculate_metrics(y_train, train_preds)
            val_metrics = self._calculate_metrics(y_val, val_preds)
            
            # Create metadata
            model_id = f"gbm_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            metadata = ModelMetadata(
                model_id=model_id,
                model_type="GradientBoosting",
                symbol=symbol,
                trained_at=datetime.now(),
                data_start=str(df.index[0]),
                data_end=str(df.index[-1]),
                train_size=train_size,
                metrics=val_metrics,
                hyperparameters=best_params,
                feature_columns=feature_cols
            )
            
            # Save model
            self.save_model(model, metadata)
            
            return TrainingResult(
                success=True,
                model=model,
                metadata=metadata,
                train_metrics=train_metrics,
                validation_metrics=val_metrics
            )
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return TrainingResult(
                success=False,
                model=None,
                metadata=None,
                train_metrics={},
                validation_metrics={},
                error_message=str(e)
            )
    
    def _tune_hyperparameters(self, X: np.ndarray, y: np.ndarray, 
                               n_trials: int = 50) -> Dict:
        """Tune hyperparameters using Optuna"""
        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)
            
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.model_selection import cross_val_score
            
            def objective(trial):
                params = {
                    'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                    'max_depth': trial.suggest_int('max_depth', 3, 10),
                    'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                    'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
                    'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10)
                }
                
                model = GradientBoostingRegressor(**params, random_state=42)
                scores = cross_val_score(model, X, y, cv=5, scoring='neg_mean_squared_error')
                return scores.mean()
            
            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
            
            logger.info(f"Best params: {study.best_params}")
            return study.best_params
            
        except ImportError:
            logger.warning("Optuna not installed, using default params")
            return {
                'n_estimators': 100,
                'max_depth': 5,
                'learning_rate': 0.1,
                'min_samples_split': 5
            }
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """Calculate regression metrics"""
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae = mean_absolute_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)
        
        # Direction accuracy
        direction_correct = np.mean(np.sign(y_true) == np.sign(y_pred))
        
        return {
            'rmse': round(rmse, 6),
            'mae': round(mae, 6),
            'r2': round(r2, 4),
            'direction_accuracy': round(direction_correct, 4)
        }


class LSTMTrainer(BaseModelTrainer):
    """
    LSTM Neural Network trainer for time series forecasting
    """
    
    def train(self, df: pd.DataFrame, symbol: str,
              lookback: int = 60,
              epochs: int = 50,
              batch_size: int = 32,
              **kwargs) -> TrainingResult:
        """
        Train LSTM model
        
        Args:
            df: OHLCV DataFrame
            symbol: Stock symbol
            lookback: Number of past days to use
            epochs: Training epochs
            batch_size: Batch size
        """
        try:
            # Try importing TensorFlow
            try:
                import tensorflow as tf
                from tensorflow.keras.models import Sequential
                from tensorflow.keras.layers import LSTM, Dense, Dropout
                from sklearn.preprocessing import MinMaxScaler
            except ImportError:
                logger.error("TensorFlow not installed")
                return TrainingResult(
                    success=False,
                    model=None,
                    metadata=None,
                    train_metrics={},
                    validation_metrics={},
                    error_message="TensorFlow not installed"
                )
            
            # Prepare data
            prices = df['Close'].values.reshape(-1, 1)
            scaler = MinMaxScaler()
            scaled_prices = scaler.fit_transform(prices)
            
            # Create sequences
            X, y = [], []
            for i in range(lookback, len(scaled_prices)):
                X.append(scaled_prices[i-lookback:i, 0])
                y.append(scaled_prices[i, 0])
            
            X, y = np.array(X), np.array(y)
            X = X.reshape((X.shape[0], X.shape[1], 1))
            
            # Split train/validation
            train_size = int(len(X) * 0.8)
            X_train, X_val = X[:train_size], X[train_size:]
            y_train, y_val = y[:train_size], y[train_size:]
            
            # Build model
            model = Sequential([
                LSTM(50, return_sequences=True, input_shape=(lookback, 1)),
                Dropout(0.2),
                LSTM(50, return_sequences=False),
                Dropout(0.2),
                Dense(25),
                Dense(1)
            ])
            
            model.compile(optimizer='adam', loss='mse')
            
            # Train
            history = model.fit(
                X_train, y_train,
                epochs=epochs,
                batch_size=batch_size,
                validation_data=(X_val, y_val),
                verbose=0
            )
            
            # Evaluate
            train_loss = model.evaluate(X_train, y_train, verbose=0)
            val_loss = model.evaluate(X_val, y_val, verbose=0)
            
            train_metrics = {'mse': train_loss, 'rmse': np.sqrt(train_loss)}
            val_metrics = {'mse': val_loss, 'rmse': np.sqrt(val_loss)}
            
            # Create metadata
            model_id = f"lstm_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            metadata = ModelMetadata(
                model_id=model_id,
                model_type="LSTM",
                symbol=symbol,
                trained_at=datetime.now(),
                data_start=str(df.index[0]),
                data_end=str(df.index[-1]),
                train_size=train_size,
                metrics=val_metrics,
                hyperparameters={
                    'lookback': lookback,
                    'epochs': epochs,
                    'batch_size': batch_size
                }
            )
            
            # Save model (use keras format)
            model_path = self.model_dir / f"{model_id}.keras"
            model.save(model_path)
            
            # Save scaler
            scaler_path = self.model_dir / f"{model_id}_scaler.pkl"
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
            
            return TrainingResult(
                success=True,
                model=model,
                metadata=metadata,
                train_metrics=train_metrics,
                validation_metrics=val_metrics
            )
            
        except Exception as e:
            logger.error(f"LSTM training failed: {e}")
            return TrainingResult(
                success=False,
                model=None,
                metadata=None,
                train_metrics={},
                validation_metrics={},
                error_message=str(e)
            )


# ============================================
# TRAINING PIPELINE
# ============================================

class MLPipeline:
    """
    Unified ML Training Pipeline
    """
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        self.trainers = {
            'gbm': GradientBoostingTrainer(model_dir),
            'lstm': LSTMTrainer(model_dir)
        }
    
    def train_all(self, df: pd.DataFrame, symbol: str,
                  models: List[str] = None) -> Dict[str, TrainingResult]:
        """
        Train multiple models
        
        Args:
            df: OHLCV DataFrame
            symbol: Stock symbol
            models: List of model types to train (default: all)
        """
        if models is None:
            models = list(self.trainers.keys())
        
        results = {}
        
        for model_type in models:
            if model_type in self.trainers:
                logger.info(f"Training {model_type} for {symbol}...")
                result = self.trainers[model_type].train(df, symbol)
                results[model_type] = result
                
                if result.success:
                    logger.info(f"  ✅ {model_type}: RMSE={result.validation_metrics.get('rmse', 'N/A')}")
                else:
                    logger.error(f"  ❌ {model_type}: {result.error_message}")
        
        return results
    
    def get_best_model(self, symbol: str) -> Optional[Tuple[Any, ModelMetadata]]:
        """Get best model for a symbol based on validation metrics"""
        models = self.list_models(symbol)
        
        if not models:
            return None
        
        # Sort by RMSE (lowest is best)
        best_model = min(models, key=lambda x: x.metrics.get('rmse', float('inf')))
        
        trainer = self.trainers.get(best_model.model_type.lower())
        if trainer:
            return trainer.load_model(best_model.model_id)
        
        return None
    
    def list_models(self, symbol: str = None) -> List[ModelMetadata]:
        """List all trained models"""
        models = []
        
        for meta_file in self.model_dir.glob("*_meta.json"):
            with open(meta_file, 'r') as f:
                metadata = ModelMetadata.from_dict(json.load(f))
                
                if symbol is None or metadata.symbol == symbol:
                    models.append(metadata)
        
        return sorted(models, key=lambda x: x.trained_at, reverse=True)


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    print("Testing ML Pipeline...")
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=500, freq='D')
    base_price = 50
    returns = np.random.normal(0.001, 0.02, 500)
    prices = base_price * np.cumprod(1 + returns)
    
    df = pd.DataFrame({
        'Open': prices * (1 + np.random.uniform(-0.01, 0.01, 500)),
        'High': prices * (1 + np.random.uniform(0, 0.02, 500)),
        'Low': prices * (1 - np.random.uniform(0, 0.02, 500)),
        'Close': prices,
        'Volume': np.random.randint(100000, 1000000, 500)
    }, index=dates)
    
    # Test feature engineering
    print("\n1. Feature Engineering:")
    feat_df = FeatureEngineer.create_features(df)
    print(f"   Created {len(feat_df.columns)} features")
    
    # Test GBM training
    print("\n2. Gradient Boosting Training:")
    pipeline = MLPipeline(model_dir="test_models")
    
    result = pipeline.trainers['gbm'].train(
        df, 'TEST', 
        tune_hyperparameters=False  # Skip tuning for test
    )
    
    if result.success:
        print(f"   ✅ Training successful")
        print(f"   Train RMSE: {result.train_metrics['rmse']:.6f}")
        print(f"   Val RMSE: {result.validation_metrics['rmse']:.6f}")
        print(f"   Direction Accuracy: {result.validation_metrics['direction_accuracy']:.2%}")
    else:
        print(f"   ❌ Training failed: {result.error_message}")
    
    print("\nML Pipeline ready!")
