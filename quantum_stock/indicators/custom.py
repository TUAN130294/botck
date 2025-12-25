"""
Custom Indicators for Vietnamese Stock Market
Vietnam-specific and advanced composite indicators
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from .trend import TrendIndicators
from .momentum import MomentumIndicators
from .volatility import VolatilityIndicators
from .volume import VolumeIndicators


class CustomIndicators:
    """Custom and composite indicators optimized for Vietnamese market"""

    @staticmethod
    def vn_market_strength(vn_index: pd.Series, vn30: pd.Series,
                          advance_decline: pd.Series = None) -> pd.Series:
        """
        VN Market Strength Index
        Combines VN-Index and VN30 momentum
        """
        vn_index_change = vn_index.pct_change()
        vn30_change = vn30.pct_change()

        # VN30 leads the market
        strength = (vn_index_change * 0.4 + vn30_change * 0.6) * 100

        if advance_decline is not None:
            strength = strength * 0.8 + advance_decline.pct_change() * 0.2 * 100

        return strength

    @staticmethod
    def foreign_flow_indicator(foreign_buy: pd.Series, foreign_sell: pd.Series,
                               period: int = 10) -> Dict[str, pd.Series]:
        """
        Foreign Investor Flow Indicator
        Track net foreign buying/selling
        """
        net_flow = foreign_buy - foreign_sell
        cumulative_flow = net_flow.cumsum()
        flow_ma = net_flow.rolling(period).mean()

        # Normalize
        flow_strength = net_flow / net_flow.rolling(period).std()

        return {
            'net_flow': net_flow,
            'cumulative': cumulative_flow,
            'flow_ma': flow_ma,
            'flow_strength': flow_strength.fillna(0)
        }

    @staticmethod
    def vn_sector_rotation(sector_returns: Dict[str, pd.Series],
                          period: int = 20) -> Dict[str, pd.Series]:
        """
        Sector Rotation Analysis for Vietnam market
        """
        sector_momentum = {}
        sector_relative = {}

        # Calculate momentum for each sector
        for sector, returns in sector_returns.items():
            sector_momentum[sector] = returns.rolling(period).sum()

        # Calculate relative strength
        all_sectors = pd.DataFrame(sector_momentum)
        mean_momentum = all_sectors.mean(axis=1)

        for sector in sector_returns.keys():
            sector_relative[sector] = sector_momentum[sector] - mean_momentum

        return {
            'momentum': pd.DataFrame(sector_momentum),
            'relative_strength': pd.DataFrame(sector_relative)
        }

    @staticmethod
    def liquidity_score(volume: pd.Series, avg_volume_20: pd.Series,
                       close: pd.Series, spread: pd.Series = None) -> pd.Series:
        """
        Liquidity Score for Vietnamese stocks
        Higher score = better liquidity
        """
        # Volume ratio
        vol_ratio = volume / avg_volume_20

        # Turnover
        if spread is not None:
            liquidity = vol_ratio * (1 - spread / close)
        else:
            liquidity = vol_ratio

        # Normalize to 0-100
        liquidity_score = (liquidity - liquidity.min()) / (liquidity.max() - liquidity.min()) * 100

        return liquidity_score.fillna(50)

    @staticmethod
    def ceiling_floor_detector(high: pd.Series, low: pd.Series, close: pd.Series,
                               period: int = 20) -> Dict[str, pd.Series]:
        """
        Detect ceiling/floor price (Vietnam market specific)
        Stocks have +/-7% daily limit
        """
        ref_price = close.shift(1)
        ceiling = ref_price * 1.07
        floor = ref_price * 0.93

        at_ceiling = (high >= ceiling * 0.995).astype(int)
        at_floor = (low <= floor * 1.005).astype(int)

        ceiling_hits = at_ceiling.rolling(period).sum()
        floor_hits = at_floor.rolling(period).sum()

        return {
            'ceiling': ceiling,
            'floor': floor,
            'at_ceiling': at_ceiling,
            'at_floor': at_floor,
            'ceiling_hits': ceiling_hits,
            'floor_hits': floor_hits
        }

    @staticmethod
    def smart_money_index(open_: pd.Series, close: pd.Series, volume: pd.Series,
                         period: int = 14) -> pd.Series:
        """
        Smart Money Index
        Early trading = Emotional, Late trading = Smart money
        """
        # Approximation using open-to-close dynamics
        early_move = (close.shift(1) - open_) / open_ * 100
        late_move = (close - open_) / open_ * 100

        smi = late_move.rolling(period).sum() - early_move.rolling(period).sum()
        return smi

    @staticmethod
    def composite_momentum(close: pd.Series, high: pd.Series, low: pd.Series,
                          volume: pd.Series) -> pd.Series:
        """
        Composite Momentum Score (0-100)
        Combines multiple momentum indicators
        """
        rsi = MomentumIndicators.rsi(close, 14)
        stoch = MomentumIndicators.stochastic(high, low, close)['stoch_k']
        cci = MomentumIndicators.cci(high, low, close, 20)
        mfi = VolumeIndicators.mfi(high, low, close, volume, 14)

        # Normalize CCI to 0-100
        cci_norm = 50 + cci / 4  # CCI typically ranges -200 to 200
        cci_norm = cci_norm.clip(0, 100)

        # Composite
        composite = (rsi * 0.3 + stoch * 0.2 + cci_norm * 0.2 + mfi * 0.3)
        return composite

    @staticmethod
    def trend_strength_composite(close: pd.Series, high: pd.Series, low: pd.Series,
                                volume: pd.Series) -> Dict[str, pd.Series]:
        """
        Composite Trend Strength Analysis
        """
        # ADX
        adx_data = TrendIndicators.adx(high, low, close, 14)
        adx = adx_data['adx']

        # EMA alignment
        ema10 = TrendIndicators.ema(close, 10)
        ema20 = TrendIndicators.ema(close, 20)
        ema50 = TrendIndicators.ema(close, 50)

        ema_aligned_bull = ((close > ema10) & (ema10 > ema20) & (ema20 > ema50)).astype(int)
        ema_aligned_bear = ((close < ema10) & (ema10 < ema20) & (ema20 < ema50)).astype(int)

        # Supertrend
        supertrend_data = TrendIndicators.supertrend(high, low, close, 10, 3)
        supertrend_dir = supertrend_data['direction']

        # Composite trend score
        trend_score = pd.Series(50, index=close.index)
        trend_score = trend_score + (adx - 25) * 0.5  # ADX contribution
        trend_score = trend_score + ema_aligned_bull * 20 - ema_aligned_bear * 20
        trend_score = trend_score + supertrend_dir * 10

        trend_score = trend_score.clip(0, 100)

        return {
            'trend_score': trend_score,
            'adx': adx,
            'direction': supertrend_dir,
            'ema_aligned': ema_aligned_bull - ema_aligned_bear
        }

    @staticmethod
    def volatility_regime(close: pd.Series, high: pd.Series, low: pd.Series,
                         period: int = 20) -> Dict[str, pd.Series]:
        """
        Volatility Regime Detection
        LOW, NORMAL, HIGH, EXTREME
        """
        atr = VolatilityIndicators.atr(high, low, close, period)
        atr_pct = (atr / close) * 100

        # Historical percentiles
        atr_percentile = atr_pct.rolling(252).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False
        )

        # Regime classification
        regime = pd.Series('NORMAL', index=close.index)
        regime[atr_percentile < 25] = 'LOW'
        regime[atr_percentile > 75] = 'HIGH'
        regime[atr_percentile > 90] = 'EXTREME'

        return {
            'atr_pct': atr_pct,
            'atr_percentile': atr_percentile.fillna(50),
            'regime': regime
        }

    @staticmethod
    def price_action_score(open_: pd.Series, high: pd.Series, low: pd.Series,
                          close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Price Action Quality Score
        Combines multiple price action factors
        """
        # Body to range ratio
        body = abs(close - open_)
        range_ = high - low
        body_ratio = body / range_.replace(0, np.nan)

        # Upper/Lower wick ratio
        upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
        lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low

        # Close position in range
        close_position = (close - low) / range_.replace(0, np.nan)

        # Volume confirmation
        vol_ratio = volume / volume.rolling(20).mean()

        # Bullish factors
        bullish_close = (close > open_).astype(int)
        strong_close = (close_position > 0.7).astype(int)
        volume_confirm = (vol_ratio > 1.2).astype(int) * bullish_close

        # Score
        score = (body_ratio * 30 +
                close_position * 30 +
                bullish_close * 20 +
                volume_confirm * 20)

        return score.fillna(50).clip(0, 100)

    @staticmethod
    def breakout_strength(close: pd.Series, high: pd.Series, low: pd.Series,
                         volume: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """
        Breakout Strength Indicator
        Measures quality of price breakouts
        """
        # Resistance/Support levels
        resistance = high.rolling(period).max()
        support = low.rolling(period).min()

        # Breakout detection
        breakout_up = (close > resistance.shift(1)).astype(int)
        breakout_down = (close < support.shift(1)).astype(int)

        # Breakout strength (volume confirmation)
        vol_avg = volume.rolling(period).mean()
        vol_ratio = volume / vol_avg

        breakout_strength = breakout_up * vol_ratio - breakout_down * vol_ratio

        # Distance from breakout level
        distance_up = (close - resistance.shift(1)) / close * 100
        distance_down = (support.shift(1) - close) / close * 100

        return {
            'breakout_up': breakout_up,
            'breakout_down': breakout_down,
            'strength': breakout_strength,
            'distance_up': distance_up.fillna(0),
            'distance_down': distance_down.fillna(0),
            'resistance': resistance,
            'support': support
        }

    @staticmethod
    def risk_adjusted_momentum(close: pd.Series, high: pd.Series, low: pd.Series,
                              period: int = 20) -> pd.Series:
        """
        Risk-Adjusted Momentum (RAM)
        Momentum divided by volatility
        """
        returns = close.pct_change(period) * 100
        volatility = VolatilityIndicators.historical_volatility(close, period, annualize=False)

        ram = returns / volatility.replace(0, np.nan)
        return ram.fillna(0)

    @staticmethod
    def accumulation_distribution_zone(close: pd.Series, volume: pd.Series,
                                       period: int = 20) -> Dict[str, pd.Series]:
        """
        Accumulation/Distribution Zone Detection
        """
        ad_line = VolumeIndicators.accumulation_distribution(close, close, close, volume)
        ad_ema = ad_line.ewm(span=period).mean()

        # Zone classification
        zone = pd.Series('NEUTRAL', index=close.index)
        zone[ad_line > ad_ema] = 'ACCUMULATION'
        zone[ad_line < ad_ema] = 'DISTRIBUTION'

        # Strength
        strength = (ad_line - ad_ema) / ad_ema.abs().replace(0, np.nan) * 100

        return {
            'ad_line': ad_line,
            'ad_ema': ad_ema,
            'zone': zone,
            'strength': strength.fillna(0).clip(-100, 100)
        }

    @staticmethod
    def market_timing_signal(close: pd.Series, high: pd.Series, low: pd.Series,
                            volume: pd.Series) -> Dict[str, any]:
        """
        Comprehensive Market Timing Signal
        Combines multiple factors into a single signal
        """
        # Trend
        ema20 = TrendIndicators.ema(close, 20)
        ema50 = TrendIndicators.ema(close, 50)
        trend_bull = (ema20 > ema50).astype(int)

        # Momentum
        rsi = MomentumIndicators.rsi(close, 14)
        momentum_score = (rsi - 30) / 40  # Normalize: 30-70 -> 0-1

        # Volume
        vol_ratio = volume / volume.rolling(20).mean()
        vol_score = (vol_ratio.clip(0.5, 2) - 0.5) / 1.5  # Normalize

        # Volatility regime
        atr_pct = VolatilityIndicators.natr(high, low, close, 14)
        vol_regime_score = 1 - (atr_pct / 10).clip(0, 1)  # Lower vol = higher score

        # Composite signal
        signal = (trend_bull * 0.3 +
                 momentum_score.clip(0, 1) * 0.3 +
                 vol_score * 0.2 +
                 vol_regime_score * 0.2)

        signal = signal * 100

        # Classification
        signal_class = pd.Series('NEUTRAL', index=close.index)
        signal_class[signal > 70] = 'STRONG_BUY'
        signal_class[signal > 55] = 'BUY'
        signal_class[signal < 30] = 'STRONG_SELL'
        signal_class[signal < 45] = 'SELL'

        return {
            'signal': signal,
            'signal_class': signal_class,
            'trend_score': trend_bull * 100,
            'momentum_score': momentum_score * 100,
            'volume_score': vol_score * 100,
            'volatility_score': vol_regime_score * 100
        }
