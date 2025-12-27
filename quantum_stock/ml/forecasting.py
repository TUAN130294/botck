# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    TIME SERIES FORECASTING MODELS                            ║
║                    ARIMA, Prophet, Ensemble Methods                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

P1 Implementation - Advanced forecasting for VN-QUANT
"""

import logging
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# DATA MODELS
# ============================================

@dataclass
class ForecastResult:
    """Forecast result container"""
    model_name: str
    symbol: str
    forecast_dates: List[datetime]
    forecast_values: List[float]
    lower_bound: List[float]
    upper_bound: List[float]
    confidence: float
    metrics: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({
            'date': self.forecast_dates,
            'forecast': self.forecast_values,
            'lower': self.lower_bound,
            'upper': self.upper_bound
        })


# ============================================
# ARIMA FORECASTER
# ============================================

class ARIMAForecaster:
    """
    ARIMA/SARIMA Time Series Forecasting
    
    Auto-ARIMA with seasonal decomposition
    """
    
    def __init__(self):
        self.model = None
        self.fitted = False
        self.order = None
        self.seasonal_order = None
    
    def fit(self, data: pd.Series, 
            order: Tuple[int, int, int] = None,
            seasonal_order: Tuple[int, int, int, int] = None,
            auto: bool = True) -> bool:
        """
        Fit ARIMA model
        
        Args:
            data: Time series data (pandas Series with datetime index)
            order: (p, d, q) order
            seasonal_order: (P, D, Q, s) seasonal order
            auto: Use auto-ARIMA to find best order
        """
        try:
            from statsmodels.tsa.arima.model import ARIMA
            from statsmodels.tsa.statespace.sarimax import SARIMAX
            
            if auto:
                # Auto-select order using AIC
                order, seasonal_order = self._auto_order(data)
            
            self.order = order or (1, 1, 1)
            self.seasonal_order = seasonal_order
            
            if seasonal_order:
                self.model = SARIMAX(
                    data,
                    order=self.order,
                    seasonal_order=self.seasonal_order,
                    enforce_stationarity=False,
                    enforce_invertibility=False
                ).fit(disp=False)
            else:
                self.model = ARIMA(
                    data,
                    order=self.order
                ).fit()
            
            self.fitted = True
            logger.info(f"ARIMA fitted with order={self.order}")
            return True
            
        except ImportError:
            logger.error("statsmodels not installed. Run: pip install statsmodels")
            return False
        except Exception as e:
            logger.error(f"ARIMA fit error: {e}")
            return False
    
    def _auto_order(self, data: pd.Series, 
                    max_p: int = 3, max_d: int = 2, max_q: int = 3
                    ) -> Tuple[Tuple, Optional[Tuple]]:
        """Find best ARIMA order using grid search"""
        try:
            from statsmodels.tsa.arima.model import ARIMA
            
            best_aic = float('inf')
            best_order = (1, 1, 1)
            
            for p in range(max_p + 1):
                for d in range(max_d + 1):
                    for q in range(max_q + 1):
                        if p == 0 and q == 0:
                            continue
                        try:
                            model = ARIMA(data, order=(p, d, q)).fit()
                            if model.aic < best_aic:
                                best_aic = model.aic
                                best_order = (p, d, q)
                        except:
                            continue
            
            logger.info(f"Auto-ARIMA selected order: {best_order} (AIC: {best_aic:.2f})")
            return best_order, None
            
        except Exception as e:
            logger.warning(f"Auto-order failed: {e}")
            return (1, 1, 1), None
    
    def forecast(self, steps: int = 10, confidence: float = 0.95) -> ForecastResult:
        """Generate forecast"""
        if not self.fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Generate forecast
        forecast = self.model.get_forecast(steps=steps)
        mean = forecast.predicted_mean
        conf_int = forecast.conf_int(alpha=1 - confidence)
        
        # Calculate metrics
        metrics = {
            'aic': self.model.aic,
            'bic': self.model.bic,
            'rmse': np.sqrt(self.model.mse)
        }
        
        # Generate dates
        last_date = mean.index[-1] if hasattr(mean.index[-1], 'date') else datetime.now()
        dates = [last_date + timedelta(days=i) for i in range(1, steps + 1)]
        
        return ForecastResult(
            model_name='ARIMA',
            symbol='',
            forecast_dates=dates,
            forecast_values=mean.tolist(),
            lower_bound=conf_int.iloc[:, 0].tolist(),
            upper_bound=conf_int.iloc[:, 1].tolist(),
            confidence=confidence,
            metrics=metrics,
            metadata={'order': self.order}
        )


# ============================================
# PROPHET FORECASTER
# ============================================

class ProphetForecaster:
    """
    Facebook Prophet Forecasting
    
    Good for data with strong seasonal effects
    """
    
    def __init__(self):
        self.model = None
        self.fitted = False
    
    def fit(self, data: pd.DataFrame,
            yearly_seasonality: bool = True,
            weekly_seasonality: bool = True,
            daily_seasonality: bool = False) -> bool:
        """
        Fit Prophet model
        
        Args:
            data: DataFrame with 'ds' (date) and 'y' (value) columns
        """
        try:
            from prophet import Prophet
            
            self.model = Prophet(
                yearly_seasonality=yearly_seasonality,
                weekly_seasonality=weekly_seasonality,
                daily_seasonality=daily_seasonality,
                interval_width=0.95
            )
            
            # Suppress Stan logging
            self.model.fit(data, suppress_stdout=True)
            self.fitted = True
            logger.info("Prophet model fitted")
            return True
            
        except ImportError:
            logger.error("Prophet not installed. Run: pip install prophet")
            return False
        except Exception as e:
            logger.error(f"Prophet fit error: {e}")
            return False
    
    def forecast(self, steps: int = 30) -> ForecastResult:
        """Generate forecast"""
        if not self.fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Create future dataframe
        future = self.model.make_future_dataframe(periods=steps)
        forecast = self.model.predict(future)
        
        # Get only future predictions
        future_forecast = forecast.tail(steps)
        
        return ForecastResult(
            model_name='Prophet',
            symbol='',
            forecast_dates=future_forecast['ds'].tolist(),
            forecast_values=future_forecast['yhat'].tolist(),
            lower_bound=future_forecast['yhat_lower'].tolist(),
            upper_bound=future_forecast['yhat_upper'].tolist(),
            confidence=0.95,
            metrics={
                'trend': forecast['trend'].iloc[-1],
                'seasonality_mode': self.model.seasonality_mode
            }
        )


# ============================================
# EXPONENTIAL SMOOTHING
# ============================================

class ExponentialSmoothingForecaster:
    """
    Holt-Winters Exponential Smoothing
    
    Good for trend and seasonal data
    """
    
    def __init__(self):
        self.model = None
        self.fitted = False
    
    def fit(self, data: pd.Series, 
            trend: str = 'add', 
            seasonal: str = 'add',
            seasonal_periods: int = 5) -> bool:  # 5 trading days = 1 week
        """
        Fit Holt-Winters model
        
        Args:
            data: Time series data
            trend: 'add', 'mul', or None
            seasonal: 'add', 'mul', or None
            seasonal_periods: Number of periods in a season
        """
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            
            self.model = ExponentialSmoothing(
                data,
                trend=trend,
                seasonal=seasonal,
                seasonal_periods=seasonal_periods
            ).fit()
            
            self.fitted = True
            logger.info("Exponential Smoothing fitted")
            return True
            
        except ImportError:
            logger.error("statsmodels not installed")
            return False
        except Exception as e:
            logger.error(f"ETS fit error: {e}")
            return False
    
    def forecast(self, steps: int = 10) -> ForecastResult:
        """Generate forecast"""
        if not self.fitted:
            raise ValueError("Model not fitted")
        
        forecast = self.model.forecast(steps)
        
        # Simple confidence interval (no native support in HW)
        std = np.std(self.model.resid)
        lower = forecast - 1.96 * std
        upper = forecast + 1.96 * std
        
        return ForecastResult(
            model_name='HoltWinters',
            symbol='',
            forecast_dates=[datetime.now() + timedelta(days=i) for i in range(1, steps + 1)],
            forecast_values=forecast.tolist(),
            lower_bound=lower.tolist(),
            upper_bound=upper.tolist(),
            confidence=0.95,
            metrics={
                'aic': self.model.aic,
                'sse': self.model.sse
            }
        )


# ============================================
# ENSEMBLE FORECASTER
# ============================================

class EnsembleForecaster:
    """
    Ensemble of multiple forecasting models
    
    Combines predictions from ARIMA, Prophet, ETS
    """
    
    def __init__(self):
        self.models = {}
        self.weights = {}
        self.fitted = False
    
    def fit(self, data: pd.Series, models: List[str] = None) -> bool:
        """
        Fit ensemble of models
        
        Args:
            data: Time series data
            models: List of models to include ['arima', 'ets', 'prophet']
        """
        models = models or ['arima', 'ets']
        
        # ARIMA
        if 'arima' in models:
            arima = ARIMAForecaster()
            if arima.fit(data, auto=True):
                self.models['arima'] = arima
                self.weights['arima'] = 1.0
        
        # Exponential Smoothing
        if 'ets' in models:
            ets = ExponentialSmoothingForecaster()
            if ets.fit(data):
                self.models['ets'] = ets
                self.weights['ets'] = 0.8
        
        # Prophet (requires proper formatting)
        if 'prophet' in models:
            prophet = ProphetForecaster()
            prophet_data = pd.DataFrame({
                'ds': data.index,
                'y': data.values
            })
            if prophet.fit(prophet_data):
                self.models['prophet'] = prophet
                self.weights['prophet'] = 0.9
        
        if len(self.models) > 0:
            self.fitted = True
            logger.info(f"Ensemble fitted with {len(self.models)} models")
            return True
        
        return False
    
    def forecast(self, steps: int = 10) -> ForecastResult:
        """Generate ensemble forecast"""
        if not self.fitted:
            raise ValueError("Ensemble not fitted")
        
        forecasts = {}
        total_weight = 0
        
        # Collect forecasts from each model
        for name, model in self.models.items():
            try:
                result = model.forecast(steps)
                forecasts[name] = {
                    'values': np.array(result.forecast_values),
                    'lower': np.array(result.lower_bound),
                    'upper': np.array(result.upper_bound),
                    'weight': self.weights[name]
                }
                total_weight += self.weights[name]
            except Exception as e:
                logger.warning(f"Model {name} forecast failed: {e}")
        
        if not forecasts:
            raise ValueError("All models failed to forecast")
        
        # Weighted average
        ensemble_values = np.zeros(steps)
        ensemble_lower = np.zeros(steps)
        ensemble_upper = np.zeros(steps)
        
        for name, f in forecasts.items():
            weight = f['weight'] / total_weight
            ensemble_values += f['values'] * weight
            ensemble_lower += f['lower'] * weight
            ensemble_upper += f['upper'] * weight
        
        # Generate dates
        dates = [datetime.now() + timedelta(days=i) for i in range(1, steps + 1)]
        
        return ForecastResult(
            model_name='Ensemble',
            symbol='',
            forecast_dates=dates,
            forecast_values=ensemble_values.tolist(),
            lower_bound=ensemble_lower.tolist(),
            upper_bound=ensemble_upper.tolist(),
            confidence=0.95,
            metrics={
                'models_used': list(forecasts.keys()),
                'weights': {k: v / total_weight for k, v in self.weights.items() if k in forecasts}
            }
        )


# ============================================
# MONTE CARLO FORECASTER
# ============================================

class MonteCarloForecaster:
    """
    Monte Carlo Simulation Forecaster
    
    Uses GBM (Geometric Brownian Motion) for price simulation
    """
    
    def __init__(self, n_simulations: int = 10000):
        self.n_simulations = n_simulations
        self.mu = None
        self.sigma = None
        self.last_price = None
        self.fitted = False
    
    def fit(self, prices: pd.Series) -> bool:
        """
        Fit Monte Carlo parameters from historical data
        
        Args:
            prices: Historical price series
        """
        try:
            returns = np.log(prices / prices.shift(1)).dropna()
            
            self.mu = returns.mean() * 252  # Annualized
            self.sigma = returns.std() * np.sqrt(252)  # Annualized
            self.last_price = prices.iloc[-1]
            self.fitted = True
            
            logger.info(f"Monte Carlo fitted: μ={self.mu:.4f}, σ={self.sigma:.4f}")
            return True
            
        except Exception as e:
            logger.error(f"Monte Carlo fit error: {e}")
            return False
    
    def forecast(self, days: int = 30) -> ForecastResult:
        """
        Run Monte Carlo simulation
        
        Returns forecast with percentile bounds
        """
        if not self.fitted:
            raise ValueError("Model not fitted")
        
        dt = 1 / 252  # Daily
        
        # Generate random walks
        Z = np.random.standard_normal((self.n_simulations, days))
        
        # GBM simulation
        drift = (self.mu - 0.5 * self.sigma ** 2) * dt
        diffusion = self.sigma * np.sqrt(dt) * Z
        
        returns = drift + diffusion
        price_paths = self.last_price * np.exp(np.cumsum(returns, axis=1))
        
        # Calculate statistics
        forecast_values = np.mean(price_paths, axis=0)
        lower_bound = np.percentile(price_paths, 5, axis=0)
        upper_bound = np.percentile(price_paths, 95, axis=0)
        
        # Metrics
        final_prices = price_paths[:, -1]
        prob_profit = np.mean(final_prices > self.last_price)
        var_95 = np.percentile(final_prices, 5)
        
        dates = [datetime.now() + timedelta(days=i) for i in range(1, days + 1)]
        
        return ForecastResult(
            model_name='MonteCarlo',
            symbol='',
            forecast_dates=dates,
            forecast_values=forecast_values.tolist(),
            lower_bound=lower_bound.tolist(),
            upper_bound=upper_bound.tolist(),
            confidence=0.90,  # 5-95 percentile
            metrics={
                'prob_profit': prob_profit,
                'var_95': var_95,
                'expected_return': (np.mean(final_prices) - self.last_price) / self.last_price,
                'n_simulations': self.n_simulations,
                'drift': self.mu,
                'volatility': self.sigma
            }
        )


# ============================================
# UNIFIED FORECASTER
# ============================================

class Forecaster:
    """
    Unified forecasting interface
    
    Usage:
        forecaster = Forecaster()
        result = forecaster.forecast(prices, model='arima', steps=30)
    """
    
    @staticmethod
    def forecast(data: pd.Series, 
                 model: str = 'ensemble',
                 steps: int = 30,
                 **kwargs) -> ForecastResult:
        """
        Run forecast with specified model
        
        Args:
            data: Historical price/value series
            model: 'arima', 'ets', 'prophet', 'monte_carlo', 'ensemble'
            steps: Number of steps to forecast
        """
        if model == 'arima':
            forecaster = ARIMAForecaster()
            forecaster.fit(data, **kwargs)
        elif model == 'ets':
            forecaster = ExponentialSmoothingForecaster()
            forecaster.fit(data, **kwargs)
        elif model == 'prophet':
            forecaster = ProphetForecaster()
            prophet_data = pd.DataFrame({
                'ds': data.index,
                'y': data.values
            })
            forecaster.fit(prophet_data, **kwargs)
        elif model == 'monte_carlo':
            forecaster = MonteCarloForecaster(**kwargs)
            forecaster.fit(data)
        elif model == 'ensemble':
            forecaster = EnsembleForecaster()
            forecaster.fit(data, **kwargs)
        else:
            raise ValueError(f"Unknown model: {model}")
        
        return forecaster.forecast(steps)


# ============================================
# TESTING
# ============================================

def test_forecasters():
    """Test forecasting models"""
    print("Testing Forecasting Models...")
    print("=" * 50)
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
    returns = np.random.normal(0.001, 0.02, 252)
    prices = 50 * np.cumprod(1 + returns)
    data = pd.Series(prices, index=dates)
    
    # Test Monte Carlo (always works)
    print("\n📊 Monte Carlo Forecast:")
    mc = MonteCarloForecaster(n_simulations=1000)
    mc.fit(data)
    result = mc.forecast(10)
    print(f"  Current: {mc.last_price:.2f}")
    print(f"  Forecast (10d): {result.forecast_values[-1]:.2f}")
    print(f"  Range: [{result.lower_bound[-1]:.2f}, {result.upper_bound[-1]:.2f}]")
    print(f"  Prob Profit: {result.metrics['prob_profit']:.1%}")
    
    # Test ARIMA if statsmodels available
    try:
        print("\n📈 ARIMA Forecast:")
        arima = ARIMAForecaster()
        if arima.fit(data, auto=False, order=(1, 1, 1)):
            result = arima.forecast(10)
            print(f"  Forecast (10d): {result.forecast_values[-1]:.2f}")
            print(f"  AIC: {result.metrics['aic']:.2f}")
    except:
        print("  (statsmodels not available)")
    
    # Test Ensemble
    print("\n🎯 Ensemble Forecast:")
    ensemble = EnsembleForecaster()
    if ensemble.fit(data, models=['arima', 'ets']):
        result = ensemble.forecast(10)
        print(f"  Forecast (10d): {result.forecast_values[-1]:.2f}")
        print(f"  Models: {result.metrics['models_used']}")
    else:
        print("  (No models available)")
    
    print("\n✅ Forecasting tests completed!")


if __name__ == "__main__":
    test_forecasters()
