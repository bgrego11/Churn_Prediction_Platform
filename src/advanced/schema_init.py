"""
Phase 7 schema initialization - Creates tables for model versioning, A/B testing, and retraining.
"""

import psycopg2
import logging

logger = logging.getLogger(__name__)


def init_phase7_schema(db_config: dict):
    """Initialize Phase 7 database schema."""
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        # A/B test metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_pipeline.ab_tests (
                test_id SERIAL PRIMARY KEY,
                test_name VARCHAR(100) NOT NULL UNIQUE,
                control_version VARCHAR(50) NOT NULL,
                variant_version VARCHAR(50) NOT NULL,
                traffic_split FLOAT DEFAULT 0.5,
                start_date DATE DEFAULT CURRENT_DATE,
                end_date DATE,
                duration_days INT,
                status VARCHAR(20) DEFAULT 'active',
                winner VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (control_version) REFERENCES ml_pipeline.model_versions(version),
                FOREIGN KEY (variant_version) REFERENCES ml_pipeline.model_versions(version)
            )
        """)
        
        # A/B test results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ml_pipeline.ab_test_results (
                result_id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                test_name VARCHAR(100) NOT NULL,
                variant VARCHAR(20) NOT NULL,
                churn_probability FLOAT NOT NULL,
                latency_ms FLOAT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (test_name) REFERENCES ml_pipeline.ab_tests(test_name)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ab_results_test 
                ON ml_pipeline.ab_test_results(test_name)
        """)
        
        conn.commit()
        logger.info("✓ Phase 7 schema initialized")
        return True
        
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"✗ Failed to initialize schema: {e}")
        return False
    finally:
        cursor.close()
        conn.close()
