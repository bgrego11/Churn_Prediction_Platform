"""
Feature definitions for the churn prediction model.
Specifies which features to compute, their windows, and calculation logic.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FeatureType(str, Enum):
    """Types of features."""
    NUMERIC = "numeric"
    BINARY = "binary"
    CATEGORICAL = "categorical"


class AggregationType(str, Enum):
    """How to aggregate values over time windows."""
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    SUM = "sum"
    AVG = "avg"
    MAX = "max"
    MIN = "min"


@dataclass
class FeatureSpec:
    """Specification for a single feature."""
    
    name: str
    description: str
    feature_type: FeatureType
    window_days: Optional[int]  # None = static (from users table)
    sql_query: str  # Raw SQL to compute this feature
    
    def __post_init__(self):
        """Validate feature spec."""
        if self.feature_type == FeatureType.BINARY and "0" not in self.name.lower():
            # Binary features should typically compute to 0/1
            pass


# ============================================================================
# FEATURE CATALOG
# All features that the model can use
# ============================================================================

FEATURE_SPECS = {
    # === ENGAGEMENT FEATURES ===
    "avg_sessions_7d": FeatureSpec(
        name="avg_sessions_7d",
        description="Average daily sessions in last 7 days",
        feature_type=FeatureType.NUMERIC,
        window_days=7,
        sql_query="""
            SELECT COALESCE(COUNT(DISTINCT session_id)::float / 7, 0)
            FROM raw_data.user_events
            WHERE user_id = %s
            AND event_time >= %s::timestamp - interval '7 days'
            AND event_time < %s::timestamp
        """,
    ),
    
    "sessions_30d": FeatureSpec(
        name="sessions_30d",
        description="Total distinct sessions in last 30 days",
        feature_type=FeatureType.NUMERIC,
        window_days=30,
        sql_query="""
            SELECT COALESCE(COUNT(DISTINCT session_id), 0)
            FROM raw_data.user_events
            WHERE user_id = %s
            AND event_time >= %s::timestamp - interval '30 days'
            AND event_time < %s::timestamp
        """,
    ),
    
    "days_since_last_login": FeatureSpec(
        name="days_since_last_login",
        description="Days since user last logged in",
        feature_type=FeatureType.NUMERIC,
        window_days=None,  # Uses all history
        sql_query="""
            SELECT COALESCE(
                EXTRACT(EPOCH FROM (MAX(event_time)::timestamp - %s::timestamp)) / 86400,
                9999  -- If never logged in, return 9999 days
            )::int
            FROM raw_data.user_events
            WHERE user_id = %s
            AND event_type = 'login'
        """,
    ),
    
    "events_30d": FeatureSpec(
        name="events_30d",
        description="Total events in last 30 days",
        feature_type=FeatureType.NUMERIC,
        window_days=30,
        sql_query="""
            SELECT COALESCE(COUNT(*), 0)
            FROM raw_data.user_events
            WHERE user_id = %s
            AND event_time >= %s::timestamp - interval '30 days'
            AND event_time < %s::timestamp
        """,
    ),
    
    # === FINANCIAL FEATURES ===
    "failed_payments_30d": FeatureSpec(
        name="failed_payments_30d",
        description="Number of failed payment attempts in last 30 days",
        feature_type=FeatureType.NUMERIC,
        window_days=30,
        sql_query="""
            SELECT COALESCE(COUNT(*), 0)
            FROM raw_data.billing_events
            WHERE user_id = %s
            AND status = 'failed'
            AND event_time >= %s::timestamp - interval '30 days'
            AND event_time < %s::timestamp
        """,
    ),
    
    "total_spend_90d": FeatureSpec(
        name="total_spend_90d",
        description="Total amount spent (successful charges) in last 90 days",
        feature_type=FeatureType.NUMERIC,
        window_days=90,
        sql_query="""
            SELECT COALESCE(SUM(amount), 0.0)
            FROM raw_data.billing_events
            WHERE user_id = %s
            AND status = 'successful'
            AND event_time >= %s::timestamp - interval '90 days'
            AND event_time < %s::timestamp
        """,
    ),
    
    "refunds_30d": FeatureSpec(
        name="refunds_30d",
        description="Number of refunds in last 30 days",
        feature_type=FeatureType.NUMERIC,
        window_days=30,
        sql_query="""
            SELECT COALESCE(COUNT(*), 0)
            FROM raw_data.billing_events
            WHERE user_id = %s
            AND status = 'refunded'
            AND event_time >= %s::timestamp - interval '30 days'
            AND event_time < %s::timestamp
        """,
    ),
    
    # === SUBSCRIPTION FEATURES ===
    "is_pro_plan": FeatureSpec(
        name="is_pro_plan",
        description="Is user on PRO plan (binary: 1=pro, 0=free/basic)",
        feature_type=FeatureType.BINARY,
        window_days=None,  # Static from users table
        sql_query="""
            SELECT CASE WHEN plan_type = 'pro' THEN 1 ELSE 0 END
            FROM raw_data.users
            WHERE user_id = %s
        """,
    ),
    
    "is_paid_plan": FeatureSpec(
        name="is_paid_plan",
        description="Is user on paid plan (binary: 1=basic or pro, 0=free)",
        feature_type=FeatureType.BINARY,
        window_days=None,  # Static from users table
        sql_query="""
            SELECT CASE WHEN plan_type IN ('basic', 'pro') THEN 1 ELSE 0 END
            FROM raw_data.users
            WHERE user_id = %s
        """,
    ),
    
    "days_since_signup": FeatureSpec(
        name="days_since_signup",
        description="Days since user signed up",
        feature_type=FeatureType.NUMERIC,
        window_days=None,  # Static from users table
        sql_query="""
            SELECT EXTRACT(EPOCH FROM (%s::timestamp - signup_date)) / 86400
            FROM raw_data.users
            WHERE user_id = %s
        """,
    ),
}


# ============================================================================
# LABEL DEFINITIONS
# What we're trying to predict
# ============================================================================

@dataclass
class LabelSpec:
    """Specification for a prediction target (label)."""
    
    name: str
    description: str
    label_type: FeatureType
    prediction_window_days: int  # How far into future to look
    sql_query: str  # SQL to compute label given user_id and feature_date
    
    
LABEL_SPECS = {
    "churned_30d": LabelSpec(
        name="churned_30d",
        description="User churned within 30 days after feature_date",
        label_type=FeatureType.BINARY,
        prediction_window_days=30,
        sql_query="""
            SELECT CASE
                WHEN (
                    -- No activity in next 30 days
                    SELECT COUNT(*) FROM raw_data.user_events
                    WHERE user_id = %s
                    AND event_time >= %s::timestamp
                    AND event_time < %s::timestamp + interval '30 days'
                ) = 0
                AND (
                    -- And no successful payments in next 30 days
                    SELECT COUNT(*) FROM raw_data.billing_events
                    WHERE user_id = %s
                    AND status = 'successful'
                    AND event_time >= %s::timestamp
                    AND event_time < %s::timestamp + interval '30 days'
                ) = 0
                THEN 1
                ELSE 0
            END
        """,
    ),
}


# ============================================================================
# FEATURE SETS (Collections of features)
# ============================================================================

# Minimal set: Fast to compute, good baseline
MINIMAL_FEATURES = [
    "avg_sessions_7d",
    "days_since_last_login",
    "total_spend_90d",
    "is_paid_plan",
]

# Extended set: More comprehensive coverage
EXTENDED_FEATURES = [
    "avg_sessions_7d",
    "sessions_30d",
    "days_since_last_login",
    "events_30d",
    "failed_payments_30d",
    "total_spend_90d",
    "refunds_30d",
    "is_pro_plan",
    "is_paid_plan",
    "days_since_signup",
]

# All available features
ALL_FEATURES = list(FEATURE_SPECS.keys())


if __name__ == "__main__":
    print(f"Total features available: {len(FEATURE_SPECS)}")
    print(f"Total labels available: {len(LABEL_SPECS)}")
    print(f"\nExtended feature set: {EXTENDED_FEATURES}")
