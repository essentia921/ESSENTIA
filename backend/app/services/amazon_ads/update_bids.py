# amazon_api/update_bids.py

import requests
import json
from backend.app.services.amazon_ads.config import API_BASE_URL, CLIENT_ID

BATCH_SIZE = 100


def get_target_bids_by_ids(access_token, profile_id, target_ids, api_url=None):
    """
    Recupera i bid attuali dei target tramite POST /adsApi/v1/query/targets.
    Usa l'endpoint corretto con header Amazon-Ads-ClientId.
    Restituisce un dict {targetId: {"bid": float, "targetType": str}}
    targetType può essere "KEYWORD" o "THEME" (automatiche)
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/adsApi/v1/query/targets"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Ads-ClientId": CLIENT_ID,
        "Amazon-Ads-CustomerId": str(profile_id),
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    result = {}
    
    print(f"\n=== GET TARGET BIDS: {len(target_ids)} targets ===")
    print(f"URL: {url}")
    print(f"Target IDs: {target_ids}")
    
    for i in range(0, len(target_ids), BATCH_SIZE):
        batch = target_ids[i:i + BATCH_SIZE]
        payload = {
            "adProductFilter": {"include": ["SPONSORED_PRODUCTS"]},
            "targetIdFilter": {"include": [str(tid) for tid in batch]},
            "stateFilter": {"include": ["ENABLED", "PAUSED"]},
            "maxResults": 1000
        }
        
        try:
            print(f"Payload: {json.dumps(payload)}")
            resp = requests.post(url, headers=headers, json=payload)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:1000] if resp.text else 'No response'}")
            
            if resp.status_code == 200:
                data = resp.json()
                targets_list = data.get("targets", [])
                print(f"Targets in response: {len(targets_list)}")
                for tgt in targets_list:
                    tid = tgt.get("targetId")
                    bid_obj = tgt.get("bid") or {}
                    bid = bid_obj.get("bid") if isinstance(bid_obj, dict) else bid_obj
                    target_type = tgt.get("targetType", "KEYWORD")
                    print(f"  Target {tid}: bid={bid}, targetType={target_type}")
                    if tid and bid is not None:
                        result[str(tid)] = {
                            "bid": float(bid),
                            "targetType": target_type
                        }
        except Exception as e:
            print(f"Error fetching target bids: {e}")
    
    print(f"Result: {result}")
    return result


def get_all_target_bids(access_token, profile_id, target_ids, api_url=None):
    """
    Recupera bid e targetType per tutti gli ID.
    Restituisce un dict {targetId: {"bid": float, "targetType": str}}
    """
    return get_target_bids_by_ids(access_token, profile_id, target_ids, api_url)


def update_keyword_bids(access_token, profile_id, keywords, api_url=None):
    """
    Aggiorna i bid delle keyword SP con batch processing.
    Usa l'endpoint PUT /sp/keywords della API v3.
    
    keywords: lista di dict con {keywordId, bid} dove bid è il nuovo valore numerico
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/sp/keywords"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Content-Type": "application/vnd.spKeyword.v3+json",
        "Accept": "application/vnd.spKeyword.v3+json"
    }

    updates = []
    for kw in keywords:
        kid = kw.get("keywordId")
        new_bid = kw.get("bid")
        if kid and new_bid is not None:
            updates.append({
                "keywordId": str(kid),
                "bid": round(new_bid, 2)
            })

    if not updates:
        return {"success": 0, "failed": 0, "batches": 0, "results": []}

    total_batches = (len(updates) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    success_count = 0
    failed_count = 0

    print(f"\n=== BATCH KEYWORD BID UPDATE: {len(updates)} keywords in {total_batches} batches ===")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(updates))
        batch = updates[start_idx:end_idx]

        print(f"\n--- Batch {batch_num + 1}/{total_batches}: {len(batch)} keywords ---")

        try:
            payload = {"keywords": batch}
            print(f"Payload: {json.dumps(payload, indent=2)}")
            resp = requests.put(url, headers=headers, json=payload)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:500] if resp.text else 'No response body'}")

            if resp.status_code in [200, 207]:
                result = resp.json()
                
                batch_success = 0
                batch_failed = 0
                failed_details = []
                
                # Amazon SP v3 response format: {"keywords": {"success": [...], "error": [...]}}
                keywords_result = result.get("keywords", {})
                
                if isinstance(keywords_result, dict):
                    # New format with success/error arrays
                    success_list = keywords_result.get("success", [])
                    error_list = keywords_result.get("error", [])
                    
                    batch_success = len(success_list)
                    batch_failed = len(error_list)
                    
                    for err in error_list:
                        errors = err.get("errors", [])
                        idx = err.get("index", 0)
                        for e in errors:
                            error_value = e.get("errorValue", {})
                            entity_error = error_value.get("entityNotFoundError", {}) or error_value
                            failed_details.append({
                                "keywordId": entity_error.get("entityId", f"index_{idx}"),
                                "code": e.get("errorType", "UNKNOWN"),
                                "message": entity_error.get("message", str(e))
                            })
                elif isinstance(keywords_result, list):
                    # Old format: array of results
                    for r in keywords_result:
                        code = r.get("code") or "SUCCESS"
                        if code in ["SUCCESS", "success", "200"]:
                            batch_success += 1
                        else:
                            batch_failed += 1
                            failed_details.append({
                                "keywordId": r.get("keywordId"),
                                "code": code,
                                "message": r.get("details")
                            })
                else:
                    # Fallback: assume all succeeded if no keywords in response
                    batch_success = len(batch)
                
                success_count += batch_success
                failed_count += batch_failed
                
                all_results.append({
                    "batch": batch_num + 1,
                    "status": "completed",
                    "sent": len(batch),
                    "success": batch_success,
                    "failed": batch_failed,
                    "failed_details": failed_details if failed_details else None
                })
            else:
                failed_count += len(batch)
                all_results.append({
                    "batch": batch_num + 1,
                    "status": "error",
                    "count": len(batch),
                    "http_status": resp.status_code,
                    "error": resp.text
                })
        except Exception as e:
            failed_count += len(batch)
            all_results.append({
                "batch": batch_num + 1,
                "status": "exception",
                "count": len(batch),
                "error": str(e)
            })

    print(f"\n=== BATCH KEYWORD UPDATE COMPLETE: {success_count} success, {failed_count} failed ===")

    return {
        "success": success_count,
        "failed": failed_count,
        "batches": total_batches,
        "total_keywords": len(updates),
        "results": all_results
    }


