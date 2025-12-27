"""
Forecasting Models - Level 3/4 Agentic Architecture
Implements multiple forecasting models for price prediction
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')


class ModelType(Enum):
    """Available forecasting model types"""
    ARIMA = "ARIMA"
    PROPHET = "PROPHET"
    LSTM = "LSTM"
    GBM = "GBM"              # Geometric Brownian Motion (Monte Carlo)
    ENSEMBLE = "ENSEMBLE"     # Combination of all models


@dataclass
class ForecastResult:
    """Result from a forecasting model"""
    model_type: ModelType
    symbol: str
    forecast_dates: List[datetime]
    predicted_prices: List[float]
    confidence_lower: List[float]
    confidence_upper: List[float]
    confidence_level: float  # e.g., 0.95 for 95%
    metrics: Dict[str, float]  # MAE, RMSE, MAPE, etc.
    training_info: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'model_type': self.model_type.value,
            'symbol': self.symbol,
            'forecast_dates': [d.isoformat() for d in self.forecast_dates],
            'predicted_prices': self.predicted_prices,
            'confidence_lower': self.confidence_lower,
            'confidence_upper': self.confidence_upper,
            'confidence_level': self.confidence_level,
            'metrics': self.metrics,
            'training_info': self.training_info,
            'timestamp': self.timestamp.isoformat()
        }
    
    def get_expected_return(self, current_price: float) -> float:
        """Calculate expected return from forecast"""
        if not self.predicted_prices:
            return 0.0
        final_price = self.predicted_prices[-1]
        return ((final_price / current_price) - 1) * 100
    
    def get_probability_of_profit(self) -> float:
        """Estimate probability of profit based on confidence intervals"""
        # Count how many forecasts have lower bound above start
        if not self.predicted_prices or not self.confidence_lower:
            return 0.5
        
        start_price = self.predicted_prices[0]
        profitable_count = sum(1 for lower in self.confidence_lower if lower > start_price)
        return profitable_count / len(self.confidence_lower)


class ARIMAForecaster:
    """
    ARIMA (AutoRegressive Integrated Moving Average) model.
    Good for: Short-term forecasting with stable trends.
    """
    
    def __init__(self, order: Tuple[int, int, int] = (5, 1, 2)):
        """
        Initialize ARIMA model.
        
        Args:
            order: (p, d, q) order of the ARIMA model
                   p: AR order
                   d: degree of differencing
                   q: MA order
        """
        self.order = order
        self.model = None
        self.fitted = False
    
    def fit(self, prices: np.ndarray):
        """Fit ARIMA model to price data"""
        try:
            from statsmodels.tsa.arima.model import ARIMA
            
            # Use log prices for better stationarity
            log_prices = np.log(prices)
            
            self.model = ARIMA(log_prices, order=self.order)
            self.fit_result = self.model.fit()
            self.fitted = True
            
        except ImportError:
            # Fallback to simple AR model
            self._fit_simple_ar(prices)
        except Exception as e:
            print(f"ARIMA fit error: {e}")
            self._fit_simple_ar(prices)
    
    def _fit_simple_ar(self, prices: np.ndarray):
        """Simple AR fallback when statsmodels not available"""
        self.last_prices = prices[-5:]
        self.trend = np.mean(np.diff(prices[-20:])) if len(prices) > 20 else 0
        self.fitted = True
    
    def forecast(self, steps: int, confidence: float = 0.95) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generate forecast.
        
        Returns:
            Tuple of (predictions, lower_bound, upper_bound)
        """
        if not self.fitted:
            raise ValueError("Model not fitted")
        
        try:
            # Use statsmodels forecast
            forecast_result = self.fit_result.get_forecast(steps=steps)
            pred_mean = np.exp(forecast_result.predicted_mean)
            conf_int = forecast_result.conf_int(alpha=1-confidence)
            lower = np.exp(conf_int.iloc[:, 0].values)
            upper = np.exp(conf_int.iloc[:, 1].values)
            
            return pred_mean.values, lower, upper
            
        except AttributeError:
            # Fallback simple forecast
            predictions = []
            last_price = self.last_prices[-1]
            
            for i in range(steps):
                next_price = last_price * (1 + self.trend / last_price)
                predictions.append(next_price)
                last_price = next_price
            
            predictions = np.array(predictions)
            volatility = abs(self.trend) * 2 + 0.02 * predictions
            lower = predictions - 1.96 * volatility
            upper = predictions + 1.96 * volatility
            
            return predictions, lower, upper


