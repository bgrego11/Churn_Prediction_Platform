"""
Feature Store - Manages feature caching in Redis.
Provides fast feature lookup for online predictions.
"""

import logging
import json
from typing import Dict, Optional, List
import redis

logger = logging.getLogger(__name__)


class FeatureStore:
    """Redis-backed feature store for low-latency feature lookup."""

    def __init__(
        self,
        host: str = "redis",
        port: int = 6379,
        db: int = 0,
        default_ttl: int = 86400,  # 24 hours
    ):
        """
        Initialize feature store.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            default_ttl: Default time-to-live for cached features (seconds)
        """
        self.host = host
        self.port = port
        self.db = db
        self.default_ttl = default_ttl
        self.redis_client = None

    def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,  # Return strings instead of bytes
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"✓ Connected to Redis: {self.host}:{self.port}")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Disconnected from Redis")

    def set_features(
        self,
        user_id: int,
        features: Dict[str, float],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Store features for a user in Redis.

        Args:
            user_id: User identifier
            features: Dictionary of feature_name -> value
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            True if successful
        """
        if self.redis_client is None:
            raise RuntimeError("Not connected to Redis")

        key = f"user:{user_id}:features"
        ttl = ttl or self.default_ttl

        try:
            # Serialize features to JSON
            features_json = json.dumps(features)
            
            # Store with TTL
            self.redis_client.setex(key, ttl, features_json)
            
            return True
        except redis.RedisError as e:
            logger.error(f"Error setting features for user {user_id}: {e}")
            return False

    def get_features(self, user_id: int) -> Optional[Dict[str, float]]:
        """
        Retrieve features for a user from Redis.

        Args:
            user_id: User identifier

        Returns:
            Dictionary of features, or None if not found
        """
        if self.redis_client is None:
            raise RuntimeError("Not connected to Redis")

        key = f"user:{user_id}:features"

        try:
            features_json = self.redis_client.get(key)
            
            if features_json is None:
                return None
            
            return json.loads(features_json)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving features for user {user_id}: {e}")
            return None

    def delete_features(self, user_id: int) -> bool:
        """
        Delete features for a user from Redis.

        Args:
            user_id: User identifier

        Returns:
            True if successful
        """
        if self.redis_client is None:
            raise RuntimeError("Not connected to Redis")

        key = f"user:{user_id}:features"

        try:
            self.redis_client.delete(key)
            return True
        except redis.RedisError as e:
            logger.error(f"Error deleting features for user {user_id}: {e}")
            return False

    def set_batch_features(
        self,
        features_dict: Dict[int, Dict[str, float]],
        ttl: Optional[int] = None,
    ) -> int:
        """
        Store features for multiple users efficiently.

        Args:
            features_dict: Dictionary of user_id -> features_dict
            ttl: Time-to-live in seconds

        Returns:
            Number of users successfully cached
        """
        if self.redis_client is None:
            raise RuntimeError("Not connected to Redis")

        ttl = ttl or self.default_ttl
        count = 0

        # Use pipeline for batch operations (more efficient)
        pipe = self.redis_client.pipeline()

        try:
            for user_id, features in features_dict.items():
                key = f"user:{user_id}:features"
                features_json = json.dumps(features)
                pipe.setex(key, ttl, features_json)
                count += 1

            # Execute all commands at once
            pipe.execute()
            logger.info(f"✓ Cached features for {count} users in Redis")
            return count

        except redis.RedisError as e:
            logger.error(f"Error in batch set: {e}")
            return 0

    def get_batch_features(self, user_ids: List[int]) -> Dict[int, Optional[Dict]]:
        """
        Retrieve features for multiple users efficiently.

        Args:
            user_ids: List of user IDs

        Returns:
            Dictionary of user_id -> features (None if not found)
        """
        if self.redis_client is None:
            raise RuntimeError("Not connected to Redis")

        results = {}
        keys = [f"user:{uid}:features" for uid in user_ids]

        try:
            # Use pipeline for batch operations
            pipe = self.redis_client.pipeline()
            for key in keys:
                pipe.get(key)

            values = pipe.execute()

            # Parse results
            for user_id, features_json in zip(user_ids, values):
                if features_json:
                    try:
                        results[user_id] = json.loads(features_json)
                    except json.JSONDecodeError:
                        results[user_id] = None
                else:
                    results[user_id] = None

            return results

        except redis.RedisError as e:
            logger.error(f"Error in batch get: {e}")
            return {uid: None for uid in user_ids}

    def clear_all(self) -> int:
        """
        Clear all features from Redis (use with caution!).

        Returns:
            Number of keys deleted
        """
        if self.redis_client is None:
            raise RuntimeError("Not connected to Redis")

        try:
            # Find all feature keys
            pattern = "user:*:features"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                count = self.redis_client.delete(*keys)
                logger.warning(f"Cleared {count} feature keys from Redis")
                return count
            
            return 0

        except redis.RedisError as e:
            logger.error(f"Error clearing Redis: {e}")
            return 0

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        if self.redis_client is None:
            raise RuntimeError("Not connected to Redis")

        try:
            keys = self.redis_client.keys("user:*:features")
            info = self.redis_client.info("memory")

            return {
                "num_users_cached": len(keys),
                "memory_used_bytes": info.get("used_memory", 0),
                "memory_used_human": info.get("used_memory_human", "unknown"),
            }

        except redis.RedisError as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            if self.redis_client:
                self.redis_client.ping()
                return True
        except redis.RedisError:
            pass
        
        return False
