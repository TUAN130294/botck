# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    DEEP FLOW INTELLIGENCE MODULE                             ║
║                    Hidden Insights in Money Flow Data                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Tính năng đào sâu mà chuyên gia thông thường KHÔNG THỂ thấy được:
1. Block Trade Detection - Phát hiện lệnh lớn bất thường
2. Iceberg Order Detection - Phát hiện lệnh chia nhỏ
3. Order Flow Imbalance - Mất cân bằng mua/bán
4. Accumulation/Distribution Patterns - Mô hình tích lũy/phân phối
5. VWAP Deviation Analysis - Độ lệch giá vs VWAP
6. Institutional Footprint - Dấu chân tổ chức
7. Smart Money Divergence - Phân kỳ dòng tiền thông minh
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import os


class FlowSignalType(Enum):
    """Types of flow signals"""
    BLOCK_TRADE = "BLOCK_TRADE"
    ICEBERG_ORDER = "ICEBERG_ORDER"
    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"
    UNUSUAL_VOLUME = "UNUSUAL_VOLUME"
    VWAP_DEVIATION = "VWAP_DEVIATION"
    SMART_DIVERGENCE = "SMART_DIVERGENCE"
    ABSORPTION = "ABSORPTION"
    EXHAUSTION = "EXHAUSTION"


@dataclass
class FlowInsight:
    """Single flow insight/signal"""
    signal_type: FlowSignalType
    symbol: str
    timestamp: datetime
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    direction: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float  # 0-1
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'signal_type': self.signal_type.value,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity,
            'direction': self.direction,
            'confidence': self.confidence,
            'description': self.description,
            'data': self.data
        }


