"""
Monte Carlo Simulation Module
For risk assessment and position sizing decisions
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SimulationResult:
    """Monte Carlo simulation results"""
    symbol: str
    strategy_name: str
    num_simulations: int
    forecast_days: int
    initial_price: float
    leverage: float = 1.0

    # Price forecasts
    mean_price: float = 0.0
    median_price: float = 0.0
    std_price: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0

    # Percentile prices
    percentile_5: float = 0.0
    percentile_25: float = 0.0
    percentile_75: float = 0.0
    percentile_95: float = 0.0

    # Return distribution
    mean_return: float = 0.0
    median_return: float = 0.0
    std_return: float = 0.0

    # Probability metrics
    prob_profit: float = 0.0  # Probability of profit
    prob_loss_5pct: float = 0.0  # Probability of 5%+ loss
    prob_loss_10pct: float = 0.0  # Probability of 10%+ loss
    prob_gain_5pct: float = 0.0  # Probability of 5%+ gain
    prob_gain_10pct: float = 0.0  # Probability of 10%+ gain

    # Risk metrics
    var_95: float = 0.0  # Value at Risk (95%)
    var_99: float = 0.0  # Value at Risk (99%)
    cvar_95: float = 0.0  # Conditional VaR (Expected Shortfall)
    max_drawdown_mean: float = 0.0
    max_drawdown_worst: float = 0.0

    # Kelly and position sizing
    kelly_fraction: float = 0.0
    recommended_position_pct: float = 0.0
    expected_value: float = 0.0

    # Risk score
    risk_score: int = 0  # 0-100

    # Raw simulation data
    final_prices: List[float] = field(default_factory=list)
    final_returns: List[float] = field(default_factory=list)
    paths: Optional[np.ndarray] = None  # Full simulation paths

    # Distribution data for visualization
    return_bins: List[float] = field(default_factory=list)
    return_counts: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'strategy_name': self.strategy_name,
            'num_simulations': self.num_simulations,
            'forecast_days': self.forecast_days,
            'initial_price': self.initial_price,
            'leverage': self.leverage,
            'mean_price': self.mean_price,
            'median_price': self.median_price,
            'percentile_5': self.percentile_5,
            'percentile_95': self.percentile_95,
            'mean_return': self.mean_return,
            'prob_profit': self.prob_profit,
            'prob_loss_5pct': self.prob_loss_5pct,
            'prob_gain_5pct': self.prob_gain_5pct,
            'var_95': self.var_95,
            'cvar_95': self.cvar_95,
            'kelly_fraction': self.kelly_fraction,
            'recommended_position_pct': self.recommended_position_pct,
            'expected_value': self.expected_value,
            'risk_score': self.risk_score
        }

    def get_recommendation(self) -> str:
        """Get trading recommendation based on simulation"""
        if self.risk_score > 70:
            risk_level = "CAO"
            action = "KHÔNG NÊN MỞ VỊ THẾ"
        elif self.risk_score > 50:
            risk_level = "TRUNG BÌNH-CAO"
            action = "CẨN THẬN, giảm size"
        elif self.risk_score > 30:
            risk_level = "TRUNG BÌNH"
            action = "CÓ THỂ VÀO LỆNH"
        else:
            risk_level = "THẤP"
            action = "TÍN HIỆU TÍCH CỰC"

        return f"""
TÍN HIỆU: {action}
Điểm Rủi Ro: {self.risk_score}/100 ({risk_level})

Dự báo giá T+{self.forecast_days}:
  - Trung bình: {self.mean_price:,.0f}
  - Khoảng 90%: [{self.percentile_5:,.0f} - {self.percentile_95:,.0f}]

Xác suất:
  - Có lời: {self.prob_profit:.1f}%
  - Lời >5%: {self.prob_gain_5pct:.1f}%
  - Lỗ >5%: {self.prob_loss_5pct:.1f}%

