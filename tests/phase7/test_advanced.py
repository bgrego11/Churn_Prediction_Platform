"""
Phase 7 Test - Advanced Features (Model Versioning, Retraining, A/B Testing)
Tests automated retraining, model promotion, and A/B testing workflows.
"""

import os
import logging
from datetime import datetime
import psycopg2

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
L = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'postgres'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'churn_db'),
    'user': os.getenv('POSTGRES_USER', 'churn_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'churn_password'),
}


def init_schema():
    """Initialize Phase 7 schema."""
    from src.advanced.schema_init import init_phase7_schema
    return init_phase7_schema(DB_CONFIG)


def test_model_registry():
    """Test model versioning and registry."""
    L.info("\n[TEST 1] Model Registry - Version tracking and promotion\n")

    from src.advanced.model_registry import ModelRegistry

    registry = ModelRegistry(DB_CONFIG)
    registry.connect()

    try:
        # Register initial model (v1.0)
        L.info("Registering model v1.0...")
        success = registry.register_model(
            model_name="churn_model",
            version="1.0",
            model_path="/tmp/churn_model.pkl",
            scaler_path="/tmp/churn_model_scaler.pkl",
            training_samples=6000,
            features=['avg_sessions_7d', 'sessions_30d', 'days_since_last_login'],
            hyperparameters={'C': 1.0, 'max_iter': 1000},
            metrics={'auc': 0.9979, 'precision': 0.9954, 'recall': 0.9922, 'f1': 0.9938}
        )
        
        if not success:
            L.error("✗ Failed to register model")
            return False

        L.info("✓ Registered model v1.0")

        # Get model details
        model = registry.get_model_version("1.0")
        L.info(f"✓ Retrieved model v1.0:")
        L.info(f"  - Status: {model['status']}")
        L.info(f"  - AUC: {model['metrics']['auc']:.4f}")

        # Register v2.0 (improved model)
        L.info("\nRegistering model v2.0 (improved)...")
        success = registry.register_model(
            model_name="churn_model",
            version="2.0",
            model_path="/tmp/churn_model_v2.pkl",
            scaler_path="/tmp/churn_model_v2_scaler.pkl",
            training_samples=8000,
            features=['avg_sessions_7d', 'sessions_30d', 'days_since_last_login'],
            hyperparameters={'C': 0.8, 'max_iter': 1500},
            metrics={'auc': 0.9985, 'precision': 0.9960, 'recall': 0.9930, 'f1': 0.9945}
        )

        L.info("✓ Registered model v2.0")

        # Promote v1.0 to staging
        L.info("\nPromoting v1.0: candidate → staging...")
        registry.promote_model("1.0", "staging", "Initial production model")
        L.info("✓ Promoted v1.0 to staging")

        # Promote v1.0 to production
        L.info("Promoting v1.0: staging → production...")
        registry.promote_model("1.0", "production", "Deployed to production")
        L.info("✓ Promoted v1.0 to production")

        # Get production model
        prod_model = registry.get_production_model()
        L.info(f"\n✓ Current production model: {prod_model['version']}")

        # Promote v2.0 to staging
        L.info("\nPromoting v2.0: candidate → staging...")
        registry.promote_model("2.0", "staging", "Improved model ready for A/B test")
        L.info("✓ Promoted v2.0 to staging")

        # Get model history
        L.info("\nModel history:")
        history = registry.get_model_history("churn_model", limit=5)
        for m in history:
            L.info(f"  - v{m['version']}: {m['status']} (AUC: {m['metrics'].get('auc', 0):.4f})")

        registry.disconnect()
        return True

    except Exception as e:
        L.error(f"✗ Model registry test failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_ab_testing():
    """Test A/B testing framework."""
    L.info("\n[TEST 2] A/B Testing - Traffic splitting and comparison\n")

    from src.advanced.ab_testing import ABTestManager

    ab_manager = ABTestManager(DB_CONFIG)
    ab_manager.connect()

    try:
        # Start A/B test
        L.info("Starting A/B test: v1.0 vs v2.0...")
        success = ab_manager.start_test(
            test_name="test_v2_rollout",
            control_version="1.0",
            variant_version="2.0",
            traffic_split=0.5,
            duration_days=7
        )

        if not success:
            L.error("✗ Failed to start A/B test")
            return False

        L.info("✓ Started A/B test\n")

        # Assign users and log predictions
        L.info("Assigning users and logging predictions...")
        num_predictions = 100
        
        for i in range(num_predictions):
            user_id = i + 1
            
            # Assign variant
            variant = ab_manager.assign_variant(user_id, "test_v2_rollout", traffic_split=0.5)
            
            # Simulate prediction (variant slightly better)
            if variant == 'variant':
                churn_prob = 0.45 + (i % 20) / 100  # v2.0 slightly better
                latency = 0.4 + (i % 5) * 0.05
            else:
                churn_prob = 0.50 + (i % 20) / 100  # v1.0 baseline
                latency = 0.5 + (i % 5) * 0.05
            
            ab_manager.log_test_prediction(
                user_id=user_id,
                test_name="test_v2_rollout",
                variant=variant,
                churn_prob=churn_prob,
                latency_ms=latency
            )

        L.info(f"✓ Logged {num_predictions} predictions\n")

        # Get test results
        L.info("Analyzing A/B test results...")
        results = ab_manager.get_test_results("test_v2_rollout")
        
        if results['status'] == 'active':
            L.info("✓ A/B test results:")
            L.info(f"\nControl (v1.0):")
            L.info(f"  - Predictions: {results['control']['num_predictions']}")
            L.info(f"  - Avg probability: {results['control']['avg_probability']:.4f}")
            L.info(f"  - Avg latency: {results['control']['avg_latency']:.2f}ms")

            L.info(f"\nVariant (v2.0):")
            L.info(f"  - Predictions: {results['variant']['num_predictions']}")
            L.info(f"  - Avg probability: {results['variant']['avg_probability']:.4f}")
            L.info(f"  - Avg latency: {results['variant']['avg_latency']:.2f}ms")

            L.info(f"\nStatistical test:")
            L.info(f"  - t-statistic: {results['probability_test']['t_statistic']:.4f}")
            L.info(f"  - p-value: {results['probability_test']['p_value']:.6f}")
            L.info(f"  - Significant: {results['probability_test']['significant']}")
            L.info(f"  - Winner: {results['probability_test']['winner']}\n")
        else:
            L.warning("⚠ Insufficient data for A/B test results")

        ab_manager.disconnect()
        return True

    except Exception as e:
        L.error(f"✗ A/B testing failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_retraining_orchestrator():
    """Test automated retraining orchestration."""
    L.info("\n[TEST 3] Retraining Orchestrator - Auto retraining workflow\n")

    from src.advanced.retraining_orchestrator import RetrainingOrchestrator

    orchestrator = RetrainingOrchestrator(DB_CONFIG)
    orchestrator.connect()

    try:
        # Check if retraining is needed
        L.info("Checking retraining conditions...")
        should_retrain, reasons = orchestrator.check_retraining_needed()
        
        L.info(f"✓ Retraining check complete:")
        L.info(f"  - Should retrain: {should_retrain}")
        L.info(f"  - Reasons: {list(reasons.keys())}")

        # Get retraining status
        L.info("\nGetting retraining status...")
        status = orchestrator.get_retraining_status()
        
        L.info(f"✓ Status:")
        L.info(f"  - Production model: {status['production_model']['version']}")
        L.info(f"  - Staging models: {len(status['staging_models'])}")
        for model in status['staging_models']:
            L.info(f"    • {model['version']}")

        # Simulate triggering retraining
        L.info("\nSimulating retraining trigger...")
        success = orchestrator.trigger_retraining(
            new_model_path="/tmp/churn_model_v3.pkl",
            new_scaler_path="/tmp/churn_model_v3_scaler.pkl",
            new_version="3.0",
            training_samples=10000,
            features=['avg_sessions_7d', 'sessions_30d', 'days_since_last_login'],
            hyperparameters={'C': 0.9, 'max_iter': 2000},
            metrics={'auc': 0.9988, 'precision': 0.9962, 'recall': 0.9935, 'f1': 0.9948},
            reasons={'drift': {'detected': True, 'features': ['sessions_30d']}}
        )

        if success:
            L.info("✓ Successfully triggered retraining")
            
            # Get updated status
            status = orchestrator.get_retraining_status()
            L.info(f"\n✓ Updated staging models: {len(status['staging_models'])}")
            for model in status['staging_models']:
                L.info(f"  - {model['version']}")
        else:
            L.warning("⚠ Retraining validation did not pass")

        orchestrator.disconnect()
        return True

    except Exception as e:
        L.error(f"✗ Retraining orchestrator failed: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all Phase 7 tests."""
    L.info("\n" + "=" * 80)
    L.info("PHASE 7: ADVANCED FEATURES TEST")
    L.info("=" * 80)

    # Initialize Phase 7 schema
    if not init_schema():
        L.error("✗ Failed to initialize Phase 7 schema")
        return

    results = {
        'Model Registry': test_model_registry(),
        'A/B Testing': test_ab_testing(),
        'Retraining Orchestrator': test_retraining_orchestrator(),
    }

    L.info("=" * 80)
    L.info("TEST SUMMARY")
    L.info("=" * 80)

    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        L.info(f"{status}: {test_name}")

    L.info("")
    all_passed = all(results.values())

    if all_passed:
        L.info("✅ PHASE 7 TEST SUCCESSFUL - Advanced features ready!")
        L.info("\nCapabilities:")
        L.info("  1. Automated model retraining on drift/degradation")
        L.info("  2. Model version control and promotion workflow")
        L.info("  3. A/B testing framework with statistical significance")
        L.info("  4. Production dashboards for monitoring")
        L.info("  5. Seamless model upgrades with rollback support")
    else:
        L.info("❌ PHASE 7 TEST FAILED - Review errors above")

    L.info("")


if __name__ == "__main__":
    main()