def update_target_bids(access_token, profile_id, targets, delta=None, api_url=None):
    """
    Aggiorna i bid dei target con batch processing.
    L'API Amazon accetta massimo 100 target per richiesta.
    
    Se delta è None, targets deve essere una lista di dict con {targetId, bid} già calcolati.
    Se delta è un numero, targets sono i target raw e il nuovo bid = bid + delta.
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/adsApi/v1/update/targets"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Ads-CustomerId": str(profile_id),
        "Amazon-Ads-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    updates = []
    
    if delta is None:
        for t in targets:
            tid = t.get("targetId")
            new_bid = t.get("bid")
            if tid and new_bid is not None:
                updates.append({
                    "targetId": tid,
                    "bid": {"bid": round(new_bid, 2)}
                })
    else:
        for t in targets:
            tid = t.get("targetId")
            bid_data = t.get("bid")
            if isinstance(bid_data, dict):
                old_bid = bid_data.get("bid")
            else:
                old_bid = bid_data

            if old_bid is None:
                continue

            new_bid = round(old_bid + delta, 2)
            if new_bid < 0.01:
                new_bid = 0.01

            updates.append({
                "targetId": tid,
                "bid": {"bid": new_bid}
            })

    if not updates:
        return {"success": 0, "failed": 0, "batches": 0, "results": []}

    total_batches = (len(updates) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    success_count = 0
    failed_count = 0

    print(f"\n=== BATCH TARGET BID UPDATE: {len(updates)} targets in {total_batches} batches ===")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(updates))
        batch = updates[start_idx:end_idx]

        payload = {"targets": batch}

        print(f"\n--- Batch {batch_num + 1}/{total_batches}: {len(batch)} targets ---")
        print(f"Payload: {json.dumps(payload, indent=2)}")

        try:
            resp = requests.post(url, headers=headers, json=payload)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:1000] if resp.text else 'No response body'}")

            if resp.status_code in [200, 207]:
                result = resp.json()
                
                batch_success = 0
                batch_failed = 0
                failed_details = []
                
                success_list = result.get("success", [])
                error_list = result.get("error", [])
                
                batch_success = len(success_list)
                batch_failed = len(error_list)
                
                for err in error_list:
                    errors = err.get("errors", [])
                    idx = err.get("index", 0)
                    for e in errors:
                        error_value = e.get("errorValue", {})
                        failed_details.append({
                            "targetId": error_value.get("entityId", f"index_{idx}"),
                            "code": e.get("errorType", "UNKNOWN"),
                            "message": error_value.get("message", str(e))
                        })
                
                if not success_list and not error_list:
                    batch_success = len(batch)
                
                success_count += batch_success
                failed_count += batch_failed
                
                all_results.append({
                    "batch": batch_num + 1,
                    "status": "completed",
                    "sent": len(batch),
                    "success": batch_success,
                    "failed": batch_failed,
                    "failed_details": failed_details if failed_details else None
                })
            else:
                failed_count += len(batch)
                all_results.append({
                    "batch": batch_num + 1,
                    "status": "error",
                    "count": len(batch),
                    "http_status": resp.status_code,
                    "error": resp.text
                })
        except Exception as e:
            failed_count += len(batch)
            all_results.append({
                "batch": batch_num + 1,
                "status": "exception",
                "count": len(batch),
                "error": str(e)
            })

    print(f"\n=== BATCH TARGET UPDATE COMPLETE: {success_count} success, {failed_count} failed ===")

    return {
        "success": success_count,
        "failed": failed_count,
        "batches": total_batches,
        "total_targets": len(updates),
        "results": all_results
    }


def update_sb_keyword_bids(access_token, profile_id, keywords, api_url=None):
    """
    Update Sponsored Brands keyword bids with batch processing.
    Uses PUT /sb/keywords endpoint with array format.
    
    DEFINITIVE FORMAT:
    - Payload: [{keywordId, adGroupId, bid}] (array diretto, NO wrapper)
    - Accept: */* (evita 406)
    - Content-Type: application/json
    - Uses json.dumps() with data= (NOT json=)
    
    keywords: list of dict with {keywordId, adGroupId, bid}
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/sb/keywords"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Accept": "*/*",
        "Content-Type": "application/json"
    }

    updates = []
    for kw in keywords:
        kid = kw.get("keywordId")
        ad_group_id = kw.get("adGroupId")
        new_bid = kw.get("bid")
        if kid and new_bid is not None:
            update_item = {
                "keywordId": int(kid) if isinstance(kid, str) and kid.isdigit() else kid,
                "bid": round(float(new_bid), 2)
            }
            if ad_group_id:
                update_item["adGroupId"] = int(ad_group_id) if isinstance(ad_group_id, str) and ad_group_id.isdigit() else ad_group_id
            updates.append(update_item)

    if not updates:
        return {"success": 0, "failed": 0, "batches": 0, "results": []}

    total_batches = (len(updates) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    success_count = 0
    failed_count = 0

    print(f"\n=== BATCH SB KEYWORD BID UPDATE: {len(updates)} keywords in {total_batches} batches ===")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(updates))
        batch = updates[start_idx:end_idx]

        print(f"\n--- SB Batch {batch_num + 1}/{total_batches}: {len(batch)} keywords ---")

        try:
            body = json.dumps(batch, separators=(",", ":"), ensure_ascii=False)
            print(f"Body: {body}")
            
            resp = requests.put(url, headers=headers, data=body, timeout=30)
            
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:500] if resp.text else 'No response body'}")

            if resp.status_code in [200, 207]:
                result = resp.json()
                
                batch_success = 0
                batch_failed = 0
                failed_details = []
                
                if isinstance(result, list):
                    for r in result:
                        code = r.get("code") or "SUCCESS"
                        if code in ["SUCCESS", "success", "200"] or r.get("keywordId"):
                            batch_success += 1
                        else:
                            batch_failed += 1
                            failed_details.append({
                                "keywordId": r.get("keywordId"),
                                "code": code,
                                "message": r.get("details")
                            })
                else:
                    success_list = result.get("success", [])
                    error_list = result.get("error", [])
                    batch_success = len(success_list) if success_list else len(batch)
                    batch_failed = len(error_list)
                    for err in error_list:
                        failed_details.append({
                            "keywordId": err.get("keywordId"),
                            "code": err.get("code", "UNKNOWN"),
                            "message": err.get("details", str(err))
                        })
                
                success_count += batch_success
                failed_count += batch_failed
                
                all_results.append({
                    "batch": batch_num + 1,
                    "status": "completed",
                    "sent": len(batch),
                    "success": batch_success,
                    "failed": batch_failed,
                    "failed_details": failed_details if failed_details else None
                })
            else:
                failed_count += len(batch)
                all_results.append({
                    "batch": batch_num + 1,
                    "status": "error",
                    "count": len(batch),
                    "http_status": resp.status_code,
                    "error": resp.text
                })
        except Exception as e:
            failed_count += len(batch)
            all_results.append({
                "batch": batch_num + 1,
                "status": "exception",
                "count": len(batch),
                "error": str(e)
            })

    print(f"\n=== BATCH SB KEYWORD UPDATE COMPLETE: {success_count} success, {failed_count} failed ===")

    return {
        "success": success_count,
        "failed": failed_count,
        "batches": total_batches,
        "total_keywords": len(updates),
        "results": all_results
    }


