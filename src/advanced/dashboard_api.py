"""
Dashboard API - Provides visualization endpoints for monitoring and insights.
Real-time metrics, A/B test results, and model performance tracking.
"""

from datetime import datetime
from typing import Dict, Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# ============================================================================
# Pydantic Models
# ============================================================================


class ModelVersionResponse(BaseModel):
    """Model version details."""
    version: str
    status: str
    metrics: Dict
    created_at: Optional[str] = None
    promoted_at: Optional[str] = None


class ABTestMetricsResponse(BaseModel):
    """A/B test metrics."""
    variant: str
    num_predictions: int
    avg_probability: float
    std_probability: Optional[float] = None
    avg_latency: float


class ABTestResultsResponse(BaseModel):
    """A/B test results."""
    status: str
    control: Optional[Dict] = None
    variant: Optional[Dict] = None
    probability_test: Optional[Dict] = None


class RetrainingStatusResponse(BaseModel):
    """Retraining status."""
    should_retrain: bool
    reasons: Dict
    timestamp: str
    production_model: Optional[Dict] = None
    staging_models: List[Dict]


class DashboardMetricsResponse(BaseModel):
    """Overall dashboard metrics."""
    timestamp: str
    production_model: Optional[Dict] = None
    active_ab_tests: int
    models_in_staging: int
    retraining_needed: bool
    recent_alerts: List[Dict]


# ============================================================================
# Dashboard Router
# ============================================================================


def create_dashboard_router(
    registry=None,
    orchestrator=None,
    ab_manager=None,
    monitor=None,
) -> APIRouter:
    """Create dashboard router with dependencies."""
    
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    @router.get("/summary", response_model=DashboardMetricsResponse)
    async def get_dashboard_summary():
        """Get overall dashboard summary."""
        try:
            prod_model = registry.get_production_model() if registry else None
            retraining_status = orchestrator.get_retraining_status() if orchestrator else {}
            
            return DashboardMetricsResponse(
                timestamp=datetime.now().isoformat(),
                production_model=prod_model,
                active_ab_tests=0,  # Query from DB
                models_in_staging=len(retraining_status.get('staging_models', [])),
                retraining_needed=retraining_status.get('should_retrain', False),
                recent_alerts=[]  # Query from DB
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/models", response_model=List[ModelVersionResponse])
    async def get_models(limit: int = Query(10, ge=1, le=100)):
        """Get recent model versions."""
        if not registry:
            raise HTTPException(status_code=503, detail="Registry not initialized")
        
        history = registry.get_model_history("churn_model", limit=limit)
        return [ModelVersionResponse(**m) for m in history]

    @router.get("/models/production", response_model=ModelVersionResponse)
    async def get_production_model():
        """Get current production model details."""
        if not registry:
            raise HTTPException(status_code=503, detail="Registry not initialized")
        
        model = registry.get_production_model()
        if not model:
            raise HTTPException(status_code=404, detail="No production model found")
        
        # Add status field if missing
        if 'status' not in model:
            model['status'] = 'production'
        
        return ModelVersionResponse(**model)

    @router.get("/retraining-status", response_model=RetrainingStatusResponse)
    async def get_retraining_status():
        """Get current retraining status."""
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")
        
        status = orchestrator.get_retraining_status()
        return RetrainingStatusResponse(**status)

    @router.get("/ab-tests/{test_name}", response_model=ABTestResultsResponse)
    async def get_ab_test_results(test_name: str):
        """Get A/B test results."""
        if not ab_manager:
            raise HTTPException(status_code=503, detail="A/B test manager not initialized")
        
        results = ab_manager.get_test_results(test_name)
        if results.get('status') == 'error':
            raise HTTPException(status_code=500, detail="Failed to fetch test results")
        
        return ABTestResultsResponse(**results)

    @router.get("/metrics/timeline")
    async def get_metrics_timeline(days: int = Query(7, ge=1, le=30)):
        """Get metrics timeline for visualization."""
        if not monitor:
            raise HTTPException(status_code=503, detail="Monitor not initialized")
        
        return {
            'daily_metrics': monitor.get_performance_degradation(days=days),
            'timestamp': datetime.now().isoformat()
        }

    @router.get("/alerts")
    async def get_recent_alerts(limit: int = Query(10, ge=1, le=100)):
        """Get recent system alerts."""
        return {
            'alerts': [],
            'timestamp': datetime.now().isoformat()
        }

    @router.get("/health")
    async def dashboard_health():
        """Dashboard health check."""
        health = {
            'registry_healthy': registry.health_check() if registry else False,
            'orchestrator_healthy': orchestrator.health_check() if orchestrator else False,
            'ab_manager_healthy': ab_manager.health_check() if ab_manager else False,
            'monitor_healthy': monitor.health_check() if monitor else False,
            'timestamp': datetime.now().isoformat(),
        }
        health['overall'] = all(health[k] for k in health if k != 'timestamp')
        return health

    return router