VaR 95%: {self.var_95:.2f}% (Có thể mất tối đa trong 95% trường hợp)
Kelly Fraction: {self.kelly_fraction*100:.1f}%
Size khuyến nghị: {self.recommended_position_pct:.1f}% NAV
"""


class MonteCarloSimulator:
    """
    Monte Carlo Simulation for stock price forecasting and risk assessment
    """

    def __init__(self, num_simulations: int = 10000, random_seed: int = None):
        self.num_simulations = num_simulations
        if random_seed:
            np.random.seed(random_seed)

    def simulate(self, df: pd.DataFrame, symbol: str = "UNKNOWN",
                forecast_days: int = 10, leverage: float = 1.0,
                strategy_name: str = "Long 1x",
                method: str = "gbm") -> SimulationResult:
        """
        Run Monte Carlo simulation

        Args:
            df: Historical price data with 'close' column
            symbol: Stock symbol
            forecast_days: Number of days to forecast
            leverage: Trading leverage (1x, 2x, etc.)
            strategy_name: Strategy description
            method: Simulation method ('gbm', 'bootstrap', 'historical')

        Returns:
            SimulationResult with comprehensive metrics
        """
        prices = df['close'].values if isinstance(df, pd.DataFrame) else df

        # Calculate historical returns
        returns = np.diff(prices) / prices[:-1]

        # Run simulation based on method
        if method == "gbm":
            paths, final_prices = self._simulate_gbm(prices[-1], returns, forecast_days)
        elif method == "bootstrap":
            paths, final_prices = self._simulate_bootstrap(prices[-1], returns, forecast_days)
        else:  # historical
            paths, final_prices = self._simulate_historical(prices[-1], returns, forecast_days)

        # Apply leverage
        initial_price = prices[-1]
        leveraged_returns = ((final_prices / initial_price) - 1) * leverage
        leveraged_prices = initial_price * (1 + leveraged_returns)

        # Calculate result metrics
        result = self._calculate_metrics(
            symbol=symbol,
            strategy_name=strategy_name,
            initial_price=initial_price,
            final_prices=leveraged_prices,
            paths=paths,
            forecast_days=forecast_days,
            leverage=leverage,
            historical_returns=returns
        )

        return result

    def _simulate_gbm(self, initial_price: float, returns: np.ndarray,
                     days: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Geometric Brownian Motion simulation
        """
        mu = np.mean(returns)  # Drift
        sigma = np.std(returns)  # Volatility

        # Generate random walks
        dt = 1  # Daily
        paths = np.zeros((self.num_simulations, days + 1))
        paths[:, 0] = initial_price

        for t in range(1, days + 1):
            z = np.random.standard_normal(self.num_simulations)
            paths[:, t] = paths[:, t-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z)

        final_prices = paths[:, -1]
        return paths, final_prices

    def _simulate_bootstrap(self, initial_price: float, returns: np.ndarray,
                           days: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Bootstrap simulation - sample from historical returns
        """
        paths = np.zeros((self.num_simulations, days + 1))
        paths[:, 0] = initial_price

        for t in range(1, days + 1):
            # Random sample from historical returns
            sampled_returns = np.random.choice(returns, size=self.num_simulations, replace=True)
            paths[:, t] = paths[:, t-1] * (1 + sampled_returns)

        final_prices = paths[:, -1]
        return paths, final_prices

    def _simulate_historical(self, initial_price: float, returns: np.ndarray,
                            days: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Historical simulation - use rolling windows
        """
        n_returns = len(returns)
        paths = np.zeros((self.num_simulations, days + 1))
        paths[:, 0] = initial_price

        for i in range(self.num_simulations):
            # Random starting point
            start_idx = np.random.randint(0, max(1, n_returns - days))
            window_returns = returns[start_idx:start_idx + days]

            # Pad if not enough data
            if len(window_returns) < days:
                window_returns = np.concatenate([
                    window_returns,
                    np.random.choice(returns, size=days - len(window_returns))
                ])

            for t in range(days):
                paths[i, t+1] = paths[i, t] * (1 + window_returns[t])

        final_prices = paths[:, -1]
        return paths, final_prices

    def _calculate_metrics(self, symbol: str, strategy_name: str,
                          initial_price: float, final_prices: np.ndarray,
                          paths: np.ndarray, forecast_days: int,
                          leverage: float, historical_returns: np.ndarray) -> SimulationResult:
        """Calculate comprehensive simulation metrics"""

        final_returns = (final_prices / initial_price - 1) * 100  # Percentage returns

        result = SimulationResult(
            symbol=symbol,
            strategy_name=strategy_name,
            num_simulations=self.num_simulations,
            forecast_days=forecast_days,
            initial_price=initial_price,
            leverage=leverage
        )

        # Price statistics
        result.mean_price = np.mean(final_prices)
        result.median_price = np.median(final_prices)
        result.std_price = np.std(final_prices)
        result.min_price = np.min(final_prices)
        result.max_price = np.max(final_prices)

        # Percentiles
        result.percentile_5 = np.percentile(final_prices, 5)
        result.percentile_25 = np.percentile(final_prices, 25)
        result.percentile_75 = np.percentile(final_prices, 75)
        result.percentile_95 = np.percentile(final_prices, 95)

        # Return statistics
        result.mean_return = np.mean(final_returns)
        result.median_return = np.median(final_returns)
        result.std_return = np.std(final_returns)

        # Probabilities
        result.prob_profit = np.mean(final_returns > 0) * 100
        result.prob_loss_5pct = np.mean(final_returns < -5) * 100
        result.prob_loss_10pct = np.mean(final_returns < -10) * 100
        result.prob_gain_5pct = np.mean(final_returns > 5) * 100
        result.prob_gain_10pct = np.mean(final_returns > 10) * 100

        # Value at Risk
        result.var_95 = -np.percentile(final_returns, 5)  # 5th percentile loss
        result.var_99 = -np.percentile(final_returns, 1)  # 1st percentile loss

        # Conditional VaR (Expected Shortfall)
        var_threshold = np.percentile(final_returns, 5)
        losses_below_var = final_returns[final_returns <= var_threshold]
        if len(losses_below_var) > 0:
            result.cvar_95 = -np.mean(losses_below_var)

        # Max Drawdown from paths
        drawdowns = []
        for path in paths:
            peak = np.maximum.accumulate(path)
            dd = (path - peak) / peak * 100
            drawdowns.append(np.min(dd))

        result.max_drawdown_mean = np.mean(drawdowns)
        result.max_drawdown_worst = np.min(drawdowns)

        # Kelly Criterion calculation
        win_rate = np.mean(final_returns > 0)
        avg_win = np.mean(final_returns[final_returns > 0]) if np.any(final_returns > 0) else 0
        avg_loss = abs(np.mean(final_returns[final_returns < 0])) if np.any(final_returns < 0) else 1

        if avg_loss > 0:
            win_loss_ratio = avg_win / avg_loss
            kelly = win_rate - ((1 - win_rate) / win_loss_ratio)
            result.kelly_fraction = max(0, min(kelly * 0.5, 0.25))  # Half Kelly, capped
        else:
            result.kelly_fraction = 0.25

        # Risk Score (0-100)
        risk_factors = []

        # Factor 1: Probability of significant loss
        risk_factors.append(min(100, result.prob_loss_5pct * 2))

        # Factor 2: VaR
        risk_factors.append(min(100, result.var_95 * 5))

        # Factor 3: Return distribution skew
        skew_risk = max(0, 50 - result.mean_return)
        risk_factors.append(min(100, skew_risk))

        # Factor 4: Max drawdown risk
        risk_factors.append(min(100, abs(result.max_drawdown_mean) * 2))

        result.risk_score = int(np.mean(risk_factors))

        # Recommended position size
        if result.risk_score >= 70:
            result.recommended_position_pct = 5
        elif result.risk_score >= 50:
            result.recommended_position_pct = 10
        elif result.risk_score >= 30:
            result.recommended_position_pct = 20
        else:
            result.recommended_position_pct = result.kelly_fraction * 100

        # Expected Value
        result.expected_value = result.mean_return

        # Distribution data for visualization
        hist, bins = np.histogram(final_returns, bins=50)
        result.return_bins = bins[:-1].tolist()
        result.return_counts = hist.tolist()

        # Store raw data
        result.final_prices = final_prices.tolist()[:1000]  # Limit for storage
        result.final_returns = final_returns.tolist()[:1000]
        result.paths = paths[:100]  # Store first 100 paths for visualization

        return result

    def sensitivity_analysis(self, df: pd.DataFrame, symbol: str,
                            leverage_range: List[float] = [1, 1.5, 2, 3],
                            days_range: List[int] = [5, 10, 20, 30]) -> pd.DataFrame:
        """
        Run sensitivity analysis across different parameters

        Returns:
            DataFrame with results for different combinations
        """
        results = []

        for leverage in leverage_range:
            for days in days_range:
                try:
                    sim_result = self.simulate(
                        df=df,
                        symbol=symbol,
                        forecast_days=days,
                        leverage=leverage,
                        strategy_name=f"Long {leverage}x"
                    )

                    results.append({
                        'Leverage': f"{leverage}x",
                        'Days': days,
                        'Mean Return %': sim_result.mean_return,
                        'Prob Profit %': sim_result.prob_profit,
                        'VaR 95%': sim_result.var_95,
                        'Risk Score': sim_result.risk_score,
                        'Kelly %': sim_result.kelly_fraction * 100
                    })
                except Exception as e:
                    print(f"Error with leverage={leverage}, days={days}: {e}")

        return pd.DataFrame(results)

    def compare_scenarios(self, df: pd.DataFrame, symbol: str,
                         scenarios: List[Dict[str, Any]]) -> List[SimulationResult]:
        """
        Compare multiple trading scenarios

        Args:
            df: Historical data
            symbol: Stock symbol
            scenarios: List of dicts with 'name', 'leverage', 'days' keys

        Returns:
            List of SimulationResult for each scenario
        """
        results = []

        for scenario in scenarios:
            result = self.simulate(
                df=df,
                symbol=symbol,
                forecast_days=scenario.get('days', 10),
                leverage=scenario.get('leverage', 1.0),
                strategy_name=scenario.get('name', 'Scenario')
            )
            results.append(result)

        return results
