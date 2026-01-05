"""
FastAPI application for online churn prediction.
Provides REST endpoints for real-time churn predictions.
"""

import logging
import os
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.serving import FeatureStore, OnlineFeatureServer, FeatureCacheSyncer
from src.advanced.model_registry import ModelRegistry
from src.advanced.retraining_orchestrator import RetrainingOrchestrator
from src.advanced.ab_testing import ABTestManager
from src.advanced.dashboard_api import create_dashboard_router
from src.monitoring.model_monitor import ModelMonitor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Churn Prediction API",
    description="Real-time churn prediction service with cached features",
    version="1.0.0",
)

# ============================================================================
# Pydantic Models (Request/Response schemas)
# ============================================================================


class PredictionResponse(BaseModel):
    """Single prediction response."""
    user_id: int
    churn_probability: Optional[float] = Field(
        None, description="Probability of churn (0-1)"
    )
    churn_label: Optional[int] = Field(
        None, description="Predicted label (0=retained, 1=churned)"
    )
    timestamp: str
    from_cache: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class BatchPredictionRequest(BaseModel):
    """Batch prediction request."""
    user_ids: List[int] = Field(..., description="List of user IDs to predict")


class BatchPredictionResponse(BaseModel):
    """Batch prediction response."""
    predictions: List[PredictionResponse]
    total_time_ms: float
    num_predictions: int


class FeatureExplanationResponse(BaseModel):
    """Feature explanation response."""
    user_id: int
    features: dict
    intercept: float


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    cache_healthy: bool
    scaler_loaded: bool
    timestamp: str


class CacheSyncRequest(BaseModel):
    """Cache sync request."""
    feature_date: Optional[str] = Field(
        None, description="Feature date (ISO format, defaults to today)"
    )


class CacheSyncResponse(BaseModel):
    """Cache sync response."""
    success: bool
    message: str
    num_users_cached: Optional[int] = None
    memory_used: Optional[str] = None
    timestamp: str


# ============================================================================
# Global State (initialized on startup)
# ============================================================================

_server: Optional[OnlineFeatureServer] = None
_feature_store: Optional[FeatureStore] = None
_syncer: Optional[FeatureCacheSyncer] = None

# Phase 7 components
_registry: Optional[ModelRegistry] = None
_orchestrator: Optional[RetrainingOrchestrator] = None
_ab_manager: Optional[ABTestManager] = None
_monitor: Optional[ModelMonitor] = None


