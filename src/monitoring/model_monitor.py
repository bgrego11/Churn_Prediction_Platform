"""
Model Monitor - Tracks model performance, detects data drift, and generates alerts.
Implements performance degradation detection and feature distribution monitoring.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import psycopg2
from scipy import stats

logger = logging.getLogger(__name__)


class ModelMonitor:
    """Monitor model performance and detect data drift."""

    def __init__(self, db_config: Dict):
        """Initialize model monitor."""
        self.db_config = db_config
        self.connection = None
        self.baseline_stats = {}  # Training data statistics

    def connect(self):
        """Connect to PostgreSQL."""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            logger.info("✓ Connected to PostgreSQL for monitoring")
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to connect: {e}")
            raise

    def disconnect(self):
        """Disconnect from database."""
        if self.connection:
            self.connection.close()

    def set_baseline_statistics(self, baseline_stats: Dict):
        """Set baseline feature statistics from training data."""
        self.baseline_stats = baseline_stats
        logger.info(f"✓ Baseline statistics loaded for {len(baseline_stats)} features")

    def compute_feature_drift(self, recent_days: int = 7) -> Dict:
        """
        Detect data drift by comparing feature distributions.
        Uses Kolmogorov-Smirnov test.
        """
        cursor = self.connection.cursor()
        drift_results = {}

        try:
            # Get features used in predictions over recent period
            cursor.execute("""
                SELECT 
                    user_id,
                    (features->>'avg_sessions_7d')::FLOAT AS avg_sessions_7d,
                    (features->>'sessions_30d')::FLOAT AS sessions_30d,
                    (features->>'days_since_last_login')::FLOAT AS days_since_last_login,
                    (features->>'events_30d')::FLOAT AS events_30d,
                    (features->>'failed_payments_30d')::FLOAT AS failed_payments_30d,
                    (features->>'total_spend_90d')::FLOAT AS total_spend_90d,
                    (features->>'refunds_30d')::FLOAT AS refunds_30d
                FROM ml_pipeline.predictions
                WHERE prediction_time >= CURRENT_TIMESTAMP - INTERVAL '%s days'
                  AND features IS NOT NULL
                LIMIT 5000
            """, (recent_days,))

            rows = cursor.fetchall()
            if not rows:
                logger.warning("No recent predictions with features found")
                return {}

            # Extract features
            features = {
                'avg_sessions_7d': [],
                'sessions_30d': [],
                'days_since_last_login': [],
                'events_30d': [],
                'failed_payments_30d': [],
                'total_spend_90d': [],
                'refunds_30d': []
            }

            for row in rows:
                features['avg_sessions_7d'].append(row[1])
                features['sessions_30d'].append(row[2])
                features['days_since_last_login'].append(row[3])
                features['events_30d'].append(row[4])
                features['failed_payments_30d'].append(row[5])
                features['total_spend_90d'].append(row[6])
                features['refunds_30d'].append(row[7])

            # Compute drift for each feature
            for feature_name, values in features.items():
                if not values or feature_name not in self.baseline_stats:
                    continue

                # Filter out None values
                clean_values = [v for v in values if v is not None]
                if not clean_values:
                    continue

                baseline_mean = self.baseline_stats[feature_name].get('mean', 0)
                baseline_std = self.baseline_stats[feature_name].get('std', 1)
                
                current_mean = np.nanmean(clean_values)
                current_std = np.nanstd(clean_values)

                # Kolmogorov-Smirnov test
                baseline_sample = np.random.normal(baseline_mean, baseline_std, 1000)
                ks_stat, p_value = stats.ks_2samp(clean_values, baseline_sample)

                # Mean absolute percentage change
                mean_change = abs((current_mean - baseline_mean) / (abs(baseline_mean) + 1e-6)) * 100

                # Drift detected if p_value < 0.05 or mean change > 30%
                drift_detected = p_value < 0.05 or mean_change > 30

                drift_results[feature_name] = {
                    'baseline_mean': float(baseline_mean),
                    'current_mean': float(current_mean),
                    'mean_change_pct': float(mean_change),
                    'ks_statistic': float(ks_stat),
                    'p_value': float(p_value),
                    'drift_detected': drift_detected,
                    'drift_score': float(ks_stat * 100)
                }

            return drift_results

        except psycopg2.Error as e:
            logger.error(f"✗ Failed to compute feature drift: {e}")
            return {}
        finally:
            cursor.close()

    def log_drift_detection(self, drift_results: Dict):
        """Log drift detection results to database."""
        cursor = self.connection.cursor()
        try:
            for feature_name, metrics in drift_results.items():
                cursor.execute("""
                    INSERT INTO ml_pipeline.data_drift
                    (check_date, feature_name, mean_value, std_value, 
                     drift_detected, drift_score, notes)
                    VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (check_date, feature_name) DO UPDATE SET
                        drift_detected = EXCLUDED.drift_detected,
                        drift_score = EXCLUDED.drift_score
                """, (
                    feature_name,
                    metrics['current_mean'],
                    0,  # std calculation
                    bool(metrics['drift_detected']),  # Convert numpy bool to Python bool
                    metrics['drift_score'],
                    f"Mean change: {metrics['mean_change_pct']:.1f}%"
                ))
            self.connection.commit()
            logger.info(f"✓ Logged drift detection for {len(drift_results)} features")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to log drift: {e}")
        finally:
            cursor.close()

    def get_performance_degradation(self, days: int = 7) -> Dict:
        """
        Detect if model performance is degrading.
        Compares recent metrics with baseline.
        """
        cursor = self.connection.cursor()
        try:
            # Get baseline metrics (first 7 days of data)
            cursor.execute("""
                SELECT 
                    AVG(avg_probability)::FLOAT AS avg_probability,
                    AVG(avg_latency_ms)::FLOAT AS avg_latency
                FROM ml_pipeline.model_metrics
                WHERE metric_date < CURRENT_DATE - INTERVAL '%s days'
                LIMIT 7
            """, (days * 2,))

            baseline = cursor.fetchone()
            if not baseline or baseline[0] is None:
                return {'status': 'insufficient_data'}

            baseline_prob, baseline_latency = baseline[0], baseline[1]

            # Get recent metrics
            cursor.execute("""
                SELECT 
                    AVG(avg_probability)::FLOAT AS avg_probability,
                    AVG(avg_latency_ms)::FLOAT AS avg_latency,
                    COUNT(*)::INT AS days_measured
                FROM ml_pipeline.model_metrics
                WHERE metric_date >= CURRENT_DATE - INTERVAL '%s days'
            """, (days,))

            recent = cursor.fetchone()
            if not recent or recent[0] is None:
                return {'status': 'insufficient_data'}

            recent_prob, recent_latency, days_measured = recent[0], recent[1], recent[2]

            # Calculate degradation
            prob_change = ((baseline_prob - recent_prob) / baseline_prob * 100) if baseline_prob else 0
            latency_change = ((recent_latency - baseline_latency) / baseline_latency * 100) if baseline_latency else 0

            # Degradation detected if probability drops >10% or latency increases >50%
            degradation_detected = prob_change > 10 or latency_change > 50

            return {
                'status': 'ok' if not degradation_detected else 'degraded',
                'baseline_probability': float(baseline_prob) if baseline_prob else 0.0,
                'recent_probability': float(recent_prob) if recent_prob else 0.0,
                'probability_change_pct': float(prob_change),
                'baseline_latency_ms': float(baseline_latency) if baseline_latency else 0.0,
                'recent_latency_ms': float(recent_latency) if recent_latency else 0.0,
                'latency_change_pct': float(latency_change),
                'days_measured': int(days_measured) if days_measured else 0,
                'degradation_detected': degradation_detected
            }

        except psycopg2.Error as e:
            logger.error(f"✗ Failed to compute performance degradation: {e}")
            return {'status': 'error'}
        finally:
            cursor.close()

    def generate_monitoring_report(self) -> Dict:
        """Generate comprehensive monitoring report."""
        return {
            'timestamp': datetime.now().isoformat(),
            'drift_detection': self.compute_feature_drift(recent_days=7),
            'performance': self.get_performance_degradation(days=7),
            'status': 'monitoring_active'
        }

    def health_check(self) -> bool:
        """Check if monitor is healthy."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"✗ Health check failed: {e}")
            return False
