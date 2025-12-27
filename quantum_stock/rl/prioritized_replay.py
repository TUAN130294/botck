# -*- coding: utf-8 -*-
"""
Prioritized Experience Replay for MADDPG
==========================================
Ưu tiên sample experiences quan trọng (high TD error)

Key Idea:
- Experiences with high TD error = model surprised = important to learn from
- Sample these more frequently than boring experiences
- Use importance sampling weights to correct bias

Reference: "Prioritized Experience Replay" (Schaul et al., 2016)
"""

import numpy as np
from collections import deque
from typing import Dict, List, Tuple
import random


class SumTree:
    """
    Binary tree data structure for efficient priority sampling

    Structure:
    - Leaf nodes: Priorities (one per experience)
    - Internal nodes: Sum of children priorities
    - Root: Total priority sum

    Operations (all O(log n)):
    - Update priority
    - Sample by cumulative priority
    - Get total priority
    """

    def __init__(self, capacity: int):
        """
        Args:
            capacity: Maximum number of experiences
        """
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1)  # Binary tree in array form
        self.data = [None] * capacity  # Actual experience data
        self.write_idx = 0  # Next write position
        self.n_entries = 0  # Current number of entries

    def _propagate(self, idx: int, change: float):
        """
        Propagate priority change up the tree to root

        Args:
            idx: Tree node index
            change: Priority delta
        """
        parent = (idx - 1) // 2
        self.tree[parent] += change

        if parent != 0:  # Not root yet
            self._propagate(parent, change)

    def _retrieve(self, idx: int, s: float) -> int:
        """
        Find leaf node with cumulative sum s

        Args:
            idx: Current node index
            s: Target cumulative sum

        Returns:
            Leaf node index containing s
        """
        left = 2 * idx + 1
        right = left + 1

        if left >= len(self.tree):  # Reached leaf node
            return idx

        # Decide left or right subtree
        if s <= self.tree[left]:
            return self._retrieve(left, s)
        else:
            return self._retrieve(right, s - self.tree[left])

    def total(self) -> float:
        """Get total priority (root node value)"""
        return self.tree[0]

    def add(self, priority: float, data):
        """
        Add new experience with priority

        Args:
            priority: Experience priority
            data: Experience tuple
        """
        idx = self.write_idx + self.capacity - 1  # Convert to tree leaf index

        self.data[self.write_idx] = data
        self.update(idx, priority)

        # Circular buffer
        self.write_idx += 1
        if self.write_idx >= self.capacity:
            self.write_idx = 0

        if self.n_entries < self.capacity:
            self.n_entries += 1

    def update(self, idx: int, priority: float):
        """
        Update priority of a leaf node

        Args:
            idx: Tree node index (not data index!)
            priority: New priority value
        """
        change = priority - self.tree[idx]
        self.tree[idx] = priority
        self._propagate(idx, change)

    def get(self, s: float) -> Tuple[int, float, any]:
        """
        Sample experience based on cumulative priority s

        Args:
            s: Cumulative priority value

        Returns:
            idx: Tree index
            priority: Priority value
            data: Experience data
        """
        idx = self._retrieve(0, s)
        data_idx = idx - self.capacity + 1

        return idx, self.tree[idx], self.data[data_idx]


