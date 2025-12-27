# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    AGENT PERFORMANCE TRACKER                                 ║
║                    Track, Analyze, and Adapt Agent Weights                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

P1 Implementation - Track and optimize agent performance
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import numpy as np
import pandas as pd
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================
# DATA MODELS
# ============================================

@dataclass
class AgentSignal:
    """Record of an agent's signal"""
    agent_name: str
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float
    timestamp: datetime
    price_at_signal: float
    reasoning: str = ""
    metadata: Dict = field(default_factory=dict)


@dataclass
class SignalOutcome:
    """Outcome of a signal after evaluation period"""
    signal_id: str
    agent_name: str
    symbol: str
    action: str
    entry_price: float
    exit_price: float
    return_pct: float
    holding_period_days: int
    was_correct: bool
    timestamp: datetime


@dataclass
class AgentMetrics:
    """Agent performance metrics"""
    agent_name: str
    total_signals: int = 0
    correct_signals: int = 0
    total_return: float = 0.0
    avg_confidence: float = 0.0
    accuracy: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_return_per_signal: float = 0.0
    profit_factor: float = 0.0
    consistency_score: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['last_updated'] = self.last_updated.isoformat()
        return d


# ============================================
# PERFORMANCE TRACKER
# ============================================

class AgentPerformanceTracker:
    """
    Track and analyze agent performance over time
    
    Features:
    - Signal recording
    - Outcome evaluation
    - Performance metrics
    - Historical analysis
    - A/B testing support
    """
    
    def __init__(self, storage_path: str = "agent_performance"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        self.signals: List[AgentSignal] = []
        self.outcomes: List[SignalOutcome] = []
        self.metrics: Dict[str, AgentMetrics] = {}
        
        # Load existing data
        self._load_data()
    
    def record_signal(self, agent_name: str, symbol: str, action: str,
                      confidence: float, price: float, reasoning: str = "",
                      metadata: Dict = None) -> str:
        """
        Record a new agent signal
        
        Returns: signal_id for tracking outcome
        """
        signal_id = f"{agent_name}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        signal = AgentSignal(
            agent_name=agent_name,
            symbol=symbol,
            action=action.upper(),
            confidence=confidence,
            timestamp=datetime.now(),
            price_at_signal=price,
            reasoning=reasoning,
            metadata={**(metadata or {}), 'signal_id': signal_id}
        )
        
        self.signals.append(signal)
        self._save_signals()
        
        logger.info(f"Recorded signal: {agent_name} {action} {symbol} @ {price}")
        return signal_id
    
    def record_outcome(self, signal_id: str, exit_price: float,
                       holding_days: int = 5) -> SignalOutcome:
        """
        Record the outcome of a signal
        """
        # Find the original signal
        signal = None
        for s in self.signals:
            if s.metadata.get('signal_id') == signal_id:
                signal = s
                break
        
        if not signal:
            raise ValueError(f"Signal not found: {signal_id}")
        
        # Calculate return
        if signal.action == 'BUY':
            return_pct = (exit_price - signal.price_at_signal) / signal.price_at_signal
        elif signal.action == 'SELL':
            return_pct = (signal.price_at_signal - exit_price) / signal.price_at_signal
        else:  # HOLD
            return_pct = 0
        
        was_correct = return_pct > 0
        
        outcome = SignalOutcome(
            signal_id=signal_id,
            agent_name=signal.agent_name,
            symbol=signal.symbol,
            action=signal.action,
            entry_price=signal.price_at_signal,
            exit_price=exit_price,
            return_pct=return_pct,
            holding_period_days=holding_days,
            was_correct=was_correct,
            timestamp=datetime.now()
        )
        
        self.outcomes.append(outcome)
        self._update_metrics(signal.agent_name)
        self._save_outcomes()
        
        logger.info(f"Recorded outcome: {signal.agent_name} {signal.symbol} "
                   f"{'✅' if was_correct else '❌'} {return_pct:.2%}")
        
        return outcome
    
    def _update_metrics(self, agent_name: str):
        """Update metrics for an agent"""
        agent_outcomes = [o for o in self.outcomes if o.agent_name == agent_name]
        agent_signals = [s for s in self.signals if s.agent_name == agent_name]
        
        if not agent_outcomes:
            return
        
        returns = [o.return_pct for o in agent_outcomes]
        correct = sum(1 for o in agent_outcomes if o.was_correct)
        confidences = [s.confidence for s in agent_signals]
        
        # Calculate metrics
        winning_returns = [r for r in returns if r > 0]
        losing_returns = [abs(r) for r in returns if r < 0]
        
        # Sharpe ratio (annualized)
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0
        
        # Profit factor
        if sum(losing_returns) > 0:
            profit_factor = sum(winning_returns) / sum(losing_returns)
        else:
            profit_factor = float('inf') if sum(winning_returns) > 0 else 0
        
        # Max drawdown (simplified)
        cumulative = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = cumulative - peak
        max_dd = abs(min(drawdown)) if len(drawdown) > 0 else 0
        
        # Consistency score (rolling accuracy stability)
        if len(agent_outcomes) >= 10:
            rolling_accuracy = []
            for i in range(10, len(agent_outcomes) + 1):
                window = agent_outcomes[max(0, i-10):i]
                acc = sum(1 for o in window if o.was_correct) / len(window)
                rolling_accuracy.append(acc)
            consistency = 1 - np.std(rolling_accuracy) if rolling_accuracy else 0
        else:
            consistency = 0
        
        self.metrics[agent_name] = AgentMetrics(
            agent_name=agent_name,
            total_signals=len(agent_outcomes),
            correct_signals=correct,
            total_return=sum(returns),
            avg_confidence=np.mean(confidences) if confidences else 0,
            accuracy=correct / len(agent_outcomes) if agent_outcomes else 0,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=correct / len(agent_outcomes) if agent_outcomes else 0,
            avg_return_per_signal=np.mean(returns) if returns else 0,
            profit_factor=min(profit_factor, 10),  # Cap at 10
            consistency_score=consistency,
            last_updated=datetime.now()
        )
        
        self._save_metrics()
    
    def get_metrics(self, agent_name: str = None) -> Dict[str, AgentMetrics]:
        """Get metrics for agent(s)"""
        if agent_name:
            return {agent_name: self.metrics.get(agent_name, AgentMetrics(agent_name=agent_name))}
        return self.metrics
    
    def get_leaderboard(self) -> pd.DataFrame:
        """Get agent leaderboard sorted by performance"""
        if not self.metrics:
            return pd.DataFrame()
        
        data = []
        for name, m in self.metrics.items():
            data.append({
                'Agent': name,
                'Signals': m.total_signals,
                'Win Rate': f"{m.win_rate:.1%}",
                'Total Return': f"{m.total_return:.2%}",
                'Sharpe': f"{m.sharpe_ratio:.2f}",
                'Max DD': f"{m.max_drawdown:.2%}",
                'Profit Factor': f"{m.profit_factor:.2f}",
                'Consistency': f"{m.consistency_score:.2f}",
                'Score': self._calculate_composite_score(m)
            })
        
        df = pd.DataFrame(data)
        return df.sort_values('Score', ascending=False)
    
    def _calculate_composite_score(self, m: AgentMetrics) -> float:
        """Calculate composite performance score (0-100)"""
        # Weighted scoring
        score = 0
        score += m.win_rate * 25  # 25% weight
        score += min(m.sharpe_ratio, 3) / 3 * 25  # 25% weight (capped at 3)
        score += min(m.profit_factor, 5) / 5 * 20  # 20% weight (capped at 5)
        score += m.consistency_score * 15  # 15% weight
        score += max(0, 1 - m.max_drawdown) * 15  # 15% weight
        
        return round(score, 2)
    
    def compare_agents(self, agent1: str, agent2: str, 
                      symbol: str = None) -> Dict:
        """Compare two agents head-to-head"""
        outcomes1 = [o for o in self.outcomes if o.agent_name == agent1]
        outcomes2 = [o for o in self.outcomes if o.agent_name == agent2]
        
        if symbol:
            outcomes1 = [o for o in outcomes1 if o.symbol == symbol]
            outcomes2 = [o for o in outcomes2 if o.symbol == symbol]
        
        return {
            agent1: {
                'signals': len(outcomes1),
                'win_rate': sum(1 for o in outcomes1 if o.was_correct) / len(outcomes1) if outcomes1 else 0,
                'total_return': sum(o.return_pct for o in outcomes1)
            },
            agent2: {
                'signals': len(outcomes2),
                'win_rate': sum(1 for o in outcomes2 if o.was_correct) / len(outcomes2) if outcomes2 else 0,
                'total_return': sum(o.return_pct for o in outcomes2)
            }
        }
    
    def _save_signals(self):
        """Save signals to file"""
        data = []
        for s in self.signals[-1000:]:  # Keep last 1000
            data.append({
                'agent_name': s.agent_name,
                'symbol': s.symbol,
                'action': s.action,
                'confidence': s.confidence,
                'timestamp': s.timestamp.isoformat(),
                'price_at_signal': s.price_at_signal,
                'reasoning': s.reasoning,
                'metadata': s.metadata
            })
        
        with open(self.storage_path / 'signals.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_outcomes(self):
        """Save outcomes to file"""
        data = []
        for o in self.outcomes[-1000:]:
            data.append({
                'signal_id': o.signal_id,
                'agent_name': o.agent_name,
                'symbol': o.symbol,
                'action': o.action,
                'entry_price': o.entry_price,
                'exit_price': o.exit_price,
                'return_pct': o.return_pct,
                'holding_period_days': o.holding_period_days,
                'was_correct': o.was_correct,
                'timestamp': o.timestamp.isoformat()
            })
        
        with open(self.storage_path / 'outcomes.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_metrics(self):
        """Save metrics to file"""
        data = {name: m.to_dict() for name, m in self.metrics.items()}
        
        with open(self.storage_path / 'metrics.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_data(self):
        """Load existing data from files"""
        # Load signals
        signals_file = self.storage_path / 'signals.json'
        if signals_file.exists():
            try:
                with open(signals_file) as f:
                    data = json.load(f)
                for item in data:
                    item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                    self.signals.append(AgentSignal(**item))
            except Exception as e:
                logger.warning(f"Failed to load signals: {e}")
        
        # Load outcomes
        outcomes_file = self.storage_path / 'outcomes.json'
        if outcomes_file.exists():
            try:
                with open(outcomes_file) as f:
                    data = json.load(f)
                for item in data:
                    item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                    self.outcomes.append(SignalOutcome(**item))
            except Exception as e:
                logger.warning(f"Failed to load outcomes: {e}")
        
        # Load metrics
        metrics_file = self.storage_path / 'metrics.json'
        if metrics_file.exists():
            try:
                with open(metrics_file) as f:
                    data = json.load(f)
                for name, m in data.items():
                    m['last_updated'] = datetime.fromisoformat(m['last_updated'])
                    self.metrics[name] = AgentMetrics(**m)
            except Exception as e:
                logger.warning(f"Failed to load metrics: {e}")


# ============================================
# ADAPTIVE WEIGHT OPTIMIZER
# ============================================

class AdaptiveWeightOptimizer:
    """
    Dynamically adjust agent weights based on performance
    
    Uses:
    - Historical accuracy
    - Sharpe ratio
    - Recent performance (recency bias)
    - Consistency
    """
    
    def __init__(self, tracker: AgentPerformanceTracker):
        self.tracker = tracker
        self.base_weights = {}
        self.current_weights = {}
        self.weight_history = []
    
    def set_base_weights(self, weights: Dict[str, float]):
        """Set base weights for agents"""
        self.base_weights = weights.copy()
        self.current_weights = weights.copy()
    
    def calculate_optimal_weights(self, 
                                   recency_window: int = 30,
                                   min_signals: int = 5) -> Dict[str, float]:
        """
        Calculate optimal weights based on performance
        
        Args:
            recency_window: Days to consider for recent performance
            min_signals: Minimum signals required for weight adjustment
        """
        metrics = self.tracker.get_metrics()
        
        if not metrics:
            return self.base_weights
        
        scores = {}
        
        for agent_name, m in metrics.items():
            if m.total_signals < min_signals:
                # Not enough data, use base weight
                scores[agent_name] = self.base_weights.get(agent_name, 1.0)
                continue
            
            # Calculate composite score
            score = self.tracker._calculate_composite_score(m)
            
            # Apply recency bias
            recent_outcomes = [
                o for o in self.tracker.outcomes
                if o.agent_name == agent_name and
                (datetime.now() - o.timestamp).days <= recency_window
            ]
            
            if recent_outcomes:
                recent_accuracy = sum(1 for o in recent_outcomes if o.was_correct) / len(recent_outcomes)
                # Blend historical and recent (60% recent, 40% historical)
                blended_score = 0.6 * recent_accuracy * 100 + 0.4 * score
            else:
                blended_score = score
            
            scores[agent_name] = blended_score
        
        # Normalize weights
        if not scores:
            return self.base_weights
        
        total_score = sum(scores.values())
        if total_score == 0:
            return self.base_weights
        
        # Scale to maintain similar total weight as base
        base_total = sum(self.base_weights.values())
        weights = {
            agent: (score / total_score) * base_total * len(scores)
            for agent, score in scores.items()
        }
        
        # Apply constraints (min 0.5x, max 2.0x of base weight)
        for agent in weights:
            if agent in self.base_weights:
                base = self.base_weights[agent]
                weights[agent] = max(base * 0.5, min(base * 2.0, weights[agent]))
        
        self.current_weights = weights
        self.weight_history.append({
            'timestamp': datetime.now(),
            'weights': weights.copy()
        })
        
        return weights
    
    def get_weight_changes(self) -> pd.DataFrame:
        """Get weight changes over time"""
        if len(self.weight_history) < 2:
            return pd.DataFrame()
        
        data = []
        prev = self.weight_history[0]['weights']
        
        for entry in self.weight_history[1:]:
            for agent, weight in entry['weights'].items():
                prev_weight = prev.get(agent, weight)
                change = (weight - prev_weight) / prev_weight if prev_weight > 0 else 0
                
                data.append({
                    'timestamp': entry['timestamp'],
                    'agent': agent,
                    'weight': weight,
                    'change': change
                })
            
            prev = entry['weights']
        
        return pd.DataFrame(data)
    
    def explain_weights(self) -> str:
        """Explain current weight assignments"""
        metrics = self.tracker.get_metrics()
        explanation = ["Agent Weight Explanation:", "=" * 40]
        
        for agent, weight in sorted(self.current_weights.items(), key=lambda x: -x[1]):
            base = self.base_weights.get(agent, 1.0)
            change = (weight - base) / base * 100 if base > 0 else 0
            
            m = metrics.get(agent)
            if m:
                explanation.append(
                    f"\n{agent}:"
                    f"\n  Weight: {weight:.2f} ({change:+.1f}% from base)"
                    f"\n  Win Rate: {m.win_rate:.1%}"
                    f"\n  Sharpe: {m.sharpe_ratio:.2f}"
                    f"\n  Signals: {m.total_signals}"
                )
            else:
                explanation.append(f"\n{agent}: {weight:.2f} (no data)")
        
        return "\n".join(explanation)


# ============================================
# TESTING
# ============================================

def test_performance_tracker():
    """Test agent performance tracker"""
    print("Testing Agent Performance Tracker...")
    print("=" * 50)
    
    # Create tracker
    tracker = AgentPerformanceTracker(storage_path="test_agent_perf")
    
    # Simulate signals and outcomes
    agents = ['BullAgent', 'BearAgent', 'AnalystAgent', 'FlowAgent']
    symbols = ['HPG', 'VNM', 'FPT']
    
    np.random.seed(42)
    
    for _ in range(50):
        agent = np.random.choice(agents)
        symbol = np.random.choice(symbols)
        action = np.random.choice(['BUY', 'SELL'])
        confidence = np.random.uniform(0.5, 0.95)
        price = np.random.uniform(20000, 100000)
        
        signal_id = tracker.record_signal(
            agent_name=agent,
            symbol=symbol,
            action=action,
            confidence=confidence,
            price=price,
            reasoning=f"Test signal from {agent}"
        )
        
        # Simulate outcome
        return_pct = np.random.normal(0.02 if agent == 'AnalystAgent' else 0, 0.05)
        exit_price = price * (1 + return_pct if action == 'BUY' else 1 - return_pct)
        
        tracker.record_outcome(signal_id, exit_price, holding_days=5)
    
    # Get leaderboard
    print("\n📊 Agent Leaderboard:")
    leaderboard = tracker.get_leaderboard()
    print(leaderboard.to_string(index=False))
    
    # Test adaptive weights
    print("\n⚖️ Adaptive Weights:")
    optimizer = AdaptiveWeightOptimizer(tracker)
    optimizer.set_base_weights({
        'BullAgent': 1.0,
        'BearAgent': 1.0,
        'AnalystAgent': 1.2,
        'FlowAgent': 0.8
    })
    
    optimal_weights = optimizer.calculate_optimal_weights()
    print("\nOptimal Weights:")
    for agent, weight in sorted(optimal_weights.items(), key=lambda x: -x[1]):
        print(f"  {agent}: {weight:.3f}")
    
    # Cleanup test files
    import shutil
    shutil.rmtree("test_agent_perf", ignore_errors=True)
    
    print("\n✅ Agent Performance Tracker tests completed!")


if __name__ == "__main__":
    test_performance_tracker()
