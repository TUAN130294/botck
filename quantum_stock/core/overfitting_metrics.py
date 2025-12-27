# -*- coding: utf-8 -*-
"""
Overfitting Metrics Module
Critical for validating backtest results

Features:
- PSR (Probabilistic Sharpe Ratio)
- DSR (Deflated Sharpe Ratio)
- PBO (Probability of Backtest Overfitting)
- In-Sample vs Out-of-Sample degradation analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


@dataclass
class OverfittingMetrics:
    """Comprehensive overfitting analysis results"""
    psr: float  # Probabilistic Sharpe Ratio
    psr_threshold: float  # Threshold for significance
    psr_passed: bool
    
    dsr: float  # Deflated Sharpe Ratio
    dsr_haircut: float  # Haircut applied
    
    pbo: float  # Probability of Backtest Overfitting
    pbo_is_overfit: bool
    
    is_oos_degradation: float  # IS vs OOS degradation %
    robustness_score: float  # 0-100
    
    recommendation: str
    
    def to_dict(self) -> Dict:
        return {
            'psr': self.psr,
            'psr_threshold': self.psr_threshold,
            'psr_passed': self.psr_passed,
            'dsr': self.dsr,
            'dsr_haircut': self.dsr_haircut,
            'pbo': self.pbo,
            'pbo_is_overfit': self.pbo_is_overfit,
            'is_oos_degradation': self.is_oos_degradation,
            'robustness_score': self.robustness_score,
            'recommendation': self.recommendation
        }
    
    def get_summary(self) -> str:
        status = "✅ PASSED" if self.robustness_score >= 60 else "⚠️ CAUTION" if self.robustness_score >= 40 else "❌ HIGH RISK"
        return f"""
