"""
Feature Cache Syncer - Pre-computes and caches features for all users.
Designed to run as a scheduled background job (Airflow).
"""

import logging
from datetime import datetime
from typing import Dict
import psycopg2

from src.features.batch_feature_pipeline import BatchFeaturePipeline
from .feature_store import FeatureStore

logger = logging.getLogger(__name__)


class FeatureCacheSyncer:
    """Syncs features to Redis cache for online serving."""

    def __init__(
        self,
        db_config: Dict[str, str],
        redis_config: Dict[str, str],
    ):
        """
        Initialize syncer.

        Args:
            db_config: Database configuration
            redis_config: Redis configuration
        """
        self.db_config = db_config
        self.redis_config = redis_config
        self.feature_pipeline = None
        self.feature_store = None

    def connect(self) -> None:
        """Connect to database and Redis."""
        self.feature_pipeline = BatchFeaturePipeline(
            host=self.db_config.get("host", "postgres"),
            port=self.db_config.get("port", 5432),
            database=self.db_config.get("database", "churn_db"),
            user=self.db_config.get("user", "churn_user"),
            password=self.db_config.get("password", "churn_password"),
        )
        self.feature_pipeline.connect()

        self.feature_store = FeatureStore(
            host=self.redis_config.get("host", "redis"),
            port=self.redis_config.get("port", 6379),
            db=self.redis_config.get("db", 0),
        )
        self.feature_store.connect()

        logger.info("✓ Connected to database and Redis")

    def disconnect(self) -> None:
        """Disconnect from database and Redis."""
        if self.feature_pipeline:
            self.feature_pipeline.disconnect()
        if self.feature_store:
            self.feature_store.disconnect()
        logger.info("Disconnected from database and Redis")

    def sync_cache(self, feature_date: datetime = None) -> bool:
        """
        Compute features for all users and cache them in Redis.

        This is the main method called by Airflow scheduler.

        Args:
            feature_date: Feature computation date (defaults to today)

        Returns:
            True if successful
        """
        if not feature_date:
            feature_date = datetime.utcnow()

        logger.info(f"Starting cache sync for {feature_date.date()}...")

        try:
            # Step 1: Get all user IDs
            logger.info("Step 1: Fetching user IDs...")
            user_ids = self.feature_pipeline.get_all_users()
            logger.info(f"  Found {len(user_ids)} users")

            # Step 2: Compute features for all users
            logger.info("Step 2: Computing features...")
            features_dict = self._compute_features_for_all_users(user_ids, feature_date)
            logger.info(f"  Computed features for {len(features_dict)} users")

            # Step 3: Cache in Redis
            logger.info("Step 3: Caching features in Redis...")
            cached_count = self.feature_store.set_batch_features(features_dict)
            logger.info(f"  ✓ Cached {cached_count} users in Redis")

            # Step 4: Verify cache
            logger.info("Step 4: Verifying cache...")
            stats = self.feature_store.get_cache_stats()
            logger.info(f"  Cache stats: {stats}")

            logger.info(f"✅ Cache sync completed successfully at {datetime.utcnow()}")
            return True

        except Exception as e:
            logger.error(f"❌ Cache sync failed: {e}", exc_info=True)
            return False

    def _compute_features_for_all_users(
        self,
        user_ids: list,
        feature_date: datetime,
    ) -> Dict[int, Dict[str, float]]:
        """
        Compute features for all users at a specific date.

        Args:
            user_ids: List of user IDs
            feature_date: Feature computation date

        Returns:
            Dictionary of user_id -> features_dict
        """
        features_dict = {}

        logger.info(f"Computing features for {len(user_ids)} users at {feature_date.date()}...")

        for idx, user_id in enumerate(user_ids):
            if (idx + 1) % 100 == 0:
                logger.info(f"  Progress: {idx + 1}/{len(user_ids)}")

            try:
                # Compute all features for this user
                features = self.feature_pipeline.compute_features_for_user(
                    user_id=user_id,
                    feature_date=feature_date,
                    feature_names=None,  # Uses default extended features
                )

                # Convert to flat dictionary (remove metadata if present)
                features_clean = {
                    k: v for k, v in features.items()
                    if k not in ["user_id", "feature_date"]
                }

                features_dict[user_id] = features_clean

            except Exception as e:
                logger.warning(f"Error computing features for user {user_id}: {e}")
                # Use default feature values on error
                features_dict[user_id] = self._get_default_features()

        return features_dict

    @staticmethod
    def _get_default_features() -> Dict[str, float]:
        """
        Get default feature values (used when computation fails).

        Returns:
            Dictionary with all features set to 0/safe values
        """
        return {
            "avg_sessions_7d": 0.0,
            "sessions_30d": 0,
            "days_since_last_login": 9999,
            "events_30d": 0,
            "failed_payments_30d": 0,
            "total_spend_90d": 0.0,
            "refunds_30d": 0,
            "is_pro_plan": 0,
            "is_paid_plan": 0,
            "days_since_signup": 0,
        }

    def get_sync_status(self) -> Dict:
        """
        Get status of the feature cache.

        Returns:
            Dictionary with cache status info
        """
        try:
            stats = self.feature_store.get_cache_stats()
            is_healthy = self.feature_store.health_check()

            return {
                "healthy": is_healthy,
                "num_users_cached": stats.get("num_users_cached", 0),
                "memory_used": stats.get("memory_used_human", "unknown"),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {
                "healthy": False,
                "error": str(e),
            }
