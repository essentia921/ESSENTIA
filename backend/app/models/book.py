from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from backend.app.core.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    asin = Column(String(20), unique=True, index=True, nullable=False)
    marketplace = Column(String(10), nullable=True)
    
    title = Column(String(500), nullable=True)
    subtitle = Column(String(500), nullable=True)
    link = Column(Text, nullable=True)
    
    format = Column(String(50), nullable=True)
    pages = Column(Integer, nullable=True)
    width_inches = Column(Float, nullable=True)
    height_inches = Column(Float, nullable=True)
    trim_size = Column(String(20), nullable=True)
    ink_type = Column(String(30), default="black")
    
    price = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True)
    c_print = Column(Float, nullable=True)
    royalty_rate = Column(Float, default=0.6)
    r_net = Column(Float, nullable=True)
    acos_be = Column(Float, nullable=True)
    acos_opt = Column(Float, nullable=True)
    
    synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
