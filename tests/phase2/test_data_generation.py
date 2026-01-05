#!/usr/bin/env python3
"""
Standalone test script to generate and load synthetic data.
Run this from the project root: python3 test_data_generation.py
"""

import logging
import sys
from src.data_generation.generator import SyntheticDataGenerator
from src.data_generation.loaders import load_data

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Generate and load test data."""
    logger.info("=" * 70)
    logger.info("PHASE 2: SYNTHETIC DATA GENERATION TEST")
    logger.info("=" * 70)
    
    try:
        # Step 1: Generate synthetic data
        logger.info("\n[1/2] Generating synthetic data...")
        generator = SyntheticDataGenerator(seed=42)
        users, user_events, billing_events = generator.generate_all(
            num_users=1000,  # Small test set for speed
            churn_rate=0.15,
            backfill_days=90,  # Only 3 months for quick test
        )
        
        logger.info(f"  ✓ Generated {len(users)} users")
        logger.info(f"  ✓ Generated {len(user_events)} user events")
        logger.info(f"  ✓ Generated {len(billing_events)} billing events")
        
        # Step 2: Load into database
        logger.info("\n[2/2] Loading into PostgreSQL...")
        counts = load_data(
            users=users,
            user_events=user_events,
            billing_events=billing_events,
            host="postgres",
            port=5432,
            database="churn_db",
            user="churn_user",
            password="churn_password",
        )
        
        logger.info(f"  ✓ Users table: {counts.get('users', 0)} rows")
        logger.info(f"  ✓ User events table: {counts.get('user_events', 0)} rows")
        logger.info(f"  ✓ Billing events table: {counts.get('billing_events', 0)} rows")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ PHASE 2 TEST SUCCESSFUL - Data generation and loading complete!")
        logger.info("=" * 70)
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ PHASE 2 TEST FAILED: {e}", exc_info=True)
        logger.info("=" * 70)
        return 1

if __name__ == "__main__":
    sys.exit(main())
