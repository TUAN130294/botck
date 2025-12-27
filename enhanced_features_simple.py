"""
Enhanced Features - SIMPLE VERSION
===================================
Chỉ 15 features tốt nhất, loại bỏ noise

Selected from 40 features based on:
- Predictive power
- Low noise
- VN market specific
"""

import pandas as pd
import numpy as np


def calculate_simple_moving_average(series, period):
    """Simple Moving Average"""
    return series.rolling(window=period).mean()


def calculate_rsi(series, period=14):
    """Relative Strength Index"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_vn_market_features_simple(df, vn_index_df=None):
    """
    Calculate SIMPLE enhanced features for VN market

    Only 15 features (vs 40):
    1. Price data (4): open, high, low, close
    2. Volume (2): volume, volume_ratio
    3. Price momentum (3): change_1d, change_5d, sma_20
    4. Technical (2): RSI, volatility
    5. Market context (2): VN-Index correlation, relative_strength
    6. Calendar (2): Tet season, month

    Total: 15 features
    """

    features = df.copy()

    # ===== 1. PRICE DATA (4 features) =====
    # Already have: open, high, low, close, volume

    # ===== 2. VOLUME (2 features) =====
    features['volume_sma_20'] = features['volume'].rolling(20).mean()
    features['volume_ratio'] = features['volume'] / features['volume_sma_20']

    # ===== 3. PRICE MOMENTUM (3 features) =====
    features['price_change_1d'] = df['close'].pct_change(1)
    features['price_change_5d'] = df['close'].pct_change(5)
    features['sma_20'] = calculate_simple_moving_average(df['close'], 20)

    # ===== 4. TECHNICAL (2 features) =====
    features['rsi'] = calculate_rsi(df['close'], 14)

    # Volatility (20-day rolling std of returns)
    features['volatility'] = features['price_change_1d'].rolling(20).std()

    # ===== 5. MARKET CONTEXT (2 features) =====
    if vn_index_df is not None:
        # Ensure both have date index
        if 'date' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            df_temp = df.set_index('date')
        else:
            df_temp = df

        # VN-Index correlation
        try:
            vn_close = vn_index_df['close'].reindex(df_temp.index, method='ffill')
            features['vnindex_change'] = pd.Series(vn_close).pct_change(1).values
        except:
            features['vnindex_change'] = 0

        # Relative strength vs market
        features['relative_strength'] = (
            features['price_change_1d'] - features['vnindex_change']
        )
    else:
        features['vnindex_change'] = 0
        features['relative_strength'] = 0

    # ===== 6. CALENDAR (2 features) =====
    if 'date' in df.columns:
        date_series = pd.to_datetime(df['date'])
    else:
        date_series = pd.to_datetime(df.index)

    features['month'] = date_series.dt.month

    # Tet effect (Tết Nguyên Đán - Jan/Feb)
    features['tet_season'] = (
        (features['month'] == 1) | (features['month'] == 2)
    ).astype(int)

    # ===== CLEANUP =====

    # Drop infinite values
    features = features.replace([np.inf, -np.inf], np.nan)

    # Forward fill
    features = features.ffill()

    # Backward fill
    features = features.bfill()

    # Any remaining NaN → 0
    features = features.fillna(0)

    return features


def normalize_features_simple(df, method='robust'):
    """
    Normalize features
    """
    from sklearn.preprocessing import RobustScaler, StandardScaler, MinMaxScaler

    # Columns to NOT normalize
    exclude_cols = ['date', 'month', 'tet_season', 'symbol', 'time', 'ticker']

    # Get feature columns (only numeric)
    feature_cols = [col for col in df.columns
                   if col not in exclude_cols
                   and pd.api.types.is_numeric_dtype(df[col])]

    # Choose scaler
    if method == 'robust':
        scaler = RobustScaler()
    elif method == 'standard':
        scaler = StandardScaler()
    else:
        scaler = MinMaxScaler()

    # Normalize
    df_normalized = df.copy()
    df_normalized[feature_cols] = scaler.fit_transform(df[feature_cols])

    scaler_dict = {
        'method': method,
        'scaler': scaler,
        'feature_cols': feature_cols
    }

    return df_normalized, scaler_dict


if __name__ == "__main__":
    # Test
    print("Testing SIMPLE enhanced features...")

    # Create sample data
    dates = pd.date_range('2023-01-01', periods=300, freq='D')
    sample_data = pd.DataFrame({
        'date': dates,
        'close': np.random.randn(300).cumsum() + 100,
        'open': np.random.randn(300).cumsum() + 100,
        'high': np.random.randn(300).cumsum() + 102,
        'low': np.random.randn(300).cumsum() + 98,
        'volume': np.random.randint(1000000, 10000000, 300)
    })

    # Calculate features
    features = calculate_vn_market_features_simple(sample_data)

    print(f"Original columns: {len(sample_data.columns)}")
    print(f"Enhanced features: {len(features.columns)}")
    print(f"\nFeature names:")
    for col in features.columns:
        print(f"  - {col}")

    # Normalize
    normalized, scaler = normalize_features_simple(features)
    print(f"\nNormalized features shape: {normalized.shape}")
    print(f"Feature count for training: {len(scaler['feature_cols'])}")
    print("SUCCESS: Simple enhanced features working!")