class ProphetForecaster:
    """
    Facebook Prophet model.
    Good for: Data with strong seasonality and holidays.
    """
    
    def __init__(self, 
                 yearly_seasonality: bool = True,
                 weekly_seasonality: bool = True,
                 daily_seasonality: bool = False):
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.model = None
        self.fitted = False
    
    def fit(self, df: pd.DataFrame, date_col: str = 'date', value_col: str = 'close'):
        """
        Fit Prophet model.
        
        Args:
            df: DataFrame with date and value columns
            date_col: Name of date column
            value_col: Name of value column
        """
        try:
            from prophet import Prophet
            
            # Prepare data in Prophet format
            prophet_df = pd.DataFrame({
                'ds': pd.to_datetime(df[date_col]),
                'y': df[value_col]
            })
            
            self.model = Prophet(
                yearly_seasonality=self.yearly_seasonality,
                weekly_seasonality=self.weekly_seasonality,
                daily_seasonality=self.daily_seasonality,
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=10
            )
            
            # Vietnam holidays
            self.model.add_country_holidays(country_name='VN')
            
            self.model.fit(prophet_df)
            self.fitted = True
            
        except ImportError:
            # Fallback to trend-based model
            self._fit_trend_model(df, value_col)
        except Exception as e:
            print(f"Prophet fit error: {e}")
            self._fit_trend_model(df, value_col)
    
    def _fit_trend_model(self, df: pd.DataFrame, value_col: str):
        """Fallback trend-based model"""
        prices = df[value_col].values
        
        # Calculate trend using simple linear regression
        x = np.arange(len(prices))
        coeffs = np.polyfit(x, prices, 1)
        
        self.trend_coef = coeffs[0]
        self.intercept = coeffs[1]
        self.last_index = len(prices) - 1
        self.volatility = np.std(prices[-20:])
        self.fitted = True
    
    def forecast(self, periods: int, confidence: float = 0.95) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate forecast using Prophet or fallback"""
        if not self.fitted:
            raise ValueError("Model not fitted")
        
        try:
            # Use Prophet forecast
            future = self.model.make_future_dataframe(periods=periods)
            forecast = self.model.predict(future)
            
            pred = forecast['yhat'].values[-periods:]
            lower = forecast['yhat_lower'].values[-periods:]
            upper = forecast['yhat_upper'].values[-periods:]
            
            return pred, lower, upper
            
        except AttributeError:
            # Fallback forecast
            x_future = np.arange(self.last_index + 1, self.last_index + 1 + periods)
            pred = self.trend_coef * x_future + self.intercept
            
            # Widen confidence interval over time
            time_factor = np.sqrt(np.arange(1, periods + 1))
            margin = 1.96 * self.volatility * time_factor
            
            return pred, pred - margin, pred + margin


class LSTMForecaster:
    """
    LSTM (Long Short-Term Memory) neural network.
    Good for: Complex patterns and longer-term forecasts.
    """
    
    def __init__(self, 
                 lookback: int = 60,
                 units: int = 50,
                 epochs: int = 50):
        self.lookback = lookback
        self.units = units
        self.epochs = epochs
        self.model = None
        self.scaler = None
        self.fitted = False
    
    def fit(self, prices: np.ndarray):
        """
        Fit LSTM model to price data.
        
        Note: Requires TensorFlow/Keras. Falls back to RNN simulation if not available.
        """
        try:
            from sklearn.preprocessing import MinMaxScaler
            from tensorflow.keras.models import Sequential
            from tensorflow.keras.layers import LSTM, Dense, Dropout
            
            # Scale data
            self.scaler = MinMaxScaler()
            scaled_prices = self.scaler.fit_transform(prices.reshape(-1, 1))
            
            # Create sequences
            X, y = self._create_sequences(scaled_prices)
            
            # Build model
            self.model = Sequential([
                LSTM(self.units, return_sequences=True, input_shape=(self.lookback, 1)),
                Dropout(0.2),
                LSTM(self.units, return_sequences=False),
                Dropout(0.2),
                Dense(25),
                Dense(1)
            ])
            
            self.model.compile(optimizer='adam', loss='mse')
            self.model.fit(X, y, batch_size=32, epochs=self.epochs, verbose=0)
            self.fitted = True
            
            # Store last sequence for prediction
            self.last_sequence = scaled_prices[-self.lookback:]
            
        except ImportError:
            # Fallback to EMA-based prediction
            self._fit_ema_model(prices)
        except Exception as e:
            print(f"LSTM fit error: {e}")
            self._fit_ema_model(prices)
    
    def _create_sequences(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM training"""
        X, y = [], []
        for i in range(self.lookback, len(data)):
            X.append(data[i-self.lookback:i, 0])
            y.append(data[i, 0])
        return np.array(X).reshape(-1, self.lookback, 1), np.array(y)
    
    def _fit_ema_model(self, prices: np.ndarray):
        """Fallback EMA-based model"""
        self.ema_short = pd.Series(prices).ewm(span=10).mean().iloc[-1]
        self.ema_long = pd.Series(prices).ewm(span=30).mean().iloc[-1]
        self.last_price = prices[-1]
        self.volatility = np.std(prices[-20:]) / np.mean(prices[-20:])
        self.fitted = True
    
    def forecast(self, steps: int, confidence: float = 0.95) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate LSTM forecast"""
        if not self.fitted:
            raise ValueError("Model not fitted")
        
        try:
            # Use LSTM prediction
            predictions = []
            current_sequence = self.last_sequence.copy().reshape(1, self.lookback, 1)
            
            for _ in range(steps):
                pred = self.model.predict(current_sequence, verbose=0)
                predictions.append(pred[0, 0])
                
                # Roll sequence and add prediction
                current_sequence = np.roll(current_sequence, -1, axis=1)
                current_sequence[0, -1, 0] = pred[0, 0]
            
            # Inverse scale
            predictions = np.array(predictions).reshape(-1, 1)
            predictions = self.scaler.inverse_transform(predictions).flatten()
            
            # Estimate confidence interval based on training volatility
            margin = predictions * 0.05 * np.sqrt(np.arange(1, steps + 1))
            
            return predictions, predictions - margin, predictions + margin
            
        except AttributeError:
            # Fallback EMA-based forecast
            trend = (self.ema_short - self.ema_long) / self.ema_long
            
            predictions = []
            price = self.last_price
            
            for i in range(steps):
                price = price * (1 + trend * 0.1)  # Damped trend
                predictions.append(price)
            
            predictions = np.array(predictions)
            margin = predictions * self.volatility * np.sqrt(np.arange(1, steps + 1))
            
            return predictions, predictions - margin, predictions + margin


class GBMForecaster:
    """
    Geometric Brownian Motion Monte Carlo simulation.
    Good for: Risk analysis and probability distributions.
    """
    
    def __init__(self, num_simulations: int = 10000):
        self.num_simulations = num_simulations
        self.mu = 0  # drift
        self.sigma = 0  # volatility
        self.last_price = 0
        self.fitted = False
    
    def fit(self, prices: np.ndarray, risk_free_rate: float = 0.05):
        """
        Fit GBM parameters from historical prices.
        
        Args:
            prices: Historical price array
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        returns = np.diff(np.log(prices))
        
        # Annualize parameters (assuming daily data)
        self.sigma = np.std(returns) * np.sqrt(252)
        self.mu = risk_free_rate  # Use risk-free rate as drift
        self.last_price = prices[-1]
        self.fitted = True
    
    def forecast(self, steps: int, confidence: float = 0.95) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Run Monte Carlo simulation for price forecast.
        
        Returns median forecast with confidence intervals.
        """
        if not self.fitted:
            raise ValueError("Model not fitted")
        
        dt = 1 / 252  # Daily time step
        
        # Generate random paths
        np.random.seed(42)  # For reproducibility
        
        paths = np.zeros((self.num_simulations, steps))
        paths[:, 0] = self.last_price
        
        for t in range(1, steps):
            z = np.random.standard_normal(self.num_simulations)
            paths[:, t] = paths[:, t-1] * np.exp(
                (self.mu - 0.5 * self.sigma**2) * dt + 
                self.sigma * np.sqrt(dt) * z
            )
        
        # Calculate percentiles
        alpha = 1 - confidence
        predictions = np.median(paths, axis=0)
        lower = np.percentile(paths, alpha/2 * 100, axis=0)
        upper = np.percentile(paths, (1 - alpha/2) * 100, axis=0)
        
        return predictions, lower, upper


class EnsembleForecaster:
    """
    Ensemble model combining multiple forecasters.
    Weights models based on recent performance.
    """
    
    def __init__(self, models: Dict[ModelType, float] = None):
        """
        Initialize ensemble with model weights.
        
        Args:
            models: Dict of {ModelType: weight}
        """
        self.model_weights = models or {
            ModelType.ARIMA: 0.25,
            ModelType.PROPHET: 0.25,
            ModelType.LSTM: 0.25,
            ModelType.GBM: 0.25
        }
        self.forecasters: Dict[ModelType, Any] = {}
        self.fitted = False
    
    def fit(self, df: pd.DataFrame, date_col: str = 'date', value_col: str = 'close'):
        """Fit all component models"""
        prices = df[value_col].values
        
        # Initialize and fit each model
        self.forecasters[ModelType.ARIMA] = ARIMAForecaster()
        self.forecasters[ModelType.ARIMA].fit(prices)
        
        self.forecasters[ModelType.PROPHET] = ProphetForecaster()
        self.forecasters[ModelType.PROPHET].fit(df, date_col, value_col)
        
        self.forecasters[ModelType.LSTM] = LSTMForecaster()
        self.forecasters[ModelType.LSTM].fit(prices)
        
        self.forecasters[ModelType.GBM] = GBMForecaster()
        self.forecasters[ModelType.GBM].fit(prices)
        
        self.fitted = True
    
    def forecast(self, steps: int, confidence: float = 0.95) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate weighted ensemble forecast"""
        if not self.fitted:
            raise ValueError("Models not fitted")
        
        all_predictions = []
        all_lower = []
        all_upper = []
        weights = []
        
        for model_type, forecaster in self.forecasters.items():
            try:
                pred, lower, upper = forecaster.forecast(steps, confidence)
                all_predictions.append(pred)
                all_lower.append(lower)
                all_upper.append(upper)
                weights.append(self.model_weights[model_type])
            except Exception as e:
                print(f"Error forecasting with {model_type}: {e}")
        
        if not all_predictions:
            raise ValueError("No models produced forecasts")
        
        # Normalize weights
        weights = np.array(weights)
        weights = weights / weights.sum()
        
        # Weighted average
        predictions = np.average(all_predictions, axis=0, weights=weights)
        lower = np.average(all_lower, axis=0, weights=weights)
        upper = np.average(all_upper, axis=0, weights=weights)
        
        return predictions, lower, upper


