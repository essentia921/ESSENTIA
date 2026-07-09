from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
import enum
from backend.app.core.database import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    SUBSCRIBER = "subscriber"


class SubscriptionStatus(str, enum.Enum):
    NONE = "none"
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    
    google_id = Column(String, unique=True, nullable=True)
    
    role = Column(String, default=UserRole.USER.value)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    stripe_customer_id = Column(String, unique=True, nullable=True)
    subscription_status = Column(String, default=SubscriptionStatus.NONE.value)
    subscription_id = Column(String, nullable=True)
    subscription_ends_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
