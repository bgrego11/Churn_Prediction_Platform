# ============================================================================
# CONFIG LOADER - Centralized Configuration Management
# ============================================================================

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Centralized configuration object."""
    
    # === APPLICATION ===
    ENV = os.getenv('ENV', 'development')
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    PROJECT_NAME = os.getenv('PROJECT_NAME', 'churn-prediction-platform')
    
    # === POSTGRES (Raw Data) ===
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'churn_db')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'churn_user')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'churn_password')
    
    # === REDIS (Online Feature Store) ===
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
    
    # === PATHS ===
    OFFLINE_FEATURE_STORE_PATH = os.getenv(
        'OFFLINE_FEATURE_STORE_PATH',
        '/Users/ben/Churn_Prediction_Platform/data/features'
    )
    MODEL_ARTIFACT_PATH = os.getenv(
        'MODEL_ARTIFACT_PATH',
        '/Users/ben/Churn_Prediction_Platform/data/models'
    )
    RAW_DATA_PATH = os.getenv(
        'RAW_DATA_PATH',
        '/Users/ben/Churn_Prediction_Platform/data/raw'
    )
    LOGS_PATH = os.getenv(
        'LOGS_PATH',
        '/Users/ben/Churn_Prediction_Platform/data/logs'
    )
    
    # === FASTAPI ===
    FASTAPI_HOST = os.getenv('FASTAPI_HOST', '0.0.0.0')
    FASTAPI_PORT = int(os.getenv('FASTAPI_PORT', 8000))
    FASTAPI_WORKERS = int(os.getenv('FASTAPI_WORKERS', 4))
    
    # === DATA GENERATION ===
    SYNTHETIC_DATA_SEED = int(os.getenv('SYNTHETIC_DATA_SEED', 42))
    BACKFILL_MONTHS = int(os.getenv('BACKFILL_MONTHS', 12))
    SYNTHETIC_NUM_USERS = int(os.getenv('SYNTHETIC_NUM_USERS', 10000))
    
    # === MONITORING ===
    DRIFT_PSI_THRESHOLD = float(os.getenv('DRIFT_PSI_THRESHOLD', 0.1))
    DRIFT_ZSCORE_THRESHOLD = float(os.getenv('DRIFT_ZSCORE_THRESHOLD', 3.0))
    
    # === COMPUTED CONNECTION STRINGS ===
    @property
    def POSTGRES_CONNECTION_STRING(self) -> str:
        """PostgreSQL connection string for SQLAlchemy."""
        return (
            f'postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}'
            f'@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}'
        )
    
    @property
    def REDIS_CONNECTION_STRING(self) -> str:
        """Redis connection string."""
        password_part = f':{self.REDIS_PASSWORD}@' if self.REDIS_PASSWORD else ''
        return f'redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}'
    
    def to_dict(self) -> Dict[str, Any]:
        """Export config as dictionary."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


# Singleton instance
config = Config()
