"""
Quantum Stock Web Application
Flask-based dashboard with API endpoints
"""

from flask import Flask, render_template, jsonify, request
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'quantum-stock-secret-key')

    # Initialize components (lazy loading)
    app.coordinator = None
    app.quantum_engine = None

    def get_coordinator():
        if app.coordinator is None:
            from quantum_stock.agents import AgentCoordinator
            app.coordinator = AgentCoordinator()
        return app.coordinator

    def get_quantum_engine():
        if app.quantum_engine is None:
            from quantum_stock.core import QuantumEngine
            app.quantum_engine = QuantumEngine()
        return app.quantum_engine

    # ============== PAGE ROUTES ==============

    @app.route('/')
    def index():
        """Main dashboard"""
        return render_template('quantum_dashboard.html')

    @app.route('/agents')
    def agents_page():
        """Multi-agent discussion page"""
        return render_template('agents_chat.html')

    @app.route('/backtest')
    def backtest_page():
        """Backtesting interface"""
        return render_template('backtest.html')

    @app.route('/monte-carlo')
    def monte_carlo_page():
        """Monte Carlo simulation room"""
        return render_template('monte_carlo.html')

    @app.route('/quantum-core')
    def quantum_core_page():
        """Quantum Core AI analysis"""
        return render_template('quantum_core.html')

    # ============== API ROUTES ==============

    @app.route('/api/agents/analyze', methods=['POST'])
    def api_agent_analyze():
        """Run multi-agent analysis"""
        try:
            data = request.json
            symbol = data.get('symbol', 'FPT')

            # Create mock stock data for demo
            stock_data = create_mock_stock_data(symbol)

            # Run analysis
            coordinator = get_coordinator()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            discussion = loop.run_until_complete(coordinator.analyze_stock(stock_data))
            loop.close()

            return jsonify({
                'success': True,
                'discussion': discussion.to_dict(),
                'formatted': coordinator.format_discussion_for_display(discussion)
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/backtest/run', methods=['POST'])
    def api_run_backtest():
        """Run backtesting"""
        try:
            data = request.json
            symbol = data.get('symbol', 'FPT')
            strategy = data.get('strategy', 'MA_CROSSOVER')
            start_date = data.get('start_date', '2023-01-01')
            end_date = data.get('end_date', '2023-12-31')
            params = data.get('params', {})

            # Create mock historical data
            df = create_mock_historical_data(symbol, start_date, end_date)

            # Run backtest
            engine = get_quantum_engine()
            result = engine.quick_backtest(df, symbol, strategy, **params)

            return jsonify({
                'success': True,
                'result': result.to_dict(),
                'summary': result.get_summary(),
                'equity_curve': result.equity_curve[:100],  # Limit for response
                'drawdown_curve': result.drawdown_curve[:100]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/monte-carlo/simulate', methods=['POST'])
    def api_monte_carlo():
        """Run Monte Carlo simulation"""
        try:
            data = request.json
            symbol = data.get('symbol', 'FPT')
            days = data.get('days', 10)
            leverage = data.get('leverage', 1.0)
            simulations = data.get('simulations', 10000)
            capital = data.get('capital', 10000)

            # Create mock data
            df = create_mock_historical_data(symbol)

            # Run simulation
            engine = get_quantum_engine()
            result = engine.run_monte_carlo(df, symbol, days, leverage, simulations)

            return jsonify({
                'success': True,
                'result': result.to_dict(),
                'recommendation': result.get_recommendation(),
                'return_distribution': {
                    'bins': result.return_bins[:50],
                    'counts': result.return_counts[:50]
                }
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/quantum/full-analysis', methods=['POST'])
    def api_quantum_analysis():
        """Full Quantum Core analysis"""
        try:
            data = request.json
            symbol = data.get('symbol', 'FPT')
            strategy = data.get('strategy', 'MA_CROSSOVER')
            forecast_days = data.get('forecast_days', 10)
            leverage = data.get('leverage', 1.0)

            # Create mock data
            df = create_mock_historical_data(symbol)

            # Run full analysis
            engine = get_quantum_engine()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                engine.full_analysis(df, symbol, strategy, forecast_days, leverage, run_wfo=False)
            )
            loop.close()

            return jsonify({
                'success': True,
                'result': result.to_dict(),
                'recommendation': result.recommendation,
                'ai_summary': result.ai_summary
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/kelly/calculate', methods=['POST'])
    def api_kelly():
        """Calculate Kelly position size"""
        try:
            data = request.json
            entry = data.get('entry', 100)
            stop_loss = data.get('stop_loss', 95)
            take_profit = data.get('take_profit', 110)
            win_rate = data.get('win_rate')
            portfolio = data.get('portfolio', 100000000)

            engine = get_quantum_engine()
            engine.kelly.portfolio_value = portfolio
            result = engine.calculate_position_size(entry, stop_loss, take_profit, win_rate)

            return jsonify({
                'success': True,
                'result': result.to_dict(),
                'summary': result.get_summary()
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/strategies')
    def api_strategies():
        """Get available strategies"""
        engine = get_quantum_engine()
        return jsonify({
            'strategies': engine.get_strategy_list(),
            'param_grids': {k: v for k, v in engine.param_grids.items()}
        })

    @app.route('/api/agents/status')
    def api_agent_status():
        """Get agent status"""
        coordinator = get_coordinator()
        return jsonify(coordinator.get_agent_status())

    return app


def create_mock_stock_data(symbol: str):
    """Create mock stock data for demo purposes"""
    from quantum_stock.agents.base_agent import StockData

    # Generate random but realistic data
    np.random.seed(hash(symbol) % 2**32)

    base_price = np.random.uniform(20, 200)
    change = np.random.uniform(-3, 3)

    return StockData(
        symbol=symbol,
        current_price=base_price,
        open_price=base_price * (1 - change/200),
        high_price=base_price * (1 + abs(change)/100),
        low_price=base_price * (1 - abs(change)/100),
        volume=int(np.random.uniform(100000, 5000000)),
        change_percent=change,
        indicators={
            'ema20': base_price * np.random.uniform(0.95, 1.05),
            'ema50': base_price * np.random.uniform(0.90, 1.10),
            'ema200': base_price * np.random.uniform(0.85, 1.15),
            'rsi': np.random.uniform(25, 75),
            'macd': np.random.uniform(-2, 2),
            'macd_signal': np.random.uniform(-2, 2),
            'macd_hist': np.random.uniform(-1, 1),
            'atr': base_price * 0.02,
            'bb_upper': base_price * 1.04,
            'bb_lower': base_price * 0.96,
            'bb_mid': base_price,
            'vwap': base_price * np.random.uniform(0.98, 1.02),
            'adx': np.random.uniform(15, 45),
            'stoch_k': np.random.uniform(20, 80),
            'stoch_d': np.random.uniform(20, 80),
            'obv': np.random.uniform(-1000000, 1000000),
            'support': base_price * 0.95,
            'resistance': base_price * 1.05,
            'avg_volume': int(np.random.uniform(500000, 2000000))
        },
        fundamentals={
            'pe': np.random.uniform(8, 25),
            'pb': np.random.uniform(0.8, 3),
            'market_cap': np.random.uniform(1e12, 50e12)
        },
        news_sentiment=np.random.uniform(-0.5, 0.5),
        sector='Technology'
    )


def create_mock_historical_data(symbol: str, start_date: str = '2023-01-01',
                               end_date: str = '2023-12-31') -> pd.DataFrame:
    """Create mock historical OHLCV data"""
    np.random.seed(hash(symbol) % 2**32)

    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    n = len(dates)

    # Generate price series with random walk
    base_price = np.random.uniform(50, 150)
    returns = np.random.normal(0.0005, 0.02, n)
    prices = base_price * np.cumprod(1 + returns)

    # Generate OHLCV
    df = pd.DataFrame({
        'open': prices * np.random.uniform(0.99, 1.01, n),
        'high': prices * np.random.uniform(1.01, 1.03, n),
        'low': prices * np.random.uniform(0.97, 0.99, n),
        'close': prices,
        'volume': np.random.uniform(100000, 5000000, n).astype(int)
    }, index=dates)

    # Ensure high > open/close and low < open/close
    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)

    return df


# Run app
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5001)