╔══════════════════════════════════════════════════════════════╗
║                  OVERFITTING ANALYSIS                        ║
╠══════════════════════════════════════════════════════════════╣
║ Status: {status:52}║
╠══════════════════════════════════════════════════════════════╣
║ Probabilistic Sharpe Ratio (PSR)                             ║
║   Value: {self.psr:.2%}  Threshold: {self.psr_threshold:.2%}  {"PASS ✓" if self.psr_passed else "FAIL ✗":>12}║
╠══════════════════════════════════════════════════════════════╣
║ Deflated Sharpe Ratio (DSR)                                  ║
║   Original SR → DSR: {self.dsr:.3f}  Haircut: {self.dsr_haircut:.1%}              ║
╠══════════════════════════════════════════════════════════════╣
║ Probability of Backtest Overfitting (PBO)                    ║
║   Value: {self.pbo:.1%}  {"LIKELY OVERFIT" if self.pbo_is_overfit else "ACCEPTABLE":>20}                   ║
╠══════════════════════════════════════════════════════════════╣
║ IS vs OOS Degradation: {self.is_oos_degradation:+.1%}                              ║
║ Robustness Score: {self.robustness_score:.0f}/100                                   ║
╠══════════════════════════════════════════════════════════════╣
║ Recommendation: {self.recommendation:43}║
╚══════════════════════════════════════════════════════════════╝
"""


class OverfittingAnalyzer:
    """
    Advanced overfitting detection for backtesting
    """
    
    @staticmethod
    def probabilistic_sharpe_ratio(
        returns: pd.Series,
        benchmark_sr: float = 0.0,
        frequency: str = 'daily'
    ) -> Tuple[float, float, bool]:
        """
        Calculate Probabilistic Sharpe Ratio (PSR)
        
        PSR measures the probability that the measured Sharpe Ratio
        is greater than the benchmark Sharpe Ratio.
        
        Args:
            returns: Return series
            benchmark_sr: Benchmark Sharpe Ratio to beat
            frequency: 'daily', 'weekly', 'monthly'
            
        Returns:
            Tuple of (PSR value, threshold, passed)
        """
        if len(returns) < 30:
            return 0.5, 0.95, False
        
        # Annualization factor
        ann_factor = {
            'daily': 252,
            'weekly': 52,
            'monthly': 12
        }.get(frequency, 252)
        
        # Calculate Sharpe Ratio
        mean_return = returns.mean()
        std_return = returns.std()
        
        if std_return == 0:
            return 0.5, 0.95, False
        
        sr = mean_return / std_return * np.sqrt(ann_factor)
        
        # Calculate skewness and kurtosis
        skew = returns.skew()
        kurt = returns.kurtosis()
        
        n = len(returns)
        
        # Standard error of Sharpe Ratio
        sr_std = np.sqrt(
            (1 + 0.25 * sr**2 - skew * sr + (kurt - 3) / 4 * sr**2) / (n - 1)
        )
        
        # PSR: probability that true SR > benchmark
        if sr_std > 0:
            z_score = (sr - benchmark_sr) / sr_std
            psr = stats.norm.cdf(z_score)
        else:
            psr = 0.5
        
        threshold = 0.95  # 95% confidence
        passed = psr >= threshold
        
        return psr, threshold, passed
    
    @staticmethod
    def deflated_sharpe_ratio(
        returns: pd.Series,
        num_trials: int = 1,
        frequency: str = 'daily'
    ) -> Tuple[float, float]:
        """
        Calculate Deflated Sharpe Ratio (DSR)
        
        DSR adjusts the Sharpe Ratio for multiple testing bias.
        When you test many strategies, some will appear profitable by chance.
        
        Args:
            returns: Return series
            num_trials: Number of strategy variations tested
            frequency: Return frequency
            
        Returns:
            Tuple of (DSR, haircut percentage)
        """
        if len(returns) < 30:
            return 0.0, 1.0
        
        ann_factor = {'daily': 252, 'weekly': 52, 'monthly': 12}.get(frequency, 252)
        
        mean_return = returns.mean()
        std_return = returns.std()
        
        if std_return == 0:
            return 0.0, 1.0
        
        sr = mean_return / std_return * np.sqrt(ann_factor)
        n = len(returns)
        
        # Expected maximum Sharpe under null (multiple testing correction)
        # Using Euler-Mascheroni constant approximation
        euler_mascheroni = 0.5772
        
        if num_trials > 1:
            expected_max_sr = np.sqrt(2 * np.log(num_trials)) - \
                              (np.log(np.log(num_trials)) + np.log(4 * np.pi) - 2 * euler_mascheroni) / \
                              (2 * np.sqrt(2 * np.log(num_trials)))
        else:
            expected_max_sr = 0
        
        # Deflated Sharpe Ratio
        dsr = sr - expected_max_sr * np.sqrt(1 / n)
        
        # Haircut (reduction from original)
        if sr != 0:
            haircut = (sr - dsr) / abs(sr)
        else:
            haircut = 0
        
        return max(0, dsr), haircut
    
    @staticmethod
    def probability_of_backtest_overfitting(
        in_sample_returns: List[pd.Series],
        out_of_sample_returns: List[pd.Series],
        n_simulations: int = 1000
    ) -> Tuple[float, bool]:
        """
        Calculate Probability of Backtest Overfitting (PBO)
        
        PBO estimates the probability that the best in-sample strategy
        will underperform out-of-sample.
        
        Args:
            in_sample_returns: List of IS returns for each fold
            out_of_sample_returns: List of OOS returns for each fold
            n_simulations: Number of CSCV iterations
            
        Returns:
            Tuple of (PBO probability, is_overfit flag)
        """
        if len(in_sample_returns) < 2 or len(out_of_sample_returns) < 2:
            return 0.5, False
        
        # Calculate Sharpe for each fold
        is_sharpes = []
        oos_sharpes = []
        
        for is_ret, oos_ret in zip(in_sample_returns, out_of_sample_returns):
            if len(is_ret) > 0 and is_ret.std() > 0:
                is_sr = is_ret.mean() / is_ret.std() * np.sqrt(252)
                is_sharpes.append(is_sr)
            else:
                is_sharpes.append(0)
            
            if len(oos_ret) > 0 and oos_ret.std() > 0:
                oos_sr = oos_ret.mean() / oos_ret.std() * np.sqrt(252)
                oos_sharpes.append(oos_sr)
            else:
                oos_sharpes.append(0)
        
        is_sharpes = np.array(is_sharpes)
        oos_sharpes = np.array(oos_sharpes)
        
        # Rank correlation between IS and OOS performance
        if len(is_sharpes) >= 2:
            # Spearman rank correlation
            is_ranks = stats.rankdata(is_sharpes)
            oos_ranks = stats.rankdata(oos_sharpes)
            
            # Calculate how often best IS underperforms median OOS
            best_is_idx = np.argmax(is_sharpes)
            best_is_oos = oos_sharpes[best_is_idx]
            median_oos = np.median(oos_sharpes)
            
            # Simple PBO estimate
            underperform_count = sum(1 for sr in oos_sharpes if sr > best_is_oos)
            pbo = underperform_count / len(oos_sharpes)
        else:
            pbo = 0.5
        
        is_overfit = pbo > 0.5
        
        return pbo, is_overfit
    
    @staticmethod
    def is_oos_degradation(
        in_sample_sharpe: float,
        out_of_sample_sharpe: float
    ) -> float:
        """
        Calculate degradation from in-sample to out-of-sample
        
        Returns:
            Degradation percentage (negative means OOS worse than IS)
        """
        if in_sample_sharpe == 0:
            return 0.0
        
        degradation = (out_of_sample_sharpe - in_sample_sharpe) / abs(in_sample_sharpe)
        return degradation
    
    @staticmethod
    def analyze(
        returns: pd.Series,
        in_sample_returns: pd.Series = None,
        out_of_sample_returns: pd.Series = None,
        num_trials: int = 1,
        fold_is_returns: List[pd.Series] = None,
        fold_oos_returns: List[pd.Series] = None,
        frequency: str = 'daily'
    ) -> OverfittingMetrics:
        """
        Comprehensive overfitting analysis
        
        Args:
            returns: Full return series
            in_sample_returns: In-sample period returns
            out_of_sample_returns: Out-of-sample period returns
            num_trials: Number of parameter combinations tested
            fold_is_returns: List of IS returns per fold (for PBO)
            fold_oos_returns: List of OOS returns per fold (for PBO)
            frequency: Return frequency
            
        Returns:
            OverfittingMetrics with comprehensive analysis
        """
        # 1. PSR
        psr, psr_threshold, psr_passed = OverfittingAnalyzer.probabilistic_sharpe_ratio(
            returns, benchmark_sr=0.0, frequency=frequency
        )
        
        # 2. DSR
        dsr, dsr_haircut = OverfittingAnalyzer.deflated_sharpe_ratio(
            returns, num_trials=num_trials, frequency=frequency
        )
        
        # 3. PBO
        if fold_is_returns and fold_oos_returns:
            pbo, pbo_is_overfit = OverfittingAnalyzer.probability_of_backtest_overfitting(
                fold_is_returns, fold_oos_returns
            )
        else:
            pbo, pbo_is_overfit = 0.3, False  # Default if no fold data
        
        # 4. IS vs OOS degradation
        if in_sample_returns is not None and out_of_sample_returns is not None:
            is_sr = in_sample_returns.mean() / in_sample_returns.std() * np.sqrt(252) \
                    if len(in_sample_returns) > 0 and in_sample_returns.std() > 0 else 0
            oos_sr = out_of_sample_returns.mean() / out_of_sample_returns.std() * np.sqrt(252) \
                     if len(out_of_sample_returns) > 0 and out_of_sample_returns.std() > 0 else 0
            degradation = OverfittingAnalyzer.is_oos_degradation(is_sr, oos_sr)
        else:
            degradation = 0.0
        
        # 5. Robustness Score
        robustness = OverfittingAnalyzer._calculate_robustness_score(
            psr, psr_passed, dsr, pbo, degradation
        )
        
        # 6. Recommendation
        recommendation = OverfittingAnalyzer._get_recommendation(
            robustness, psr_passed, pbo_is_overfit, degradation
        )
        
        return OverfittingMetrics(
            psr=psr,
            psr_threshold=psr_threshold,
            psr_passed=psr_passed,
            dsr=dsr,
            dsr_haircut=dsr_haircut,
            pbo=pbo,
            pbo_is_overfit=pbo_is_overfit,
            is_oos_degradation=degradation,
            robustness_score=robustness,
            recommendation=recommendation
        )
    
    @staticmethod
    def _calculate_robustness_score(
        psr: float,
        psr_passed: bool,
        dsr: float,
        pbo: float,
        degradation: float
    ) -> float:
        """Calculate overall robustness score 0-100"""
        score = 0.0
        
        # PSR component (25 points)
        score += psr * 25
        if psr_passed:
            score += 5
        
        # DSR component (25 points)
        dsr_score = min(dsr * 10, 25)
        score += dsr_score
        
        # PBO component (25 points) - lower is better
        pbo_score = (1 - pbo) * 25
        score += pbo_score
        
        # Degradation component (25 points)
        if degradation >= 0:
            deg_score = 25  # No degradation
        elif degradation >= -0.2:
            deg_score = 20  # Mild degradation
        elif degradation >= -0.5:
            deg_score = 10  # Moderate degradation
        else:
            deg_score = 0   # Severe degradation
        score += deg_score
        
        return min(100, max(0, score))
    
    @staticmethod
    def _get_recommendation(
        robustness: float,
        psr_passed: bool,
        pbo_is_overfit: bool,
        degradation: float
    ) -> str:
        """Generate recommendation based on metrics"""
        if robustness >= 80:
            return "STRONG - Safe for live trading with full size"
        elif robustness >= 60:
            return "GOOD - Start with reduced position size"
        elif robustness >= 40:
            if pbo_is_overfit:
                return "CAUTION - High overfitting risk, re-optimize"
            if degradation < -0.3:
                return "CAUTION - Significant OOS degradation"
            return "MODERATE - Paper trade first"
        else:
            if pbo_is_overfit:
                return "HIGH RISK - Likely curve-fitted, avoid"
            return "POOR - Requires significant improvements"