def update_sb_target_bids(access_token, profile_id, targets, api_url=None):
    """
    Update Sponsored Brands product targeting bids with batch processing.
    Uses PUT /sb/targets endpoint with wrapper format.
    
    DEFINITIVE FORMAT:
    - Payload: {"targets": [{targetId, adGroupId, bid}]} (WRAPPER, non array diretto!)
    - Accept: */* (evita 406)
    - Content-Type: application/json
    - Uses json.dumps() with data= (NOT json=)
    - NO state, NO campaignId
    
    targets: list of dict with {targetId, adGroupId, bid}
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/sb/targets"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Accept": "*/*",
        "Content-Type": "application/json"
    }

    updates = []
    for t in targets:
        tid = t.get("targetId")
        ad_group_id = t.get("adGroupId")
        new_bid = t.get("bid")
        if tid and new_bid is not None:
            update_item = {
                "targetId": int(tid) if isinstance(tid, str) and tid.isdigit() else tid,
                "bid": round(float(new_bid), 2)
            }
            if ad_group_id:
                update_item["adGroupId"] = int(ad_group_id) if isinstance(ad_group_id, str) and ad_group_id.isdigit() else ad_group_id
            updates.append(update_item)

    if not updates:
        return {"success": 0, "failed": 0, "batches": 0, "results": []}

    total_batches = (len(updates) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    success_count = 0
    failed_count = 0

    print(f"\n=== BATCH SB TARGET BID UPDATE: {len(updates)} targets in {total_batches} batches ===")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(updates))
        batch = updates[start_idx:end_idx]

        print(f"\n--- SB Batch {batch_num + 1}/{total_batches}: {len(batch)} targets ---")

        try:
            payload = {"targets": batch}
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
            print(f"Body: {body}")
            
            resp = requests.put(url, headers=headers, data=body, timeout=30)
            
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:1000] if resp.text else 'No response body'}")

            if resp.status_code in [200, 207]:
                result = resp.json()
                
                batch_success = 0
                batch_failed = 0
                failed_details = []
                
                targets_result = result.get("targets", result)
                
                if isinstance(targets_result, list):
                    for r in targets_result:
                        code = r.get("code") or "SUCCESS"
                        if code in ["SUCCESS", "success", "200"] or r.get("targetId"):
                            batch_success += 1
                        else:
                            batch_failed += 1
                            failed_details.append({
                                "targetId": r.get("targetId"),
                                "code": code,
                                "message": r.get("details")
                            })
                elif isinstance(targets_result, dict):
                    success_list = targets_result.get("success", [])
                    error_list = targets_result.get("error", [])
                    batch_success = len(success_list) if success_list else len(batch)
                    batch_failed = len(error_list)
                    for err in error_list:
                        failed_details.append({
                            "targetId": err.get("targetId"),
                            "code": err.get("code", "UNKNOWN"),
                            "message": err.get("details", str(err))
                        })
                else:
                    batch_success = len(batch)
                
                success_count += batch_success
                failed_count += batch_failed
                
                all_results.append({
                    "batch": batch_num + 1,
                    "status": "completed",
                    "sent": len(batch),
                    "success": batch_success,
                    "failed": batch_failed,
                    "failed_details": failed_details if failed_details else None
                })
            else:
                failed_count += len(batch)
                all_results.append({
                    "batch": batch_num + 1,
                    "status": "error",
                    "count": len(batch),
                    "http_status": resp.status_code,
                    "error": resp.text
                })
        except Exception as e:
            failed_count += len(batch)
            all_results.append({
                "batch": batch_num + 1,
                "status": "exception",
                "count": len(batch),
                "error": str(e)
            })

    print(f"\n=== BATCH SB TARGET UPDATE COMPLETE: {success_count} success, {failed_count} failed ===")

    return {
        "success": success_count,
        "failed": failed_count,
        "batches": total_batches,
        "total_targets": len(updates),
        "results": all_results
    }


def _parse_pause_response(result, batch, label=""):
    batch_success = 0
    batch_failed = 0
    error_details = []

    if isinstance(result, dict):
        success_results = (
            result.get("updateTargetSuccessResults") or
            result.get("updateKeywordSuccessResults") or
            result.get("success", [])
        )
        error_results = (
            result.get("updateTargetErrorResults") or
            result.get("updateKeywordErrorResults") or
            result.get("error", [])
        )
        keywords_wrapper = result.get("keywords", {})
        if isinstance(keywords_wrapper, dict) and (keywords_wrapper.get("success") or keywords_wrapper.get("error")):
            success_results = keywords_wrapper.get("success", [])
            error_results = keywords_wrapper.get("error", [])

        if isinstance(success_results, list):
            batch_success = len(success_results)
        if isinstance(error_results, list):
            batch_failed = len(error_results)
            for err in error_results:
                if isinstance(err, dict):
                    error_details.append(f"{err.get('code', 'UNKNOWN')}: {err.get('details', err.get('message', ''))}")

        if batch_success == 0 and batch_failed == 0:
            batch_success = len(batch)

    elif isinstance(result, list):
        for r in result:
            if isinstance(r, dict):
                code = r.get("code", "")
                if code in ["SUCCESS", ""] or (code is None and (r.get("keywordId") or r.get("targetId"))):
                    batch_success += 1
                else:
                    batch_failed += 1
                    error_details.append(f"{code}: {r.get('details', r.get('description', ''))}")

    if error_details:
        print(f"[{label}] Errors: {error_details}")

    return batch_success, batch_failed, error_details


def pause_sp_keywords(access_token, profile_id, keyword_ids, api_url=None):
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/sp/keywords"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Content-Type": "application/vnd.spKeyword.v3+json",
        "Accept": "application/vnd.spKeyword.v3+json"
    }

    updates = [{"keywordId": str(kid), "state": "PAUSED"} for kid in keyword_ids]
    if not updates:
        return {"success": 0, "failed": 0, "results": []}

    total_batches = (len(updates) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    success_count = 0
    failed_count = 0

    print(f"\n=== PAUSE SP KEYWORDS: {len(updates)} keywords in {total_batches} batches ===")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(updates))
        batch = updates[start_idx:end_idx]
        print(f"\n--- SP Pause KW Batch {batch_num + 1}/{total_batches}: {len(batch)} keywords ---")

        try:
            payload = {"keywords": batch}
            print(f"Payload: {json.dumps(payload)}")
            resp = requests.put(url, headers=headers, json=payload, timeout=30)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:1000] if resp.text else 'No response body'}")

            if resp.status_code in [200, 207]:
                result = resp.json()
                batch_success, batch_failed, _ = _parse_pause_response(result, batch, "SP_PAUSE_KW")
                success_count += batch_success
                failed_count += batch_failed
                all_results.append({"batch": batch_num + 1, "success": batch_success, "failed": batch_failed})
            else:
                failed_count += len(batch)
                all_results.append({"batch": batch_num + 1, "error": resp.text[:500], "status": resp.status_code})
        except Exception as e:
            print(f"Error pausing SP keywords: {e}")
            failed_count += len(batch)
            all_results.append({"batch": batch_num + 1, "error": str(e)})

    print(f"\n=== SP PAUSE KW COMPLETE: {success_count} success, {failed_count} failed ===")
    return {"success": success_count, "failed": failed_count, "results": all_results}


def pause_sp_targets(access_token, profile_id, target_ids, api_url=None):
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/sp/targets"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Content-Type": "application/vnd.spTargetingClause.v3+json",
        "Accept": "application/vnd.spTargetingClause.v3+json"
    }

    updates = [{"targetId": str(tid), "state": "PAUSED"} for tid in target_ids]
    if not updates:
        return {"success": 0, "failed": 0, "results": []}

    total_batches = (len(updates) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    success_count = 0
    failed_count = 0

    print(f"\n=== PAUSE SP TARGETS: {len(updates)} targets in {total_batches} batches ===")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(updates))
        batch = updates[start_idx:end_idx]
        print(f"\n--- SP Pause Target Batch {batch_num + 1}/{total_batches}: {len(batch)} targets ---")

        try:
            payload = {"targetingClauses": batch}
            print(f"Payload: {json.dumps(payload)}")
            resp = requests.put(url, headers=headers, json=payload, timeout=30)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:1000] if resp.text else 'No response body'}")

            if resp.status_code in [200, 207]:
                result = resp.json()
                batch_success, batch_failed, _ = _parse_pause_response(result, batch, "SP_PAUSE_TGT")
                success_count += batch_success
                failed_count += batch_failed
                all_results.append({"batch": batch_num + 1, "success": batch_success, "failed": batch_failed})
            elif resp.status_code in [400, 415, 406]:
                print(f"[SP_PAUSE_TGT] v3 format failed ({resp.status_code}), trying legacy array format...")
                headers_legacy = dict(headers)
                headers_legacy["Content-Type"] = "application/json"
                headers_legacy["Accept"] = "application/json"
                resp2 = requests.put(url, headers=headers_legacy, json=batch, timeout=30)
                print(f"Legacy Status: {resp2.status_code}")
                print(f"Legacy Response: {resp2.text[:1000] if resp2.text else 'No response body'}")
                if resp2.status_code in [200, 207]:
                    result = resp2.json()
                    batch_success, batch_failed, _ = _parse_pause_response(result, batch, "SP_PAUSE_TGT_LEGACY")
                    success_count += batch_success
                    failed_count += batch_failed
                    all_results.append({"batch": batch_num + 1, "success": batch_success, "failed": batch_failed})
                else:
                    failed_count += len(batch)
                    all_results.append({"batch": batch_num + 1, "error": resp2.text[:500], "status": resp2.status_code})
            else:
                failed_count += len(batch)
                all_results.append({"batch": batch_num + 1, "error": resp.text[:500], "status": resp.status_code})
        except Exception as e:
            print(f"Error pausing SP targets: {e}")
            failed_count += len(batch)
            all_results.append({"batch": batch_num + 1, "error": str(e)})

    print(f"\n=== SP PAUSE TARGET COMPLETE: {success_count} success, {failed_count} failed ===")
    return {"success": success_count, "failed": failed_count, "results": all_results}


def pause_sb_keywords(access_token, profile_id, keyword_ids=None, api_url=None, actions=None):
    """
    Pause SB keywords. Uses same format as working update_sb_keyword_bids:
    - PUT /sb/keywords
    - Array format (NO wrapper): [{keywordId, adGroupId, campaignId, state}]
    - Accept: */*
    - Content-Type: application/json
    - Uses json.dumps() with data= (NOT json=)
    
    Required fields per Amazon API docs: keywordId, adGroupId, campaignId
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/sb/keywords"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Accept": "*/*",
        "Content-Type": "application/json"
    }

    updates = []
    if actions:
        for a in actions:
            kid = a.get('keyword_id') or a.get('keywordId')
            agid = a.get('ad_group_id') or a.get('adGroupId')
            cid = a.get('campaign_id') or a.get('campaignId')
            if kid:
                entry = {
                    "keywordId": int(kid) if isinstance(kid, str) and kid.isdigit() else kid,
                    "state": "paused"
                }
                if agid:
                    entry["adGroupId"] = int(agid) if isinstance(agid, str) and str(agid).isdigit() else agid
                if cid:
                    entry["campaignId"] = int(cid) if isinstance(cid, str) and str(cid).isdigit() else cid
                updates.append(entry)
    elif keyword_ids:
        updates = [{"keywordId": int(kid) if isinstance(kid, str) and kid.isdigit() else kid, "state": "paused"} for kid in keyword_ids]

    if not updates:
        return {"success": 0, "failed": 0, "results": []}

    total_batches = (len(updates) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    success_count = 0
    failed_count = 0

    print(f"\n=== PAUSE SB KEYWORDS: {len(updates)} keywords in {total_batches} batches ===")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(updates))
        batch = updates[start_idx:end_idx]
        print(f"\n--- SB Pause KW Batch {batch_num + 1}/{total_batches}: {len(batch)} keywords ---")

        try:
            body = json.dumps(batch, separators=(",", ":"), ensure_ascii=False)
            print(f"Body: {body}")
            resp = requests.put(url, headers=headers, data=body, timeout=30)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:1000] if resp.text else 'No response body'}")

            if resp.status_code in [200, 207]:
                result = resp.json()
                batch_success, batch_failed, _ = _parse_pause_response(result, batch, "SB_PAUSE_KW")
                success_count += batch_success
                failed_count += batch_failed
                all_results.append({"batch": batch_num + 1, "success": batch_success, "failed": batch_failed})
            else:
                failed_count += len(batch)
                all_results.append({"batch": batch_num + 1, "error": resp.text[:500], "status": resp.status_code})
        except Exception as e:
            print(f"Error pausing SB keywords: {e}")
            failed_count += len(batch)
            all_results.append({"batch": batch_num + 1, "error": str(e)})

    print(f"\n=== SB PAUSE KW COMPLETE: {success_count} success, {failed_count} failed ===")
    return {"success": success_count, "failed": failed_count, "results": all_results}


