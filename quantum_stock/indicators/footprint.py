# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    FOOTPRINT & MARKET PROFILE CHARTS                        ║
║                    Professional Order Flow Analysis                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

P1 Implementation - Advanced order flow visualization
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ============================================
# DATA MODELS
# ============================================

@dataclass
class FootprintLevel:
    """Single price level in footprint"""
    price: float
    bid_volume: int = 0
    ask_volume: int = 0
    delta: int = 0  # ask - bid
    trades: int = 0
    
    @property
    def total_volume(self) -> int:
        return self.bid_volume + self.ask_volume
    
    @property
    def imbalance_ratio(self) -> float:
        if self.total_volume == 0:
            return 0
        return self.delta / self.total_volume


@dataclass
class FootprintBar:
    """Footprint bar (single candle with order flow)"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    levels: Dict[float, FootprintLevel] = field(default_factory=dict)
    
    @property
    def total_delta(self) -> int:
        return sum(level.delta for level in self.levels.values())
    
    @property
    def poc(self) -> float:
        """Point of Control - price with highest volume"""
        if not self.levels:
            return self.close
        return max(self.levels.keys(), key=lambda p: self.levels[p].total_volume)
    
    @property
    def vah(self) -> float:
        """Value Area High"""
        return self._value_area()[1]
    
    @property
    def val(self) -> float:
        """Value Area Low"""
        return self._value_area()[0]
    
    def _value_area(self, pct: float = 0.70) -> Tuple[float, float]:
        """Calculate value area (70% of volume)"""
        if not self.levels:
            return (self.low, self.high)
        
        total_vol = sum(l.total_volume for l in self.levels.values())
        target_vol = total_vol * pct
        
        sorted_levels = sorted(self.levels.items(), key=lambda x: x[1].total_volume, reverse=True)
        
        accumulated = 0
        prices = []
        
        for price, level in sorted_levels:
            accumulated += level.total_volume
            prices.append(price)
            if accumulated >= target_vol:
                break
        
        return (min(prices), max(prices)) if prices else (self.low, self.high)


@dataclass
class TPOProfile:
    """Time-Price Opportunity Profile (Market Profile)"""
    date: datetime
    levels: Dict[float, List[str]] = field(default_factory=dict)  # price -> list of TPO letters
    
    @property
    def poc(self) -> float:
        """Point of Control"""
        if not self.levels:
            return 0
        return max(self.levels.keys(), key=lambda p: len(self.levels[p]))
    
    @property
    def value_area(self) -> Tuple[float, float]:
        """70% value area"""
        if not self.levels:
            return (0, 0)
        
        total_tpos = sum(len(letters) for letters in self.levels.values())
        target = total_tpos * 0.70
        
        sorted_levels = sorted(self.levels.items(), key=lambda x: len(x[1]), reverse=True)
        
        accumulated = 0
        prices = []
        
        for price, letters in sorted_levels:
            accumulated += len(letters)
            prices.append(price)
            if accumulated >= target:
                break
        
        return (min(prices), max(prices)) if prices else (0, 0)


# ============================================
# FOOTPRINT CALCULATOR
# ============================================

class FootprintCalculator:
    """
    Calculate footprint chart data from OHLCV
    
    Note: Real footprint requires tick data.
    This implementation estimates order flow from OHLCV.
    """
    
    def __init__(self, tick_size: float = 100):  # VN stocks: 100 VND tick
        self.tick_size = tick_size
    
    def calculate(self, df: pd.DataFrame, n_levels: int = 10) -> List[FootprintBar]:
        """
        Calculate footprint bars from OHLCV data
        
        Args:
            df: OHLCV DataFrame
            n_levels: Number of price levels per bar
        """
        footprints = []
        
        for idx, row in df.iterrows():
            # Create price levels
            price_range = row['High'] - row['Low']
            if price_range == 0:
                continue
            
            level_size = price_range / n_levels
            levels = {}
            
            # Estimate volume distribution (simplified)
            # In reality, this requires tick data
            for i in range(n_levels):
                price = row['Low'] + i * level_size + level_size / 2
                price = round(price / self.tick_size) * self.tick_size
                
                # Estimate volume at this level
                # Distribute based on proximity to OHLC
                weight = self._estimate_weight(price, row)
                level_volume = int(row['Volume'] * weight / n_levels)
                
                # Estimate bid/ask split
                if row['Close'] >= row['Open']:  # Bullish bar
                    ask_ratio = 0.6
                else:  # Bearish bar
                    ask_ratio = 0.4
                
                # Adjust for price position
                if price > (row['Open'] + row['Close']) / 2:
                    ask_ratio += 0.1
                else:
                    ask_ratio -= 0.1
                
                ask_vol = int(level_volume * ask_ratio)
                bid_vol = level_volume - ask_vol
                
                levels[price] = FootprintLevel(
                    price=price,
                    bid_volume=bid_vol,
                    ask_volume=ask_vol,
                    delta=ask_vol - bid_vol,
                    trades=max(1, level_volume // 100)
                )
            
            footprints.append(FootprintBar(
                timestamp=idx if isinstance(idx, datetime) else datetime.now(),
                open=row['Open'],
                high=row['High'],
                low=row['Low'],
                close=row['Close'],
                levels=levels
            ))
        
        return footprints
    
    def _estimate_weight(self, price: float, row: pd.Series) -> float:
        """Estimate volume weight at price level"""
        mid = (row['High'] + row['Low']) / 2
        distance = abs(price - mid) / (row['High'] - row['Low']) if row['High'] != row['Low'] else 0
        # Normal distribution-like weight
        return np.exp(-2 * distance ** 2)


# ============================================
# MARKET PROFILE CALCULATOR
# ============================================

class MarketProfileCalculator:
    """
    Calculate Market Profile (TPO)
    
    Time-Price Opportunity analysis
    """
    
    TPO_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    
    def __init__(self, tick_size: float = 100):
        self.tick_size = tick_size
    
    def calculate_daily(self, df: pd.DataFrame, periods_per_day: int = 13) -> TPOProfile:
        """
        Calculate daily Market Profile
        
        Args:
            df: OHLCV DataFrame (intraday data recommended)
            periods_per_day: Number of 30-min periods in trading day
        """
        levels: Dict[float, List[str]] = {}
        
        # Group into TPO periods
        rows_per_period = max(1, len(df) // periods_per_day)
        
        for i, (idx, row) in enumerate(df.iterrows()):
            period_idx = min(i // rows_per_period, len(self.TPO_LETTERS) - 1)
            letter = self.TPO_LETTERS[period_idx]
            
            # Add TPO at each price level touched
            high = round(row['High'] / self.tick_size) * self.tick_size
            low = round(row['Low'] / self.tick_size) * self.tick_size
            
            price = low
            while price <= high:
                if price not in levels:
                    levels[price] = []
                if letter not in levels[price]:
                    levels[price].append(letter)
                price += self.tick_size
        
        return TPOProfile(
            date=df.index[0] if len(df) > 0 else datetime.now(),
            levels=levels
        )
    
    def calculate_composite(self, df: pd.DataFrame, lookback_days: int = 20) -> TPOProfile:
        """Calculate composite profile over multiple days"""
        levels: Dict[float, List[str]] = {}
        
        # Process each day
        if not df.empty:
            for date, group in df.groupby(df.index.date):
                daily_profile = self.calculate_daily(group)
                
                for price, letters in daily_profile.levels.items():
                    if price not in levels:
                        levels[price] = []
                    levels[price].extend(letters)
        
        return TPOProfile(
            date=datetime.now(),
            levels=levels
        )


# ============================================
# VISUALIZATION
# ============================================

def plot_footprint(footprints: List[FootprintBar], 
                   title: str = "Footprint Chart") -> go.Figure:
    """Create footprint chart visualization"""
    
    if not footprints:
        return go.Figure()
    
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.75, 0.25],
        shared_xaxes=True,
        vertical_spacing=0.03
    )
    
    # Candlestick
    dates = [fp.timestamp for fp in footprints]
    opens = [fp.open for fp in footprints]
    highs = [fp.high for fp in footprints]
    lows = [fp.low for fp in footprints]
    closes = [fp.close for fp in footprints]
    
    fig.add_trace(go.Candlestick(
        x=dates,
        open=opens,
        high=highs,
        low=lows,
        close=closes,
        increasing_line_color='#00ff88',
        decreasing_line_color='#ff4444',
        name='Price'
    ), row=1, col=1)
    
    # Delta bars
    deltas = [fp.total_delta for fp in footprints]
    colors = ['#00ff88' if d > 0 else '#ff4444' for d in deltas]
    
    fig.add_trace(go.Bar(
        x=dates,
        y=deltas,
        marker_color=colors,
        name='Delta'
    ), row=2, col=1)
    
    # Add POC lines
    for i, fp in enumerate(footprints):
        poc = fp.poc
        fig.add_shape(
            type="line",
            x0=i - 0.3, x1=i + 0.3,
            y0=poc, y1=poc,
            line=dict(color="yellow", width=2),
            row=1, col=1
        )
    
    fig.update_layout(
        title=title,
        template='plotly_dark',
        height=700,
        xaxis_rangeslider_visible=False,
        showlegend=False
    )
    
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Delta", row=2, col=1)
    
    return fig


def plot_market_profile(profile: TPOProfile,
                        title: str = "Market Profile") -> go.Figure:
    """Create Market Profile (TPO) visualization"""
    
    if not profile.levels:
        return go.Figure()
    
    fig = go.Figure()
    
    # Sort price levels
    sorted_prices = sorted(profile.levels.keys())
    
    # Create TPO horizontal bars
    for price in sorted_prices:
        letters = profile.levels[price]
        n_tpos = len(letters)
        
        # Color based on TPO count
        intensity = min(1, n_tpos / 10)
        color = f'rgba(0, 229, 255, {intensity})'
        
        fig.add_trace(go.Bar(
            y=[price],
            x=[n_tpos],
            orientation='h',
            marker_color=color,
            text=f"{''.join(letters[:5])}{'...' if len(letters) > 5 else ''}",
            textposition='outside',
            showlegend=False,
            hovertemplate=f"Price: {price}<br>TPOs: {n_tpos}<br>{' '.join(letters)}<extra></extra>"
        ))
    
    # Add POC line
    poc = profile.poc
    fig.add_hline(
        y=poc,
        line_dash="dash",
        line_color="yellow",
        annotation_text=f"POC: {poc:,.0f}"
    )
    
    # Add Value Area
    val, vah = profile.value_area
    fig.add_hrect(
        y0=val, y1=vah,
        fillcolor="rgba(255, 235, 59, 0.1)",
        line=dict(color="rgba(255, 235, 59, 0.5)", width=1),
        annotation_text=f"VA: {val:,.0f} - {vah:,.0f}"
    )
    
    fig.update_layout(
        title=title,
        template='plotly_dark',
        height=600,
        xaxis_title="TPO Count",
        yaxis_title="Price",
        barmode='stack'
    )
    
    return fig


def plot_volume_profile(df: pd.DataFrame, 
                        n_bins: int = 30,
                        title: str = "Volume Profile") -> go.Figure:
    """Create Volume Profile visualization"""
    
    if df.empty:
        return go.Figure()
    
    # Calculate volume at each price level
    price_min = df['Low'].min()
    price_max = df['High'].max()
    bin_size = (price_max - price_min) / n_bins
    
    volume_profile = {}
    
    for _, row in df.iterrows():
        # Distribute volume across price range
        low_bin = int((row['Low'] - price_min) / bin_size)
        high_bin = int((row['High'] - price_min) / bin_size)
        
        n_levels = high_bin - low_bin + 1
        vol_per_level = row['Volume'] / max(1, n_levels)
        
        for b in range(low_bin, high_bin + 1):
            price = price_min + b * bin_size + bin_size / 2
            if price not in volume_profile:
                volume_profile[price] = 0
            volume_profile[price] += vol_per_level
    
    # Sort and prepare data
    prices = sorted(volume_profile.keys())
    volumes = [volume_profile[p] for p in prices]
    
    # Find POC
    poc = prices[volumes.index(max(volumes))]
    
    # Value Area (70%)
    total_vol = sum(volumes)
    target_vol = total_vol * 0.70
    
    sorted_by_vol = sorted(zip(prices, volumes), key=lambda x: x[1], reverse=True)
    accumulated = 0
    va_prices = []
    
    for p, v in sorted_by_vol:
        accumulated += v
        va_prices.append(p)
        if accumulated >= target_vol:
            break
    
    val = min(va_prices)
    vah = max(va_prices)
    
    # Create figure
    fig = make_subplots(
        rows=1, cols=2,
        column_widths=[0.75, 0.25],
        horizontal_spacing=0.02
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        increasing_line_color='#00ff88',
        decreasing_line_color='#ff4444',
        name='Price'
    ), row=1, col=1)
    
    # Volume Profile bars
    colors = ['yellow' if abs(p - poc) < bin_size else '#00e5ff' for p in prices]
    
    fig.add_trace(go.Bar(
        y=prices,
        x=volumes,
        orientation='h',
        marker_color=colors,
        name='Volume Profile',
        opacity=0.7
    ), row=1, col=2)
    
    # POC line
    fig.add_hline(
        y=poc,
        line_dash="dash",
        line_color="yellow",
        annotation_text=f"POC"
    )
    
    # Value Area
    fig.add_hrect(
        y0=val, y1=vah,
        fillcolor="rgba(255, 235, 59, 0.1)",
        line=dict(color="rgba(255, 235, 59, 0.3)")
    )
    
    fig.update_layout(
        title=title,
        template='plotly_dark',
        height=600,
        xaxis_rangeslider_visible=False,
        showlegend=False
    )
    
    return fig


# ============================================
# TESTING
# ============================================

def test_footprint():
    """Test footprint and market profile"""
    print("Testing Footprint & Market Profile...")
    print("=" * 50)
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=20, freq='D')
    base_price = 25000
    
    data = []
    for i, date in enumerate(dates):
        close = base_price + np.random.randn() * 500
        high = close + np.random.uniform(100, 500)
        low = close - np.random.uniform(100, 500)
        open_price = low + np.random.uniform(0, high - low)
        volume = np.random.randint(100000, 1000000)
        
        data.append({
            'Open': open_price,
            'High': high,
            'Low': low,
            'Close': close,
            'Volume': volume
        })
        base_price = close
    
    df = pd.DataFrame(data, index=dates)
    
    # Test Footprint Calculator
    fp_calc = FootprintCalculator(tick_size=100)
    footprints = fp_calc.calculate(df, n_levels=8)
    
    print(f"\n📊 Footprint Chart:")
    print(f"   Bars: {len(footprints)}")
    if footprints:
        last_fp = footprints[-1]
        print(f"   Last POC: {last_fp.poc:,.0f}")
        print(f"   Last Delta: {last_fp.total_delta:,}")
        print(f"   Value Area: {last_fp.val:,.0f} - {last_fp.vah:,.0f}")
    
    # Test Market Profile
    mp_calc = MarketProfileCalculator(tick_size=100)
    profile = mp_calc.calculate_daily(df)
    
    print(f"\n📈 Market Profile:")
    print(f"   Levels: {len(profile.levels)}")
    print(f"   POC: {profile.poc:,.0f}")
    val, vah = profile.value_area
    print(f"   Value Area: {val:,.0f} - {vah:,.0f}")
    
    print("\n✅ Footprint & Market Profile tests completed!")


if __name__ == "__main__":
    test_footprint()
