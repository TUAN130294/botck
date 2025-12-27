# -*- coding: utf-8 -*-
"""
Test Suite for Vietnam T+2.5 Settlement Data Preparation
==========================================================
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from quantum_stock.ml.vietnam_data_prep import VietnamSettlementDataPrep


def test_settlement_alignment():
    """CRITICAL: Test that labels skip T+1, T+2 (non-tradeable days)"""
    print("\n[TEST] Settlement Alignment...")

    prep = VietnamSettlementDataPrep(seq_len=60, forecast_len=5)

    # Create 300 days of simple sequential data
    prices = np.arange(300, dtype=float)  # 0, 1, 2, ..., 299

    X, y, metadata = prep.prepare_sequences_vietnam(
        prices=prices,
        normalize_per_sequence=False  # Keep raw for testing
    )

    # First sample verification
    # Input: [0, 1, ..., 59]
    # Should skip 60, 61, 62 (T+0, T+1, T+2)
    # Output: [63, 64, 65, 66, 67] (T+3 to T+7)

    assert X[0, -1] == 59, f"Last input should be day 59, got {X[0, -1]}"
    assert y[0, 0] == 63, f"First target should be day 63 (T+3), got {y[0, 0]}"
    assert y[0, -1] == 67, f"Last target should be day 67 (T+7), got {y[0, -1]}"

    # Second sample
    assert X[1, -1] == 60, f"Second sample last input should be day 60"
    assert y[1, 0] == 64, f"Second sample first target should be day 64 (T+3)"

    print("  [OK] Labels correctly skip T+1, T+2")
    print("  [OK] Labels start at T+3 (first tradeable day)")
    print("  [OK] Settlement alignment test PASSED")


def test_normalization():
    """Test normalization and denormalization"""
    print("\n[TEST] Normalization...")

    prep = VietnamSettlementDataPrep(seq_len=60, forecast_len=5)

    # Flat 100 for 60 days, then jump to 110 for rest
    prices = np.array([100.0] * 60 + [110.0] * 20)

    X, y, metadata = prep.prepare_sequences_vietnam(
        prices=prices,
        normalize_per_sequence=True
    )

    # First sequence: all 100 (flat)
    # Should normalize to all 0s (min-max)
    assert np.allclose(X[0], 0.0, atol=0.01), "Flat sequence should normalize to 0"

    # Denormalize first prediction
    y_denorm = prep.denormalize_predictions(y[0], metadata[0])

    # Should get back ~110 (T+3 to T+7 are all 110 in this example)
    # But first sample might still be in 100 range, check last sample
    if len(X) > 1:
        y_denorm_last = prep.denormalize_predictions(y[-1], metadata[-1])
        assert np.allclose(y_denorm_last, 110.0, atol=1.0), \
            f"Expected ~110, got {y_denorm_last}"

    print("  [OK] Normalization works correctly")
    print("  [OK] Denormalization recovers original scale")
    print("  [OK] Normalization test PASSED")


def test_insufficient_data():
    """Test error handling for insufficient data"""
    print("\n[TEST] Insufficient Data Error Handling...")

    prep = VietnamSettlementDataPrep(seq_len=60, forecast_len=5)

    # Only 50 days (need 60 + 3 + 5 = 68 minimum)
    prices = np.arange(50, dtype=float)

    with pytest.raises(ValueError) as exc_info:
        X, y, _ = prep.prepare_sequences_vietnam(prices=prices)

    assert "Need at least" in str(exc_info.value)

    print("  [OK] Correctly raises ValueError for insufficient data")
    print("  [OK] Error message is clear")
    print("  [OK] Insufficient data test PASSED")


def test_multiple_features():
    """Test with price + volume + sentiment"""
    print("\n[TEST] Multiple Features...")

    prep = VietnamSettlementDataPrep(seq_len=60, forecast_len=5)

    n_days = 200
    prices = np.random.rand(n_days) * 1000 + 50000
    volumes = np.random.randint(100000, 1000000, n_days).astype(float)
    sentiment = np.random.randn(n_days) * 0.3

    X, y, metadata = prep.prepare_sequences_vietnam(
        prices=prices,
        volumes=volumes,
        news_sentiment=sentiment,
        normalize_per_sequence=True
    )

    # Should have 3 features: price, volume, sentiment
    assert X.shape[2] == 3, f"Expected 3 features, got {X.shape[2]}"
    assert X.shape[1] == 60, f"Expected 60 timesteps, got {X.shape[1]}"
    assert y.shape[1] == 5, f"Expected 5 forecast steps, got {y.shape[1]}"

    print(f"  [OK] X shape: {X.shape} (samples, timesteps, features)")
    print(f"  [OK] y shape: {y.shape} (samples, forecast_horizon)")
    print("  [OK] Multiple features test PASSED")


def test_dataframe_integration():
    """Test create_training_data_with_features method"""
    print("\n[TEST] DataFrame Integration...")

    prep = VietnamSettlementDataPrep(seq_len=60, forecast_len=5)

    # Create sample DataFrame
    n_days = 200
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=n_days),
        'close': np.random.rand(n_days) * 1000 + 50000,
        'volume': np.random.randint(100000, 1000000, n_days),
        'sentiment': np.random.randn(n_days) * 0.3
    })

    X, y, metadata_df = prep.create_training_data_with_features(
        df,
        price_col='close',
        volume_col='volume',
        sentiment_col='sentiment'
    )

    assert isinstance(metadata_df, pd.DataFrame), "Metadata should be DataFrame"
    assert len(metadata_df) == len(X), "Metadata length should match X"
    assert 'min' in metadata_df.columns, "Metadata should have 'min' column"
    assert 'max' in metadata_df.columns, "Metadata should have 'max' column"

    print(f"  [OK] Created {len(X)} training samples from DataFrame")
    print(f"  [OK] Metadata DataFrame has {len(metadata_df)} rows")
    print("  [OK] DataFrame integration test PASSED")


def test_edge_cases():
    """Test edge cases"""
    print("\n[TEST] Edge Cases...")

    prep = VietnamSettlementDataPrep(seq_len=60, forecast_len=5)

    # Exactly minimum data
    min_needed = 60 + 3 + 5  # 68
    prices = np.arange(min_needed, dtype=float)

    X, y, metadata = prep.prepare_sequences_vietnam(
        prices=prices,
        normalize_per_sequence=False
    )

    # Should have exactly 1 sample
    assert len(X) == 1, f"Expected 1 sample with minimum data, got {len(X)}"

    # Test with constant prices (edge case for normalization)
    prices_const = np.ones(100) * 50000

    X_const, y_const, _ = prep.prepare_sequences_vietnam(
        prices=prices_const,
        normalize_per_sequence=True
    )

    # Constant prices should normalize to 0
    assert np.allclose(X_const, 0.0), "Constant prices should normalize to 0"

    print("  [OK] Handles minimum data correctly (1 sample)")
    print("  [OK] Handles constant prices (edge case)")
    print("  [OK] Edge cases test PASSED")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("VIETNAM T+2.5 SETTLEMENT TEST SUITE")
    print("="*60)

    try:
        test_settlement_alignment()
        test_normalization()
        test_insufficient_data()
        test_multiple_features()
        test_dataframe_integration()
        test_edge_cases()

        print("\n" + "="*60)
        print("ALL TESTS PASSED")
        print("="*60)
        print("\nSummary:")
        print("  - T+2.5 settlement alignment: OK")
        print("  - Normalization/denormalization: OK")
        print("  - Error handling: OK")
        print("  - Multiple features: OK")
        print("  - DataFrame integration: OK")
        print("  - Edge cases: OK")
        print("\n[SUCCESS] Vietnam T+2.5 data preparation is production-ready!")

        return True

    except Exception as e:
        print("\n" + "="*60)
        print("TEST FAILED")
        print("="*60)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
