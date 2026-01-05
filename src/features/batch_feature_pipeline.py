"""
Batch Feature Pipeline - Computes ML features from raw events.
Ensures point-in-time correctness and generates training datasets.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import pandas as pd
import psycopg2
from .feature_definitions import FEATURE_SPECS, LABEL_SPECS, EXTENDED_FEATURES

logger = logging.getLogger(__name__)


class BatchFeaturePipeline:
    """Computes features from raw events with point-in-time correctness."""

    def __init__(
        self,
        host: str = "postgres",
        port: int = 5432,
        database: str = "churn_db",
        user: str = "churn_user",
        password: str = "churn_password",
    ):
        """
        Initialize feature pipeline.
        
        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
        """
        self.connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }
        self.conn = None

    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(**self.connection_params)
            logger.info(f"Connected to PostgreSQL: {self.connection_params['host']}")
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from PostgreSQL")

    def get_all_users(self) -> List[int]:
        """Get all user IDs from database."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT user_id FROM raw_data.users ORDER BY user_id")
            users = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found {len(users)} users in database")
            return users
        finally:
            cursor.close()

    def compute_feature(
        self,
        feature_name: str,
        user_id: int,
        feature_date: datetime,
    ) -> float:
        """
        Compute a single feature for a user at a specific point in time.
        
        Args:
            feature_name: Name of feature to compute
            user_id: User identifier
            feature_date: Feature computation date (point-in-time)
            
        Returns:
            Feature value
        """
        if feature_name not in FEATURE_SPECS:
            raise ValueError(f"Unknown feature: {feature_name}")

        spec = FEATURE_SPECS[feature_name]
        cursor = self.conn.cursor()

        try:
            # Execute SQL with parameters for point-in-time correctness
            if spec.window_days:
                # Time-windowed feature: parameters are (user_id, feature_date, feature_date)
                cursor.execute(spec.sql_query, (user_id, feature_date, feature_date))
            elif feature_name in ["days_since_last_login", "days_since_signup"]:
                # Features that need both feature_date and user_id: parameters are (feature_date, user_id)
                cursor.execute(spec.sql_query, (feature_date, user_id))
            else:
                # Static feature from users table: only needs user_id
                cursor.execute(spec.sql_query, (user_id,))

            result = cursor.fetchone()
            value = result[0] if result else 0
            return float(value) if value is not None else 0.0

        except psycopg2.Error as e:
            logger.error(f"Error computing feature {feature_name} for user {user_id}: {e}")
            return 0.0
        finally:
            cursor.close()

    def compute_label(
        self,
        label_name: str,
        user_id: int,
        feature_date: datetime,
    ) -> int:
        """
        Compute label for a user at a specific point in time.
        
        Args:
            label_name: Name of label to compute
            user_id: User identifier
            feature_date: Feature computation date (label looks forward from here)
            
        Returns:
            Label value (0 or 1 for binary)
        """
        if label_name not in LABEL_SPECS:
            raise ValueError(f"Unknown label: {label_name}")

        spec = LABEL_SPECS[label_name]
        cursor = self.conn.cursor()

        try:
            # Execute SQL with parameters for point-in-time correctness
            # Note: Label looks forward prediction_window_days from feature_date
            # churned_30d needs: (user_id, feature_date, feature_date, user_id, feature_date, feature_date)
            cursor.execute(
                spec.sql_query,
                (user_id, feature_date, feature_date, user_id, feature_date, feature_date),
            )

            result = cursor.fetchone()
            value = result[0] if result else 0
            return int(value)

        except psycopg2.Error as e:
            logger.error(f"Error computing label {label_name} for user {user_id}: {e}")
            return 0
        finally:
            cursor.close()

    def compute_features_for_user(
        self,
        user_id: int,
        feature_date: datetime,
        feature_names: List[str] = None,
    ) -> Dict[str, float]:
        """
        Compute all features for a single user at a point in time.
        
        Args:
            user_id: User identifier
            feature_date: Feature computation date
            feature_names: Specific features to compute (default: all)
            
        Returns:
            Dictionary of feature_name -> value
        """
        if feature_names is None:
            feature_names = EXTENDED_FEATURES

        features = {"user_id": user_id, "feature_date": feature_date}

        for feature_name in feature_names:
            value = self.compute_feature(feature_name, user_id, feature_date)
            features[feature_name] = value

        return features

    def compute_features_for_date(
        self,
        feature_date: datetime,
        user_ids: List[int] = None,
        feature_names: List[str] = None,
        include_label: bool = False,
    ) -> pd.DataFrame:
        """
        Compute features for all users at a specific date (point-in-time snapshot).
        
        Args:
            feature_date: Feature computation date
            user_ids: Specific users to compute (default: all)
            feature_names: Specific features to compute (default: extended set)
            include_label: Whether to include churned_30d label
            
        Returns:
            DataFrame with shape (num_users, num_features + 2 [user_id, feature_date] + label)
        """
        if feature_names is None:
            feature_names = EXTENDED_FEATURES

        if user_ids is None:
            user_ids = self.get_all_users()

        logger.info(
            f"Computing features for {len(user_ids)} users at {feature_date.date()}"
        )

        records = []
        for idx, user_id in enumerate(user_ids):
            if (idx + 1) % 100 == 0:
                logger.info(f"  Progress: {idx + 1}/{len(user_ids)}")

            try:
                features = self.compute_features_for_user(
                    user_id, feature_date, feature_names
                )

                if include_label:
                    label = self.compute_label("churned_30d", user_id, feature_date)
                    features["churned_30d"] = label

                records.append(features)
            
            except Exception as e:
                # Log error and skip this user
                logger.error(f"Error computing features for user {user_id}: {e}")
                # Reset transaction if needed
                try:
                    self.conn.rollback()
                except:
                    pass
                continue

        df = pd.DataFrame(records)
        logger.info(f"Generated feature matrix: {df.shape}")
        return df

    def generate_training_dataset(
        self,
        start_date: datetime,
        num_weeks: int = 12,
        feature_names: List[str] = None,
        frequency: str = "weekly",
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Generate training dataset with multiple point-in-time snapshots.
        
        This is critical for ML: We create features at multiple dates to avoid
        overfitting to a single point in time.
        
        Args:
            start_date: First feature date to compute
            num_weeks: Number of weeks of data
            feature_names: Features to compute (default: extended)
            frequency: "weekly" or "daily"
            
        Returns:
            Tuple of (features_df, labels_df)
        """
        if feature_names is None:
            feature_names = EXTENDED_FEATURES

        all_features = []
        all_labels = []

        # Determine step size
        step = timedelta(days=7 if frequency == "weekly" else 1)
        current_date = start_date

        for week_num in range(num_weeks):
            logger.info(f"\nComputing snapshot {week_num + 1}/{num_weeks}")
            logger.info(f"  Feature date: {current_date.date()}")

            # Compute features at this point in time
            df = self.compute_features_for_date(
                current_date,
                feature_names=feature_names,
                include_label=True,
            )

            all_features.append(df)
            current_date += step

        # Combine all snapshots
        combined_df = pd.concat(all_features, ignore_index=True)

        logger.info(f"\nTraining dataset shape: {combined_df.shape}")
        logger.info(f"Feature date range: {combined_df['feature_date'].min()} to {combined_df['feature_date'].max()}")
        logger.info(f"Churn rate in dataset: {combined_df['churned_30d'].mean():.2%}")

        # Split features and labels
        features_df = combined_df.drop(columns=["churned_30d"])
        labels_df = combined_df[["user_id", "feature_date", "churned_30d"]]

        return features_df, labels_df

    def save_features(self, df: pd.DataFrame, table_name: str = "features_daily"):
        """
        Save computed features to database for later use.
        
        Args:
            df: DataFrame with features
            table_name: Table name to save to
        """
        cursor = self.conn.cursor()
        try:
            # Create table if not exists
            columns_def = ", ".join(
                [f'"{col}" FLOAT' if col not in ["user_id", "feature_date"] else f'"{col}" VARCHAR' 
                 for col in df.columns]
            )
            
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id SERIAL PRIMARY KEY,
                    {columns_def},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert data
            cols = ", ".join([f'"{col}"' for col in df.columns])
            placeholders = ", ".join(["%s"] * len(df.columns))

            insert_sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"

            cursor.executemany(
                insert_sql,
                df.values.tolist(),
            )

            self.conn.commit()
            logger.info(f"Saved {len(df)} feature vectors to {table_name}")

        except psycopg2.Error as e:
            self.conn.rollback()
            logger.error(f"Error saving features: {e}")
            raise
        finally:
            cursor.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example: Compute features for a single date
    pipeline = BatchFeaturePipeline()
    pipeline.connect()

    try:
        # Use a recent date from our synthetic data
        feature_date = datetime.utcnow() - timedelta(days=30)
        
        logger.info("Computing features for sample date...")
        df = pipeline.compute_features_for_date(feature_date)
        
        print(f"\nFeature matrix shape: {df.shape}")
        print(f"\nFirst 5 rows:\n{df.head()}")
        print(f"\nFeature statistics:\n{df.describe()}")

    finally:
        pipeline.disconnect()
