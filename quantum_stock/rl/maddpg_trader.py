# -*- coding: utf-8 -*-
"""
MADDPG Multi-Agent Trader - Level 4 Agentic AI
===============================================
Multi-Agent Deep Deterministic Policy Gradient with Cooperative Reward Boosting.

Agents (8 total):
1. Momentum Trader - Trend following
2. Mean Reversion - Counter-trend
3. Market Maker - Spread capture
4. Volatility Seller - Premium collection
5. News Trader - Sentiment-based
6. Risk Manager - Position sizing
7. Hedger - Downside protection
8. Portfolio Optimizer - Asset allocation

Framework: CTDE (Centralized Training, Decentralized Execution)
Reference: "Improved MADDPG for Cooperative-Competitive" (Qi et al., 2024)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import random
import json
from datetime import datetime

# Check for PyTorch
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class AgentRole(Enum):
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    MARKET_MAKER = "market_maker"
    VOLATILITY = "volatility"
    NEWS_TRADER = "news"
    RISK_MANAGER = "risk"
    HEDGER = "hedger"
    OPTIMIZER = "optimizer"


@dataclass
class TradingAction:
    """Action output from an agent"""
    agent_name: str
    symbol: str
    action_type: str  # "BUY", "SELL", "HOLD"
    quantity_pct: float  # -1 to 1 (% of max position)
    confidence: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass 
class MarketState:
    """Market observation for agents"""
    prices: np.ndarray
    volumes: np.ndarray
    returns: np.ndarray
    volatility: float
    trend: float  # -1 to 1
    regime: str
    sentiment: float  # -1 to 1
    timestamp: datetime = field(default_factory=datetime.now)


class ReplayBuffer:
    """Experience replay buffer for MADDPG training"""
    
    def __init__(self, capacity: int = 100000):
        self.buffer = deque(maxlen=capacity)
    
    def add(
        self,
        states: Dict[str, np.ndarray],
        actions: Dict[str, np.ndarray],
        rewards: Dict[str, float],
        next_states: Dict[str, np.ndarray],
        dones: Dict[str, bool]
    ):
        self.buffer.append((states, actions, rewards, next_states, dones))
    
    def sample(self, batch_size: int) -> List[Tuple]:
        return random.sample(self.buffer, min(batch_size, len(self.buffer)))
    
    def __len__(self):
        return len(self.buffer)


if TORCH_AVAILABLE:
    
    class ActorNetwork(nn.Module):
        """Actor network for individual agent"""
        
        def __init__(self, state_dim: int, action_dim: int = 3, hidden_dim: int = 256):
            super().__init__()
            
            self.network = nn.Sequential(
                nn.Linear(state_dim, hidden_dim),
                nn.ReLU(),
                nn.LayerNorm(hidden_dim),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.LayerNorm(hidden_dim),
                nn.Linear(hidden_dim, action_dim),
                nn.Tanh()  # Actions in [-1, 1]
            )
        
        def forward(self, state: torch.Tensor) -> torch.Tensor:
            return self.network(state)
    
    
    class CriticNetwork(nn.Module):
        """Critic network (centralized, sees all agents)"""
        
        def __init__(
            self,
            state_dim: int,
            action_dim: int,
            n_agents: int,
            hidden_dim: int = 256
        ):
            super().__init__()
            
            # Input: all states + all actions
            total_input = state_dim * n_agents + action_dim * n_agents
            
            self.network = nn.Sequential(
                nn.Linear(total_input, hidden_dim),
                nn.ReLU(),
                nn.LayerNorm(hidden_dim),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.LayerNorm(hidden_dim),
                nn.Linear(hidden_dim, 1)
            )
        
        def forward(
            self,
            states: torch.Tensor,
            actions: torch.Tensor
        ) -> torch.Tensor:
            """
            states: (batch, n_agents * state_dim)
            actions: (batch, n_agents * action_dim)
            """
            x = torch.cat([states, actions], dim=-1)
            return self.network(x)


class TradingAgent:
    """
    Individual trading agent with specific strategy
    
    Each agent has:
    - Role-specific state processing
    - Actor network for action selection
    - Reward function tailored to role
    """
    
    def __init__(
        self,
        name: str,
        role: AgentRole,
        state_dim: int = 100,
        action_dim: int = 3
    ):
        self.name = name
        self.role = role
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.sharpe_contribution = 0.0
        
        # Neural networks (if PyTorch available)
        if TORCH_AVAILABLE:
            self.actor = ActorNetwork(state_dim, action_dim)
            self.actor_target = ActorNetwork(state_dim, action_dim)
            self.actor_target.load_state_dict(self.actor.state_dict())
            self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=1e-4)
    
    def process_state(self, market_state: MarketState) -> np.ndarray:
        """
        Process market state into agent-specific features
        
        Each role focuses on different aspects of the market
        """
        base_features = []
        
        # Common features
        if len(market_state.returns) >= 20:
            base_features.extend([
                np.mean(market_state.returns[-5:]),   # Short-term return
                np.mean(market_state.returns[-20:]),  # Medium-term return
                market_state.volatility,
                market_state.trend,
                market_state.sentiment
            ])
        else:
            base_features = [0.0] * 5
        
        # Role-specific features
        if self.role == AgentRole.MOMENTUM:
            # Focus on trend indicators
            if len(market_state.prices) >= 50:
                ma20 = np.mean(market_state.prices[-20:])
                ma50 = np.mean(market_state.prices[-50:])
                momentum = (ma20 - ma50) / ma50 if ma50 > 0 else 0
                base_features.append(momentum)
            else:
                base_features.append(0.0)
                
        elif self.role == AgentRole.MEAN_REVERSION:
            # Focus on deviation from mean
            if len(market_state.prices) >= 20:
                mean_price = np.mean(market_state.prices[-20:])
                std_price = np.std(market_state.prices[-20:])
                z_score = (market_state.prices[-1] - mean_price) / (std_price + 1e-10)
                base_features.append(np.clip(z_score, -3, 3) / 3)
            else:
                base_features.append(0.0)
                
        elif self.role == AgentRole.VOLATILITY:
            # Focus on volatility regime
            if len(market_state.returns) >= 50:
                recent_vol = np.std(market_state.returns[-10:])
                historical_vol = np.std(market_state.returns[-50:])
                vol_ratio = recent_vol / (historical_vol + 1e-10)
                base_features.append(np.clip(vol_ratio, 0.5, 2) - 1)
            else:
                base_features.append(0.0)
                
        elif self.role == AgentRole.RISK_MANAGER:
            # Focus on drawdown and risk metrics
            if len(market_state.prices) >= 20:
                peak = np.max(market_state.prices[-20:])
                drawdown = (market_state.prices[-1] - peak) / peak
                base_features.append(drawdown)
            else:
                base_features.append(0.0)
        else:
            base_features.append(0.0)
        
        # Pad to state_dim
        features = np.array(base_features, dtype=np.float32)
        if len(features) < self.state_dim:
            features = np.pad(features, (0, self.state_dim - len(features)))
        
        return features[:self.state_dim]
    
    def select_action(
        self,
        state: np.ndarray,
        epsilon: float = 0.1
    ) -> np.ndarray:
        """Select action using actor network with exploration"""
        if not TORCH_AVAILABLE:
            # Random action fallback
            return np.random.uniform(-1, 1, self.action_dim)
        
        if random.random() < epsilon:
            # Exploration
            return np.random.uniform(-1, 1, self.action_dim)
        
        # Exploitation
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0)
            action = self.actor(state_tensor).numpy()[0]
        
        return action
    
    def compute_reward(
        self,
        action: np.ndarray,
        market_state: MarketState,
        next_market_state: MarketState,
        position_pnl: float
    ) -> float:
        """
        Compute role-specific reward
        
        Base: P/L
        Role-specific bonuses/penalties
        """
        # Base reward: P/L
        reward = position_pnl / 1000  # Normalize
        
        # Role-specific bonuses
        if self.role == AgentRole.MOMENTUM:
            # Bonus for riding trends correctly
            if market_state.trend > 0.3 and action[0] > 0:
                reward += 0.1
            elif market_state.trend < -0.3 and action[0] < 0:
                reward += 0.1
                
        elif self.role == AgentRole.MEAN_REVERSION:
            # Bonus for counter-trend trades at extremes
            if len(market_state.prices) >= 20:
                z_score = (market_state.prices[-1] - np.mean(market_state.prices[-20:])) / (np.std(market_state.prices[-20:]) + 1e-10)
                if z_score > 2 and action[0] < 0:  # Sell at high
                    reward += 0.1
                elif z_score < -2 and action[0] > 0:  # Buy at low
                    reward += 0.1
                    
        elif self.role == AgentRole.RISK_MANAGER:
            # Penalty for excessive risk
            if abs(action[0]) > 0.8:  # Large position
                reward -= 0.05
            # Bonus for proper stop-loss
            if action[1] > 0:  # Has stop-loss
                reward += 0.02
                
        elif self.role == AgentRole.HEDGER:
            # Reward for reducing portfolio volatility
            if market_state.volatility > 0.03:
                if action[0] * position_pnl < 0:  # Offsetting position
                    reward += 0.05
        
        return reward
    
    def update_performance(self, pnl: float, was_winner: bool):
        """Update agent performance metrics"""
        self.total_trades += 1
        self.total_pnl += pnl
        if was_winner:
            self.winning_trades += 1
    
    def get_stats(self) -> Dict:
        """Get agent statistics"""
        win_rate = self.winning_trades / max(self.total_trades, 1)
        return {
            "name": self.name,
            "role": self.role.value,
            "total_trades": self.total_trades,
            "win_rate": round(win_rate, 4),
            "total_pnl": round(self.total_pnl, 2),
            "sharpe": round(self.sharpe_contribution, 4)
        }


class MADDPGTrader:
    """
    Multi-Agent Deep Deterministic Policy Gradient Trader
    
    Coordinates 8 specialized agents with:
    - Centralized training (critic sees all)
    - Decentralized execution (each agent acts alone)
    - Cooperative reward boosting
    """
    
    # Cooperative boosting parameters
    PHI = 1.5  # Reward multiplier
    L = 2      # Min agents for boost
    
    def __init__(
        self,
        state_dim: int = 100,
        action_dim: int = 3,
        gamma: float = 0.99,
        tau: float = 0.01
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.tau = tau
        
        # Create agents
        self.agents: Dict[str, TradingAgent] = {}
        for role in AgentRole:
            agent = TradingAgent(role.value, role, state_dim, action_dim)
            self.agents[role.value] = agent
        
        self.n_agents = len(self.agents)
        
        # Centralized critic (if PyTorch available)
        if TORCH_AVAILABLE:
            self.critics: Dict[str, CriticNetwork] = {}
            self.critic_targets: Dict[str, CriticNetwork] = {}
            self.critic_optimizers: Dict[str, optim.Optimizer] = {}
            
            for name in self.agents.keys():
                critic = CriticNetwork(state_dim, action_dim, self.n_agents)
                critic_target = CriticNetwork(state_dim, action_dim, self.n_agents)
                critic_target.load_state_dict(critic.state_dict())
                
                self.critics[name] = critic
                self.critic_targets[name] = critic_target
                self.critic_optimizers[name] = optim.Adam(critic.parameters(), lr=1e-3)
        
        # Replay buffer
        self.replay_buffer = ReplayBuffer()
        
        # Training stats
        self.training_steps = 0
        self.episode_rewards = []
    
    def compute_cooperative_rewards(
        self,
        raw_rewards: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Apply cooperative reward boosting
        
        If ≥ L agents have positive rewards:
            Boost all positive rewards by φ
        
        This encourages agents to work together!
        """
        positive_count = sum(1 for r in raw_rewards.values() if r > 0)
        
        boosted_rewards = {}
        for agent_name, reward in raw_rewards.items():
            if positive_count >= self.L and reward > 0:
                boosted_rewards[agent_name] = self.PHI * reward
            else:
                boosted_rewards[agent_name] = reward
        
        return boosted_rewards
    
    def get_ensemble_action(
        self,
        market_state: MarketState,
        epsilon: float = 0.1
    ) -> Tuple[TradingAction, Dict[str, np.ndarray]]:
        """
        Get consensus action from all agents
        
        Returns:
            - Final trading action (weighted average)
            - Individual agent actions (for training)
        """
        all_actions = {}
        weighted_action = np.zeros(self.action_dim)
        total_weight = 0
        
        for agent_name, agent in self.agents.items():
            # Process state for this agent
            state = agent.process_state(market_state)
            
            # Get action
            action = agent.select_action(state, epsilon)
            all_actions[agent_name] = action
            
            # Weight by historical performance
            win_rate = agent.winning_trades / max(agent.total_trades, 1)
            weight = 0.5 + win_rate  # Base weight + performance bonus
            
            weighted_action += action * weight
            total_weight += weight
        
        # Average
        if total_weight > 0:
            final_action = weighted_action / total_weight
        else:
            final_action = np.zeros(self.action_dim)
        
        # Convert to TradingAction
        if final_action[0] > 0.3:
            action_type = "BUY"
        elif final_action[0] < -0.3:
            action_type = "SELL"
        else:
            action_type = "HOLD"
        
        trading_action = TradingAction(
            agent_name="MADDPG_Ensemble",
            symbol="-",  # To be set by caller
            action_type=action_type,
            quantity_pct=float(np.clip(final_action[0], -1, 1)),
            confidence=float(abs(final_action[0])),
            stop_loss=float(final_action[1]) if len(final_action) > 1 else None,
            take_profit=float(final_action[2]) if len(final_action) > 2 else None
        )
        
        return trading_action, all_actions
    
    def store_experience(
        self,
        market_state: MarketState,
        actions: Dict[str, np.ndarray],
        rewards: Dict[str, float],
        next_market_state: MarketState,
        done: bool
    ):
        """Store experience in replay buffer"""
        states = {}
        next_states = {}
        
        for agent_name, agent in self.agents.items():
            states[agent_name] = agent.process_state(market_state)
            next_states[agent_name] = agent.process_state(next_market_state)
        
        # Apply cooperative boosting
        boosted_rewards = self.compute_cooperative_rewards(rewards)
        
        dones = {name: done for name in self.agents.keys()}
        
        self.replay_buffer.add(states, actions, boosted_rewards, next_states, dones)
    
    def train_step(self, batch_size: int = 64):
        """
        One training step for all agents
        
        MADDPG update:
        1. Sample batch from replay buffer
        2. Update each agent's critic (centralized)
        3. Update each agent's actor (decentralized objective)
        4. Soft update target networks
        """
        if len(self.replay_buffer) < batch_size:
            return
        
        if not TORCH_AVAILABLE:
            return
        
        batch = self.replay_buffer.sample(batch_size)
        
        for agent_name, agent in self.agents.items():
            # Skip if no actor
            if not hasattr(agent, 'actor'):
                continue
            
            # Prepare batch data
            states_batch = []
            actions_batch = []
            rewards_batch = []
            next_states_batch = []
            
            for states, actions, rewards, next_states, dones in batch:
                # Flatten all agent states
                all_states = np.concatenate([states[n] for n in self.agents.keys()])
                all_actions = np.concatenate([actions[n] for n in self.agents.keys()])
                all_next_states = np.concatenate([next_states[n] for n in self.agents.keys()])
                
                states_batch.append(all_states)
                actions_batch.append(all_actions)
                rewards_batch.append(rewards[agent_name])
                next_states_batch.append(all_next_states)
            
            states_tensor = torch.FloatTensor(states_batch)
            actions_tensor = torch.FloatTensor(actions_batch)
            rewards_tensor = torch.FloatTensor(rewards_batch).unsqueeze(1)
            next_states_tensor = torch.FloatTensor(next_states_batch)
            
            # Update critic
            with torch.no_grad():
                # Get target actions from all agents
                next_actions_list = []
                for i, (name, ag) in enumerate(self.agents.items()):
                    if hasattr(ag, 'actor_target'):
                        ns = next_states_tensor[:, i*self.state_dim:(i+1)*self.state_dim]
                        na = ag.actor_target(ns)
                        next_actions_list.append(na)
                    else:
                        next_actions_list.append(torch.zeros(batch_size, self.action_dim))
                
                next_actions = torch.cat(next_actions_list, dim=1)
                target_q = self.critic_targets[agent_name](next_states_tensor, next_actions)
                y = rewards_tensor + self.gamma * target_q
            
            current_q = self.critics[agent_name](states_tensor, actions_tensor)
            critic_loss = nn.MSELoss()(current_q, y)
            
            self.critic_optimizers[agent_name].zero_grad()
            critic_loss.backward()
            nn.utils.clip_grad_norm_(self.critics[agent_name].parameters(), 1.0)
            self.critic_optimizers[agent_name].step()
            
            # Update actor
            # Get current agent's action, keep others fixed
            agent_idx = list(self.agents.keys()).index(agent_name)
            agent_state = states_tensor[:, agent_idx*self.state_dim:(agent_idx+1)*self.state_dim]
            current_action = agent.actor(agent_state)
            
            # Reconstruct all actions with updated agent action
            new_actions = actions_tensor.clone()
            new_actions[:, agent_idx*self.action_dim:(agent_idx+1)*self.action_dim] = current_action
            
            actor_loss = -self.critics[agent_name](states_tensor, new_actions).mean()
            
            agent.actor_optimizer.zero_grad()
            actor_loss.backward()
            nn.utils.clip_grad_norm_(agent.actor.parameters(), 1.0)
            agent.actor_optimizer.step()
            
            # Soft update targets
            for target_param, param in zip(
                self.critic_targets[agent_name].parameters(),
                self.critics[agent_name].parameters()
            ):
                target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)
            
            for target_param, param in zip(
                agent.actor_target.parameters(),
                agent.actor.parameters()
            ):
                target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)
        
        self.training_steps += 1
    
    def get_all_stats(self) -> List[Dict]:
        """Get statistics for all agents"""
        return [agent.get_stats() for agent in self.agents.values()]
    
    def save(self, path: str):
        """Save all models"""
        if not TORCH_AVAILABLE:
            return
        
        state = {
            "training_steps": self.training_steps,
            "agents": {}
        }
        
        for name, agent in self.agents.items():
            if hasattr(agent, 'actor'):
                state["agents"][name] = {
                    "actor": agent.actor.state_dict(),
                    "stats": agent.get_stats()
                }
        
        torch.save(state, f"{path}/maddpg_trader.pt")
    
    def load(self, path: str):
        """Load all models"""
        if not TORCH_AVAILABLE:
            return
        
        try:
            state = torch.load(f"{path}/maddpg_trader.pt")
            self.training_steps = state.get("training_steps", 0)
            
            for name, agent_state in state.get("agents", {}).items():
                if name in self.agents and hasattr(self.agents[name], 'actor'):
                    self.agents[name].actor.load_state_dict(agent_state["actor"])
        except:
            pass


