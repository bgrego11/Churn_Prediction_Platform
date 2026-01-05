# ============================================================================
# MASTER DAG ORCHESTRATOR
# Defines the complete data pipeline workflow
# 
# DAG: churn_platform_main
# Schedule: Daily at 1 AM UTC
# 
# Dependency Graph:
#   generate_data (or skip if data exists)
#       ↓
#   compute_features (daily increment)
#       ↓
#   sync_online_features (push to Redis)
#       ↓
#   train_model (weekly, Mon-Wed)
#       ↓
#   run_drift_detection (daily)
#       ↓
#   validate_predictions (log only)
# ============================================================================

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.trigger_rule import TriggerRule

# Default arguments for all tasks
default_args = {
    'owner': 'churn_platform',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# === DAG DEFINITION ===
dag = DAG(
    'churn_platform_main',
    default_args=default_args,
    description='Main orchestration pipeline for churn prediction platform',
    schedule_interval='0 1 * * *',  # Daily at 1 AM UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['churn_platform', 'ml', 'production'],
    max_active_runs=1,  # Only one DAG run at a time
)

# ============================================================================
# TASK 1: SYNTHETIC DATA GENERATION
# - Backfill: One-time, disabled after initial setup
# - Daily: Generate features for new users/events
# ============================================================================

def task_generate_synthetic_data(**context):
    """Generate and load synthetic data for the platform."""
    import logging
    from src.data_generation.generator import SyntheticDataGenerator
    from src.data_generation.loaders import load_data
    
    logger = logging.getLogger(__name__)
    
    # Get parameters from Airflow variables
    num_users = int(context['var']['value'].get('synthetic_num_users', 10000))
    # NOTE: Backfill has been completed. Set to 0 to only generate new daily data.
    # On initial setup, use backfill_months=12. After backfill completes, set to 0.
    backfill_months = int(context['var']['value'].get('backfill_months', 0))
    seed = int(context['var']['value'].get('synthetic_data_seed', 42))
    
    logger.info(f"Generating synthetic data: {num_users} users, {backfill_months} months backfill")
    
    # Generate synthetic data
    generator = SyntheticDataGenerator(seed=seed)
    users, user_events, billing_events = generator.generate_all(
        num_users=num_users,
        churn_rate=0.15,  # 15% churn rate
        backfill_days=backfill_months * 30,
    )
    
    logger.info(f"Generated {len(users)} users, {len(user_events)} events, {len(billing_events)} billing records")
    
    # Load into PostgreSQL
    db_config = {
        'host': context['var']['value'].get('postgres_host', 'postgres'),
        'port': int(context['var']['value'].get('postgres_port', 5432)),
        'database': context['var']['value'].get('postgres_db', 'churn_db'),
        'user': context['var']['value'].get('postgres_user', 'churn_user'),
        'password': context['var']['value'].get('postgres_password', 'churn_password'),
    }
    
    counts = load_data(
        users=users,
        user_events=user_events,
        billing_events=billing_events,
        **db_config
    )
    
    logger.info(f"Data loaded successfully: {counts}")
    return counts


generate_data = PythonOperator(
    task_id='generate_synthetic_data',
    python_callable=task_generate_synthetic_data,
    provide_context=True,
    dag=dag,
)

# ============================================================================
# TASK 2: COMPUTE FEATURES (Batch Feature Pipeline)
# - Point-in-time correct feature computation
# - Window: T-90d to T
# - Label window: T to T+30d
# ============================================================================

def task_compute_features(**context):
    """Compute features with point-in-time correctness."""
    from src.features.batch_feature_pipeline import BatchFeaturePipeline
    
    pipeline = BatchFeaturePipeline()
    
    # Daily incremental feature computation
    feature_time = context['execution_date'].date()
    pipeline.compute_daily_features(feature_time=feature_time)
    
    # Log statistics
    stats = pipeline.get_stats()
    print(f"✓ Features computed for {feature_time}")
    print(f"  - Total users: {stats['num_users']}")
    print(f"  - Features generated: {stats['num_features']}")


compute_features = PythonOperator(
    task_id='compute_features',
    python_callable=task_compute_features,
    provide_context=True,
    dag=dag,
)

# ============================================================================
# TASK 3: SYNC ONLINE FEATURE STORE
# - Push latest features from offline → online (Redis)
# - Only latest feature vector per user
# ============================================================================

def task_sync_online_features(**context):
    """Sync latest features to Redis online store using FeatureCacheSyncer."""
    import logging
    import os
    from datetime import datetime
    from src.serving import FeatureCacheSyncer
    
    logger = logging.getLogger(__name__)
    
    # Get configuration from environment
    db_config = {
        "host": os.getenv("POSTGRES_HOST", "postgres"),
        "port": int(os.getenv("POSTGRES_PORT", 5432)),
        "database": os.getenv("POSTGRES_DB", "churn_db"),
        "user": os.getenv("POSTGRES_USER", "churn_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "churn_password"),
    }
    
    redis_config = {
        "host": os.getenv("REDIS_HOST", "redis"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "db": int(os.getenv("REDIS_DB", 0)),
    }
    
    logger.info("Starting online feature cache sync...")
    
    # Initialize syncer
    syncer = FeatureCacheSyncer(
        db_config=db_config,
        redis_config=redis_config,
    )
    
    try:
        syncer.connect()
        
        # Sync features for today
        feature_date = datetime.utcnow()
        success = syncer.sync_cache(feature_date=feature_date)
        
        if success:
            # Get sync status
            status = syncer.get_sync_status()
            logger.info(f"✓ Cache sync successful")
            logger.info(f"  - Users cached: {status.get('num_users_cached', 0)}")
            logger.info(f"  - Memory used: {status.get('memory_used', 'unknown')}")
        else:
            logger.error("Cache sync failed")
            raise Exception("Cache sync failed")
    
    finally:
        syncer.disconnect()
    online_store = OnlineFeatureStore()
    
    # Get latest features for all users
    feature_time = context['execution_date'].date()
    latest_features = offline_store.get_latest_features(feature_time=feature_time)
    
    # Push to Redis
    synced_count = online_store.sync_features(features_df=latest_features)
    print(f"✓ Synced {synced_count} features to online store")


sync_online_features = PythonOperator(
    task_id='sync_online_features',
    python_callable=task_sync_online_features,
    provide_context=True,
    dag=dag,
)

# ============================================================================
# TASK 4: TRAIN MODEL (Conditional, Weekly)
# - Only runs on specific days (Monday, Tuesday, Wednesday)
# - Trains on last 6 months of data
# - Saves model artifact + metadata
# ============================================================================

def task_train_model(**context):
    """Train baseline logistic regression model."""
    from src.models.training import ModelTrainer
    
    trainer = ModelTrainer()
    feature_time = context['execution_date'].date()
    
    # Train on last 6 months
    model_version = trainer.train(feature_time=feature_time, lookback_days=180)
    
    print(f"✓ Model trained: v{model_version}")
    print(f"  - Training data window: last 180 days")
    print(f"  - Model artifact saved to registry")


train_model = PythonOperator(
    task_id='train_model',
    python_callable=task_train_model,
    provide_context=True,
    # Only run on Mon-Wed (0=Monday, 1=Tuesday, 2=Wednesday)
    pool_slots=1,
    dag=dag,
)

# Add conditional to only run on certain days
train_model.set_upstream([sync_online_features])

# ============================================================================
# TASK 5: RUN DRIFT DETECTION
# - Compare feature distributions vs training baseline
# - Compute PSI, z-scores
# - Log drift alerts
# ============================================================================

def task_run_drift_detection(**context):
    """Detect feature and prediction drift."""
    from src.monitoring.drift_detection import DriftDetector
    
    detector = DriftDetector()
    feature_time = context['execution_date'].date()
    
    # Run drift checks
    drift_report = detector.detect(feature_time=feature_time)
    
    # Log results
    print(f"✓ Drift detection complete for {feature_time}")
    print(f"  - Features with drift: {len(drift_report['drifted_features'])}")
    if drift_report['drifted_features']:
        print(f"  - Alert: {drift_report['drifted_features']}")


run_drift_detection = PythonOperator(
    task_id='run_drift_detection',
    python_callable=task_run_drift_detection,
    provide_context=True,
    trigger_rule=TriggerRule.ALL_DONE,  # Run regardless of upstream status
    dag=dag,
)

# ============================================================================
# TASK 6: VALIDATE PREDICTION SCHEMA
# - Check online store is healthy
# - Validate feature schema
# - Log schema drift
# ============================================================================

def task_validate_schema(**context):
    """Validate feature schema and online store health."""
    from src.stores.online_store import OnlineFeatureStore
    from src.utils.schema_validation import SchemaValidator
    
    online_store = OnlineFeatureStore()
    validator = SchemaValidator()
    
    # Check online store health
    health = online_store.health_check()
    print(f"✓ Online store health: {health['status']}")
    print(f"  - Keys in Redis: {health['key_count']}")
    
    # Validate schema
    schema_valid = validator.validate_schema()
    if not schema_valid:
        print(f"⚠ Schema validation failed")


validate_schema = PythonOperator(
    task_id='validate_schema',
    python_callable=task_validate_schema,
    provide_context=True,
    trigger_rule=TriggerRule.ALL_DONE,
    dag=dag,
)

# ============================================================================
# DAG DEPENDENCIES
# ============================================================================

generate_data >> compute_features >> sync_online_features
sync_online_features >> train_model
sync_online_features >> run_drift_detection >> validate_schema
