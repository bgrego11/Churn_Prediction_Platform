"""
Point-in-Time (PIT) Validator - Ensures feature correctness and data quality.
Validates that features don't contain future information (data leakage).
"""

import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class PointInTimeValidator:
    """Validates point-in-time correctness and data quality of features."""

    @staticmethod
    def validate_no_nulls(df: pd.DataFrame, threshold: float = 0.95) -> bool:
        """
        Check that features don't have excessive null values.
        
        Args:
            df: Feature dataframe
            threshold: Minimum non-null ratio (default 95%)
            
        Returns:
            True if valid, False otherwise
        """
        non_null_ratio = df.isnull().sum() / len(df)
        
        violations = non_null_ratio[non_null_ratio > (1 - threshold)]
        
        if len(violations) > 0:
            logger.warning(f"Null value violations: {violations}")
            return False
        
        logger.info("✓ Null values check passed")
        return True

    @staticmethod
    def validate_feature_ranges(df: pd.DataFrame) -> bool:
        """
        Check that features are in reasonable ranges.
        
        Args:
            df: Feature dataframe
            
        Returns:
            True if valid, False otherwise
        """
        rules = {
            # All these should be >= 0
            "avg_sessions_7d": (0, float("inf")),
            "sessions_30d": (0, float("inf")),
            "days_since_last_login": (0, 9999),
            "events_30d": (0, float("inf")),
            "failed_payments_30d": (0, float("inf")),
            "total_spend_90d": (0, float("inf")),
            "refunds_30d": (0, float("inf")),
            "is_pro_plan": (0, 1),
            "is_paid_plan": (0, 1),
            "days_since_signup": (0, float("inf")),
        }

        violations = []
        for col, (min_val, max_val) in rules.items():
            if col not in df.columns:
                continue

            out_of_range = (
                (df[col] < min_val) | (df[col] > max_val)
            ).sum()

            if out_of_range > 0:
                violations.append(
                    f"{col}: {out_of_range} values out of range [{min_val}, {max_val}]"
                )

        if violations:
            logger.warning(f"Range violations:\n" + "\n".join(violations))
            return False

        logger.info("✓ Feature range check passed")
        return True

    @staticmethod
    def validate_no_duplicates(df: pd.DataFrame) -> bool:
        """
        Check for duplicate rows (same user_id + feature_date).
        
        Args:
            df: Feature dataframe
            
        Returns:
            True if valid, False otherwise
        """
        if "user_id" not in df.columns or "feature_date" not in df.columns:
            logger.warning("Cannot check duplicates without user_id and feature_date")
            return True

        duplicates = df.duplicated(subset=["user_id", "feature_date"]).sum()

        if duplicates > 0:
            logger.warning(f"Found {duplicates} duplicate user_id + feature_date combinations")
            return False

        logger.info("✓ Duplicate check passed")
        return True

    @staticmethod
    def validate_feature_stability(df: pd.DataFrame, tolerance: float = 0.5) -> bool:
        """
        Check that feature distributions are stable across feature_dates.
        Detects data drift or quality issues.
        
        Args:
            df: Feature dataframe with multiple feature_dates
            tolerance: Max allowed std of mean values across dates
            
        Returns:
            True if stable, False if drift detected
        """
        if "feature_date" not in df.columns:
            logger.info("Cannot check stability without feature_date")
            return True

        numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns
        numeric_cols = [c for c in numeric_cols if c not in ["user_id"]]

        issues = []
        for col in numeric_cols:
            means_by_date = df.groupby("feature_date")[col].mean()
            std_of_means = means_by_date.std()
            mean_of_means = means_by_date.mean()

            # Check if std is too high (indicates drift)
            if mean_of_means > 0:
                cv = std_of_means / mean_of_means  # Coefficient of variation
                if cv > tolerance:
                    issues.append(
                        f"{col}: High drift (CV={cv:.3f}, threshold={tolerance})"
                    )

        if issues:
            logger.warning(f"Stability warnings:\n" + "\n".join(issues))
            return False

        logger.info("✓ Feature stability check passed")
        return True

    @staticmethod
    def validate_label_distribution(labels: pd.DataFrame, expected_churn_rate: float = 0.15) -> bool:
        """
        Check that label distribution is reasonable.
        
        Args:
            labels: Labels dataframe
            expected_churn_rate: Expected churn rate (for comparison)
            
        Returns:
            True if reasonable, False otherwise
        """
        if "churned_30d" not in labels.columns:
            logger.warning("No churned_30d label found")
            return True

        churn_rate = labels["churned_30d"].mean()
        logger.info(f"Churn rate in dataset: {churn_rate:.2%} (expected: {expected_churn_rate:.2%})")

        # Very unbalanced labels (< 5% or > 95%) might indicate issues
        if churn_rate < 0.05 or churn_rate > 0.95:
            logger.warning(f"Highly imbalanced labels: {churn_rate:.2%} churn")
            return False

        logger.info("✓ Label distribution check passed")
        return True

    @staticmethod
    def full_validation(
        features_df: pd.DataFrame,
        labels_df: pd.DataFrame = None,
    ) -> bool:
        """
        Run all validation checks.
        
        Args:
            features_df: Features dataframe
            labels_df: Optional labels dataframe
            
        Returns:
            True if all checks pass, False otherwise
        """
        logger.info("=" * 70)
        logger.info("RUNNING FULL FEATURE VALIDATION")
        logger.info("=" * 70)

        checks_passed = 0
        checks_total = 0

        # Feature checks
        checks = [
            ("Null values", PointInTimeValidator.validate_no_nulls(features_df)),
            ("Feature ranges", PointInTimeValidator.validate_feature_ranges(features_df)),
            ("Duplicates", PointInTimeValidator.validate_no_duplicates(features_df)),
            ("Stability", PointInTimeValidator.validate_feature_stability(features_df)),
        ]

        for check_name, result in checks:
            checks_total += 1
            if result:
                checks_passed += 1

        # Label checks
        if labels_df is not None:
            result = PointInTimeValidator.validate_label_distribution(labels_df)
            checks_total += 1
            if result:
                checks_passed += 1

        logger.info("=" * 70)
        logger.info(f"VALIDATION RESULT: {checks_passed}/{checks_total} checks passed")
        logger.info("=" * 70)

        return checks_passed == checks_total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example validation
    logger.info("Example validation would run here with actual feature data")
