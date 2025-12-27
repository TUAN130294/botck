"""
Market Regime Detector - Level 4 Agentic Architecture
Automatically detects market conditions and adapts strategies
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from datetime import datetime
import pandas as pd
import numpy as np


class MarketRegime(Enum):
    """Market regime classifications"""
    STRONG_BULL = "STRONG_BULL"       # Strong uptrend
    BULL = "BULL"                     # Moderate uptrend
    SIDEWAYS = "SIDEWAYS"             # Range-bound
    BEAR = "BEAR"                     # Moderate downtrend
    STRONG_BEAR = "STRONG_BEAR"       # Strong downtrend
    HIGH_VOLATILITY = "HIGH_VOLATILITY"  # High volatility (direction unclear)
    RECOVERY = "RECOVERY"             # Recovering from bear
    DISTRIBUTION = "DISTRIBUTION"     # Potential top formation


class VolatilityRegime(Enum):
    """Volatility regime classifications"""
    LOW = "LOW"           # < 15% annualized
    NORMAL = "NORMAL"     # 15-25% annualized
    HIGH = "HIGH"         # 25-40% annualized
    EXTREME = "EXTREME"   # > 40% annualized


class LiquidityRegime(Enum):
    """Liquidity regime classifications"""
    HIGH = "HIGH"         # High volume, tight spreads
    NORMAL = "NORMAL"     # Normal trading conditions
    LOW = "LOW"           # Low volume, wide spreads
    CRISIS = "CRISIS"     # Liquidity crisis


@dataclass
class RegimeState:
    """Current market regime state"""
    market_regime: MarketRegime
    volatility_regime: VolatilityRegime
    liquidity_regime: LiquidityRegime
    confidence: float
    timestamp: datetime
    indicators: Dict[str, Any]
    recommended_strategies: List[str]
    risk_adjustment: float  # 0.5 = half risk, 2.0 = double risk
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'market_regime': self.market_regime.value,
            'volatility_regime': self.volatility_regime.value,
            'liquidity_regime': self.liquidity_regime.value,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'indicators': self.indicators,
            'recommended_strategies': self.recommended_strategies,
            'risk_adjustment': self.risk_adjustment
        }


class MarketRegimeDetector:
    """
    Detects current market regime to adapt trading strategies.
    Key component of Level 4 Agentic Architecture.
    """
    
    # Vietnam-specific parameters
    VN_CEILING_PCT = 7.0   # HOSE ceiling
    VN_FLOOR_PCT = -7.0    # HOSE floor
    
    # Strategy mapping for each regime
    REGIME_STRATEGIES = {
        MarketRegime.STRONG_BULL: ['MOMENTUM', 'BREAKOUT', 'MA_CROSSOVER'],
        MarketRegime.BULL: ['TREND_FOLLOWING', 'MA_CROSSOVER', 'RSI_PULLBACK'],
        MarketRegime.SIDEWAYS: ['MEAN_REVERSION', 'BOLLINGER_BOUNCE', 'RSI_REVERSAL'],
        MarketRegime.BEAR: ['SHORT_TERM_BOUND', 'DEFENSIVE', 'CASH'],
        MarketRegime.STRONG_BEAR: ['CASH', 'DEFENSIVE', 'INVERSE'],
        MarketRegime.HIGH_VOLATILITY: ['VOLATILITY_BREAKOUT', 'STRADDLE'],
        MarketRegime.RECOVERY: ['EARLY_MOMENTUM', 'VALUE', 'RSI_OVERSOLD'],
        MarketRegime.DISTRIBUTION: ['DEFENSIVE', 'REDUCE_EXPOSURE', 'TIGHT_STOPS']
    }
    
    # Risk adjustment by regime
    RISK_ADJUSTMENT = {
        MarketRegime.STRONG_BULL: 1.2,
        MarketRegime.BULL: 1.0,
        MarketRegime.SIDEWAYS: 0.8,
        MarketRegime.BEAR: 0.5,
        MarketRegime.STRONG_BEAR: 0.3,
        MarketRegime.HIGH_VOLATILITY: 0.6,
        MarketRegime.RECOVERY: 0.7,
        MarketRegime.DISTRIBUTION: 0.6
    }
    
    def __init__(self):
        self.current_state: Optional[RegimeState] = None
        self.history: List[RegimeState] = []
    
    def detect(self, df: pd.DataFrame, 
               vn_index_df: pd.DataFrame = None) -> RegimeState:
        """
        Detect current market regime from price data.
        
        Args:
            df: Stock OHLCV data
            vn_index_df: VN-Index data for market context
            
        Returns:
            RegimeState with detected regime and recommendations
        """
        if len(df) < 50:
            return self._default_state()
        
        # Calculate all regime indicators
        indicators = self._calculate_indicators(df)
        
        # Add VN-Index context if available
        if vn_index_df is not None and len(vn_index_df) >= 20:
            indicators.update(self._calculate_market_context(vn_index_df))
        
        # Detect individual regimes
        market_regime, market_conf = self._detect_market_regime(indicators)
        volatility_regime = self._detect_volatility_regime(indicators)
        liquidity_regime = self._detect_liquidity_regime(df, indicators)
        
        # Get recommended strategies
        strategies = self.REGIME_STRATEGIES.get(
            market_regime, 
            ['MA_CROSSOVER', 'RSI_REVERSAL']
        )
        
        # Calculate risk adjustment
        risk_adj = self.RISK_ADJUSTMENT.get(market_regime, 1.0)
        
        # Adjust for volatility
        if volatility_regime == VolatilityRegime.HIGH:
            risk_adj *= 0.8
        elif volatility_regime == VolatilityRegime.EXTREME:
            risk_adj *= 0.5
        
        # Adjust for liquidity
        if liquidity_regime == LiquidityRegime.LOW:
            risk_adj *= 0.9
        elif liquidity_regime == LiquidityRegime.CRISIS:
            risk_adj *= 0.5
        
        state = RegimeState(
            market_regime=market_regime,
            volatility_regime=volatility_regime,
            liquidity_regime=liquidity_regime,
            confidence=market_conf,
            timestamp=datetime.now(),
            indicators=indicators,
            recommended_strategies=strategies,
            risk_adjustment=round(risk_adj, 2)
        )
        
        self.current_state = state
        self.history.append(state)
        
        # Keep history manageable
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        return state
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all indicators needed for regime detection"""
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        indicators = {}
        
        # Trend indicators
        sma_20 = pd.Series(close).rolling(20).mean().iloc[-1]
        sma_50 = pd.Series(close).rolling(50).mean().iloc[-1]
        sma_200 = pd.Series(close).rolling(200).mean().iloc[-1] if len(close) >= 200 else sma_50
        
        current_price = close[-1]
        
        indicators['price'] = current_price
        indicators['sma_20'] = sma_20
        indicators['sma_50'] = sma_50
        indicators['sma_200'] = sma_200
        
        # MA alignment score (-100 to 100)
        ma_score = 0
        if current_price > sma_20:
            ma_score += 25
        if current_price > sma_50:
            ma_score += 25
        if current_price > sma_200:
            ma_score += 25
        if sma_20 > sma_50:
            ma_score += 12.5
        if sma_50 > sma_200:
            ma_score += 12.5
        indicators['ma_score'] = ma_score
        
        # Trend strength (ADX approximation)
        tr = np.maximum(high - low, 
                        np.maximum(np.abs(high - np.roll(close, 1)),
                                  np.abs(low - np.roll(close, 1))))
        atr = pd.Series(tr).rolling(14).mean().iloc[-1]
        indicators['atr'] = atr
        indicators['atr_pct'] = (atr / current_price) * 100
        
        # Momentum (ROC)
        roc_20 = ((current_price / close[-21]) - 1) * 100 if len(close) > 20 else 0
        roc_50 = ((current_price / close[-51]) - 1) * 100 if len(close) > 50 else 0
        indicators['roc_20'] = roc_20
        indicators['roc_50'] = roc_50
        
        # RSI
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(14).mean().iloc[-1]
        avg_loss = pd.Series(loss).rolling(14).mean().iloc[-1]
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi = 100 - (100 / (1 + rs))
        indicators['rsi'] = rsi
        
        # Volatility (annualized)
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:]) * np.sqrt(252) * 100
        indicators['volatility'] = volatility
        
        # Historical volatility comparison
        short_vol = np.std(returns[-10:]) * np.sqrt(252) * 100 if len(returns) >= 10 else volatility
        long_vol = np.std(returns[-60:]) * np.sqrt(252) * 100 if len(returns) >= 60 else volatility
        indicators['vol_ratio'] = short_vol / long_vol if long_vol > 0 else 1.0
        
        # Volume analysis
        avg_volume = pd.Series(volume).rolling(20).mean().iloc[-1]
        indicators['avg_volume'] = avg_volume
        indicators['volume_ratio'] = volume[-1] / avg_volume if avg_volume > 0 else 1.0
        
        # Drawdown from peak
        rolling_max = pd.Series(close).rolling(252).max()
        drawdown = ((close - rolling_max.values) / rolling_max.values * 100)
        indicators['current_drawdown'] = drawdown[-1] if not np.isnan(drawdown[-1]) else 0
        indicators['max_drawdown_30d'] = np.min(drawdown[-30:]) if len(drawdown) >= 30 else drawdown[-1]
        
        # Breadth (if available from VN30)
        # Higher highs / lower lows ratio
        hh = sum(1 for i in range(-20, 0) 
                 if i + 1 < len(high) and high[i] > high[i-1])
        ll = sum(1 for i in range(-20, 0) 
                 if i + 1 < len(low) and low[i] < low[i-1])
        indicators['hh_ll_ratio'] = hh / (ll + 1)
        
        return indicators
    
    def _calculate_market_context(self, vn_index_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate VN-Index context indicators"""
        close = vn_index_df['close'].values
        
        return {
            'vn_index': close[-1],
            'vn_index_sma_20': pd.Series(close).rolling(20).mean().iloc[-1],
            'vn_index_roc_20': ((close[-1] / close[-21]) - 1) * 100 if len(close) > 20 else 0
        }
    
    def _detect_market_regime(self, indicators: Dict[str, Any]) -> Tuple[MarketRegime, float]:
        """Detect market regime from indicators"""
        ma_score = indicators.get('ma_score', 50)
        roc_20 = indicators.get('roc_20', 0)
        roc_50 = indicators.get('roc_50', 0)
        rsi = indicators.get('rsi', 50)
        volatility = indicators.get('volatility', 25)
        drawdown = indicators.get('current_drawdown', 0)
        vol_ratio = indicators.get('vol_ratio', 1.0)
        
        confidence = 0.7  # Base confidence
        
        # Strong Bull: Everything aligned up
        if ma_score >= 90 and roc_20 > 5 and rsi > 55:
            return MarketRegime.STRONG_BULL, min(0.95, confidence + 0.2)
        
        # Strong Bear: Everything aligned down
        if ma_score <= 25 and roc_20 < -5 and rsi < 40:
            return MarketRegime.STRONG_BEAR, min(0.95, confidence + 0.2)
        
        # High Volatility: Large vol ratio, unclear direction
        if vol_ratio > 1.5 and volatility > 35:
            return MarketRegime.HIGH_VOLATILITY, confidence
        
        # Bull market
        if ma_score >= 60 and roc_20 > 0:
            return MarketRegime.BULL, confidence + 0.1
        
        # Bear market
        if ma_score <= 40 and roc_20 < 0:
            return MarketRegime.BEAR, confidence + 0.1
        
        # Recovery: Coming off lows with momentum
        if drawdown < -15 and roc_20 > 3 and rsi > 40:
            return MarketRegime.RECOVERY, confidence
        
        # Distribution: At highs with weakening
        if drawdown > -5 and roc_20 < roc_50 and rsi > 65:
            return MarketRegime.DISTRIBUTION, confidence - 0.1
        
        # Default: Sideways
        return MarketRegime.SIDEWAYS, confidence - 0.1
    
    def _detect_volatility_regime(self, indicators: Dict[str, Any]) -> VolatilityRegime:
        """Detect volatility regime"""
        volatility = indicators.get('volatility', 25)
        
        if volatility < 15:
            return VolatilityRegime.LOW
        elif volatility < 25:
            return VolatilityRegime.NORMAL
        elif volatility < 40:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME
    
    def _detect_liquidity_regime(self, df: pd.DataFrame, 
                                  indicators: Dict[str, Any]) -> LiquidityRegime:
        """Detect liquidity regime"""
        volume_ratio = indicators.get('volume_ratio', 1.0)
        
        # Check for very low volume
        if volume_ratio < 0.3:
            return LiquidityRegime.CRISIS
        elif volume_ratio < 0.7:
            return LiquidityRegime.LOW
        elif volume_ratio > 1.5:
            return LiquidityRegime.HIGH
        else:
            return LiquidityRegime.NORMAL
    
    def _default_state(self) -> RegimeState:
        """Return default state when insufficient data"""
        return RegimeState(
            market_regime=MarketRegime.SIDEWAYS,
            volatility_regime=VolatilityRegime.NORMAL,
            liquidity_regime=LiquidityRegime.NORMAL,
            confidence=0.3,
            timestamp=datetime.now(),
            indicators={},
            recommended_strategies=['MA_CROSSOVER', 'RSI_REVERSAL'],
            risk_adjustment=0.8
        )
    
    def get_regime_summary(self) -> str:
        """Get human-readable regime summary"""
        if not self.current_state:
            return "No regime detected yet."
        
        state = self.current_state
        
        summary = f"""
📊 **Market Regime Analysis**

🎯 **Current Regime**: {state.market_regime.value}
📈 **Confidence**: {state.confidence:.1%}

📉 **Conditions**:
- Volatility: {state.volatility_regime.value}
- Liquidity: {state.liquidity_regime.value}

💡 **Recommended Strategies**:
{', '.join(state.recommended_strategies)}

⚠️ **Risk Adjustment**: {state.risk_adjustment}x normal
"""
        return summary.strip()
    
    def should_trade(self) -> Tuple[bool, str]:
        """Check if current conditions are favorable for trading"""
        if not self.current_state:
            return True, "No regime detected, proceeding with caution"
        
        state = self.current_state
        
        # Don't trade in extreme conditions
        if state.market_regime == MarketRegime.STRONG_BEAR:
            return False, "Strong bear market - avoid new longs"
        
        if state.volatility_regime == VolatilityRegime.EXTREME:
            return False, "Extreme volatility - wait for stabilization"
        
        if state.liquidity_regime == LiquidityRegime.CRISIS:
            return False, "Liquidity crisis - execution risk too high"
        
        return True, f"Regime {state.market_regime.value} - trading allowed"
