# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ADVANCED CHART TYPES                                      ║
║                    Renko, Heikin Ashi, Point & Figure                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Gap Analysis: Chart Types Coverage 70% → 90%
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ============================================
# HEIKIN ASHI
# ============================================

def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Heikin Ashi candles
    
    Heikin Ashi smooths price action and makes trends easier to identify.
    
    Formulas:
    - HA Close = (Open + High + Low + Close) / 4
    - HA Open = (Previous HA Open + Previous HA Close) / 2
    - HA High = max(High, HA Open, HA Close)
    - HA Low = min(Low, HA Open, HA Close)
    """
    ha = pd.DataFrame(index=df.index)
    
    # HA Close
    ha['Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
    
    # HA Open (start with actual open)
    ha['Open'] = 0.0
    ha.iloc[0, ha.columns.get_loc('Open')] = df['Open'].iloc[0]
    
    for i in range(1, len(df)):
        ha.iloc[i, ha.columns.get_loc('Open')] = (
            ha['Open'].iloc[i-1] + ha['Close'].iloc[i-1]
        ) / 2
    
    # HA High and Low
    ha['High'] = df[['High']].join(ha[['Open', 'Close']]).max(axis=1)
    ha['Low'] = df[['Low']].join(ha[['Open', 'Close']]).min(axis=1)
    
    # Keep volume
    if 'Volume' in df.columns:
        ha['Volume'] = df['Volume']
    
    return ha


def plot_heikin_ashi(df: pd.DataFrame, title: str = "Heikin Ashi Chart") -> go.Figure:
    """Create Heikin Ashi candlestick chart"""
    ha = calculate_heikin_ashi(df)
    
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=ha.index,
        open=ha['Open'],
        high=ha['High'],
        low=ha['Low'],
        close=ha['Close'],
        name='Heikin Ashi',
        increasing_line_color='#00ff88',
        decreasing_line_color='#ff4444'
    ))
    
    fig.update_layout(
        title=title,
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=500
    )
    
    return fig


# ============================================
# RENKO
# ============================================

@dataclass
class RenkoBrick:
    """Single Renko brick"""
    date: pd.Timestamp
    open: float
    close: float
    direction: str  # 'up' or 'down'


def calculate_renko(df: pd.DataFrame, brick_size: float = None, 
                    atr_period: int = 14) -> List[RenkoBrick]:
    """
    Calculate Renko bricks
    
    Renko charts filter out noise by using fixed price movements (bricks).
    A new brick is only drawn when price moves by the brick size amount.
    
    Args:
        df: OHLCV DataFrame
        brick_size: Fixed brick size (if None, uses ATR)
        atr_period: Period for ATR calculation
    """
    if df.empty:
        return []
    
    # Calculate brick size from ATR if not provided
    if brick_size is None:
        tr = pd.DataFrame()
        tr['hl'] = df['High'] - df['Low']
        tr['hc'] = abs(df['High'] - df['Close'].shift())
        tr['lc'] = abs(df['Low'] - df['Close'].shift())
        tr['tr'] = tr[['hl', 'hc', 'lc']].max(axis=1)
        atr = tr['tr'].rolling(window=atr_period).mean().iloc[-1]
        brick_size = atr
    
    if brick_size <= 0:
        brick_size = df['Close'].mean() * 0.02  # 2% of average price
    
    bricks = []
    prices = df['Close'].values
    dates = df.index
    
    if len(prices) == 0:
        return bricks
    
    # Initialize first brick
    current_price = prices[0]
    brick_start = (current_price // brick_size) * brick_size
    
    for i, (date, price) in enumerate(zip(dates, prices)):
        # Check for up bricks
        while price >= brick_start + 2 * brick_size:
            bricks.append(RenkoBrick(
                date=date,
                open=brick_start,
                close=brick_start + brick_size,
                direction='up'
            ))
            brick_start += brick_size
        
        # Check for down bricks
        while price <= brick_start - brick_size:
            bricks.append(RenkoBrick(
                date=date,
                open=brick_start,
                close=brick_start - brick_size,
                direction='down'
            ))
            brick_start -= brick_size
    
    return bricks


def plot_renko(df: pd.DataFrame, brick_size: float = None,
               title: str = "Renko Chart") -> go.Figure:
    """Create Renko chart"""
    bricks = calculate_renko(df, brick_size)
    
    if not bricks:
        return go.Figure()
    
    fig = go.Figure()
    
    for i, brick in enumerate(bricks):
        color = '#00ff88' if brick.direction == 'up' else '#ff4444'
        
        # Draw brick as filled rectangle
        fig.add_trace(go.Scatter(
            x=[i, i+1, i+1, i, i],
            y=[brick.open, brick.open, brick.close, brick.close, brick.open],
            fill='toself',
            fillcolor=color,
            line=dict(color=color),
            mode='lines',
            showlegend=False,
            hovertemplate=f"Brick {i+1}<br>Open: {brick.open:.2f}<br>Close: {brick.close:.2f}<extra></extra>"
        ))
    
    fig.update_layout(
        title=title,
        template='plotly_dark',
        height=500,
        xaxis_title='Brick Number',
        yaxis_title='Price'
    )
    
    return fig


# ============================================
# POINT & FIGURE
# ============================================

@dataclass
class PFColumn:
    """Point & Figure column"""
    start_price: float
    end_price: float
    boxes: List[float]
    direction: str  # 'X' (up) or 'O' (down)


def calculate_point_figure(df: pd.DataFrame, box_size: float = None,
                          reversal: int = 3) -> List[PFColumn]:
    """
    Calculate Point & Figure chart data
    
    P&F charts use Xs for rising prices and Os for falling prices.
    A reversal occurs when price moves by (reversal * box_size) in opposite direction.
    
    Args:
        df: OHLCV DataFrame
        box_size: Fixed box size (if None, uses ATR/10)
        reversal: Number of boxes needed for reversal (typically 3)
    """
    if df.empty:
        return []
    
    # Calculate box size
    if box_size is None:
        price_range = df['High'].max() - df['Low'].min()
        box_size = price_range / 100  # 100 boxes
    
    if box_size <= 0:
        box_size = df['Close'].mean() * 0.01
    
    columns = []
    highs = df['High'].values
    lows = df['Low'].values
    
    # Initialize
    current_direction = 'X'  # Start with up
    current_boxes = []
    column_start = (highs[0] // box_size) * box_size
    current_price = column_start
    
    for high, low in zip(highs, lows):
        if current_direction == 'X':
            # Looking for higher highs
            while high >= current_price + box_size:
                current_price += box_size
                current_boxes.append(current_price)
            
            # Check for reversal
            if low <= current_price - reversal * box_size:
                # Save current column
                if current_boxes:
                    columns.append(PFColumn(
                        start_price=column_start,
                        end_price=current_price,
                        boxes=current_boxes.copy(),
                        direction='X'
                    ))
                
                # Start new down column
                current_direction = 'O'
                column_start = current_price
                current_boxes = []
                current_price -= box_size
                current_boxes.append(current_price)
        
        else:  # direction == 'O'
            # Looking for lower lows
            while low <= current_price - box_size:
                current_price -= box_size
                current_boxes.append(current_price)
            
            # Check for reversal
            if high >= current_price + reversal * box_size:
                # Save current column
                if current_boxes:
                    columns.append(PFColumn(
                        start_price=column_start,
                        end_price=current_price,
                        boxes=current_boxes.copy(),
                        direction='O'
                    ))
                
                # Start new up column
                current_direction = 'X'
                column_start = current_price
                current_boxes = []
                current_price += box_size
                current_boxes.append(current_price)
    
    # Add final column
    if current_boxes:
        columns.append(PFColumn(
            start_price=column_start,
            end_price=current_price,
            boxes=current_boxes.copy(),
            direction=current_direction
        ))
    
    return columns


def plot_point_figure(df: pd.DataFrame, box_size: float = None,
                     reversal: int = 3, title: str = "Point & Figure") -> go.Figure:
    """Create Point & Figure chart"""
    columns = calculate_point_figure(df, box_size, reversal)
    
    if not columns:
        return go.Figure()
    
    fig = go.Figure()
    
    for col_idx, column in enumerate(columns):
        color = '#00ff88' if column.direction == 'X' else '#ff4444'
        symbol = 'x' if column.direction == 'X' else 'circle-open'
        
        for price in column.boxes:
            fig.add_trace(go.Scatter(
                x=[col_idx],
                y=[price],
                mode='markers',
                marker=dict(
                    symbol=symbol,
                    size=15,
                    color=color
                ),
                showlegend=False,
                hovertemplate=f"Column {col_idx+1}<br>Price: {price:.2f}<br>Type: {column.direction}<extra></extra>"
            ))
    
    fig.update_layout(
        title=title,
        template='plotly_dark',
        height=500,
        xaxis_title='Column',
        yaxis_title='Price'
    )
    
    return fig


# ============================================
# KAGI CHART
# ============================================

@dataclass
class KagiLine:
    """Kagi line segment"""
    start_price: float
    end_price: float
    is_yang: bool  # Yang (thick) = bullish, Yin (thin) = bearish


def calculate_kagi(df: pd.DataFrame, reversal_pct: float = 0.04) -> List[KagiLine]:
    """
    Calculate Kagi chart data
    
    Kagi charts change direction when price reverses by a certain percentage.
    Yang (thick) lines indicate bullish, Yin (thin) lines indicate bearish.
    
    Args:
        df: OHLCV DataFrame
        reversal_pct: Percentage for reversal (default 4%)
    """
    if df.empty:
        return []
    
    lines = []
    prices = df['Close'].values
    
    if len(prices) < 2:
        return lines
    
    current_price = prices[0]
    direction = 1 if prices[1] > prices[0] else -1
    is_yang = direction == 1
    line_start = prices[0]
    
    for price in prices[1:]:
        if direction == 1:  # Currently going up
            if price > current_price:
                current_price = price
            elif price <= current_price * (1 - reversal_pct):
                # Reversal down
                lines.append(KagiLine(line_start, current_price, is_yang))
                line_start = current_price
                current_price = price
                direction = -1
                # Check if we break previous low
                if lines and current_price < lines[-1].start_price:
                    is_yang = False
        
        else:  # Currently going down
            if price < current_price:
                current_price = price
            elif price >= current_price * (1 + reversal_pct):
                # Reversal up
                lines.append(KagiLine(line_start, current_price, is_yang))
                line_start = current_price
                current_price = price
                direction = 1
                # Check if we break previous high
                if lines and current_price > lines[-1].start_price:
                    is_yang = True
    
    # Add final line
    lines.append(KagiLine(line_start, current_price, is_yang))
    
    return lines


def plot_kagi(df: pd.DataFrame, reversal_pct: float = 0.04,
              title: str = "Kagi Chart") -> go.Figure:
    """Create Kagi chart"""
    lines = calculate_kagi(df, reversal_pct)
    
    if not lines:
        return go.Figure()
    
    fig = go.Figure()
    
    x_pos = 0
    for i, line in enumerate(lines):
        color = '#00ff88' if line.is_yang else '#ff4444'
        width = 3 if line.is_yang else 1
        
        # Vertical line
        fig.add_trace(go.Scatter(
            x=[x_pos, x_pos],
            y=[line.start_price, line.end_price],
            mode='lines',
            line=dict(color=color, width=width),
            showlegend=False,
            hovertemplate=f"Line {i+1}<br>Start: {line.start_price:.2f}<br>End: {line.end_price:.2f}<extra></extra>"
        ))
        
        # Horizontal connector to next column
        if i < len(lines) - 1:
            fig.add_trace(go.Scatter(
                x=[x_pos, x_pos + 1],
                y=[line.end_price, line.end_price],
                mode='lines',
                line=dict(color=color, width=width),
                showlegend=False
            ))
        
        x_pos += 1
    
    fig.update_layout(
        title=title,
        template='plotly_dark',
        height=500,
        xaxis_title='Line Number',
        yaxis_title='Price'
    )
    
    return fig


# ============================================
# COMBINED CHART BUILDER
# ============================================

class ChartBuilder:
    """
    Unified chart builder for all chart types
    """
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
    
    def candlestick(self, title: str = "Candlestick") -> go.Figure:
        """Standard candlestick chart"""
        fig = go.Figure()
        
        fig.add_trace(go.Candlestick(
            x=self.df.index,
            open=self.df['Open'],
            high=self.df['High'],
            low=self.df['Low'],
            close=self.df['Close'],
            increasing_line_color='#00ff88',
            decreasing_line_color='#ff4444'
        ))
        
        fig.update_layout(
            title=title,
            template='plotly_dark',
            xaxis_rangeslider_visible=False,
            height=500
        )
        
        return fig
    
    def heikin_ashi(self, title: str = "Heikin Ashi") -> go.Figure:
        return plot_heikin_ashi(self.df, title)
    
    def renko(self, brick_size: float = None, title: str = "Renko") -> go.Figure:
        return plot_renko(self.df, brick_size, title)
    
    def point_figure(self, box_size: float = None, reversal: int = 3,
                    title: str = "Point & Figure") -> go.Figure:
        return plot_point_figure(self.df, box_size, reversal, title)
    
    def kagi(self, reversal_pct: float = 0.04, title: str = "Kagi") -> go.Figure:
        return plot_kagi(self.df, reversal_pct, title)
    
    def line(self, title: str = "Line Chart") -> go.Figure:
        """Simple line chart"""
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=self.df.index,
            y=self.df['Close'],
            mode='lines',
            line=dict(color='#00e5ff'),
            name='Close'
        ))
        
        fig.update_layout(
            title=title,
            template='plotly_dark',
            height=500
        )
        
        return fig
    
    def area(self, title: str = "Area Chart") -> go.Figure:
        """Area chart"""
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=self.df.index,
            y=self.df['Close'],
            mode='lines',
            fill='tozeroy',
            fillcolor='rgba(0, 229, 255, 0.2)',
            line=dict(color='#00e5ff'),
            name='Close'
        ))
        
        fig.update_layout(
            title=title,
            template='plotly_dark',
            height=500
        )
        
        return fig


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    print("Testing Advanced Chart Types...")
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=200, freq='D')
    base_price = 50
    returns = np.random.normal(0.001, 0.02, 200)
    prices = base_price * np.cumprod(1 + returns)
    
    df = pd.DataFrame({
        'Open': prices * (1 + np.random.uniform(-0.01, 0.01, 200)),
        'High': prices * (1 + np.random.uniform(0, 0.02, 200)),
        'Low': prices * (1 - np.random.uniform(0, 0.02, 200)),
        'Close': prices,
        'Volume': np.random.randint(100000, 1000000, 200)
    }, index=dates)
    
    # Test Heikin Ashi
    ha = calculate_heikin_ashi(df)
    print(f"Heikin Ashi: {len(ha)} candles")
    
    # Test Renko
    renko = calculate_renko(df)
    print(f"Renko: {len(renko)} bricks")
    
    # Test Point & Figure
    pf = calculate_point_figure(df)
    print(f"Point & Figure: {len(pf)} columns")
    
    # Test Kagi
    kagi = calculate_kagi(df)
    print(f"Kagi: {len(kagi)} lines")
    
    print("\nAll chart types working!")
