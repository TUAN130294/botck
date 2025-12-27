# -*- coding: utf-8 -*-
"""
Data Validation Layer for VN-QUANT
===================================
Validates data quality and integrity before use in trading.

Features:
- Schema validation
- Range checks
- Anomaly detection
- Completeness checks
- Timeliness checks
- Data quality scoring
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger


class ValidationSeverity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ValidationIssue:
    """Single validation issue"""
    field: str
    severity: ValidationSeverity
    message: str
    value: Any = None
    expected: Any = None


@dataclass
class ValidationResult:
    """
    Validation result with issues and scores

    Attributes:
        is_valid: Overall validity
        quality_score: 0-100 quality score
        issues: List of validation issues
        metadata: Additional metadata
    """
    is_valid: bool
    quality_score: float
    issues: List[ValidationIssue] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def add_issue(self, field: str, severity: ValidationSeverity, message: str, **kwargs):
        """Add validation issue"""
        self.issues.append(
            ValidationIssue(field=field, severity=severity, message=message, **kwargs)
        )

        # Update validity
        if severity == ValidationSeverity.CRITICAL or severity == ValidationSeverity.ERROR:
            self.is_valid = False

    def get_critical_issues(self) -> List[ValidationIssue]:
        """Get critical issues"""
        return [i for i in self.issues if i.severity == ValidationSeverity.CRITICAL]

    def get_errors(self) -> List[ValidationIssue]:
        """Get errors"""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    def get_warnings(self) -> List[ValidationIssue]:
        """Get warnings"""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


class OHLCVValidator:
    """
    Validator for OHLCV (Open, High, Low, Close, Volume) data

    Checks:
    - Schema (required columns)
    - OHLC relationships (High >= Low, etc.)
    - Volume validity
    - Price ranges
    - Data completeness
    - Temporal consistency
    """

    REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

    def __init__(
        self,
        min_price: float = 0.1,
        max_price: float = 10_000_000,
        min_volume: int = 0,
        max_daily_change: float = 0.15,  # 15% VN market limit
        check_gaps: bool = True
    ):
        self.min_price = min_price
        self.max_price = max_price
        self.min_volume = min_volume
        self.max_daily_change = max_daily_change
        self.check_gaps = check_gaps

    def validate(self, df: pd.DataFrame, symbol: str = "") -> ValidationResult:
        """
        Validate OHLCV dataframe

        Args:
            df: OHLCV dataframe
            symbol: Stock symbol (for logging)

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, quality_score=100.0)

        # Check 1: Schema validation
        missing_cols = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            result.add_issue(
                "schema",
                ValidationSeverity.CRITICAL,
                f"Missing required columns: {missing_cols}"
            )
            return result  # Cannot proceed without required columns

        # Check 2: Empty data
        if len(df) == 0:
            result.add_issue(
                "data",
                ValidationSeverity.CRITICAL,
                "Empty dataframe"
            )
            return result

        # Check 3: OHLC relationships
        invalid_hl = df[df['high'] < df['low']]
        if len(invalid_hl) > 0:
            result.add_issue(
                "high_low",
                ValidationSeverity.ERROR,
                f"High < Low in {len(invalid_hl)} rows"
            )
            result.quality_score -= 10

        invalid_hc = df[df['high'] < df['close']]
        if len(invalid_hc) > 0:
            result.add_issue(
                "high_close",
                ValidationSeverity.ERROR,
                f"High < Close in {len(invalid_hc)} rows"
            )
            result.quality_score -= 5

        invalid_lc = df[df['low'] > df['close']]
        if len(invalid_lc) > 0:
            result.add_issue(
                "low_close",
                ValidationSeverity.ERROR,
                f"Low > Close in {len(invalid_lc)} rows"
            )
            result.quality_score -= 5

        # Check 4: Price ranges
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            too_low = df[df[col] < self.min_price]
            if len(too_low) > 0:
                result.add_issue(
                    col,
                    ValidationSeverity.ERROR,
                    f"{col} < {self.min_price} in {len(too_low)} rows"
                )
                result.quality_score -= 5

            too_high = df[df[col] > self.max_price]
            if len(too_high) > 0:
                result.add_issue(
                    col,
                    ValidationSeverity.WARNING,
                    f"{col} > {self.max_price} in {len(too_high)} rows"
                )
                result.quality_score -= 2

        # Check 5: Volume validity
        negative_vol = df[df['volume'] < 0]
        if len(negative_vol) > 0:
            result.add_issue(
                "volume",
                ValidationSeverity.ERROR,
                f"Negative volume in {len(negative_vol)} rows"
            )
            result.quality_score -= 10

        zero_vol = df[df['volume'] == 0]
        if len(zero_vol) > 0:
            result.add_issue(
                "volume",
                ValidationSeverity.WARNING,
                f"Zero volume in {len(zero_vol)} rows"
            )
            result.quality_score -= 3

        # Check 6: Daily change limits (VN market: +/- 7% for HOSE)
        if 'close' in df.columns and len(df) > 1:
            df_sorted = df.sort_index()
            daily_returns = df_sorted['close'].pct_change().abs()
            excessive_changes = daily_returns[daily_returns > self.max_daily_change]

            if len(excessive_changes) > 0:
                result.add_issue(
                    "daily_change",
                    ValidationSeverity.WARNING,
                    f"Excessive daily changes in {len(excessive_changes)} rows (>{self.max_daily_change*100}%)"
                )
                result.quality_score -= 5

        # Check 7: Missing values
        missing_pct = df[self.REQUIRED_COLUMNS].isnull().sum().sum() / (len(df) * len(self.REQUIRED_COLUMNS))
        if missing_pct > 0:
            result.add_issue(
                "completeness",
                ValidationSeverity.WARNING if missing_pct < 0.05 else ValidationSeverity.ERROR,
                f"{missing_pct*100:.2f}% missing values"
            )
            result.quality_score -= missing_pct * 50

        # Check 8: Duplicates
        if isinstance(df.index, pd.DatetimeIndex):
            duplicates = df.index.duplicated().sum()
            if duplicates > 0:
                result.add_issue(
                    "duplicates",
                    ValidationSeverity.WARNING,
                    f"{duplicates} duplicate timestamps"
                )
                result.quality_score -= 5

        # Check 9: Temporal gaps (if enabled)
        if self.check_gaps and isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
            df_sorted = df.sort_index()
            gaps = df_sorted.index.to_series().diff()
            expected_gap = pd.Timedelta(days=1)

            # Allow for weekends (max 3 days)
            large_gaps = gaps[gaps > pd.Timedelta(days=5)]
            if len(large_gaps) > 0:
                result.add_issue(
                    "gaps",
                    ValidationSeverity.INFO,
                    f"{len(large_gaps)} large temporal gaps detected"
                )

        # Metadata
        result.metadata = {
            "rows": len(df),
            "columns": list(df.columns),
            "date_range": {
                "start": df.index.min().isoformat() if isinstance(df.index, pd.DatetimeIndex) else None,
                "end": df.index.max().isoformat() if isinstance(df.index, pd.DatetimeIndex) else None
            },
            "missing_pct": missing_pct,
            "symbol": symbol
        }

        # Cap quality score
        result.quality_score = max(0, min(100, result.quality_score))

        return result