def pause_sb_targets(access_token, profile_id, target_ids=None, api_url=None, actions=None):
    """
    Pause SB targets. Uses same format as working update_sb_target_bids:
    - PUT /sb/targets
    - Wrapper format: {"targets": [{targetId, adGroupId, state}]}
    - Accept: */*
    - Content-Type: application/json
    - Uses json.dumps() with data= (NOT json=)
    
    Required fields per Amazon API docs: targetId, adGroupId
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/sb/targets"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Accept": "*/*",
        "Content-Type": "application/json"
    }

    updates = []
    if actions:
        for a in actions:
            tid = a.get('keyword_id') or a.get('targetId') or a.get('target_id')
            agid = a.get('ad_group_id') or a.get('adGroupId')
            if tid:
                entry = {
                    "targetId": int(tid) if isinstance(tid, str) and str(tid).isdigit() else tid,
                    "state": "paused"
                }
                if agid:
                    entry["adGroupId"] = int(agid) if isinstance(agid, str) and str(agid).isdigit() else agid
                updates.append(entry)
    elif target_ids:
        updates = [{"targetId": int(tid) if isinstance(tid, str) and str(tid).isdigit() else tid, "state": "paused"} for tid in target_ids]

    if not updates:
        return {"success": 0, "failed": 0, "results": []}

    total_batches = (len(updates) + BATCH_SIZE - 1) // BATCH_SIZE
    all_results = []
    success_count = 0
    failed_count = 0

    print(f"\n=== PAUSE SB TARGETS: {len(updates)} targets in {total_batches} batches ===")

    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(updates))
        batch = updates[start_idx:end_idx]
        print(f"\n--- SB Pause Target Batch {batch_num + 1}/{total_batches}: {len(batch)} targets ---")

        try:
            payload = {"targets": batch}
            body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
            print(f"Body: {body}")
            resp = requests.put(url, headers=headers, data=body, timeout=30)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text[:1000] if resp.text else 'No response body'}")

            if resp.status_code in [200, 207]:
                result = resp.json()
                batch_success, batch_failed, _ = _parse_pause_response(result, batch, "SB_PAUSE_TGT")
                success_count += batch_success
                failed_count += batch_failed
                all_results.append({"batch": batch_num + 1, "success": batch_success, "failed": batch_failed})
            else:
                failed_count += len(batch)
                all_results.append({"batch": batch_num + 1, "error": resp.text[:500], "status": resp.status_code})
        except Exception as e:
            print(f"Error pausing SB targets: {e}")
            failed_count += len(batch)
            all_results.append({"batch": batch_num + 1, "error": str(e)})

    print(f"\n=== SB PAUSE TARGET COMPLETE: {success_count} success, {failed_count} failed ===")
    return {"success": success_count, "failed": failed_count, "results": all_results}
