from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from backend.app.core.database import Base


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seed_keywords = Column(ARRAY(Text), nullable=False)
    extraction_type = Column(String(20), default="asins")
    category_mode = Column(String(20), default="books")
    status = Column(String(20), default="pending")
    progress = Column(Integer, default=0)
    asins_found = Column(Integer, default=0)
    keywords_found = Column(Integer, default=0)
    max_asins = Column(Integer, default=1000)
    max_keywords = Column(Integer, default=1000)
    include_merch = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ExtractedAsin(Base):
    __tablename__ = "extracted_asins"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("extraction_jobs.id"), nullable=True)
    asin = Column(String(20), nullable=False, index=True)
    title = Column(Text, nullable=False)
    brand = Column(Text, nullable=True)
    price = Column(String(50), nullable=True)
    rating = Column(Float, nullable=True)
    ratings_total = Column(Integer, nullable=True)
    bsr = Column(Integer, nullable=True)
    image_url = Column(Text, nullable=True)
    format = Column(String(50), nullable=True)
    source = Column(String(50), nullable=False)
    seed_keyword = Column(Text, nullable=False)
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())


class ExtractedKeyword(Base):
    __tablename__ = "extracted_keywords"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("extraction_jobs.id"), nullable=True)
    keyword = Column(Text, nullable=False, index=True)
    source = Column(String(50), nullable=False)
    source_asin = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True)
    relevance_score = Column(Float, nullable=True)
    is_seed = Column(Boolean, default=False)
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())


class ExtractorApiLog(Base):
    __tablename__ = "extractor_api_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), ForeignKey("extraction_jobs.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    log_type = Column(String(50), nullable=False)
    endpoint = Column(Text, nullable=False)
    request_data = Column(Text, nullable=False)
    response_data = Column(Text, nullable=False)
    source = Column(String(50), nullable=False)
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
