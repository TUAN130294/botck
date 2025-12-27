# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ADDITIONAL INDICATORS                                     ║
║                    Anchored VWAP, VWAP Bands, VaR Decomposition             ║
╚══════════════════════════════════════════════════════════════════════════════╝

P2 Implementation - Missing indicators from audit
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from scipy import stats


# ============================================
# ANCHORED VWAP
# ============================================

def anchored_vwap(df: pd.DataFrame, anchor_date: datetime = None,
                  anchor_idx: int = None) -> pd.Series:
    """
    Anchored VWAP - VWAP starting from a specific anchor point
    
    Args:
        df: OHLCV DataFrame
        anchor_date: Date to anchor VWAP from
        anchor_idx: Index to anchor VWAP from (alternative to date)
    
    Returns:
        Series of anchored VWAP values
    """
    if anchor_date is not None:
        mask = df.index >= anchor_date
    elif anchor_idx is not None:
        mask = pd.Series([False] * anchor_idx + [True] * (len(df) - anchor_idx), index=df.index)
    else:
        # Default: anchor from first data point
        mask = pd.Series([True] * len(df), index=df.index)
    
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    volume = df['Volume']
    
    # Calculate cumulative from anchor
    cumulative_tp_vol = (typical_price * volume).where(mask, 0).cumsum()
    cumulative_vol = volume.where(mask, 0).cumsum()
    
    avwap = cumulative_tp_vol / cumulative_vol.replace(0, np.nan)
    
    return avwap


def multi_anchor_vwap(df: pd.DataFrame, anchor_dates: List[datetime]) -> pd.DataFrame:
    """
    Multiple anchored VWAPs for key dates
    
    Args:
        df: OHLCV DataFrame
        anchor_dates: List of anchor dates
    
    Returns:
        DataFrame with VWAP for each anchor
    """
    result = pd.DataFrame(index=df.index)
    
    for i, date in enumerate(anchor_dates):
        result[f'AVWAP_{i+1}'] = anchored_vwap(df, anchor_date=date)
    
    return result


# ============================================
# VWAP BANDS
# ============================================

def vwap_bands(df: pd.DataFrame, std_multipliers: List[float] = [1, 2, 3]) -> pd.DataFrame:
    """
    VWAP with standard deviation bands
    
    Args:
        df: OHLCV DataFrame
        std_multipliers: Standard deviation multipliers for bands
    
    Returns:
        DataFrame with VWAP and bands
    """
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    volume = df['Volume']
    
    # Calculate VWAP
    cumulative_tp_vol = (typical_price * volume).cumsum()
    cumulative_vol = volume.cumsum()
    vwap = cumulative_tp_vol / cumulative_vol
    
    # Calculate standard deviation from VWAP
    sq_diff = ((typical_price - vwap) ** 2 * volume).cumsum()
    variance = sq_diff / cumulative_vol
    std = np.sqrt(variance)
    
    result = pd.DataFrame({
        'VWAP': vwap,
        'VWAP_STD': std
    }, index=df.index)
    
    for mult in std_multipliers:
        result[f'VWAP_Upper_{mult}'] = vwap + mult * std
        result[f'VWAP_Lower_{mult}'] = vwap - mult * std
    
    return result


def vwap_deviation(df: pd.DataFrame) -> pd.Series:
    """
    Calculate price deviation from VWAP (z-score)
    
    Useful for mean reversion strategies
    """
    bands = vwap_bands(df)
    
    deviation = (df['Close'] - bands['VWAP']) / bands['VWAP_STD']
    deviation = deviation.replace([np.inf, -np.inf], np.nan)
    
    return deviation


# ============================================
# VALUE AT RISK (DECOMPOSITION)
# ============================================

def marginal_var(returns: pd.DataFrame, weights: Dict[str, float],
                 confidence: float = 0.95) -> Dict[str, float]:
    """
    Marginal VaR - risk contribution per 1% increase in weight
    
    Args:
        returns: DataFrame of asset returns
        weights: Current portfolio weights
        confidence: VaR confidence level
    
    Returns:
        Dict of marginal VaR by asset
    """
    assets = list(weights.keys())
    w = np.array([weights[a] for a in assets])
    
    # Covariance matrix
    cov = returns[assets].cov() * 252  # Annualized
    
    # Portfolio variance
    port_var = np.dot(w.T, np.dot(cov, w))
    port_std = np.sqrt(port_var)
    
    # Z-score for confidence level
    z = stats.norm.ppf(1 - confidence)
    
    # Marginal VaR = (Cov * w) / portfolio_std * z
    marginal = np.dot(cov, w) / port_std * abs(z)
    
    return dict(zip(assets, marginal))


