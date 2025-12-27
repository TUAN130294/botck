# -*- coding: utf-8 -*-
"""
AI Learning System - Level 4 Autonomous Learning
=================================================
Tích hợp đầy đủ các components để agents tự học và cải thiện

Features:
1. Performance tracking & feedback loop
2. Memory system cho learning
3. Strategy adaptation dựa trên results
4. Market regime detection & adaptation
5. Continuous model improvement
6. Agent weight optimization
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Import existing components
from quantum_stock.agents.performance_tracker import AgentPerformanceTracker, AgentMetrics
from quantum_stock.agents.memory_system import AgentMemorySystem, Memory, MemoryType
from quantum_stock.agents.market_regime_detector import MarketRegimeDetector


@dataclass
class LearningConfig:
    """Configuration for learning system"""
    # Performance tracking
    min_signals_for_evaluation: int = 10  # Minimum signals before adjusting weights
    evaluation_window_days: int = 30      # Rolling window for performance

    # Weight adjustment
    min_agent_weight: float = 0.1         # Minimum weight for any agent
    max_agent_weight: float = 3.0         # Maximum weight multiplier
    weight_adjustment_rate: float = 0.1   # How aggressively to adjust weights

    # Learning
    memory_retention_days: int = 180      # Keep memories for 6 months
    pattern_confidence_threshold: float = 0.7  # Min confidence to act on pattern

    # Retraining
    auto_retrain_enabled: bool = True
    retrain_threshold_accuracy: float = 0.45  # Retrain if accuracy drops below
    retrain_interval_days: int = 7        # Check weekly


class AILearningSystem:
    """
    Central AI Learning System

    Manages:
    - Agent performance tracking
    - Memory and learning
    - Strategy adaptation
    - Model retraining triggers
    """

    def __init__(self, config: LearningConfig = None):
        self.config = config or LearningConfig()

        # Initialize components
        self.performance_tracker = AgentPerformanceTracker(storage_path="data/learning/performance")
        self.memory_system = AgentMemorySystem(storage_path="data/learning/agent_memory.json")
        self.regime_detector = MarketRegimeDetector()

        # Agent weights (dynamically adjusted)
        self.agent_weights: Dict[str, float] = {
            'Alex': 1.2,      # Analyst - slightly higher weight
            'Bull': 1.0,
            'Bear': 1.0,
            'RiskDoctor': 1.3, # Risk - higher weight
            'Chief': 1.0
        }

        # Learning state
        self.learning_enabled = True
        self.last_weight_update: Optional[datetime] = None
        self.last_retrain_check: Optional[datetime] = None

        # Create data directory
        Path("data/learning").mkdir(parents=True, exist_ok=True)

        # Load previous state
        self._load_state()

    def _load_state(self):
        """Load learning state from disk"""
        state_file = Path("data/learning/learning_state.json")
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.agent_weights = state.get('agent_weights', self.agent_weights)
                    self.last_weight_update = datetime.fromisoformat(state['last_weight_update']) if state.get('last_weight_update') else None
                    self.last_retrain_check = datetime.fromisoformat(state['last_retrain_check']) if state.get('last_retrain_check') else None
                    logger.info(f"Loaded learning state: {len(self.agent_weights)} agent weights")
            except Exception as e:
                logger.error(f"Error loading learning state: {e}")

    def _save_state(self):
        """Save learning state to disk"""
        state_file = Path("data/learning/learning_state.json")
        try:
            state = {
                'agent_weights': self.agent_weights,
                'last_weight_update': self.last_weight_update.isoformat() if self.last_weight_update else None,
                'last_retrain_check': self.last_retrain_check.isoformat() if self.last_retrain_check else None,
                'updated_at': datetime.now().isoformat()
            }
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving learning state: {e}")

    async def record_agent_decision(self, agent_name: str, symbol: str,
                                    signal_type: str, confidence: float,
                                    price: float, reasoning: str) -> str:
        """
        Record an agent's decision for later evaluation

        Returns: signal_id for tracking outcome
        """
        # Record in performance tracker
        signal_id = self.performance_tracker.record_signal(
            agent_name=agent_name,
            symbol=symbol,
            action=signal_type,
            confidence=confidence,
            price=price,
            reasoning=reasoning
        )

        # Store in memory
        memory = Memory(
            memory_id=signal_id,
            memory_type=MemoryType.PREDICTION,
            symbol=symbol,
            content={
                'signal_type': signal_type,
                'confidence': confidence,
                'price': price,
                'reasoning': reasoning
            },
            confidence=confidence,
            timestamp=datetime.now()
        )
        self.memory_system.store(agent_name, memory, shared=False)

        logger.info(f"📝 Recorded decision: {agent_name} {signal_type} {symbol} @ {price}")
        return signal_id

    async def record_outcome(self, signal_id: str, exit_price: float,
                            holding_days: int, pnl_pct: float):
        """
        Record the actual outcome of a decision for learning
        """
        try:
            # Record in performance tracker
            outcome = self.performance_tracker.record_outcome(
                signal_id=signal_id,
                exit_price=exit_price,
                holding_days=holding_days
            )

            # Update memory with outcome
            # Find the memory and update it with actual results
            for agent_name, memories in self.memory_system.memories.items():
                for memory in memories:
                    if memory.memory_id == signal_id:
                        memory.outcome = {
                            'exit_price': exit_price,
                            'holding_days': holding_days,
                            'pnl_pct': pnl_pct,
                            'was_correct': outcome.was_correct
                        }
                        self.memory_system._save()
                        break

            logger.info(f"📊 Recorded outcome: {signal_id} → {pnl_pct*100:.2f}% P&L")

            # Trigger learning if enough data
            await self._check_and_update_weights()

        except Exception as e:
            logger.error(f"Error recording outcome: {e}")

    async def _check_and_update_weights(self):
        """
        Check if we have enough data to update agent weights
        Called after each outcome is recorded
        """
        # Only update weekly
        if self.last_weight_update and \
           (datetime.now() - self.last_weight_update).days < 7:
            return

        # Update metrics
        self.performance_tracker.update_all_metrics()

        # Check if we have enough signals
        total_signals = sum(m.total_signals for m in self.performance_tracker.metrics.values())
        if total_signals < self.config.min_signals_for_evaluation:
            logger.info(f"Not enough signals yet ({total_signals}/{self.config.min_signals_for_evaluation})")
            return

        # Adjust weights based on performance
        await self._adjust_agent_weights()

        self.last_weight_update = datetime.now()
        self._save_state()

    async def _adjust_agent_weights(self):
        """
        Adjust agent weights based on historical performance

        Better performing agents get higher weights in consensus voting
        """
        logger.info("🧠 Adjusting agent weights based on performance...")

        metrics = self.performance_tracker.metrics

        for agent_name, agent_metrics in metrics.items():
            if agent_metrics.total_signals < 5:
                continue  # Not enough data

            # Calculate performance score (0-1)
            accuracy_score = agent_metrics.accuracy
            sharpe_score = min(1.0, max(0, agent_metrics.sharpe_ratio / 3.0))  # Normalize Sharpe
            consistency_score = agent_metrics.consistency_score

            # Weighted average
            performance_score = (
                accuracy_score * 0.4 +
                sharpe_score * 0.3 +
                consistency_score * 0.3
            )

            # Calculate new weight
            old_weight = self.agent_weights.get(agent_name, 1.0)

            # Adjust towards performance score
            target_weight = 0.5 + (performance_score * 2.5)  # Range: 0.5 to 3.0
            new_weight = old_weight + (target_weight - old_weight) * self.config.weight_adjustment_rate

            # Clamp to limits
            new_weight = max(self.config.min_agent_weight,
                           min(self.config.max_agent_weight, new_weight))

            # Update weight
            self.agent_weights[agent_name] = new_weight

            logger.info(
                f"  {agent_name}: {old_weight:.2f} → {new_weight:.2f} "
                f"(acc={accuracy_score:.1%}, sharpe={agent_metrics.sharpe_ratio:.2f})"
            )

        logger.info(f"✅ Agent weights updated: {self.agent_weights}")

    def get_agent_weight(self, agent_name: str) -> float:
        """Get current weight for an agent"""
        return self.agent_weights.get(agent_name, 1.0)

    def get_weighted_consensus(self, agent_signals: Dict[str, Any]) -> float:
        """
        Calculate weighted consensus score

        Args:
            agent_signals: Dict of agent_name -> signal with confidence

        Returns:
            Weighted consensus score (0-1)
        """
        total_weight = 0
        weighted_sum = 0

        for agent_name, signal in agent_signals.items():
            weight = self.get_agent_weight(agent_name)
            confidence = signal.confidence if hasattr(signal, 'confidence') else 0.5

            # Convert signal type to numeric (-1 to 1)
            signal_value = 0
            if hasattr(signal, 'signal_type'):
                signal_str = str(signal.signal_type.value)
                if 'BUY' in signal_str:
                    signal_value = 1.0 if 'STRONG' in signal_str else 0.75
                elif 'SELL' in signal_str:
                    signal_value = -1.0 if 'STRONG' in signal_str else -0.75

            weighted_sum += signal_value * confidence * weight
            total_weight += weight

        if total_weight == 0:
            return 0.5

        # Normalize to 0-1 range
        consensus = (weighted_sum / total_weight + 1) / 2
        return consensus

    async def check_retrain_needed(self) -> bool:
        """
        Check if models need retraining based on performance degradation

        Returns: True if retraining is recommended
        """
        if not self.config.auto_retrain_enabled:
            return False

        # Check weekly
        if self.last_retrain_check and \
           (datetime.now() - self.last_retrain_check).days < self.config.retrain_interval_days:
            return False

        self.last_retrain_check = datetime.now()
        self._save_state()

        # Get recent performance
        self.performance_tracker.update_all_metrics()

        # Check if any agent's accuracy dropped significantly
        for agent_name, metrics in self.performance_tracker.metrics.items():
            if metrics.total_signals < 20:
                continue  # Not enough data

            if metrics.accuracy < self.config.retrain_threshold_accuracy:
                logger.warning(
                    f"⚠️ {agent_name} accuracy dropped to {metrics.accuracy:.1%} "
                    f"(threshold: {self.config.retrain_threshold_accuracy:.1%})"
                )
                logger.info("🔄 Recommending model retraining")
                return True

        return False

    def get_learning_stats(self) -> Dict[str, Any]:
        """Get current learning system statistics"""
        self.performance_tracker.update_all_metrics()

        return {
            'agent_weights': self.agent_weights,
            'total_signals': sum(m.total_signals for m in self.performance_tracker.metrics.values()),
            'agent_performance': {
                name: {
                    'accuracy': m.accuracy,
                    'sharpe': m.sharpe_ratio,
                    'win_rate': m.win_rate,
                    'total_signals': m.total_signals
                }
                for name, m in self.performance_tracker.metrics.items()
            },
            'last_weight_update': self.last_weight_update.isoformat() if self.last_weight_update else None,
            'learning_enabled': self.learning_enabled
        }

    async def analyze_patterns(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Analyze historical patterns for a symbol

        Returns: Detected patterns and recommendations
        """
        # Get memories for this symbol
        all_memories = []
        for agent_name in self.memory_system.memories.keys():
            memories = self.memory_system.recall(
                agent_name=agent_name,
                symbol=symbol,
                memory_type=MemoryType.PREDICTION,
                limit=50
            )
            all_memories.extend(memories)

        if len(all_memories) < 5:
            return None  # Not enough data

        # Analyze outcomes
        successful = [m for m in all_memories if m.outcome and m.outcome.get('was_correct')]
        failed = [m for m in all_memories if m.outcome and not m.outcome.get('was_correct')]

        if len(successful) + len(failed) == 0:
            return None

        success_rate = len(successful) / (len(successful) + len(failed))

        # Find common patterns in successful trades
        successful_conditions = []
        for memory in successful:
            content = memory.content
            successful_conditions.append({
                'confidence': content.get('confidence'),
                'signal': content.get('signal_type'),
                'price': content.get('price')
            })

        pattern = {
            'symbol': symbol,
            'total_trades': len(all_memories),
            'success_rate': success_rate,
            'avg_confidence_on_success': sum(c['confidence'] for c in successful_conditions) / len(successful_conditions) if successful_conditions else 0,
            'recommendation': 'HIGH_CONFIDENCE' if success_rate > 0.6 else 'CAUTION' if success_rate > 0.4 else 'AVOID',
            'detected_at': datetime.now().isoformat()
        }

        # Cache pattern
        self.memory_system.pattern_cache[symbol] = pattern
        self.memory_system._save()

        return pattern

    def get_pattern_insight(self, symbol: str) -> Optional[Dict]:
        """Get cached pattern insight for symbol"""
        return self.memory_system.pattern_cache.get(symbol)


# Singleton instance
_learning_system: Optional[AILearningSystem] = None

def get_learning_system() -> AILearningSystem:
    """Get singleton learning system instance"""
    global _learning_system
    if _learning_system is None:
        _learning_system = AILearningSystem()
    return _learning_system
