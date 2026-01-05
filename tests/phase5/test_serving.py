"""
Phase 5 Test: Online Feature Serving
Tests the complete online prediction pipeline with cached features.
"""

import os
import sys
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

from src.serving import FeatureStore, FeatureCacheSyncer, OnlineFeatureServer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_db_config():
    """Get database configuration."""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", 5433)),
        "database": os.getenv("POSTGRES_DB", "churn_db"),
        "user": os.getenv("POSTGRES_USER", "churn_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "churn_password"),
    }


def get_redis_config():
    """Get Redis configuration."""
    return {
        "host": os.getenv("REDIS_HOST", "localhost"),
        "port": int(os.getenv("REDIS_PORT", 6379)),
        "db": int(os.getenv("REDIS_DB", 0)),
    }


def test_feature_store():
    """Test 1: Feature Store (Redis connectivity and caching)."""
    print("\n[TEST 1] Feature Store - Redis caching\n")
    
    redis_config = get_redis_config()
    store = FeatureStore(
        host=redis_config["host"],
        port=redis_config["port"],
        db=redis_config["db"],
    )
    
    try:
        store.connect()
        print("✓ Connected to Redis")
        
        # Test single feature set/get
        test_features = {
            "avg_sessions_7d": 0.5,
            "sessions_30d": 10,
            "days_since_last_login": 5,
            "events_30d": 20,
            "failed_payments_30d": 1,
            "total_spend_90d": 150.0,
            "refunds_30d": 0,
            "is_pro_plan": 1,
            "is_paid_plan": 1,
            "days_since_signup": 100,
        }
        
        user_id = 123
        store.set_features(user_id, test_features)
        print(f"✓ Set features for user {user_id}")
        
        retrieved = store.get_features(user_id)
        assert retrieved == test_features, "Retrieved features don't match"
        print(f"✓ Retrieved features for user {user_id}")
        
        # Test batch operations
        batch_features = {
            i: {k: v * (i % 5 + 1) / 10 for k, v in test_features.items()}
            for i in range(1, 11)
        }
        
        count = store.set_batch_features(batch_features)
        print(f"✓ Set batch features for {count} users")
        
        batch_retrieved = store.get_batch_features(list(range(1, 11)))
        print(f"✓ Retrieved batch features for {len(batch_retrieved)} users")
        
        # Cache stats
        stats = store.get_cache_stats()
        print(f"✓ Cache stats:")
        print(f"  - Users cached: {stats['num_users_cached']}")
        print(f"  - Memory used: {stats['memory_used_human']}")
        
        return True
    
    except Exception as e:
        print(f"✗ Feature store test failed: {e}")
        return False
    
    finally:
        store.disconnect()


def test_cache_syncer():
    """Test 2: Cache Syncer (populate cache from database)."""
    print("\n[TEST 2] Cache Syncer - Populate cache from database\n")
    
    db_config = get_db_config()
    redis_config = get_redis_config()
    
    syncer = FeatureCacheSyncer(
        db_config=db_config,
        redis_config=redis_config,
    )
    
    try:
        syncer.connect()
        print("✓ Connected to database and Redis")
        
        # Sync cache
        print("Syncing feature cache (this may take a minute)...")
        success = syncer.sync_cache()
        
        if success:
            print("✓ Cache sync successful")
            
            # Check status
            status = syncer.get_sync_status()
            print(f"✓ Sync status:")
            print(f"  - Healthy: {status['healthy']}")
            print(f"  - Users cached: {status['num_users_cached']}")
            print(f"  - Memory used: {status['memory_used']}")
            return True
        else:
            print("✗ Cache sync failed")
            return False
    
    except Exception as e:
        print(f"✗ Cache syncer test failed: {e}")
        return False
    
    finally:
        syncer.disconnect()


