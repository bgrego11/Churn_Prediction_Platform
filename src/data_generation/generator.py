"""
Main synthetic data generator for churn prediction platform.
Orchestrates user, event, and billing data generation.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import List, Tuple

from .events import EventGenerator
from .schemas import BillingEventSchema, PlanType, UserEventSchema, UserSchema

logger = logging.getLogger(__name__)


class SyntheticDataGenerator:
    """
    Generates synthetic data for the churn prediction platform.
    
    Produces:
    - Users with signup dates and plan types
    - User events (sessions, page views, searches, etc.)
    - Billing events (charges, failures, refunds)
    
    Churn is modeled as users who reduce activity and eventually stop paying.
    """

    def __init__(self, seed: int = 42, base_date: datetime = None):
        """
        Initialize the data generator.
        
        Args:
            seed: Random seed for reproducibility
            base_date: Reference date for generation (defaults to now)
        """
        self.seed = seed
        self.base_date = base_date or datetime.utcnow()
        random.seed(seed)
        self.event_generator = EventGenerator(seed=seed)

    def generate_users(
        self, num_users: int, signup_window_days: int = 365
    ) -> List[UserSchema]:
        """
        Generate synthetic users with diverse signup dates and plans.
        
        Args:
            num_users: Number of users to generate
            signup_window_days: Days back to distribute signups across
            
        Returns:
            List of user records
        """
        users = []
        countries = ["US", "CA", "UK", "DE", "FR", "AU", "JP", "IN", "BR"]

        for user_id in range(1, num_users + 1):
            # Random signup date within window
            days_ago = random.randint(1, signup_window_days)
            signup_date = self.base_date - timedelta(days=days_ago)

            # Plan distribution: 60% free, 25% basic, 15% pro
            plan_choice = random.random()
            if plan_choice < 0.6:
                plan_type = PlanType.FREE
            elif plan_choice < 0.85:
                plan_type = PlanType.BASIC
            else:
                plan_type = PlanType.PRO

            users.append(
                UserSchema(
                    user_id=user_id,
                    plan_type=plan_type,
                    signup_date=signup_date,
                    country=random.choice(countries),
                )
            )

        logger.info(f"Generated {len(users)} synthetic users")
        return users

    def _identify_churned_users(
        self, users: List[UserSchema], churn_rate: float = 0.15
    ) -> Tuple[List[int], dict]:
        """
        Probabilistically identify which users will churn.
        
        Args:
            users: List of user records
            churn_rate: Proportion of users to churn (default 15%)
            
        Returns:
            Tuple of (churned_user_ids, user_churn_info dict)
        """
        churned_users = {}
        num_to_churn = int(len(users) * churn_rate)

        # Sample random users to churn
        churn_user_ids = random.sample(
            [u.user_id for u in users], k=num_to_churn
        )

        for user_id in churn_user_ids:
            # Assign random churn date (60-360 days after base date)
            days_until_churn = random.randint(60, 360)
            churn_date = self.base_date - timedelta(days=days_until_churn)
            churned_users[user_id] = churn_date

        logger.info(f"Marked {len(churned_users)} users as churned")
        return churn_user_ids, churned_users

    def generate_events(
        self,
        users: List[UserSchema],
        churn_rate: float = 0.15,
        backfill_days: int = 365,
    ) -> Tuple[List[UserEventSchema], List[BillingEventSchema]]:
        """
        Generate events for all users.
        
        Args:
            users: List of user records
            churn_rate: Proportion of users to churn
            backfill_days: Days of historical data to generate
            
        Returns:
            Tuple of (user_events, billing_events)
        """
        churn_user_ids, churned_users = self._identify_churned_users(
            users, churn_rate
        )

        user_events = []
        billing_events = []

        for user in users:
            is_churned = user.user_id in churn_user_ids
            churn_date = churned_users.get(user.user_id)

            # Generate user events
            user_events.extend(
                self.event_generator.generate_user_events(
                    user_id=user.user_id,
                    signup_date=user.signup_date,
                    churn_date=churn_date,
                    num_days=backfill_days,
                    is_churned=is_churned,
                )
            )

            # Generate billing events (monthly billing)
            plan_prices = {
                PlanType.FREE: 0.0,
                PlanType.BASIC: 9.99,
                PlanType.PRO: 29.99,
            }
            plan_price = plan_prices[PlanType(user.plan_type)]

            # Only generate billing for paid plans
            if plan_price > 0:
                billing_events.extend(
                    self.event_generator.generate_billing_events(
                        user_id=user.user_id,
                        signup_date=user.signup_date,
                        plan_price=plan_price,
                        churn_date=churn_date,
                        num_months=backfill_days // 30,
                        is_churned=is_churned,
                    )
                )

        logger.info(
            f"Generated {len(user_events)} user events and "
            f"{len(billing_events)} billing events"
        )
        return user_events, billing_events

    def generate_all(
        self,
        num_users: int = 10000,
        churn_rate: float = 0.15,
        backfill_days: int = 365,
    ) -> Tuple[List[UserSchema], List[UserEventSchema], List[BillingEventSchema]]:
        """
        Generate complete synthetic dataset.
        
        Args:
            num_users: Number of users to generate
            churn_rate: Proportion of users to churn
            backfill_days: Days of historical data
            
        Returns:
            Tuple of (users, user_events, billing_events)
        """
        logger.info(
            f"Starting synthetic data generation: "
            f"{num_users} users, {churn_rate*100}% churn rate, "
            f"{backfill_days} days backfill"
        )

        users = self.generate_users(num_users=num_users)
        user_events, billing_events = self.generate_events(
            users=users, churn_rate=churn_rate, backfill_days=backfill_days
        )

        return users, user_events, billing_events


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    generator = SyntheticDataGenerator(seed=42)
    users, user_events, billing_events = generator.generate_all(
        num_users=100,  # Small test set
        churn_rate=0.15,
        backfill_days=365,
    )

    print(f"\n✅ Generated:")
    print(f"  • {len(users)} users")
    print(f"  • {len(user_events)} user events")
    print(f"  • {len(billing_events)} billing events")
    print(f"\nSample user: {users[0]}")
    print(f"Sample event: {user_events[0]}")
    if billing_events:
        print(f"Sample billing: {billing_events[0]}")
