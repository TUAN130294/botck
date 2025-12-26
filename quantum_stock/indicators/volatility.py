"""
Volatility Indicators (15+)
For measuring market volatility and potential breakouts
"""

import pandas as pd
import numpy as np
from typing import Dict


class VolatilityIndicators:
    """Collection of volatility indicators"""

    @staticmethod
    def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        """Bollinger Bands"""
        sma = series.rolling(period).mean()
        std = series.rolling(period).std()

        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        # Bandwidth and %B
        bandwidth = (upper - lower) / sma * 100
        percent_b = (series - lower) / (upper - lower)

        return {
            'upper': upper,
            'middle': sma,
            'lower': lower,
            'bandwidth': bandwidth,
            'percent_b': percent_b.fillna(0.5)
        }

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    @staticmethod
    def natr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Normalized Average True Range (percentage)"""
        atr = VolatilityIndicators.atr(high, low, close, period)
        return (atr / close) * 100

    @staticmethod
    def keltner_channels(high: pd.Series, low: pd.Series, close: pd.Series,
                        ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> Dict[str, pd.Series]:
        """Keltner Channels"""
        ema = close.ewm(span=ema_period, adjust=False).mean()
        atr = VolatilityIndicators.atr(high, low, close, atr_period)

        upper = ema + (multiplier * atr)
        lower = ema - (multiplier * atr)

        return {
            'upper': upper,
            'middle': ema,
            'lower': lower
        }

    @staticmethod
    def donchian_channels(high: pd.Series, low: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """Donchian Channels"""
        upper = high.rolling(period).max()
        lower = low.rolling(period).min()
        middle = (upper + lower) / 2

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }

    @staticmethod
    def standard_deviation(series: pd.Series, period: int = 20) -> pd.Series:
        """Rolling Standard Deviation"""
        return series.rolling(period).std()

    @staticmethod
    def historical_volatility(series: pd.Series, period: int = 20, annualize: bool = True) -> pd.Series:
        """Historical Volatility (HV)"""
        log_returns = np.log(series / series.shift(1))
        hv = log_returns.rolling(period).std()

        if annualize:
            hv = hv * np.sqrt(252) * 100

        return hv

    @staticmethod
    def chaikin_volatility(high: pd.Series, low: pd.Series,
                          ema_period: int = 10, roc_period: int = 10) -> pd.Series:
        """Chaikin Volatility"""
        hl_range = high - low
        hl_ema = hl_range.ewm(span=ema_period, adjust=False).mean()
        cv = ((hl_ema - hl_ema.shift(roc_period)) / hl_ema.shift(roc_period)) * 100
        return cv.fillna(0)

    @staticmethod
    def ulcer_index(series: pd.Series, period: int = 14) -> pd.Series:
        """Ulcer Index - Downside volatility"""
        rolling_max = series.rolling(period).max()
        drawdown = ((series - rolling_max) / rolling_max) * 100
        ui = np.sqrt((drawdown ** 2).rolling(period).mean())
        return ui

    @staticmethod
    def volatility_ratio(high: pd.Series, low: pd.Series, close: pd.Series,
                        period: int = 14) -> pd.Series:
        """Volatility Ratio (Schwager)"""
        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()
        vr = tr / atr
        return vr.fillna(1)

    @staticmethod
    def chandelier_exit(high: pd.Series, low: pd.Series, close: pd.Series,
                       period: int = 22, multiplier: float = 3.0) -> Dict[str, pd.Series]:
        """Chandelier Exit"""
        atr = VolatilityIndicators.atr(high, low, close, period)
        highest_high = high.rolling(period).max()
        lowest_low = low.rolling(period).min()

        long_exit = highest_high - (atr * multiplier)
        short_exit = lowest_low + (atr * multiplier)

        return {
            'long_exit': long_exit,
            'short_exit': short_exit
        }

    @staticmethod
    def mass_index(high: pd.Series, low: pd.Series,
                   ema_period: int = 9, sum_period: int = 25) -> pd.Series:
        """Mass Index - Reversal signals"""
        range_hl = high - low
        ema1 = range_hl.ewm(span=ema_period, adjust=False).mean()
        ema2 = ema1.ewm(span=ema_period, adjust=False).mean()
        ratio = ema1 / ema2.replace(0, np.nan)
        return ratio.rolling(sum_period).sum()

    @staticmethod
    def relative_volatility_index(series: pd.Series, period: int = 14,
                                  smoothing: int = 14) -> pd.Series:
        """Relative Volatility Index"""
        std = series.rolling(period).std()
        change = std.diff()

        gains = change.where(change > 0, 0)
        losses = -change.where(change < 0, 0)

        avg_gain = gains.ewm(span=smoothing, adjust=False).mean()
        avg_loss = losses.ewm(span=smoothing, adjust=False).mean()

        rvi = 100 * avg_gain / (avg_gain + avg_loss).replace(0, np.nan)
        return rvi.fillna(50)

    @staticmethod
    def choppiness_index(high: pd.Series, low: pd.Series, close: pd.Series,
                        period: int = 14) -> pd.Series:
        """Choppiness Index - Market trending vs ranging"""
        atr = VolatilityIndicators.atr(high, low, close, 1)  # Daily TR
        atr_sum = atr.rolling(period).sum()

        highest_high = high.rolling(period).max()
        lowest_low = low.rolling(period).min()
        hl_range = highest_high - lowest_low

        ci = 100 * np.log10(atr_sum / hl_range.replace(0, np.nan)) / np.log10(period)
        return ci.fillna(50)

    @staticmethod
    def price_channel(high: pd.Series, low: pd.Series, period: int = 20,
                     offset: float = 0) -> Dict[str, pd.Series]:
        """Price Channel (Highest High, Lowest Low)"""
        upper = high.rolling(period).max() * (1 + offset/100)
        lower = low.rolling(period).min() * (1 - offset/100)
        middle = (upper + lower) / 2

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }

    @staticmethod
    def atr_bands(close: pd.Series, high: pd.Series, low: pd.Series,
                  period: int = 14, multiplier: float = 2.0) -> Dict[str, pd.Series]:
        """ATR Bands"""
        atr = VolatilityIndicators.atr(high, low, close, period)
        ema = close.ewm(span=period, adjust=False).mean()

        upper = ema + (atr * multiplier)
        lower = ema - (atr * multiplier)

        return {
            'upper': upper,
            'middle': ema,
            'lower': lower,
            'atr': atr
        }

    @staticmethod
    def bbw_squeeze(close: pd.Series, high: pd.Series, low: pd.Series,
                   bb_period: int = 20, kc_period: int = 20,
                   bb_mult: float = 2.0, kc_mult: float = 1.5) -> Dict[str, pd.Series]:
        """BB Width Squeeze (BB inside Keltner = Squeeze)"""
        bb = VolatilityIndicators.bollinger_bands(close, bb_period, bb_mult)
        kc = VolatilityIndicators.keltner_channels(high, low, close, kc_period, kc_period, kc_mult)

        squeeze_on = (bb['lower'] > kc['lower']) & (bb['upper'] < kc['upper'])
        squeeze_off = (bb['lower'] < kc['lower']) | (bb['upper'] > kc['upper'])

        return {
            'squeeze_on': squeeze_on.astype(int),
            'squeeze_off': squeeze_off.astype(int),
            'bb_width': bb['bandwidth'],
            'momentum': close - close.rolling(bb_period).mean()
        }

    @staticmethod
    def projected_volatility(series: pd.Series, period: int = 20,
                            forecast: int = 5) -> pd.Series:
        """Projected Volatility using EWMA"""
        log_returns = np.log(series / series.shift(1))

        # EWMA variance with decay
        lambda_ = 0.94  # RiskMetrics decay factor

        var = pd.Series(index=series.index, dtype=float)
        var.iloc[period-1] = log_returns.iloc[:period].var()

        for i in range(period, len(series)):
            var.iloc[i] = lambda_ * var.iloc[i-1] + (1 - lambda_) * log_returns.iloc[i] ** 2

        # Project forward
        projected = var * (lambda_ ** forecast)

        return np.sqrt(projected * 252) * 100  # Annualized