def test_online_server():
    """Test 3: Online Feature Server (inference with cached features)."""
    print("\n[TEST 3] Online Feature Server - Single & batch predictions\n")
    
    redis_config = get_redis_config()
    
    # Initialize feature store
    feature_store = FeatureStore(
        host=redis_config["host"],
        port=redis_config["port"],
        db=redis_config["db"],
    )
    
    try:
        feature_store.connect()
        print("✓ Connected to Redis")
        
        # Initialize server
        model_path = "/tmp/churn_model"
        server = OnlineFeatureServer(
            model_path=model_path,
            feature_store=feature_store,
        )
        print("✓ Initialized online server")
        
        # Test single prediction
        print("\nTesting single prediction...")
        result = server.predict(user_id=1)
        
        if result.get("error"):
            print(f"✗ Prediction failed: {result['error']}")
            return False
        
        print(f"✓ Single prediction successful")
        print(f"  - User ID: {result['user_id']}")
        print(f"  - Churn probability: {result['churn_probability']:.4f}")
        print(f"  - Predicted label: {result['churn_label']}")
        print(f"  - Latency: {result['latency_ms']:.2f}ms")
        print(f"  - From cache: {result['from_cache']}")
        
        # Test batch prediction
        print("\nTesting batch predictions (100 users)...")
        test_users = list(range(1, 101))
        predictions = server.predict_batch(test_users)
        
        successful = sum(1 for p in predictions if p.get("churn_probability") is not None)
        print(f"✓ Batch prediction complete")
        print(f"  - Requested: {len(test_users)} users")
        print(f"  - Successful: {successful} predictions")
        print(f"  - Failed: {len(test_users) - successful} predictions")
        
        # Check latency
        total_latency = sum(p.get("latency_ms", 0) for p in predictions if "latency_ms" in p)
        avg_latency = total_latency / len(predictions) if predictions else 0
        print(f"  - Average latency: {avg_latency:.2f}ms per user")
        
        # Test explanation
        print("\nTesting feature explanation...")
        explanation = server.get_feature_explanation(user_id=1)
        
        if explanation:
            print(f"✓ Feature explanation available")
            print(f"  - Intercept: {explanation['intercept']:.4f}")
            print(f"  - Top 5 features by impact:")
            sorted_features = sorted(
                explanation['features'].items(),
                key=lambda x: abs(x[1]['contribution']),
                reverse=True
            )[:5]
            for feature_name, data in sorted_features:
                print(f"    • {feature_name}: {data['contribution']:.4f}")
        else:
            print("✗ Could not generate explanation")
            return False
        
        # Health check
        print("\nTesting health check...")
        health = server.health_check()
        print(f"✓ Health check:")
        print(f"  - Model loaded: {health['model_loaded']}")
        print(f"  - Scaler loaded: {health['scaler_loaded']}")
        print(f"  - Cache healthy: {health['feature_cache_healthy']}")
        
        return True
    
    except Exception as e:
        print(f"✗ Online server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        feature_store.disconnect()


def test_prediction_speed():
    """Test 4: Prediction Speed (benchmark)."""
    print("\n[TEST 4] Prediction Speed Benchmark\n")
    
    import time
    
    redis_config = get_redis_config()
    feature_store = FeatureStore(
        host=redis_config["host"],
        port=redis_config["port"],
        db=redis_config["db"],
    )
    
    try:
        feature_store.connect()
        
        model_path = "/tmp/churn_model"
        server = OnlineFeatureServer(
            model_path=model_path,
            feature_store=feature_store,
        )
        
        # Warmup
        server.predict(1)
        
        # Benchmark 1000 predictions
        print("Benchmarking 1,000 single predictions...")
        start = time.time()
        for user_id in range(1, 1001):
            result = server.predict(user_id)
            if result.get("error"):
                raise Exception(f"Prediction failed for user {user_id}")
        elapsed = time.time() - start
        
        avg_latency = (elapsed * 1000) / 1000  # ms
        qps = 1000 / elapsed  # queries per second
        
        print(f"✓ Benchmark results:")
        print(f"  - Total time: {elapsed:.2f}s")
        print(f"  - Average latency: {avg_latency:.2f}ms")
        print(f"  - Throughput: {qps:.0f} predictions/second")
        
        # Goal: <50ms per prediction, >20 predictions/second
        if avg_latency < 50 and qps > 20:
            print(f"✓ Performance targets met!")
            return True
        else:
            print(f"✗ Performance below targets")
            return False
    
    except Exception as e:
        print(f"✗ Speed benchmark failed: {e}")
        return False
    
    finally:
        feature_store.disconnect()


def main():
    """Run all Phase 5 tests."""
    
    print("=" * 80)
    print("PHASE 5: ONLINE FEATURE SERVING TEST")
    print("=" * 80)
    
    results = {}
    
    # Run tests
    results["Feature Store"] = test_feature_store()
    results["Cache Syncer"] = test_cache_syncer()
    results["Online Server"] = test_online_server()
    results["Prediction Speed"] = test_prediction_speed()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ PHASE 5 TEST SUCCESSFUL - Online serving ready for deployment!")
        print("\nNext Steps:")
        print("  1. Configure Airflow to schedule cache sync daily")
        print("  2. Deploy FastAPI with docker-compose up")
        print("  3. Test API endpoints:")
        print("     - GET /health")
        print("     - GET /predict/1")
        print("     - POST /predict/batch")
        print("  4. Phase 6: Model deployment & monitoring")
    else:
        print("\n❌ PHASE 5 TEST FAILED - Fix issues above")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
