"""
Monitoring API endpoints - Metrics, alerts, and monitoring dashboards.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Models for Monitoring Responses
# ============================================================================


class MetricsResponse(BaseModel):
    """Daily metrics response."""
    dates: List[str]
    predictions: List[int]
    positive_rate: List[float]
    avg_probability: List[float]
    avg_latency: List[float]
    cache_hit_rate: List[float]


class DriftDetectionResponse(BaseModel):
    """Drift detection results."""
    feature_name: str
    baseline_mean: float
    current_mean: float
    mean_change_pct: float
    drift_detected: bool
    drift_score: float


class PerformanceDegradationResponse(BaseModel):
    """Performance degradation detection."""
    status: str
    baseline_probability: Optional[float] = None
    recent_probability: Optional[float] = None
    probability_change_pct: Optional[float] = None
    baseline_latency_ms: Optional[float] = None
    recent_latency_ms: Optional[float] = None
    latency_change_pct: Optional[float] = None
    days_measured: Optional[int] = None
    degradation_detected: bool


class MonitoringReportResponse(BaseModel):
    """Comprehensive monitoring report."""
    timestamp: str
    drift_detection: Dict
    performance: Dict
    status: str


class AlertResponse(BaseModel):
    """Alert response."""
    alert_level: str  # 'info', 'warning', 'critical'
    message: str
    timestamp: str
    affected_component: str


# ============================================================================
# Monitoring API Router
# ============================================================================


def create_monitoring_router(
    prediction_logger=None,
    model_monitor=None,
) -> APIRouter:
    """Create monitoring router with dependencies."""
    
    router = APIRouter(prefix="/monitoring", tags=["monitoring"])

    @router.get("/health", response_model=Dict)
    async def health_check():
        """Health check for monitoring system."""
        health = {
            'logger_healthy': False,
            'monitor_healthy': False,
            'timestamp': datetime.now().isoformat(),
        }

        if prediction_logger:
            health['logger_healthy'] = prediction_logger.health_check()
        if model_monitor:
            health['monitor_healthy'] = model_monitor.health_check()

        health['overall'] = health['logger_healthy'] and health['monitor_healthy']
        return health

    @router.get("/metrics", response_model=MetricsResponse)
    async def get_metrics(days: int = Query(7, ge=1, le=90)):
        """Get daily performance metrics."""
        if not prediction_logger:
            raise HTTPException(status_code=503, detail="Logger not initialized")

        metrics = prediction_logger.get_daily_metrics(days=days)
        if not metrics:
            raise HTTPException(status_code=404, detail="No metrics available")

        return MetricsResponse(**metrics)

    @router.post("/drift-detection", response_model=List[DriftDetectionResponse])
    async def detect_drift(days: int = Query(7, ge=1, le=30)):
        """Detect data drift in features."""
        if not model_monitor:
            raise HTTPException(status_code=503, detail="Monitor not initialized")

        drift_results = model_monitor.compute_feature_drift(recent_days=days)
        if not drift_results:
            raise HTTPException(status_code=404, detail="No drift detection available")

        # Log drift results
        model_monitor.log_drift_detection(drift_results)

        # Convert to response format
        responses = []
        for feature_name, metrics in drift_results.items():
            responses.append(
                DriftDetectionResponse(
                    feature_name=feature_name,
                    baseline_mean=metrics['baseline_mean'],
                    current_mean=metrics['current_mean'],
                    mean_change_pct=metrics['mean_change_pct'],
                    drift_detected=metrics['drift_detected'],
                    drift_score=metrics['drift_score']
                )
            )

        return responses

    @router.get("/performance-degradation", response_model=PerformanceDegradationResponse)
    async def check_performance(days: int = Query(7, ge=1, le=30)):
        """Check if model performance is degrading."""
        if not model_monitor:
            raise HTTPException(status_code=503, detail="Monitor not initialized")

        degradation = model_monitor.get_performance_degradation(days=days)
        if degradation.get('status') == 'error':
            raise HTTPException(status_code=500, detail="Failed to compute degradation")

        return PerformanceDegradationResponse(**degradation)

    @router.get("/report", response_model=MonitoringReportResponse)
    async def get_monitoring_report():
        """Get comprehensive monitoring report."""
        if not model_monitor:
            raise HTTPException(status_code=503, detail="Monitor not initialized")

        report = model_monitor.generate_monitoring_report()
        return MonitoringReportResponse(**report)

    @router.get("/alerts", response_model=List[AlertResponse])
    async def get_alerts(severity: Optional[str] = None):
        """Get active alerts."""
        alerts = []

        if model_monitor:
            # Check for drift alerts
            drift_results = model_monitor.compute_feature_drift(recent_days=7)
            for feature_name, metrics in drift_results.items():
                if metrics['drift_detected']:
                    alerts.append(
                        AlertResponse(
                            alert_level='warning',
                            message=f"Data drift detected in {feature_name} "
                                   f"({metrics['mean_change_pct']:.1f}% change)",
                            timestamp=datetime.now().isoformat(),
                            affected_component=feature_name
                        )
                    )

            # Check for performance degradation
            degradation = model_monitor.get_performance_degradation(days=7)
            if degradation.get('degradation_detected'):
                alerts.append(
                    AlertResponse(
                        alert_level='critical',
                        message=f"Model performance degradation detected. "
                               f"Probability change: {degradation.get('probability_change_pct', 0):.1f}%",
                        timestamp=datetime.now().isoformat(),
                        affected_component='model_performance'
                    )
                )

        # Filter by severity if provided
        if severity:
            alerts = [a for a in alerts if a.alert_level == severity]

        return alerts

    @router.post("/flush-logs")
    async def flush_logs():
        """Flush prediction logs to database."""
        if not prediction_logger:
            raise HTTPException(status_code=503, detail="Logger not initialized")

        prediction_logger.flush()
        return {
            'status': 'success',
            'message': 'Logs flushed to database',
            'timestamp': datetime.now().isoformat()
        }

    return router
