# -*- coding: utf-8 -*-
"""
Cooperative Voting System - Level 4 Agentic AI
===============================================
Multi-agent signal aggregation with confidence boosting.

Features:
- Aggregate signals from multiple agents
- Cooperative reward boosting (φ parameter)
- Conflict resolution
- Consensus detection
- Risk-weighted voting

Based on: MADDPG with Cooperative Behavior Encouragement (Qi et al., 2024)
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json


class SignalType(Enum):
    STRONG_BUY = 2
    BUY = 1
    HOLD = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class AgentSignal:
    agent_name: str
    symbol: str
    signal: SignalType
    confidence: float  # 0-1
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Performance metrics for weighting
    historical_accuracy: float = 0.5
    recent_win_rate: float = 0.5
    sharpe_contribution: float = 0.0


@dataclass
class ConsensusResult:
    symbol: str
    final_signal: SignalType
    final_confidence: float
    consensus_strength: float  # 0-1, how much agents agree
    contributing_agents: List[str]
    dissenting_agents: List[str]
    position_recommendation: float  # -1 to 1 (full short to full long)
    reasoning: str
    is_actionable: bool
    cooperative_boost_applied: bool


class CooperativeVotingSystem:
    """
    Multi-Agent Cooperative Voting System
    
    Algorithm:
    1. Collect signals from all agents
    2. Weight by historical accuracy
    3. Apply cooperative boost when agents agree
    4. Resolve conflicts using risk-weighted voting
    5. Output final recommendation with confidence
    
    Cooperative Boosting (φ parameter):
    - When ≥ L agents have positive signals, boost all positive signals by φ
    - Encourages agent coordination naturally
    
    Parameters:
    - phi (φ): Cooperative boost multiplier (default 1.5)
    - L: Minimum agents for boost trigger (default 2)
    - consensus_threshold: Min agreement for actionable signal (default 0.6)
    """
    
    def __init__(
        self,
        phi: float = 1.5,
        min_agents_for_boost: int = 2,
        consensus_threshold: float = 0.6,
        min_confidence: float = 0.5
    ):
        self.phi = phi  # Cooperative boost multiplier
        self.L = min_agents_for_boost
        self.consensus_threshold = consensus_threshold
        self.min_confidence = min_confidence
        
        # Agent performance tracking
        self.agent_performance: Dict[str, Dict] = {}
        
        # Signal history for analysis
        self.signal_history: List[ConsensusResult] = []
    
    def register_agent(
        self,
        agent_name: str,
        initial_accuracy: float = 0.5,
        initial_sharpe: float = 0.0
    ):
        """Register an agent for voting"""
        self.agent_performance[agent_name] = {
            "total_signals": 0,
            "correct_signals": 0,
            "accuracy": initial_accuracy,
            "recent_signals": [],  # Last 20 signals
            "sharpe_contribution": initial_sharpe,
            "weight": 1.0
        }
    
    def update_agent_performance(
        self,
        agent_name: str,
        was_correct: bool,
        pnl_contribution: float = 0.0
    ):
        """Update agent's performance metrics"""
        if agent_name not in self.agent_performance:
            self.register_agent(agent_name)
        
        perf = self.agent_performance[agent_name]
        perf["total_signals"] += 1
        
        if was_correct:
            perf["correct_signals"] += 1
        
        # Update accuracy
        perf["accuracy"] = perf["correct_signals"] / max(perf["total_signals"], 1)
        
        # Update recent signals (rolling window of 20)
        perf["recent_signals"].append({
            "correct": was_correct,
            "pnl": pnl_contribution,
            "timestamp": datetime.now().isoformat()
        })
        if len(perf["recent_signals"]) > 20:
            perf["recent_signals"] = perf["recent_signals"][-20:]
        
        # Calculate recent win rate
        recent_correct = sum(1 for s in perf["recent_signals"] if s["correct"])
        perf["recent_win_rate"] = recent_correct / len(perf["recent_signals"])
        
        # Update weight based on performance
        perf["weight"] = self._calculate_agent_weight(agent_name)
    
    def _calculate_agent_weight(self, agent_name: str) -> float:
        """Calculate agent's voting weight based on performance"""
        if agent_name not in self.agent_performance:
            return 1.0
        
        perf = self.agent_performance[agent_name]
        
        # Base weight from accuracy (50-150%)
        accuracy_weight = 0.5 + perf["accuracy"]
        
        # Recency bonus (recent performance matters more)
        if len(perf["recent_signals"]) >= 5:
            recency_weight = 0.8 + 0.4 * perf.get("recent_win_rate", 0.5)
        else:
            recency_weight = 1.0
        
        # Sharpe contribution bonus
        sharpe_weight = 1.0 + 0.1 * max(0, perf.get("sharpe_contribution", 0))
        
        # Combined weight (capped at 2.0)
        return min(accuracy_weight * recency_weight * sharpe_weight, 2.0)
    
    def collect_votes(
        self,
        symbol: str,
        signals: List[AgentSignal]
    ) -> ConsensusResult:
        """
        Main voting function: Collect signals and produce consensus
        
        Algorithm:
        1. Filter valid signals
        2. Calculate weighted votes
        3. Apply cooperative boost if applicable
        4. Determine final signal
        5. Calculate confidence and consensus strength
        """
        if not signals:
            return ConsensusResult(
                symbol=symbol,
                final_signal=SignalType.HOLD,
                final_confidence=0.0,
                consensus_strength=0.0,
                contributing_agents=[],
                dissenting_agents=[],
                position_recommendation=0.0,
                reasoning="No signals received",
                is_actionable=False,
                cooperative_boost_applied=False
            )
        
        # Step 1: Calculate weighted votes
        weighted_votes = {}
        total_weight = 0
        
        for sig in signals:
            # Get agent weight
            if sig.agent_name in self.agent_performance:
                agent_weight = self.agent_performance[sig.agent_name]["weight"]
            else:
                agent_weight = 1.0
            
            # Combine with signal confidence
            vote_weight = agent_weight * sig.confidence
            
            weighted_votes[sig.agent_name] = {
                "signal": sig.signal,
                "signal_value": sig.signal.value,
                "confidence": sig.confidence,
                "weight": vote_weight,
                "reasoning": sig.reasoning
            }
            total_weight += vote_weight
        
        # Step 2: Check for cooperative boost
        positive_signals = [v for v in weighted_votes.values() if v["signal_value"] > 0]
        negative_signals = [v for v in weighted_votes.values() if v["signal_value"] < 0]
        
        cooperative_boost_applied = False
        
        # Apply φ boost if enough agents agree (majority direction)
        if len(positive_signals) >= self.L and len(positive_signals) > len(negative_signals):
            # Boost positive signals
            for agent_name, vote in weighted_votes.items():
                if vote["signal_value"] > 0:
                    vote["weight"] *= self.phi
            cooperative_boost_applied = True
            boost_reason = "bullish"
            
        elif len(negative_signals) >= self.L and len(negative_signals) > len(positive_signals):
            # Boost negative signals
            for agent_name, vote in weighted_votes.items():
                if vote["signal_value"] < 0:
                    vote["weight"] *= self.phi
            cooperative_boost_applied = True
            boost_reason = "bearish"
        
        # Step 3: Calculate weighted average signal
        total_boosted_weight = sum(v["weight"] for v in weighted_votes.values())
        weighted_signal = sum(
            v["signal_value"] * v["weight"] 
            for v in weighted_votes.values()
        ) / max(total_boosted_weight, 1e-10)
        
        # Step 4: Determine final signal
        if weighted_signal >= 1.5:
            final_signal = SignalType.STRONG_BUY
        elif weighted_signal >= 0.5:
            final_signal = SignalType.BUY
        elif weighted_signal <= -1.5:
            final_signal = SignalType.STRONG_SELL
        elif weighted_signal <= -0.5:
            final_signal = SignalType.SELL
        else:
            final_signal = SignalType.HOLD
        
        # Step 5: Calculate consensus strength
        # Higher when agents agree, lower when they disagree
        signal_values = [v["signal_value"] for v in weighted_votes.values()]
        if len(signal_values) > 1:
            signal_std = np.std(signal_values)
            # Lower std = higher consensus (max std ≈ 2 for extreme disagreement)
            consensus_strength = 1 - min(signal_std / 2, 1)
        else:
            consensus_strength = 1.0
        
        # Step 6: Calculate final confidence
        avg_confidence = np.mean([v["confidence"] for v in weighted_votes.values()])
        
        # Boost confidence with consensus
        final_confidence = avg_confidence * (0.5 + 0.5 * consensus_strength)
        
        # Apply cooperative boost to confidence
        if cooperative_boost_applied:
            final_confidence = min(final_confidence * 1.2, 0.99)
        
        # Step 7: Categorize agents
        contributing_agents = []
        dissenting_agents = []
        
        for agent_name, vote in weighted_votes.items():
            if (final_signal.value > 0 and vote["signal_value"] > 0) or \
               (final_signal.value < 0 and vote["signal_value"] < 0) or \
               final_signal == SignalType.HOLD:
                contributing_agents.append(agent_name)
            else:
                dissenting_agents.append(agent_name)
        
        # Step 8: Position recommendation (-1 to 1)
        position_recommendation = np.clip(weighted_signal / 2, -1, 1)
        
        # Step 9: Determine if actionable
        is_actionable = (
            final_confidence >= self.min_confidence and
            consensus_strength >= self.consensus_threshold and
            final_signal != SignalType.HOLD
        )
        
        # Build reasoning
        reasoning_parts = []
        reasoning_parts.append(f"Weighted signal: {weighted_signal:.2f}")
        reasoning_parts.append(f"Consensus: {consensus_strength:.0%}")
        
        if cooperative_boost_applied:
            reasoning_parts.append(f"Cooperative boost ({boost_reason}): φ={self.phi}")
        
        if dissenting_agents:
            reasoning_parts.append(f"Dissent from: {', '.join(dissenting_agents)}")
        
        reasoning = " | ".join(reasoning_parts)
        
        result = ConsensusResult(
            symbol=symbol,
            final_signal=final_signal,
            final_confidence=round(final_confidence, 4),
            consensus_strength=round(consensus_strength, 4),
            contributing_agents=contributing_agents,
            dissenting_agents=dissenting_agents,
            position_recommendation=round(position_recommendation, 4),
            reasoning=reasoning,
            is_actionable=is_actionable,
            cooperative_boost_applied=cooperative_boost_applied
        )
        
        # Store in history
        self.signal_history.append(result)
        if len(self.signal_history) > 1000:
            self.signal_history = self.signal_history[-1000:]
        
        return result
    
    def get_agent_rankings(self) -> List[Dict]:
        """Get agents ranked by performance"""
        rankings = []
        
        for name, perf in self.agent_performance.items():
            rankings.append({
                "agent": name,
                "accuracy": round(perf["accuracy"], 4),
                "recent_win_rate": round(perf.get("recent_win_rate", 0.5), 4),
                "total_signals": perf["total_signals"],
                "weight": round(perf["weight"], 4)
            })
        
        return sorted(rankings, key=lambda x: x["accuracy"], reverse=True)
    
    def export_state(self) -> Dict:
        """Export system state for persistence"""
        return {
            "phi": self.phi,
            "L": self.L,
            "agent_performance": self.agent_performance,
            "history_count": len(self.signal_history)
        }
    
    def import_state(self, state: Dict):
        """Import system state"""
        self.phi = state.get("phi", self.phi)
        self.L = state.get("L", self.L)
        self.agent_performance = state.get("agent_performance", {})


