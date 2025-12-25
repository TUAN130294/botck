"""
Trend Indicators (20+)
For identifying market direction and trend strength
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional


class TrendIndicators:
    """Collection of trend-following indicators"""

    @staticmethod
    def sma(series: pd.Series, period: int = 20) -> pd.Series:
        """Simple Moving Average"""
        return series.rolling(window=period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int = 20) -> pd.Series:
        """Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def wma(series: pd.Series, period: int = 20) -> pd.Series:
        """Weighted Moving Average"""
        weights = np.arange(1, period + 1)
        return series.rolling(period).apply(
            lambda x: np.sum(weights * x) / weights.sum(), raw=True
        )

    @staticmethod
    def dema(series: pd.Series, period: int = 20) -> pd.Series:
        """Double Exponential Moving Average"""
        ema1 = series.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        return 2 * ema1 - ema2

    @staticmethod
    def tema(series: pd.Series, period: int = 20) -> pd.Series:
        """Triple Exponential Moving Average"""
        ema1 = series.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        return 3 * ema1 - 3 * ema2 + ema3

    @staticmethod
    def kama(series: pd.Series, period: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
        """Kaufman Adaptive Moving Average"""
        change = abs(series - series.shift(period))
        volatility = abs(series - series.shift(1)).rolling(period).sum()

        er = change / volatility.replace(0, np.nan)
        er = er.fillna(0)

        fast_sc = 2 / (fast + 1)
        slow_sc = 2 / (slow + 1)
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

        kama = pd.Series(index=series.index, dtype=float)
        kama.iloc[period-1] = series.iloc[period-1]

        for i in range(period, len(series)):
            kama.iloc[i] = kama.iloc[i-1] + sc.iloc[i] * (series.iloc[i] - kama.iloc[i-1])

        return kama

    @staticmethod
    def hull_ma(series: pd.Series, period: int = 20) -> pd.Series:
        """Hull Moving Average - Low lag, smooth"""
        half_period = int(period / 2)
        sqrt_period = int(np.sqrt(period))

        wma_half = TrendIndicators.wma(series, half_period)
        wma_full = TrendIndicators.wma(series, period)

        raw = 2 * wma_half - wma_full
        return TrendIndicators.wma(raw, sqrt_period)

    @staticmethod
    def vwma(close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
        """Volume Weighted Moving Average"""
        return (close * volume).rolling(period).sum() / volume.rolling(period).sum()

    @staticmethod
    def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """MACD - Moving Average Convergence Divergence"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, pd.Series]:
        """Average Directional Index - Trend strength"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        atr = tr.ewm(span=period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(span=period, adjust=False).mean()

        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
            'dx': dx
        }

    @staticmethod
    def parabolic_sar(high: pd.Series, low: pd.Series, af_start: float = 0.02,
                      af_step: float = 0.02, af_max: float = 0.2) -> pd.Series:
        """Parabolic SAR - Stop and Reverse"""
        length = len(high)
        sar = pd.Series(index=high.index, dtype=float)
        trend = pd.Series(index=high.index, dtype=int)
        ep = pd.Series(index=high.index, dtype=float)
        af = pd.Series(index=high.index, dtype=float)

        # Initialize
        sar.iloc[0] = low.iloc[0]
        trend.iloc[0] = 1
        ep.iloc[0] = high.iloc[0]
        af.iloc[0] = af_start

        for i in range(1, length):
            if trend.iloc[i-1] == 1:  # Uptrend
                sar.iloc[i] = sar.iloc[i-1] + af.iloc[i-1] * (ep.iloc[i-1] - sar.iloc[i-1])
                sar.iloc[i] = min(sar.iloc[i], low.iloc[i-1], low.iloc[i-2] if i >= 2 else low.iloc[i-1])

                if low.iloc[i] < sar.iloc[i]:
                    trend.iloc[i] = -1
                    sar.iloc[i] = ep.iloc[i-1]
                    ep.iloc[i] = low.iloc[i]
                    af.iloc[i] = af_start
                else:
                    trend.iloc[i] = 1
                    if high.iloc[i] > ep.iloc[i-1]:
                        ep.iloc[i] = high.iloc[i]
                        af.iloc[i] = min(af.iloc[i-1] + af_step, af_max)
                    else:
                        ep.iloc[i] = ep.iloc[i-1]
                        af.iloc[i] = af.iloc[i-1]
            else:  # Downtrend
                sar.iloc[i] = sar.iloc[i-1] - af.iloc[i-1] * (sar.iloc[i-1] - ep.iloc[i-1])
                sar.iloc[i] = max(sar.iloc[i], high.iloc[i-1], high.iloc[i-2] if i >= 2 else high.iloc[i-1])

                if high.iloc[i] > sar.iloc[i]:
                    trend.iloc[i] = 1
                    sar.iloc[i] = ep.iloc[i-1]
                    ep.iloc[i] = high.iloc[i]
                    af.iloc[i] = af_start
                else:
                    trend.iloc[i] = -1
                    if low.iloc[i] < ep.iloc[i-1]:
                        ep.iloc[i] = low.iloc[i]
                        af.iloc[i] = min(af.iloc[i-1] + af_step, af_max)
                    else:
                        ep.iloc[i] = ep.iloc[i-1]
                        af.iloc[i] = af.iloc[i-1]

        return sar

    @staticmethod
    def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
                   period: int = 10, multiplier: float = 3.0) -> Dict[str, pd.Series]:
        """Supertrend Indicator"""
        atr = TrendIndicators.atr(high, low, close, period)

        hl2 = (high + low) / 2
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)

        supertrend = pd.Series(index=close.index, dtype=float)
        direction = pd.Series(index=close.index, dtype=int)

        supertrend.iloc[0] = upper_band.iloc[0]
        direction.iloc[0] = 1

        for i in range(1, len(close)):
            if close.iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1]

            if direction.iloc[i] == 1:
                supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1]) if direction.iloc[i-1] == 1 else lower_band.iloc[i]
            else:
                supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1]) if direction.iloc[i-1] == -1 else upper_band.iloc[i]

        return {
            'supertrend': supertrend,
            'direction': direction,
            'upper_band': upper_band,
            'lower_band': lower_band
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
    def aroon(high: pd.Series, low: pd.Series, period: int = 25) -> Dict[str, pd.Series]:
        """Aroon Indicator - Trend identification"""
        aroon_up = pd.Series(index=high.index, dtype=float)
        aroon_down = pd.Series(index=high.index, dtype=float)

        for i in range(period, len(high)):
            high_window = high.iloc[i-period:i+1]
            low_window = low.iloc[i-period:i+1]

            days_since_high = period - high_window.argmax()
            days_since_low = period - low_window.argmin()

            aroon_up.iloc[i] = ((period - days_since_high) / period) * 100
            aroon_down.iloc[i] = ((period - days_since_low) / period) * 100

        return {
            'aroon_up': aroon_up,
            'aroon_down': aroon_down,
            'aroon_oscillator': aroon_up - aroon_down
        }

    @staticmethod
    def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series,
                 tenkan: int = 9, kijun: int = 26, senkou_b: int = 52) -> Dict[str, pd.Series]:
        """Ichimoku Cloud"""
        # Tenkan-sen (Conversion Line)
        tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2

        # Kijun-sen (Base Line)
        kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2

        # Senkou Span A (Leading Span A)
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)

        # Senkou Span B (Leading Span B)
        senkou_span_b = ((high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2).shift(kijun)

        # Chikou Span (Lagging Span)
        chikou_span = close.shift(-kijun)

        return {
            'tenkan_sen': tenkan_sen,
            'kijun_sen': kijun_sen,
            'senkou_span_a': senkou_span_a,
            'senkou_span_b': senkou_span_b,
            'chikou_span': chikou_span
        }

    @staticmethod
    def linear_regression(series: pd.Series, period: int = 14) -> Dict[str, pd.Series]:
        """Linear Regression Line and related indicators"""
        def calc_lr(window):
            x = np.arange(len(window))
            slope, intercept = np.polyfit(x, window, 1)
            return intercept + slope * (len(window) - 1)

        lr_value = series.rolling(period).apply(calc_lr, raw=True)

        def calc_slope(window):
            x = np.arange(len(window))
            slope, _ = np.polyfit(x, window, 1)
            return slope

        lr_slope = series.rolling(period).apply(calc_slope, raw=True)

        # R-squared
        def calc_r2(window):
            x = np.arange(len(window))
            correlation = np.corrcoef(x, window)[0, 1]
            return correlation ** 2

        lr_r2 = series.rolling(period).apply(calc_r2, raw=True)

        return {
            'lr_value': lr_value,
            'lr_slope': lr_slope,
            'lr_r2': lr_r2
        }

    @staticmethod
    def vortex(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, pd.Series]:
        """Vortex Indicator"""
        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)

        vm_plus = abs(high - low.shift(1))
        vm_minus = abs(low - high.shift(1))

        tr_sum = tr.rolling(period).sum()
        vi_plus = vm_plus.rolling(period).sum() / tr_sum
        vi_minus = vm_minus.rolling(period).sum() / tr_sum

        return {
            'vi_plus': vi_plus,
            'vi_minus': vi_minus
        }

    @staticmethod
    def mass_index(high: pd.Series, low: pd.Series, ema_period: int = 9,
                   sum_period: int = 25) -> pd.Series:
        """Mass Index - Reversal signal"""
        range_hl = high - low
        ema1 = range_hl.ewm(span=ema_period, adjust=False).mean()
        ema2 = ema1.ewm(span=ema_period, adjust=False).mean()
        ratio = ema1 / ema2
        return ratio.rolling(sum_period).sum()

    @staticmethod
    def trix(series: pd.Series, period: int = 15) -> pd.Series:
        """TRIX - Triple Smoothed EMA Rate of Change"""
        ema1 = series.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        return ((ema3 - ema3.shift(1)) / ema3.shift(1)) * 100