def component_var(returns: pd.DataFrame, weights: Dict[str, float],
                  confidence: float = 0.95) -> Dict[str, float]:
    """
    Component VaR - absolute risk contribution by asset
    
    Component VaR = weight * Marginal VaR
    
    Sum of component VaRs = Total Portfolio VaR
    """
    marginal = marginal_var(returns, weights, confidence)
    
    return {
        asset: weights[asset] * mvar
        for asset, mvar in marginal.items()
    }


def incremental_var(returns: pd.DataFrame, weights: Dict[str, float],
                    new_asset: str, new_weight: float,
                    confidence: float = 0.95) -> float:
    """
    Incremental VaR - change in VaR from adding a new position
    
    Args:
        returns: Current asset returns
        weights: Current portfolio weights
        new_asset: Asset to add
        new_weight: Weight of new asset
        confidence: VaR confidence level
    
    Returns:
        Change in portfolio VaR
    """
    if new_asset not in returns.columns:
        raise ValueError(f"Asset {new_asset} not in returns data")
    
    # Current portfolio VaR
    current_assets = list(weights.keys())
    current_w = np.array([weights[a] for a in current_assets])
    current_returns = returns[current_assets].dot(current_w)
    current_var = np.percentile(current_returns, (1 - confidence) * 100) * np.sqrt(252)
    
    # New portfolio with asset
    new_weights = {**weights, new_asset: new_weight}
    # Rescale weights
    total_weight = sum(new_weights.values())
    new_weights = {k: v / total_weight for k, v in new_weights.items()}
    
    new_assets = list(new_weights.keys())
    new_w = np.array([new_weights[a] for a in new_assets])
    new_port_returns = returns[new_assets].dot(new_w)
    new_var = np.percentile(new_port_returns, (1 - confidence) * 100) * np.sqrt(252)
    
    return new_var - current_var


# ============================================
# CONDITIONAL DRAWDOWN AT RISK
# ============================================

def calculate_drawdown(returns: pd.Series) -> pd.Series:
    """Calculate rolling drawdown from returns"""
    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    return drawdown