# Singleton
_voting_system = None

def get_voting_system() -> CooperativeVotingSystem:
    global _voting_system
    if _voting_system is None:
        _voting_system = CooperativeVotingSystem()
    return _voting_system


# Test
if __name__ == "__main__":
    vs = CooperativeVotingSystem(phi=1.5, min_agents_for_boost=2)
    
    # Register agents
    for agent in ["Momentum", "MeanReversion", "RiskManager", "FlowDetective", "NewsSentinel"]:
        vs.register_agent(agent, initial_accuracy=0.6)
    
    # Simulate signals
    signals = [
        AgentSignal("Momentum", "VNM", SignalType.BUY, 0.8, "Uptrend confirmed"),
        AgentSignal("MeanReversion", "VNM", SignalType.HOLD, 0.5, "Near mean"),
        AgentSignal("RiskManager", "VNM", SignalType.BUY, 0.7, "Risk acceptable"),
        AgentSignal("FlowDetective", "VNM", SignalType.STRONG_BUY, 0.9, "Block trade detected"),
        AgentSignal("NewsSentinel", "VNM", SignalType.BUY, 0.6, "Positive news"),
    ]
    
    result = vs.collect_votes("VNM", signals)
    
    print("=== COOPERATIVE VOTING RESULT ===")
    print(f"Symbol: {result.symbol}")
    print(f"Final Signal: {result.final_signal.name}")
    print(f"Confidence: {result.final_confidence:.2%}")
    print(f"Consensus: {result.consensus_strength:.2%}")
    print(f"Position: {result.position_recommendation:+.2f}")
    print(f"Actionable: {result.is_actionable}")
    print(f"Cooperative Boost: {result.cooperative_boost_applied}")
    print(f"Contributing: {result.contributing_agents}")
    print(f"Dissenting: {result.dissenting_agents}")
    print(f"Reasoning: {result.reasoning}")
