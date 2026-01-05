"""
Online Feature Server - Loads cached features and runs model inference.
Handles single and batch predictions with sub-millisecond latency.
"""

import logging
import pickle
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import numpy as np

from .feature_store import FeatureStore

logger = logging.getLogger(__name__)


class OnlineFeatureServer:
    """Serves predictions using cached features and trained model."""

    def __init__(
        self,
        model_path: str,
        feature_store: FeatureStore,
        feature_columns: List[str] = None,
    ):
        """
        Initialize online server.

        Args:
            model_path: Path to trained model (without .pkl extension)
            feature_store: Connected FeatureStore instance
            feature_columns: List of feature column names
        """
        self.model_path = model_path
        self.feature_store = feature_store
        self.model = None
        self.scaler = None
        self.feature_columns = feature_columns or [
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

        self._load_model()

    def _load_model(self) -> None:
        """Load trained model and scaler from disk."""
        try:
            # Load model
            with open(f"{self.model_path}.pkl", "rb") as f:
                self.model = pickle.load(f)
            logger.info(f"✓ Loaded model from {self.model_path}.pkl")

            # Load scaler if available
            try:
                with open(f"{self.model_path}_scaler.pkl", "rb") as f:
                    self.scaler = pickle.load(f)
                logger.info(f"✓ Loaded scaler from {self.model_path}_scaler.pkl")
            except FileNotFoundError:
                logger.warning("Scaler not found, predictions may be unscaled")
                self.scaler = None

        except FileNotFoundError as e:
            logger.error(f"Model not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise

    def predict(self, user_id: int) -> Dict:
        """
        Predict churn probability for a single user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with prediction results:
            {
                "user_id": int,
                "churn_probability": float (0-1),
                "churn_label": int (0 or 1),
                "timestamp": str,
                "from_cache": bool,
            }
        """
        start_time = datetime.utcnow()

        # Step 1: Get features from cache
        features = self.feature_store.get_features(user_id)
        from_cache = features is not None

        if features is None:
            logger.warning(f"Features not found in cache for user {user_id}")
            return {
                "user_id": user_id,
                "churn_probability": None,
                "churn_label": None,
                "error": "Features not found in cache",
                "timestamp": start_time.isoformat(),
                "from_cache": False,
            }

        # Step 2: Prepare feature vector in correct order
        try:
            feature_vector = np.array([
                [features.get(col, 0.0) for col in self.feature_columns]
            ])

            # Step 3: Scale if scaler available
            if self.scaler:
                feature_vector = self.scaler.transform(feature_vector)

            # Step 4: Run inference
            churn_probability = self.model.predict_proba(feature_vector)[0, 1]
            churn_label = int(self.model.predict(feature_vector)[0])

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = {
                "user_id": user_id,
                "churn_probability": float(churn_probability),
                "churn_label": churn_label,
                "timestamp": start_time.isoformat(),
                "from_cache": from_cache,
                "latency_ms": latency_ms,
            }

            logger.info(
                f"Prediction for user {user_id}: "
                f"churn_prob={churn_probability:.4f}, latency={latency_ms:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Error during inference for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "churn_probability": None,
                "churn_label": None,
                "error": str(e),
                "timestamp": start_time.isoformat(),
                "from_cache": from_cache,
            }

    def predict_batch(self, user_ids: List[int]) -> List[Dict]:
        """
        Predict churn probability for multiple users.

        Args:
            user_ids: List of user IDs

        Returns:
            List of prediction dictionaries
        """
        start_time = datetime.utcnow()
        results = []

        logger.info(f"Batch prediction for {len(user_ids)} users")

        # Get all features at once
        features_dict = self.feature_store.get_batch_features(user_ids)

        # Process each user
        for user_id in user_ids:
            features = features_dict.get(user_id)

            if features is None:
                results.append({
                    "user_id": user_id,
                    "churn_probability": None,
                    "churn_label": None,
                    "error": "Features not found",
                    "from_cache": False,
                })
                continue

            try:
                # Prepare feature vector
                feature_vector = np.array([
                    [features.get(col, 0.0) for col in self.feature_columns]
                ])

                # Scale if needed
                if self.scaler:
                    feature_vector = self.scaler.transform(feature_vector)

                # Predict
                churn_probability = self.model.predict_proba(feature_vector)[0, 1]
                churn_label = int(self.model.predict(feature_vector)[0])

                results.append({
                    "user_id": user_id,
                    "churn_probability": float(churn_probability),
                    "churn_label": churn_label,
                    "timestamp": start_time.isoformat(),
                    "from_cache": True,
                })

            except Exception as e:
                logger.error(f"Error predicting for user {user_id}: {e}")
                results.append({
                    "user_id": user_id,
                    "churn_probability": None,
                    "churn_label": None,
                    "error": str(e),
                })

        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.info(
            f"Batch prediction completed: {len(results)} predictions in {latency_ms:.2f}ms "
            f"({latency_ms/len(user_ids):.2f}ms per user)"
        )

        return results

    def get_feature_explanation(self, user_id: int) -> Optional[Dict]:
        """
        Get feature values and model coefficients for interpretability.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with features and their contribution to prediction
        """
        features = self.feature_store.get_features(user_id)

        if features is None:
            logger.warning(f"Features not found for user {user_id}")
            return None

        if not hasattr(self.model, "coef_"):
            logger.warning("Model doesn't have coefficients for explanation")
            return None

        try:
            coefficients = self.model.coef_[0]

            # Calculate feature contributions
            contributions = {}
            for feature_name, coef in zip(self.feature_columns, coefficients):
                feature_value = features.get(feature_name, 0.0)
                contribution = float(feature_value * coef)
                contributions[feature_name] = {
                    "value": feature_value,
                    "coefficient": float(coef),
                    "contribution": contribution,
                }

            # Sort by absolute contribution
            sorted_contributions = sorted(
                contributions.items(),
                key=lambda x: abs(x[1]["contribution"]),
                reverse=True,
            )

            return {
                "user_id": user_id,
                "features": dict(sorted_contributions),
                "intercept": float(self.model.intercept_[0]),
            }

        except Exception as e:
            logger.error(f"Error generating explanation for user {user_id}: {e}")
            return None

    def health_check(self) -> Dict:
        """
        Check health of the prediction server.

        Returns:
            Health status dictionary
        """
        return {
            "model_loaded": self.model is not None,
            "scaler_loaded": self.scaler is not None,
            "feature_cache_healthy": self.feature_store.health_check(),
            "timestamp": datetime.utcnow().isoformat(),
        }
