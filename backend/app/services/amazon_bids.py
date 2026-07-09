"""
Amazon Bids Adapter - Wrapper for batch bid updates

Provides clean functions for updating keyword and target bids in batch.
Wraps the existing update_bids.py functions.
Supports both Sponsored Products (SP) and Sponsored Brands (SB).
"""

import logging
from typing import List, Dict

from backend.app.services.amazon_ads.update_bids import (
    update_keyword_bids as _update_keyword_bids,
    update_target_bids as _update_target_bids,
    get_all_target_bids as _get_all_target_bids,
    update_sb_keyword_bids as _update_sb_keyword_bids,
    update_sb_target_bids as _update_sb_target_bids,
)

logger = logging.getLogger(__name__)


def update_keyword_bids(access_token: str, profile_id: str, updates_batch: List[Dict], api_url: str = None) -> Dict:
    """
    Update keyword bids in batch.
    
    Args:
        access_token: Amazon access token
        profile_id: Amazon profile ID
        updates_batch: List of dicts with {keywordId, bid}
        api_url: Optional API URL override
        
    Returns:
        Result dict with success/failed counts
    """
    if not updates_batch:
        return {"success": 0, "failed": 0, "batches": 0, "results": []}
    
    logger.info(f"Updating {len(updates_batch)} keyword bids for profile {profile_id}")
    
    result = _update_keyword_bids(
        access_token=access_token,
        profile_id=profile_id,
        keywords=updates_batch,
        api_url=api_url
    )
    
    logger.info(f"Keyword update result: {result.get('success', 0)} success, {result.get('failed', 0)} failed")
    
    return result


def update_target_bids(access_token: str, profile_id: str, updates_batch: List[Dict], api_url: str = None) -> Dict:
    """
    Update target bids in batch.
    
    Args:
        access_token: Amazon access token
        profile_id: Amazon profile ID
        updates_batch: List of dicts with {targetId, bid}
        api_url: Optional API URL override
        
    Returns:
        Result dict with success/failed counts
    """
    if not updates_batch:
        return {"success": 0, "failed": 0, "batches": 0, "results": []}
    
    logger.info(f"Updating {len(updates_batch)} target bids for profile {profile_id}")
    
    result = _update_target_bids(
        access_token=access_token,
        profile_id=profile_id,
        targets=updates_batch,
        api_url=api_url
    )
    
    logger.info(f"Target update result: {result.get('success', 0)} success, {result.get('failed', 0)} failed")
    
    return result


def get_current_bids(access_token: str, profile_id: str, target_ids: List[str], api_url: str = None) -> Dict:
    """
    Get current bids for a list of target IDs.
    
    Args:
        access_token: Amazon access token
        profile_id: Amazon profile ID
        target_ids: List of target/keyword IDs
        api_url: Optional API URL override
        
    Returns:
        Dict mapping target_id to {bid, targetType}
    """
    if not target_ids:
        return {}
    
    logger.info(f"Fetching bids for {len(target_ids)} targets in profile {profile_id}")
    
    result = _get_all_target_bids(
        access_token=access_token,
        profile_id=profile_id,
        target_ids=target_ids,
        api_url=api_url
    )
    
    logger.info(f"Retrieved bids for {len(result)} targets")
    
    return result


def update_sb_keyword_bids(access_token: str, profile_id: str, updates_batch: List[Dict], api_url: str = None) -> Dict:
    """
    Update Sponsored Brands keyword bids in batch.
    
    Args:
        access_token: Amazon access token
        profile_id: Amazon profile ID
        updates_batch: List of dicts with {keywordId, bid}
        api_url: Optional API URL override
        
    Returns:
        Result dict with success/failed counts
    """
    if not updates_batch:
        return {"success": 0, "failed": 0, "batches": 0, "results": []}
    
    logger.info(f"Updating {len(updates_batch)} SB keyword bids for profile {profile_id}")
    
    result = _update_sb_keyword_bids(
        access_token=access_token,
        profile_id=profile_id,
        keywords=updates_batch,
        api_url=api_url
    )
    
    logger.info(f"SB Keyword update result: {result.get('success', 0)} success, {result.get('failed', 0)} failed")
    
    return result


def update_sb_target_bids(access_token: str, profile_id: str, updates_batch: List[Dict], api_url: str = None) -> Dict:
    """
    Update Sponsored Brands target bids in batch.
    
    Args:
        access_token: Amazon access token
        profile_id: Amazon profile ID
        updates_batch: List of dicts with {targetId, bid}
        api_url: Optional API URL override
        
    Returns:
        Result dict with success/failed counts
    """
    if not updates_batch:
        return {"success": 0, "failed": 0, "batches": 0, "results": []}
    
    logger.info(f"Updating {len(updates_batch)} SB target bids for profile {profile_id}")
    
    result = _update_sb_target_bids(
        access_token=access_token,
        profile_id=profile_id,
        targets=updates_batch,
        api_url=api_url
    )
    
    logger.info(f"SB Target update result: {result.get('success', 0)} success, {result.get('failed', 0)} failed")
    
    return result