# Singleton
_maddpg_trader = None

def get_maddpg_trader() -> MADDPGTrader:
    global _maddpg_trader
    if _maddpg_trader is None:
        _maddpg_trader = MADDPGTrader()
    return _maddpg_trader


# Test
if __name__ == "__main__":
    print(f"PyTorch available: {TORCH_AVAILABLE}")
    
    # Create trader
    trader = MADDPGTrader()
    
    # Create sample market state
    np.random.seed(42)
    prices = 50000 * np.exp(np.cumsum(0.001 + 0.02 * np.random.randn(100)))
    
    market_state = MarketState(
        prices=prices,
        volumes=np.random.randint(100000, 1000000, 100),
        returns=np.diff(np.log(prices)),
        volatility=0.02,
        trend=0.3,
        regime="TRENDING",
        sentiment=0.5
    )
    
    # Get action
    action, all_actions = trader.get_ensemble_action(market_state)
    
    print("\n=== MADDPG TRADER TEST ===")
    print(f"Final Action: {action.action_type}")
    print(f"Quantity: {action.quantity_pct:+.2%}")
    print(f"Confidence: {action.confidence:.2%}")
    print(f"\nAgent Actions:")
    for name, act in all_actions.items():
        print(f"  {name}: {act[0]:+.3f}")
    
    print(f"\nAgent Stats:")
    for stat in trader.get_all_stats():
        print(f"  {stat['name']}: WR={stat['win_rate']:.0%}")
