# ============================================================================
# AIRFLOW CONFIGURATION & SETUP
# ============================================================================
# This file configures Airflow-specific settings for the Churn Platform.
# Environment variables override these settings.

import os
from datetime import timedelta

# === CORE SETTINGS ===
AIRFLOW_HOME = os.getenv('AIRFLOW_HOME', '/Users/ben/Churn_Prediction_Platform/airflow')
DAGS_FOLDER = os.getenv('AIRFLOW__CORE__DAGS_FOLDER', '/Users/ben/Churn_Prediction_Platform/airflow_dags')

# === DATABASE ===
# Using Postgres for Airflow metadata store
SQL_ALCHEMY_CONN = os.getenv(
    'AIRFLOW__DATABASE__SQL_ALCHEMY_CONN',
    'postgresql+psycopg2://churn_user:churn_password@localhost:5432/airflow_db'
)

# === EXECUTOR ===
# LocalExecutor: Single machine, sequential + parallel task execution
# Good for development and small deployments
EXECUTOR = os.getenv('AIRFLOW__CORE__EXECUTOR', 'LocalExecutor')

# === LOAD EXAMPLES ===
LOAD_EXAMPLES = os.getenv('AIRFLOW__CORE__LOAD_EXAMPLES', 'false').lower() == 'true'
LOAD_DEFAULT_CONNECTIONS = os.getenv('AIRFLOW__CORE__LOAD_DEFAULT_CONNECTIONS', 'false').lower() == 'true'

# === SECURITY ===
# Secrets backend (can be extended to use Vault, AWS Secrets Manager, etc.)
FERNET_KEY = os.getenv(
    'AIRFLOW__CORE__FERNET_KEY',
    'default-insecure-key-for-development-only'  # CHANGE IN PRODUCTION
)

# === LOGGING ===
LOGS_FOLDER = os.getenv('AIRFLOW__LOGGING__BASE_LOG_FOLDER', '/Users/ben/Churn_Prediction_Platform/airflow/logs')

# === DEFAULT DAG SETTINGS ===
DEFAULT_DAG_ARGS = {
    'owner': 'churn_platform',
    'depends_on_past': False,
    'email': ['admin@churnplatform.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# === SCHEDULING ===
DAG_DEFAULT_VIEW = 'tree'
DEFAULT_VIEW = 'tree'

# === AIRFLOW UI ===
WEBSERVER_PORT = int(os.getenv('AIRFLOW__WEBSERVER__WEB_SERVER_PORT', 8080))
