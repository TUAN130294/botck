# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite for VN-QUANT
======================================
Unit tests and integration tests for trading system.

Coverage target: 70%+
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ===================================
# BACKTEST ENGINE TESTS
# ===================================

class TestBacktestEngine:
    """Test backtesting engine"""

    def test_walk_forward_windows(self):
        """Test walk-forward window generation"""
        from quantum_stock.backtest.backtest_engine import BacktestEngine, BacktestConfig

        config = BacktestConfig(
            train_window=180,
            test_window=30,
            step_size=30
        )

        engine = BacktestEngine(config)

        # Create test data (1 year)
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        data = pd.DataFrame({'close': np.random.randn(365)}, index=dates)

        windows = engine._walk_forward_windows(data)

        assert len(windows) > 0
        assert all(len(w) == 4 for w in windows)

    def test_backtest_result_metrics(self):
        """Test backtest metrics calculation"""
        from quantum_stock.backtest.backtest_engine import BacktestEngine, Trade

        # Create mock trades
        trades = [
            Trade(symbol="VCB", entry_date=datetime.now(), entry_price=90000,
                  exit_date=datetime.now(), exit_price=95000, quantity=100, pnl=500000, pnl_pct=5.5),
            Trade(symbol="HPG", entry_date=datetime.now(), entry_price=25000,
                  exit_date=datetime.now(), exit_price=24000, quantity=100, pnl=-100000, pnl_pct=-4.0),
        ]

        # Create equity curve
        equity = pd.Series([100_000_000, 100_500_000, 100_400_000],
                          index=pd.date_range('2024-01-01', periods=3))

        engine = BacktestEngine()
        result = engine._calculate_metrics(equity, trades)

        assert result.total_trades == 2
        assert result.winning_trades == 1
        assert result.losing_trades == 1
        assert 0 < result.win_rate < 100

    def test_monte_carlo_simulation(self):
        """Test Monte Carlo simulation"""
        from quantum_stock.backtest.backtest_engine import run_monte_carlo_simulation, BacktestResult, Trade

        # Mock result
        trades = [
            Trade(symbol="VCB", entry_date=datetime.now(), entry_price=90000,
                  exit_date=datetime.now(), exit_price=95000, quantity=100, pnl=500000),
        ]

        equity = pd.Series([100_000_000, 100_500_000],
                          index=pd.date_range('2024-01-01', periods=2))

        result = BacktestResult(
            equity_curve=equity,
            trades=trades,
            total_return=0.5,
            annual_return=2.0,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=-5.0,
            max_drawdown_duration=10,
            win_rate=50.0,
            profit_factor=1.5,
            avg_win=500000,
            avg_loss=-300000,
            expectancy=100000,
            value_at_risk_95=-1000000,
            conditional_var_95=-1500000,
            calmar_ratio=0.4,
            total_trades=1,
            winning_trades=1,
            losing_trades=0,
            avg_holding_days=5.0,
            max_consecutive_wins=1,
            max_consecutive_losses=0
        )

        mc_result = run_monte_carlo_simulation(result, num_simulations=100)

        assert 'mean_sharpe' in mc_result
        assert 'mean_return' in mc_result
        assert mc_result['mean_sharpe'] > 0


# ===================================
# DATA VALIDATION TESTS
# ===================================

class TestDataValidator:
    """Test data validation"""

    def test_ohlcv_validator_valid_data(self):
        """Test OHLCV validator with valid data"""
        from quantum_stock.data.data_validator import OHLCVValidator

        # Create valid OHLCV data
        df = pd.DataFrame({
            'open': [100, 105, 103],
            'high': [110, 112, 108],
            'low': [95, 100, 98],
            'close': [105, 103, 106],
            'volume': [1000000, 1500000, 1200000]
        }, index=pd.date_range('2024-01-01', periods=3))

        validator = OHLCVValidator()
        result = validator.validate(df, symbol="VCB")

        assert result.is_valid
        assert result.quality_score >= 90

    def test_ohlcv_validator_invalid_hl(self):
        """Test validator detects High < Low"""
        from quantum_stock.data.data_validator import OHLCVValidator

        df = pd.DataFrame({
            'open': [100],
            'high': [95],  # Invalid: High < Low
            'low': [100],
            'close': [98],
            'volume': [1000000]
        }, index=pd.date_range('2024-01-01', periods=1))

        validator = OHLCVValidator()
        result = validator.validate(df)

        assert not result.is_valid
        assert len(result.get_errors()) > 0

    def test_freshness_validator(self):
        """Test data freshness validation"""
        from quantum_stock.data.data_validator import DataFreshnessValidator

        validator = DataFreshnessValidator(max_age_seconds=3600)

        # Fresh data
        fresh_timestamp = datetime.now()
        result = validator.validate(fresh_timestamp)

        assert result.is_valid
        assert result.quality_score == 100

        # Stale data
        stale_timestamp = datetime.now() - timedelta(hours=2)
        result = validator.validate(stale_timestamp)

        assert result.quality_score < 100


# ===================================
# NOTIFICATION TESTS
# ===================================