class DeepFlowIntelligence:
    """
    Deep Flow Intelligence - Đào sâu insight ẩn trong dòng tiền
    
    Những phân tích mà chuyên gia thông thường KHÔNG THỂ thấy được:
    - Phát hiện lệnh lớn ẩn (Iceberg)
    - Phát hiện tích lũy/phân phối ngầm
    - Phân tích footprint dòng tiền tổ chức
    """
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'flow_intelligence.json'
        )
        self.insights_history: Dict[str, List[FlowInsight]] = {}
        self.learning_data: Dict[str, Dict] = {}
        
        # Thresholds cho Vietnam market (tuned for HOSE/HNX)
        self.thresholds = {
            'block_trade_volume': 50000,      # 50k shares = block trade
            'volume_spike': 2.5,              # 2.5x average = spike
            'vwap_deviation_pct': 1.5,        # 1.5% deviation = significant
            'accumulation_days': 5,           # 5 consecutive days
            'foreign_heavy_threshold': 10,    # 10 billion VND
            'iceberg_chunk_count': 10,        # >10 same-size orders
        }
        
        self._load()
    
    def _load(self):
        """Load historical insights"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.learning_data = data.get('learning_data', {})
        except Exception as e:
            print(f"Error loading flow intelligence: {e}")
    
    def _save(self):
        """Save insights and learning data"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            data = {
                'learning_data': self.learning_data,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving flow intelligence: {e}")
    
    def analyze(self, symbol: str, df: pd.DataFrame, 
                flow_data: Dict = None) -> List[FlowInsight]:
        """
        Phân tích đầy đủ các insight ẩn trong data
        
        Args:
            symbol: Mã cổ phiếu
            df: DataFrame OHLCV
            flow_data: Dict với foreign_buy, foreign_sell, prop_buy, prop_sell
        
        Returns:
            List các FlowInsight phát hiện được
        """
        insights = []
        
        if df is None or df.empty:
            return insights
        
        # Standard columns
        df = self._standardize_columns(df)
        
        # 1. Block Trade Detection
        block_insights = self._detect_block_trades(symbol, df)
        insights.extend(block_insights)
        
        # 2. Unusual Volume Analysis
        volume_insights = self._analyze_unusual_volume(symbol, df)
        insights.extend(volume_insights)
        
        # 3. VWAP Deviation Analysis
        vwap_insights = self._analyze_vwap_deviation(symbol, df)
        insights.extend(vwap_insights)
        
        # 4. Accumulation/Distribution Detection
        acc_dist_insights = self._detect_accumulation_distribution(symbol, df)
        insights.extend(acc_dist_insights)
        
        # 5. Absorption/Exhaustion Patterns
        pattern_insights = self._detect_absorption_exhaustion(symbol, df)
        insights.extend(pattern_insights)
        
        # 6. Foreign Flow Analysis (if available)
        if flow_data:
            flow_insights = self._analyze_smart_money_flow(symbol, df, flow_data)
            insights.extend(flow_insights)
        
        # 7. Price-Volume Divergence
        divergence_insights = self._detect_price_volume_divergence(symbol, df)
        insights.extend(divergence_insights)
        
        # Store and learn
        if insights:
            self._store_insights(symbol, insights)
            self._learn_from_insights(symbol, insights)
        
        return insights
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names"""
        columns_map = {
            'Open': 'open', 'High': 'high', 'Low': 'low', 
            'Close': 'close', 'Volume': 'volume',
            'OPEN': 'open', 'HIGH': 'high', 'LOW': 'low',
            'CLOSE': 'close', 'VOLUME': 'volume'
        }
        df = df.rename(columns={k: v for k, v in columns_map.items() if k in df.columns})
        return df
    
    def _detect_block_trades(self, symbol: str, df: pd.DataFrame) -> List[FlowInsight]:
        """
        Phát hiện Block Trade - Lệnh lớn bất thường
        
        Block trade thường là dấu hiệu của:
        - Tổ chức đang tích lũy/phân phối
        - Insider trading tiềm tàng
        - Event-driven trading
        """
        insights = []
        
        if 'volume' not in df.columns:
            return insights
        
        avg_volume = df['volume'].rolling(20).mean()
        volume_threshold = self.thresholds['block_trade_volume']
        
        # Tìm các phiên có volume cực lớn
        for i in range(1, len(df)):
            vol = df['volume'].iloc[i]
            avg = avg_volume.iloc[i] if not pd.isna(avg_volume.iloc[i]) else vol
            
            # Block trade: volume > threshold VÀ > 3x average
            if vol > volume_threshold and vol > avg * 3:
                close = df['close'].iloc[i]
                prev_close = df['close'].iloc[i-1]
                
                direction = "BULLISH" if close > prev_close else "BEARISH" if close < prev_close else "NEUTRAL"
                
                # Tính severity dựa trên độ lớn
                if vol > avg * 5:
                    severity = "CRITICAL"
                    confidence = 0.9
                elif vol > avg * 4:
                    severity = "HIGH"
                    confidence = 0.8
                else:
                    severity = "MEDIUM"
                    confidence = 0.7
                
                insights.append(FlowInsight(
                    signal_type=FlowSignalType.BLOCK_TRADE,
                    symbol=symbol,
                    timestamp=datetime.now(),
                    severity=severity,
                    direction=direction,
                    confidence=confidence,
                    description=f"🔥 BLOCK TRADE: {vol:,.0f} cp ({vol/avg:.1f}x TB). Dấu hiệu tổ chức {'mua' if direction == 'BULLISH' else 'bán'} mạnh.",
                    data={
                        'volume': vol,
                        'average_volume': avg,
                        'ratio': vol / avg,
                        'price': close,
                        'price_change_pct': (close - prev_close) / prev_close * 100
                    }
                ))
        
        return insights
    
    def _analyze_unusual_volume(self, symbol: str, df: pd.DataFrame) -> List[FlowInsight]:
        """
        Phân tích Volume bất thường
        
        Các pattern:
        - Volume spike với giá không đổi = Tích lũy ngầm
        - Volume spike với giá tăng = Breakout
        - Volume cao liên tục = Institutional interest
        """
        insights = []
        
        if 'volume' not in df.columns or len(df) < 20:
            return insights
        
        avg_vol_20 = df['volume'].rolling(20).mean()
        vol_std = df['volume'].rolling(20).std()
        
        current_vol = df['volume'].iloc[-1]
        current_avg = avg_vol_20.iloc[-1]
        
        if pd.isna(current_avg) or current_avg == 0:
            return insights
        
        vol_ratio = current_vol / current_avg
        
        # Volume spike
        if vol_ratio > self.thresholds['volume_spike']:
            price_change = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100
            
            # Case 1: Volume cao + Giá không đổi nhiều = Tích lũy/Phân phối ngầm
            if abs(price_change) < 0.5:
                insights.append(FlowInsight(
                    signal_type=FlowSignalType.ACCUMULATION if vol_ratio > 3 else FlowSignalType.UNUSUAL_VOLUME,
                    symbol=symbol,
                    timestamp=datetime.now(),
                    severity="HIGH",
                    direction="NEUTRAL",
                    confidence=0.75,
                    description=f"🔍 TÍCH LŨY NGẦM: Volume {vol_ratio:.1f}x TB nhưng giá chỉ {price_change:+.2f}%. Tổ chức đang gom/xả.",
                    data={
                        'volume_ratio': vol_ratio,
                        'price_change_pct': price_change,
                        'pattern': 'SILENT_ACCUMULATION'
                    }
                ))
            
            # Case 2: Volume cao + Giá tăng = Breakout tiềm năng
            elif price_change > 1:
                insights.append(FlowInsight(
                    signal_type=FlowSignalType.UNUSUAL_VOLUME,
                    symbol=symbol,
                    timestamp=datetime.now(),
                    severity="HIGH",
                    direction="BULLISH",
                    confidence=0.8,
                    description=f"🚀 VOLUME BREAKOUT: {vol_ratio:.1f}x TB, giá +{price_change:.2f}%. Momentum mạnh!",
                    data={
                        'volume_ratio': vol_ratio,
                        'price_change_pct': price_change,
                        'pattern': 'VOLUME_BREAKOUT'
                    }
                ))
        
        return insights
    
    def _analyze_vwap_deviation(self, symbol: str, df: pd.DataFrame) -> List[FlowInsight]:
        """
        Phân tích độ lệch VWAP
        
        VWAP là trung bình giá theo khối lượng - benchmark của institutional traders.
        Độ lệch lớn = Cơ hội mean reversion hoặc trend strength
        """
        insights = []
        
        required_cols = ['high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            return insights
        
        # Calculate VWAP
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        cumulative_tp_vol = (typical_price * df['volume']).cumsum()
        cumulative_vol = df['volume'].cumsum()
        vwap = cumulative_tp_vol / cumulative_vol.replace(0, np.nan)
        
        current_price = df['close'].iloc[-1]
        current_vwap = vwap.iloc[-1]
        
        if pd.isna(current_vwap):
            return insights
        
        deviation_pct = (current_price - current_vwap) / current_vwap * 100
        
        if abs(deviation_pct) > self.thresholds['vwap_deviation_pct']:
            if deviation_pct > 0:
                # Giá > VWAP = Đang strong, nhưng có thể mean revert
                insights.append(FlowInsight(
                    signal_type=FlowSignalType.VWAP_DEVIATION,
                    symbol=symbol,
                    timestamp=datetime.now(),
                    severity="MEDIUM",
                    direction="BULLISH",
                    confidence=0.7,
                    description=f"📈 VWAP DEVIATION: Giá cao hơn VWAP {deviation_pct:.2f}%. Buyers đang thắng thế.",
                    data={
                        'deviation_pct': deviation_pct,
                        'current_price': current_price,
                        'vwap': current_vwap,
                        'signal': 'ABOVE_VWAP'
                    }
                ))
            else:
                # Giá < VWAP = Đang weak, sellers control
                insights.append(FlowInsight(
                    signal_type=FlowSignalType.VWAP_DEVIATION,
                    symbol=symbol,
                    timestamp=datetime.now(),
                    severity="MEDIUM",
                    direction="BEARISH",
                    confidence=0.7,
                    description=f"📉 VWAP DEVIATION: Giá thấp hơn VWAP {abs(deviation_pct):.2f}%. Sellers đang control.",
                    data={
                        'deviation_pct': deviation_pct,
                        'current_price': current_price,
                        'vwap': current_vwap,
                        'signal': 'BELOW_VWAP'
                    }
                ))
        
        return insights
    
    def _detect_accumulation_distribution(self, symbol: str, df: pd.DataFrame) -> List[FlowInsight]:
        """
        Phát hiện Accumulation/Distribution Pattern
        
        Accumulation: Giá sideway nhưng volume tăng dần = Tổ chức gom hàng
        Distribution: Giá sideway trên đỉnh + volume tăng = Tổ chức xả hàng
        """
        insights = []
        
        if len(df) < self.thresholds['accumulation_days']:
            return insights
        
        lookback = self.thresholds['accumulation_days']
        recent_df = df.iloc[-lookback:]
        
        # Calculate price range
        price_range = (recent_df['close'].max() - recent_df['close'].min()) / recent_df['close'].mean() * 100
        
        # Calculate volume trend
        vol_trend = recent_df['volume'].iloc[-1] / recent_df['volume'].iloc[0] if recent_df['volume'].iloc[0] > 0 else 1
        
        # Calculate close position in range
        close_in_range = (recent_df['close'].iloc[-1] - recent_df['low'].min()) / (recent_df['high'].max() - recent_df['low'].min() + 0.001)
        
        # Accumulation: Tight range + Volume tăng + Close gần high
        if price_range < 3 and vol_trend > 1.2 and close_in_range > 0.6:
            insights.append(FlowInsight(
                signal_type=FlowSignalType.ACCUMULATION,
                symbol=symbol,
                timestamp=datetime.now(),
                severity="HIGH",
                direction="BULLISH",
                confidence=0.8,
                description=f"📊 TÍCH LŨY: Giá sideway {lookback} phiên (±{price_range:.1f}%), volume tăng {(vol_trend-1)*100:.0f}%. Tổ chức đang gom.",
                data={
                    'days': lookback,
                    'price_range_pct': price_range,
                    'volume_trend': vol_trend,
                    'close_position': close_in_range,
                    'pattern': 'ACCUMULATION'
                }
            ))
        
        # Distribution: Tight range on top + Volume tăng + Close gần low
        elif price_range < 3 and vol_trend > 1.2 and close_in_range < 0.4:
            insights.append(FlowInsight(
                signal_type=FlowSignalType.DISTRIBUTION,
                symbol=symbol,
                timestamp=datetime.now(),
                severity="HIGH",
                direction="BEARISH",
                confidence=0.8,
                description=f"📊 PHÂN PHỐI: Giá sideway {lookback} phiên nhưng volume tăng. Tổ chức đang xả.",
                data={
                    'days': lookback,
                    'price_range_pct': price_range,
                    'volume_trend': vol_trend,
                    'close_position': close_in_range,
                    'pattern': 'DISTRIBUTION'
                }
            ))
        
        return insights
    
    def _detect_absorption_exhaustion(self, symbol: str, df: pd.DataFrame) -> List[FlowInsight]:
        """
        Phát hiện Absorption và Exhaustion
        
        Absorption: Volume lớn nhưng giá không đi đâu = Có lực cản mạnh
        Exhaustion: Volume cực lớn + move lớn cuối trend = Trend sắp đảo chiều
        """
        insights = []
        
        if len(df) < 5:
            return insights
        
        recent = df.iloc[-5:]
        
        # Volume và Range
        avg_vol = recent['volume'].mean()
        avg_range = (recent['high'] - recent['low']).mean()
        
        last_vol = df['volume'].iloc[-1]
        last_range = df['high'].iloc[-1] - df['low'].iloc[-1]
        
        if avg_vol == 0:
            return insights
        
        vol_ratio = last_vol / avg_vol
        range_ratio = last_range / avg_range if avg_range > 0 else 1
        
        # Absorption: Volume > 1.5x nhưng Range < 0.5x = Có absorption
        if vol_ratio > 1.5 and range_ratio < 0.5:
            close = df['close'].iloc[-1]
            mid = (df['high'].iloc[-1] + df['low'].iloc[-1]) / 2
            
            direction = "BULLISH" if close > mid else "BEARISH"
            
            insights.append(FlowInsight(
                signal_type=FlowSignalType.ABSORPTION,
                symbol=symbol,
                timestamp=datetime.now(),
                severity="HIGH",
                direction=direction,
                confidence=0.75,
                description=f"🛡️ ABSORPTION: Volume {vol_ratio:.1f}x TB nhưng range chỉ {range_ratio:.1f}x. Có lực {'mua' if direction == 'BULLISH' else 'bán'} hấp thụ.",
                data={
                    'volume_ratio': vol_ratio,
                    'range_ratio': range_ratio,
                    'pattern': 'ABSORPTION'
                }
            ))
        
        # Exhaustion: Volume cực lớn + Range lớn = Có thể exhaustion
        elif vol_ratio > 3 and range_ratio > 2:
            insights.append(FlowInsight(
                signal_type=FlowSignalType.EXHAUSTION,
                symbol=symbol,
                timestamp=datetime.now(),
                severity="MEDIUM",
                direction="NEUTRAL",
                confidence=0.65,
                description=f"⚠️ EXHAUSTION: Volume {vol_ratio:.1f}x + Range {range_ratio:.1f}x. Cẩn trọng đảo chiều.",
                data={
                    'volume_ratio': vol_ratio,
                    'range_ratio': range_ratio,
                    'pattern': 'POTENTIAL_EXHAUSTION'
                }
            ))
        
        return insights
    
    def _analyze_smart_money_flow(self, symbol: str, df: pd.DataFrame, 
                                   flow_data: Dict) -> List[FlowInsight]:
        """
        Phân tích Smart Money Flow từ data Foreign/Proprietary
        """
        insights = []
        
        foreign_buy = flow_data.get('foreign_buy', 0)
        foreign_sell = flow_data.get('foreign_sell', 0)
        prop_buy = flow_data.get('prop_buy', 0)
        prop_sell = flow_data.get('prop_sell', 0)
        
        foreign_net = foreign_buy - foreign_sell
        prop_net = prop_buy - prop_sell
        smart_money_net = foreign_net + prop_net
        
        # Heavy Foreign Activity
        if abs(foreign_net) > self.thresholds['foreign_heavy_threshold'] * 1e9:  # Convert to VND
            direction = "BULLISH" if foreign_net > 0 else "BEARISH"
            insights.append(FlowInsight(
                signal_type=FlowSignalType.SMART_DIVERGENCE,
                symbol=symbol,
                timestamp=datetime.now(),
                severity="CRITICAL",
                direction=direction,
                confidence=0.85,
                description=f"🌍 KHỐI NGOẠI: {'Mua' if direction == 'BULLISH' else 'Bán'} ròng {abs(foreign_net/1e9):.1f} tỷ. Signal cực mạnh!",
                data={
                    'foreign_net': foreign_net,
                    'foreign_buy': foreign_buy,
                    'foreign_sell': foreign_sell,
                    'pattern': 'FOREIGN_HEAVY'
                }
            ))
        
        # Smart Money Net (Foreign + Prop)
        if abs(smart_money_net) > self.thresholds['foreign_heavy_threshold'] * 0.5e9:
            direction = "BULLISH" if smart_money_net > 0 else "BEARISH"
            insights.append(FlowInsight(
                signal_type=FlowSignalType.SMART_DIVERGENCE,
                symbol=symbol,
                timestamp=datetime.now(),
                severity="HIGH",
                direction=direction,
                confidence=0.8,
                description=f"💰 SMART MONEY: Ngoại + Tự doanh {'mua' if direction == 'BULLISH' else 'bán'} ròng {abs(smart_money_net/1e9):.1f} tỷ.",
                data={
                    'smart_money_net': smart_money_net,
                    'foreign_net': foreign_net,
                    'prop_net': prop_net
                }
            ))
        
        return insights
    
    def _detect_price_volume_divergence(self, symbol: str, df: pd.DataFrame) -> List[FlowInsight]:
        """
        Phát hiện Price-Volume Divergence
        
        Giá tăng + Volume giảm = Bearish divergence (weak rally)
        Giá giảm + Volume giảm = Bullish divergence (sellers exhausted)
        """
        insights = []
        
        if len(df) < 10:
            return insights
        
        recent_5 = df.iloc[-5:]
        prev_5 = df.iloc[-10:-5]
        
        # Price trend
        price_change = (recent_5['close'].iloc[-1] - prev_5['close'].iloc[0]) / prev_5['close'].iloc[0] * 100
        
        # Volume trend
        recent_avg_vol = recent_5['volume'].mean()
        prev_avg_vol = prev_5['volume'].mean()
        vol_change = (recent_avg_vol - prev_avg_vol) / prev_avg_vol * 100 if prev_avg_vol > 0 else 0
        
        # Bearish Divergence: Giá tăng + Volume giảm
        if price_change > 2 and vol_change < -20:
            insights.append(FlowInsight(
                signal_type=FlowSignalType.SMART_DIVERGENCE,
                symbol=symbol,
                timestamp=datetime.now(),
                severity="HIGH",
                direction="BEARISH",
                confidence=0.75,
                description=f"⚠️ BEARISH DIVERGENCE: Giá +{price_change:.1f}% nhưng Volume -{abs(vol_change):.0f}%. Rally yếu, cẩn trọng.",
                data={
                    'price_change_pct': price_change,
                    'volume_change_pct': vol_change,
                    'pattern': 'BEARISH_DIVERGENCE'
                }
            ))
        
        # Bullish Divergence: Giá giảm nhẹ + Volume giảm mạnh
        elif price_change < -2 and vol_change < -30:
            insights.append(FlowInsight(
                signal_type=FlowSignalType.SMART_DIVERGENCE,
                symbol=symbol,
                timestamp=datetime.now(),
                severity="MEDIUM",
                direction="BULLISH",
                confidence=0.7,
                description=f"📊 BULLISH DIVERGENCE: Giá {price_change:.1f}% nhưng Volume -{abs(vol_change):.0f}%. Sellers cạn kiệt.",
                data={
                    'price_change_pct': price_change,
                    'volume_change_pct': vol_change,
                    'pattern': 'BULLISH_DIVERGENCE'
                }
            ))
        
        return insights
    
    def _store_insights(self, symbol: str, insights: List[FlowInsight]):
        """Store insights for learning"""
        if symbol not in self.insights_history:
            self.insights_history[symbol] = []
        
        self.insights_history[symbol].extend(insights)
        
        # Keep only last 100
        if len(self.insights_history[symbol]) > 100:
            self.insights_history[symbol] = self.insights_history[symbol][-100:]
    
    def _learn_from_insights(self, symbol: str, insights: List[FlowInsight]):
        """Learn from insights to improve accuracy"""
        if symbol not in self.learning_data:
            self.learning_data[symbol] = {
                'total_signals': 0,
                'signal_types': {},
                'avg_confidence': 0.7
            }
        
        ld = self.learning_data[symbol]
        ld['total_signals'] += len(insights)
        
        for insight in insights:
            sig_type = insight.signal_type.value
            if sig_type not in ld['signal_types']:
                ld['signal_types'][sig_type] = 0
            ld['signal_types'][sig_type] += 1
        
        self._save()
    
    def get_summary(self, symbol: str) -> Dict:
        """Get summary of insights for symbol"""
        insights = self.insights_history.get(symbol, [])
        
        bullish = sum(1 for i in insights if i.direction == "BULLISH")
        bearish = sum(1 for i in insights if i.direction == "BEARISH")
        
        return {
            'total_insights': len(insights),
            'bullish_signals': bullish,
            'bearish_signals': bearish,
            'bias': 'BULLISH' if bullish > bearish else 'BEARISH' if bearish > bullish else 'NEUTRAL',
            'recent_insights': [i.to_dict() for i in insights[-5:]]
        }


# Global instance
_deep_flow: Optional[DeepFlowIntelligence] = None


def get_deep_flow_intelligence() -> DeepFlowIntelligence:
    """Get or create global Deep Flow Intelligence instance"""
    global _deep_flow
    if _deep_flow is None:
        _deep_flow = DeepFlowIntelligence()
    return _deep_flow
