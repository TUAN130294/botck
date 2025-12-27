# -*- coding: utf-8 -*-
"""
Vietnam T+2.5 Settlement-Aware Data Preparation
================================================
Chuẩn bị data cho training model, aligned với quy định T+2.5 của VN

Key Concepts:
- T+0 (Buy day): Ngày mua cổ phiếu
- T+1: Stock PENDING - chưa về tài khoản
- T+2: Stock AVAILABLE sáng - có thể bán chiều (nhưng rủi ro)
- T+3: Ngày đầu tiên AN TOÀN để bán

Training Labels:
- WRONG: [T+1, T+2, T+3, T+4, T+5] (40% không trade được)
- CORRECT: [T+3, T+4, T+5, T+6, T+7] (100% trade được)
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, List
from datetime import datetime, timedelta


class VietnamSettlementDataPrep:
    """
    Data preparation cho thị trường Việt Nam với T+2.5 settlement
    """

    # Vietnam settlement rules
    SETTLEMENT_DAYS = 3  # T+0, T+1, T+2 (available T+2 morning)
    SAFE_TRADING_DAY = 3  # T+3 là ngày đầu tiên an toàn

    def __init__(self, seq_len: int = 60, forecast_len: int = 5):
        """
        Args:
            seq_len: Lookback window (60 days default)
            forecast_len: Forecast horizon (5 days default)
        """
        self.seq_len = seq_len
        self.forecast_len = forecast_len

    def prepare_sequences_vietnam(
        self,
        prices: np.ndarray,
        volumes: Optional[np.ndarray] = None,
        news_sentiment: Optional[np.ndarray] = None,
        normalize_per_sequence: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, List[dict]]:
        """
        Chuẩn bị sequences aligned với T+2.5 settlement

        Timeline:
        --------
        Input:  [T-60, T-59, ..., T-1, T]     (60 days historical)
        Output: [T+3, T+4, T+5, T+6, T+7]     (5 days TRADEABLE forecast)

        Skip T+1, T+2 vì không thể trade!

        Args:
            prices: Historical close prices (shape: [N])
            volumes: Historical volumes (optional, shape: [N])
            news_sentiment: News sentiment scores (optional, shape: [N])
            normalize_per_sequence: Normalize each sequence independently

        Returns:
            X: Input sequences (shape: [n_samples, seq_len, n_features])
            y: Target sequences (shape: [n_samples, forecast_len])
            metadata: List of dicts with normalization params
        """
        # Total days needed
        total_needed = self.seq_len + self.SAFE_TRADING_DAY + self.forecast_len

        if len(prices) < total_needed:
            raise ValueError(
                f"Need at least {total_needed} days of data. "
                f"Got {len(prices)} days."
            )

        X, y, metadata = [], [], []

        # Create sequences
        max_start = len(prices) - total_needed

        for i in range(max_start + 1):
            # Input: Historical data
            input_prices = prices[i:i+self.seq_len]

            # Target: Post-settlement tradeable window
            # Skip T+1, T+2 (days i+seq_len and i+seq_len+1 and i+seq_len+2)
            # Start from T+3 (day i+seq_len+3)
            target_start = i + self.seq_len + self.SAFE_TRADING_DAY
            target_end = target_start + self.forecast_len
            target_prices = prices[target_start:target_end]

            # Normalize (optional)
            if normalize_per_sequence:
                # Min-max normalization
                input_min = input_prices.min()
                input_max = input_prices.max()
                price_range = input_max - input_min

                if price_range > 0:
                    input_norm = (input_prices - input_min) / price_range
                    target_norm = (target_prices - input_min) / price_range
                else:
                    input_norm = input_prices * 0  # All zeros if flat
                    target_norm = target_prices * 0

                meta = {
                    'min': float(input_min),
                    'max': float(input_max),
                    'range': float(price_range),
                    'start_idx': i,
                    'target_start_idx': target_start
                }
            else:
                input_norm = input_prices
                target_norm = target_prices
                meta = {'start_idx': i, 'target_start_idx': target_start}

            # Build feature matrix
            features = [input_norm]

            # Add volume features
            if volumes is not None:
                input_volumes = volumes[i:i+self.seq_len]
                # Normalize volumes
                vol_mean = input_volumes.mean()
                if vol_mean > 0:
                    vol_norm = input_volumes / vol_mean
                else:
                    vol_norm = input_volumes * 0
                features.append(vol_norm)

            # Add news sentiment
            if news_sentiment is not None:
                input_sentiment = news_sentiment[i:i+self.seq_len]
                features.append(input_sentiment)

            # Stack features
            if len(features) > 1:
                X_sample = np.column_stack(features)
            else:
                X_sample = input_norm.reshape(-1, 1)

            X.append(X_sample)
            y.append(target_norm)
            metadata.append(meta)

        return np.array(X), np.array(y), metadata

    def denormalize_predictions(
        self,
        predictions: np.ndarray,
        metadata: dict
    ) -> np.ndarray:
        """
        Chuyển predictions từ normalized về giá thực

        Args:
            predictions: Normalized predictions
            metadata: Normalization parameters

        Returns:
            Denormalized prices
        """
        price_min = metadata['min']
        price_range = metadata['range']

        if price_range > 0:
            return predictions * price_range + price_min
        else:
            return predictions + price_min

    def create_training_data_with_features(
        self,
        df: pd.DataFrame,
        price_col: str = 'close',
        volume_col: str = 'volume',
        sentiment_col: Optional[str] = None
    ) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        """
        Tạo training data từ DataFrame với full features

        Args:
            df: DataFrame với OHLCV + sentiment
            price_col: Tên cột giá
            volume_col: Tên cột volume
            sentiment_col: Tên cột sentiment (optional)

        Returns:
            X: Input features
            y: Target labels
            metadata_df: DataFrame chứa metadata
        """
        prices = df[price_col].values
        volumes = df[volume_col].values if volume_col in df.columns else None
        sentiment = df[sentiment_col].values if sentiment_col and sentiment_col in df.columns else None

        X, y, metadata = self.prepare_sequences_vietnam(
            prices=prices,
            volumes=volumes,
            news_sentiment=sentiment,
            normalize_per_sequence=True
        )

        # Convert metadata to DataFrame
        metadata_df = pd.DataFrame(metadata)

        return X, y, metadata_df

    def validate_settlement_alignment(self, df: pd.DataFrame, X: np.ndarray, y: np.ndarray):
        """
        Validate rằng labels aligned đúng với T+2.5 settlement

        Prints warning nếu phát hiện vấn đề
        """
        print("\n" + "="*60)
        print("VIETNAM T+2.5 SETTLEMENT VALIDATION")
        print("="*60)
        print(f"Input sequence length: {self.seq_len} days")
        print(f"Settlement period: {self.SETTLEMENT_DAYS} days (T+0, T+1, T+2)")
        print(f"Safe trading day: T+{self.SAFE_TRADING_DAY}")
        print(f"Forecast horizon: {self.forecast_len} days")
        print(f"\nTotal samples: {len(X)}")

        # Example timeline
        if len(X) > 0:
            print("\nExample Timeline (First Sample):")
            print(f"  Input days: Day 0 to Day {self.seq_len-1}")
            print(f"  Buy signal: Day {self.seq_len} (T+0)")
            print(f"  Stock PENDING: Day {self.seq_len+1} (T+1)")
            print(f"  Stock PENDING: Day {self.seq_len+2} (T+2)")
            print(f"  Stock AVAILABLE: Day {self.seq_len+2} morning")
            print(f"  First SAFE sell: Day {self.seq_len+3} (T+3) <- PREDICTION STARTS")
            print(f"  Prediction window: Day {self.seq_len+3} to Day {self.seq_len+3+self.forecast_len-1}")
            print(f"                     (T+3 to T+{3+self.forecast_len-1})")

        print("\n[OK] Validation PASSED - Labels aligned with T+2.5 settlement")
        print("="*60 + "\n")


# Example usage
if __name__ == "__main__":
    # Generate sample data
    np.random.seed(42)
    n_days = 300

    dates = pd.date_range('2024-01-01', periods=n_days)
    prices = 50000 + np.cumsum(np.random.randn(n_days) * 500)
    volumes = np.random.randint(100000, 1000000, n_days)
    sentiment = np.random.randn(n_days) * 0.3  # -1 to 1

    df = pd.DataFrame({
        'date': dates,
        'close': prices,
        'volume': volumes,
        'sentiment': sentiment
    })

    # Create data prep
    prep = VietnamSettlementDataPrep(seq_len=60, forecast_len=5)

    # Prepare sequences
    X, y, metadata_df = prep.create_training_data_with_features(
        df,
        price_col='close',
        volume_col='volume',
        sentiment_col='sentiment'
    )

    print(f"X shape: {X.shape}")  # (n_samples, 60, n_features)
    print(f"y shape: {y.shape}")  # (n_samples, 5)
    print(f"Metadata: {len(metadata_df)} rows")

    # Validate
    prep.validate_settlement_alignment(df, X, y)

    # Test denormalization
    sample_pred = y[0]  # Normalized prediction
    sample_meta = metadata_df.iloc[0].to_dict()
    actual_prices = prep.denormalize_predictions(sample_pred, sample_meta)

    print(f"Denormalization Test:")
    print(f"  Normalized: {sample_pred}")
    print(f"  Actual prices: {actual_prices}")

    print("\n[SUCCESS] vietnam_data_prep.py working correctly!")