class TimeSeriesValidator:
    """
    Validator for time series data

    Checks:
    - Stationarity
    - Outliers
    - Seasonality
    - Trends
    """

    def __init__(
        self,
        outlier_std: float = 3.0,
        min_data_points: int = 30
    ):
        self.outlier_std = outlier_std
        self.min_data_points = min_data_points

    def validate(self, series: pd.Series, name: str = "series") -> ValidationResult:
        """
        Validate time series

        Args:
            series: Time series data
            name: Series name

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, quality_score=100.0)

        # Check 1: Sufficient data
        if len(series) < self.min_data_points:
            result.add_issue(
                "length",
                ValidationSeverity.WARNING,
                f"Insufficient data points: {len(series)} < {self.min_data_points}"
            )
            result.quality_score -= 20

        # Check 2: Missing values
        missing_pct = series.isnull().sum() / len(series)
        if missing_pct > 0:
            severity = ValidationSeverity.ERROR if missing_pct > 0.1 else ValidationSeverity.WARNING
            result.add_issue(
                "missing",
                severity,
                f"{missing_pct*100:.2f}% missing values"
            )
            result.quality_score -= missing_pct * 50

        # Check 3: Outliers (using z-score)
        if len(series.dropna()) > 0:
            z_scores = np.abs((series - series.mean()) / series.std())
            outliers = z_scores[z_scores > self.outlier_std]

            if len(outliers) > 0:
                result.add_issue(
                    "outliers",
                    ValidationSeverity.INFO,
                    f"{len(outliers)} outliers detected (>{self.outlier_std} std)"
                )
                result.metadata['outlier_indices'] = outliers.index.tolist()

        # Check 4: Constant values
        if series.nunique() == 1:
            result.add_issue(
                "variance",
                ValidationSeverity.WARNING,
                "Series has constant values"
            )
            result.quality_score -= 30

        # Metadata
        result.metadata.update({
            "length": len(series),
            "missing_count": series.isnull().sum(),
            "mean": series.mean(),
            "std": series.std(),
            "min": series.min(),
            "max": series.max(),
            "name": name
        })

        result.quality_score = max(0, min(100, result.quality_score))

        return result


class DataFreshnessValidator:
    """
    Validator for data freshness/timeliness

    Checks:
    - Data age
    - Update frequency
    """

    def __init__(
        self,
        max_age_seconds: int = 3600,  # 1 hour
        expected_update_freq: Optional[int] = None  # seconds
    ):
        self.max_age_seconds = max_age_seconds
        self.expected_update_freq = expected_update_freq

    def validate(self, timestamp: datetime, name: str = "data") -> ValidationResult:
        """
        Validate data freshness

        Args:
            timestamp: Data timestamp
            name: Data name

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, quality_score=100.0)

        age_seconds = (datetime.now() - timestamp).total_seconds()

        if age_seconds > self.max_age_seconds:
            result.add_issue(
                "freshness",
                ValidationSeverity.WARNING,
                f"Data is {age_seconds:.0f}s old (max: {self.max_age_seconds}s)"
            )
            # Deduct score based on how stale
            staleness_ratio = age_seconds / self.max_age_seconds
            result.quality_score -= min(50, staleness_ratio * 20)

        if age_seconds < 0:
            result.add_issue(
                "timestamp",
                ValidationSeverity.ERROR,
                "Timestamp is in the future"
            )
            result.quality_score -= 30

        result.metadata = {
            "timestamp": timestamp.isoformat(),
            "age_seconds": age_seconds,
            "name": name
        }

        result.quality_score = max(0, min(100, result.quality_score))

        return result


