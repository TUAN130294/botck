# -*- coding: utf-8 -*-
"""
Market Regime Detector - Level 4 Agentic AI
============================================
Detects market regimes using Hurst Exponent and Volatility Clustering.

Regimes:
- TRENDING: Hurst > 0.55, use Momentum strategies
- MEAN_REVERTING: Hurst < 0.45, use Mean Reversion strategies  
- VOLATILE: High volatility, reduce position size
- QUIET: Low volatility, increase position size
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


class MarketRegime(Enum):
    TRENDING = "TRENDING"
    MEAN_REVERTING = "MEAN_REVERTING"
    VOLATILE = "VOLATILE"
    QUIET = "QUIET"
    NEUTRAL = "NEUTRAL"


@dataclass
class RegimeAnalysis:
    regime: MarketRegime
    hurst_exponent: float
    volatility_percentile: float
    trend_strength: float
    confidence: float
    recommended_strategies: List[str]
    position_multiplier: float  # 0.5 = reduce, 1.0 = normal, 1.5 = increase


class MarketRegimeDetector:
    """
    Advanced Market Regime Detection System
    
    Uses:
    1. Hurst Exponent - Detect trend persistence
    2. Volatility Clustering - Detect regime changes
    3. Trend Strength - ADX-like measure
    4. Rolling correlation with market index
    
    Reference: Mandelbrot (1968), Hurst (1951)
    """
    
    def __init__(self, lookback_hurst: int = 100, lookback_vol: int = 20):
        self.lookback_hurst = lookback_hurst
        self.lookback_vol = lookback_vol
        self.volatility_history = []
        
    def calculate_hurst_exponent(self, prices: np.ndarray) -> float:
        """
        Calculate Hurst Exponent using R/S Analysis
        
        H > 0.5: Trending (persistent)
        H = 0.5: Random walk
        H < 0.5: Mean-reverting (anti-persistent)
        
        Implementation: Rescaled Range (R/S) method
        """
        if len(prices) < 20:
            return 0.5  # Default to random walk
            
        # Log returns
        returns = np.diff(np.log(prices))
        
        # Calculate R/S for different time scales
        max_k = min(len(returns) // 2, 50)
        if max_k < 4:
            return 0.5
            
        rs_values = []
        n_values = []
        
        for n in range(4, max_k):
            # Split into subseries
            num_subseries = len(returns) // n
            if num_subseries < 1:
                continue
                
            rs_n = []
            for i in range(num_subseries):
                subseries = returns[i*n:(i+1)*n]
                
                # Mean-adjusted cumulative deviation
                mean_adj = subseries - np.mean(subseries)
                cumdev = np.cumsum(mean_adj)
                
                # Range
                R = np.max(cumdev) - np.min(cumdev)
                
                # Standard deviation
                S = np.std(subseries, ddof=1)
                
                if S > 0:
                    rs_n.append(R / S)
            
            if len(rs_n) > 0:
                rs_values.append(np.mean(rs_n))
                n_values.append(n)
        
        if len(rs_values) < 3:
            return 0.5
            
        # Linear regression to find H
        log_n = np.log(n_values)
        log_rs = np.log(rs_values)
        
        # H is the slope
        slope, _ = np.polyfit(log_n, log_rs, 1)
        
        # Clamp to valid range
        return np.clip(slope, 0.0, 1.0)
    
    def calculate_volatility_percentile(self, prices: np.ndarray) -> float:
        """
        Calculate current volatility percentile vs history
        
        Returns: 0-100 percentile (100 = highest volatility)
        """
        if len(prices) < self.lookback_vol + 1:
            return 50.0
            
        # Calculate rolling volatility
        returns = np.diff(np.log(prices))
        current_vol = np.std(returns[-self.lookback_vol:]) * np.sqrt(252)  # Annualized
        
        # Compare to history
        historical_vols = []
        for i in range(len(returns) - self.lookback_vol):
            vol = np.std(returns[i:i+self.lookback_vol]) * np.sqrt(252)
            historical_vols.append(vol)
        
        if len(historical_vols) == 0:
            return 50.0
            
        # Percentile rank
        percentile = (np.sum(np.array(historical_vols) < current_vol) / len(historical_vols)) * 100
        
        return percentile
    
    def calculate_trend_strength(self, prices: np.ndarray, period: int = 14) -> float:
        """
        Calculate trend strength (ADX-like measure)
        
        Returns: 0-100 (higher = stronger trend)
        """
        if len(prices) < period + 1:
            return 0.0
            
        high = prices  # Simplified: using close as proxy
        low = prices
        close = prices
        
        # True Range components
        plus_dm = np.zeros(len(prices))
        minus_dm = np.zeros(len(prices))
        tr = np.zeros(len(prices))
        
        for i in range(1, len(prices)):
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]
            
            plus_dm[i] = up_move if up_move > down_move and up_move > 0 else 0
            minus_dm[i] = down_move if down_move > up_move and down_move > 0 else 0
            
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
        
        # Smoothed averages
        def smooth_avg(arr, period):
            result = np.zeros(len(arr))
            result[period] = np.mean(arr[1:period+1])
            for i in range(period+1, len(arr)):
                result[i] = (result[i-1] * (period-1) + arr[i]) / period
            return result
        
        atr = smooth_avg(tr, period)
        plus_di = smooth_avg(plus_dm, period)
        minus_di = smooth_avg(minus_dm, period)
        
        # Avoid division by zero
        atr = np.where(atr == 0, 1e-10, atr)
        
        plus_di = 100 * plus_di / atr
        minus_di = 100 * minus_di / atr
        
        # DX and ADX
        di_sum = plus_di + minus_di
        di_sum = np.where(di_sum == 0, 1e-10, di_sum)
        dx = 100 * np.abs(plus_di - minus_di) / di_sum
        
        adx = smooth_avg(dx, period)
        
        return float(adx[-1]) if len(adx) > 0 else 0.0
    
    def detect_regime(self, prices: np.ndarray) -> RegimeAnalysis:
        """
        Main regime detection function
        
        Logic:
        1. Calculate Hurst Exponent → Trend vs Mean-Revert
        2. Calculate Volatility Percentile → High vs Low vol
        3. Calculate Trend Strength → Strong vs Weak
        4. Combine into regime classification
        """
        prices = np.array(prices)
        
        # Calculate metrics
        hurst = self.calculate_hurst_exponent(prices[-self.lookback_hurst:])
        vol_pct = self.calculate_volatility_percentile(prices)
        trend_str = self.calculate_trend_strength(prices)
        
        # Determine regime
        if vol_pct > 80:
            regime = MarketRegime.VOLATILE
            strategies = ["Volatility Trading", "Options", "Hedging"]
            position_mult = 0.5
            confidence = min(vol_pct / 100, 0.95)
            
        elif vol_pct < 20:
            regime = MarketRegime.QUIET
            strategies = ["Range Trading", "Mean Reversion", "Premium Selling"]
            position_mult = 1.2
            confidence = min((100 - vol_pct) / 100, 0.90)
            
        elif hurst > 0.55:
            regime = MarketRegime.TRENDING
            strategies = ["Momentum", "Trend Following", "Breakout"]
            position_mult = 1.0
            confidence = min(hurst, 0.95)
            
        elif hurst < 0.45:
            regime = MarketRegime.MEAN_REVERTING
            strategies = ["Mean Reversion", "Pairs Trading", "RSI Oversold/Overbought"]
            position_mult = 1.0
            confidence = min(1 - hurst, 0.90)
            
        else:
            regime = MarketRegime.NEUTRAL
            strategies = ["Balanced", "Diversified", "Wait for Signal"]
            position_mult = 0.8
            confidence = 0.5
        
        return RegimeAnalysis(
            regime=regime,
            hurst_exponent=round(hurst, 4),
            volatility_percentile=round(vol_pct, 2),
            trend_strength=round(trend_str, 2),
            confidence=round(confidence, 4),
            recommended_strategies=strategies,
            position_multiplier=position_mult
        )
    
    def get_strategy_weights(self, regime: MarketRegime) -> Dict[str, float]:
        """
        Get recommended strategy weights based on regime
        
        Returns dict of strategy_name: weight (0-1)
        """
        weights = {
            MarketRegime.TRENDING: {
                "momentum": 0.70,
                "mean_reversion": 0.10,
                "volatility": 0.10,
                "hedging": 0.10
            },
            MarketRegime.MEAN_REVERTING: {
                "momentum": 0.10,
                "mean_reversion": 0.70,
                "volatility": 0.10,
                "hedging": 0.10
            },
            MarketRegime.VOLATILE: {
                "momentum": 0.15,
                "mean_reversion": 0.15,
                "volatility": 0.40,
                "hedging": 0.30
            },
            MarketRegime.QUIET: {
                "momentum": 0.30,
                "mean_reversion": 0.40,
                "volatility": 0.20,
                "hedging": 0.10
            },
            MarketRegime.NEUTRAL: {
                "momentum": 0.25,
                "mean_reversion": 0.25,
                "volatility": 0.25,
                "hedging": 0.25
            }
        }
        
        return weights.get(regime, weights[MarketRegime.NEUTRAL])


# Singleton instance
_regime_detector = None

def get_regime_detector() -> MarketRegimeDetector:
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = MarketRegimeDetector()
    return _regime_detector


# Quick test
if __name__ == "__main__":
    # Generate sample data
    np.random.seed(42)
    
    # Trending market (random walk with drift)
    trending_prices = 100 * np.exp(np.cumsum(0.001 + 0.02 * np.random.randn(200)))
    
    # Mean-reverting market (Ornstein-Uhlenbeck)
    mean_rev_prices = [100]
    for _ in range(199):
        mean_rev_prices.append(
            mean_rev_prices[-1] + 0.1 * (100 - mean_rev_prices[-1]) + 2 * np.random.randn()
        )
    mean_rev_prices = np.array(mean_rev_prices)
    
    detector = MarketRegimeDetector()
    
    print("=== TRENDING MARKET ===")
    result = detector.detect_regime(trending_prices)
    print(f"Regime: {result.regime.value}")
    print(f"Hurst: {result.hurst_exponent}")
    print(f"Confidence: {result.confidence}")
    print(f"Strategies: {result.recommended_strategies}")
    
    print("\n=== MEAN-REVERTING MARKET ===")
    result = detector.detect_regime(mean_rev_prices)
    print(f"Regime: {result.regime.value}")
    print(f"Hurst: {result.hurst_exponent}")
    print(f"Confidence: {result.confidence}")
    print(f"Strategies: {result.recommended_strategies}")