class TestNotificationSystem:
    """Test notification system"""

    @pytest.mark.asyncio
    async def test_notification_manager(self):
        """Test notification manager"""
        from quantum_stock.utils.notification_system import NotificationManager, NotificationLevel

        manager = NotificationManager()

        # Track notifications
        notifications = []

        class MockChannel:
            async def send(self, notification):
                notifications.append(notification)

        manager.add_channel("mock", MockChannel())

        await manager.info("Test", "Test message")

        assert len(notifications) == 1
        assert notifications[0].title == "Test"

    @pytest.mark.asyncio
    async def test_notification_filter(self):
        """Test notification filtering"""
        from quantum_stock.utils.notification_system import NotificationManager, NotificationLevel

        manager = NotificationManager()

        # Filter out INFO
        manager.add_filter(lambda n: n.level != NotificationLevel.INFO)

        notifications = []

        class MockChannel:
            async def send(self, notification):
                notifications.append(notification)

        manager.add_channel("mock", MockChannel())

        await manager.info("Test", "Should be filtered")
        await manager.critical("Test", "Should pass")

        assert len(notifications) == 1
        assert notifications[0].level == NotificationLevel.CRITICAL


# ===================================
# AUTO SCANNER TESTS
# ===================================

class TestAutoScanner:
    """Test auto scanner"""

    @pytest.mark.asyncio
    async def test_scan_symbol(self):
        """Test single symbol scan"""
        from quantum_stock.agents.auto_scanner import AutoScanner
        import tempfile

        # Create temp data
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test parquet file
            df = pd.DataFrame({
                'open': np.random.uniform(90, 110, 100),
                'high': np.random.uniform(95, 115, 100),
                'low': np.random.uniform(85, 105, 100),
                'close': np.random.uniform(90, 110, 100),
                'volume': np.random.randint(1000000, 5000000, 100)
            }, index=pd.date_range('2024-01-01', periods=100))

            df.to_parquet(f"{tmpdir}/VCB.parquet")

            scanner = AutoScanner(data_dir=tmpdir)
            result = await scanner._scan_symbol("VCB")

            assert result is not None
            assert result.symbol == "VCB"
            assert result.signal in ["BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL"]

    def test_calculate_indicators(self):
        """Test indicator calculation"""
        from quantum_stock.agents.auto_scanner import AutoScanner

        df = pd.DataFrame({
            'close': [100, 102, 101, 103, 105, 104, 106, 108, 107, 109] * 3,
            'volume': [1000000] * 30
        })

        scanner = AutoScanner()
        indicators = scanner._calculate_indicators(df)

        assert 'rsi' in indicators
        assert 'macd' in indicators
        assert 'sma_20' in indicators
        assert 0 <= indicators['rsi'] <= 100


# ===================================
# METRICS TESTS
# ===================================

class TestMetrics:
    """Test Prometheus metrics"""

    def test_metrics_recording(self):
        """Test metrics are recorded correctly"""
        from quantum_stock.utils.metrics import PrometheusMetrics

        metrics = PrometheusMetrics()

        # Record order
        metrics.record_order("BUY", "VCB", "FILLED")

        # Record portfolio
        metrics.update_portfolio(
            total_value=105_000_000,
            cash=50_000_000,
            realized_pnl=5_000_000,
            unrealized_pnl=0
        )

        # Get metrics
        output = metrics.get_metrics()

        assert isinstance(output, bytes)
        assert b'vnquant_orders_total' in output


# ===================================
# CONFIG TESTS
# ===================================

class TestConfigManager:
    """Test configuration management"""

    def test_config_validation(self):
        """Test config validation"""
        from quantum_stock.core.config_manager import Config, Environment, TradingMode

        config = Config(
            environment=Environment.PRODUCTION,
            debug=False
        )

        errors = config.validate()

        # Production should have validation errors (missing keys)
        assert len(errors) > 0

    def test_trading_config(self):
        """Test trading config"""
        from quantum_stock.core.config_manager import TradingConfig

        config = TradingConfig()

        assert 0 < config.max_position_pct <= 1
        assert config.max_positions > 0
        assert 0 < config.stop_loss_pct < 1


# ===================================
# DATABASE TESTS
# ===================================

class TestDatabase:
    """Test database operations"""

    def test_database_health_check(self):
        """Test database health check"""
        from quantum_stock.db.connection import DatabaseManager

        # Use SQLite for testing
        manager = DatabaseManager("sqlite:///test.db")

        health = manager.health_check()

        assert health['status'] in ['healthy', 'unhealthy', 'error']

    def test_model_creation(self):
        """Test model instantiation"""
        from quantum_stock.db.models import Order, OrderType, OrderStatus

        order = Order(
            order_id="TEST123",
            order_type=OrderType.BUY,
            symbol="VCB",
            quantity=100,
            price=95000,
            status=OrderStatus.PENDING
        )

        assert order.symbol == "VCB"
        assert order.order_type == OrderType.BUY


# ===================================
# MODEL TRAINER TESTS
# ===================================

class TestModelTrainer:
    """Test model training pipeline"""

    def test_trainer_initialization(self):
        """Test trainer init"""
        from quantum_stock.ml.model_trainer import ModelTrainer
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = ModelTrainer(model_dir=tmpdir)

            assert trainer.model_dir.exists()

    def test_save_load_weights(self):
        """Test weight persistence"""
        from quantum_stock.ml.model_trainer import ModelTrainer
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = ModelTrainer(model_dir=tmpdir)

            weights = {
                "Bull": 1.2,
                "Bear": 0.8,
                "Alex": 1.5
            }

            trainer._save_weights(weights, "test_weights")
            loaded = trainer.load_weights("test_weights")

            assert loaded == weights


# ===================================
# PYTEST CONFIGURATION
# ===================================

@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing"""
    return pd.DataFrame({
        'open': np.random.uniform(90, 110, 100),
        'high': np.random.uniform(95, 115, 100),
        'low': np.random.uniform(85, 105, 100),
        'close': np.random.uniform(90, 110, 100),
        'volume': np.random.randint(1000000, 5000000, 100)
    }, index=pd.date_range('2024-01-01', periods=100))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=quantum_stock", "--cov-report=html"])
