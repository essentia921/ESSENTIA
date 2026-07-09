from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.sql import func
from backend.app.core.database import Base


TIER_COMMISSION = {
    "platinum": 0.10,
    "diamond": 0.20,
}


class Affiliate(Base):
    __tablename__ = "affiliates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    tier = Column(String(20), default="platinum")
    is_active = Column(Boolean, default=True)
    balance_pending = Column(Float, default=0.0)
    total_earned = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    affiliate_id = Column(Integer, ForeignKey("affiliates.id"), nullable=False)
    referred_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    stripe_session_id = Column(String(200), nullable=True, unique=True)
    amount_paid = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)


def init_affiliate_tables():
    from backend.app.core.database import engine
    Affiliate.__table__.create(bind=engine, checkfirst=True)
    Referral.__table__.create(bind=engine, checkfirst=True)
