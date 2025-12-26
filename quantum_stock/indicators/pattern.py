"""
Pattern Recognition (20+)
Candlestick patterns and chart patterns
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional


class PatternRecognition:
    """Candlestick and chart pattern recognition"""

    @staticmethod
    def detect_all_patterns(open_: pd.Series, high: pd.Series, low: pd.Series,
                           close: pd.Series) -> pd.DataFrame:
        """Detect all candlestick patterns"""
        patterns = pd.DataFrame(index=close.index)

        # Single candle patterns
        patterns['doji'] = PatternRecognition.doji(open_, high, low, close)
        patterns['hammer'] = PatternRecognition.hammer(open_, high, low, close)
        patterns['inverted_hammer'] = PatternRecognition.inverted_hammer(open_, high, low, close)
        patterns['shooting_star'] = PatternRecognition.shooting_star(open_, high, low, close)
        patterns['hanging_man'] = PatternRecognition.hanging_man(open_, high, low, close)
        patterns['marubozu'] = PatternRecognition.marubozu(open_, high, low, close)
        patterns['spinning_top'] = PatternRecognition.spinning_top(open_, high, low, close)

        # Double candle patterns
        patterns['engulfing_bullish'] = PatternRecognition.engulfing_bullish(open_, close)
        patterns['engulfing_bearish'] = PatternRecognition.engulfing_bearish(open_, close)
        patterns['harami_bullish'] = PatternRecognition.harami_bullish(open_, close)
        patterns['harami_bearish'] = PatternRecognition.harami_bearish(open_, close)
        patterns['tweezer_top'] = PatternRecognition.tweezer_top(high, low, close)
        patterns['tweezer_bottom'] = PatternRecognition.tweezer_bottom(high, low, close)

        # Triple candle patterns
        patterns['morning_star'] = PatternRecognition.morning_star(open_, close)
        patterns['evening_star'] = PatternRecognition.evening_star(open_, close)
        patterns['three_white_soldiers'] = PatternRecognition.three_white_soldiers(open_, close)
        patterns['three_black_crows'] = PatternRecognition.three_black_crows(open_, close)

        return patterns

    @staticmethod
    def doji(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series,
             threshold: float = 0.1) -> pd.Series:
        """Doji - Open and close nearly equal"""
        body = abs(close - open_)
        range_ = high - low
        return (body / range_.replace(0, np.nan) < threshold).astype(int)

    @staticmethod
    def hammer(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Hammer - Bullish reversal at bottom"""
        body = abs(close - open_)
        range_ = high - low
        lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low
        upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)

        return ((lower_shadow >= 2 * body) &
                (upper_shadow < body * 0.5) &
                (body / range_.replace(0, np.nan) >= 0.1)).astype(int)

    @staticmethod
    def inverted_hammer(open_: pd.Series, high: pd.Series, low: pd.Series,
                       close: pd.Series) -> pd.Series:
        """Inverted Hammer - Bullish reversal"""
        body = abs(close - open_)
        range_ = high - low
        lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low
        upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)

        return ((upper_shadow >= 2 * body) &
                (lower_shadow < body * 0.5) &
                (body / range_.replace(0, np.nan) >= 0.1)).astype(int)

    @staticmethod
    def shooting_star(open_: pd.Series, high: pd.Series, low: pd.Series,
                     close: pd.Series) -> pd.Series:
        """Shooting Star - Bearish reversal at top"""
        body = abs(close - open_)
        upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)
        lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low

        return ((upper_shadow >= 2 * body) &
                (lower_shadow < body * 0.5) &
                (close < open_)).astype(int)

    @staticmethod
    def hanging_man(open_: pd.Series, high: pd.Series, low: pd.Series,
                   close: pd.Series) -> pd.Series:
        """Hanging Man - Bearish reversal at top"""
        body = abs(close - open_)
        lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low
        upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)

        return ((lower_shadow >= 2 * body) &
                (upper_shadow < body * 0.5)).astype(int)

    @staticmethod
    def marubozu(open_: pd.Series, high: pd.Series, low: pd.Series,
                close: pd.Series, threshold: float = 0.05) -> pd.Series:
        """Marubozu - Strong trend candle with no shadows"""
        body = abs(close - open_)
        range_ = high - low

        bullish = ((close > open_) &
                  ((high - close) / range_.replace(0, np.nan) < threshold) &
                  ((open_ - low) / range_.replace(0, np.nan) < threshold))

        bearish = ((close < open_) &
                  ((high - open_) / range_.replace(0, np.nan) < threshold) &
                  ((close - low) / range_.replace(0, np.nan) < threshold))

        result = pd.Series(0, index=close.index)
        result[bullish] = 1  # Bullish marubozu
        result[bearish] = -1  # Bearish marubozu
        return result

    @staticmethod
    def spinning_top(open_: pd.Series, high: pd.Series, low: pd.Series,
                    close: pd.Series) -> pd.Series:
        """Spinning Top - Indecision"""
        body = abs(close - open_)
        range_ = high - low
        upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)
        lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low

        return ((body / range_.replace(0, np.nan) < 0.3) &
                (upper_shadow > body) &
                (lower_shadow > body)).astype(int)

    @staticmethod
    def engulfing_bullish(open_: pd.Series, close: pd.Series) -> pd.Series:
        """Bullish Engulfing - Reversal pattern"""
        prev_bearish = close.shift(1) < open_.shift(1)
        curr_bullish = close > open_
        engulfs = (open_ < close.shift(1)) & (close > open_.shift(1))

        return (prev_bearish & curr_bullish & engulfs).astype(int)

    @staticmethod
    def engulfing_bearish(open_: pd.Series, close: pd.Series) -> pd.Series:
        """Bearish Engulfing - Reversal pattern"""
        prev_bullish = close.shift(1) > open_.shift(1)
        curr_bearish = close < open_
        engulfs = (open_ > close.shift(1)) & (close < open_.shift(1))

        return (prev_bullish & curr_bearish & engulfs).astype(int)

    @staticmethod
    def harami_bullish(open_: pd.Series, close: pd.Series) -> pd.Series:
        """Bullish Harami - Inside bar reversal"""
        prev_bearish = close.shift(1) < open_.shift(1)
        curr_bullish = close > open_
        inside = (open_ > close.shift(1)) & (close < open_.shift(1))

        return (prev_bearish & curr_bullish & inside).astype(int)

    @staticmethod
    def harami_bearish(open_: pd.Series, close: pd.Series) -> pd.Series:
        """Bearish Harami - Inside bar reversal"""
        prev_bullish = close.shift(1) > open_.shift(1)
        curr_bearish = close < open_
        inside = (open_ < close.shift(1)) & (close > open_.shift(1))

        return (prev_bullish & curr_bearish & inside).astype(int)

    @staticmethod
    def tweezer_top(high: pd.Series, low: pd.Series, close: pd.Series,
                   tolerance: float = 0.001) -> pd.Series:
        """Tweezer Top - Equal highs"""
        equal_highs = abs(high - high.shift(1)) / high < tolerance
        return equal_highs.astype(int)

    @staticmethod
    def tweezer_bottom(high: pd.Series, low: pd.Series, close: pd.Series,
                      tolerance: float = 0.001) -> pd.Series:
        """Tweezer Bottom - Equal lows"""
        equal_lows = abs(low - low.shift(1)) / low < tolerance
        return equal_lows.astype(int)

    @staticmethod
    def morning_star(open_: pd.Series, close: pd.Series) -> pd.Series:
        """Morning Star - Bullish 3-candle reversal"""
        first_bearish = close.shift(2) < open_.shift(2)
        small_body = abs(close.shift(1) - open_.shift(1)) < abs(close.shift(2) - open_.shift(2)) * 0.3
        third_bullish = close > open_
        closes_above_mid = close > (open_.shift(2) + close.shift(2)) / 2

        return (first_bearish & small_body & third_bullish & closes_above_mid).astype(int)

    @staticmethod
    def evening_star(open_: pd.Series, close: pd.Series) -> pd.Series:
        """Evening Star - Bearish 3-candle reversal"""
        first_bullish = close.shift(2) > open_.shift(2)
        small_body = abs(close.shift(1) - open_.shift(1)) < abs(close.shift(2) - open_.shift(2)) * 0.3
        third_bearish = close < open_
        closes_below_mid = close < (open_.shift(2) + close.shift(2)) / 2

        return (first_bullish & small_body & third_bearish & closes_below_mid).astype(int)

    @staticmethod
    def three_white_soldiers(open_: pd.Series, close: pd.Series) -> pd.Series:
        """Three White Soldiers - Strong bullish"""
        bull1 = close.shift(2) > open_.shift(2)
        bull2 = close.shift(1) > open_.shift(1)
        bull3 = close > open_

        higher_closes = (close > close.shift(1)) & (close.shift(1) > close.shift(2))
        opens_in_body = ((open_.shift(1) > open_.shift(2)) & (open_.shift(1) < close.shift(2)) &
                        (open_ > open_.shift(1)) & (open_ < close.shift(1)))

        return (bull1 & bull2 & bull3 & higher_closes & opens_in_body).astype(int)

    @staticmethod
    def three_black_crows(open_: pd.Series, close: pd.Series) -> pd.Series:
        """Three Black Crows - Strong bearish"""
        bear1 = close.shift(2) < open_.shift(2)
        bear2 = close.shift(1) < open_.shift(1)
        bear3 = close < open_

        lower_closes = (close < close.shift(1)) & (close.shift(1) < close.shift(2))

        return (bear1 & bear2 & bear3 & lower_closes).astype(int)

    @staticmethod
    def detect_support_resistance(high: pd.Series, low: pd.Series, close: pd.Series,
                                  window: int = 20, num_levels: int = 5) -> Dict[str, List[float]]:
        """Detect support and resistance levels using pivot points"""
        # Find local highs and lows
        local_highs = high[(high.shift(1) < high) & (high.shift(-1) < high)]
        local_lows = low[(low.shift(1) > low) & (low.shift(-1) > low)]

        # Cluster nearby levels
        def cluster_levels(levels, tolerance=0.02):
            if len(levels) == 0:
                return []

            levels = sorted(levels)
            clusters = [[levels[0]]]

            for level in levels[1:]:
                if (level - clusters[-1][0]) / clusters[-1][0] < tolerance:
                    clusters[-1].append(level)
                else:
                    clusters.append([level])

            return [np.mean(c) for c in clusters]

        resistance_levels = cluster_levels(local_highs.tolist())[-num_levels:]
        support_levels = cluster_levels(local_lows.tolist())[:num_levels]

        current_price = close.iloc[-1]

        # Filter levels near current price
        resistance = [r for r in resistance_levels if r > current_price]
        support = [s for s in support_levels if s < current_price]

        return {
            'resistance': sorted(resistance),
            'support': sorted(support, reverse=True)
        }

    @staticmethod
    def detect_divergence(close: pd.Series, indicator: pd.Series,
                         window: int = 14) -> Dict[str, pd.Series]:
        """Detect bullish and bearish divergence"""
        bullish_div = pd.Series(0, index=close.index)
        bearish_div = pd.Series(0, index=close.index)

        for i in range(window, len(close)):
            # Price lows
            price_window = close.iloc[i-window:i+1]
            ind_window = indicator.iloc[i-window:i+1]

            # Find local minima/maxima
            price_min_idx = price_window.idxmin()
            price_max_idx = price_window.idxmax()
            ind_min_idx = ind_window.idxmin()
            ind_max_idx = ind_window.idxmax()

            # Bullish divergence: Lower low in price, higher low in indicator
            if (close.iloc[i] < close.loc[price_min_idx] and
                indicator.iloc[i] > indicator.loc[ind_min_idx]):
                bullish_div.iloc[i] = 1

            # Bearish divergence: Higher high in price, lower high in indicator
            if (close.iloc[i] > close.loc[price_max_idx] and
                indicator.iloc[i] < indicator.loc[ind_max_idx]):
                bearish_div.iloc[i] = 1

        return {
            'bullish': bullish_div,
            'bearish': bearish_div
        }

    @staticmethod
    def double_top(high: pd.Series, close: pd.Series, tolerance: float = 0.02,
                   min_distance: int = 5) -> pd.Series:
        """Double Top Pattern Detection"""
        result = pd.Series(0, index=close.index)

        for i in range(min_distance * 2, len(high)):
            # Find peaks in window
            window = high.iloc[i-min_distance*2:i]
            peak1_idx = window.iloc[:min_distance].idxmax()
            peak2_idx = window.iloc[min_distance:].idxmax()

            peak1 = high.loc[peak1_idx]
            peak2 = high.loc[peak2_idx]

            # Check if peaks are similar
            if abs(peak1 - peak2) / peak1 < tolerance:
                # Check if there's a trough between
                trough = window.loc[peak1_idx:peak2_idx].min()
                if trough < peak1 * 0.98:
                    result.iloc[i] = 1

        return result

    @staticmethod
    def double_bottom(low: pd.Series, close: pd.Series, tolerance: float = 0.02,
                     min_distance: int = 5) -> pd.Series:
        """Double Bottom Pattern Detection"""
        result = pd.Series(0, index=close.index)

        for i in range(min_distance * 2, len(low)):
            window = low.iloc[i-min_distance*2:i]
            trough1_idx = window.iloc[:min_distance].idxmin()
            trough2_idx = window.iloc[min_distance:].idxmin()

            trough1 = low.loc[trough1_idx]
            trough2 = low.loc[trough2_idx]

            if abs(trough1 - trough2) / trough1 < tolerance:
                peak = window.loc[trough1_idx:trough2_idx].max()
                if peak > trough1 * 1.02:
                    result.iloc[i] = 1

        return result
