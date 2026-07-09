import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from backend.app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


class ProfileResponse(BaseModel):
    profileId: str
    countryCode: str
    marketplace: Optional[str] = None
    accountId: Optional[str] = None
    region: Optional[str] = None
    
    class Config:
        from_attributes = True


class ProfilesResponse(BaseModel):
    profiles: List[dict]
    warning: Optional[str] = None


def normalize_profile(profile: dict) -> dict:
    return {
        "profileId": str(profile.get("profileId") or profile.get("profile_id", "")),
        "countryCode": profile.get("countryCode") or profile.get("country_code", ""),
        "marketplace": profile.get("marketplace") or profile.get("marketplaceString") or profile.get("marketplace_string", ""),
        "accountId": str(profile.get("accountId", "")) if profile.get("accountId") else None,
        "region": profile.get("region") or profile.get("_region", ""),
    }


@router.get("/{account_id}")
async def get_profiles(account_id: int, force_refresh: bool = False, db: Session = Depends(get_db)):
    from db.accounts_db import get_client_profiles, save_client_profiles
    from backend.app.services.amazon import get_amazon_profiles
    
    if not force_refresh:
        cached_profiles = get_client_profiles(account_id)
        if cached_profiles:
            return [normalize_profile(p.get("profile_data", p) if isinstance(p, dict) else p) for p in cached_profiles]
    
    profiles, status = get_amazon_profiles(account_id)
    
    if status:
        status_code = status.get("code", "UNKNOWN")
        
        if status_code == "PARTIAL_SUCCESS":
            logger.warning(f"Partial success for account {account_id}: {status.get('warning', '')}")
        elif status_code == "NO_TOKENS":
            raise HTTPException(status_code=424, detail="Account not connected to Amazon Ads. Please connect your Amazon account first.")
        elif status_code == "AUTH_FAILED":
            raise HTTPException(status_code=424, detail="Amazon authentication expired. Please reconnect your account.")
        elif status_code == "API_ERROR":
            raise HTTPException(status_code=502, detail=f"Amazon API error: {status.get('error', 'Unknown error')}")
        elif status_code != "PARTIAL_SUCCESS":
            raise HTTPException(status_code=500, detail=status.get("error", "Unknown error"))
    
    if profiles:
        save_client_profiles(account_id, profiles)
    
    return [normalize_profile(p) for p in profiles]
