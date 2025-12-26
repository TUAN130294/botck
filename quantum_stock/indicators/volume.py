"""
Volume Indicators (15+)
For analyzing trading volume and money flow
"""

import pandas as pd
import numpy as np
from typing import Dict


class VolumeIndicators:
    """Collection of volume-based indicators"""

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """On-Balance Volume"""
        sign = np.sign(close.diff())
        return (sign * volume).cumsum()

    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
             period: int = None) -> pd.Series:
        """Volume Weighted Average Price"""
        typical_price = (high + low + close) / 3
        cumulative_tp_vol = (typical_price * volume).cumsum()
        cumulative_vol = volume.cumsum()

        if period:
            cumulative_tp_vol = (typical_price * volume).rolling(period).sum()
            cumulative_vol = volume.rolling(period).sum()

        return cumulative_tp_vol / cumulative_vol

    @staticmethod
    def mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
            period: int = 14) -> pd.Series:
        """Money Flow Index"""
        typical_price = (high + low + close) / 3
        raw_money_flow = typical_price * volume

        positive_flow = raw_money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = raw_money_flow.where(typical_price < typical_price.shift(1), 0)

        positive_mf = positive_flow.rolling(period).sum()
        negative_mf = negative_flow.rolling(period).sum()

        mfi = 100 - (100 / (1 + positive_mf / negative_mf.replace(0, np.nan)))
        return mfi.fillna(50)

    @staticmethod
    def accumulation_distribution(high: pd.Series, low: pd.Series, close: pd.Series,
                                 volume: pd.Series) -> pd.Series:
        """Accumulation/Distribution Line"""
        clv = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
        clv = clv.fillna(0)
        ad = (clv * volume).cumsum()
        return ad

    @staticmethod
    def chaikin_money_flow(high: pd.Series, low: pd.Series, close: pd.Series,
                          volume: pd.Series, period: int = 20) -> pd.Series:
        """Chaikin Money Flow"""
        clv = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
        clv = clv.fillna(0)
        cmf = (clv * volume).rolling(period).sum() / volume.rolling(period).sum()
        return cmf.fillna(0)

    @staticmethod
    def force_index(close: pd.Series, volume: pd.Series, period: int = 13) -> pd.Series:
        """Force Index"""
        fi = close.diff() * volume
        return fi.ewm(span=period, adjust=False).mean()

    @staticmethod
    def ease_of_movement(high: pd.Series, low: pd.Series, volume: pd.Series,
                        period: int = 14) -> pd.Series:
        """Ease of Movement"""
        dm = ((high + low) / 2) - ((high.shift(1) + low.shift(1)) / 2)
        br = (volume / 1000000) / (high - low)
        emv = dm / br.replace(0, np.nan)
        return emv.rolling(period).mean()

    @staticmethod
    def volume_oscillator(volume: pd.Series, fast: int = 5, slow: int = 20) -> pd.Series:
        """Volume Oscillator"""
        fast_ma = volume.rolling(fast).mean()
        slow_ma = volume.rolling(slow).mean()
        return ((fast_ma - slow_ma) / slow_ma) * 100

    @staticmethod
    def volume_price_trend(close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume Price Trend"""
        vpt = ((close.diff() / close.shift(1)) * volume).cumsum()
        return vpt

    @staticmethod
    def negative_volume_index(close: pd.Series, volume: pd.Series) -> pd.Series:
        """Negative Volume Index"""
        nvi = pd.Series(index=close.index, dtype=float)
        nvi.iloc[0] = 1000

        for i in range(1, len(close)):
            if volume.iloc[i] < volume.iloc[i-1]:
                nvi.iloc[i] = nvi.iloc[i-1] * (1 + (close.iloc[i] - close.iloc[i-1]) / close.iloc[i-1])
            else:
                nvi.iloc[i] = nvi.iloc[i-1]

        return nvi

    @staticmethod
    def positive_volume_index(close: pd.Series, volume: pd.Series) -> pd.Series:
        """Positive Volume Index"""
        pvi = pd.Series(index=close.index, dtype=float)
        pvi.iloc[0] = 1000

        for i in range(1, len(close)):
            if volume.iloc[i] > volume.iloc[i-1]:
                pvi.iloc[i] = pvi.iloc[i-1] * (1 + (close.iloc[i] - close.iloc[i-1]) / close.iloc[i-1])
            else:
                pvi.iloc[i] = pvi.iloc[i-1]

        return pvi

    @staticmethod
    def klinger_oscillator(high: pd.Series, low: pd.Series, close: pd.Series,
                          volume: pd.Series, fast: int = 34, slow: int = 55) -> Dict[str, pd.Series]:
        """Klinger Volume Oscillator"""
        hlc3 = (high + low + close) / 3
        dm = high - low

        # Trend
        trend = pd.Series(index=close.index, dtype=float)
        trend.iloc[0] = 0

        for i in range(1, len(close)):
            if hlc3.iloc[i] > hlc3.iloc[i-1]:
                trend.iloc[i] = 1
            elif hlc3.iloc[i] < hlc3.iloc[i-1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i-1]

        vf = volume * abs(2 * (dm / hlc3) - 1) * trend * 100

        kvo = vf.ewm(span=fast, adjust=False).mean() - vf.ewm(span=slow, adjust=False).mean()
        signal = kvo.ewm(span=13, adjust=False).mean()

        return {
            'kvo': kvo,
            'signal': signal
        }

    @staticmethod
    def elder_force_index(close: pd.Series, volume: pd.Series,
                         period: int = 13) -> pd.Series:
        """Elder's Force Index"""
        fi = close.diff() * volume
        return fi.ewm(span=period, adjust=False).mean()

    @staticmethod
    def volume_weighted_macd(close: pd.Series, volume: pd.Series,
                            fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Volume Weighted MACD"""
        def vwma(price, vol, period):
            return (price * vol).rolling(period).sum() / vol.rolling(period).sum()

        vwma_fast = vwma(close, volume, fast)
        vwma_slow = vwma(close, volume, slow)

        vw_macd = vwma_fast - vwma_slow
        vw_signal = vw_macd.ewm(span=signal, adjust=False).mean()
        vw_hist = vw_macd - vw_signal

        return {
            'vw_macd': vw_macd,
            'signal': vw_signal,
            'histogram': vw_hist
        }

    @staticmethod
    def volume_zone_oscillator(close: pd.Series, volume: pd.Series,
                              period: int = 14) -> pd.Series:
        """Volume Zone Oscillator"""
        price_change = close.diff()
        pos_vol = volume.where(price_change > 0, 0)
        neg_vol = volume.where(price_change < 0, 0)

        pos_vol_sum = pos_vol.rolling(period).sum()
        neg_vol_sum = neg_vol.rolling(period).sum()
        total_vol_sum = volume.rolling(period).sum()

        vzo = 100 * (pos_vol_sum - neg_vol_sum) / total_vol_sum
        return vzo.fillna(0)

    @staticmethod
    def price_volume_trend_rate(close: pd.Series, volume: pd.Series,
                               period: int = 14) -> pd.Series:
        """Price Volume Trend Rate of Change"""
        pvt = VolumeIndicators.volume_price_trend(close, volume)
        pvt_roc = (pvt - pvt.shift(period)) / pvt.shift(period).abs().replace(0, np.nan) * 100
        return pvt_roc.fillna(0)

    @staticmethod
    def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
        """Volume Ratio (current vs average)"""
        avg_vol = volume.rolling(period).mean()
        return volume / avg_vol

    @staticmethod
    def cumulative_volume_delta(open_: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Cumulative Volume Delta (Buy vs Sell Pressure)"""
        # Estimate buying/selling volume based on candle position
        hl_range = close - open_

        buy_vol = volume.where(hl_range > 0, volume * 0.5)
        sell_vol = volume.where(hl_range < 0, volume * 0.5)

        delta = buy_vol - sell_vol
        return delta.cumsum()

    @staticmethod
    def twiggs_money_flow(high: pd.Series, low: pd.Series, close: pd.Series,
                         volume: pd.Series, period: int = 21) -> pd.Series:
        """Twiggs Money Flow"""
        # True Range High/Low
        tr_high = pd.concat([high, close.shift(1)], axis=1).max(axis=1)
        tr_low = pd.concat([low, close.shift(1)], axis=1).min(axis=1)

        ad = ((close - tr_low) - (tr_high - close)) / (tr_high - tr_low).replace(0, np.nan) * volume

        # Smoothed
        ad_smooth = ad.ewm(span=period, adjust=False).mean()
        vol_smooth = volume.ewm(span=period, adjust=False).mean()

        return ad_smooth / vol_smooth

    @staticmethod
    def volume_profile(close: pd.Series, volume: pd.Series, bins: int = 20) -> Dict[str, any]:
        """Volume Profile (Volume at Price)"""
        price_min = close.min()
        price_max = close.max()
        price_range = price_max - price_min
        bin_size = price_range / bins

        levels = []
        volumes = []

        for i in range(bins):
            level_low = price_min + (i * bin_size)
            level_high = price_min + ((i + 1) * bin_size)
            level_mid = (level_low + level_high) / 2

            mask = (close >= level_low) & (close < level_high)
            vol_at_level = volume[mask].sum()

            levels.append(level_mid)
            volumes.append(vol_at_level)

        # Point of Control (highest volume price)
        max_vol_idx = np.argmax(volumes)
        poc = levels[max_vol_idx]

        return {
            'levels': levels,
            'volumes': volumes,
            'poc': poc,
            'value_area_high': levels[max_vol_idx + 1] if max_vol_idx < len(levels) - 1 else poc,
            'value_area_low': levels[max_vol_idx - 1] if max_vol_idx > 0 else poc
        }
