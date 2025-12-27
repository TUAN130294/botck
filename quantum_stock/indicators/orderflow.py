# -*- coding: utf-8 -*-
"""
Order Flow Analysis Indicators
Advanced indicators for reading institutional order flow
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class OrderFlowSignal:
    """Order flow trading signal"""
    signal_type: str
    direction: str
    strength: float
    price: float
    description: str
    
    def to_dict(self) -> Dict:
        return {
            'type': self.signal_type,
            'direction': self.direction,
            'strength': self.strength,
            'price': self.price,
            'description': self.description
        }


class OrderFlowIndicators:
    """Advanced Order Flow Analysis"""
    
    @staticmethod
    def vwap_bands(high: pd.Series, low: pd.Series, close: pd.Series,
                   volume: pd.Series, num_std: float = 2.0) -> Dict:
        """VWAP with Standard Deviation Bands"""
        typical_price = (high + low + close) / 3
        cumulative_tp_vol = (typical_price * volume).cumsum()
        cumulative_vol = volume.cumsum()
        vwap = cumulative_tp_vol / cumulative_vol.replace(0, np.nan)
        
        squared_diff = (typical_price - vwap) ** 2
        variance = (squared_diff * volume).cumsum() / cumulative_vol.replace(0, np.nan)
        std = np.sqrt(variance)
        
        return {
            'vwap': vwap,
            'upper_1': vwap + std,
            'upper_2': vwap + 2 * std,
            'lower_1': vwap - std,
            'lower_2': vwap - 2 * std,
            'distance_from_vwap': (close - vwap) / vwap * 100
        }
    
    @staticmethod
    def cumulative_delta(open_: pd.Series, high: pd.Series, low: pd.Series,
                         close: pd.Series, volume: pd.Series) -> Dict:
        """Cumulative Volume Delta"""
        full_range = (high - low).replace(0, np.nan)
        buy_ratio = ((close - low) / full_range).clip(0.2, 0.8).fillna(0.5)
        
        buy_volume = volume * buy_ratio
        sell_volume = volume * (1 - buy_ratio)
        delta = buy_volume - sell_volume
        
        return {
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'delta': delta,
            'cumulative_delta': delta.cumsum(),
            'delta_ema': delta.ewm(span=14).mean()
        }
    
    @staticmethod
    def absorption_exhaustion(open_: pd.Series, high: pd.Series, low: pd.Series,
                              close: pd.Series, volume: pd.Series) -> Dict:
        """Detect Absorption and Exhaustion patterns"""
        price_range = high - low
        avg_volume = volume.rolling(20).mean()
        avg_range = price_range.rolling(20).mean()
        
        volume_ratio = volume / avg_volume.replace(0, np.nan)
        range_ratio = price_range / avg_range.replace(0, np.nan)
        
        absorption = (volume_ratio > 1.5) & (range_ratio < 0.5)
        bullish_absorption = absorption & (close > (high + low) / 2)
        bearish_absorption = absorption & (close <= (high + low) / 2)
        
        return {
            'absorption': absorption,
            'bullish_absorption': bullish_absorption,
            'bearish_absorption': bearish_absorption,
            'volume_ratio': volume_ratio
        }


class ForeignFlowIndicators:
    """Foreign & Proprietary Flow Analysis for Vietnamese market"""
    
    @staticmethod
    def foreign_flow_analysis(foreign_buy: pd.Series, foreign_sell: pd.Series,
                              total_volume: pd.Series, close: pd.Series) -> Dict:
        """Analyze foreign investor flow"""
        net_foreign = foreign_buy - foreign_sell
        cumulative = net_foreign.cumsum()
        participation = (foreign_buy + foreign_sell) / total_volume * 100
        
        return {
            'net_foreign': net_foreign,
            'cumulative_foreign': cumulative,
            'participation_ratio': participation,
            'is_accumulating': net_foreign.rolling(5).mean() > 0
        }
    
    @staticmethod
    def smart_money_index(close: pd.Series, volume: pd.Series,
                          foreign_net: pd.Series = None) -> pd.Series:
        """Smart Money Index combining institutional flows"""
        price_momentum = close.pct_change(5)
        volume_ratio = volume / volume.rolling(20).mean().replace(0, np.nan)
        
        if foreign_net is not None:
            foreign_component = foreign_net / volume * 100
        else:
            foreign_component = pd.Series(0, index=close.index)
        
        smi = price_momentum.fillna(0) * 50 + volume_ratio.fillna(1) * 30 + foreign_component.fillna(0) * 20
        
        return ((smi - smi.rolling(50).min()) / 
                (smi.rolling(50).max() - smi.rolling(50).min() + 0.0001) * 100).fillna(50)
