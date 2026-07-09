"""
Action Executor - Execute planned actions in batches

Responsibility: Execute actions with status PLANNED in batches of 100.
Updates action statuses and finalizes runs when complete.
"""

import logging
from typing import Dict
from collections import defaultdict

from db.accounts_db import (
    get_actions_by_status,
    mark_actions_status,
    get_runs_by_status,
    set_run_status,
    count_actions_by_run_and_status,
    get_account_for_profile,
)
from backend.app.services.amazon_bids import (
    update_keyword_bids,
    update_target_bids,
    get_current_bids,
    update_sb_keyword_bids,
    update_sb_target_bids,
)
from backend.app.services.amazon import get_api_url_for_country, get_valid_access_token

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


def execute_actions_once(batch_size: int = BATCH_SIZE) -> Dict:
    """
    Execute a batch of planned actions.
    
    - Fetches up to batch_size actions with status PLANNED
    - Marks them EXECUTING
    - Gets current bids from Amazon
    - Calculates new bids and sends updates
    - Marks actions as EXECUTED or FAILED
    
    Returns:
        Dict with execution results
    """
    actions = get_actions_by_status("PLANNED", limit=batch_size)
    
    if not actions:
        logger.info("No planned actions to execute")
        return {"executed": 0, "failed": 0, "message": "No actions to execute"}
    
    action_ids = [a["id"] for a in actions]
    mark_actions_status(action_ids, "EXECUTING")
    
    logger.info(f"Executing {len(actions)} actions")
    
    actions_by_profile = defaultdict(list)
    for action in actions:
        profile_id = str(action.get("profile_id", ""))
        actions_by_profile[profile_id].append(action)
    
    total_success = 0
    total_failed = 0
    profile_results = []
    
    for profile_id, profile_actions in actions_by_profile.items():
        result = _execute_profile_actions(profile_id, profile_actions)
        
        total_success += result.get("success", 0)
        total_failed += result.get("failed", 0)
        profile_results.append({
            "profile_id": profile_id,
            "success": result.get("success", 0),
            "failed": result.get("failed", 0),
            "error": result.get("error")
        })
    
    logger.info(f"Execution complete: {total_success} success, {total_failed} failed")
    
    return {
        "executed": total_success,
        "failed": total_failed,
        "profiles_processed": len(actions_by_profile),
        "results": profile_results
    }


