#!/usr/bin/env python3
"""
Phase 3 test: Generate feature matrix from raw events.
Demonstrates point-in-time correctness and data validation.
"""

import logging
import sys
from datetime import datetime, timedelta

from src.features.batch_feature_pipeline import BatchFeaturePipeline
from src.features.pit_validator import PointInTimeValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Generate and validate training features."""
    logger.info("=" * 70)
    logger.info("PHASE 3: BATCH FEATURE PIPELINE TEST")
    logger.info("=" * 70)

    try:
        # Step 1: Connect to database
        logger.info("\n[1/4] Connecting to database...")
        pipeline = BatchFeaturePipeline(
            host="postgres",
            port=5432,
            database="churn_db",
            user="churn_user",
            password="churn_password",
        )
        pipeline.connect()
        logger.info("✓ Connected to PostgreSQL")

        # Step 2: Generate training dataset with multiple point-in-time snapshots
        logger.info("\n[2/4] Generating training dataset with PIT snapshots...")
        
        # Use data from the synthetic generation window
        # Start from 60 days ago (data has 90 days backfill)
        start_date = datetime.utcnow() - timedelta(days=60)
        
        features_df, labels_df = pipeline.generate_training_dataset(
            start_date=start_date,
            num_weeks=8,  # 8 weeks of snapshots
            frequency="weekly",
        )
        
        logger.info(f"✓ Generated features: {features_df.shape}")
        logger.info(f"✓ Generated labels: {labels_df.shape}")

        # Step 3: Validate features
        logger.info("\n[3/4] Running point-in-time validation...")
        is_valid = PointInTimeValidator.full_validation(features_df, labels_df)

        if not is_valid:
            logger.warning("⚠ Some validation checks failed (see details above)")
        else:
            logger.info("✓ All validation checks passed!")

        # Step 4: Display summary statistics
        logger.info("\n[4/4] Feature summary statistics...")
        logger.info(f"\nFeature matrix shape: {features_df.shape}")
        logger.info(f"\nFeatures computed:")
        feature_cols = [c for c in features_df.columns if c not in ["user_id", "feature_date"]]
        for col in sorted(feature_cols):
            logger.info(f"  • {col}")

        logger.info(f"\nFeature statistics:")
        stats = features_df[feature_cols].describe()
        logger.info(f"\n{stats}")

        logger.info(f"\nLabel distribution:")
        logger.info(f"  Churn rate: {labels_df['churned_30d'].mean():.2%}")
        logger.info(f"  Churned users: {labels_df['churned_30d'].sum()}")
        logger.info(f"  Non-churned users: {(1 - labels_df['churned_30d']).sum()}")

        # Step 5: Save features to database for Phase 4
        logger.info("\n[5/4] Saving features to database...")
        pipeline.save_features(features_df, table_name="ml_pipeline.features")
        pipeline.save_features(labels_df, table_name="ml_pipeline.labels")
        logger.info("✓ Features and labels saved to database")

        logger.info("\n" + "=" * 70)
        logger.info("✅ PHASE 3 TEST SUCCESSFUL - Feature pipeline working!")
        logger.info("=" * 70)
        
        return 0

    except Exception as e:
        logger.error(f"\n❌ PHASE 3 TEST FAILED: {e}", exc_info=True)
        logger.info("=" * 70)
        return 1

    finally:
        pipeline.disconnect()


if __name__ == "__main__":
    sys.exit(main())
