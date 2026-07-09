import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Amazon Ads Manager"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    DATABASE_URL: str = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "")
    
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_ID: str = os.getenv("STRIPE_PRICE_ID", "")
    
    AMAZON_ADS_CLIENT_ID: str = os.getenv("AMAZON_ADS_CLIENT_ID", "")
    AMAZON_ADS_CLIENT_SECRET: str = os.getenv("AMAZON_ADS_CLIENT_SECRET", "")
    AMAZON_ADS_REDIRECT_URI: str = os.getenv("AMAZON_ADS_REDIRECT_URI", "")
    
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "erba.francesco.mp@gmail.com")
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
