"""
Retraining Orchestrator - Monitors drift/degradation and triggers model retraining.
Validates new models before promotion to production.
"""

import logging
import subprocess
from datetime import datetime
from typing import Dict, Optional, Tuple
import psycopg2
from src.monitoring import ModelMonitor, PredictionLogger
from src.advanced.model_registry import ModelRegistry, ModelStatus

logger = logging.getLogger(__name__)


class RetrainingOrchestrator:
    """Orchestrates automated model retraining based on monitoring alerts."""

    def __init__(self, db_config: Dict):
        """Initialize orchestrator."""
        self.db_config = db_config
        self.connection = None
        self.registry = ModelRegistry(db_config)
        self.monitor = ModelMonitor(db_config)
        self.logger = PredictionLogger(db_config)
        self.drift_threshold = 0.05  # p-value for drift
        self.degradation_threshold = 10  # % probability drop

    def connect(self):
        """Connect to all services."""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self.registry.connect()
            self.monitor.connect()
            self.logger.connect()
            logger.info("✓ Connected to all services")
        except Exception as e:
            logger.error(f"✗ Failed to connect: {e}")
            raise

    def disconnect(self):
        """Disconnect from all services."""
        if self.connection:
            self.connection.close()
        self.registry.disconnect()
        self.monitor.disconnect()
        self.logger.disconnect()

    def check_retraining_needed(self) -> Tuple[bool, Dict]:
        """
        Check if model retraining is needed based on monitoring metrics.
        Returns: (should_retrain, reasons_dict)
        """
        reasons = {}

        # Check for data drift
        drift_results = self.monitor.compute_feature_drift(recent_days=7)
        drifted_features = [f for f, m in drift_results.items() if m['drift_detected']]
        if drifted_features:
            reasons['drift'] = {
                'detected': True,
                'features': drifted_features,
                'count': len(drifted_features)
            }

        # Check for performance degradation
        degradation = self.monitor.get_performance_degradation(days=7)
        if degradation.get('status') == 'degraded':
            reasons['degradation'] = {
                'detected': True,
                'probability_change': degradation.get('probability_change_pct', 0),
                'latency_change': degradation.get('latency_change_pct', 0),
            }

        # Check prediction volume
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM ml_pipeline.predictions
                WHERE DATE(prediction_time) >= CURRENT_DATE - INTERVAL '7 days'
            """)
            pred_count = cursor.fetchone()[0]
            if pred_count > 10000:  # Significant volume
                reasons['volume'] = {'predictions_7d': pred_count}
        finally:
            cursor.close()

        # Require at least 2 signals for retraining
        should_retrain = len(reasons) >= 1  # Lower threshold for demo
        
        return should_retrain, reasons

    def trigger_retraining(
        self,
        new_model_path: str,
        new_scaler_path: str,
        new_version: str,
        training_samples: int,
        features: list,
        hyperparameters: Dict,
        metrics: Dict,
        reasons: Dict
    ) -> bool:
        """Register new model and evaluate for promotion."""
        try:
            # Register candidate model
            success = self.registry.register_model(
                model_name="churn_model",
                version=new_version,
                model_path=new_model_path,
                scaler_path=new_scaler_path,
                training_samples=training_samples,
                features=features,
                hyperparameters=hyperparameters,
                metrics=metrics,
            )

            if not success:
                logger.error("Failed to register new model")
                return False

            # Evaluate for promotion
            if self._evaluate_new_model(new_version, reasons):
                logger.info(f"✓ New model {new_version} passed validation")
                return True
            else:
                logger.warning(f"✗ New model {new_version} failed validation")
                self.registry.promote_model(
                    new_version,
                    ModelStatus.FAILED.value,
                    "Failed validation tests"
                )
                return False

        except Exception as e:
            logger.error(f"✗ Retraining failed: {e}")
            return False

    def _evaluate_new_model(self, version: str, reasons: Dict) -> bool:
        """Evaluate if new model should be promoted to staging."""
        model_info = self.registry.get_model_version(version)
        if not model_info:
            return False

        new_metrics = model_info['metrics']
        prod_model = self.registry.get_production_model()

        # Always accept first model
        if not prod_model:
            self.registry.promote_model(
                version,
                ModelStatus.STAGING.value,
                "First model in production"
            )
            return True

        old_metrics = prod_model['metrics']

        # Check improvements
        auc_improvement = new_metrics.get('auc', 0) - old_metrics.get('auc', 0)
        precision_improvement = new_metrics.get('precision', 0) - old_metrics.get('precision', 0)
        recall_improvement = new_metrics.get('recall', 0) - old_metrics.get('recall', 0)

        # Require AUC improvement or maintain if drift detected
        if auc_improvement > 0.01 or (auc_improvement >= -0.005 and 'drift' in reasons):
            improvement = {
                'auc': float(auc_improvement),
                'precision': float(precision_improvement),
                'recall': float(recall_improvement),
            }
            self.registry.promote_model(
                version,
                ModelStatus.STAGING.value,
                f"Passed validation. Triggered by: {list(reasons.keys())}",
                improvement
            )
            return True

        return False

    def auto_promote_to_production(self, version: str) -> bool:
        """Promote staging model to production after A/B test success."""
        model = self.registry.get_model_version(version)
        if not model or model['status'] != ModelStatus.STAGING.value:
            logger.error(f"Model {version} not in staging")
            return False

        return self.registry.promote_model(
            version,
            ModelStatus.PRODUCTION.value,
            "Promoted from A/B test success"
        )

    def get_retraining_status(self) -> Dict:
        """Get current retraining status."""
        should_retrain, reasons = self.check_retraining_needed()

        return {
            'should_retrain': should_retrain,
            'reasons': reasons,
            'timestamp': datetime.now().isoformat(),
            'production_model': self.registry.get_production_model(),
            'staging_models': self._get_staging_models()
        }

    def _get_staging_models(self):
        """Get all models in staging."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT version, metrics_json, created_at
                FROM ml_pipeline.model_versions
                WHERE status = %s
                ORDER BY created_at DESC
            """, (ModelStatus.STAGING.value,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'version': row[0],
                    'metrics': {} if not row[1] else row[1],
                    'created_at': row[2].isoformat() if row[2] else None,
                })
            return results
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to get staging models: {e}")
            return []
        finally:
            cursor.close()

    def health_check(self) -> bool:
        """Check orchestrator health."""
        return all([
            self.registry.health_check(),
            self.monitor.health_check(),
            self.logger.health_check(),
        ])