def conditional_drawdown_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Conditional Drawdown at Risk (CDaR)
    
    Average of drawdowns worse than VaR level
    Similar to CVaR but for drawdowns
    
    Args:
        returns: Return series
        confidence: Confidence level
    
    Returns:
        CDaR value (positive number)
    """
    drawdowns = calculate_drawdown(returns)
    
    # Drawdown at risk (worst quantile)
    dar = np.percentile(drawdowns, (1 - confidence) * 100)
    
    # Conditional: average of drawdowns worse than DaR
    cdar = drawdowns[drawdowns <= dar].mean()
    
    return abs(cdar)


def drawdown_duration(returns: pd.Series) -> Dict:
    """
    Analyze drawdown duration statistics
    
    Returns:
        Dict with max, avg, and current drawdown duration
    """
    cumulative = (1 + returns).cumprod()
    peak = cumulative.cummax()
    
    # Find drawdown periods
    in_drawdown = cumulative < peak
    
    # Calculate duration of each drawdown
    durations = []
    current_duration = 0
    
    for is_dd in in_drawdown:
        if is_dd:
            current_duration += 1
        else:
            if current_duration > 0:
                durations.append(current_duration)
            current_duration = 0
    
    # Add current ongoing drawdown
    if current_duration > 0:
        durations.append(current_duration)
    
    return {
        'max_duration': max(durations) if durations else 0,
        'avg_duration': np.mean(durations) if durations else 0,
        'current_duration': current_duration,
        'total_drawdowns': len(durations)
    }


# ============================================
# MULTI-PERIOD EXPECTED SHORTFALL
# ============================================

def multi_period_es(returns: pd.Series, periods: List[int] = [1, 5, 10, 21],
                    confidence: float = 0.95) -> Dict[str, float]:
    """
    Expected Shortfall (CVaR) for multiple holding periods
    
    Args:
        returns: Daily return series
        periods: List of holding periods (days)
        confidence: Confidence level
    
    Returns:
        Dict of ES values for each period
    """
    result = {}
    
    for period in periods:
        # Calculate n-period returns
        if period == 1:
            period_returns = returns
        else:
            period_returns = returns.rolling(period).apply(
                lambda x: (1 + x).prod() - 1,
                raw=False
            ).dropna()
        
        if len(period_returns) < 20:
            result[f'ES_{period}d'] = np.nan
            continue
        
        # VaR
        var = np.percentile(period_returns, (1 - confidence) * 100)
        
        # ES (CVaR) = average of returns below VaR
        es = period_returns[period_returns <= var].mean()
        
        result[f'ES_{period}d'] = abs(es)
    
    return result


# ============================================
# ADVANCED RISK METRICS
# ============================================

def downside_deviation(returns: pd.Series, threshold: float = 0) -> float:
    """
    Downside deviation (semi-deviation below threshold)
    
    Used in Sortino ratio calculation
    """
    downside = returns[returns < threshold] - threshold
    return np.sqrt(np.mean(downside ** 2)) * np.sqrt(252)


def upside_potential_ratio(returns: pd.Series, threshold: float = 0) -> float:
    """
    Upside Potential Ratio
    
    Ratio of upside potential to downside risk
    """
    upside = returns[returns > threshold] - threshold
    upside_potential = np.mean(upside) * np.sqrt(252) if len(upside) > 0 else 0
    
    downside = abs(downside_deviation(returns, threshold))
    
    if downside == 0:
        return np.inf if upside_potential > 0 else 0
    
    return upside_potential / downside


def gain_loss_ratio(returns: pd.Series) -> float:
    """
    Gain-Loss Ratio
    
    Average gain / average loss
    """
    gains = returns[returns > 0]
    losses = returns[returns < 0]
    
    avg_gain = gains.mean() if len(gains) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
    
    if avg_loss == 0:
        return np.inf if avg_gain > 0 else 0
    
    return avg_gain / avg_loss


def pain_index(returns: pd.Series) -> float:
    """
    Pain Index
    
    Average drawdown over entire period
    """
    drawdowns = calculate_drawdown(returns)
    return abs(drawdowns.mean())


def pain_ratio(returns: pd.Series, risk_free: float = 0.05) -> float:
    """
    Pain Ratio
    
    Excess return / Pain Index
    """
    total_return = (1 + returns).prod() - 1
    excess_return = total_return - risk_free * len(returns) / 252
    
    pain = pain_index(returns)
    
    if pain == 0:
        return np.inf if excess_return > 0 else 0
    
    return excess_return / pain


# ============================================
# TESTING
# ============================================

def test_indicators():
    """Test additional indicators"""
    print("Testing Additional Indicators...")
    print("=" * 50)
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
    
    # OHLCV data
    close = 50000 + np.cumsum(np.random.randn(252) * 500)
    df = pd.DataFrame({
        'Open': close + np.random.randn(252) * 100,
        'High': close + np.abs(np.random.randn(252) * 200),
        'Low': close - np.abs(np.random.randn(252) * 200),
        'Close': close,
        'Volume': np.random.randint(100000, 1000000, 252)
    }, index=dates)
    
    # Returns data
    returns = df['Close'].pct_change().dropna()
    
    # Test VWAP Bands
    print("\n📊 VWAP Bands:")
    bands = vwap_bands(df)
    print(f"   VWAP: {bands['VWAP'].iloc[-1]:,.0f}")
    print(f"   Upper 2σ: {bands['VWAP_Upper_2'].iloc[-1]:,.0f}")
    print(f"   Lower 2σ: {bands['VWAP_Lower_2'].iloc[-1]:,.0f}")
    
    # Test Anchored VWAP
    print("\n📈 Anchored VWAP:")
    anchor = dates[100]
    avwap = anchored_vwap(df, anchor_date=anchor)
    print(f"   Anchored from: {anchor.date()}")
    print(f"   Current AVWAP: {avwap.iloc[-1]:,.0f}")
    
    # Test VaR Decomposition
    print("\n⚠️ VaR Decomposition:")
    portfolio_returns = pd.DataFrame({
        'HPG': np.random.normal(0.001, 0.02, 252),
        'VNM': np.random.normal(0.0008, 0.015, 252),
        'FPT': np.random.normal(0.0012, 0.025, 252)
    })
    weights = {'HPG': 0.4, 'VNM': 0.35, 'FPT': 0.25}
    
    mvar = marginal_var(portfolio_returns, weights)
    cvar = component_var(portfolio_returns, weights)
    print(f"   Marginal VaR: {dict((k, f'{v:.4f}') for k, v in mvar.items())}")
    print(f"   Component VaR: {dict((k, f'{v:.4f}') for k, v in cvar.items())}")
    
    # Test CDaR
    print("\n📉 Drawdown Analysis:")
    cdar = conditional_drawdown_at_risk(returns)
    dd_stats = drawdown_duration(returns)
    print(f"   CDaR 95%: {cdar:.2%}")
    print(f"   Max Duration: {dd_stats['max_duration']} days")
    print(f"   Avg Duration: {dd_stats['avg_duration']:.1f} days")
    
    # Test Multi-period ES
    print("\n📊 Multi-period Expected Shortfall:")
    es = multi_period_es(returns)
    for period, value in es.items():
        print(f"   {period}: {value:.4f}")
    
    print("\n✅ Additional indicators tests completed!")


if __name__ == "__main__":
    test_indicators()