class ForecastingEngine:
    """
    Main forecasting engine that orchestrates all models.
    """
    
    def __init__(self):
        self.models: Dict[ModelType, Any] = {}
        self.results_cache: Dict[str, ForecastResult] = {}
    
    def forecast(self, df: pd.DataFrame, 
                 symbol: str,
                 steps: int = 10,
                 model_type: ModelType = ModelType.ENSEMBLE,
                 date_col: str = 'date',
                 value_col: str = 'close',
                 confidence: float = 0.95) -> ForecastResult:
        """
        Generate price forecast.
        
        Args:
            df: Historical OHLCV data
            symbol: Stock symbol
            steps: Number of days to forecast
            model_type: Which model to use
            date_col: Date column name
            value_col: Value column name
            confidence: Confidence level for intervals
            
        Returns:
            ForecastResult with predictions
        """
        prices = df[value_col].values
        
        # Select and fit model
        if model_type == ModelType.ARIMA:
            forecaster = ARIMAForecaster()
            forecaster.fit(prices)
        elif model_type == ModelType.PROPHET:
            forecaster = ProphetForecaster()
            forecaster.fit(df, date_col, value_col)
        elif model_type == ModelType.LSTM:
            forecaster = LSTMForecaster()
            forecaster.fit(prices)
        elif model_type == ModelType.GBM:
            forecaster = GBMForecaster()
            forecaster.fit(prices)
        else:  # ENSEMBLE
            forecaster = EnsembleForecaster()
            forecaster.fit(df, date_col, value_col)
        
        # Generate forecast
        predictions, lower, upper = forecaster.forecast(steps, confidence)
        
        # Generate forecast dates
        last_date = pd.to_datetime(df[date_col].iloc[-1])
        forecast_dates = [last_date + timedelta(days=i+1) for i in range(steps)]
        
        # Calculate metrics (use last 20% of data as validation)
        split_idx = int(len(prices) * 0.8)
        train = prices[:split_idx]
        test = prices[split_idx:]
        
        metrics = self._calculate_metrics(train, test, forecaster, len(test))
        
        result = ForecastResult(
            model_type=model_type,
            symbol=symbol,
            forecast_dates=forecast_dates,
            predicted_prices=predictions.tolist(),
            confidence_lower=lower.tolist(),
            confidence_upper=upper.tolist(),
            confidence_level=confidence,
            metrics=metrics,
            training_info={
                'data_points': len(prices),
                'train_size': split_idx,
                'test_size': len(test),
                'last_price': float(prices[-1])
            }
        )
        
        # Cache result
        cache_key = f"{symbol}_{model_type.value}_{steps}"
        self.results_cache[cache_key] = result
        
        return result
    
    def _calculate_metrics(self, train: np.ndarray, test: np.ndarray,
                           forecaster: Any, steps: int) -> Dict[str, float]:
        """Calculate forecast accuracy metrics"""
        try:
            # Refit on training data and predict test period
            if hasattr(forecaster, 'fit'):
                forecaster.fit(train)
                pred, _, _ = forecaster.forecast(min(steps, len(test)))
                
                actual = test[:len(pred)]
                
                mae = np.mean(np.abs(pred - actual))
                rmse = np.sqrt(np.mean((pred - actual) ** 2))
                mape = np.mean(np.abs((pred - actual) / actual)) * 100
                
                return {
                    'MAE': round(mae, 4),
                    'RMSE': round(rmse, 4),
                    'MAPE': round(mape, 2)
                }
        except Exception:
            pass
        
        return {'MAE': 0, 'RMSE': 0, 'MAPE': 0}
    
    def compare_models(self, df: pd.DataFrame,
                       symbol: str,
                       steps: int = 10) -> Dict[str, ForecastResult]:
        """
        Compare all models and return results.
        
        Returns:
            Dict of {model_name: ForecastResult}
        """
        results = {}
        
        for model_type in [ModelType.ARIMA, ModelType.PROPHET, 
                          ModelType.LSTM, ModelType.GBM, ModelType.ENSEMBLE]:
            try:
                result = self.forecast(df, symbol, steps, model_type)
                results[model_type.value] = result
            except Exception as e:
                print(f"Error with {model_type}: {e}")
        
        return results
    
    def get_best_model(self, df: pd.DataFrame,
                       symbol: str,
                       metric: str = 'MAPE') -> Tuple[ModelType, ForecastResult]:
        """
        Find the best performing model based on specified metric.
        
        Returns:
            Tuple of (best_model_type, forecast_result)
        """
        results = self.compare_models(df, symbol)
        
        best_model = None
        best_result = None
        best_score = float('inf')
        
        for model_name, result in results.items():
            score = result.metrics.get(metric, float('inf'))
            if score < best_score:
                best_score = score
                best_model = ModelType(model_name)
                best_result = result
        
        return best_model, best_result
