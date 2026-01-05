"""
Event generation logic for realistic user behavior.
Includes session patterns, churn indicators, and billing cycles.
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from .schemas import (
    BillingEventSchema,
    BillingStatus,
    EventType,
    UserEventSchema,
)


class EventGenerator:
    """Generates realistic user and billing events."""

    def __init__(self, seed: int = 42):
        """
        Initialize event generator.
        
        Args:
            seed: Random seed for reproducibility
        """
        random.seed(seed)

    def generate_user_events(
        self,
        user_id: int,
        signup_date: datetime,
        churn_date: Optional[datetime] = None,
        num_days: int = 365,
        is_churned: bool = False,
    ) -> List[UserEventSchema]:
        """
        Generate realistic user events with session patterns.
        
        Args:
            user_id: User identifier
            signup_date: When user signed up
            churn_date: Optional date user churned
            num_days: Number of days to generate events for
            is_churned: Whether user has churned
            
        Returns:
            List of user event records
        """
        events = []
        current_date = signup_date
        end_date = signup_date + timedelta(days=num_days)

        while current_date < end_date:
            # Skip days probabilistically (users don't log in every day)
            if random.random() < 0.3:  # 30% chance to skip day
                current_date += timedelta(days=1)
                continue

            # If churned, stop generating events after churn date
            if is_churned and churn_date and current_date > churn_date:
                break

            # Generate 1-5 sessions per active day
            num_sessions = random.randint(1, 5)
            for session_num in range(num_sessions):
                session_id = str(uuid.uuid4())
                session_start = current_date + timedelta(
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )

                # Generate 2-15 events per session
                num_session_events = random.randint(2, 15)
                for event_num in range(num_session_events):
                    event_time = session_start + timedelta(
                        seconds=random.randint(0, 1800)
                    )

                    # Event type distribution (realistic patterns)
                    event_type_choice = random.random()
                    if event_type_choice < 0.4:
                        event_type = EventType.PAGE_VIEW
                    elif event_type_choice < 0.6:
                        event_type = EventType.SEARCH
                    elif event_type_choice < 0.8:
                        event_type = EventType.DOWNLOAD
                    else:
                        event_type = EventType.LOGIN

                    events.append(
                        UserEventSchema(
                            user_id=user_id,
                            event_type=event_type,
                            event_time=event_time,
                            session_id=session_id,
                        )
                    )

            current_date += timedelta(days=1)

        return events

    def generate_billing_events(
        self,
        user_id: int,
        signup_date: datetime,
        plan_price: float,
        churn_date: Optional[datetime] = None,
        num_months: int = 12,
        is_churned: bool = False,
    ) -> List[BillingEventSchema]:
        """
        Generate monthly billing events with occasional failures and refunds.
        
        Args:
            user_id: User identifier
            signup_date: When user signed up
            plan_price: Monthly plan cost
            churn_date: Optional date user churned
            num_months: Number of months to generate billing for
            is_churned: Whether user has churned
            
        Returns:
            List of billing event records
        """
        events = []
        current_month = signup_date

        for month_offset in range(num_months):
            billing_date = current_month + timedelta(days=month_offset * 30)

            # Stop billing if user churned
            if is_churned and churn_date and billing_date > churn_date:
                break

            # 85% chance of successful charge
            if random.random() < 0.85:
                status = BillingStatus.SUCCESSFUL
                amount = plan_price
            else:
                # Failed charges (retry logic)
                status = BillingStatus.FAILED
                amount = plan_price

            events.append(
                BillingEventSchema(
                    user_id=user_id,
                    amount=amount,
                    status=status,
                    event_time=billing_date,
                )
            )

            # Occasional refunds (5% chance)
            if random.random() < 0.05 and status == BillingStatus.SUCCESSFUL:
                events.append(
                    BillingEventSchema(
                        user_id=user_id,
                        amount=plan_price,
                        status=BillingStatus.REFUNDED,
                        event_time=billing_date + timedelta(days=random.randint(1, 7)),
                    )
                )

        return events
