#!/usr/bin/env python3
"""
Test script for batch feature query.
Executes the query, benchmarks it, and shows results without inserting to database.
Uses actual BatchFeaturePipeline class.
"""

import sys
import time
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def main():
    # Database connection config
    db_config = {
        'host': 'postgres',
        'port': 5432,
        'database': 'churn_platform',
        'user': 'postgres',
        'password': 'postgres',
    }
    
    logger.info("=" * 80)
    logger.info("BATCH FEATURE QUERY TEST")
    logger.info("=" * 80)
    
    try:
        # Import here so we don't fail if psycopg2 isn't available outside container
        import psycopg2
        import pandas as pd
        from src.features.batch_feature_pipeline import BatchFeaturePipeline
        from src.features.feature_definitions import EXTENDED_FEATURES
        
        # Connect to database
        logger.info("\n[1/4] Connecting to database...")
        conn = psycopg2.connect(**db_config)
        logger.info("✓ Connected to PostgreSQL")
        
        # Initialize pipeline (real class, not mock)
        logger.info("\n[2/4] Initializing BatchFeaturePipeline...")
        pipeline = BatchFeaturePipeline(**db_config)
        pipeline.conn = conn
        
        # Use yesterday's date as feature_date
        feature_date = datetime.utcnow() - timedelta(days=1)
        
        logger.info(f"✓ Pipeline ready")
        logger.info(f"✓ Feature date: {feature_date.date()}")
        logger.info(f"✓ Features: {EXTENDED_FEATURES}")
        
        # Build the query using actual method
        logger.info("\n[3/4] Building batch feature query...")
        batch_query = pipeline._build_batch_feature_query(
            feature_date=feature_date,
            feature_names=EXTENDED_FEATURES
        )
        
        logger.info("✓ Query built successfully")
        logger.info("-" * 80)
        logger.info("FIRST 1000 CHARS OF QUERY:")
        logger.info("-" * 80)
        logger.info(batch_query[:1000])
        logger.info("... [rest of query omitted] ...\n")
        
        # Execute and time it
        logger.info("Executing query...")
        start_time = time.time()
        df = pd.read_sql(batch_query, conn)
        execution_time = time.time() - start_time
        
        logger.info("-" * 80)
        logger.info(f"✓ Query executed in {execution_time:.2f} seconds")
        logger.info(f"✓ Results: {len(df)} users × {len(df.columns)} columns")
        
        # Show results
        logger.info("\n[4/4] Sample results:")
        logger.info("-" * 80)
        logger.info(f"\nDataFrame shape: {df.shape}")
        logger.info(f"\nColumns: {df.columns.tolist()}")
        logger.info(f"\nData types:")
        for col, dtype in df.dtypes.items():
            logger.info(f"  {col:30} {str(dtype)}")
        
        logger.info(f"\nFirst 5 rows:")
        logger.info(df.head().to_string())
        
        logger.info(f"\nBasic statistics:")
        logger.info(df.describe().to_string())
        
        # Check for nulls
        logger.info(f"\nNull values per column:")
        for col, null_count in df.isnull().sum().items():
            if null_count > 0:
                logger.info(f"  {col}: {null_count}")
        if df.isnull().sum().sum() == 0:
            logger.info("  (No nulls found)")
        
        # Verify no duplicate users
        duplicates = df['user_id'].duplicated().sum()
        if duplicates == 0:
            logger.info(f"\n✓ No duplicate users (each user appears exactly once)")
        else:
            logger.warning(f"\n⚠ Found {duplicates} duplicate users!")
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ TEST COMPLETE - NO DATA INSERTED")
        logger.info("✓ Batch query syntax and execution validated")
        logger.info("=" * 80)
        
        return 0
        
    except ImportError as e:
        logger.error(f"\n❌ Import Error (containers running?): {e}")
        logger.error("\nMake sure containers are running:")
        logger.error("  docker-compose up -d")
        return 1
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        try:
            conn.close()
        except:
            pass
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
