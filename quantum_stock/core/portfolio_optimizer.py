# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PORTFOLIO OPTIMIZATION                                    ║
║                    Mean-Variance, Risk Parity, Black-Litterman             ║
╚══════════════════════════════════════════════════════════════════════════════╝

P2 Implementation - Portfolio optimization for VN-QUANT
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from scipy import optimize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# DATA MODELS
# ============================================

@dataclass
class OptimizationResult:
    """Portfolio optimization result"""
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    method: str
    metadata: Dict = field(default_factory=dict)
    
    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({
            'Symbol': list(self.weights.keys()),
            'Weight': list(self.weights.values()),
            'Allocation %': [w * 100 for w in self.weights.values()]
        })


# ============================================
# PORTFOLIO OPTIMIZER
# ============================================

class PortfolioOptimizer:
    """
    Portfolio Optimization Engine
    
    Supports:
    - Mean-Variance (Markowitz)
    - Minimum Variance
    - Maximum Sharpe
    - Risk Parity
    - Kelly Criterion
    - Black-Litterman
    """
    
    def __init__(self, returns: pd.DataFrame, risk_free_rate: float = 0.05):
        """
        Initialize optimizer
        
        Args:
            returns: DataFrame of asset returns (columns = assets)
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        self.returns = returns
        self.risk_free_rate = risk_free_rate
        self.daily_rf = risk_free_rate / 252
        
        # Calculate statistics
        self.mean_returns = returns.mean() * 252
        self.cov_matrix = returns.cov() * 252
        self.assets = list(returns.columns)
        self.n_assets = len(self.assets)
    
    def optimize_max_sharpe(self, constraints: Dict = None) -> OptimizationResult:
        """
        Maximum Sharpe Ratio Portfolio
        
        Markowitz mean-variance optimization targeting highest Sharpe ratio
        """
        def neg_sharpe(weights):
            port_return = np.dot(weights, self.mean_returns)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            return -(port_return - self.risk_free_rate) / port_vol
        
        # Constraints
        cons = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Weights sum to 1
        ]
        
        # Bounds
        bounds = [(0, 1) for _ in range(self.n_assets)]  # Long only
        
        if constraints:
            if 'max_weight' in constraints:
                bounds = [(0, constraints['max_weight']) for _ in range(self.n_assets)]
        
        # Initial guess (equal weight)
        x0 = np.array([1 / self.n_assets] * self.n_assets)
        
        # Optimize
        result = optimize.minimize(
            neg_sharpe, x0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        weights = result.x
        port_return = np.dot(weights, self.mean_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        sharpe = (port_return - self.risk_free_rate) / port_vol
        
        return OptimizationResult(
            weights=dict(zip(self.assets, weights)),
            expected_return=port_return,
            volatility=port_vol,
            sharpe_ratio=sharpe,
            method='Max Sharpe',
            metadata={'success': result.success}
        )
    
    def optimize_min_variance(self) -> OptimizationResult:
        """
        Minimum Variance Portfolio
        
        Lowest risk portfolio on the efficient frontier
        """
        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(self.cov_matrix, weights))
        
        cons = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        bounds = [(0, 1) for _ in range(self.n_assets)]
        x0 = np.array([1 / self.n_assets] * self.n_assets)
        
        result = optimize.minimize(
            portfolio_variance, x0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        weights = result.x
        port_return = np.dot(weights, self.mean_returns)
        port_vol = np.sqrt(portfolio_variance(weights))
        sharpe = (port_return - self.risk_free_rate) / port_vol
        
        return OptimizationResult(
            weights=dict(zip(self.assets, weights)),
            expected_return=port_return,
            volatility=port_vol,
            sharpe_ratio=sharpe,
            method='Min Variance'
        )
    
    def optimize_risk_parity(self) -> OptimizationResult:
        """
        Risk Parity Portfolio
        
        Equal risk contribution from each asset
        """
        def risk_parity_objective(weights):
            # Portfolio variance
            port_var = np.dot(weights.T, np.dot(self.cov_matrix, weights))
            
            # Marginal risk contribution
            mrc = np.dot(self.cov_matrix, weights)
            
            # Risk contribution
            rc = weights * mrc
            
            # Target: equal risk contribution
            target_rc = port_var / self.n_assets
            
            return np.sum((rc - target_rc) ** 2)
        
        cons = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        bounds = [(0.01, 1) for _ in range(self.n_assets)]  # Min 1% per asset
        x0 = np.array([1 / self.n_assets] * self.n_assets)
        
        result = optimize.minimize(
            risk_parity_objective, x0,
            method='SLSQP',
            bounds=bounds,
            constraints=cons
        )
        
        weights = result.x
        port_return = np.dot(weights, self.mean_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        sharpe = (port_return - self.risk_free_rate) / port_vol
        
        return OptimizationResult(
            weights=dict(zip(self.assets, weights)),
            expected_return=port_return,
            volatility=port_vol,
            sharpe_ratio=sharpe,
            method='Risk Parity'
        )
    
    def optimize_kelly(self, max_leverage: float = 1.0) -> OptimizationResult:
        """
        Kelly Criterion Portfolio
        
        Maximizes long-term growth rate
        
        Kelly = Σ (Cov^-1 * (μ - r_f))
        """
        try:
            # Inverse covariance matrix
            cov_inv = np.linalg.inv(self.cov_matrix)
            
            # Excess returns
            excess_returns = self.mean_returns - self.risk_free_rate
            
            # Raw Kelly weights
            kelly_weights = np.dot(cov_inv, excess_returns)
            
            # Normalize and apply leverage constraint
            kelly_sum = np.sum(kelly_weights)
            if kelly_sum > max_leverage:
                kelly_weights = kelly_weights * (max_leverage / kelly_sum)
            
            # Handle negative weights (short positions) - set to 0 for long-only
            kelly_weights = np.maximum(kelly_weights, 0)
            
            # Normalize to sum to 1
            if np.sum(kelly_weights) > 0:
                kelly_weights = kelly_weights / np.sum(kelly_weights)
            else:
                kelly_weights = np.array([1 / self.n_assets] * self.n_assets)
            
            port_return = np.dot(kelly_weights, self.mean_returns)
            port_vol = np.sqrt(np.dot(kelly_weights.T, np.dot(self.cov_matrix, kelly_weights)))
            sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0
            
            return OptimizationResult(
                weights=dict(zip(self.assets, kelly_weights)),
                expected_return=port_return,
                volatility=port_vol,
                sharpe_ratio=sharpe,
                method='Kelly Criterion',
                metadata={'max_leverage': max_leverage}
            )
            
        except np.linalg.LinAlgError:
            logger.warning("Kelly optimization failed, falling back to equal weight")
            return self.equal_weight()
    
    def optimize_black_litterman(self, views: Dict[str, float], 
                                  view_confidence: float = 0.5,
                                  market_cap_weights: Dict[str, float] = None
                                  ) -> OptimizationResult:
        """
        Black-Litterman Portfolio
        
        Combines market equilibrium with investor views
        
        Args:
            views: Dict of expected returns by asset {'HPG': 0.15, 'VNM': 0.08}
            view_confidence: Confidence in views (0-1)
            market_cap_weights: Market cap weights (default: equal)
        """
        # Market cap weights (default equal)
        if market_cap_weights is None:
            w_mkt = np.array([1 / self.n_assets] * self.n_assets)
        else:
            w_mkt = np.array([market_cap_weights.get(a, 1/self.n_assets) for a in self.assets])
            w_mkt = w_mkt / np.sum(w_mkt)
        
        # Risk aversion coefficient
        delta = 2.5
        
        # Implied equilibrium returns (CAPM)
        pi = delta * np.dot(self.cov_matrix, w_mkt)
        
        # Views matrix (P) and view returns (Q)
        P = np.zeros((len(views), self.n_assets))
        Q = np.zeros(len(views))
        
        for i, (asset, view_return) in enumerate(views.items()):
            if asset in self.assets:
                P[i, self.assets.index(asset)] = 1
                Q[i] = view_return
        
        if len(views) == 0:
            # No views, return market portfolio
            return OptimizationResult(
                weights=dict(zip(self.assets, w_mkt)),
                expected_return=np.dot(w_mkt, self.mean_returns),
                volatility=np.sqrt(np.dot(w_mkt.T, np.dot(self.cov_matrix, w_mkt))),
                sharpe_ratio=0,
                method='Black-Litterman (Market)'
            )
        
        # Uncertainty in views (Omega)
        tau = view_confidence
        omega = np.diag(np.diag(np.dot(np.dot(P, self.cov_matrix), P.T)) * tau)
        
        # Black-Litterman formula
        # E[R] = [(τΣ)^-1 + P'Ω^-1 P]^-1 [(τΣ)^-1 π + P'Ω^-1 Q]
        try:
            tau_cov_inv = np.linalg.inv(tau * self.cov_matrix)
            omega_inv = np.linalg.inv(omega)
            
            left = np.linalg.inv(tau_cov_inv + np.dot(np.dot(P.T, omega_inv), P))
            right = np.dot(tau_cov_inv, pi) + np.dot(np.dot(P.T, omega_inv), Q)
            
            bl_returns = np.dot(left, right)
            
            # Optimize using BL returns
            temp_mean = self.mean_returns.copy()
            self.mean_returns = pd.Series(bl_returns, index=self.assets)
            result = self.optimize_max_sharpe()
            self.mean_returns = temp_mean
            
            result.method = 'Black-Litterman'
            result.metadata = {'views': views, 'confidence': view_confidence}
            return result
            
        except np.linalg.LinAlgError:
            logger.warning("BL optimization failed")
            return self.equal_weight()
    
    def equal_weight(self) -> OptimizationResult:
        """Equal weight portfolio"""
        weights = np.array([1 / self.n_assets] * self.n_assets)
        port_return = np.dot(weights, self.mean_returns)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        sharpe = (port_return - self.risk_free_rate) / port_vol
        
        return OptimizationResult(
            weights=dict(zip(self.assets, weights)),
            expected_return=port_return,
            volatility=port_vol,
            sharpe_ratio=sharpe,
            method='Equal Weight'
        )
    
    def efficient_frontier(self, n_points: int = 50) -> pd.DataFrame:
        """
        Calculate efficient frontier
        
        Returns DataFrame of (risk, return) points
        """
        # Find min and max returns
        min_ret = self.optimize_min_variance().expected_return
        max_ret = self.mean_returns.max()
        
        target_returns = np.linspace(min_ret, max_ret, n_points)
        
        frontier = []
        
        for target in target_returns:
            def portfolio_vol(weights):
                return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            
            cons = [
                {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                {'type': 'eq', 'fun': lambda x, t=target: np.dot(x, self.mean_returns) - t}
            ]
            bounds = [(0, 1) for _ in range(self.n_assets)]
            x0 = np.array([1 / self.n_assets] * self.n_assets)
            
            try:
                result = optimize.minimize(
                    portfolio_vol, x0,
                    method='SLSQP',
                    bounds=bounds,
                    constraints=cons
                )
                
                if result.success:
                    frontier.append({
                        'return': target,
                        'volatility': result.fun,
                        'sharpe': (target - self.risk_free_rate) / result.fun
                    })
            except:
                continue
        
        return pd.DataFrame(frontier)
    
    def compare_strategies(self) -> pd.DataFrame:
        """Compare all optimization strategies"""
        strategies = {
            'Equal Weight': self.equal_weight(),
            'Max Sharpe': self.optimize_max_sharpe(),
            'Min Variance': self.optimize_min_variance(),
            'Risk Parity': self.optimize_risk_parity(),
            'Kelly': self.optimize_kelly()
        }
        
        comparison = []
        for name, result in strategies.items():
            comparison.append({
                'Strategy': name,
                'Return': f"{result.expected_return:.2%}",
                'Volatility': f"{result.volatility:.2%}",
                'Sharpe': f"{result.sharpe_ratio:.2f}"
            })
        
        return pd.DataFrame(comparison)


# ============================================
# RISK METRICS
# ============================================

class PortfolioRiskAnalyzer:
    """Portfolio risk analysis"""
    
    def __init__(self, returns: pd.DataFrame, weights: Dict[str, float]):
        self.returns = returns
        self.weights = np.array([weights.get(a, 0) for a in returns.columns])
        self.portfolio_returns = returns.dot(self.weights)
    
    def var(self, confidence: float = 0.95, method: str = 'historical') -> float:
        """
        Value at Risk
        
        Args:
            confidence: Confidence level (e.g., 0.95)
            method: 'historical', 'parametric', 'monte_carlo'
        """
        if method == 'historical':
            return np.percentile(self.portfolio_returns, (1 - confidence) * 100)
        elif method == 'parametric':
            from scipy import stats
            mu = self.portfolio_returns.mean()
            sigma = self.portfolio_returns.std()
            return stats.norm.ppf(1 - confidence) * sigma + mu
        else:
            # Monte Carlo
            mu = self.portfolio_returns.mean()
            sigma = self.portfolio_returns.std()
            simulated = np.random.normal(mu, sigma, 10000)
            return np.percentile(simulated, (1 - confidence) * 100)
    
    def cvar(self, confidence: float = 0.95) -> float:
        """Conditional VaR (Expected Shortfall)"""
        var = self.var(confidence)
        return self.portfolio_returns[self.portfolio_returns <= var].mean()
    
    def max_drawdown(self) -> float:
        """Maximum drawdown"""
        cumulative = (1 + self.portfolio_returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        return drawdown.min()
    
    def marginal_var(self, confidence: float = 0.95) -> Dict[str, float]:
        """Marginal VaR by asset"""
        marginal = {}
        base_var = self.var(confidence)
        
        for asset in self.returns.columns:
            # Increase weight slightly
            modified_weights = self.weights.copy()
            idx = list(self.returns.columns).index(asset)
            modified_weights[idx] += 0.01
            modified_weights = modified_weights / np.sum(modified_weights)
            
            modified_returns = self.returns.dot(modified_weights)
            modified_var = np.percentile(modified_returns, (1 - confidence) * 100)
            
            marginal[asset] = (modified_var - base_var) / 0.01
        
        return marginal


# ============================================
# TESTING
# ============================================

def test_portfolio_optimization():
    """Test portfolio optimization"""
    print("Testing Portfolio Optimization...")
    print("=" * 50)
    
    # Create sample data
    np.random.seed(42)
    n_days = 252
    assets = ['HPG', 'VNM', 'FPT', 'VCB', 'TCB']
    
    # Simulate returns
    returns_data = {}
    for asset in assets:
        mu = np.random.uniform(0.05, 0.20) / 252  # Daily return
        sigma = np.random.uniform(0.15, 0.35) / np.sqrt(252)  # Daily vol
        returns_data[asset] = np.random.normal(mu, sigma, n_days)
    
    returns = pd.DataFrame(returns_data)
    
    # Initialize optimizer
    optimizer = PortfolioOptimizer(returns, risk_free_rate=0.05)
    
    # Test different strategies
    print("\n📊 Portfolio Optimization Results:")
    print("-" * 50)
    
    # Max Sharpe
    result = optimizer.optimize_max_sharpe()
    print(f"\n🎯 Max Sharpe Portfolio:")
    print(f"   Return: {result.expected_return:.2%}")
    print(f"   Vol: {result.volatility:.2%}")
    print(f"   Sharpe: {result.sharpe_ratio:.2f}")
    
    # Min Variance
    result = optimizer.optimize_min_variance()
    print(f"\n🛡️ Min Variance Portfolio:")
    print(f"   Return: {result.expected_return:.2%}")
    print(f"   Vol: {result.volatility:.2%}")
    
    # Risk Parity
    result = optimizer.optimize_risk_parity()
    print(f"\n⚖️ Risk Parity Portfolio:")
    print(f"   Sharpe: {result.sharpe_ratio:.2f}")
    
    # Kelly
    result = optimizer.optimize_kelly()
    print(f"\n📈 Kelly Portfolio:")
    print(f"   Sharpe: {result.sharpe_ratio:.2f}")
    
    # Compare all
    print("\n📋 Strategy Comparison:")
    comparison = optimizer.compare_strategies()
    print(comparison.to_string(index=False))
    
    # Test Black-Litterman with views
    views = {'HPG': 0.25, 'VNM': 0.10}  # Expect HPG +25%, VNM +10%
    result = optimizer.optimize_black_litterman(views, view_confidence=0.6)
    print(f"\n🔮 Black-Litterman (with views):")
    print(f"   Return: {result.expected_return:.2%}")
    print(f"   Views: {views}")
    
    print("\n✅ Portfolio optimization tests completed!")


if __name__ == "__main__":
    test_portfolio_optimization()
