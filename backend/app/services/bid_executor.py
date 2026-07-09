"""In-process bid execution service.

Extracted from autopilot_v2.step_execute_actions to allow direct invocation
from the BIG BANG worker without HTTP overhead or timeout limitations.
"""
from collections import defaultdict


def execute_all_bids(account_id: int) -> dict:
    """Execute all planned bid actions for an account.
    
    This is the core bid execution logic, callable directly from any context
    (API endpoint, worker, etc.) without HTTP.
    
    Returns dict with execution results.
    """
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    from backend.app.services.amazon_ads.update_bids import (
        update_target_bids, update_keyword_bids, 
        update_sb_keyword_bids, update_sb_target_bids,
        pause_sp_targets, pause_sb_targets, pause_sp_keywords, pause_sb_keywords
    )
    from backend.app.services.amazon_ads.targets import get_targets_for_campaign, get_keywords_for_campaign
    from backend.app.services.amazon import get_valid_access_token
    
    access_token, token_error = get_valid_access_token(account_id)
    if not access_token:
        error_msg = token_error.get('error', 'Token non disponibile') if token_error else 'Token non disponibile'
        return {"status": "error", "executed": 0, "failed": 0, "message": error_msg}
    
    print(f"[EXECUTE-BATCH] Token prefix: {access_token[:20]}... len={len(access_token)}")
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT pa.*, cp.country_code
            FROM planned_actions pa
            LEFT JOIN client_profiles cp ON pa.profile_id = cp.profile_id
            JOIN autopilot_profiles ap ON pa.profile_id = ap.profile_id AND ap.enabled = true
            WHERE pa.account_id = %s AND pa.status = 'PLANNED'
            ORDER BY pa.profile_id, pa.campaign_id, pa.id
        """, (account_id,))
        actions = cur.fetchall()
        
        if not actions:
            return {"status": "completed", "executed": 0, "failed": 0, "paused": 0, "message": "Nessuna azione da eseguire"}
        
        sp_actions_all = [a for a in actions if a.get('ad_product') != 'SB']
        sb_actions_all = [a for a in actions if a.get('ad_product') == 'SB']
        
        def _is_pause_action(a):
            r = a.get('reason', '')
            return r == 'PAUSE_HIGH_CLICKS_NO_SALES' or (isinstance(r, str) and r.startswith('PAUSA'))
        
        sp_pause_actions = [a for a in sp_actions_all if _is_pause_action(a)]
        sb_pause_actions = [a for a in sb_actions_all if _is_pause_action(a)]
        sp_actions = [a for a in sp_actions_all if not _is_pause_action(a)]
        sb_actions = [a for a in sb_actions_all if not _is_pause_action(a)]
        
        print(f"[EXECUTE-BATCH] Found {len(actions)} actions: {len(sp_actions)} SP bid, {len(sb_actions)} SB bid, {len(sp_pause_actions)} SP pause, {len(sb_pause_actions)} SB pause")
        
        total_executed = 0
        total_failed = 0
        total_paused = 0
        skipped = 0
        
        all_pause_actions = sp_pause_actions + sb_pause_actions
        if all_pause_actions:
            by_profile_type = defaultdict(list)
            for a in all_pause_actions:
                pid = str(a.get('profile_id', ''))
                cc = a.get('country_code', 'US')
                ap = a.get('ad_product', 'SP')
                tt = a.get('target_type', 'keyword')
                pause_key = f"{ap}_{'kw' if tt == 'keyword' else 'tgt'}"
                by_profile_type[(pid, cc, pause_key)].append(a)
            
            pause_fn_map = {
                "SP_kw": pause_sp_keywords,
                "SP_tgt": pause_sp_targets,
                "SB_kw": pause_sb_keywords,
                "SB_tgt": pause_sb_targets,
            }
            
            for (pid, cc, pause_key), pause_acts in by_profile_type.items():
                api_url_p = "https://advertising-api.amazon.com" if cc == 'US' else "https://advertising-api-eu.amazon.com"
                pause_fn = pause_fn_map.get(pause_key, pause_sp_keywords)
                is_sb = pause_key.startswith("SB")
                if pause_acts:
                    print(f"[EXECUTE-BATCH] Pausing {len(pause_acts)} {pause_key} for profile {pid}")
                    if is_sb:
                        result = pause_fn(access_token, pid, api_url=api_url_p, actions=pause_acts)
                    else:
                        entity_ids = [str(a.get('keyword_id', '')) for a in pause_acts if a.get('keyword_id')]
                        result = pause_fn(access_token, pid, entity_ids, api_url=api_url_p)
                    total_paused += result.get("success", 0)
                    pause_fail = result.get("failed", 0)
                    total_failed += pause_fail
                    if pause_fail == 0:
                        for a in pause_acts:
                            cur.execute("UPDATE planned_actions SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP WHERE id = %s", (a['id'],))
                    else:
                        error_msg = str(result.get("results", []))[:500]
                        for a in pause_acts:
                            cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", (error_msg, a['id']))
        
        sb_executed, sb_failed = _execute_sb_actions_sync(cur, sb_actions, access_token)
        total_executed += sb_executed
        total_failed += sb_failed
        
        by_campaign = defaultdict(list)
        for action in sp_actions:
            campaign_id = str(action.get('campaign_id', ''))
            profile_id = str(action.get('profile_id', ''))
            if campaign_id:
                by_campaign[(profile_id, campaign_id, action.get('country_code', 'US'))].append(action)
        
        keyword_expr_map = {}
        target_expr_map = {}
        keyword_id_map = {}
        target_id_map = {}
        
        for (profile_id, campaign_id, country_code), campaign_actions in by_campaign.items():
            api_url = "https://advertising-api.amazon.com" if country_code == 'US' else "https://advertising-api-eu.amazon.com"
            
            has_keywords = any(a.get('target_type') == 'keyword' for a in campaign_actions)
            has_targets = any(a.get('target_type') != 'keyword' for a in campaign_actions)
            
            try:
                if has_keywords:
                    print(f"[EXECUTE-BATCH] Fetching keywords for profile {profile_id}, campaign {campaign_id}...")
                    keywords = get_keywords_for_campaign(access_token, profile_id, campaign_id, api_url=api_url)
                    for kw in keywords:
                        kw_id = str(kw.get('keywordId', ''))
                        kw_text = kw.get('keywordText', '')
                        live_bid = float(kw.get('bid')) if kw.get('bid') else None
                        
                        if kw_id and live_bid is not None:
                            keyword_id_map[(profile_id, kw_id)] = live_bid
                        
                        if kw_text:
                            keyword_expr_map[(profile_id, campaign_id, kw_text.lower())] = {
                                'keywordId': kw.get('keywordId'),
                                'live_bid': live_bid
                            }
                
                if has_targets:
                    print(f"[EXECUTE-BATCH] Fetching targets for profile {profile_id}, campaign {campaign_id}...")
                    targets = get_targets_for_campaign(access_token, profile_id, campaign_id, api_url=api_url)
                    
                    for t in targets:
                        tid = str(t.get('targetId', ''))
                        td = t.get('targetDetails', {}) or {}
                        bid_obj = t.get('bid', {})
                        current_bid = bid_obj.get('bid') if isinstance(bid_obj, dict) else bid_obj
                        
                        if tid and current_bid is not None:
                            target_id_map[(profile_id, tid)] = float(current_bid)
                        
                        expression_key = None
                        
                        if 'keywordTarget' in td:
                            kw = (td.get('keywordTarget') or {}).get('keyword', '')
                            if kw:
                                expression_key = (profile_id, campaign_id, kw.lower())
                        elif 'productTarget' in td:
                            product_target = td.get('productTarget') or {}
                            product_info = product_target.get('product') or {}
                            asin = product_info.get('productId', '')
                            if asin:
                                expression_key = (profile_id, campaign_id, asin.upper())
                        elif 'autoTarget' in td:
                            auto_target = td.get('autoTarget') or {}
                            expressions = auto_target.get('expression') or []
                            if expressions and len(expressions) > 0:
                                auto_type = expressions[0].get('type', '')
                                if auto_type:
                                    expression_key = (profile_id, campaign_id, auto_type.lower())
                        
                        if expression_key and current_bid is not None:
                            target_expr_map[expression_key] = {
                                'targetId': tid,
                                'live_bid': float(current_bid)
                            }
                        
            except Exception as e:
                print(f"[EXECUTE-BATCH] Error fetching campaign {campaign_id}: {e}")
        
        print(f"[EXECUTE-BATCH] Built maps: {len(keyword_expr_map)} keywords (expr), {len(keyword_id_map)} keywords (id), {len(target_expr_map)} targets (expr), {len(target_id_map)} targets (id)")
        
        by_profile = defaultdict(lambda: {"targets": [], "keywords": [], "country_code": "US"})
        
        for action in sp_actions:
            profile_id = str(action.get('profile_id', ''))
            campaign_id = str(action.get('campaign_id', ''))
            action_keyword = action.get('keyword') or ''
            delta_bid = float(action.get('delta_bid', 0) or 0)
            target_type = action.get('target_type', 'keyword')
            is_keyword_type = (target_type == 'keyword')
            
            entity_id = action.get('entity_id')
            
            if entity_id:
                resolved_id = str(entity_id)
                
                if is_keyword_type:
                    live_bid = keyword_id_map.get((profile_id, resolved_id))
                else:
                    live_bid = target_id_map.get((profile_id, resolved_id))
                
                if live_bid is None:
                    stored_bid = action.get('current_bid')
                    if stored_bid and float(stored_bid) > 0:
                        live_bid = float(stored_bid)
                        print(f"[EXECUTE-BATCH] Using stored current_bid for entity_id={resolved_id}")
                
                if live_bid is None or live_bid <= 0:
                    skipped += 1
                    cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", 
                               (f"Live bid non trovato per entity_id={resolved_id}", action['id']))
                    continue
                
                new_bid = max(0.02, round(live_bid + delta_bid, 2))
                by_profile[profile_id]["country_code"] = action.get('country_code', 'US')
                
                if is_keyword_type:
                    by_profile[profile_id]["keywords"].append({
                        "action_id": action['id'],
                        "keywordId": resolved_id,
                        "live_bid": live_bid,
                        "new_bid": new_bid
                    })
                else:
                    by_profile[profile_id]["targets"].append({
                        "action_id": action['id'],
                        "targetId": resolved_id,
                        "live_bid": live_bid,
                        "new_bid": new_bid
                    })
                continue
            
            if not action_keyword:
                skipped += 1
                cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", 
                           ("Keyword/expression mancante", action['id']))
                continue
            
            entity_info = None
            
            if is_keyword_type:
                entity_info = keyword_expr_map.get((profile_id, campaign_id, action_keyword.lower()))
            else:
                action_asin = action_keyword
                if 'asin="' in action_keyword:
                    action_asin = action_keyword.replace('asin="', '').replace('"', '').strip()
                elif action_keyword.startswith('"') and action_keyword.endswith('"'):
                    action_asin = action_keyword.strip('"')
                
                entity_info = target_expr_map.get((profile_id, campaign_id, action_keyword.lower()))
                
                if not entity_info:
                    entity_info = target_expr_map.get((profile_id, campaign_id, action_asin.upper()))
                
                if not entity_info:
                    entity_info = target_expr_map.get((profile_id, campaign_id, action_asin.lower()))
                
                if not entity_info:
                    entity_info = target_expr_map.get((profile_id, campaign_id, action_keyword.upper()))
            
            if not entity_info or entity_info.get('live_bid') is None:
                entity_type = "Keyword" if is_keyword_type else "Target"
                target_type_detail = action.get('target_type', 'unknown')
                print(f"[EXECUTE-BATCH] No match for {entity_type} '{action_keyword}' (type={target_type_detail}) in campaign {campaign_id}")
                if not is_keyword_type:
                    debug_asin = action_keyword
                    if 'asin="' in action_keyword:
                        debug_asin = action_keyword.replace('asin="', '').replace('"', '').strip()
                    available_keys = [k[2] for k in target_expr_map.keys() if k[0] == profile_id and k[1] == campaign_id]
                    print(f"[EXECUTE-BATCH] Tried keys: lowercase='{action_keyword.lower()}', asin_upper='{debug_asin.upper()}', asin_lower='{debug_asin.lower()}'")
                    print(f"[EXECUTE-BATCH] Available targets ({len(available_keys)}): {available_keys[:15]}")
                skipped += 1
                cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", 
                           (f"{entity_type} '{action_keyword}' non trovato", action['id']))
                continue
            
            live_bid = entity_info['live_bid']
            new_bid = max(0.02, round(live_bid + delta_bid, 2))
            
            by_profile[profile_id]["country_code"] = action.get('country_code', 'US')
            
            if is_keyword_type:
                by_profile[profile_id]["keywords"].append({
                    "action_id": action['id'],
                    "keywordId": str(entity_info['keywordId']),
                    "live_bid": live_bid,
                    "new_bid": new_bid
                })
            else:
                by_profile[profile_id]["targets"].append({
                    "action_id": action['id'],
                    "targetId": str(entity_info['targetId']),
                    "live_bid": live_bid,
                    "new_bid": new_bid
                })
        
        for profile_id, data in by_profile.items():
            country_code = data["country_code"]
            api_url = "https://advertising-api.amazon.com" if country_code == 'US' else "https://advertising-api-eu.amazon.com"
            
            try:
                if data["targets"]:
                    print(f"[EXECUTE] Profile {profile_id}: updating {len(data['targets'])} targets")
                    api_payload = [{"targetId": t["targetId"], "bid": t["new_bid"]} for t in data["targets"]]
                    result = update_target_bids(access_token, profile_id, api_payload, api_url=api_url)
                    success_count = result.get("success", 0)
                    fail_count = result.get("failed", 0)
                    total_executed += success_count
                    total_failed += fail_count
                    
                    for t in data["targets"]:
                        if success_count > 0:
                            cur.execute("""
                                UPDATE planned_actions 
                                SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP, 
                                    current_bid = %s, new_bid = %s
                                WHERE id = %s
                            """, (t["live_bid"], t["new_bid"], t["action_id"]))
                        else:
                            error_msg = str(result.get("results", []))[:500]
                            cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", 
                                       (error_msg, t["action_id"]))
                
                if data["keywords"]:
                    print(f"[EXECUTE] Profile {profile_id}: updating {len(data['keywords'])} keywords")
                    api_payload = [{"keywordId": k["keywordId"], "bid": k["new_bid"]} for k in data["keywords"]]
                    result = update_keyword_bids(access_token, profile_id, api_payload, api_url=api_url)
                    success_count = result.get("success", 0)
                    fail_count = result.get("failed", 0)
                    total_executed += success_count
                    total_failed += fail_count
                    
                    for k in data["keywords"]:
                        if success_count > 0:
                            cur.execute("""
                                UPDATE planned_actions 
                                SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP, 
                                    current_bid = %s, new_bid = %s
                                WHERE id = %s
                            """, (k["live_bid"], k["new_bid"], k["action_id"]))
                        else:
                            error_msg = str(result.get("results", []))[:500]
                            cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", 
                                       (error_msg, k["action_id"]))
                            
            except Exception as e:
                error_msg = str(e)[:500]
                print(f"[EXECUTE ERROR] Profile {profile_id}: {error_msg}")
                for t in data["targets"]:
                    cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", (error_msg, t["action_id"]))
                    total_failed += 1
                for k in data["keywords"]:
                    cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", (error_msg, k["action_id"]))
                    total_failed += 1
        
        conn.commit()
        
        sb_executed_count = sb_executed
        sb_failed_count = sb_failed
        
        return {
            "status": "completed",
            "executed": total_executed,
            "paused": total_paused,
            "failed": total_failed,
            "skipped": skipped,
            "total": len(actions),
            "sp_count": len(sp_actions),
            "sb_count": len(sb_actions),
            "sp_paused": len(sp_pause_actions),
            "sb_paused": len(sb_pause_actions),
            "sb_executed": sb_executed_count,
            "sb_failed": sb_failed_count
        }
    except Exception as e:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _execute_sb_actions_sync(cur, sb_actions: list, access_token: str) -> tuple:
    """Execute SB actions using direct IDs. Synchronous version.
    
    Returns (executed_count, failed_count)
    """
    from backend.app.services.amazon_ads.update_bids import update_sb_keyword_bids, update_sb_target_bids
    
    if not sb_actions:
        return (0, 0)
    
    print(f"[EXECUTE-SB] Processing {len(sb_actions)} SB actions with direct IDs")
    
    by_profile = defaultdict(lambda: {"keywords": [], "targets": [], "country_code": "US"})
    skipped = 0
    
    for action in sb_actions:
        profile_id = str(action.get('profile_id', ''))
        keyword_id = action.get('keyword_id')
        ad_group_id = action.get('ad_group_id')
        target_type = action.get('target_type', 'keyword')
        current_bid = float(action.get('current_bid', 0) or 0)
        delta_bid = float(action.get('delta_bid', 0) or 0)
        country_code = action.get('country_code', 'US')
        
        if not keyword_id:
            skipped += 1
            cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", 
                       ("Missing keyword_id for SB action", action['id']))
            continue
        
        new_bid = max(0.02, round(current_bid + delta_bid, 2))
        by_profile[profile_id]["country_code"] = country_code
        
        if target_type == 'keyword':
            by_profile[profile_id]["keywords"].append({
                "action_id": action['id'],
                "keywordId": str(keyword_id),
                "adGroupId": str(ad_group_id) if ad_group_id else None,
                "bid": new_bid,
                "current_bid": current_bid
            })
        else:
            by_profile[profile_id]["targets"].append({
                "action_id": action['id'],
                "targetId": str(keyword_id),
                "adGroupId": str(ad_group_id) if ad_group_id else None,
                "bid": new_bid,
                "current_bid": current_bid
            })
    
    total_executed = 0
    total_failed = 0
    
    for profile_id, data in by_profile.items():
        country_code = data["country_code"]
        api_url = "https://advertising-api.amazon.com" if country_code == 'US' else "https://advertising-api-eu.amazon.com"
        
        try:
            if data["keywords"]:
                print(f"[EXECUTE-SB] Profile {profile_id}: updating {len(data['keywords'])} SB keywords")
                api_payload = [{"keywordId": k["keywordId"], "adGroupId": k["adGroupId"], "bid": k["bid"]} for k in data["keywords"]]
                result = update_sb_keyword_bids(access_token, profile_id, api_payload, api_url=api_url)
                success_count = result.get("success", 0)
                fail_count = result.get("failed", 0)
                total_executed += success_count
                total_failed += fail_count
                
                for i, k in enumerate(data["keywords"]):
                    if success_count > 0 and i < success_count:
                        cur.execute("""
                            UPDATE planned_actions 
                            SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP, 
                                new_bid = %s
                            WHERE id = %s
                        """, (k["bid"], k["action_id"]))
                    else:
                        error_msg = str(result.get("results", []))[:500]
                        cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", 
                                   (error_msg, k["action_id"]))
            
            if data["targets"]:
                print(f"[EXECUTE-SB] Profile {profile_id}: updating {len(data['targets'])} SB targets")
                api_payload = [{"targetId": t["targetId"], "adGroupId": t["adGroupId"], "bid": t["bid"]} for t in data["targets"]]
                result = update_sb_target_bids(access_token, profile_id, api_payload, api_url=api_url)
                success_count = result.get("success", 0)
                fail_count = result.get("failed", 0)
                total_executed += success_count
                total_failed += fail_count
                
                for i, t in enumerate(data["targets"]):
                    if success_count > 0 and i < success_count:
                        cur.execute("""
                            UPDATE planned_actions 
                            SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP, 
                                new_bid = %s
                            WHERE id = %s
                        """, (t["bid"], t["action_id"]))
                    else:
                        error_msg = str(result.get("results", []))[:500]
                        cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", 
                                   (error_msg, t["action_id"]))
                        
        except Exception as e:
            error_msg = str(e)[:500]
            print(f"[EXECUTE-SB ERROR] Profile {profile_id}: {error_msg}")
            for k in data["keywords"]:
                cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", (error_msg, k["action_id"]))
                total_failed += 1
            for t in data["targets"]:
                cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", (error_msg, t["action_id"]))
                total_failed += 1
    
    print(f"[EXECUTE-SB] Completed: {total_executed} executed, {total_failed} failed, {skipped} skipped")
    return (total_executed, total_failed)
