#!/usr/bin/env python3
"""
Test script to validate batch feature query syntax without database.
Shows the final generated SQL query for inspection and testing.
"""

from datetime import datetime, timedelta
from src.features.feature_definitions import EXTENDED_FEATURES

# Simplified version of _build_batch_feature_query for testing
def build_test_query(feature_date: datetime, feature_names: list) -> str:
    """Build batch feature query."""
    feature_selects = []
    
    for fname in feature_names:
        if fname == "avg_sessions_7d":
            feature_selects.append(f"""
                    COALESCE(COUNT(DISTINCT CASE 
                        WHEN ue.event_time >= '{feature_date.date()}'::timestamp - interval '7 days' 
                        THEN ue.session_id 
                    END)::float / 7, 0) as avg_sessions_7d
                """)
        
        elif fname == "sessions_30d":
            feature_selects.append(f"""
                    COALESCE(COUNT(DISTINCT CASE 
                        WHEN ue.event_time >= '{feature_date.date()}'::timestamp - interval '30 days' 
                        THEN ue.session_id 
                    END), 0) as sessions_30d
                """)
        
        elif fname == "days_since_last_login":
            feature_selects.append(f"""
                    COALESCE(
                        EXTRACT(EPOCH FROM (MAX(ue.event_time)::timestamp - '{feature_date.date()}'::timestamp)) / 86400,
                        9999
                    )::int as days_since_last_login
                """)
        
        elif fname == "events_30d":
            feature_selects.append(f"""
                    COUNT(*) FILTER (WHERE ue.event_time >= '{feature_date.date()}'::timestamp - interval '30 days') as events_30d
                """)
        
        elif fname == "failed_payments_30d":
            feature_selects.append(f"""
                    COUNT(*) FILTER (
                        WHERE be.status = 'failed' 
                        AND be.event_time >= '{feature_date.date()}'::timestamp - interval '30 days'
                    ) as failed_payments_30d
                """)
        
        elif fname == "total_spend_90d":
            feature_selects.append(f"""
                    COALESCE(SUM(be.amount) FILTER (
                        WHERE be.status = 'successful'
                        AND be.event_time >= '{feature_date.date()}'::timestamp - interval '90 days'
                    ), 0) as total_spend_90d
                """)
        
        elif fname == "refunds_30d":
            feature_selects.append(f"""
                    COUNT(*) FILTER (
                        WHERE be.status = 'refunded'
                        AND be.event_time >= '{feature_date.date()}'::timestamp - interval '30 days'
                    ) as refunds_30d
                """)
        
        elif fname == "is_pro_plan":
            feature_selects.append("u.is_pro_plan")
        
        elif fname == "is_paid_plan":
            feature_selects.append("u.is_paid_plan")
        
        elif fname == "days_since_signup":
            feature_selects.append(f"""
                    COALESCE(
                        EXTRACT(EPOCH FROM ('{feature_date.date()}'::timestamp - u.signup_date::timestamp)) / 86400,
                        0
                    )::int as days_since_signup
                """)
    
    select_clause = ",\n                    ".join(feature_selects)
    
    query = f"""
            SELECT 
                u.user_id,
                '{feature_date.date()}'::timestamp as feature_date,
                {select_clause}
            FROM raw_data.users u
            LEFT JOIN raw_data.user_events ue ON u.user_id = ue.user_id 
                AND ue.event_time < '{feature_date.date()}'::timestamp
            LEFT JOIN raw_data.billing_events be ON u.user_id = be.user_id 
                AND be.event_time < '{feature_date.date()}'::timestamp
            GROUP BY u.user_id, u.is_pro_plan, u.is_paid_plan, u.signup_date
            ORDER BY u.user_id
        """
    
    return query

def main():
    print("=" * 90)
    print("BATCH FEATURE QUERY SYNTAX TEST")
    print("=" * 90)
    
    # Generate query for yesterday
    feature_date = datetime.utcnow() - timedelta(days=1)
    
    print(f"\n✓ Feature date: {feature_date.date()}")
    print(f"✓ Features to compute: {EXTENDED_FEATURES}")
    print(f"✓ Total features: {len(EXTENDED_FEATURES)}")
    
    print("\n" + "=" * 90)
    print("GENERATED SQL QUERY:")
    print("=" * 90 + "\n")
    
    query = build_test_query(feature_date, EXTENDED_FEATURES)
    print(query)
    
    print("\n" + "=" * 90)
    print("QUERY STRUCTURE ANALYSIS:")
    print("=" * 90)
    
    # Count features in query
    feature_count = 0
    for fname in EXTENDED_FEATURES:
        if fname in query:
            feature_count += 1
            print(f"✓ {fname:25} - Present in query")
        else:
            print(f"✗ {fname:25} - MISSING from query")
    
    print(f"\n✓ Total features found: {feature_count}/{len(EXTENDED_FEATURES)}")
    
    # Check key SQL patterns
    print("\n" + "-" * 90)
    print("SYNTAX VALIDATION:")
    print("-" * 90)
    
    checks = [
        ("SELECT statement", "SELECT u.user_id", query),
        ("FROM clause", "FROM raw_data.users u", query),
        ("LEFT JOIN user_events", "LEFT JOIN raw_data.user_events ue", query),
        ("LEFT JOIN billing_events", "LEFT JOIN raw_data.billing_events be", query),
        ("GROUP BY clause", "GROUP BY u.user_id", query),
        ("ORDER BY clause", "ORDER BY u.user_id", query),
        ("FILTER clause (PostgreSQL)", "FILTER (WHERE", query),
        ("CASE WHEN clause", "CASE WHEN", query),
        ("COALESCE functions", "COALESCE", query),
    ]
    
    all_valid = True
    for check_name, pattern, text in checks:
        if pattern in text:
            print(f"✓ {check_name:40} - Found")
        else:
            print(f"✗ {check_name:40} - MISSING")
            all_valid = False
    
    print("\n" + "=" * 90)
    if all_valid and feature_count == len(EXTENDED_FEATURES):
        print("✓ QUERY SYNTAX VALIDATION PASSED")
        print("=" * 90)
        print("\nReady to test with actual database. Run:")
        print("  1. docker-compose up -d")
        print("  2. python test_batch_query.py")
        return 0
    else:
        print("✗ QUERY SYNTAX VALIDATION FAILED")
        print("=" * 90)
        return 1

if __name__ == "__main__":
    exit(main())