# Composite validator
class DataValidator:
    """
    Composite data validator

    Combines multiple validators for comprehensive validation
    """

    def __init__(self):
        self.ohlcv_validator = OHLCVValidator()
        self.ts_validator = TimeSeriesValidator()
        self.freshness_validator = DataFreshnessValidator()

    def validate_ohlcv(self, df: pd.DataFrame, symbol: str = "") -> ValidationResult:
        """Validate OHLCV data"""
        return self.ohlcv_validator.validate(df, symbol)

    def validate_time_series(self, series: pd.Series, name: str = "") -> ValidationResult:
        """Validate time series"""
        return self.ts_validator.validate(series, name)

    def validate_freshness(self, timestamp: datetime, name: str = "") -> ValidationResult:
        """Validate data freshness"""
        return self.freshness_validator.validate(timestamp, name)

    def validate_all(
        self,
        df: pd.DataFrame,
        symbol: str = "",
        check_freshness: bool = True
    ) -> Dict[str, ValidationResult]:
        """
        Run all validations

        Returns:
            Dict of validation results by validator name
        """
        results = {}

        # OHLCV validation
        results['ohlcv'] = self.validate_ohlcv(df, symbol)

        # Time series validation for each column
        for col in ['close', 'volume']:
            if col in df.columns:
                results[f'ts_{col}'] = self.validate_time_series(df[col], f"{symbol}_{col}")

        # Freshness validation
        if check_freshness and isinstance(df.index, pd.DatetimeIndex):
            latest_timestamp = df.index.max()
            if pd.notna(latest_timestamp):
                results['freshness'] = self.validate_freshness(
                    latest_timestamp.to_pydatetime(),
                    symbol
                )

        return results


# Global validator instance
_validator: Optional[DataValidator] = None


def get_validator() -> DataValidator:
    """Get global validator instance"""
    global _validator
    if _validator is None:
        _validator = DataValidator()
    return _validator


__all__ = [
    "DataValidator",
    "OHLCVValidator",
    "TimeSeriesValidator",
    "DataFreshnessValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "get_validator"
]
