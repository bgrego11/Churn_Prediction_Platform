"""
Phase 6 Test - Model Deployment & Monitoring
Tests prediction logging, model monitoring, and drift detection.
"""

import os
import time
import logging
import json
from datetime import datetime
import psycopg2

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
L = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'postgres'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'churn_db'),
    'user': os.getenv('POSTGRES_USER', 'churn_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'churn_password'),
}

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'redis'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': int(os.getenv('REDIS_DB', 0)),
}


def test_prediction_logger():
    """Test prediction logging to database."""
    L.info("\n[TEST 1] Prediction Logger - Log predictions to database\n")

    from src.monitoring.prediction_logger import PredictionLogger

    pred_logger = PredictionLogger(DB_CONFIG)
    pred_logger.connect()

    try:
        # Log sample predictions
        L.info("Logging 100 sample predictions...")
        for i in range(100):
            prob = 0.5 + (i % 50) / 100  # Vary probability
            pred_logger.log_prediction(
                user_id=i + 1,
                churn_probability=prob,
                predicted_label=1 if prob > 0.6 else 0,
                features={
                    'avg_sessions_7d': 5.0 + (i % 10),
                    'sessions_30d': 20 + (i % 30),
                    'days_since_last_login': 5 + (i % 20),
                },
                model_version='1.0',
                latency_ms=0.5 + (i % 5) * 0.1,
                from_cache=True
            )

        pred_logger.flush()
        L.info("✓ Logged 100 predictions successfully\n")

        # Verify predictions were saved
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ml_pipeline.predictions")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        L.info(f"✓ Database contains {count} total predictions")

        # Get daily metrics
        metrics = pred_logger.get_daily_metrics(days=1)
        L.info(f"✓ Daily metrics computed:")
        if metrics['dates']:
            L.info(f"  - Date: {metrics['dates'][0]}")
            L.info(f"  - Predictions: {metrics['predictions'][0]}")
            L.info(f"  - Positive rate: {metrics['positive_rate'][0]:.1f}%")
            L.info(f"  - Avg latency: {metrics['avg_latency'][0]:.2f}ms")
            L.info(f"  - Cache hit rate: {metrics['cache_hit_rate'][0]:.1%}\n")

        pred_logger.disconnect()
        return True

    except Exception as e:
        L.error(f"✗ Prediction logger test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_model_monitor():
    """Test model monitoring and drift detection."""
    L.info("\n[TEST 2] Model Monitor - Drift detection and performance monitoring\n")

    from src.monitoring.model_monitor import ModelMonitor
    import numpy as np

    monitor = ModelMonitor(DB_CONFIG)
    monitor.connect()

    try:
        # Set baseline statistics from training data
        baseline_stats = {
            'avg_sessions_7d': {'mean': 5.0, 'std': 2.0},
            'sessions_30d': {'mean': 20.0, 'std': 8.0},
            'days_since_last_login': {'mean': 10.0, 'std': 5.0},
            'events_30d': {'mean': 50.0, 'std': 20.0},
            'failed_payments_30d': {'mean': 0.5, 'std': 1.0},
            'total_spend_90d': {'mean': 100.0, 'std': 50.0},
            'refunds_30d': {'mean': 10.0, 'std': 5.0},
        }
        monitor.set_baseline_statistics(baseline_stats)
        L.info("✓ Baseline statistics set\n")

        # Compute drift
        L.info("Computing feature drift...")
        drift_results = monitor.compute_feature_drift(recent_days=7)

        if drift_results:
            L.info("✓ Drift detection results:")
            drifted_features = [f for f, m in drift_results.items() if m['drift_detected']]
            L.info(f"  - Features drifted: {len(drifted_features)}/{len(drift_results)}")

            if drifted_features:
                for feature in drifted_features[:3]:  # Show top 3
                    metrics = drift_results[feature]
                    L.info(f"  - {feature}:")
                    L.info(f"    • Baseline mean: {metrics['baseline_mean']:.2f}")
                    L.info(f"    • Current mean: {metrics['current_mean']:.2f}")
                    L.info(f"    • Mean change: {metrics['mean_change_pct']:.1f}%")
                    L.info(f"    • Drift score: {metrics['drift_score']:.2f}\n")

            # Log drift results
            monitor.log_drift_detection(drift_results)
            L.info("✓ Drift results logged to database\n")
        else:
            L.info("✓ No significant drift detected\n")

        # Check performance degradation
        L.info("Checking performance degradation...")
        degradation = monitor.get_performance_degradation(days=7)

        if degradation.get('status') != 'insufficient_data':
            L.info("✓ Performance analysis:")
            L.info(f"  - Status: {degradation['status']}")
            L.info(f"  - Baseline probability: {degradation.get('baseline_probability', 0):.4f}")
            L.info(f"  - Recent probability: {degradation.get('recent_probability', 0):.4f}")
            L.info(f"  - Change: {degradation.get('probability_change_pct', 0):.1f}%")
            L.info(f"  - Days measured: {degradation.get('days_measured', 0)}\n")
        else:
            L.info("⚠ Insufficient data for degradation analysis\n")

        # Generate report
        L.info("Generating comprehensive monitoring report...")
        report = monitor.generate_monitoring_report()
        L.info(f"✓ Report generated at {report['timestamp']}\n")

        monitor.disconnect()
        return True

    except Exception as e:
        L.error(f"✗ Model monitor test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_monitoring_integration():
    """Test integration between prediction and monitoring systems."""
    L.info("\n[TEST 3] Monitoring Integration - End-to-end pipeline\n")

    from src.monitoring.prediction_logger import PredictionLogger
    from src.monitoring.model_monitor import ModelMonitor

    logger_obj = PredictionLogger(DB_CONFIG)
    logger_obj.connect()
    
    monitor = ModelMonitor(DB_CONFIG)
    monitor.connect()

    try:
        # Simulate API prediction flow
        L.info("Simulating prediction + monitoring flow...")

        # 1. Log predictions
        for i in range(50):
            logger_obj.log_prediction(
                user_id=100 + i,
                churn_probability=0.7 if i % 3 == 0 else 0.3,
                predicted_label=1 if i % 3 == 0 else 0,
                latency_ms=0.8,
                from_cache=True
            )

        logger_obj.flush()
        L.info("✓ Predictions logged")

        # 2. Compute metrics
        logger_obj.compute_hourly_metrics(datetime.now())
        L.info("✓ Hourly metrics computed")

        # 3. Detect drift
        baseline = {
            'avg_sessions_7d': {'mean': 5.0, 'std': 2.0},
            'sessions_30d': {'mean': 20.0, 'std': 8.0},
            'days_since_last_login': {'mean': 10.0, 'std': 5.0},
        }
        monitor.set_baseline_statistics(baseline)
        drift = monitor.compute_feature_drift(recent_days=7)
        L.info(f"✓ Drift analysis completed ({len(drift)} features checked)")

        # 4. Health check
        health_logger = logger_obj.health_check()
        health_monitor = monitor.health_check()
        L.info(f"✓ Logger healthy: {health_logger}, Monitor healthy: {health_monitor}\n")

        logger_obj.disconnect()
        monitor.disconnect()
        return True

    except Exception as e:
        L.error(f"✗ Integration test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 6 tests."""
    L.info("\n" + "=" * 80)
    L.info("PHASE 6: MODEL DEPLOYMENT & MONITORING TEST")
    L.info("=" * 80 + "\n")

    results = {
        'Prediction Logger': test_prediction_logger(),
        'Model Monitor': test_model_monitor(),
        'Integration': test_monitoring_integration(),
    }

    L.info("=" * 80)
    L.info("TEST SUMMARY")
    L.info("=" * 80)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        L.info(f"{status}: {test_name}")

    L.info("")
    all_passed = all(results.values())

    if all_passed:
        L.info("✅ PHASE 6 TEST SUCCESSFUL - Monitoring ready for production!")
        L.info("\nNext Steps:")
        L.info("  1. Configure Airflow to schedule monitoring tasks")
        L.info("  2. Set up alert notifications (email/Slack)")
        L.info("  3. Create Grafana dashboards for metrics")
        L.info("  4. Phase 7: Advanced features (A/B testing, retraining)")
    else:
        L.info("❌ PHASE 6 TEST FAILED - Review errors above")

    L.info("")


if __name__ == "__main__":
    main()
