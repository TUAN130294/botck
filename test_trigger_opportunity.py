"""
Test script to trigger a mock trading opportunity
This will simulate the Model Scanner finding an opportunity
"""

import asyncio
import requests
import json
from datetime import datetime

async def trigger_mock_opportunity():
    """
    Simulate a model prediction finding ACB as a strong opportunity
    """
    print("=" * 70)
    print("🧪 TESTING: Triggering Mock Trading Opportunity")
    print("=" * 70)
    print()

    # We'll use the orchestrator directly by importing it
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    from quantum_stock.scanners.model_prediction_scanner import ModelPrediction
    from quantum_stock.autonomous.orchestrator import AutonomousOrchestrator

    # Create a mock prediction for ACB (one of our PASSED stocks)
    mock_prediction = ModelPrediction(
        symbol='ACB',
        timestamp=datetime.now(),
        current_price=26500.0,
        predicted_prices=[26800, 27200, 27500, 27800, 28100],  # Next 5 days
        expected_return_5d=0.0604,  # +6.04% expected return
        confidence=0.82,  # 82% confidence
        direction='UP',
        has_opportunity=True,
        signal_strength=0.0496,  # 6.04% * 0.82
        model_path='models/ACB_stockformer_simple_best.pt',
        features_used=15
    )

    print(f"📊 Mock Prediction Created:")
    print(f"   Symbol: {mock_prediction.symbol}")
    print(f"   Current Price: {mock_prediction.current_price:,.0f} VND")
    print(f"   Expected Return (5d): {mock_prediction.expected_return_5d*100:.2f}%")
    print(f"   Confidence: {mock_prediction.confidence:.2f}")
    print(f"   Signal Strength: {mock_prediction.signal_strength:.4f}")
    print()

    # Now we need to send this to the running orchestrator
    # Since orchestrator is running in another process, we'll create a simple HTTP endpoint
    # Or we can directly trigger via WebSocket

    print("⚠️  NOTE: To actually trigger this in the running system:")
    print("   1. The orchestrator is running in background")
    print("   2. We need to add an API endpoint to inject test opportunities")
    print("   3. OR wait for market hours when scanner runs automatically")
    print()
    print("🔄 Let me add a test endpoint to the server...")

    return mock_prediction


if __name__ == "__main__":
    asyncio.run(trigger_mock_opportunity())
