#!/usr/bin/env python3
"""
Autonomous Paper Trading Runner
================================
Chạy hệ thống autonomous trading với paper trading mode

User chỉ cần:
1. Chạy script này
2. Mở http://localhost:8000/autonomous
3. Xem agents thảo luận và trade real-time

KHÔNG CẦN xác nhận trades - hệ thống tự động hoàn toàn
"""

import asyncio
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

from quantum_stock.autonomous.orchestrator import AutonomousOrchestrator
import logging
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import json
import os

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/autonomous_trading.log')
    ]
)
logger = logging.getLogger(__name__)

# Create logs directory
os.makedirs('logs', exist_ok=True)

# Create FastAPI app
app = FastAPI(
    title="Autonomous Paper Trading",
    description="Real-time autonomous trading system with agent conversations",
    version="1.0.0"
)

# CORS - Restricted to localhost for security
# NOTE: Only localhost origins are allowed to prevent unauthorized API access
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:8003",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:8003",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global orchestrator
orchestrator: AutonomousOrchestrator = None
active_websockets: List[WebSocket] = []


@app.on_event("startup")
async def startup_event():
    """Start autonomous system on app startup"""
    global orchestrator

    logger.info("=" * 70)
    logger.info("🚀 STARTING AUTONOMOUS PAPER TRADING SYSTEM")
    logger.info("=" * 70)

    # Create orchestrator
    orchestrator = AutonomousOrchestrator(
        paper_trading=True,
        initial_balance=100_000_000  # 100M VND
    )

    # Start orchestrator in background
    asyncio.create_task(orchestrator.start())
    asyncio.create_task(broadcast_messages())

    logger.info("✅ System ready!")
    logger.info("📊 Open http://localhost:8001/autonomous to view dashboard")
    logger.info("")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop autonomous system on shutdown"""
    global orchestrator

    if orchestrator:
        logger.info("Stopping autonomous system...")
        await orchestrator.stop()


async def broadcast_messages():
    """Broadcast orchestrator messages to all WebSocket clients"""
    global orchestrator, active_websockets

    while True:
        try:
            if orchestrator and orchestrator.is_running:
                # Get message from orchestrator queue
                message = await asyncio.wait_for(
                    orchestrator.agent_message_queue.get(),
                    timeout=1.0
                )

                logger.info(f"📤 Broadcasting message type: {message.get('type')} to {len(active_websockets)} clients")

                # Broadcast to all connected clients
                for ws in active_websockets[:]:  # Copy list to avoid modification during iteration
                    try:
                        await ws.send_json(message)
                        logger.debug(f"✅ Sent to WebSocket client")
                    except Exception as e:
                        logger.warning(f"Failed to send to WebSocket: {e}")
                        active_websockets.remove(ws)

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            await asyncio.sleep(1)


@app.get("/", response_class=HTMLResponse)
async def homepage():
    """Redirect to dashboard"""
    return """
    <html>
        <head>
            <meta http-equiv="refresh" content="0; url=/autonomous">
        </head>
    </html>
    """


@app.get("/autonomous", response_class=HTMLResponse)
async def autonomous_dashboard():
    """Main autonomous trading dashboard"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Autonomous Paper Trading - Live</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0e27;
            color: #e0e0e0;
            padding: 20px;
        }
        .container { max-width: 1800px; margin: 0 auto; }
        h1 {
            text-align: center;
            color: #00ff88;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 0 0 10px #00ff88;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #1e2749 0%, #2d3561 100%);
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #3d4577;
        }
        .stat-label {
            color: #888;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #00ff88;
        }
        .main-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }
        .panel {
            background: linear-gradient(135deg, #1e2749 0%, #2d3561 100%);
            border-radius: 10px;
            border: 1px solid #3d4577;
            padding: 20px;
        }
        .panel-title {
            font-size: 1.3em;
            color: #00ff88;
            margin-bottom: 15px;
            border-bottom: 2px solid #00ff88;
            padding-bottom: 10px;
        }
        #conversations {
            height: 600px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .message {
            margin-bottom: 15px;
            padding: 10px;
            background: rgba(0,255,136,0.05);
            border-left: 3px solid #00ff88;
            border-radius: 5px;
        }
        .message.discussion { border-left-color: #00aaff; }
        .message.order { border-left-color: #ffaa00; }
        .message.exit { border-left-color: #ff5555; }
        .timestamp {
            color: #666;
            font-size: 0.85em;
        }
        .agent-name {
            color: #00ff88;
            font-weight: bold;
        }
        .verdict-buy { color: #00ff88; }
        .verdict-sell { color: #ff5555; }
        .verdict-hold { color: #ffaa00; }
        #positions {
            max-height: 600px;
            overflow-y: auto;
        }
        .position {
            background: rgba(255,255,255,0.05);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
        }
        .position-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .symbol {
            font-size: 1.3em;
            font-weight: bold;
            color: #00ff88;
        }
        .pnl-positive { color: #00ff88; }
        .pnl-negative { color: #ff5555; }
        .status-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .status-running { background: #00ff88; color: #000; }
        .status-stopped { background: #666; color: #fff; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1e2749; }
        ::-webkit-scrollbar-thumb { background: #00ff88; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AUTONOMOUS PAPER TRADING - LIVE</h1>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">System Status</div>
                <div class="stat-value" id="system-status">
                    <span class="status-badge status-running">● RUNNING</span>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Portfolio Value</div>
                <div class="stat-value" id="portfolio-value">100,000,000 VND</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Active Positions</div>
                <div class="stat-value" id="active-positions">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Today P&L</div>
                <div class="stat-value pnl-positive" id="today-pnl">+0 VND</div>
            </div>
        </div>

        <!-- Main Grid -->
        <div class="main-grid">
            <!-- Agent Conversations -->
            <div class="panel">
                <div class="panel-title">🗨️ AGENT CONVERSATIONS (Real-time)</div>
                <div id="conversations">
                    <div class="message">
                        <div class="timestamp">Waiting for agent activity...</div>
                    </div>
                </div>
            </div>

            <!-- Positions -->
            <div class="panel">
                <div class="panel-title">📊 POSITIONS</div>
                <div id="positions">
                    <div style="text-align: center; color: #666; padding: 20px;">
                        No positions yet
                    </div>
                </div>
            </div>
        </div>

        <!-- Orders & Trades History -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
            <!-- Orders History -->
            <div class="panel">
                <div class="panel-title">📝 ORDERS HISTORY</div>
                <div id="orders" style="max-height: 400px; overflow-y: auto;">
                    <div style="text-align: center; color: #666; padding: 20px;">
                        No orders yet
                    </div>
                </div>
            </div>

            <!-- Trades History -->
            <div class="panel">
                <div class="panel-title">💰 TRADES HISTORY</div>
                <div id="trades" style="max-height: 400px; overflow-y: auto;">
                    <div style="text-align: center; color: #666; padding: 20px;">
                        No trades yet
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        console.log('🚀 Initializing WebSocket connection...');
        const ws = new WebSocket('ws://localhost:8001/ws/autonomous');
        const conversations = document.getElementById('conversations');
        const positionsDiv = document.getElementById('positions');
        const ordersDiv = document.getElementById('orders');
        const tradesDiv = document.getElementById('trades');
        let positions = {};

        ws.onopen = () => {
            console.log('✅ WebSocket connected successfully!');
            addMessage('system', '✅ Connected to autonomous trading system', 'System');
        };

        ws.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
            addMessage('system', '❌ WebSocket connection error - Check if server is running', 'System');
        };

        ws.onclose = (event) => {
            console.log('⚠️ WebSocket disconnected. Code:', event.code, 'Reason:', event.reason);
            addMessage('system', '⚠️ Disconnected from server', 'System');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('📨 Received message:', data);

            if (data.type === 'agent_discussion') {
                handleDiscussion(data);
            } else if (data.type === 'order_executed') {
                handleOrder(data);
            } else if (data.type === 'position_exited') {
                handleExit(data);
            } else if (data.type === 'status_update') {
                handleStatusUpdate(data);
            }
        };

        function handleDiscussion(data) {
            let html = `<div class="message discussion">`;
            html += `<div class="timestamp">${new Date(data.timestamp).toLocaleTimeString()}</div>`;
            html += `<div style="margin: 10px 0; font-size: 1.2em;"><strong>📊 ${data.symbol}</strong> - ${data.source} PATHWAY</div>`;

            // Show agent messages với card riêng biệt
            if (data.messages) {
                for (const msg of data.messages) {
                    const agentName = msg.agent_name || msg.agent || 'Unknown';
                    const agentEmoji = msg.agent_emoji || '🤖';

                    // Màu sắc cho từng agent
                    let bgColor = 'rgba(0,255,136,0.08)';
                    let borderColor = '#00ff88';
                    if (agentName === 'Bull') {
                        bgColor = 'rgba(0,200,255,0.08)';
                        borderColor = '#00c8ff';
                    } else if (agentName === 'Bear') {
                        bgColor = 'rgba(255,100,100,0.08)';
                        borderColor = '#ff6464';
                    } else if (agentName === 'Chief') {
                        bgColor = 'rgba(255,200,0,0.08)';
                        borderColor = '#ffc800';
                    } else if (agentName === 'RiskDoctor') {
                        bgColor = 'rgba(150,100,255,0.08)';
                        borderColor = '#9664ff';
                    }

                    html += `<div style="margin: 12px 0; padding: 12px; background: ${bgColor}; border-left: 4px solid ${borderColor}; border-radius: 6px;">`;
                    html += `<div style="font-weight: bold; color: ${borderColor}; margin-bottom: 8px; font-size: 1.05em;">${agentEmoji} ${agentName}</div>`;

                    // Format content với line breaks preserved - use split/join to avoid regex issues
                    const rawContent = msg.content || msg.message || '';
                    const content = rawContent.split('\\n').join('<br>');
                    html += `<div style="color: #ddd; line-height: 1.6; white-space: pre-wrap; font-family: 'Segoe UI', Arial, sans-serif;">${content}</div>`;
                    html += `</div>`;
                }
            }

            // Show verdict
            if (data.verdict) {
                const verdictClass = data.verdict.action === 'BUY' ? 'verdict-buy' :
                                   data.verdict.action === 'SELL' ? 'verdict-sell' : 'verdict-hold';
                html += `<div style="margin-top: 15px; padding: 15px; background: rgba(0,255,136,0.15); border: 2px solid #00ff88; border-radius: 8px; text-align: center;">`;
                html += `<div style="font-size: 1.3em;"><strong class="${verdictClass}">⚖️ VERDICT: ${data.verdict.action}</strong></div>`;
                if (data.verdict.confidence) {
                    html += `<div style="margin-top: 5px; color: #aaa;">Confidence: ${(data.verdict.confidence * 100).toFixed(0)}%</div>`;
                }
                html += `</div>`;
            }

            html += `</div>`;
            conversations.innerHTML = html + conversations.innerHTML;
        }

        function handleOrder(data) {
            let html = `<div class="message order">`;
            html += `<div class="timestamp">${new Date(data.timestamp).toLocaleTimeString()}</div>`;
            html += `<div style="margin: 10px 0;"><strong>💰 ORDER EXECUTED</strong></div>`;
            html += `<div style="margin: 5px 0 5px 20px;">`;
            html += `${data.action} ${data.quantity} ${data.symbol} @ ${data.price.toLocaleString()} VND`;
            html += `</div>`;
            html += `</div>`;
            conversations.innerHTML = html + conversations.innerHTML;

            // Add to positions
            if (data.action === 'BUY') {
                positions[data.symbol] = {
                    symbol: data.symbol,
                    quantity: data.quantity,
                    avg_price: data.price,
                    entry_time: data.timestamp
                };
                updatePositions();
            }
        }

        function handleExit(data) {
            let html = `<div class="message exit">`;
            html += `<div class="timestamp">${new Date(data.timestamp).toLocaleTimeString()}</div>`;
            html += `<div style="margin: 10px 0;"><strong>🔄 POSITION EXITED</strong></div>`;
            html += `<div style="margin: 5px 0 5px 20px;">`;
            html += `${data.symbol} - ${data.exit_reason}<br>`;
            const pnlClass = data.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
            html += `P&L: <span class="${pnlClass}">${data.pnl >= 0 ? '+' : ''}${data.pnl.toLocaleString()} VND (${(data.pnl_pct * 100).toFixed(2)}%)</span><br>`;
            html += `Days held: T+${data.days_held.toFixed(1)}`;
            html += `</div>`;
            html += `</div>`;
            conversations.innerHTML = html + conversations.innerHTML;

            // Remove from positions
            delete positions[data.symbol];
            updatePositions();
        }

        function handleStatusUpdate(data) {
            if (data.portfolio_value) {
                document.getElementById('portfolio-value').textContent =
                    data.portfolio_value.toLocaleString() + ' VND';
            }
            if (data.active_positions !== undefined) {
                document.getElementById('active-positions').textContent = data.active_positions;
            }
            if (data.today_pnl !== undefined) {
                const pnl = document.getElementById('today-pnl');
                pnl.textContent = (data.today_pnl >= 0 ? '+' : '') + data.today_pnl.toLocaleString() + ' VND';
                pnl.className = 'stat-value ' + (data.today_pnl >= 0 ? 'pnl-positive' : 'pnl-negative');
            }
        }

        function updatePositions() {
            const count = Object.keys(positions).length;
            document.getElementById('active-positions').textContent = count;

            if (count === 0) {
                positionsDiv.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">No positions yet</div>';
                return;
            }

            let html = '';
            for (const pos of Object.values(positions)) {
                html += `<div class="position">`;
                html += `<div class="position-header">`;
                html += `<div class="symbol">${pos.symbol}</div>`;
                html += `</div>`;
                html += `<div>Qty: ${pos.quantity} @ ${pos.avg_price.toLocaleString()}</div>`;
                html += `<div style="font-size: 0.85em; color: #888;">Entry: ${new Date(pos.entry_time).toLocaleString()}</div>`;
                html += `</div>`;
            }
            positionsDiv.innerHTML = html;
        }

        function addMessage(type, content, agent) {
            let html = `<div class="message">`;
            html += `<div class="timestamp">${new Date().toLocaleTimeString()}</div>`;
            if (agent) html += `<span class="agent-name">${agent}:</span> `;
            html += content;
            html += `</div>`;
            conversations.innerHTML = html + conversations.innerHTML;
        }

        // Fetch and display orders
        async function fetchOrders() {
            try {
                const response = await fetch('/api/orders');
                const data = await response.json();

                if (data.orders && data.orders.length > 0) {
                    let html = '<table style="width: 100%; font-size: 0.85em;">';
                    html += '<tr style="background: #1a1f3a; font-weight: bold;">';
                    html += '<th style="padding: 8px;">Time</th>';
                    html += '<th>Symbol</th>';
                    html += '<th>Side</th>';
                    html += '<th>Qty</th>';
                    html += '<th>Price</th>';
                    html += '<th>Status</th>';
                    html += '</tr>';

                    for (const order of data.orders) {
                        const time = new Date(order.created_at).toLocaleString('vi-VN');
                        const sideColor = order.side === 'BUY' ? '#00ff88' : '#ff5555';
                        const statusColor = order.status === 'FILLED' ? '#00ff88' : '#ffaa00';

                        html += '<tr style="border-bottom: 1px solid #2a2f4a;">';
                        html += `<td style="padding: 8px;">${time}</td>`;
                        html += `<td><strong>${order.symbol}</strong></td>`;
                        html += `<td style="color: ${sideColor}; font-weight: bold;">${order.side}</td>`;
                        html += `<td>${order.quantity.toLocaleString()}</td>`;
                        html += `<td>${order.price.toLocaleString()} VND</td>`;
                        html += `<td style="color: ${statusColor};">${order.status}</td>`;
                        html += '</tr>';
                    }
                    html += '</table>';
                    ordersDiv.innerHTML = html;
                } else {
                    ordersDiv.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">No orders yet</div>';
                }
            } catch (error) {
                console.error('Error fetching orders:', error);
            }
        }

        // Fetch and display trades
        async function fetchTrades() {
            try {
                const response = await fetch('/api/trades');
                const data = await response.json();

                if (data.trades && data.trades.length > 0) {
                    let html = '<table style="width: 100%; font-size: 0.85em;">';
                    html += '<tr style="background: #1a1f3a; font-weight: bold;">';
                    html += '<th style="padding: 8px;">Time</th>';
                    html += '<th>Symbol</th>';
                    html += '<th>Action</th>';
                    html += '<th>Qty</th>';
                    html += '<th>Price</th>';
                    html += '<th>P&L</th>';
                    html += '</tr>';

                    for (const trade of data.trades) {
                        const time = new Date(trade.timestamp || trade.date).toLocaleString('vi-VN');
                        const actionColor = trade.action === 'BUY' ? '#00ff88' : '#ff5555';
                        const pnl = trade.pnl || 0;
                        const pnlColor = pnl >= 0 ? '#00ff88' : '#ff5555';
                        const pnlSign = pnl >= 0 ? '+' : '';

                        html += '<tr style="border-bottom: 1px solid #2a2f4a;">';
                        html += `<td style="padding: 8px;">${time}</td>`;
                        html += `<td><strong>${trade.symbol}</strong></td>`;
                        html += `<td style="color: ${actionColor}; font-weight: bold;">${trade.action || trade.side}</td>`;
                        html += `<td>${trade.quantity.toLocaleString()}</td>`;
                        html += `<td>${trade.price.toLocaleString()} VND</td>`;
                        html += `<td style="color: ${pnlColor};">${pnlSign}${pnl.toLocaleString()} VND</td>`;
                        html += '</tr>';
                    }
                    html += '</table>';
                    tradesDiv.innerHTML = html;
                } else {
                    tradesDiv.innerHTML = '<div style="text-align: center; color: #666; padding: 20px;">No trades yet</div>';
                }
            } catch (error) {
                console.error('Error fetching trades:', error);
            }
        }

        // Auto-refresh orders and trades every 5 seconds
        setInterval(() => {
            fetchOrders();
            fetchTrades();
        }, 5000);

        // Initial fetch
        fetchOrders();
        fetchTrades();
    </script>
</body>
</html>
    """


@app.websocket("/ws/autonomous")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    active_websockets.append(websocket)

    logger.info(f"WebSocket client connected (total: {len(active_websockets)})")

    try:
        # Send initial status
        if orchestrator:
            await websocket.send_json({
                'type': 'status_update',
                'portfolio_value': orchestrator.broker.cash_balance,
                'active_positions': len(orchestrator.exit_scheduler.get_all_positions()),
                'today_pnl': 0
            })

        # Keep connection alive
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        logger.info(f"WebSocket client disconnected (total: {len(active_websockets)})")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)


@app.get("/api/status")
async def get_status():
    """Get system status"""
    if orchestrator:
        return orchestrator.get_status()
    return {"error": "Orchestrator not initialized"}


@app.get("/api/orders")
async def get_orders():
    """Get all orders history"""
    if orchestrator and orchestrator.broker:
        orders = []
        for order in orchestrator.broker.orders.values():
            orders.append(order.to_dict())
        # Sort by created_at descending
        orders.sort(key=lambda x: x['created_at'], reverse=True)
        return {"orders": orders}
    return {"orders": []}


@app.get("/api/positions")
async def get_positions():
    """Get current positions"""
    if orchestrator and orchestrator.broker:
        positions = []
        for pos in orchestrator.broker.positions.values():
            positions.append(pos.to_dict())
        return {"positions": positions}
    return {"positions": []}


@app.get("/api/trades")
async def get_trades():
    """Get trade history"""
    if orchestrator and orchestrator.broker:
        trades = orchestrator.broker.trade_history.copy()
        # Sort by timestamp descending
        trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return {"trades": trades}
    return {"trades": []}


@app.post("/api/test/opportunity")
async def trigger_test_opportunity(symbol: str = "ACB"):
    """
    Trigger a test opportunity for testing
    This simulates the model scanner finding a strong opportunity
    """
    global orchestrator
    if not orchestrator:
        return {"error": "Orchestrator not initialized"}

    try:
        from quantum_stock.scanners.model_prediction_scanner import ModelPrediction
        from datetime import datetime

        # Create mock prediction
        mock_prediction = ModelPrediction(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=26500.0,
            predicted_prices=[26800, 27200, 27500, 27800, 28100],
            expected_return_5d=0.0604,  # +6.04%
            confidence=0.82,
            direction='UP',
            has_opportunity=True,
            signal_strength=0.0496,
            model_path=f'models/{symbol}_stockformer_simple_best.pt',
            features_used=15
        )

        # Trigger the opportunity callback
        await orchestrator._on_model_opportunity(mock_prediction)

        return {
            "status": "triggered",
            "symbol": symbol,
            "expected_return": f"{mock_prediction.expected_return_5d*100:.2f}%",
            "confidence": mock_prediction.confidence
        }

    except Exception as e:
        logger.error(f"Error triggering test opportunity: {e}")
        return {"error": str(e)}


@app.post("/api/test/trade")
async def trigger_test_trade(symbol: str = "ACB", action: str = "BUY"):
    """
    Direct test trade - bypasses agents for instant demo
    """
    global orchestrator
    if not orchestrator:
        return {"error": "Orchestrator not initialized"}

    try:
        from quantum_stock.autonomous.position_exit_scheduler import Position
        from quantum_stock.core.broker_api import OrderSide, OrderType
        from datetime import datetime

        # Use realistic current price for ACB (in thousand VND)
        # Note: Prices are stored as thousand VND (26.5 = 26,500 VND)
        current_price = 26.5

        # Calculate position size (12.5% of portfolio)
        portfolio_value = orchestrator.broker.cash_balance
        position_value = portfolio_value * 0.125
        quantity = int(position_value / current_price / 100) * 100

        if action == "BUY" and quantity > 0:
            # Place buy order using broker directly
            order = await orchestrator.broker.place_order(
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=current_price
            )

            # Add to position monitor
            position = Position(
                symbol=symbol,
                quantity=quantity,
                avg_price=current_price,
                entry_date=datetime.now(),
                take_profit_pct=0.15,
                trailing_stop_pct=0.05,
                stop_loss_pct=-0.05,
                entry_reason="TEST - Direct trade for demo"
            )
            orchestrator.exit_scheduler.add_position(position)

            # Broadcast order
            await orchestrator.agent_message_queue.put({
                'type': 'order_executed',
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'price': current_price,
                'timestamp': datetime.now().isoformat()
            })

            logger.info(f"TEST TRADE: {action} {quantity} {symbol} @ {current_price:,.0f}")

            return {
                "status": "success",
                "action": action,
                "symbol": symbol,
                "quantity": quantity,
                "price": current_price,
                "value": quantity * current_price
            }

        return {"error": "Invalid trade parameters"}

    except Exception as e:
        logger.error(f"Error in test trade: {e}")
        return {"error": str(e)}


@app.post("/api/stop")
async def stop_system():
    """Stop autonomous system"""
    global orchestrator
    if orchestrator:
        orchestrator.is_running = False
        return {"status": "stopping"}
    return {"error": "Not running"}


if __name__ == "__main__":
    logger.info("Starting Autonomous Paper Trading Server...")
    logger.info("Dashboard will be available at: http://localhost:8001/autonomous")
    logger.info("")
    logger.info("Press Ctrl+C to stop")
    logger.info("")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
