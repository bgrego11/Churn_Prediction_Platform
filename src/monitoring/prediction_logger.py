"""
Prediction Logger - Logs all predictions to database for monitoring and auditing.
Tracks prediction metadata, actual outcomes, and model performance over time.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import execute_batch

logger = logging.getLogger(__name__)


class PredictionLogger:
    """Logs predictions to PostgreSQL for monitoring and auditing."""

    def __init__(self, db_config: Dict):
        """Initialize prediction logger with database config."""
        self.db_config = db_config
        self.connection = None
        self.batch_predictions = []
        self.batch_size = 100

    def connect(self):
        """Connect to PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self._create_tables()
            logger.info("✓ Connected to PostgreSQL for prediction logging")
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to connect to PostgreSQL: {e}")
            raise

    def disconnect(self):
        """Disconnect from database."""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from PostgreSQL")

    def _create_tables(self):
        """Create monitoring tables if they don't exist."""
        cursor = self.connection.cursor()
        try:
            # Predictions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ml_pipeline.predictions (
                    prediction_id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    churn_probability FLOAT NOT NULL,
                    predicted_label INT NOT NULL,
                    prediction_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    features JSONB,
                    model_version VARCHAR(50),
                    latency_ms FLOAT,
                    from_cache BOOLEAN DEFAULT TRUE,
                    is_monitored BOOLEAN DEFAULT FALSE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_user_id 
                    ON ml_pipeline.predictions(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_time 
                    ON ml_pipeline.predictions(prediction_time)
            """)

            # Model performance metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ml_pipeline.model_metrics (
                    metric_id SERIAL PRIMARY KEY,
                    metric_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    metric_hour INT,
                    total_predictions INT DEFAULT 0,
                    positive_predictions INT DEFAULT 0,
                    negative_predictions INT DEFAULT 0,
                    avg_probability FLOAT,
                    avg_latency_ms FLOAT,
                    cache_hit_rate FLOAT,
                    model_version VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_date_hour 
                    ON ml_pipeline.model_metrics(metric_date, metric_hour, model_version)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_metrics_date 
                    ON ml_pipeline.model_metrics(metric_date)
            """)

            # Data drift detection table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ml_pipeline.data_drift (
                    drift_id SERIAL PRIMARY KEY,
                    check_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    feature_name VARCHAR(100) NOT NULL,
                    mean_value FLOAT,
                    std_value FLOAT,
                    min_value FLOAT,
                    max_value FLOAT,
                    drift_detected BOOLEAN DEFAULT FALSE,
                    drift_score FLOAT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_drift_date_feature 
                    ON ml_pipeline.data_drift(check_date, feature_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_data_drift_date 
                    ON ml_pipeline.data_drift(check_date)
            """)

            self.connection.commit()
            logger.info("✓ Monitoring tables created/verified")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to create monitoring tables: {e}")
            raise
        finally:
            cursor.close()

    def log_prediction(
        self,
        user_id: int,
        churn_probability: float,
        predicted_label: int,
        features: Optional[Dict] = None,
        model_version: str = "1.0",
        latency_ms: float = 0.0,
        from_cache: bool = True,
    ):
        """Log a single prediction."""
        self.batch_predictions.append({
            'user_id': user_id,
            'churn_probability': churn_probability,
            'predicted_label': predicted_label,
            'features': json.dumps(features) if features else None,
            'model_version': model_version,
            'latency_ms': latency_ms,
            'from_cache': from_cache,
        })

        if len(self.batch_predictions) >= self.batch_size:
            self.flush()

    def flush(self):
        """Flush batch predictions to database."""
        if not self.batch_predictions:
            return

        cursor = self.connection.cursor()
        try:
            execute_batch(
                cursor,
                """
                    INSERT INTO ml_pipeline.predictions 
                    (user_id, churn_probability, predicted_label, features, 
                     model_version, latency_ms, from_cache)
                    VALUES (%(user_id)s, %(churn_probability)s, %(predicted_label)s,
                            %(features)s, %(model_version)s, %(latency_ms)s, %(from_cache)s)
                """,
                self.batch_predictions,
                page_size=100
            )
            self.connection.commit()
            logger.info(f"✓ Logged {len(self.batch_predictions)} predictions")
            self.batch_predictions = []
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to log predictions: {e}")
        finally:
            cursor.close()

    def update_actual_label(
        self,
        user_id: int,
        actual_churned: bool,
        observation_date: datetime
    ):
        """Update actual churn label (called after observation period)."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                UPDATE ml_pipeline.predictions
                SET is_monitored = TRUE
                WHERE user_id = %s 
                  AND prediction_time >= %s - INTERVAL '30 days'
                  AND is_monitored = FALSE
            """, (user_id, observation_date))
            self.connection.commit()
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to update actual label: {e}")
        finally:
            cursor.close()

    def compute_hourly_metrics(self, metric_date: datetime):
        """Compute hourly performance metrics from predictions."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO ml_pipeline.model_metrics
                (metric_date, metric_hour, total_predictions, positive_predictions,
                 negative_predictions, avg_probability, avg_latency_ms, 
                 cache_hit_rate, model_version)
                SELECT 
                    DATE(%s),
                    EXTRACT(HOUR FROM prediction_time)::INT,
                    COUNT(*)::INT,
                    SUM(CASE WHEN predicted_label = 1 THEN 1 ELSE 0 END)::INT,
                    SUM(CASE WHEN predicted_label = 0 THEN 1 ELSE 0 END)::INT,
                    AVG(churn_probability)::FLOAT,
                    AVG(latency_ms)::FLOAT,
                    SUM(CASE WHEN from_cache THEN 1 ELSE 0 END)::FLOAT / COUNT(*)::FLOAT,
                    model_version
                FROM ml_pipeline.predictions
                WHERE DATE(prediction_time) = DATE(%s)
                GROUP BY DATE(%s), EXTRACT(HOUR FROM prediction_time), model_version
                ON CONFLICT (metric_date, metric_hour, model_version) 
                DO UPDATE SET
                    total_predictions = EXCLUDED.total_predictions,
                    positive_predictions = EXCLUDED.positive_predictions,
                    negative_predictions = EXCLUDED.negative_predictions,
                    avg_probability = EXCLUDED.avg_probability,
                    avg_latency_ms = EXCLUDED.avg_latency_ms,
                    cache_hit_rate = EXCLUDED.cache_hit_rate
            """, (metric_date, metric_date, metric_date))
            self.connection.commit()
            logger.info(f"✓ Computed hourly metrics for {metric_date}")
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to compute hourly metrics: {e}")
        finally:
            cursor.close()

    def get_daily_metrics(self, days: int = 7) -> Dict:
        """Get daily performance metrics for the last N days."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT 
                    metric_date,
                    SUM(total_predictions)::INT AS total_predictions,
                    SUM(positive_predictions)::INT AS positive_predictions,
                    AVG(avg_probability)::FLOAT AS avg_probability,
                    AVG(avg_latency_ms)::FLOAT AS avg_latency_ms,
                    AVG(cache_hit_rate)::FLOAT AS cache_hit_rate
                FROM ml_pipeline.model_metrics
                WHERE metric_date >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY metric_date
                ORDER BY metric_date DESC
            """, (days,))
            
            rows = cursor.fetchall()
            metrics = {
                'dates': [],
                'predictions': [],
                'positive_rate': [],
                'avg_probability': [],
                'avg_latency': [],
                'cache_hit_rate': []
            }
            
            for row in rows:
                metrics['dates'].append(str(row[0]))
                metrics['predictions'].append(row[1])
                pos_rate = (row[2] / row[1] * 100) if row[1] > 0 else 0
                metrics['positive_rate'].append(pos_rate)
                metrics['avg_probability'].append(row[3])
                metrics['avg_latency'].append(row[4])
                metrics['cache_hit_rate'].append(row[5])
            
            return metrics
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to get daily metrics: {e}")
            return {}
        finally:
            cursor.close()

    def health_check(self) -> bool:
        """Check if logger is healthy."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"✗ Health check failed: {e}")
            return False
