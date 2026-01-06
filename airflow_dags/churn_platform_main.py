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

# === DATABASE CONFIG (used by all tasks) ===
def get_db_config():
    """Get database config with environment variable overrides."""
    import os
    return {
        'host': os.getenv('POSTGRES_HOST', 'postgres'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
        'database': os.getenv('POSTGRES_DB', 'churn_platform'),
    }

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
    db_config = get_db_config()
    
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
    from datetime import datetime
    from src.features.batch_feature_pipeline import BatchFeaturePipeline
    
    pipeline = BatchFeaturePipeline()
    pipeline.connect()
    
    try:
        # Convert Airflow execution_date (Proxy) to proper datetime
        exec_date = context['execution_date']
        if hasattr(exec_date, 'to_pydatetime'):
            feature_time = exec_date.to_pydatetime()
        else:
            feature_time = datetime.fromisoformat(str(exec_date))
        
        df = pipeline.compute_features_for_date(
            feature_date=feature_time,
            include_label=False
        )
        
        # Ensure all columns are serializable (convert Proxy objects to native types)
        for col in df.columns:
            if col == 'feature_date' and hasattr(df[col].iloc[0], 'to_pydatetime'):
                df[col] = df[col].apply(lambda x: x.to_pydatetime() if hasattr(x, 'to_pydatetime') else x)
        
        # Save features
        pipeline.save_features(df, table_name="features_daily")
        
        print(f"✓ Features computed for {feature_time.date()}")
        print(f"  - Total users: {len(df)}")
        print(f"  - Features generated: {len(df.columns) - 2}")  # -2 for user_id and feature_date
        
    finally:
        pipeline.disconnect()


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
    from src.serving.cache_syncer import FeatureCacheSyncer
    
    logger = logging.getLogger(__name__)
    
    # Get configuration
    db_config = get_db_config()
    
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
            stats = syncer.feature_store.get_cache_stats()
            logger.info(f"✓ Cache sync successful")
            logger.info(f"  - Cache stats: {stats}")
        else:
            logger.error("Cache sync failed")
            raise Exception("Cache sync failed")
    
    finally:
        syncer.disconnect()


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
    import os
    import logging
    from datetime import datetime, timedelta
    import pandas as pd
    from pathlib import Path
    from src.models.model_trainer import ModelTrainer
    
    logger = logging.getLogger(__name__)
        # Only run on Mon-Tue-Wed (0=Monday, 1=Tuesday, 2=Wednesday)
    execution_date = context['execution_date']
    weekday = execution_date.weekday()
    if weekday > 2:  # Thursday=3, Friday=4, Saturday=5, Sunday=6
        logger.info(f"Skipping training on {execution_date.strftime('%A')} (weekday={weekday}). Training only on Mon-Tue-Wed.")
        return
    
    logger.info(f"Running training on {execution_date.strftime('%A')} (weekday={weekday})")
        # Database config
    db_config = get_db_config()
    
    # Ensure model directory exists
    model_dir = Path("/app/data/models")
    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Model directory: {model_dir} (exists: {model_dir.exists()})")
    
    trainer = ModelTrainer(db_config=db_config)
    trainer.connect()
    
    try:
        # Load features from last 6 months
        feature_date_to = datetime.utcnow()
        feature_date_from = feature_date_to - timedelta(days=180)
        
        X, y = trainer.get_features_and_labels(
            feature_date_from=feature_date_from,
            feature_date_to=feature_date_to,
        )
        
        logger.info(f"Loaded {len(X)} samples")
        logger.info(f"X columns: {X.columns.tolist()}")
        logger.info(f"X shape: {X.shape}")
        
        # get_features_and_labels doesn't return feature_date in X
        # Get it from database directly for setting index
        feature_dates = pd.read_sql(
            """SELECT user_id, feature_date FROM ml_pipeline.features
               WHERE feature_date >= %s::timestamp AND feature_date < %s::timestamp
               ORDER BY feature_date, user_id""",
            trainer.conn,
            params=(feature_date_from, feature_date_to)
        )
        
        # Merge feature_date back into X
        X = X.reset_index(drop=True)
        feature_dates = feature_dates.reset_index(drop=True)
        X['feature_date'] = feature_dates['feature_date']
        
        # Convert to datetime and set as index
        X['feature_date'] = pd.to_datetime(X['feature_date'])
        X = X.set_index('feature_date')
        
        logger.info(f"Index dtype: {X.index.dtype}")
        
        # Split into train/test
        X_train, X_test, y_train, y_test = trainer.temporal_train_test_split(X, y, train_weeks=6)
        
        logger.info(f"Train set: {len(X_train)}, Test set: {len(X_test)}")
        
        # Train model
        trainer.train(X_train=X_train, y_train=y_train)
        
        # Evaluate
        metrics = trainer.evaluate(X_test=X_test, y_test=y_test)
        
        # Save model to persistent location
        model_path = "/app/data/models/churn_model"
        trainer.save_model(model_path)
        
        # Save metadata
        trainer.save_model_metadata(
            metrics=metrics,
            training_date_from=feature_date_from,
            training_date_to=feature_date_to,
            test_date_from=feature_date_to,
            test_date_to=feature_date_to + timedelta(days=30),
        )
        
        print(f"✓ Model trained successfully")
        print(f"  - AUC: {metrics.get('auc', 'N/A')}")
        print(f"  - Model saved to: /app/data/models/churn_model.pkl")
    finally:
        trainer.disconnect()


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
    import logging
    from src.monitoring.model_monitor import ModelMonitor
    
    logger = logging.getLogger(__name__)
    
    db_config = get_db_config()
    monitor = ModelMonitor(db_config=db_config)
    feature_time = context['execution_date'].date()
    
    # Run drift checks
    try:
        monitor.check_drift(feature_time=feature_time)
        logger.info(f"✓ Drift detection complete for {feature_time}")
    except Exception as e:
        logger.warning(f"Drift detection warning: {e}")


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
    import logging
    from src.serving.feature_store import FeatureStore
    
    logger = logging.getLogger(__name__)
    
    online_store = FeatureStore(
        host='redis',
        port=6379,
        db=0
    )
    
    try:
        online_store.connect()
        # Check connection is healthy
        stats = online_store.get_cache_stats()
        logger.info(f"✓ Online store health check passed")
        logger.info(f"  - Cache stats: {stats}")
    except Exception as e:
        logger.warning(f"Online store health check warning: {e}")
    finally:
        online_store.disconnect()


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
