from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from backend.app.core.database import get_db

router = APIRouter()


class BidUpdate(BaseModel):
    target_id: str
    new_bid: float


class BidUpdateRequest(BaseModel):
    account_id: int
    profile_id: str
    updates: List[BidUpdate]


class BidApplyRequest(BaseModel):
    account_id: int
    profile_id: str
    campaign_ids: List[str]
    strategy: str
    value_mode: Optional[str] = "percentage"
    percentage: Optional[float] = None
    absolute_value: Optional[float] = None
    fixed_value: Optional[float] = None
    country_code: Optional[str] = None
    min_bid: float = 0.02
    max_bid: float = 100.0


@router.post("/apply")
async def apply_bids(request: BidApplyRequest, db: Session = Depends(get_db)):
    from db.accounts_db import get_client_tokens
    from backend.app.services.amazon_ads.targets import get_targets_for_campaign
    from backend.app.services.amazon_ads.update_bids import update_target_bids
    from backend.app.services.amazon import get_api_url_for_country
    
    if request.strategy not in ["increase", "decrease", "set"]:
        raise HTTPException(status_code=400, detail="Strategy must be 'increase', 'decrease', or 'set'")
    
    value_mode = request.value_mode or "percentage"
    
    if request.strategy in ["increase", "decrease"]:
        if value_mode == "percentage" and not request.percentage:
            raise HTTPException(status_code=400, detail="Percentage is required for percentage mode")
        if value_mode == "absolute" and not request.absolute_value:
            raise HTTPException(status_code=400, detail="Absolute value is required for absolute mode")
    
    if request.strategy == "set" and not request.absolute_value and not request.fixed_value:
        raise HTTPException(status_code=400, detail="Value is required for set strategy")
    
    if not request.campaign_ids:
        raise HTTPException(status_code=400, detail="At least one campaign_id is required")
    
    token_data = get_client_tokens(request.account_id)
    if not token_data:
        raise HTTPException(status_code=401, detail="Account not connected")
    
    access_token = token_data.get("access_token")
    api_url = get_api_url_for_country(request.country_code) if request.country_code else None
    
    all_targets = []
    for campaign_id in request.campaign_ids:
        if not campaign_id or campaign_id == "undefined":
            continue
        try:
            targets = get_targets_for_campaign(access_token, request.profile_id, campaign_id, api_url=api_url)
            if targets:
                all_targets.extend(targets)
        except Exception as e:
            print(f"Error fetching targets for campaign {campaign_id}: {e}")
            continue
    
    if not all_targets:
        return {"updated_count": 0, "message": "Nessun target trovato nelle campagne selezionate"}
    
    fixed_value = request.absolute_value or request.fixed_value
    
    updates = []
    for target in all_targets:
        if not target or not isinstance(target, dict):
            continue
        
        bid_data = target.get("bid", {})
        if isinstance(bid_data, dict):
            current_bid = bid_data.get("bid", 0)
        else:
            current_bid = bid_data
            
        if not current_bid or current_bid <= 0:
            continue
            
        if request.strategy == "set":
            new_bid = fixed_value
        elif request.strategy == "increase":
            if value_mode == "percentage":
                new_bid = current_bid * (1 + request.percentage / 100)
            else:
                new_bid = current_bid + request.absolute_value
        else:
            if value_mode == "percentage":
                new_bid = current_bid * (1 - request.percentage / 100)
            else:
                new_bid = current_bid - request.absolute_value
        
        new_bid = max(0.01, new_bid)
        new_bid = round(new_bid, 2)
        
        target_id = target.get("targetId")
        if target_id:
            updates.append({
                "targetId": target_id,
                "bid": new_bid
            })
    
    if updates:
        try:
            result = update_target_bids(access_token, request.profile_id, updates, api_url=api_url)
            return {"updated_count": len(updates), "result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating bids: {str(e)}")
    
    return {"updated_count": 0, "message": "Nessun target da aggiornare"}


@router.post("/update")
async def update_bids(request: BidUpdateRequest, db: Session = Depends(get_db)):
    from db.accounts_db import get_client_tokens
    from backend.app.services.amazon_ads.update_bids import update_target_bids

    token_data = get_client_tokens(request.account_id)
    if not token_data:
        raise HTTPException(status_code=401, detail="Account not connected")
    
    access_token = token_data.get("access_token")
    
    updates_list = [{"targetId": u.target_id, "bid": u.new_bid} for u in request.updates]
    
    result = update_target_bids(access_token, request.profile_id, updates_list)
    
    return result
