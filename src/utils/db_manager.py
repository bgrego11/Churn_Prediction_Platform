# ============================================================================
# DATABASE CONNECTION MANAGER
# Provides singleton connections to Postgres and Redis
# ============================================================================

from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from redis import Redis
from src.utils.config import config

class DatabaseManager:
    """Manages database connections."""
    
    _postgres_engine: Optional[Engine] = None
    _postgres_session_maker: Optional[sessionmaker] = None
    _redis_client: Optional[Redis] = None
    
    @classmethod
    def get_postgres_engine(cls) -> Engine:
        """Get or create Postgres connection engine."""
        if cls._postgres_engine is None:
            cls._postgres_engine = create_engine(
                config.POSTGRES_CONNECTION_STRING,
                echo=config.DEBUG,
                pool_pre_ping=True,  # Test connection before using
                pool_size=10,
                max_overflow=20,
            )
        return cls._postgres_engine
    
    @classmethod
    def get_postgres_session(cls) -> Session:
        """Get new Postgres session."""
        if cls._postgres_session_maker is None:
            engine = cls.get_postgres_engine()
            cls._postgres_session_maker = sessionmaker(bind=engine, expire_on_commit=False)
        return cls._postgres_session_maker()
    
    @classmethod
    def get_redis_client(cls) -> Redis:
        """Get or create Redis client."""
        if cls._redis_client is None:
            cls._redis_client = Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD or None,
                decode_responses=True,  # Decode strings automatically
            )
            # Test connection
            cls._redis_client.ping()
        return cls._redis_client
    
    @classmethod
    def close_all(cls):
        """Close all connections."""
        if cls._postgres_engine:
            cls._postgres_engine.dispose()
            cls._postgres_engine = None
            cls._postgres_session_maker = None
        if cls._redis_client:
            cls._redis_client.close()
            cls._redis_client = None


# Convenience functions
def get_postgres_session() -> Session:
    """Get Postgres session."""
    return DatabaseManager.get_postgres_session()

def get_redis_client() -> Redis:
    """Get Redis client."""
    return DatabaseManager.get_redis_client()