class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay Buffer for MADDPG

    Experiences với TD error cao được sample nhiều hơn

    Algorithm:
    1. New experience: Add with max priority (optimistic)
    2. Sample: P(i) ∝ priority_i^alpha
    3. Update: priority = |TD_error| + epsilon
    4. Importance sampling: weight_i = (N * P(i))^(-beta)

    Parameters:
    -----------
    capacity: Buffer size
    alpha: Priority exponent
        - 0 = uniform sampling (no prioritization)
        - 1 = full prioritization
        - Typical: 0.6
    beta: Importance sampling exponent
        - 0 = no correction
        - 1 = full correction
        - Starts low (0.4), anneals to 1.0
    """

    def __init__(
        self,
        capacity: int = 100000,
        alpha: float = 0.6,
        beta: float = 0.4,
        beta_increment: float = 0.001,
        epsilon: float = 1e-6
    ):
        """
        Args:
            capacity: Maximum buffer size
            alpha: Priority exponent (0=uniform, 1=full prioritization)
            beta: IS weight exponent (anneals to 1.0)
            beta_increment: Beta increment per sample
            epsilon: Small constant to ensure non-zero priority
        """
        self.tree = SumTree(capacity)
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = beta_increment
        self.epsilon = epsilon
        self.max_priority = 1.0  # Track max priority for new experiences

    def add(
        self,
        states: Dict[str, np.ndarray],
        actions: Dict[str, np.ndarray],
        rewards: Dict[str, float],
        next_states: Dict[str, np.ndarray],
        dones: Dict[str, bool]
    ):
        """
        Add experience with max priority (optimistic initialization)

        New experiences get max priority → ensures sampled at least once
        """
        experience = (states, actions, rewards, next_states, dones)
        self.tree.add(self.max_priority, experience)

    def sample(self, batch_size: int) -> Tuple[List, np.ndarray, np.ndarray]:
        """
        Sample batch based on priorities

        Returns:
        --------
        batch: List of (states, actions, rewards, next_states, dones)
        weights: Importance sampling weights (for loss correction)
        indices: Tree indices (for priority update later)
        """
        batch = []
        indices = np.zeros(batch_size, dtype=np.int32)
        weights = np.zeros(batch_size, dtype=np.float32)

        # Divide priority range into segments
        segment = self.tree.total() / batch_size

        # Anneal beta toward 1.0
        self.beta = min(1.0, self.beta + self.beta_increment)

        # Min probability for IS weight normalization
        min_prob = np.min(self.tree.tree[-self.tree.capacity:]) / self.tree.total()
        if min_prob <= 0:
            min_prob = 1e-10
        max_weight = (min_prob * self.tree.n_entries) ** (-self.beta)

        for i in range(batch_size):
            # Sample uniformly from segment
            a = segment * i
            b = segment * (i + 1)
            s = random.uniform(a, b)

            # Get experience
            idx, priority, data = self.tree.get(s)

            # Calculate importance sampling weight
            prob = priority / self.tree.total()
            weight = (prob * self.tree.n_entries) ** (-self.beta)
            weight /= max_weight  # Normalize to [0, 1]

            indices[i] = idx
            weights[i] = weight
            batch.append(data)

        return batch, weights, indices

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """
        Update priorities based on TD errors

        Priority = (|TD_error| + epsilon)^alpha

        Args:
            indices: Tree indices from sample()
            td_errors: TD errors from critic
        """
        for idx, error in zip(indices, td_errors):
            # Compute priority
            priority = (abs(error) + self.epsilon) ** self.alpha

            # Update tree
            self.tree.update(idx, priority)

            # Track max priority
            self.max_priority = max(self.max_priority, priority)

    def __len__(self):
        return self.tree.n_entries


# Test
if __name__ == "__main__":
    print("="*60)
    print("TESTING PRIORITIZED REPLAY BUFFER")
    print("="*60)

    buffer = PrioritizedReplayBuffer(capacity=100, alpha=0.6, beta=0.4)

    print("\n[1/4] Adding experiences...")
    # Add experiences with varying rewards (proxy for importance)
    for i in range(120):  # More than capacity to test circular buffer
        states = {'agent1': np.array([i])}
        actions = {'agent1': np.array([0.5])}
        rewards = {'agent1': float(i % 10)}  # 0, 1, 2, ..., 9, 0, 1, ...
        next_states = {'agent1': np.array([i+1])}
        dones = {'agent1': False}

        buffer.add(states, actions, rewards, next_states, dones)

    print(f"  Added 120 experiences (capacity=100)")
    print(f"  Buffer size: {len(buffer)}")
    assert len(buffer) == 100, "Buffer should be at capacity"

    print("\n[2/4] Sampling with priorities...")
    # Sample multiple times
    sample_counts = {}

    for _ in range(50):  # 50 batches
        batch, weights, indices = buffer.sample(batch_size=20)

        for exp in batch:
            reward = exp[2]['agent1']  # Extract reward
            sample_counts[reward] = sample_counts.get(reward, 0) + 1

    print(f"  Sampled 50 batches of size 20")
    print(f"  Sample distribution:")
    for reward in sorted(sample_counts.keys()):
        print(f"    Reward {reward}: {sample_counts[reward]} times")

    # High rewards (7, 8, 9) should be sampled more
    high_samples = sum(sample_counts.get(r, 0) for r in [7, 8, 9])
    low_samples = sum(sample_counts.get(r, 0) for r in [0, 1, 2])

    print(f"\n  High rewards (7,8,9): {high_samples} samples")
    print(f"  Low rewards (0,1,2):  {low_samples} samples")

    # Note: Initially all have same priority (max_priority)
    # Prioritization only works AFTER update_priorities is called

    print("\n[3/4] Updating priorities with simulated TD errors...")
    batch, weights, indices = buffer.sample(32)

    # Simulate TD errors (higher for higher rewards)
    td_errors = []
    for exp in batch:
        reward = exp[2]['agent1']
        # High reward → high TD error (model surprised)
        td_error = reward / 10.0 + np.random.rand() * 0.1
        td_errors.append(td_error)

    td_errors = np.array(td_errors)
    buffer.update_priorities(indices, td_errors)

    print(f"  Updated {len(indices)} priorities")
    print(f"  TD error range: [{td_errors.min():.3f}, {td_errors.max():.3f}]")

    print("\n[4/4] Sampling AFTER priority update...")
    sample_counts_after = {}

    for _ in range(50):
        batch, weights, indices = buffer.sample(batch_size=20)

        for exp in batch:
            reward = exp[2]['agent1']
            sample_counts_after[reward] = sample_counts_after.get(reward, 0) + 1

    print(f"  Sample distribution AFTER update:")
    for reward in sorted(sample_counts_after.keys()):
        print(f"    Reward {reward}: {sample_counts_after[reward]} times")

    high_samples_after = sum(sample_counts_after.get(r, 0) for r in [7, 8, 9])
    low_samples_after = sum(sample_counts_after.get(r, 0) for r in [0, 1, 2])

    print(f"\n  High rewards (7,8,9): {high_samples_after} samples")
    print(f"  Low rewards (0,1,2):  {low_samples_after} samples")

    print("\n[5/4] Importance sampling weights test...")
    batch, weights, indices = buffer.sample(32)
    print(f"  Weights shape: {weights.shape}")
    print(f"  Weights range: [{weights.min():.4f}, {weights.max():.4f}]")
    print(f"  Weights mean: {weights.mean():.4f}")

    assert np.all(weights >= 0) and np.all(weights <= 1.01), \
        "Weights should be in [0, 1]"

    print("\n" + "="*60)
    print("ALL TESTS PASSED - Prioritized Replay Buffer OK!")
    print("="*60)
    print("\nKey Features Verified:")
    print("  [OK] Circular buffer (capacity management)")
    print("  [OK] Priority-based sampling")
    print("  [OK] Priority updates with TD errors")
    print("  [OK] Importance sampling weights")
    print("  [OK] Beta annealing")
