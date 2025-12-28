# -*- coding: utf-8 -*-
"""
Model Prediction Scanner
=========================
Scan 102 stocks với Stockformer models để tìm cơ hội trading

Path A: Model-based opportunity detection
- Load 100 trained Stockformer models
- Predict all stocks every 3 minutes
- Filter: Only trigger agents when REAL opportunity found
- Criteria: Expected return > 3% AND Confidence > 0.7
"""

import asyncio
import pandas as pd
import numpy as np
import torch
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)

# Import Stockformer
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from quantum_stock.models.stockformer import StockformerPredictor
from enhanced_features_simple import calculate_vn_market_features_simple, normalize_features_simple


@dataclass
class ModelPrediction:
    """Prediction result from Stockformer model"""
    symbol: str
    timestamp: datetime

    # Price prediction
    current_price: float
    predicted_prices: List[float]  # Next 5 days
    expected_return_5d: float  # Expected return in 5 days (%)

    # Model confidence
    confidence: float  # 0-1
    direction: str  # UP, DOWN, SIDEWAYS

    # Signal
    has_opportunity: bool
    signal_strength: float  # 0-1

    # Context
    model_path: str
    features_used: int

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'current_price': self.current_price,
            'predicted_prices': self.predicted_prices,
            'expected_return_5d': self.expected_return_5d,
            'confidence': self.confidence,
            'direction': self.direction,
            'has_opportunity': self.has_opportunity,
            'signal_strength': self.signal_strength,
            'model_path': self.model_path,
            'features_used': self.features_used
        }


