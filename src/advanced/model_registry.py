"""
Model Registry - Manages model versioning, metadata, and promotion workflow.
Tracks all model versions with their performance metrics and deployment status.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import psycopg2
from enum import Enum

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """Model lifecycle status."""
    CANDIDATE = "candidate"  # New model, not yet evaluated
    STAGING = "staging"      # Validated, ready for A/B testing
    PRODUCTION = "production"  # Active in production
    DEPRECATED = "deprecated"  # Replaced by newer version
    FAILED = "failed"        # Failed validation


class ModelRegistry:
    """Registry for managing model versions and promotions."""

    def __init__(self, db_config: Dict):
        """Initialize model registry."""
        self.db_config = db_config
        self.connection = None

    def connect(self):
        """Connect to PostgreSQL."""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self._create_tables()
            logger.info("✓ Connected to PostgreSQL for model registry")
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to connect: {e}")
            raise

    def disconnect(self):
        """Disconnect from database."""
        if self.connection:
            self.connection.close()

    def _create_tables(self):
        """Create registry tables if they don't exist."""
        cursor = self.connection.cursor()
        try:
            # Model versions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ml_pipeline.model_versions (
                    model_id SERIAL PRIMARY KEY,
                    model_name VARCHAR(100) NOT NULL,
                    version VARCHAR(50) NOT NULL UNIQUE,
                    status VARCHAR(20) NOT NULL DEFAULT 'candidate',
                    model_path VARCHAR(500),
                    scaler_path VARCHAR(500),
                    training_date DATE,
                    training_samples INT,
                    features_json JSONB,
                    hyperparameters JSONB,
                    metrics_json JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    retired_at TIMESTAMP,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_model_version 
                    ON ml_pipeline.model_versions(version)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_status 
                    ON ml_pipeline.model_versions(status)
            """)

            # Model promotion history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ml_pipeline.model_promotions (
                    promotion_id SERIAL PRIMARY KEY,
                    from_version VARCHAR(50),
                    to_version VARCHAR(50) NOT NULL,
                    from_status VARCHAR(20),
                    to_status VARCHAR(20) NOT NULL,
                    reason TEXT,
                    promoted_by VARCHAR(100),
                    promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metrics_improvement JSONB
                )
            """)

            # A/B test assignments
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ml_pipeline.ab_assignments (
                    assignment_id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    test_name VARCHAR(100) NOT NULL,
                    variant VARCHAR(20) NOT NULL,
                    control_version VARCHAR(50),
                    variant_version VARCHAR(50),
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, test_name)
                )
            """)

            self.connection.commit()
            logger.info("✓ Model registry tables created/verified")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to create tables: {e}")
            raise
        finally:
            cursor.close()

    def register_model(
        self,
        model_name: str,
        version: str,
        model_path: str,
        scaler_path: str,
        training_samples: int,
        features: List[str],
        hyperparameters: Dict,
        metrics: Dict,
        training_date: Optional[str] = None,
    ) -> bool:
        """Register a new model version."""
        cursor = self.connection.cursor()
        try:
            training_date = training_date or datetime.now().date()
            
            cursor.execute("""
                INSERT INTO ml_pipeline.model_versions
                (model_name, version, status, model_path, scaler_path,
                 training_date, training_samples, features_json,
                 hyperparameters, metrics_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                model_name,
                version,
                ModelStatus.CANDIDATE.value,
                model_path,
                scaler_path,
                training_date,
                training_samples,
                json.dumps(features),
                json.dumps(hyperparameters),
                json.dumps(metrics)
            ))
            self.connection.commit()
            logger.info(f"✓ Registered model version {version}")
            return True
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to register model: {e}")
            return False
        finally:
            cursor.close()

    def get_model_version(self, version: str) -> Optional[Dict]:
        """Get model version details."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT model_id, model_name, version, status, model_path,
                       scaler_path, training_date, training_samples,
                       features_json, hyperparameters, metrics_json,
                       created_at, promoted_at
                FROM ml_pipeline.model_versions
                WHERE version = %s
            """, (version,))
            
            row = cursor.fetchone()
            if not row:
                return None

            return {
                'model_id': row[0],
                'model_name': row[1],
                'version': row[2],
                'status': row[3],
                'model_path': row[4],
                'scaler_path': row[5],
                'training_date': str(row[6]),
                'training_samples': row[7],
                'features': row[8] if isinstance(row[8], list) else json.loads(row[8]),
                'hyperparameters': row[9] if isinstance(row[9], dict) else json.loads(row[9]),
                'metrics': row[10] if isinstance(row[10], dict) else json.loads(row[10]),
                'created_at': row[11].isoformat() if row[11] else None,
                'promoted_at': row[12].isoformat() if row[12] else None,
            }
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to get model version: {e}")
            return None
        finally:
            cursor.close()

    def promote_model(
        self,
        version: str,
        to_status: str,
        reason: str = "",
        metrics_improvement: Optional[Dict] = None
    ) -> bool:
        """Promote model to new status (candidate → staging → production)."""
        cursor = self.connection.cursor()
        try:
            # Get current status
            cursor.execute(
                "SELECT status FROM ml_pipeline.model_versions WHERE version = %s",
                (version,)
            )
            row = cursor.fetchone()
            if not row:
                logger.error(f"Model version {version} not found")
                return False

            from_status = row[0]

            # Validate promotion workflow
            valid_transitions = {
                ModelStatus.CANDIDATE.value: [ModelStatus.STAGING.value, ModelStatus.FAILED.value],
                ModelStatus.STAGING.value: [ModelStatus.PRODUCTION.value, ModelStatus.FAILED.value],
                ModelStatus.PRODUCTION.value: [ModelStatus.DEPRECATED.value],
            }

            if to_status not in valid_transitions.get(from_status, []):
                logger.error(f"Invalid transition: {from_status} → {to_status}")
                return False

            # If promoting to production, deprecate current production model
            if to_status == ModelStatus.PRODUCTION.value:
                cursor.execute("""
                    UPDATE ml_pipeline.model_versions
                    SET status = %s, retired_at = CURRENT_TIMESTAMP
                    WHERE status = %s AND version != %s
                """, (ModelStatus.DEPRECATED.value, ModelStatus.PRODUCTION.value, version))

            # Update model status
            cursor.execute("""
                UPDATE ml_pipeline.model_versions
                SET status = %s, promoted_at = CURRENT_TIMESTAMP
                WHERE version = %s
            """, (to_status, version))

            # Log promotion
            cursor.execute("""
                INSERT INTO ml_pipeline.model_promotions
                (from_version, to_version, from_status, to_status, reason,
                 metrics_improvement)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                version,
                version,
                from_status,
                to_status,
                reason,
                json.dumps(metrics_improvement) if metrics_improvement else None
            ))

            self.connection.commit()
            logger.info(f"✓ Promoted {version} to {to_status}")
            return True

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to promote model: {e}")
            return False
        finally:
            cursor.close()

    def get_production_model(self) -> Optional[Dict]:
        """Get current production model."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT model_id, model_name, version, model_path, scaler_path,
                       metrics_json, created_at, promoted_at
                FROM ml_pipeline.model_versions
                WHERE status = %s
                ORDER BY promoted_at DESC
                LIMIT 1
            """, (ModelStatus.PRODUCTION.value,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'model_id': row[0],
                'model_name': row[1],
                'version': row[2],
                'model_path': row[3],
                'scaler_path': row[4],
                'metrics': row[5] if isinstance(row[5], dict) else json.loads(row[5]) if row[5] else {},
                'created_at': row[6].isoformat() if row[6] else None,
                'promoted_at': row[7].isoformat() if row[7] else None,
            }
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to get production model: {e}")
            return None
        finally:
            cursor.close()

    def get_model_history(self, model_name: str, limit: int = 10) -> List[Dict]:
        """Get model version history."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT version, status, metrics_json, created_at, promoted_at
                FROM ml_pipeline.model_versions
                WHERE model_name = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (model_name, limit))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'version': row[0],
                    'status': row[1],
                    'metrics': row[2] if isinstance(row[2], dict) else (json.loads(row[2]) if row[2] else {}),
                    'created_at': row[3].isoformat() if row[3] else None,
                    'promoted_at': row[4].isoformat() if row[4] else None,
                })
            return results

        except psycopg2.Error as e:
            logger.error(f"✗ Failed to get model history: {e}")
            return []
        finally:
            cursor.close()

    def health_check(self) -> bool:
        """Check registry health."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"✗ Health check failed: {e}")
            return False
