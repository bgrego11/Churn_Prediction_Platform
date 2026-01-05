"""
Pydantic schemas for synthetic data generation.
Defines the shape of users, user_events, and billing_events.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PlanType(str, Enum):
    """Available subscription plan types."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"


class EventType(str, Enum):
    """Available user event types."""
    LOGIN = "login"
    LOGOUT = "logout"
    PAGE_VIEW = "page_view"
    SEARCH = "search"
    DOWNLOAD = "download"
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


class BillingStatus(str, Enum):
    """Billing transaction statuses."""
    SUCCESSFUL = "successful"
    FAILED = "failed"
    REFUNDED = "refunded"


class UserSchema(BaseModel):
    """Schema for user records."""
    user_id: int = Field(..., description="Unique user identifier")
    plan_type: PlanType = Field(..., description="Current subscription plan")
    signup_date: datetime = Field(..., description="Date user signed up")
    country: str = Field(..., description="User's country code (ISO 3166-1 alpha-2)")

    class Config:
        use_enum_values = True


class UserEventSchema(BaseModel):
    """Schema for user behavior events."""
    user_id: int = Field(..., description="User who triggered event")
    event_type: EventType = Field(..., description="Type of event")
    event_time: datetime = Field(..., description="When event occurred")
    session_id: Optional[str] = Field(
        None, description="Session identifier for grouping events"
    )

    class Config:
        use_enum_values = True


class BillingEventSchema(BaseModel):
    """Schema for billing/payment events."""
    user_id: int = Field(..., description="User being charged")
    amount: float = Field(..., ge=0, description="Amount in USD")
    status: BillingStatus = Field(..., description="Payment status")
    event_time: datetime = Field(..., description="When transaction occurred")

    class Config:
        use_enum_values = True