def _execute_profile_actions(profile_id: str, actions: list) -> Dict:
    """Execute actions for a single profile."""
    profile_info = get_account_for_profile(profile_id)
    if not profile_info:
        action_ids = [a["id"] for a in actions]
        mark_actions_status(action_ids, "FAILED")
        logger.error(f"Profile {profile_id} not found")
        return {"success": 0, "failed": len(actions), "error": "Profile not found"}
    
    account_id = profile_info.get("client_account_id")
    country_code = profile_info.get("country_code", "")
    api_url = profile_info.get("api_url") or get_api_url_for_country(country_code) or "https://advertising-api-eu.amazon.com"
    
    access_token, token_error = get_valid_access_token(account_id)
    if not access_token:
        action_ids = [a["id"] for a in actions]
        mark_actions_status(action_ids, "FAILED")
        error_msg = token_error.get('error', 'No valid tokens') if token_error else 'No valid tokens'
        logger.error(f"No valid token for account {account_id}: {error_msg}")
        return {"success": 0, "failed": len(actions), "error": error_msg}
    
    logger.info(f"[EXECUTOR] Token prefix: {access_token[:20]}... len={len(access_token)}")
    
    sp_actions = [a for a in actions if a.get("ad_product", "SP") == "SP"]
    sb_actions = [a for a in actions if a.get("ad_product") == "SB"]
    
    sp_target_ids = [str(a.get("keyword_id")) for a in sp_actions if a.get("keyword_id")]
    current_bids = get_current_bids(access_token, profile_id, sp_target_ids, api_url) if sp_target_ids else {}
    
    sp_keyword_updates = []
    sp_target_updates = []
    sp_keyword_action_ids = []
    sp_target_action_ids = []
    sb_keyword_updates = []
    sb_keyword_action_ids = []
    sb_target_updates = []
    sb_target_action_ids = []
    failed_action_ids = []
    
    for action in sp_actions:
        action_id = action.get("id")
        target_id = str(action.get("keyword_id", ""))
        delta_bid = float(action.get("delta_bid") or 0)
        
        bid_info = current_bids.get(target_id)
        if not bid_info:
            failed_action_ids.append(action_id)
            continue
        
        current_bid = bid_info.get("bid")
        target_type = str(bid_info.get("targetType", "KEYWORD")).upper()
        
        new_bid = max(0.02, round(current_bid + delta_bid, 2))
        
        if target_type == "KEYWORD":
            sp_keyword_updates.append({"keywordId": target_id, "bid": new_bid})
            sp_keyword_action_ids.append(action_id)
        else:
            sp_target_updates.append({"targetId": target_id, "bid": new_bid})
            sp_target_action_ids.append(action_id)
    
    for action in sb_actions:
        action_id = action.get("id")
        target_id = str(action.get("keyword_id", ""))
        ad_group_id = action.get("ad_group_id")
        delta_bid = float(action.get("delta_bid") or 0)
        current_bid = action.get("current_bid")
        target_type = str(action.get("target_type", "")).upper()
        
        if current_bid is None or not target_id:
            failed_action_ids.append(action_id)
            logger.warning(f"[EXECUTOR] SB action {action_id} failed: current_bid={current_bid}, target_id={target_id}")
            continue
        
        if not ad_group_id:
            failed_action_ids.append(action_id)
            logger.warning(f"[EXECUTOR] SB action {action_id} failed: missing ad_group_id")
            continue
        
        new_bid = max(0.02, round(float(current_bid) + delta_bid, 2))
        
        if target_type == "KEYWORD":
            sb_keyword_updates.append({
                "keywordId": target_id,
                "adGroupId": ad_group_id,
                "bid": new_bid
            })
            sb_keyword_action_ids.append(action_id)
        else:
            sb_target_updates.append({
                "targetId": target_id,
                "adGroupId": ad_group_id,
                "bid": new_bid
            })
            sb_target_action_ids.append(action_id)
    
    if failed_action_ids:
        mark_actions_status(failed_action_ids, "FAILED")
    
    success_count = 0
    
    if sp_keyword_updates:
        kw_result = update_keyword_bids(access_token, profile_id, sp_keyword_updates, api_url)
        kw_success = kw_result.get("success", 0)
        success_count += kw_success
        
        if kw_success > 0:
            mark_actions_status(sp_keyword_action_ids[:kw_success], "EXECUTED")
        if kw_result.get("failed", 0) > 0:
            mark_actions_status(sp_keyword_action_ids[kw_success:], "FAILED")
    
    if sp_target_updates:
        tgt_result = update_target_bids(access_token, profile_id, sp_target_updates, api_url)
        tgt_success = tgt_result.get("success", 0)
        success_count += tgt_success
        
        if tgt_success > 0:
            mark_actions_status(sp_target_action_ids[:tgt_success], "EXECUTED")
        if tgt_result.get("failed", 0) > 0:
            mark_actions_status(sp_target_action_ids[tgt_success:], "FAILED")
    
    if sb_keyword_updates:
        sb_kw_result = update_sb_keyword_bids(access_token, profile_id, sb_keyword_updates, api_url)
        sb_kw_success = sb_kw_result.get("success", 0)
        success_count += sb_kw_success
        
        if sb_kw_success > 0:
            mark_actions_status(sb_keyword_action_ids[:sb_kw_success], "EXECUTED")
        if sb_kw_result.get("failed", 0) > 0:
            mark_actions_status(sb_keyword_action_ids[sb_kw_success:], "FAILED")
    
    if sb_target_updates:
        sb_tgt_result = update_sb_target_bids(access_token, profile_id, sb_target_updates, api_url)
        sb_tgt_success = sb_tgt_result.get("success", 0)
        success_count += sb_tgt_success
        
        if sb_tgt_success > 0:
            mark_actions_status(sb_target_action_ids[:sb_tgt_success], "EXECUTED")
        if sb_tgt_result.get("failed", 0) > 0:
            mark_actions_status(sb_target_action_ids[sb_tgt_success:], "FAILED")
    
    total_failed = len(failed_action_ids)
    total_failed += len(sp_keyword_updates) + len(sp_target_updates) + len(sb_keyword_updates) + len(sb_target_updates) - success_count
    
    return {
        "success": success_count,
        "failed": total_failed
    }


def finalize_runs_once() -> Dict:
    """
    Check runs in ACTIONS_PLANNED or EXECUTING state.
    If no pending actions remain, set run to DONE.
    
    Returns:
        Dict with finalization results
    """
    runs = get_runs_by_status(["ACTIONS_PLANNED", "EXECUTING"])
    
    if not runs:
        return {"finalized": 0, "message": "No runs to finalize"}
    
    finalized = 0
    
    for run in runs:
        run_id = run.get("id")
        
        pending_count = count_actions_by_run_and_status(run_id, ["PLANNED", "EXECUTING"])
        
        if pending_count == 0:
            set_run_status(run_id, "DONE")
            logger.info(f"Run {run_id} finalized to DONE")
            finalized += 1
        else:
            logger.info(f"Run {run_id} still has {pending_count} pending actions")
    
    return {
        "finalized": finalized,
        "checked": len(runs)
    }