class ModelPredictionScanner:
    """
    Scanner dùng Stockformer models để tìm cơ hội

    Features:
    - Load 100 trained models (8 PASSED stocks priority)
    - Continuous prediction during market hours
    - Filter opportunities: return > 3%, confidence > 0.7
    - Callback system to trigger agents
    """

    def __init__(
        self,
        model_dir: str = "models",
        data_dir: str = "data/historical",
        passed_stocks_file: str = "PASSED_STOCKS.txt",
        scan_interval: int = 180,  # 3 minutes
        min_return: float = 0.03,  # 3%
        min_confidence: float = 0.7
    ):
        self.model_dir = Path(model_dir)
        self.data_dir = Path(data_dir)
        self.passed_stocks_file = Path(passed_stocks_file)
        self.scan_interval = scan_interval
        self.min_return = min_return
        self.min_confidence = min_confidence

        # Callbacks
        self.on_opportunity_callbacks: List[Callable] = []

        # State
        self.is_running = False
        self.last_scan: Optional[datetime] = None
        self.predictions: Dict[str, ModelPrediction] = {}

        # Load PASSED stocks (priority)
        self.passed_stocks = self._load_passed_stocks()

        # Device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")

    def _load_passed_stocks(self) -> List[str]:
        """Load 8 PASSED stocks from backtest"""
        if not self.passed_stocks_file.exists():
            logger.warning(f"PASSED_STOCKS.txt not found, will scan all")
            return []

        with open(self.passed_stocks_file, 'r') as f:
            stocks = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith('#')
            ]

        logger.info(f"Loaded {len(stocks)} PASSED stocks: {stocks}")
        return stocks

    def add_opportunity_callback(self, callback: Callable):
        """Add callback for opportunity detection"""
        self.on_opportunity_callbacks.append(callback)

    async def start(self):
        """
        Start continuous scanning

        Logic: Scan xong đợt này → nghỉ min_interval → scan tiếp
        (Không overlap, không dùng fixed interval)
        """
        self.is_running = True
        self.min_rest_interval = 60  # Nghỉ tối thiểu 60s giữa các đợt

        logger.info(
            f"Model prediction scanner started\n"
            f"  - Mode: Sequential (scan xong mới scan tiếp)\n"
            f"  - Min rest between scans: {self.min_rest_interval}s\n"
            f"  - Min return: {self.min_return*100}%\n"
            f"  - Min confidence: {self.min_confidence}\n"
            f"  - Total models: ~131 stocks"
        )

        while self.is_running:
            try:
                # Check market hours (9:00-15:00)
                if self._is_market_open():
                    scan_start = datetime.now()

                    # Scan all stocks (blocking until complete)
                    await self.scan_all_stocks()

                    scan_duration = (datetime.now() - scan_start).total_seconds()
                    logger.info(f"⏱️ Scan completed in {scan_duration:.1f}s")

                    # Rest before next scan (minimum rest period)
                    rest_time = max(self.min_rest_interval, 60)
                    logger.info(f"💤 Resting {rest_time}s before next scan...")
                    await asyncio.sleep(rest_time)

                else:
                    logger.info("Market closed, waiting 5 minutes...")
                    await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"Scanner error: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop scanner"""
        self.is_running = False
        logger.info("Model prediction scanner stopped")

    def _is_market_open(self) -> bool:
        """
        Check if VN market is open (9:00-15:00 weekdays)

        Set BYPASS_MARKET_HOURS=true to run 24/7 for testing
        """
        import os

        # Bypass for testing/paper trading
        if os.getenv('BYPASS_MARKET_HOURS', 'false').lower() == 'true':
            logger.debug("Market hours bypassed for testing")
            return True

        now = datetime.now()

        # Weekend
        if now.weekday() >= 5:
            return False

        # Market hours: 9:00-15:00
        market_open = now.replace(hour=9, minute=0, second=0)
        market_close = now.replace(hour=15, minute=0, second=0)

        return market_open <= now <= market_close

    async def scan_all_stocks(self):
        """
        Scan all stocks with models

        Priority order:
        1. PASSED stocks (8 stocks) - higher confidence
        2. All other stocks with models
        """
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info("Starting model prediction scan...")

        # Get all model files
        model_files = list(self.model_dir.glob("*_stockformer_simple_best.pt"))

        # Separate PASSED stocks (priority)
        passed_models = []
        other_models = []

        for model_file in model_files:
            symbol = model_file.stem.replace('_stockformer_simple_best', '')
            if symbol in self.passed_stocks:
                passed_models.append(model_file)
            else:
                other_models.append(model_file)

        logger.info(
            f"Found {len(model_files)} models:\n"
            f"  - PASSED: {len(passed_models)}\n"
            f"  - Others: {len(other_models)}"
        )

        # Scan PASSED stocks first (priority)
        opportunities = []

        if passed_models:
            logger.info(f"Scanning {len(passed_models)} PASSED stocks...")
            passed_predictions = await self._predict_batch(passed_models)

            for pred in passed_predictions:
                if pred and pred.has_opportunity:
                    opportunities.append(pred)
                    logger.info(
                        f"🎯 OPPORTUNITY: {pred.symbol} | "
                        f"Return: {pred.expected_return_5d*100:.1f}% | "
                        f"Confidence: {pred.confidence:.2f}"
                    )

        # Scan other stocks if no opportunities from PASSED
        if len(opportunities) < 3 and other_models:
            logger.info(f"Scanning {len(other_models)} other stocks...")
            other_predictions = await self._predict_batch(other_models)

            for pred in other_predictions:
                if pred and pred.has_opportunity:
                    opportunities.append(pred)

        # Sort by signal strength
        opportunities.sort(key=lambda x: x.signal_strength, reverse=True)

        # Trigger callbacks for top opportunities
        for opp in opportunities[:5]:  # Top 5
            await self._notify_opportunity(opp)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Scan complete in {duration:.1f}s\n"
            f"  - Opportunities: {len(opportunities)}\n"
            f"  - Top: {opportunities[0].symbol if opportunities else 'None'}"
        )
        logger.info("=" * 60)

        self.last_scan = datetime.now()

    async def _predict_batch(self, model_files: List[Path]) -> List[Optional[ModelPrediction]]:
        """Predict batch of stocks"""
        predictions = []

        for model_file in model_files:
            try:
                pred = await self._predict_single(model_file)
                predictions.append(pred)
            except Exception as e:
                symbol = model_file.stem.replace('_stockformer_simple_best', '')
                logger.warning(f"Prediction failed for {symbol}: {e}")
                predictions.append(None)

        return predictions

    async def _predict_single(self, model_file: Path) -> Optional[ModelPrediction]:
        """Predict single stock"""
        symbol = model_file.stem.replace('_stockformer_simple_best', '')

        # Load data
        data_file = self.data_dir / f"{symbol}.parquet"
        if not data_file.exists():
            return None

        df = pd.read_parquet(data_file)
        df = df.sort_values('date').reset_index(drop=True)

        if len(df) < 100:
            return None

        # Load VN-Index for context
        try:
            vn_index = pd.read_parquet(self.data_dir / 'VNINDEX.parquet')
            vn_index = vn_index.set_index('date')
        except:
            vn_index = None

        # Calculate features (15 simple features)
        df_features = calculate_vn_market_features_simple(df, vn_index)

        # Get recent data for prediction
        recent_data = df_features.iloc[-60:].copy()

        # Normalize
        feature_cols = [c for c in recent_data.columns if c not in ['date', 'close']]
        recent_data[feature_cols] = normalize_features_simple(recent_data[feature_cols])

        # Prepare input
        X = recent_data[feature_cols].values.astype(np.float32)
        X = torch.tensor(X, dtype=torch.float32).unsqueeze(0)  # (1, seq_len, features)

        # Load model
        predictor = StockformerPredictor(
            input_size=len(feature_cols),
            d_model=64,
            n_heads=4,
            n_layers=2,
            dropout=0.5,
            device=self.device
        )

        predictor.model.load_state_dict(torch.load(model_file, map_location=self.device))
        predictor.model.eval()

        # Predict
        with torch.no_grad():
            X = X.to(self.device)
            output = predictor.model(X)  # (1, 5)
            predictions = output.cpu().numpy()[0]

        # Denormalize predictions
        current_price = df.iloc[-1]['close']
        predicted_prices = predictions.tolist()

        # Calculate expected return
        expected_return_5d = (predicted_prices[-1] - current_price) / current_price

        # Direction
        if expected_return_5d > 0.01:
            direction = "UP"
        elif expected_return_5d < -0.01:
            direction = "DOWN"
        else:
            direction = "SIDEWAYS"

        # Confidence (simplified: based on model quality + return magnitude)
        confidence = min(0.9, abs(expected_return_5d) * 10 + 0.5)

        # Check if opportunity
        has_opportunity = (
            expected_return_5d >= self.min_return and
            confidence >= self.min_confidence and
            direction == "UP"
        )

        # Signal strength
        signal_strength = expected_return_5d * confidence if has_opportunity else 0

        return ModelPrediction(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=current_price,
            predicted_prices=predicted_prices,
            expected_return_5d=expected_return_5d,
            confidence=confidence,
            direction=direction,
            has_opportunity=has_opportunity,
            signal_strength=signal_strength,
            model_path=str(model_file),
            features_used=len(feature_cols)
        )

    async def _notify_opportunity(self, prediction: ModelPrediction):
        """Notify all callbacks about opportunity"""
        logger.info(
            f"🔔 Triggering agents for {prediction.symbol}\n"
            f"   Expected return: {prediction.expected_return_5d*100:.1f}%\n"
            f"   Confidence: {prediction.confidence:.2f}\n"
            f"   Signal strength: {prediction.signal_strength:.3f}"
        )

        for callback in self.on_opportunity_callbacks:
            try:
                await callback(prediction)
            except Exception as e:
                logger.error(f"Callback error: {e}")


# Example usage
if __name__ == "__main__":
    async def on_opportunity(pred: ModelPrediction):
        print(f"Opportunity detected: {pred.symbol}")
        print(f"  Return: {pred.expected_return_5d*100:.1f}%")
        print(f"  Confidence: {pred.confidence:.2f}")

    scanner = ModelPredictionScanner()
    scanner.add_opportunity_callback(on_opportunity)

    # Test single scan
    asyncio.run(scanner.scan_all_stocks())
