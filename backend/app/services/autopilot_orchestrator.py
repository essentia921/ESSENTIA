"""
Autopilot Orchestrator - State Machine for Autopilot Runs

Responsibility: Process ONE step per run based on current status.
Each call to process_run executes at most one state transition.

State Transitions:
- CREATED -> REPORTS_PENDING: Request reports from Amazon
- REPORTS_READY -> ANALYZING -> ACTIONS_PLANNED: Analyze and generate actions
- ACTIONS_PLANNED -> EXECUTING: Optional, executor handles this
- DONE / FAILED: No-op
"""

import logging
from typing import Dict, Optional

from db.accounts_db import (
    get_autopilot_run,
    set_run_status,
    attach_run_reports,
    create_report_record,
    get_reports_for_run,
    insert_planned_actions,
    get_asin_to_acos_be_map,
    get_account_for_profile,
    get_client_tokens,
)
from backend.app.services.amazon_reports import (
    create_report as amazon_create_report,
    get_date_range,
)
from backend.app.services.amazon import get_api_url_for_country, get_amazon_keywords_and_targets
from backend.app.services.autopilot_sync_service import get_sb_inventory_for_profile

logger = logging.getLogger(__name__)


def _get_autopilot_settings(account_id: int) -> Dict:
    """Load autopilot settings for an account from DB."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM autopilot_settings WHERE account_id = %s", (account_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return {
                "delta_excellent": float(row["delta_excellent"]),
                "delta_good": float(row["delta_good"]),
                "delta_above_be": float(row["delta_above_be"]),
                "delta_high": float(row["delta_high"]),
                "delta_low_impressions": float(row["delta_low_impressions"]),
                "delta_no_sales": float(row["delta_no_sales"]),
                "low_impressions_threshold": int(row["low_impressions_threshold"]),
                "min_spend_for_decrement": float(row["min_spend_for_decrement"])
            }
    except Exception as e:
        logger.warning(f"Could not load autopilot settings for account {account_id}: {e}")
    
    return None


def process_run(run_id: int) -> Dict:
    """
    Process one step for a run based on its current status.
    Executes at most one state transition per call.
    
    Returns:
        Updated run dict with new status
    """
    run = get_autopilot_run(run_id)
    if not run:
        logger.error(f"Run {run_id} not found")
        return {"error": "Run not found", "run_id": run_id}
    
    status = run.get("status", "")
    profile_id = run.get("profile_id")
    account_id = run.get("account_id")
    
    logger.info(f"Processing run {run_id} with status {status}")
    
    if status == "CREATED":
        return _transition_created_to_reports_pending(run_id, profile_id, account_id)
    
    elif status == "REPORTS_READY":
        return _transition_reports_ready_to_actions_planned(run_id, profile_id)
    
    elif status == "ACTIONS_PLANNED":
        return _transition_actions_planned_to_executing(run_id)
    
    elif status in ["DONE", "FAILED"]:
        logger.info(f"Run {run_id} is in terminal state {status}, no-op")
        return run
    
    elif status in ["REPORTS_PENDING", "ANALYZING", "EXECUTING"]:
        logger.info(f"Run {run_id} is in intermediate state {status}, no transition needed")
        return run
    
    else:
        logger.warning(f"Run {run_id} has unknown status {status}")
        return run


def _transition_created_to_reports_pending(run_id: int, profile_id: str, account_id: int) -> Dict:
    """
    Transition: CREATED -> REPORTS_PENDING
    - Request 14D and 30D reports from Amazon for both SP and SB
    - Save report records linked to run
    - Update run with report IDs
    """
    logger.info(f"Run {run_id}: Transitioning CREATED -> REPORTS_PENDING")
    
    profile_info = get_account_for_profile(profile_id)
    if not profile_info:
        set_run_status(run_id, "FAILED")
        logger.error(f"Run {run_id}: Profile {profile_id} not found")
        return {"run_id": run_id, "status": "FAILED", "error": "Profile not found"}
    
    api_url = profile_info.get("api_url") or get_api_url_for_country(profile_info.get("country_code")) or "https://advertising-api-eu.amazon.com"
    
    tokens = get_client_tokens(account_id)
    if not tokens or not tokens.get("access_token"):
        set_run_status(run_id, "FAILED")
        logger.error(f"Run {run_id}: No valid tokens for account {account_id}")
        return {"run_id": run_id, "status": "FAILED", "error": "No valid tokens"}
    
    access_token = tokens.get("access_token")
    
    # Only use 30D reports (14D removed per user request)
    start_30d, end_30d = get_date_range(30)
    
    sp_report_30d_id = None
    created_reports = 0
    
    for ad_product in ["SP", "SB"]:
        report_type_30d = f"{ad_product}_TARGETING_30D"
        
        try:
            report_30d_id = amazon_create_report(
                access_token, profile_id, api_url, report_type_30d, start_30d, end_30d, ad_product=ad_product
            )
            create_report_record(
                report_id=report_30d_id,
                run_id=run_id,
                profile_id=profile_id,
                account_id=account_id,
                report_type=report_type_30d,
                start_date=start_30d,
                end_date=end_30d,
                status="PENDING",
                ad_product=ad_product
            )
            if ad_product == "SP":
                sp_report_30d_id = report_30d_id
            created_reports += 1
            logger.info(f"Run {run_id}: Created {ad_product} 30D report {report_30d_id}")
        except Exception as e:
            logger.error(f"Run {run_id}: Failed to create {ad_product} 30D report: {e}")
    
    if created_reports == 0:
        set_run_status(run_id, "FAILED")
        return {"run_id": run_id, "status": "FAILED", "error": "Failed to create any reports"}
    
    attach_run_reports(run_id, None, sp_report_30d_id)  # No 14D report
    updated_run = set_run_status(run_id, "REPORTS_PENDING")
    
    logger.info(f"Run {run_id}: Transitioned to REPORTS_PENDING with {created_reports} reports")
    return updated_run


def _transition_reports_ready_to_actions_planned(run_id: int, profile_id: str) -> Dict:
    """
    Transition: REPORTS_READY -> ANALYZING -> ACTIONS_PLANNED
    - Load parsed report data from DB for both SP and SB
    - Load ASIN to ACOS BE map
    - Fetch targeting_to_id_map from Amazon API
    - Call bid_analyzer.analyze() for each ad_product
    - Save planned actions with ad_product field
    """
    from backend.app.services.bid_analyzer import analyze
    
    logger.info(f"Run {run_id}: Transitioning REPORTS_READY -> ACTIONS_PLANNED")
    
    set_run_status(run_id, "ANALYZING")
    
    run = get_autopilot_run(run_id)
    account_id = run.get("account_id") if run else None
    
    reports = get_reports_for_run(run_id)
    
    # Only check 30D reports (14D removed per user request)
    has_any_reports = any([
        reports.get("SP_30"), reports.get("SB_30")
    ])
    
    if not has_any_reports:
        set_run_status(run_id, "FAILED")
        logger.error(f"Run {run_id}: No 30D reports found")
        return {"run_id": run_id, "status": "FAILED", "error": "No 30D reports found"}
    
    asin_to_acos_be = get_asin_to_acos_be_map(profile_id)
    
    # Load delta_config for the account
    delta_config = None
    if account_id:
        delta_config = _get_autopilot_settings(account_id)
    
    targeting_to_id_map = {}
    live_bids = {}
    targets_map = {}
    if account_id:
        keywords_map, targets_map, err = get_amazon_keywords_and_targets(account_id, profile_id)
        if not err:
            targeting_to_id_map = keywords_map.pop("_targeting_to_id", {})
            logger.info(f"Run {run_id}: Loaded {len(targeting_to_id_map)} targeting expressions for resolution")
            
            for kw_id, kw_data in keywords_map.items():
                live_bids[kw_id] = {"bid": kw_data.get("bid"), "targetType": "keyword"}
                if kw_data.get("keyword"):
                    live_bids[kw_data["keyword"].lower()] = {"bid": kw_data.get("bid"), "targetType": "keyword"}
            for tgt_id, tgt_data in targets_map.items():
                bid_info = {"bid": tgt_data.get("bid"), "targetType": "target"}
                live_bids[tgt_id] = bid_info
                if tgt_data.get("report_targeting"):
                    live_bids[tgt_data["report_targeting"]] = bid_info
                    live_bids[tgt_data["report_targeting"].lower()] = bid_info
            logger.info(f"Run {run_id}: Built live_bids with {len(live_bids)} entries")
        else:
            logger.warning(f"Run {run_id}: Could not load targeting map: {err}")
    
    total_actions_count = 0
    
    for ad_product in ["SP", "SB"]:
        # Only use 30D reports (14D removed per user request)
        report_30 = reports.get(f"{ad_product}_30")
        
        if not report_30:
            logger.info(f"Run {run_id}: No {ad_product} 30D report found, skipping")
            continue
        
        data_30d = []
        
        # Accept both PARSED and COMPLETED status
        if report_30 and report_30.get("status") in ("PARSED", "COMPLETED"):
            report_data = report_30.get("report_data")
            if isinstance(report_data, list):
                # Handle nested list format [[{row1}, {row2}]] -> [{row1}, {row2}]
                if len(report_data) > 0 and isinstance(report_data[0], list):
                    data_30d = report_data[0]
                    logger.info(f"Run {run_id}: Flattened nested report data for {ad_product}")
                else:
                    data_30d = report_data
            elif isinstance(report_data, dict):
                data_30d = report_data.get("rows", report_data.get("data", []))
        
        if not data_30d:
            logger.info(f"Run {run_id}: No parsed {ad_product} 30D data, skipping")
            continue
        
        logger.info(f"Run {run_id}: Analyzing {ad_product}: {len(data_30d)} rows from 30D")
        
        # For SB, load separate inventory data from sb_inventory table
        if ad_product == "SB":
            sb_live_bids = {}
            sb_targeting_to_id_map = {}
            sb_targets_map = {}
            
            try:
                sb_inventory = get_sb_inventory_for_profile(profile_id)
                logger.info(f"Run {run_id}: Loaded {len(sb_inventory)} SB inventory entries")
                
                for row in sb_inventory:
                    entity_id = str(row.get('entity_id', ''))
                    entity_type = row.get('entity_type', '')
                    expression = row.get('expression', '') or ''
                    bid = float(row.get('current_bid')) if row.get('current_bid') else None
                    campaign_id = str(row.get('campaign_id', ''))
                    ad_group_id = str(row.get('ad_group_id', ''))
                    
                    if not entity_id or bid is None:
                        continue
                    
                    # Build live_bids map
                    target_type = "keyword" if entity_type == 'keyword' else "target"
                    sb_live_bids[entity_id] = {"bid": bid, "targetType": target_type}
                    
                    # Build targets_map
                    sb_targets_map[entity_id] = {
                        "bid": bid,
                        "expression": expression,
                        "keywordText": expression if entity_type == 'keyword' else None,
                        "report_targeting": expression,
                        "campaignId": campaign_id,
                        "adGroupId": ad_group_id,
                        "targetType": target_type
                    }
                    
                    # Build targeting_to_id_map for SB
                    if expression:
                        expr_lower = expression.lower().strip()
                        sb_targeting_to_id_map[expr_lower] = entity_id
                        # Composite key for precise matching
                        composite_key = f"{campaign_id}_{ad_group_id}_kw={expr_lower}" if entity_type == 'keyword' else f"{campaign_id}_{ad_group_id}_tgt={expr_lower}"
                        sb_targeting_to_id_map[composite_key] = entity_id
                
                logger.info(f"Run {run_id}: Built SB live_bids with {len(sb_live_bids)} entries, targeting_map with {len(sb_targeting_to_id_map)} entries")
                
            except Exception as e:
                logger.error(f"Run {run_id}: Failed to load SB inventory: {e}")
                sb_live_bids = {}
                sb_targeting_to_id_map = {}
                sb_targets_map = {}
            
            current_live_bids = sb_live_bids
            current_targeting_to_id_map = sb_targeting_to_id_map
            current_targets_map = sb_targets_map
        else:
            # SP uses the data loaded earlier
            current_live_bids = live_bids
            current_targeting_to_id_map = targeting_to_id_map
            current_targets_map = targets_map
        
        try:
            actions = analyze(
                profile_id=profile_id,
                report_14_data=[],  # 14D reports removed per user request
                report_30_data=data_30d,
                asin_to_acos_be_map=asin_to_acos_be,
                targeting_to_id_map=current_targeting_to_id_map,
                live_bids=current_live_bids,
                ad_product=ad_product,
                targets_map=current_targets_map,
                delta_config=delta_config
            )
        except Exception as e:
            logger.error(f"Run {run_id}: {ad_product} analysis failed: {e}")
            import traceback
            logger.error(f"Run {run_id}: {ad_product} traceback: {traceback.format_exc()}")
            continue
        
        if actions:
            for action in actions:
                action["ad_product"] = ad_product
            
            inserted = insert_planned_actions(run_id, profile_id, actions)
            total_actions_count += inserted
            logger.info(f"Run {run_id}: Inserted {inserted} {ad_product} planned actions")
        else:
            logger.info(f"Run {run_id}: No {ad_product} actions generated")
    
    updated_run = set_run_status(run_id, "ACTIONS_PLANNED")
    
    updated_run["actions_count"] = total_actions_count
    
    logger.info(f"Run {run_id}: Transitioned to ACTIONS_PLANNED with {total_actions_count} actions")
    return updated_run


def _transition_actions_planned_to_executing(run_id: int) -> Dict:
    """
    Transition: ACTIONS_PLANNED -> EXECUTING
    Optional: Executor will handle the actual execution
    """
    logger.info(f"Run {run_id}: Transitioning ACTIONS_PLANNED -> EXECUTING")
    updated_run = set_run_status(run_id, "EXECUTING")
    return updated_run
