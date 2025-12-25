"""
Momentum Indicators (20+)
For measuring speed and strength of price movements
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class MomentumIndicators:
    """Collection of momentum indicators"""

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50)

    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                   k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """Stochastic Oscillator"""
        lowest_low = low.rolling(k_period).min()
        highest_high = high.rolling(k_period).max()

        stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
        stoch_d = stoch_k.rolling(d_period).mean()

        return {
            'stoch_k': stoch_k.fillna(50),
            'stoch_d': stoch_d.fillna(50)
        }

    @staticmethod
    def stochastic_rsi(series: pd.Series, rsi_period: int = 14,
                       k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """Stochastic RSI"""
        rsi = MomentumIndicators.rsi(series, rsi_period)

        lowest_rsi = rsi.rolling(k_period).min()
        highest_rsi = rsi.rolling(k_period).max()

        stoch_rsi = (rsi - lowest_rsi) / (highest_rsi - lowest_rsi).replace(0, np.nan)
        stoch_rsi_k = stoch_rsi * 100
        stoch_rsi_d = stoch_rsi_k.rolling(d_period).mean()

        return {
            'stoch_rsi_k': stoch_rsi_k.fillna(50),
            'stoch_rsi_d': stoch_rsi_d.fillna(50)
        }

    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
        """Commodity Channel Index"""
        typical_price = (high + low + close) / 3
        sma = typical_price.rolling(period).mean()
        mad = typical_price.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)

        cci = (typical_price - sma) / (0.015 * mad)
        return cci.fillna(0)

    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Williams %R"""
        highest_high = high.rolling(period).max()
        lowest_low = low.rolling(period).min()

        williams = -100 * (highest_high - close) / (highest_high - lowest_low).replace(0, np.nan)
        return williams.fillna(-50)

    @staticmethod
    def momentum(series: pd.Series, period: int = 10) -> pd.Series:
        """Simple Momentum"""
        return series - series.shift(period)

    @staticmethod
    def roc(series: pd.Series, period: int = 10) -> pd.Series:
        """Rate of Change"""
        return ((series - series.shift(period)) / series.shift(period).replace(0, np.nan)) * 100

    @staticmethod
    def ppo(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Percentage Price Oscillator"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()

        ppo_line = ((ema_fast - ema_slow) / ema_slow) * 100
        signal_line = ppo_line.ewm(span=signal, adjust=False).mean()
        histogram = ppo_line - signal_line

        return {
            'ppo': ppo_line,
            'signal': signal_line,
            'histogram': histogram
        }

    @staticmethod
    def tsi(series: pd.Series, long_period: int = 25, short_period: int = 13) -> pd.Series:
        """True Strength Index"""
        pc = series.diff()

        # Double smoothing
        pc_double_smooth = pc.ewm(span=long_period, adjust=False).mean().ewm(span=short_period, adjust=False).mean()
        abs_pc_double_smooth = abs(pc).ewm(span=long_period, adjust=False).mean().ewm(span=short_period, adjust=False).mean()

        tsi = 100 * (pc_double_smooth / abs_pc_double_smooth.replace(0, np.nan))
        return tsi.fillna(0)

    @staticmethod
    def ultimate_oscillator(high: pd.Series, low: pd.Series, close: pd.Series,
                           period1: int = 7, period2: int = 14, period3: int = 28) -> pd.Series:
        """Ultimate Oscillator"""
        bp = close - pd.concat([low, close.shift(1)], axis=1).min(axis=1)
        tr = pd.concat([
            high - low,
            abs(high - close.shift(1)),
            abs(low - close.shift(1))
        ], axis=1).max(axis=1)

        avg1 = bp.rolling(period1).sum() / tr.rolling(period1).sum()
        avg2 = bp.rolling(period2).sum() / tr.rolling(period2).sum()
        avg3 = bp.rolling(period3).sum() / tr.rolling(period3).sum()

        uo = 100 * ((4 * avg1) + (2 * avg2) + avg3) / 7
        return uo.fillna(50)

    @staticmethod
    def awesome_oscillator(high: pd.Series, low: pd.Series,
                          fast: int = 5, slow: int = 34) -> pd.Series:
        """Awesome Oscillator"""
        median_price = (high + low) / 2
        ao = median_price.rolling(fast).mean() - median_price.rolling(slow).mean()
        return ao

    @staticmethod
    def accelerator_oscillator(high: pd.Series, low: pd.Series,
                              fast: int = 5, slow: int = 34, signal: int = 5) -> pd.Series:
        """Accelerator Oscillator"""
        ao = MomentumIndicators.awesome_oscillator(high, low, fast, slow)
        ac = ao - ao.rolling(signal).mean()
        return ac

    @staticmethod
    def cmo(series: pd.Series, period: int = 14) -> pd.Series:
        """Chande Momentum Oscillator"""
        delta = series.diff()
        gains = delta.where(delta > 0, 0).rolling(period).sum()
        losses = (-delta.where(delta < 0, 0)).rolling(period).sum()

        cmo = 100 * (gains - losses) / (gains + losses).replace(0, np.nan)
        return cmo.fillna(0)

    @staticmethod
    def dpo(series: pd.Series, period: int = 20) -> pd.Series:
        """Detrended Price Oscillator"""
        shift = int(period / 2) + 1
        sma = series.rolling(period).mean()
        return series.shift(shift) - sma

    @staticmethod
    def kst(series: pd.Series, roc1: int = 10, roc2: int = 15, roc3: int = 20, roc4: int = 30,
            sma1: int = 10, sma2: int = 10, sma3: int = 10, sma4: int = 15,
            signal: int = 9) -> Dict[str, pd.Series]:
        """Know Sure Thing (KST)"""
        rocma1 = MomentumIndicators.roc(series, roc1).rolling(sma1).mean()
        rocma2 = MomentumIndicators.roc(series, roc2).rolling(sma2).mean()
        rocma3 = MomentumIndicators.roc(series, roc3).rolling(sma3).mean()
        rocma4 = MomentumIndicators.roc(series, roc4).rolling(sma4).mean()

        kst = (rocma1 * 1) + (rocma2 * 2) + (rocma3 * 3) + (rocma4 * 4)
        kst_signal = kst.rolling(signal).mean()

        return {
            'kst': kst,
            'signal': kst_signal
        }

    @staticmethod
    def rvi(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series,
            period: int = 10, signal_period: int = 4) -> Dict[str, pd.Series]:
        """Relative Vigor Index"""
        numerator = (close - open_) + 2 * (close.shift(1) - open_.shift(1)) + 2 * (close.shift(2) - open_.shift(2)) + (close.shift(3) - open_.shift(3))
        denominator = (high - low) + 2 * (high.shift(1) - low.shift(1)) + 2 * (high.shift(2) - low.shift(2)) + (high.shift(3) - low.shift(3))

        rvi = (numerator / 6) / (denominator / 6).replace(0, np.nan)
        rvi_smooth = rvi.rolling(period).mean()
        rvi_signal = (rvi_smooth + 2 * rvi_smooth.shift(1) + 2 * rvi_smooth.shift(2) + rvi_smooth.shift(3)) / 6

        return {
            'rvi': rvi_smooth.fillna(0),
            'signal': rvi_signal.fillna(0)
        }

    @staticmethod
    def elder_ray(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 13) -> Dict[str, pd.Series]:
        """Elder Ray Index (Bull/Bear Power)"""
        ema = close.ewm(span=period, adjust=False).mean()

        bull_power = high - ema
        bear_power = low - ema

        return {
            'bull_power': bull_power,
            'bear_power': bear_power
        }

    @staticmethod
    def fisher_transform(high: pd.Series, low: pd.Series, period: int = 10) -> Dict[str, pd.Series]:
        """Fisher Transform"""
        hl2 = (high + low) / 2
        max_high = hl2.rolling(period).max()
        min_low = hl2.rolling(period).min()

        value = 2 * ((hl2 - min_low) / (max_high - min_low).replace(0, np.nan)) - 1
        value = value.clip(-0.999, 0.999)

        fisher = pd.Series(index=high.index, dtype=float)
        fisher.iloc[0] = 0

        for i in range(1, len(value)):
            if pd.notna(value.iloc[i]):
                fisher.iloc[i] = 0.5 * np.log((1 + value.iloc[i]) / (1 - value.iloc[i])) + 0.5 * fisher.iloc[i-1]

        fisher_signal = fisher.shift(1)

        return {
            'fisher': fisher,
            'signal': fisher_signal
        }

    @staticmethod
    def connors_rsi(series: pd.Series, rsi_period: int = 3,
                   streak_period: int = 2, rank_period: int = 100) -> pd.Series:
        """Connors RSI"""
        # RSI component
        rsi = MomentumIndicators.rsi(series, rsi_period)

        # Streak RSI
        streak = pd.Series(index=series.index, dtype=float)
        streak.iloc[0] = 0

        for i in range(1, len(series)):
            if series.iloc[i] > series.iloc[i-1]:
                streak.iloc[i] = max(0, streak.iloc[i-1]) + 1
            elif series.iloc[i] < series.iloc[i-1]:
                streak.iloc[i] = min(0, streak.iloc[i-1]) - 1
            else:
                streak.iloc[i] = 0

        streak_rsi = MomentumIndicators.rsi(streak, streak_period)

        # Percent Rank
        pct_rank = series.diff().rolling(rank_period).apply(
            lambda x: np.sum(x.iloc[-1] > x[:-1]) / (len(x) - 1) * 100, raw=False
        )

        crsi = (rsi + streak_rsi + pct_rank) / 3
        return crsi.fillna(50)

    @staticmethod
    def qstick(open_: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """QStick Indicator"""
        return (close - open_).rolling(period).mean()

    @staticmethod
    def balance_of_power(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Balance of Power"""
        bop = (close - open_) / (high - low).replace(0, np.nan)
        return bop.fillna(0)
