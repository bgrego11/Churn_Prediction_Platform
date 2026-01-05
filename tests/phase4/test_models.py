"""
Phase 4: Model Training Test
Tests the complete training pipeline with temporal split and evaluation.
"""

import os
import sys
import logging
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from features.batch_feature_pipeline import BatchFeaturePipeline
from models import ModelTrainer, ModelEvaluator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_db_config():
    """Get database configuration from environment."""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", 5433)),
        "database": os.getenv("POSTGRES_DB", "churn_db"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
    }


def main():
    """Run Phase 4: Model Training."""
    
    print("\n" + "=" * 80)
    print("PHASE 4: ML MODEL TRAINING & EVALUATION")
    print("=" * 80)

    db_config = get_db_config()

    try:
        # ====================================================================
        # [1/5] Load features from database
        # ====================================================================
        print("\n[1/5] Loading features from database...\n")
        
        trainer = ModelTrainer(db_config)
        trainer.connect()

        # Load all features and labels from database
        try:
            X, y = trainer.get_features_and_labels(
                feature_date_from=datetime(2025, 1, 1),
                feature_date_to=datetime(2026, 12, 31),
            )
            print(f"✓ Loaded {len(X)} feature vectors from database")
            print(f"  Features shape: {X.shape}")
            print(f"  Churn rate: {y.mean():.2%}")
        except Exception as e:
            print(f"⚠ Could not load from database: {e}")
            print("  Please run test_features.py first to populate the database")
            trainer.disconnect()
            return 1

        # ====================================================================
        # [2/5] Temporal train-test split
        # ====================================================================
        print("\n[2/5] Splitting data (temporal, not random)...\n")
        
        # Split into train (first 6 samples) and test (last 2 samples)
        # Since we have 8 snapshots of 1000 users = 8000 rows
        split_point = 6000  # 6 weeks worth
        X_train = X.iloc[:split_point].copy()
        X_test = X.iloc[split_point:].copy()
        y_train = y.iloc[:split_point].copy()
        y_test = y.iloc[split_point:].copy()

        print(f"✓ Train/Test split complete")
        print(f"  Train: {len(X_train)} samples ({y_train.mean():.2%} churn)")
        print(f"  Test:  {len(X_test)} samples ({y_test.mean():.2%} churn)")

        # ====================================================================
        # [3/5] Train model
        # ====================================================================
        print("\n[3/5] Training Logistic Regression model...\n")
        
        trainer.train(X_train, y_train, scale_features=True)
        print("✓ Model training complete")

        # ====================================================================
        # [4/5] Evaluate model
        # ====================================================================
        print("\n[4/5] Evaluating model on test set...\n")
        
        metrics = trainer.evaluate(X_test, y_test, threshold=0.5)
        
        print(f"✓ Evaluation complete")
        print(f"  AUC-ROC:  {metrics['auc']:.4f}")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall:    {metrics['recall']:.4f}")
        print(f"  F1 Score:  {metrics['f1']:.4f}")

        # ====================================================================
        # [5/5] Save Model
        # ====================================================================
        print("\n[5/5] Persisting model to disk...\n")
        
        evaluator = ModelEvaluator()
        importance_df = evaluator.feature_importance(
            trainer.model,
            trainer.feature_columns,
            top_n=10,
        )

        # Threshold analysis
        print("\n[BONUS] Threshold Analysis...\n")
        
        if trainer.scaler:
            X_test_scaled = trainer.scaler.transform(X_test)
        else:
            X_test_scaled = X_test.values
            
        y_pred_proba = trainer.model.predict_proba(X_test_scaled)[:, 1]
        
        threshold_df = evaluator.threshold_analysis(
            y_test,
            y_pred_proba,
            thresholds=[0.3, 0.4, 0.5, 0.6, 0.7],
        )

        # Prediction distribution
        print("\n[BONUS] Prediction Distribution...\n")
        
        dist = evaluator.get_prediction_distribution(y_pred_proba)

        # ====================================================================
        # Additional Analysis
        # ====================================================================
        print("\n[BONUS] Feature Importance Analysis...\n")
        
        model_path = "/tmp/churn_model"
        trainer.save_model(model_path)
        print(f"✓ Model saved to {model_path}.pkl")

        # Save metadata to database
        trainer.save_model_metadata(
            metrics=metrics,
            training_date_from=datetime(2025, 11, 6),
            training_date_to=datetime(2025, 12, 24),
            test_date_from=datetime(2025, 12, 25),
            test_date_to=datetime(2026, 1, 8),
        )
        print(f"✓ Model metadata saved to database")

        trainer.disconnect()

        # ====================================================================
        # Summary
        # ====================================================================
        print("\n" + "=" * 80)
        print("✅ PHASE 4 TEST SUCCESSFUL - Model trained and evaluated!")
        print("=" * 80)
        print(f"\nKey Results:")
        print(f"  • AUC-ROC Score: {metrics['auc']:.4f}")
        print(f"  • Test Precision: {metrics['precision']:.4f} (of predicted churners, % correct)")
        print(f"  • Test Recall: {metrics['recall']:.4f} (of actual churners, % we caught)")
        print(f"  • F1 Score: {metrics['f1']:.4f}")
        print(f"\nNext Steps:")
        print(f"  Phase 5: Online Feature Serving (Redis)")
        print(f"  Phase 6: Model Deployment & Monitoring")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"\n❌ PHASE 4 TEST FAILED: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
