# -*- coding: utf-8 -*-
"""
Advanced Agent Weight Optimization
====================================
Tính agent weights dựa trên nhiều yếu tố:

1. Magnitude-weighted accuracy (không chỉ binary đúng/sai)
2. Confidence scores (agent tự tin cao hơn → trọng số cao hơn nếu đúng)
3. Time decay (tín hiệu gần đây quan trọng hơn)
4. Regime-specific weights (bull/bear/sideways markets khác nhau)
5. Ensemble diversity (agent khác biệt → portfolio mạnh hơn)

Old Method (WRONG):
-------------------
if prediction_correct:
    accuracy += 1  # Binary: 0.1% lợi nhuận = 10% lợi nhuận!

New Method (CORRECT):
--------------------
score = confidence * directional_accuracy * magnitude * time_weight
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
from collections import defaultdict
# Fallback logging
try:
    from loguru import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class AdvancedAgentWeightOptimizer:
    """
    Optimize agent weights với multiple sophisticated factors
    """

    def __init__(
        self,
        time_decay_halflife: int = 90,  # 90 days
        min_weight: float = 0.1,
        max_weight: float = 3.0
    ):
        """
        Args:
            time_decay_halflife: Tín hiệu cũ hơn X ngày có weight = 50%
            min_weight: Min agent weight (tránh weight = 0)
            max_weight: Max agent weight (tránh quá lệch)
        """
        self.time_decay_halflife = time_decay_halflife
        self.min_weight = min_weight
        self.max_weight = max_weight

    def calculate_magnitude_weighted_accuracy(
        self,
        signals: List[Dict],
        outcomes: List[float],
        dates: List[datetime]
    ) -> Dict[str, float]:
        """
        Tính accuracy có tính đến magnitude + confidence + time

        Formula:
        --------
        score = Σ(confidence × correct × magnitude × time_weight)

        Where:
        - confidence: Agent's confidence [0, 1]
        - correct: +1 if direction right, -1 if wrong
        - magnitude: |outcome| / 5 (capped at 2x)
        - time_weight: exp(-days_ago / halflife)

        Args:
            signals: List of {action, confidence}
            outcomes: List of actual returns (%)
            dates: List of signal dates

        Returns:
            Dict with score, signal count, etc.
        """
        total_score = 0.0
        total_weight = 0.0
        correct_count = 0
        current_date = datetime.now()

        for signal, outcome, date in zip(signals, outcomes, dates):
            # Time decay
            days_ago = (current_date - date).days
            time_weight = np.exp(-days_ago / self.time_decay_halflife)

            # Directional accuracy
            predicted_direction = 1 if signal['action'] == 'BUY' else -1
            actual_direction = 1 if outcome > 0 else -1
            directional_correct = (predicted_direction == actual_direction)

            # Magnitude factor (cap at 2x)
            magnitude_factor = min(abs(outcome) / 5.0, 2.0)

            # Confidence (default 0.5 nếu không có)
            confidence = signal.get('confidence', 0.5)

            # Calculate score
            if directional_correct:
                score = confidence * magnitude_factor * time_weight
                correct_count += 1
            else:
                # Penalty for confident wrong predictions
                score = -confidence * time_weight

            total_score += score
            total_weight += time_weight

        # Normalized score
        if total_weight > 0:
            normalized_score = total_score / total_weight
        else:
            normalized_score = 0.0

        # Simple accuracy for reference
        simple_accuracy = correct_count / len(signals) if len(signals) > 0 else 0.0

        return {
            'score': normalized_score,
            'simple_accuracy': simple_accuracy,
            'total_signals': len(signals),
            'correct_signals': correct_count,
            'total_weight': total_weight
        }

    def calculate_regime_specific_weights(
        self,
        historical_signals: Dict[str, List[Dict]],
        actual_outcomes: List[float],
        market_regimes: List[str],
        dates: List[datetime]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate weights cho từng market regime

        Idea: Momentum agent tốt trong bull, mean reversion tốt trong sideways

        Args:
            historical_signals: {agent_id: [signals]}
            actual_outcomes: List of returns
            market_regimes: List of regime labels (BULL/BEAR/SIDEWAYS)
            dates: List of dates

        Returns:
            {
                'BULL': {'agent1': 1.5, 'agent2': 0.8, ...},
                'BEAR': {'agent1': 0.7, 'agent2': 1.8, ...},
                'SIDEWAYS': {...}
            }
        """
        regime_weights = {}
        unique_regimes = set(market_regimes)

        logger.info(f"Calculating regime-specific weights for {len(unique_regimes)} regimes")

        for regime in unique_regimes:
            # Filter signals for this regime
            regime_indices = [i for i, r in enumerate(market_regimes) if r == regime]

            if len(regime_indices) < 10:  # Need minimum data
                logger.warning(f"  Skipping {regime}: only {len(regime_indices)} samples")
                continue

            regime_outcomes = [actual_outcomes[i] for i in regime_indices]
            regime_dates = [dates[i] for i in regime_indices]

            agent_scores = {}

            for agent_id, all_signals in historical_signals.items():
                # Filter agent signals for this regime
                regime_signals = [all_signals[i] for i in regime_indices if i < len(all_signals)]

                if len(regime_signals) > 0:
                    metrics = self.calculate_magnitude_weighted_accuracy(
                        regime_signals,
                        regime_outcomes[:len(regime_signals)],
                        regime_dates[:len(regime_signals)]
                    )
                    agent_scores[agent_id] = metrics['score']
                else:
                    agent_scores[agent_id] = 0.0

            # Normalize scores to weights
            regime_weights[regime] = self._scores_to_weights(agent_scores)

            logger.info(f"  {regime}: {len(regime_indices)} samples")

        return regime_weights

    def calculate_diversity_adjusted_weights(
        self,
        historical_signals: Dict[str, List[Dict]],
        base_weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Adjust weights to promote ensemble diversity

        Idea: Agent giống nhau → dư thừa → giảm weight
              Agent khác biệt → bổ sung → tăng weight

        Formula:
        --------
        diversity_factor = 1 + (1 - avg_correlation) × 0.3

        Args:
            historical_signals: {agent_id: [signals]}
            base_weights: {agent_id: base_weight}

        Returns:
            {agent_id: diversity_adjusted_weight}
        """
        agent_ids = list(historical_signals.keys())
        n_agents = len(agent_ids)

        if n_agents < 2:
            return base_weights

        # Calculate pairwise correlations
        correlations = np.zeros((n_agents, n_agents))

        for i, agent_i in enumerate(agent_ids):
            signals_i = [1 if s['action'] == 'BUY' else -1
                        for s in historical_signals[agent_i]]

            for j, agent_j in enumerate(agent_ids):
                if i != j:
                    signals_j = [1 if s['action'] == 'BUY' else -1
                                for s in historical_signals[agent_j]]

                    # Handle different lengths
                    min_len = min(len(signals_i), len(signals_j))
                    if min_len > 10:
                        try:
                            corr = np.corrcoef(
                                signals_i[:min_len],
                                signals_j[:min_len]
                            )[0, 1]
                            correlations[i, j] = corr
                        except:
                            correlations[i, j] = 0.0

        # Diversity bonus
        diversity_adjusted = {}

        for i, agent_id in enumerate(agent_ids):
            # Average absolute correlation with other agents
            avg_corr = np.mean(np.abs(correlations[i, :]))

            # Diversity factor: Lower correlation = Higher weight
            # correlation=0 → factor=1.3 (30% bonus)
            # correlation=1 → factor=1.0 (no bonus)
            diversity_factor = 1.0 + (1.0 - avg_corr) * 0.3

            diversity_adjusted[agent_id] = base_weights[agent_id] * diversity_factor

        # Normalize weights
        total = sum(diversity_adjusted.values())
        if total > 0:
            for agent_id in diversity_adjusted:
                diversity_adjusted[agent_id] /= total

        return diversity_adjusted

    def _scores_to_weights(self, scores: Dict[str, float]) -> Dict[str, float]:
        """
        Convert raw scores to weights in [min_weight, max_weight]

        Uses min-max normalization then rescaling
        """
        if not scores:
            return {}

        min_score = min(scores.values())
        max_score = max(scores.values())

        weights = {}

        for agent_id, score in scores.items():
            if max_score > min_score:
                # Normalize to [0, 1]
                normalized = (score - min_score) / (max_score - min_score)
            else:
                normalized = 0.5

            # Map to [min_weight, max_weight]
            weight = self.min_weight + normalized * (self.max_weight - self.min_weight)
            weights[agent_id] = weight

        return weights

    def optimize_weights(
        self,
        historical_signals: Dict[str, List[Dict]],
        actual_outcomes: List[float],
        dates: List[datetime],
        market_regimes: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Main optimization function - tính tất cả weights

        Args:
            historical_signals: {agent_id: [{action, confidence}, ...]}
            actual_outcomes: [return_%, ...]
            dates: [datetime, ...]
            market_regimes: ['BULL', 'BEAR', 'SIDEWAYS', ...] (optional)

        Returns:
            {
                'global_weights': {agent_id: weight},
                'regime_weights': {regime: {agent_id: weight}},
                'diversity_adjusted_weights': {agent_id: weight},
                'metadata': {...}
            }
        """
        logger.info("="*60)
        logger.info("ADVANCED AGENT WEIGHT OPTIMIZATION")
        logger.info("="*60)

        # 1. Calculate base weights (magnitude + confidence + time decay)
        logger.info("\n[1/4] Calculating magnitude-weighted scores...")
        base_weights = {}
        agent_metrics = {}

        for agent_id, signals in historical_signals.items():
            metrics = self.calculate_magnitude_weighted_accuracy(
                signals,
                actual_outcomes[:len(signals)],
                dates[:len(signals)]
            )
            base_weights[agent_id] = metrics['score']
            agent_metrics[agent_id] = metrics

            logger.info(
                f"  {agent_id}: "
                f"score={metrics['score']:.3f}, "
                f"accuracy={metrics['simple_accuracy']:.1%}, "
                f"signals={metrics['total_signals']}"
            )

        global_weights = self._scores_to_weights(base_weights)

        # 2. Calculate regime-specific weights (if regimes provided)
        logger.info("\n[2/4] Calculating regime-specific weights...")
        regime_weights = {}
        if market_regimes:
            regime_weights = self.calculate_regime_specific_weights(
                historical_signals,
                actual_outcomes,
                market_regimes,
                dates
            )
        else:
            logger.info("  Skipped (no regime data provided)")

        # 3. Diversity adjustment
        logger.info("\n[3/4] Calculating diversity-adjusted weights...")
        diversity_weights = self.calculate_diversity_adjusted_weights(
            historical_signals,
            global_weights
        )

        for agent_id in diversity_weights:
            logger.info(
                f"  {agent_id}: "
                f"base={global_weights[agent_id]:.3f} → "
                f"diversity={diversity_weights[agent_id]:.3f}"
            )

        # 4. Compile results
        logger.info("\n[4/4] Compiling results...")
        results = {
            'global_weights': global_weights,
            'regime_weights': regime_weights,
            'diversity_adjusted_weights': diversity_weights,
            'agent_metrics': agent_metrics,
            'metadata': {
                'n_agents': len(historical_signals),
                'n_signals': len(actual_outcomes),
                'date_range': f"{min(dates)} to {max(dates)}",
                'time_decay_halflife': self.time_decay_halflife,
                'has_regimes': market_regimes is not None,
                'timestamp': datetime.now().isoformat()
            }
        }

        logger.info("\n" + "="*60)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info("="*60)

        return results

    def save_weights(self, weights_dict: Dict, filepath: str):
        """Save weights to JSON"""
        # Convert numpy types to Python types
        def convert(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        # Deep convert
        import copy
        weights_copy = copy.deepcopy(weights_dict)

        def recursive_convert(d):
            if isinstance(d, dict):
                return {k: recursive_convert(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [recursive_convert(v) for v in d]
            else:
                return convert(d)

        weights_converted = recursive_convert(weights_copy)

        with open(filepath, 'w') as f:
            json.dump(weights_converted, f, indent=2)

        logger.info(f"Weights saved to {filepath}")

    def load_weights(self, filepath: str) -> Dict:
        """Load weights from JSON"""
        with open(filepath, 'r') as f:
            return json.load(f)


# Example usage and test
if __name__ == "__main__":
    print("="*60)
    print("TESTING ADVANCED AGENT WEIGHT OPTIMIZER")
    print("="*60)

    # Sample data
    np.random.seed(42)

    n_days = 200
    dates = [datetime.now() - timedelta(days=i) for i in range(n_days, 0, -1)]

    # Create historical signals (3 agents with different strategies)
    historical_signals = {
        'momentum': [
            {
                'action': 'BUY' if np.random.rand() > 0.4 else 'SELL',
                'confidence': 0.5 + np.random.rand() * 0.5
            }
            for _ in range(n_days)
        ],
        'mean_reversion': [
            {
                'action': 'BUY' if np.random.rand() > 0.5 else 'SELL',
                'confidence': 0.3 + np.random.rand() * 0.4
            }
            for _ in range(n_days)
        ],
        'news': [
            {
                'action': 'BUY' if np.random.rand() > 0.45 else 'SELL',
                'confidence': 0.6 + np.random.rand() * 0.3
            }
            for _ in range(n_days)
        ]
    }

    # Actual outcomes (returns in %)
    actual_outcomes = np.random.randn(n_days) * 5

    # Market regimes
    market_regimes = []
    for i in range(n_days):
        if i < 70:
            market_regimes.append('BULL')
        elif i < 140:
            market_regimes.append('BEAR')
        else:
            market_regimes.append('SIDEWAYS')

    # Optimize
    optimizer = AdvancedAgentWeightOptimizer(time_decay_halflife=90)

    results = optimizer.optimize_weights(
        historical_signals,
        actual_outcomes,
        dates,
        market_regimes
    )

    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)

    print("\nGlobal Weights:")
    for agent, weight in results['global_weights'].items():
        print(f"  {agent:20s}: {weight:.3f}")

    if results['regime_weights']:
        print("\nRegime-Specific Weights:")
        for regime, weights in results['regime_weights'].items():
            print(f"  {regime}:")
            for agent, weight in weights.items():
                print(f"    {agent:18s}: {weight:.3f}")

    print("\nDiversity-Adjusted Weights:")
    for agent, weight in results['diversity_adjusted_weights'].items():
        print(f"  {agent:20s}: {weight:.3f}")

    # Save
    optimizer.save_weights(results, 'test_agent_weights.json')
    print("\n[OK] Weights saved to test_agent_weights.json")

    print("\n" + "="*60)
    print("TEST COMPLETE - Advanced Agent Weights OK!")
    print("="*60)
