# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AUTO SCAN SCHEDULER                                       ║
║                    Automatic Signal Detection Every X Minutes                ║
╚══════════════════════════════════════════════════════════════════════════════╝

Features:
- Configurable scan intervals (5/15/30 minutes)
- Multi-symbol scanning
- Deep Flow Intelligence integration
- Memory-based learning
- Push notification support
"""

import threading
import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field
import pandas as pd
import json
import os


@dataclass
class ScanResult:
    """Result from a single stock scan"""
    symbol: str
    timestamp: datetime
    price: float
    change_pct: float
    signals: List[Dict]
    insights: List[Dict]
    recommendation: str  # BUY, SELL, HOLD, WATCH
    confidence: float
    summary: str
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'change_pct': self.change_pct,
            'signals': self.signals,
            'insights': self.insights,
            'recommendation': self.recommendation,
            'confidence': self.confidence,
            'summary': self.summary
        }


class AutoScanScheduler:
    """
    Auto Scan Scheduler - Quét tín hiệu tự động
    
    Features:
    - Quét mỗi 5/15/30 phút
    - Tích hợp Deep Flow Intelligence
    - Lưu lịch sử và học từ kết quả
    - Push notification qua callback
    """
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'scan_history.json'
        )
        
        self.is_running = False
        self.scan_interval_minutes = 15  # Default 15 minutes
        self.watchlist: List[str] = []
        self.last_scan_time: Optional[datetime] = None
        self.scan_history: List[ScanResult] = []
        self.callbacks: List[Callable[[List[ScanResult]], None]] = []
        
        # Scheduler thread
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Learning data
        self.learning_stats = {
            'total_scans': 0,
            'signals_generated': 0,
            'accuracy_tracking': {}
        }
        
        self._load_history()
    
    def _load_history(self):
        """Load scan history from file"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.learning_stats = data.get('learning_stats', self.learning_stats)
                    self.watchlist = data.get('watchlist', [])
        except Exception as e:
            print(f"Error loading scan history: {e}")
    
    def _save_history(self):
        """Save scan history to file"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            data = {
                'learning_stats': self.learning_stats,
                'watchlist': self.watchlist,
                'last_scan': self.last_scan_time.isoformat() if self.last_scan_time else None,
                'scan_history': [r.to_dict() for r in self.scan_history[-100:]]  # Keep last 100
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving scan history: {e}")
    
    def set_interval(self, minutes: int):
        """Set scan interval (5, 15, or 30 minutes)"""
        if minutes in [1, 5, 15, 30, 60]:
            self.scan_interval_minutes = minutes
            print(f"✅ Scan interval set to {minutes} minutes")
            
            # Restart scheduler if running
            if self.is_running:
                self.stop()
                self.start()
        else:
            print(f"⚠️ Invalid interval. Use 1, 5, 15, 30, or 60 minutes.")
    
    def set_watchlist(self, symbols: List[str]):
        """Set list of symbols to scan"""
        self.watchlist = [s.upper().strip() for s in symbols]
        self._save_history()
        print(f"✅ Watchlist updated: {len(self.watchlist)} symbols")
    
    def add_callback(self, callback: Callable[[List[ScanResult]], None]):
        """Add callback to be called when scan completes"""
        self.callbacks.append(callback)
    
    def start(self):
        """Start the auto-scan scheduler"""
        if self.is_running:
            print("⚠️ Scheduler already running")
            return
        
        if not self.watchlist:
            print("⚠️ Watchlist is empty. Add symbols first.")
            return
        
        self.is_running = True
        self._stop_event.clear()
        
        # Start scheduler thread
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        
        print(f"🚀 Auto-scan started: Every {self.scan_interval_minutes} minutes")
        print(f"📋 Watching: {', '.join(self.watchlist[:10])}{'...' if len(self.watchlist) > 10 else ''}")
    
    def stop(self):
        """Stop the auto-scan scheduler"""
        if not self.is_running:
            print("⚠️ Scheduler not running")
            return
        
        self.is_running = False
        self._stop_event.set()
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        
        print("🛑 Auto-scan stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        # Run first scan immediately
        self._perform_scan()
        
        # Then run at intervals
        while not self._stop_event.is_set():
            time.sleep(60)  # Check every minute
            
            if self._stop_event.is_set():
                break
            
            minutes_since_last = 999
            if self.last_scan_time:
                minutes_since_last = (datetime.now() - self.last_scan_time).total_seconds() / 60
            
            if minutes_since_last >= self.scan_interval_minutes:
                self._perform_scan()
    
    def _perform_scan(self):
        """Perform a full scan of all watchlist symbols"""
        self.last_scan_time = datetime.now()
        self.learning_stats['total_scans'] += 1
        
        print(f"\n{'='*60}")
        print(f"🔍 AUTO SCAN: {self.last_scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        results: List[ScanResult] = []
        
        for symbol in self.watchlist:
            try:
                result = self._scan_symbol(symbol)
                if result:
                    results.append(result)
                    
                    # Log important signals
                    if result.confidence > 0.7:
                        print(f"🔥 {symbol}: {result.recommendation} ({result.confidence:.0%}) - {result.summary}")
                    elif result.insights:
                        print(f"📊 {symbol}: {len(result.insights)} insights detected")
                
            except Exception as e:
                print(f"❌ Error scanning {symbol}: {e}")
        
        # Store results
        self.scan_history.extend(results)
        if len(self.scan_history) > 500:
            self.scan_history = self.scan_history[-500:]
        
        self._save_history()
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(results)
            except Exception as e:
                print(f"❌ Callback error: {e}")
        
        # Summary
        signals_count = sum(len(r.signals) for r in results)
        insights_count = sum(len(r.insights) for r in results)
        self.learning_stats['signals_generated'] += signals_count
        
        print(f"\n📈 Scan Complete: {len(results)} stocks, {signals_count} signals, {insights_count} insights")
        print(f"⏰ Next scan in {self.scan_interval_minutes} minutes")
        
        return results
    
    def _scan_symbol(self, symbol: str) -> Optional[ScanResult]:
        """Scan a single symbol"""
        try:
            # Fetch data
            df = self._fetch_data(symbol)
            if df is None or df.empty:
                return None
            
            # Calculate indicators
            indicators = self._calculate_indicators(df)
            
            # Get Deep Flow Intelligence
            from .deep_flow_intelligence import get_deep_flow_intelligence
            dfi = get_deep_flow_intelligence()
            insights = dfi.analyze(symbol, df)
            
            # Generate signals
            signals = self._generate_signals(indicators)
            
            # Determine recommendation
            recommendation, confidence = self._determine_recommendation(signals, insights)
            
            # Generate summary
            summary = self._generate_summary(symbol, indicators, signals, insights)
            
            return ScanResult(
                symbol=symbol,
                timestamp=datetime.now(),
                price=indicators.get('price', 0),
                change_pct=indicators.get('change_pct', 0),
                signals=signals,
                insights=[i.to_dict() for i in insights],
                recommendation=recommendation,
                confidence=confidence,
                summary=summary
            )
            
        except Exception as e:
            print(f"Error in _scan_symbol({symbol}): {e}")
            return None
    
    def _fetch_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch stock data"""
        try:
            from vnstock import Vnstock
            
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            
            df = stock.quote.history(start=start_date, end=end_date)
            
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]
                return df
                
        except Exception as e:
            pass
        
        return None
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators"""
        close = df['close'].values
        high = df['high'].values if 'high' in df.columns else close
        low = df['low'].values if 'low' in df.columns else close
        volume = df['volume'].values if 'volume' in df.columns else [0] * len(close)
        
        # Current values
        current_price = close[-1]
        prev_price = close[-2] if len(close) > 1 else current_price
        change_pct = (current_price - prev_price) / prev_price * 100
        
        # RSI
        delta = pd.Series(close).diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        
        # MACD
        exp1 = pd.Series(close).ewm(span=12).mean()
        exp2 = pd.Series(close).ewm(span=26).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9).mean()
        current_macd = macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0
        current_signal = signal.iloc[-1] if not pd.isna(signal.iloc[-1]) else 0
        
        # Volume
        avg_volume = pd.Series(volume).rolling(20).mean().iloc[-1]
        volume_ratio = volume[-1] / avg_volume if avg_volume > 0 else 1
        
        # Trend
        sma20 = pd.Series(close).rolling(20).mean().iloc[-1]
        sma50 = pd.Series(close).rolling(50).mean().iloc[-1]
        
        if current_price > sma20 > sma50:
            trend = "UPTREND"
        elif current_price < sma20 < sma50:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"
        
        return {
            'price': current_price,
            'change_pct': change_pct,
            'rsi': current_rsi,
            'macd': current_macd,
            'macd_signal': current_signal,
            'macd_hist': current_macd - current_signal,
            'sma20': sma20,
            'sma50': sma50,
            'volume': volume[-1],
            'volume_ratio': volume_ratio,
            'trend': trend
        }
    
    def _generate_signals(self, indicators: Dict) -> List[Dict]:
        """Generate trading signals from indicators"""
        signals = []
        
        rsi = indicators.get('rsi', 50)
        macd_hist = indicators.get('macd_hist', 0)
        trend = indicators.get('trend', 'SIDEWAYS')
        volume_ratio = indicators.get('volume_ratio', 1)
        
        # RSI Signal
        if rsi < 30:
            signals.append({
                'type': 'RSI_OVERSOLD',
                'direction': 'BULLISH',
                'strength': (30 - rsi) / 30,
                'description': f'RSI {rsi:.1f} - Oversold zone'
            })
        elif rsi > 70:
            signals.append({
                'type': 'RSI_OVERBOUGHT',
                'direction': 'BEARISH',
                'strength': (rsi - 70) / 30,
                'description': f'RSI {rsi:.1f} - Overbought zone'
            })
        
        # MACD Signal
        if macd_hist > 0 and indicators.get('macd', 0) > indicators.get('macd_signal', 0):
            signals.append({
                'type': 'MACD_BULLISH',
                'direction': 'BULLISH',
                'strength': min(abs(macd_hist) * 10, 1),
                'description': 'MACD bullish crossover'
            })
        elif macd_hist < 0:
            signals.append({
                'type': 'MACD_BEARISH',
                'direction': 'BEARISH',
                'strength': min(abs(macd_hist) * 10, 1),
                'description': 'MACD bearish'
            })
        
        # Volume Signal
        if volume_ratio > 2:
            signals.append({
                'type': 'VOLUME_SPIKE',
                'direction': 'NEUTRAL',
                'strength': min((volume_ratio - 1) / 3, 1),
                'description': f'Volume {volume_ratio:.1f}x average'
            })
        
        return signals
    
    def _determine_recommendation(self, signals: List[Dict], insights: List) -> tuple:
        """Determine overall recommendation"""
        bullish_score = 0
        bearish_score = 0
        
        # Score from signals
        for sig in signals:
            if sig['direction'] == 'BULLISH':
                bullish_score += sig['strength']
            elif sig['direction'] == 'BEARISH':
                bearish_score += sig['strength']
        
        # Score from insights
        for insight in insights:
            if insight.direction == 'BULLISH':
                bullish_score += insight.confidence
            elif insight.direction == 'BEARISH':
                bearish_score += insight.confidence
        
        total = bullish_score + bearish_score
        if total == 0:
            return 'HOLD', 0.5
        
        if bullish_score > bearish_score * 1.5:
            confidence = bullish_score / (total + 1)
            return 'BUY', min(confidence, 0.95)
        elif bearish_score > bullish_score * 1.5:
            confidence = bearish_score / (total + 1)
            return 'SELL', min(confidence, 0.95)
        elif total > 1:
            return 'WATCH', 0.6
        else:
            return 'HOLD', 0.5
    
    def _generate_summary(self, symbol: str, indicators: Dict, 
                          signals: List[Dict], insights: List) -> str:
        """Generate human-readable summary"""
        parts = []
        
        # Price info
        price = indicators.get('price', 0)
        change = indicators.get('change_pct', 0)
        parts.append(f"{price:,.0f}đ ({change:+.2f}%)")
        
        # Key indicator
        rsi = indicators.get('rsi', 50)
        trend = indicators.get('trend', 'N/A')
        parts.append(f"RSI:{rsi:.0f} {trend}")
        
        # Insights summary
        if insights:
            insight_types = [i.signal_type.value for i in insights[:2]]
            parts.append(f"[{','.join(insight_types)}]")
        
        return " | ".join(parts)
    
    def get_status(self) -> Dict:
        """Get current scheduler status"""
        return {
            'is_running': self.is_running,
            'interval_minutes': self.scan_interval_minutes,
            'watchlist_count': len(self.watchlist),
            'last_scan': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'total_scans': self.learning_stats['total_scans'],
            'signals_generated': self.learning_stats['signals_generated']
        }
    
    def manual_scan(self) -> List[ScanResult]:
        """Perform manual scan immediately"""
        return self._perform_scan()


# Global instance
_auto_scanner: Optional[AutoScanScheduler] = None


def get_auto_scanner() -> AutoScanScheduler:
    """Get or create global Auto Scanner instance"""
    global _auto_scanner
    if _auto_scanner is None:
        _auto_scanner = AutoScanScheduler()
    return _auto_scanner