def get_db_config():
    """Get database configuration from environment."""
    return {
        "host": os.getenv("POSTGRES_HOST", "postgres"),
        "port": int(os.getenv("POSTGRES_PORT", 5432)),
        "database": os.getenv("POSTGRES_DB", "churn_db"),
        "user": os.getenv("POSTGRES_USER", "churn_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "churn_password"),
    }


def get_redis_config():
    """Get Redis configuration from environment."""
    return {
        "host": os.getenv("REDIS_HOST", "redis"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "db": int(os.getenv("REDIS_DB", 0)),
    }


# ============================================================================
# Startup/Shutdown Events
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    global _server, _feature_store, _syncer, _registry, _orchestrator, _ab_manager, _monitor

    logger.info("🚀 Starting up Churn Prediction API...")

    try:
        # Initialize feature store
        redis_config = get_redis_config()
        _feature_store = FeatureStore(
            host=redis_config["host"],
            port=redis_config["port"],
            db=redis_config["db"],
        )
        _feature_store.connect()
        logger.info("✓ Feature store initialized")

        # Initialize online server
        model_path = "/tmp/churn_model"
        _server = OnlineFeatureServer(
            model_path=model_path,
            feature_store=_feature_store,
        )
        logger.info("✓ Online server initialized")

        # Initialize syncer
        db_config = get_db_config()
        _syncer = FeatureCacheSyncer(
            db_config=db_config,
            redis_config=redis_config,
        )
        _syncer.connect()
        logger.info("✓ Cache syncer initialized")

        # Initialize Phase 7 components
        _registry = ModelRegistry(db_config)
        _registry.connect()
        logger.info("✓ Model registry initialized")

        _monitor = ModelMonitor(db_config)
        _monitor.connect()
        logger.info("✓ Model monitor initialized")

        _orchestrator = RetrainingOrchestrator(db_config)
        _orchestrator.connect()
        logger.info("✓ Retraining orchestrator initialized")

        _ab_manager = ABTestManager(db_config)
        _ab_manager.connect()
        logger.info("✓ A/B test manager initialized")

        # Register dashboard router
        dashboard_router = create_dashboard_router(_registry, _orchestrator, _ab_manager, _monitor)
        app.include_router(dashboard_router)
        logger.info("✓ Dashboard API initialized")

        logger.info("✅ API startup complete!")

    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    global _server, _feature_store, _syncer, _registry, _orchestrator, _ab_manager, _monitor

    logger.info("🛑 Shutting down...")

    if _syncer:
        _syncer.disconnect()
    if _feature_store:
        _feature_store.disconnect()
    if _registry:
        _registry.disconnect()
    if _orchestrator:
        _orchestrator.disconnect()
    if _ab_manager:
        _ab_manager.disconnect()
    if _monitor:
        _monitor.disconnect()

    logger.info("✓ Shutdown complete")


# ============================================================================
# Health & Status Endpoints
# ============================================================================


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Check if the API is healthy."""
    if not _server or not _feature_store:
        raise HTTPException(status_code=503, detail="Server not initialized")

    health = _server.health_check()

    return HealthCheckResponse(
        status="healthy",
        model_loaded=health["model_loaded"],
        cache_healthy=health["feature_cache_healthy"],
        scaler_loaded=health["scaler_loaded"],
        timestamp=health["timestamp"],
    )


@app.get("/status")
async def get_status():
    """Get API and cache status."""
    if not _feature_store or not _syncer:
        raise HTTPException(status_code=503, detail="Server not initialized")

    status = _syncer.get_sync_status()
    return status


# ============================================================================
# Prediction Endpoints
# ============================================================================


@app.post("/predict/{user_id}", response_model=PredictionResponse)
async def predict_single(user_id: int):
    """
    Predict churn probability for a single user.

    Args:
        user_id: User ID to predict

    Returns:
        Prediction with probability and label
    """
    if not _server:
        raise HTTPException(status_code=503, detail="Server not initialized")

    try:
        result = _server.predict(user_id)

        if result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])

        return PredictionResponse(**result)

    except Exception as e:
        logger.error(f"Prediction error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(request: BatchPredictionRequest):
    """
    Predict churn for multiple users.

    Args:
        request: BatchPredictionRequest with list of user IDs

    Returns:
        List of predictions
    """
    if not _server:
        raise HTTPException(status_code=503, detail="Server not initialized")

    try:
        start = datetime.utcnow()
        predictions = _server.predict_batch(request.user_ids)
        elapsed_ms = (datetime.utcnow() - start).total_seconds() * 1000

        return BatchPredictionResponse(
            predictions=[PredictionResponse(**p) for p in predictions],
            total_time_ms=elapsed_ms,
            num_predictions=len(predictions),
        )

    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Explainability Endpoints
# ============================================================================


@app.get("/explain/{user_id}", response_model=Optional[FeatureExplanationResponse])
async def explain_prediction(user_id: int):
    """
    Get feature explanation for a prediction.

    Args:
        user_id: User ID to explain

    Returns:
        Feature values and their contribution to the prediction
    """
    if not _server:
        raise HTTPException(status_code=503, detail="Server not initialized")

    try:
        explanation = _server.get_feature_explanation(user_id)

        if not explanation:
            raise HTTPException(status_code=404, detail="Explanation not available")

        return FeatureExplanationResponse(**explanation)

    except Exception as e:
        logger.error(f"Explanation error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Cache Management Endpoints
# ============================================================================


@app.post("/cache/sync", response_model=CacheSyncResponse)
async def sync_cache(request: Optional[CacheSyncRequest] = None):
    """
    Manually trigger cache sync (normally done by Airflow).

    Args:
        request: Optional feature date (defaults to today)

    Returns:
        Sync result
    """
    if not _syncer:
        raise HTTPException(status_code=503, detail="Server not initialized")

    try:
        feature_date = None
        if request and request.feature_date:
            feature_date = datetime.fromisoformat(request.feature_date)

        success = _syncer.sync_cache(feature_date)
        status = _syncer.get_sync_status()

        return CacheSyncResponse(
            success=success,
            message="Cache sync completed successfully" if success else "Cache sync failed",
            num_users_cached=status.get("num_users_cached"),
            memory_used=status.get("memory_used"),
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Cache sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/clear")
async def clear_cache():
    """Clear all cached features (use with caution!)."""
    if not _feature_store:
        raise HTTPException(status_code=503, detail="Server not initialized")

    try:
        count = _feature_store.clear_all()
        return {
            "success": True,
            "message": f"Cleared {count} feature keys",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Info Endpoints
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Churn Prediction API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "predict_single": "/predict/{user_id}",
            "predict_batch": "/predict/batch",
            "explain": "/explain/{user_id}",
            "cache_sync": "/cache/sync",
            "cache_clear": "/cache/clear",
            "docs": "/docs",
        },
    }
