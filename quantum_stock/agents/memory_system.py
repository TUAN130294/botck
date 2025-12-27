"""
Agent Memory System - Level 3 Agentic Architecture
Provides persistent memory for agents to learn from past analyses
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import os
from enum import Enum


class MemoryType(Enum):
    """Types of memories stored by agents"""
    ANALYSIS = "ANALYSIS"           # Past analysis results
    PREDICTION = "PREDICTION"       # Predictions made
    FEEDBACK = "FEEDBACK"           # Feedback on predictions
    PATTERN = "PATTERN"             # Recognized patterns
    MARKET_REGIME = "MARKET_REGIME" # Market regime observations
    ALERT = "ALERT"                 # Important alerts


@dataclass
class Memory:
    """Single memory entry"""
    memory_id: str
    memory_type: MemoryType
    symbol: str
    content: Dict[str, Any]
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    outcome: Optional[Dict[str, Any]] = None  # Actual outcome for learning
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'memory_id': self.memory_id,
            'memory_type': self.memory_type.value,
            'symbol': self.symbol,
            'content': self.content,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'tags': self.tags,
            'outcome': self.outcome
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        return cls(
            memory_id=data['memory_id'],
            memory_type=MemoryType(data['memory_type']),
            symbol=data['symbol'],
            content=data['content'],
            confidence=data['confidence'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
            tags=data.get('tags', []),
            outcome=data.get('outcome')
        )


class AgentMemorySystem:
    """
    Centralized memory system for all agents.
    Enables agents to:
    1. Store and retrieve past analyses
    2. Learn from prediction outcomes
    3. Share knowledge between agents
    4. Recognize recurring patterns
    """
    
    def __init__(self, storage_path: str = "agent_memory.json"):
        self.storage_path = storage_path
        self.memories: Dict[str, List[Memory]] = {}  # agent_name -> memories
        self.shared_memories: List[Memory] = []  # Shared across agents
        self.pattern_cache: Dict[str, Dict[str, Any]] = {}  # symbol -> patterns
        self._load()
    
    def _load(self):
        """Load memories from persistent storage"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Load agent memories
                for agent_name, memories in data.get('agent_memories', {}).items():
                    self.memories[agent_name] = [
                        Memory.from_dict(m) for m in memories
                    ]
                
                # Load shared memories
                self.shared_memories = [
                    Memory.from_dict(m) for m in data.get('shared_memories', [])
                ]
                
                # Load pattern cache
                self.pattern_cache = data.get('pattern_cache', {})
                
            except Exception as e:
                print(f"Error loading memory: {e}")
    
    def _save(self):
        """Save memories to persistent storage"""
        try:
            data = {
                'agent_memories': {
                    name: [m.to_dict() for m in memories]
                    for name, memories in self.memories.items()
                },
                'shared_memories': [m.to_dict() for m in self.shared_memories],
                'pattern_cache': self.pattern_cache,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error saving memory: {e}")
    
    def store(self, agent_name: str, memory: Memory, shared: bool = False):
        """Store a memory for an agent"""
        if agent_name not in self.memories:
            self.memories[agent_name] = []
        
        self.memories[agent_name].append(memory)
        
        if shared:
            self.shared_memories.append(memory)
        
        self._save()
    
    def recall(self, agent_name: str, symbol: str = None, 
               memory_type: MemoryType = None,
               limit: int = 10,
               include_shared: bool = True) -> List[Memory]:
        """
        Recall memories for an agent.
        Can filter by symbol and memory type.
        """
        memories = self.memories.get(agent_name, [])
        
        if include_shared:
            memories = memories + self.shared_memories
        
        # Filter expired memories
        now = datetime.now()
        memories = [m for m in memories 
                   if m.expires_at is None or m.expires_at > now]
        
        # Filter by symbol
        if symbol:
            memories = [m for m in memories if m.symbol == symbol]
        
        # Filter by type
        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]
        
        # Sort by timestamp (most recent first)
        memories.sort(key=lambda m: m.timestamp, reverse=True)
        
        return memories[:limit]
    
    def record_outcome(self, memory_id: str, outcome: Dict[str, Any]):
        """
        Record the actual outcome of a prediction for learning.
        This is crucial for feedback loops.
        """
        for agent_memories in self.memories.values():
            for memory in agent_memories:
                if memory.memory_id == memory_id:
                    memory.outcome = outcome
                    self._save()
                    return True
        
        for memory in self.shared_memories:
            if memory.memory_id == memory_id:
                memory.outcome = outcome
                self._save()
                return True
        
        return False
    
    def get_prediction_accuracy(self, agent_name: str, 
                                 symbol: str = None,
                                 lookback_days: int = 30) -> Dict[str, Any]:
        """
        Calculate prediction accuracy for an agent.
        Used for agent self-improvement.
        """
        memories = self.recall(
            agent_name, 
            symbol=symbol,
            memory_type=MemoryType.PREDICTION,
            limit=1000,
            include_shared=False
        )
        
        cutoff = datetime.now() - timedelta(days=lookback_days)
        memories = [m for m in memories if m.timestamp > cutoff and m.outcome]
        
        if not memories:
            return {'accuracy': 0.5, 'sample_size': 0}
        
        correct = 0
        total = len(memories)
        
        for memory in memories:
            prediction = memory.content.get('direction', 'NEUTRAL')
            actual = memory.outcome.get('direction', 'NEUTRAL')
            
            if prediction == actual:
                correct += 1
        
        return {
            'accuracy': correct / total if total > 0 else 0.5,
            'sample_size': total,
            'correct_predictions': correct,
            'confidence_calibration': self._calculate_calibration(memories)
        }
    
    def _calculate_calibration(self, memories: List[Memory]) -> float:
        """
        Calculate how well-calibrated the confidence scores are.
        A well-calibrated agent should be right ~70% of the time
        when it says it's 70% confident.
        """
        if not memories:
            return 0.5
        
        buckets = {i: {'correct': 0, 'total': 0} for i in range(10)}
        
        for memory in memories:
            confidence = memory.confidence
            bucket = min(9, int(confidence / 10))
            
            prediction = memory.content.get('direction', 'NEUTRAL')
            actual = memory.outcome.get('direction', 'NEUTRAL')
            
            buckets[bucket]['total'] += 1
            if prediction == actual:
                buckets[bucket]['correct'] += 1
        
        # Calculate calibration error
        total_error = 0
        count = 0
        
        for bucket, data in buckets.items():
            if data['total'] > 0:
                expected_accuracy = (bucket + 0.5) / 10
                actual_accuracy = data['correct'] / data['total']
                total_error += abs(expected_accuracy - actual_accuracy)
                count += 1
        
        return 1 - (total_error / count) if count > 0 else 0.5
    
    def store_pattern(self, symbol: str, pattern: Dict[str, Any]):
        """Store a recognized pattern for a symbol"""
        if symbol not in self.pattern_cache:
            self.pattern_cache[symbol] = {
                'patterns': [],
                'last_updated': datetime.now().isoformat()
            }
        
        self.pattern_cache[symbol]['patterns'].append({
            **pattern,
            'discovered_at': datetime.now().isoformat()
        })
        
        # Keep only recent patterns
        self.pattern_cache[symbol]['patterns'] = \
            self.pattern_cache[symbol]['patterns'][-50:]
        
        self._save()
    
    def get_patterns(self, symbol: str) -> List[Dict[str, Any]]:
        """Get recognized patterns for a symbol"""
        return self.pattern_cache.get(symbol, {}).get('patterns', [])
    
    def get_inter_agent_context(self, requesting_agent: str, 
                                 symbol: str) -> Dict[str, Any]:
        """
        Get context from other agents' analyses.
        Enables agents to build on each other's work.
        """
        context = {}
        
        for agent_name, memories in self.memories.items():
            if agent_name == requesting_agent:
                continue
            
            recent_analysis = None
            for memory in reversed(memories):
                if memory.symbol == symbol and \
                   memory.memory_type == MemoryType.ANALYSIS:
                    recent_analysis = memory
                    break
            
            if recent_analysis:
                context[agent_name] = {
                    'signal': recent_analysis.content.get('signal'),
                    'confidence': recent_analysis.confidence,
                    'reasoning': recent_analysis.content.get('reasoning', ''),
                    'timestamp': recent_analysis.timestamp.isoformat()
                }
        
        return context
    
    def cleanup_expired(self):
        """Remove expired memories"""
        now = datetime.now()
        
        for agent_name in self.memories:
            self.memories[agent_name] = [
                m for m in self.memories[agent_name]
                if m.expires_at is None or m.expires_at > now
            ]
        
        self.shared_memories = [
            m for m in self.shared_memories
            if m.expires_at is None or m.expires_at > now
        ]
        
        self._save()
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics about the memory system"""
        stats = {
            'total_memories': sum(len(m) for m in self.memories.values()),
            'shared_memories': len(self.shared_memories),
            'agents_with_memory': list(self.memories.keys()),
            'symbols_tracked': len(self.pattern_cache),
            'memory_by_agent': {
                name: len(memories) 
                for name, memories in self.memories.items()
            }
        }
        return stats


# Global memory instance
_memory_system: Optional[AgentMemorySystem] = None


def get_memory_system(storage_path: str = None) -> AgentMemorySystem:
    """Get or create the global memory system instance"""
    global _memory_system
    
    if _memory_system is None:
        path = storage_path or os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 'data', 'agent_memory.json'
        )
        _memory_system = AgentMemorySystem(storage_path=path)
    
    return _memory_system
