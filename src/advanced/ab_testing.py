"""
A/B Testing Manager - Routes traffic between models and tracks performance.
Supports statistical significance testing for model comparison.
"""

import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import psycopg2
from scipy import stats
import numpy as np

logger = logging.getLogger(__name__)


class ABTestManager:
    """Manages A/B tests between model versions."""

    def __init__(self, db_config: Dict):
        """Initialize A/B test manager."""
        self.db_config = db_config
        self.connection = None

    def connect(self):
        """Connect to PostgreSQL."""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            logger.info("✓ Connected to PostgreSQL for A/B testing")
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to connect: {e}")
            raise

    def disconnect(self):
        """Disconnect from database."""
        if self.connection:
            self.connection.close()

    def start_test(
        self,
        test_name: str,
        control_version: str,
        variant_version: str,
        traffic_split: float = 0.5,
        duration_days: int = 7
    ) -> bool:
        """Start a new A/B test."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO ml_pipeline.ab_tests
                (test_name, control_version, variant_version, traffic_split,
                 start_date, duration_days, status)
                VALUES (%s, %s, %s, %s, CURRENT_DATE, %s, 'active')
                ON CONFLICT (test_name) DO NOTHING
            """, (test_name, control_version, variant_version, traffic_split, duration_days))
            
            self.connection.commit()
            logger.info(f"✓ Started A/B test: {test_name}")
            return True
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to start test: {e}")
            return False
        finally:
            cursor.close()

    def assign_variant(
        self,
        user_id: int,
        test_name: str,
        traffic_split: float = 0.5
    ) -> str:
        """
        Assign user to control or variant.
        Returns: 'control' or 'variant'
        """
        cursor = self.connection.cursor()
        try:
            # Check if user already assigned
            cursor.execute("""
                SELECT variant FROM ml_pipeline.ab_assignments
                WHERE user_id = %s AND test_name = %s
            """, (user_id, test_name))

            row = cursor.fetchone()
            if row:
                return row[0]

            # Get test info
            cursor.execute("""
                SELECT control_version, variant_version
                FROM ml_pipeline.ab_tests
                WHERE test_name = %s AND status = 'active'
            """, (test_name,))

            test_row = cursor.fetchone()
            if not test_row:
                return 'control'  # Default if test not found

            control_version, variant_version = test_row

            # Assign based on traffic split
            variant = 'variant' if random.random() < traffic_split else 'control'

            # Store assignment
            cursor.execute("""
                INSERT INTO ml_pipeline.ab_assignments
                (user_id, test_name, variant, control_version, variant_version)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, test_name, variant, control_version, variant_version))

            self.connection.commit()
            return variant

        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to assign variant: {e}")
            return 'control'
        finally:
            cursor.close()

    def get_variant_for_user(self, user_id: int, test_name: str) -> Optional[str]:
        """Get assigned variant for user."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT variant FROM ml_pipeline.ab_assignments
                WHERE user_id = %s AND test_name = %s
            """, (user_id, test_name))

            row = cursor.fetchone()
            return row[0] if row else None
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to get variant: {e}")
            return None
        finally:
            cursor.close()

    def log_test_prediction(
        self,
        user_id: int,
        test_name: str,
        variant: str,
        churn_prob: float,
        latency_ms: float
    ) -> bool:
        """Log prediction for A/B test analysis."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO ml_pipeline.ab_test_results
                (user_id, test_name, variant, churn_probability, latency_ms)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, test_name, variant, churn_prob, latency_ms))

            self.connection.commit()
            return True
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to log prediction: {e}")
            return False
        finally:
            cursor.close()

    def get_test_results(self, test_name: str) -> Dict:
        """Get A/B test results and statistical significance."""
        cursor = self.connection.cursor()
        try:
            # Get metrics by variant
            cursor.execute("""
                SELECT 
                    variant,
                    COUNT(*) as num_predictions,
                    AVG(churn_probability) as avg_probability,
                    STDDEV(churn_probability) as std_probability,
                    AVG(latency_ms) as avg_latency,
                    MIN(latency_ms) as min_latency,
                    MAX(latency_ms) as max_latency
                FROM ml_pipeline.ab_test_results
                WHERE test_name = %s
                GROUP BY variant
            """, (test_name,))

            rows = cursor.fetchall()
            if not rows or len(rows) < 2:
                return {'status': 'insufficient_data'}

            control_stats = {
                'variant': rows[0][0],
                'num_predictions': rows[0][1],
                'avg_probability': rows[0][2],
                'std_probability': rows[0][3],
                'avg_latency': rows[0][4],
                'min_latency': rows[0][5],
                'max_latency': rows[0][6],
            }

            variant_stats = {
                'variant': rows[1][0],
                'num_predictions': rows[1][1],
                'avg_probability': rows[1][2],
                'std_probability': rows[1][3],
                'avg_latency': rows[1][4],
                'min_latency': rows[1][5],
                'max_latency': rows[1][6],
            }

            # Statistical significance test (t-test for probability)
            prob_t_stat, prob_p_value = self._t_test(
                control_stats['avg_probability'],
                control_stats['std_probability'],
                control_stats['num_predictions'],
                variant_stats['avg_probability'],
                variant_stats['std_probability'],
                variant_stats['num_predictions']
            )

            return {
                'status': 'active',
                'control': control_stats,
                'variant': variant_stats,
                'probability_test': {
                    't_statistic': float(prob_t_stat),
                    'p_value': float(prob_p_value),
                    'significant': prob_p_value < 0.05,
                    'winner': 'variant' if (variant_stats['avg_probability'] < control_stats['avg_probability'] 
                                          and prob_p_value < 0.05) else 'control'
                }
            }

        except psycopg2.Error as e:
            logger.error(f"✗ Failed to get test results: {e}")
            return {'status': 'error'}
        finally:
            cursor.close()

    def _t_test(
        self,
        mean1: float,
        std1: float,
        n1: int,
        mean2: float,
        std2: float,
        n2: int
    ) -> Tuple[float, float]:
        """Welch's t-test for unequal variances."""
        if std1 == 0 or std2 == 0 or n1 < 2 or n2 < 2:
            return 0.0, 1.0

        t_stat = (mean1 - mean2) / np.sqrt((std1**2 / n1) + (std2**2 / n2))
        df = ((std1**2/n1 + std2**2/n2)**2) / ((std1**2/n1)**2/(n1-1) + (std2**2/n2)**2/(n2-1))
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))
        
        return float(t_stat), float(p_value)

    def end_test(self, test_name: str, winner: str) -> bool:
        """End A/B test and declare winner."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                UPDATE ml_pipeline.ab_tests
                SET status = 'completed', end_date = CURRENT_DATE, winner = %s
                WHERE test_name = %s
            """, (winner, test_name))

            self.connection.commit()
            logger.info(f"✓ Ended test {test_name}, winner: {winner}")
            return True
        except psycopg2.Error as e:
            self.connection.rollback()
            logger.error(f"✗ Failed to end test: {e}")
            return False
        finally:
            cursor.close()

    def health_check(self) -> bool:
        """Check A/B test manager health."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"✗ Health check failed: {e}")
            return False
