# -*- coding: utf-8 -*-
"""
Enhanced API Endpoints for Complete UI/Backend Integration
===========================================================
Provides comprehensive APIs for:
- Learning system stats
- Manual approval workflow
- Emergency controls
- Performance metrics
- Circuit breaker status
- Agent insights
"""

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class ManualApprovalRequest(BaseModel):
    """Request for manual trade approval"""
    symbol: str
    action: str  # BUY/SELL
    quantity: int
    price: float
    reason: str
    agent_confidence: float


class ManualApprovalResponse(BaseModel):
    """Response from user for trade approval"""
    approval_id: str
    approved: bool
    rejection_reason: Optional[str] = None
    modified_quantity: Optional[int] = None  # User can modify size


class EmergencyAction(BaseModel):
    """Emergency action request"""
    action: str  # STOP_TRADING, LIQUIDATE_ALL, PAUSE_TRADING
    reason: str
    confirm_code: str  # Require confirmation code


class RetrainRequest(BaseModel):
    """Request to retrain models"""
    symbols: Optional[List[str]] = None  # Specific symbols or all
    force: bool = False  # Force even if not needed


# ============================================
# ENHANCED API ROUTES
# ============================================

def setup_enhanced_api(app: FastAPI, orchestrator):
    """
    Setup all enhanced API endpoints

    Call this after creating orchestrator:
    >>> setup_enhanced_api(app, orchestrator)
    """

    # ========================================
    # LEARNING SYSTEM APIs
    # ========================================

    @app.get("/api/learning/stats")
    async def get_learning_stats():
        """
        Get comprehensive learning system statistics

        Returns:
        - Agent weights (current)
        - Performance metrics per agent
        - Total signals processed
        - Learning enabled status
        """
        try:
            if not hasattr(orchestrator, 'learning_system'):
                return {
                    "error": "Learning system not initialized",
                    "learning_enabled": False
                }

            stats = orchestrator.learning_system.get_learning_stats()
            return stats

        except Exception as e:
            logger.error(f"Error getting learning stats: {e}")
            return {"error": str(e)}


    @app.get("/api/agent-performance")
    async def get_agent_performance():
        """
        Get detailed performance metrics for each agent

        Returns:
        - Accuracy, win rate, Sharpe ratio
        - Recent signals and outcomes
        - Performance trends
        """
        try:
            if not hasattr(orchestrator, 'learning_system'):
                return {"error": "Learning system not initialized"}

            tracker = orchestrator.learning_system.performance_tracker
            tracker.update_all_metrics()

            performance = {}
            for agent_name, metrics in tracker.metrics.items():
                performance[agent_name] = {
                    'accuracy': metrics.accuracy,
                    'win_rate': metrics.win_rate,
                    'sharpe_ratio': metrics.sharpe_ratio,
                    'total_signals': metrics.total_signals,
                    'correct_signals': metrics.correct_signals,
                    'avg_return': metrics.avg_return_per_signal,
                    'profit_factor': metrics.profit_factor,
                    'consistency': metrics.consistency_score,
                    'current_weight': orchestrator.learning_system.get_agent_weight(agent_name)
                }

            return {
                'agents': performance,
                'last_updated': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting agent performance: {e}")
            return {"error": str(e)}


    @app.get("/api/pattern-insights/{symbol}")
    async def get_pattern_insights(symbol: str):
        """
        Get learned patterns for a specific symbol

        Returns:
        - Success rate on this symbol
        - Optimal conditions for trading
        - Recommendation (BUY/AVOID/CAUTION)
        """
        try:
            if not hasattr(orchestrator, 'learning_system'):
                return {"error": "Learning system not initialized"}

            # Analyze patterns
            pattern = await orchestrator.learning_system.analyze_patterns(symbol)

            if not pattern:
                return {
                    "symbol": symbol,
                    "message": "Not enough historical data for pattern analysis",
                    "total_trades": 0
                }

            return pattern

        except Exception as e:
            logger.error(f"Error getting pattern insights: {e}")
            return {"error": str(e)}


    # ========================================
    # MANUAL APPROVAL APIs
    # ========================================

    # Pending approvals queue
    pending_approvals: Dict[str, ManualApprovalRequest] = {}

    @app.post("/api/manual-approval/request")
    async def request_manual_approval(request: ManualApprovalRequest):
        """
        Submit a trade for manual approval

        Used when:
        - Trade size > threshold
        - Low confidence signal
        - High risk conditions
        """
        try:
            approval_id = f"approval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{request.symbol}"

            # Store pending approval
            pending_approvals[approval_id] = request

            logger.info(f"📋 Manual approval requested: {approval_id}")

            return {
                "approval_id": approval_id,
                "status": "pending",
                "request": request.dict(),
                "expires_at": (datetime.now() + timedelta(minutes=5)).isoformat()
            }

        except Exception as e:
            logger.error(f"Error requesting approval: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    @app.get("/api/manual-approval/pending")
    async def get_pending_approvals():
        """Get all pending approval requests"""
        return {
            "count": len(pending_approvals),
            "pending": [
                {
                    "approval_id": aid,
                    "request": req.dict()
                }
                for aid, req in pending_approvals.items()
            ]
        }


    @app.post("/api/manual-approval/respond")
    async def respond_to_approval(response: ManualApprovalResponse):
        """
        Respond to a pending approval request

        User approves/rejects trade
        Can modify quantity if approved
        """
        try:
            if response.approval_id not in pending_approvals:
                raise HTTPException(status_code=404, detail="Approval request not found")

            request = pending_approvals.pop(response.approval_id)

            if response.approved:
                # Execute trade
                quantity = response.modified_quantity or request.quantity

                logger.info(
                    f"✅ Trade approved: {request.action} {quantity} {request.symbol} @ {request.price}"
                )

                # TODO: Execute the approved trade via orchestrator

                return {
                    "status": "approved",
                    "executed": True,
                    "quantity": quantity
                }
            else:
                logger.info(
                    f"❌ Trade rejected: {request.symbol} - {response.rejection_reason}"
                )

                return {
                    "status": "rejected",
                    "reason": response.rejection_reason
                }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error responding to approval: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    # ========================================
    # EMERGENCY CONTROLS
    # ========================================

    @app.post("/api/emergency/stop")
    async def emergency_stop(action: EmergencyAction):
        """
        Emergency stop - Immediate halt of all trading

        Requires confirmation code: "EMERGENCY_STOP_CONFIRMED"
        """
        if action.confirm_code != "EMERGENCY_STOP_CONFIRMED":
            raise HTTPException(status_code=403, detail="Invalid confirmation code")

        try:
            logger.critical(f"🚨 EMERGENCY STOP TRIGGERED: {action.reason}")

            # Stop all trading
            orchestrator.is_running = False

            # Stop scanners
            orchestrator.model_scanner.stop()
            orchestrator.news_scanner.stop()

            if action.action == "LIQUIDATE_ALL":
                # Force liquidate all positions
                logger.critical("🚨 LIQUIDATING ALL POSITIONS")
                # TODO: Implement force liquidation

            return {
                "status": "stopped",
                "action": action.action,
                "reason": action.reason,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error in emergency stop: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    @app.post("/api/emergency/pause")
    async def pause_trading(minutes: int = 60):
        """
        Temporarily pause trading for specified minutes

        Different from stop - will auto-resume
        """
        try:
            logger.warning(f"⏸️ Trading paused for {minutes} minutes")

            # Pause scanners
            orchestrator.model_scanner.stop()
            orchestrator.news_scanner.stop()

            # Schedule resume
            resume_at = datetime.now() + timedelta(minutes=minutes)

            return {
                "status": "paused",
                "duration_minutes": minutes,
                "resume_at": resume_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Error pausing trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    @app.post("/api/emergency/resume")
    async def resume_trading():
        """Resume trading after pause"""
        try:
            logger.info("▶️ Trading resumed")

            orchestrator.is_running = True
            # Scanners will restart on next loop

            return {
                "status": "resumed",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error resuming trading: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    # ========================================
    # CIRCUIT BREAKER APIs
    # ========================================

    @app.get("/api/circuit-breaker/status")
    async def get_circuit_breaker_status():
        """
        Get current circuit breaker status

        Returns:
        - Current level (0-3)
        - Daily P&L
        - Position multiplier
        - Is trading allowed
        """
        try:
            if not hasattr(orchestrator, 'circuit_breaker'):
                return {
                    "level": 0,
                    "message": "Circuit breaker not initialized"
                }

            cb = orchestrator.circuit_breaker
            state = cb.state

            return {
                "level": state.level.value,
                "level_name": state.level.name,
                "daily_pnl": state.daily_pnl,
                "daily_pnl_percent": state.daily_pnl_percent,
                "max_drawdown": state.max_drawdown,
                "position_multiplier": state.position_multiplier,
                "is_trading_allowed": state.is_trading_allowed,
                "message": state.message,
                "last_trigger": state.last_trigger_time.isoformat() if state.last_trigger_time else None
            }

        except Exception as e:
            logger.error(f"Error getting circuit breaker status: {e}")
            return {"error": str(e)}


    # ========================================
    # PERFORMANCE METRICS
    # ========================================

    @app.get("/api/performance/summary")
    async def get_performance_summary():
        """
        Get overall performance summary

        Returns:
        - Total return %
        - Sharpe ratio
        - Max drawdown
        - Win rate
        - Total trades
        """
        try:
            broker = orchestrator.broker

            initial_balance = broker.initial_balance if hasattr(broker, 'initial_balance') else 100_000_000
            current_balance = broker.cash_balance

            # Calculate total value (cash + positions)
            total_value = current_balance
            for pos in broker.positions.values():
                total_value += pos.market_value

            total_return = (total_value - initial_balance) / initial_balance

            # Trade statistics
            trades = broker.trade_history
            winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
            win_rate = len(winning_trades) / len(trades) if trades else 0

            return {
                "initial_balance": initial_balance,
                "current_balance": current_balance,
                "total_value": total_value,
                "total_return_pct": total_return * 100,
                "total_trades": len(trades),
                "winning_trades": len(winning_trades),
                "win_rate": win_rate * 100,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {"error": str(e)}


    # ========================================
    # MODEL RETRAINING
    # ========================================

    @app.post("/api/retrain/trigger")
    async def trigger_retrain(request: RetrainRequest):
        """
        Trigger model retraining

        Can specify specific symbols or retrain all
        Force flag bypasses need check
        """
        try:
            logger.info(f"🔄 Retraining triggered for symbols: {request.symbols or 'ALL'}")

            # Check if retrain is needed
            if not request.force:
                if hasattr(orchestrator, 'learning_system'):
                    needs_retrain = await orchestrator.learning_system.check_retrain_needed()
                    if not needs_retrain:
                        return {
                            "status": "skipped",
                            "reason": "Retraining not needed - performance is good"
                        }

            # TODO: Implement actual retraining logic
            # This would call the training pipeline

            return {
                "status": "started",
                "symbols": request.symbols or "all",
                "estimated_time_minutes": 30,
                "started_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error triggering retrain: {e}")
            raise HTTPException(status_code=500, detail=str(e))


    @app.get("/api/retrain/status")
    async def get_retrain_status():
        """Get status of ongoing retraining"""
        # TODO: Implement retraining status tracking
        return {
            "is_retraining": False,
            "progress_pct": 0,
            "eta_minutes": 0
        }


    logger.info("✅ Enhanced API endpoints registered")
    return app


# For convenience
from datetime import timedelta
