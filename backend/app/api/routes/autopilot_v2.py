"""
Autopilot V2 Router - Simplified Autopilot Flow

Endpoints for:
1. Profile autopilot enable/disable
2. Sync pipeline (reports + Oxylab)
3. Runs and actions management
4. Execution reports
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import time
import uuid as _uuid
import threading as _threading

# --- Search Term Report Job Store (in-memory, single-worker) ---
_str_jobs: Dict[str, Any] = {}
_str_jobs_lock = _threading.Lock()


def _map_str_row(row: dict, item: dict) -> dict:
    impressions = int(row.get("impressions") or 0)
    clicks = int(row.get("clicks") or 0)
    cost = float(row.get("cost") or 0.0)
    purchases = int(row.get("purchases14d") or 0)
    sales = float(row.get("sales14d") or 0.0)
    units = int(row.get("unitsSoldClicks14d") or 0)
    raw_acos = row.get("acosClicks14d")
    raw_roas = row.get("roasClicks14d")
    raw_cpc = row.get("costPerClick")
    raw_ctr = row.get("clickThroughRate")
    raw_kenp = row.get("kindleEditionNormalizedPagesRead14d")
    raw_kenp_roy = row.get("kindleEditionNormalizedPagesRoyalties14d")
    return {
        "date": str(row.get("date") or ""),
        "marketplace": item["marketplace"],
        "profile_id": item["profile_id"],
        "campaign_id": str(row.get("campaignId") or ""),
        "campaign_name": str(row.get("campaignName") or ""),
        "ad_group_id": str(row.get("adGroupId") or ""),
        "ad_group_name": str(row.get("adGroupName") or ""),
        "keyword_id": str(row.get("keywordId") or ""),
        "keyword": str(row.get("keyword") or ""),
        "targeting": str(row.get("targeting") or ""),
        "match_type": str(row.get("matchType") or ""),
        "search_term": str(row.get("searchTerm") or ""),
        "impressions": impressions,
        "clicks": clicks,
        "cost": cost,
        "cost_per_click": float(raw_cpc) if raw_cpc is not None else None,
        "ctr": float(raw_ctr) if raw_ctr is not None else None,
        "purchases14d": purchases,
        "sales14d": sales,
        "units14d": units,
        "acos14d": float(raw_acos) if raw_acos is not None else None,
        "roas14d": float(raw_roas) if raw_roas is not None else None,
        "kenp_read14d": int(raw_kenp) if raw_kenp is not None else None,
        "kenp_royalties14d": float(raw_kenp_roy) if raw_kenp_roy is not None else None,
    }


def _str_poll_thread(job_id: str, account_id: int):
    """Background thread: polls all pending report items and stores results when ready."""
    import time as _t
    from backend.app.services.amazon_ads.report import check_report_status_once, download_report_gzip_json
    from backend.app.services.amazon import get_valid_access_token

    deadline = _t.time() + 1800  # 30 minuti max (report DAILY 30gg possono richiedere 15-20 min)
    poll_interval = 20  # secondi tra un giro di polling e il successivo

    while _t.time() < deadline:
        with _str_jobs_lock:
            job = _str_jobs.get(job_id)
            if not job or job["status"] != "RUNNING":
                return
            pending_items = [i for i in job["items"] if i["status"] == "PENDING"]

        if not pending_items:
            break

        access_token, _ = get_valid_access_token(account_id)
        if not access_token:
            _t.sleep(30)
            continue

        elapsed = int(_t.time() - (deadline - 1800))
        print(f"[STR-POLL] Job {job_id} — {elapsed}s — {len(pending_items)} report in attesa")

        for item in pending_items:
            if not item.get("report_id"):
                continue
            try:
                meta = check_report_status_once(
                    access_token=access_token,
                    profile_id=item["profile_id"],
                    report_id=item["report_id"],
                    api_url=item["api_url"],
                )
                amazon_status = meta.get("status")
                print(f"[STR-POLL]   {item['report_id'][:16]}… → {amazon_status}")
                with _str_jobs_lock:
                    for i in _str_jobs[job_id]["items"]:
                        if i["report_id"] == item["report_id"]:
                            i["amazon_status"] = amazon_status
                            if amazon_status in ("SUCCESS", "COMPLETED"):
                                i["status"] = "SUCCESS"
                                i["location"] = meta.get("location") or meta.get("url")
                            elif amazon_status in ("FAILURE", "CANCELLED", "FAILED"):
                                i["status"] = "FAILED"
                                i["error"] = f"Amazon status: {amazon_status}"
            except Exception as e:
                print(f"[STR-POLL] Errore poll {item.get('report_id','?')}: {e}")

        with _str_jobs_lock:
            all_done = all(i["status"] != "PENDING" for i in _str_jobs[job_id]["items"])

        if not all_done:
            _t.sleep(poll_interval)
            continue

        # Tutti completati — scarica i risultati
        access_token, _ = get_valid_access_token(account_id)
        all_rows = []
        with _str_jobs_lock:
            items_snapshot = list(_str_jobs[job_id]["items"])
        for item in items_snapshot:
            if item["status"] != "SUCCESS" or not item.get("location"):
                continue
            try:
                rows = download_report_gzip_json(item["location"])
                for row in rows:
                    all_rows.append(_map_str_row(row, item))
            except Exception as e:
                print(f"[STR-POLL] Errore download {item['report_id']}: {e}")

        with _str_jobs_lock:
            _str_jobs[job_id]["status"] = "DONE"
            _str_jobs[job_id]["rows"] = all_rows
            _str_jobs[job_id]["total_rows"] = len(all_rows)
        print(f"[STR-POLL] Job {job_id} completato — {len(all_rows)} righe")
        return

    with _str_jobs_lock:
        if _str_jobs.get(job_id, {}).get("status") == "RUNNING":
            _str_jobs[job_id]["status"] = "TIMEOUT"
            print(f"[STR-POLL] Job {job_id} timeout")


def _get_user_id_from_request(request: Request) -> int:
    from backend.app.core.security import decode_access_token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(payload.get("sub"))


DEFAULT_PROFILES_TEMPLATE = [
    {
        "name": "Default",
        "description": "Profilo standard bilanciato",
        "delta_excellent": 0.05, "delta_good": 0.02, "delta_above_be": -0.02,
        "delta_high": -0.05, "delta_low_impressions": 0.01, "delta_no_sales": -0.02,
        "low_impressions_threshold": 100, "min_spend_for_decrement": 1.00,
        "max_clicks_no_sales": 10, "max_clicks_for_low_impressions": 0,
        "pause_on_clicks_enabled": True, "is_default": True, "is_system": True
    },
    {
        "name": "Conservative",
        "description": "Modifiche graduali e conservative per ottimizzazione sicura",
        "delta_excellent": 0.01, "delta_good": 0.01, "delta_above_be": -0.01,
        "delta_high": -0.01, "delta_low_impressions": 0.01, "delta_no_sales": -0.01,
        "low_impressions_threshold": 100, "min_spend_for_decrement": 1.00,
        "max_clicks_no_sales": 10, "max_clicks_for_low_impressions": 0,
        "pause_on_clicks_enabled": True, "is_default": False, "is_system": True
    }
]


def _ensure_default_profiles(conn, user_id: int):
    """Ensure user has Default + Conservative system profiles. Uses its own cursor to avoid state issues."""
    import logging
    logger = logging.getLogger(__name__)
    from psycopg2.extras import RealDictCursor

    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            UPDATE autopilot_settings_profiles asp SET user_id = %s
            FROM client_accounts ca 
            WHERE asp.account_id = ca.id AND ca.user_id = %s AND asp.user_id IS NULL
        """, (user_id, user_id))
        migrated = cur.rowcount
        if migrated > 0:
            logger.info(f"Migrated {migrated} existing settings profiles to user_id={user_id}")

        cur.execute("SELECT name FROM autopilot_settings_profiles WHERE user_id = %s AND is_system = TRUE", (user_id,))
        existing_system = {row["name"] for row in cur.fetchall()}

        for tpl in DEFAULT_PROFILES_TEMPLATE:
            if tpl["name"] not in existing_system:
                cur.execute("""
                    INSERT INTO autopilot_settings_profiles 
                    (user_id, name, description, delta_excellent, delta_good, delta_above_be,
                     delta_high, delta_low_impressions, delta_no_sales, low_impressions_threshold,
                     min_spend_for_decrement, max_clicks_no_sales, max_clicks_for_low_impressions,
                     pause_on_clicks_enabled, is_default, is_system)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (user_id, tpl["name"], tpl["description"], tpl["delta_excellent"],
                      tpl["delta_good"], tpl["delta_above_be"], tpl["delta_high"],
                      tpl["delta_low_impressions"], tpl["delta_no_sales"],
                      tpl["low_impressions_threshold"], tpl["min_spend_for_decrement"],
                      tpl["max_clicks_no_sales"], tpl["max_clicks_for_low_impressions"],
                      tpl["pause_on_clicks_enabled"], False, tpl["is_system"]))
                logger.info(f"Created system profile '{tpl['name']}' for user_id={user_id}")

        cur.execute("""
            SELECT id FROM autopilot_settings_profiles 
            WHERE user_id = %s AND is_system = TRUE AND name = 'Default' LIMIT 1
        """, (user_id,))
        default_row = cur.fetchone()
        if default_row:
            default_sp_id = default_row["id"]
            cur.execute("""
                SELECT ca.id as account_id FROM client_accounts ca WHERE ca.user_id = %s
            """, (user_id,))
            user_accounts = [r["account_id"] for r in cur.fetchall()]
            for acc_id in user_accounts:
                cur.execute("""
                    UPDATE autopilot_profiles SET settings_profile_id = %s
                    WHERE account_id = %s AND settings_profile_id IS NULL
                """, (default_sp_id, acc_id))
                assigned = cur.rowcount
                if assigned > 0:
                    logger.info(f"Assigned Default settings profile to {assigned} marketplace profiles for account {acc_id}")

        conn.commit()
    except Exception as e:
        logger.error(f"Error in _ensure_default_profiles for user_id={user_id}: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()

_live_bids_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300

def get_cached_live_bids(profile_id: str, ad_product: str) -> Optional[Dict]:
    """Get cached live bids for a profile if not expired."""
    cache_key = f"{profile_id}_{ad_product}"
    if cache_key in _live_bids_cache:
        cached = _live_bids_cache[cache_key]
        if time.time() - cached["timestamp"] < CACHE_TTL_SECONDS:
            return cached["data"]
    return None

def set_cached_live_bids(profile_id: str, ad_product: str, data: Dict):
    """Cache live bids for a profile."""
    cache_key = f"{profile_id}_{ad_product}"
    _live_bids_cache[cache_key] = {"data": data, "timestamp": time.time()}

def clear_live_bids_cache(profile_id: str = None):
    """Clear cache for a profile or all profiles."""
    global _live_bids_cache
    if profile_id:
        keys_to_remove = [k for k in _live_bids_cache if k.startswith(f"{profile_id}_")]
        for k in keys_to_remove:
            del _live_bids_cache[k]
    else:
        _live_bids_cache = {}

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    return {
        "total_keys": len(_live_bids_cache),
        "keys": list(_live_bids_cache.keys()),
        "ttl_seconds": CACHE_TTL_SECONDS
    }

from db.accounts_db import (
    get_autopilot_profiles_for_account,
    upsert_autopilot_profile,
    get_books_for_profile,
    upsert_profile_book,
    get_book_metrics_for_profile,
    get_enabled_autopilot_profiles_due,
    get_all_client_accounts,
    get_client_tokens,
    get_client_profiles,
)

router = APIRouter()


class ExportRequest(BaseModel):
    password: str


@router.post("/export-tokens")
async def export_all_tokens(request: ExportRequest):
    """Export all tokens and profile IDs for all accounts. Password protected."""
    import os
    if request.password != "GIFT":
        raise HTTPException(status_code=403, detail="Invalid password")
    
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    accounts = get_all_client_accounts()
    result = []
    
    for account in accounts:
        account_id = account["id"]
        account_name = account.get("client_name", "Unknown")
        
        tokens = get_client_tokens(account_id)
        profiles = get_client_profiles(account_id)
        
        profile_list = []
        for p in profiles:
            profile_list.append({
                "profile_id": p.get("profile_id"),
                "country_code": p.get("country_code"),
                "marketplace": p.get("marketplace_string"),
                "api_url": p.get("api_url"),
            })
        
        result.append({
            "account_id": account_id,
            "account_name": account_name,
            "access_token": tokens.get("access_token") if tokens else None,
            "refresh_token": tokens.get("refresh_token") if tokens else None,
            "expires_at": str(tokens.get("expires_at")) if tokens and tokens.get("expires_at") else None,
            "profiles": profile_list,
        })
    
    return {"client_id": client_id, "accounts": result, "total": len(result)}


@router.get("/sb-test/keywords/{account_id}")
async def sb_test_keywords(account_id: int):
    """
    Test endpoint per scaricare SB Keywords.
    Step 1: Fetch profiles via /v2/profiles (no scope)
    Step 2: Use profile_id as scope for /sb/keywords
    Accept: */* to avoid 406 errors
    """
    import requests
    import os
    from db.accounts_db import get_client_tokens
    from backend.app.services.amazon import AmazonAdsService
    
    tokens = get_client_tokens(account_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=400, detail="No tokens found for this account")
    
    service = AmazonAdsService(tokens["access_token"], tokens["refresh_token"], account_id)
    try:
        new_access, new_refresh, expires = service.refresh_access_token()
        access_token = new_access
        token_refreshed = True
    except Exception as e:
        access_token = tokens["access_token"]
        token_refreshed = False
    
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    base_url = "https://advertising-api.amazon.com"
    
    step1_result = {}
    step2_result = {}
    profile_id = None
    
    profiles_url = f"{base_url}/v2/profiles"
    profiles_headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/json",
    }
    
    try:
        r1 = requests.get(profiles_url, headers=profiles_headers, timeout=30)
        step1_result = {
            "url": profiles_url,
            "status_code": r1.status_code,
            "headers_sent": {k: v for k, v in profiles_headers.items() if k != "Authorization"},
        }
        
        if r1.status_code == 200:
            profiles_data = r1.json()
            step1_result["profiles_count"] = len(profiles_data)
            step1_result["profiles"] = profiles_data
            
            us_profile = next((p for p in profiles_data if p.get("countryCode") == "US"), None)
            if us_profile:
                profile_id = us_profile.get("profileId")
                step1_result["selected_profile"] = us_profile
            elif profiles_data:
                profile_id = profiles_data[0].get("profileId")
                step1_result["selected_profile"] = profiles_data[0]
        else:
            step1_result["response_body"] = r1.text[:2000]
    except Exception as e:
        step1_result["error"] = str(e)
    
    if profile_id:
        sb_url = f"{base_url}/sb/keywords"
        sb_params = {"startIndex": 0, "count": 100, "stateFilter": "enabled"}
        sb_headers = {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Accept": "*/*",
        }
        
        try:
            r2 = requests.get(sb_url, headers=sb_headers, params=sb_params, timeout=30)
            step2_result = {
                "url": f"{sb_url}?startIndex=0&count=100&stateFilter=enabled",
                "status_code": r2.status_code,
                "headers_sent": {k: v for k, v in sb_headers.items() if k != "Authorization"},
                "response_body": r2.text[:3000] if len(r2.text) > 3000 else r2.text,
            }
            
            if r2.status_code == 200:
                try:
                    step2_result["response_json"] = r2.json()
                    step2_result["keywords_count"] = len(r2.json()) if isinstance(r2.json(), list) else 0
                except:
                    pass
        except Exception as e:
            step2_result["error"] = str(e)
    else:
        step2_result = {"skipped": True, "reason": "No profile_id found in step 1"}
    
    return {
        "account_id": account_id,
        "token_refreshed": token_refreshed,
        "access_token_preview": f"{access_token[:20]}...{access_token[-10:]}" if access_token else None,
        "profile_id_used": profile_id,
        "step1_profiles": step1_result,
        "step2_sb_keywords": step2_result
    }


@router.get("/sb-test/products/{account_id}")
async def sb_test_products(account_id: int):
    """
    Test endpoint per scaricare SB Product Targets.
    Step 1: Fetch profiles via /v2/profiles (no scope)
    Step 2: Use profile_id as scope for POST /sb/targets/list
    """
    import requests
    import os
    from db.accounts_db import get_client_tokens
    from backend.app.services.amazon import AmazonAdsService
    
    tokens = get_client_tokens(account_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=400, detail="No tokens found for this account")
    
    service = AmazonAdsService(tokens["access_token"], tokens["refresh_token"], account_id)
    try:
        new_access, new_refresh, expires = service.refresh_access_token()
        access_token = new_access
        token_refreshed = True
    except Exception as e:
        access_token = tokens["access_token"]
        token_refreshed = False
    
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    base_url = "https://advertising-api.amazon.com"
    
    step1_result = {}
    step2_result = {}
    profile_id = None
    
    profiles_url = f"{base_url}/v2/profiles"
    profiles_headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/json",
    }
    
    try:
        r1 = requests.get(profiles_url, headers=profiles_headers, timeout=30)
        step1_result = {
            "url": profiles_url,
            "status_code": r1.status_code,
            "headers_sent": {k: v for k, v in profiles_headers.items() if k != "Authorization"},
        }
        
        if r1.status_code == 200:
            profiles_data = r1.json()
            step1_result["profiles_count"] = len(profiles_data)
            step1_result["profiles"] = profiles_data
            
            us_profile = next((p for p in profiles_data if p.get("countryCode") == "US"), None)
            if us_profile:
                profile_id = us_profile.get("profileId")
                step1_result["selected_profile"] = us_profile
            elif profiles_data:
                profile_id = profiles_data[0].get("profileId")
                step1_result["selected_profile"] = profiles_data[0]
        else:
            step1_result["response_body"] = r1.text[:2000]
    except Exception as e:
        step1_result["error"] = str(e)
    
    if profile_id:
        sb_url = f"{base_url}/sb/targets/list"
        sb_headers = {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": client_id,
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Accept": "*/*",
            "Content-Type": "application/json",
        }
        sb_payload = {
            "maxResults": 1000
        }
        
        try:
            r2 = requests.post(sb_url, headers=sb_headers, json=sb_payload, timeout=30)
            step2_result = {
                "url": sb_url,
                "method": "POST",
                "status_code": r2.status_code,
                "headers_sent": {k: v for k, v in sb_headers.items() if k != "Authorization"},
                "payload_sent": sb_payload,
                "response_body": r2.text[:3000] if len(r2.text) > 3000 else r2.text,
            }
            
            if r2.status_code == 200:
                try:
                    json_data = r2.json()
                    step2_result["response_json"] = json_data
                    targets = json_data.get("targets", [])
                    step2_result["targets_count"] = len(targets)
                except:
                    pass
        except Exception as e:
            step2_result["error"] = str(e)
    else:
        step2_result = {"skipped": True, "reason": "No profile_id found in step 1"}
    
    return {
        "account_id": account_id,
        "token_refreshed": token_refreshed,
        "access_token_preview": f"{access_token[:20]}...{access_token[-10:]}" if access_token else None,
        "profile_id_used": profile_id,
        "step1_profiles": step1_result,
        "step2_sb_products": step2_result
    }


class SBKeywordBidUpdate(BaseModel):
    keyword_id: int
    ad_group_id: int
    new_bid: float
    profile_id: int


class SBTargetBidUpdate(BaseModel):
    target_id: int
    ad_group_id: int
    new_bid: float
    profile_id: int


@router.post("/sb-test/update-keyword-bid/{account_id}")
async def sb_test_update_keyword_bid(account_id: int, update: SBKeywordBidUpdate):
    """
    Test endpoint per aggiornare il bid di una SB Keyword.
    PUT /sb/keywords con array diretto [{ keywordId, bid }]
    """
    import requests
    import os
    from db.accounts_db import get_client_tokens
    from backend.app.services.amazon import AmazonAdsService
    
    tokens = get_client_tokens(account_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=400, detail="No tokens found for this account")
    
    service = AmazonAdsService(tokens["access_token"], tokens["refresh_token"], account_id)
    try:
        new_access, new_refresh, expires = service.refresh_access_token()
        access_token = new_access
        token_refreshed = True
    except Exception as e:
        access_token = tokens["access_token"]
        token_refreshed = False
    
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    base_url = "https://advertising-api.amazon.com"
    
    url = f"{base_url}/sb/keywords"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": client_id,
        "Amazon-Advertising-API-Scope": str(update.profile_id),
        "Accept": "*/*",
        "Content-Type": "application/json",
    }
    
    payload = [
        {
            "keywordId": update.keyword_id,
            "adGroupId": update.ad_group_id,
            "bid": round(update.new_bid, 2)
        }
    ]
    
    try:
        r = requests.put(url, headers=headers, json=payload, timeout=30)
        result = {
            "url": url,
            "method": "PUT",
            "status_code": r.status_code,
            "headers_sent": {k: v for k, v in headers.items() if k != "Authorization"},
            "payload_sent": payload,
            "response_body": r.text[:3000] if len(r.text) > 3000 else r.text,
        }
        
        if r.status_code in [200, 207]:
            try:
                result["response_json"] = r.json()
            except:
                pass
    except Exception as e:
        result = {"error": str(e)}
    
    return {
        "account_id": account_id,
        "token_refreshed": token_refreshed,
        "keyword_id": update.keyword_id,
        "new_bid": update.new_bid,
        "profile_id": update.profile_id,
        "result": result
    }


@router.post("/sb-test/update-target-bid/{account_id}")
async def sb_test_update_target_bid(account_id: int, update: SBTargetBidUpdate):
    """
    PUT /sb/targets - Array diretto [{ targetId, adGroupId, bid }]
    Tentativo 1: Content-Type: application/json
    Tentativo 2 (se 422): Content-Type: application/vnd.sbtargetingclause.v3+json
    Accept: */* sempre (evita 406)
    """
    import json
    import requests
    import os
    from db.accounts_db import get_client_tokens
    from backend.app.services.amazon import AmazonAdsService
    
    tokens = get_client_tokens(account_id)
    if not tokens or not tokens.get("access_token"):
        raise HTTPException(status_code=400, detail="No tokens found for this account")
    
    service = AmazonAdsService(tokens["access_token"], tokens["refresh_token"], account_id)
    try:
        new_access, new_refresh, expires = service.refresh_access_token()
        access_token = new_access
        token_refreshed = True
    except Exception as e:
        access_token = tokens["access_token"]
        token_refreshed = False
    
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = "https://advertising-api.amazon.com/sb/targets"
    
    payload = {
        "targets": [
            {
                "targetId": int(update.target_id),
                "adGroupId": int(update.ad_group_id),
                "bid": float(f"{update.new_bid:.2f}")
            }
        ]
    }
    
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": client_id,
        "Amazon-Advertising-API-Scope": str(update.profile_id),
        "Accept": "*/*",
        "Content-Type": "application/json",
    }
    
    try:
        r = requests.put(url, headers=headers, data=body, timeout=30)
        result = {
            "url": url,
            "body_sent": body,
            "status_code": r.status_code,
            "response": r.text[:2000]
        }
        if r.status_code in [200, 207]:
            try:
                result["response_json"] = r.json()
            except:
                pass
    except Exception as e:
        result = {"error": str(e)}
    
    return {
        "account_id": account_id,
        "token_refreshed": token_refreshed,
        "target_id": update.target_id,
        "ad_group_id": update.ad_group_id,
        "new_bid": update.new_bid,
        "profile_id": update.profile_id,
        "result": result
    }


class AutopilotProfileUpdate(BaseModel):
    profile_ids: List[str]
    enabled: bool
    cadence: str = "daily"


class ProfileBookAdd(BaseModel):
    asin: str
    title: Optional[str] = None
    marketplace: Optional[str] = None


class SyncRequest(BaseModel):
    account_id: int
    profile_ids: List[str]
    marketplaces: List[str] = ["US"]
    period_days: List[int] = [14, 30]


# ============================================
# Test Endpoints for API Debugging
# ============================================

@router.get("/test-sb-targets/{account_id}/{profile_id}")
async def test_sb_targets_api(account_id: int, profile_id: str):
    """Test endpoint to verify SB targets API call."""
    from db.accounts_db import get_client_tokens
    from backend.app.services.autopilot_sync_service import get_profile_api_url
    from backend.app.services.amazon import CLIENT_ID
    import requests
    
    try:
        token_data = get_client_tokens(account_id)
        if not token_data:
            return {"error": "No tokens found for account", "account_id": account_id}
        
        access_token = token_data.get("access_token")
        if not access_token:
            return {"error": "Invalid token data"}
        
        api_url = get_profile_api_url(profile_id)
        results = []
        
        endpoints = [
            ("POST", f"{api_url}/sb/targets/list", "application/json", {"maxResults": 5}),
            ("GET", f"{api_url}/sb/keywords", "application/json", None),
        ]
        
        for method, url, accept_header, payload in endpoints:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Amazon-Advertising-API-Scope": str(profile_id),
                "Amazon-Advertising-API-ClientId": CLIENT_ID,
                "Accept": accept_header,
                "Content-Type": "application/json",
            }
            try:
                if method == "POST":
                    resp = requests.post(url, headers=headers, json=payload, timeout=30)
                else:
                    resp = requests.get(url, headers=headers, params={"count": 5}, timeout=30)
                results.append({
                    "endpoint": url.split("/")[-1],
                    "method": method,
                    "status": resp.status_code,
                    "response": resp.text[:500] if resp.text else None
                })
            except Exception as e:
                results.append({"endpoint": url, "error": str(e)})
        
        return {"profile_id": profile_id, "api_url": api_url, "tests": results}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@router.post("/test-sb-report/{account_id}/{profile_id}")
async def test_sb_report_api(account_id: int, profile_id: str):
    """Test endpoint to create SB report."""
    from db.accounts_db import get_client_tokens
    from backend.app.services.autopilot_sync_service import get_profile_api_url
    from backend.app.services.amazon_reports import create_report, get_date_range
    
    try:
        token_data = get_client_tokens(account_id)
        if not token_data:
            return {"error": "No tokens found for account", "account_id": account_id}
        
        access_token = token_data.get("access_token")
        if not access_token:
            return {"error": "Invalid token data"}
        
        api_url = get_profile_api_url(profile_id)
        start_date, end_date = get_date_range(30)
        
        report_id = create_report(
            access_token=access_token,
            profile_id=profile_id,
            api_url=api_url,
            report_type="SB_TARGETING_30D",
            start_date=start_date,
            end_date=end_date,
            ad_product="SB"
        )
        
        return {
            "success": True,
            "profile_id": profile_id,
            "api_url": api_url,
            "report_id": report_id,
            "start_date": start_date,
            "end_date": end_date
        }
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


# ============================================
# Quick SB Bid Test Endpoints (hardcoded for rapid testing)
# ============================================

TEST_SB_KEYWORD = {
    "profile_id": "2870680072270358",
    "campaign_id": 489845741101592,
    "ad_group_id": 544822444097359,
    "keyword_id": 376124940669417,
    "keyword_text": "5 lb",
    "match_type": "BROAD",
}

TEST_SB_PRODUCT_TARGET = {
    "profile_id": "2870680072270358",
    "campaign_id": 457778383367689,
    "ad_group_id": 123456789012345,
    "target_id": 469629330335462,
    "expression": "asin=\"B08XXXXXXX\"",
}


@router.post("/test-sb-bid/{account_id}/{test_type}")
async def test_sb_bid_update(account_id: int, test_type: str):
    """
    Quick test endpoint for SB bid updates.
    test_type: 'keyword' or 'product'
    Increases bid by 0.01 each time.
    """
    from db.accounts_db import get_client_tokens
    from backend.app.services.autopilot_sync_service import get_profile_api_url
    from backend.app.services.amazon import AmazonAdsService
    
    try:
        token_data = get_client_tokens(account_id)
        if not token_data:
            return {"error": "No tokens found for account", "account_id": account_id}
        
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        if not access_token:
            return {"error": "Invalid token data"}
        
        if test_type == "keyword":
            test_data = TEST_SB_KEYWORD
            profile_id = test_data["profile_id"]
            api_url = get_profile_api_url(profile_id)
            
            service = AmazonAdsService(access_token, refresh_token, account_id)
            service.profile_id = profile_id
            service.api_url = api_url
            
            sb_targets = service.get_sb_targets(profile_id, api_url)
            sb_keywords = [t for t in sb_targets if t.get("_sb_type") == "keyword"]
            
            current_bid = None
            for kw in sb_keywords:
                if str(kw.get("keywordId")) == str(test_data["keyword_id"]):
                    current_bid = kw.get("bid")
                    break
            
            if current_bid is None:
                return {
                    "error": f"Keyword {test_data['keyword_id']} not found in fetched keywords",
                    "fetched_count": len(sb_keywords),
                    "sample_keywords": sb_keywords[:3] if sb_keywords else []
                }
            
            new_bid = round(current_bid + 0.01, 2)
            result = service.update_sb_keyword_bid(str(test_data["keyword_id"]), new_bid, api_url)
            
            response = {
                "test_type": "SB_KEYWORD",
                "keyword_id": test_data["keyword_id"],
                "keyword_text": test_data["keyword_text"],
                "current_bid": current_bid,
                "new_bid": new_bid,
                "result": result,
                "api_url": api_url
            }
            import json
            response["copy_json"] = json.dumps(response, indent=2, default=str)
            return response
        
        elif test_type == "product":
            test_data = TEST_SB_PRODUCT_TARGET
            profile_id = test_data["profile_id"]
            api_url = get_profile_api_url(profile_id)
            
            service = AmazonAdsService(access_token, refresh_token, account_id)
            service.profile_id = profile_id
            service.api_url = api_url
            
            sb_targets = service.get_sb_targets(profile_id, api_url)
            sb_products = [t for t in sb_targets if t.get("_sb_type") == "product_target"]
            
            current_bid = None
            for t in sb_products:
                if str(t.get("targetId")) == str(test_data["target_id"]):
                    current_bid = t.get("bid")
                    break
            
            if current_bid is None:
                return {
                    "error": f"Target {test_data['target_id']} not found in fetched targets",
                    "fetched_count": len(sb_products),
                    "sample_targets": sb_products[:3] if sb_products else []
                }
            
            new_bid = round(current_bid + 0.01, 2)
            result = service.update_sb_target_bid(str(test_data["target_id"]), new_bid, api_url)
            
            response = {
                "test_type": "SB_PRODUCT_TARGET",
                "target_id": test_data["target_id"],
                "expression": test_data["expression"],
                "current_bid": current_bid,
                "new_bid": new_bid,
                "result": result,
                "api_url": api_url
            }
            import json
            response["copy_json"] = json.dumps(response, indent=2, default=str)
            return response
        
        else:
            return {"error": f"Unknown test_type: {test_type}. Use 'keyword' or 'product'"}
    
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


# ============================================
# Profile Autopilot Management
# ============================================

@router.get("/profiles/{account_id}")
async def get_profiles_autopilot_status(account_id: int, request: Request):
    """Get autopilot status for all profiles of an account."""
    from db.accounts_db import get_profiles_for_account, get_connection
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        try:
            user_id = _get_user_id_from_request(request)
            conn = get_connection()
            try:
                _ensure_default_profiles(conn, user_id)
            finally:
                conn.close()
        except HTTPException:
            pass
        except Exception as e:
            logger.warning(f"Could not ensure default profiles for account {account_id}: {e}")
        
        all_profiles = get_profiles_for_account(account_id)
        autopilot_profiles = get_autopilot_profiles_for_account(account_id)
        
        autopilot_map = {ap['profile_id']: ap for ap in autopilot_profiles}
        
        result = []
        for p in all_profiles:
            profile_id = p.get('profile_id')
            ap = autopilot_map.get(profile_id, {})
            result.append({
                "profile_id": profile_id,
                "country_code": p.get('country_code'),
                "marketplace": p.get('marketplace_string'),
                "enabled": ap.get('enabled', False),
                "cadence": ap.get('cadence', 'daily'),
                "next_run_at": ap.get('next_run_at'),
                "last_run_at": ap.get('last_run_at'),
                "settings_profile_id": ap.get('settings_profile_id'),
            })
        
        return {"profiles": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profiles/{account_id}")
async def update_profiles_autopilot(account_id: int, data: AutopilotProfileUpdate):
    """Enable or disable autopilot for profiles. When disabling, cleans up PLANNED actions."""
    from db.accounts_db import get_connection
    
    conn = None
    try:
        updated = []
        for profile_id in data.profile_ids:
            result = upsert_autopilot_profile(
                account_id=account_id,
                profile_id=profile_id,
                enabled=data.enabled,
                cadence=data.cadence
            )
            if result:
                updated.append(result)
        
        if not data.enabled and data.profile_ids:
            conn = get_connection()
            cur = conn.cursor()
            for profile_id in data.profile_ids:
                cur.execute("""
                    DELETE FROM planned_actions 
                    WHERE profile_id = %s AND status = 'PLANNED'
                """, (profile_id,))
                deleted = cur.rowcount
                print(f"[AUTOPILOT] Disabled profile {profile_id}: deleted {deleted} PLANNED actions")
            
            cur.execute("""
                SELECT COUNT(*) FROM autopilot_profiles 
                WHERE account_id = %s AND enabled = TRUE
            """, (account_id,))
            active_count = cur.fetchone()[0]
            
            if active_count == 0:
                cur.execute("""
                    UPDATE big_bang_jobs 
                    SET status = 'CANCELLED', phase_status = 'cancelled', 
                        phase_message = 'Annullato: autopilot disattivato'
                    WHERE account_id = %s AND status IN ('RUNNING', 'SCHEDULED', 'WAITING', 'EXECUTING')
                """, (account_id,))
                cancelled_jobs = cur.rowcount
                if cancelled_jobs > 0:
                    print(f"[AUTOPILOT] Disabled all profiles for account {account_id}: cancelled {cancelled_jobs} active jobs")
            
            conn.commit()
            cur.close()
        
        return {"updated": len(updated), "profiles": updated}
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


# ============================================
# Books Management
# ============================================

@router.get("/profiles/{profile_id}/books")
async def get_profile_books(profile_id: str):
    """Get all books for a profile with economics data."""
    try:
        books = get_books_for_profile(profile_id)
        metrics = get_book_metrics_for_profile(profile_id)
        
        metrics_map = {m['asin']: m for m in metrics}
        
        result = []
        for book in books:
            asin = book.get('asin')
            m = metrics_map.get(asin, {})
            marketplace = book.get('marketplace', 'US')
            domain_map = {'US': 'com', 'UK': 'co.uk', 'GB': 'co.uk', 'IT': 'it', 'DE': 'de', 'FR': 'fr', 'ES': 'es'}
            domain = domain_map.get(marketplace, 'com')
            amazon_url = f"https://www.amazon.{domain}/dp/{asin}"
            
            result.append({
                "asin": asin,
                "title": book.get('title'),
                "author": book.get('author'),
                "image_url": book.get('image_url'),
                "amazon_url": amazon_url,
                "marketplace": marketplace,
                "price": float(book.get('price')) if book.get('price') is not None else None,
                "royalty_net": float(book.get('royalty_net')) if book.get('royalty_net') is not None else None,
                "acos_be": float(book.get('acos_be')) if book.get('acos_be') is not None else None,
                "acos_opt": float(book.get('acos_opt')) if book.get('acos_opt') is not None else None,
                "spend": float(m.get('spend')) if m.get('spend') is not None else None,
                "sales": float(m.get('sales')) if m.get('sales') is not None else None,
                "orders": m.get('orders'),
                "clicks": m.get('clicks'),
                "impressions": m.get('impressions'),
                "acos_actual": float(m.get('acos')) if m.get('acos') is not None else None,
            })
        
        return {"books": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profiles/{profile_id}/books")
async def add_profile_book(profile_id: str, book: ProfileBookAdd):
    """Add a book to a profile."""
    try:
        result = upsert_profile_book(
            profile_id=profile_id,
            asin=book.asin,
            title=book.title,
            marketplace=book.marketplace
        )
        return {"book": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profiles/{profile_id}/books/import")
async def import_profile_books(profile_id: str, asins: List[str]):
    """Import multiple ASINs for a profile."""
    try:
        imported = []
        for asin in asins:
            result = upsert_profile_book(profile_id=profile_id, asin=asin.strip())
            if result:
                imported.append(result)
        
        return {"imported": len(imported), "books": imported}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Sync Pipeline
# ============================================

@router.post("/refresh/{account_id}")
async def start_full_refresh(account_id: int):
    """Start complete data refresh for account (economics + reports)."""
    try:
        from backend.app.services.autopilot_sync_service import start_sync_job_async, get_latest_sync_job
        
        existing = get_latest_sync_job(account_id)
        if existing and existing.get('status') == 'RUNNING':
            return {
                "status": "already_running",
                "job_id": existing['id'],
                "message": "Un sync è già in corso per questo account"
            }
        
        job_id = start_sync_job_async(account_id)
        
        return {
            "status": "started",
            "job_id": job_id,
            "message": "Sync avviato per tutti i profili US/UK/IT"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync-status/{account_id}")
async def get_sync_status(account_id: int):
    """Get current sync job status for account."""
    try:
        from backend.app.services.autopilot_sync_service import get_latest_sync_job
        
        job = get_latest_sync_job(account_id)
        
        if not job:
            return {
                "has_job": False,
                "status": None,
                "message": "Nessun sync eseguito"
            }
        
        return {
            "has_job": True,
            "job_id": job['id'],
            "status": job['status'],
            "phase": job['phase'],
            "progress_pct": job['progress_pct'],
            "message": job['message'],
            "total_asins": job['total_asins'],
            "completed_asins": job['completed_asins'],
            "total_reports": job['total_reports'],
            "completed_reports": job['completed_reports'],
            "started_at": job['started_at'],
            "completed_at": job['completed_at'],
            "error": job['error'],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def start_sync(data: SyncRequest):
    """Start sync pipeline for profiles (legacy endpoint)."""
    try:
        from backend.app.services.autopilot_sync_service import start_sync_job_async
        
        job_id = start_sync_job_async(data.account_id)
        
        return {
            "status": "started",
            "job_id": job_id,
            "message": f"Sync avviato per account {data.account_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiles/{profile_id}/report-status")
async def get_profile_report_status(profile_id: str):
    """Get report status for a specific profile."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT report_id, report_type, start_date, end_date, status, created_at, completed_at
            FROM amazon_reports 
            WHERE profile_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (profile_id,))
        
        reports = cur.fetchall()
        cur.close()
        conn.close()
        
        pending = sum(1 for r in reports if r['status'] == 'PENDING')
        completed = sum(1 for r in reports if r['status'] == 'COMPLETED')
        failed = sum(1 for r in reports if r['status'] == 'FAILED')
        
        return {
            "profile_id": profile_id,
            "summary": {
                "pending": pending,
                "completed": completed,
                "failed": failed,
                "total": len(reports)
            },
            "reports": [
                {
                    "report_id": r['report_id'],
                    "type": r['report_type'],
                    "start_date": str(r['start_date']),
                    "end_date": str(r['end_date']),
                    "status": r['status'],
                    "created_at": r['created_at'].isoformat() if r['created_at'] else None,
                    "completed_at": r['completed_at'].isoformat() if r['completed_at'] else None,
                }
                for r in reports
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Report Management
# ============================================

@router.get("/accounts/{account_id}/reports")
async def get_account_reports(account_id: int, limit: int = 50):
    """Get all reports for an account with full details."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT r.report_id, r.profile_id, r.report_type, r.start_date, r.end_date, 
                   r.status, r.created_at, r.completed_at, r.ad_product,
                   p.country_code as marketplace,
                   r.report_data IS NOT NULL as has_data
            FROM amazon_reports r
            LEFT JOIN client_profiles p ON r.profile_id = p.profile_id
            WHERE r.account_id = %s
            ORDER BY r.created_at DESC
            LIMIT %s
        """, (account_id, limit))
        
        reports = cur.fetchall()
        cur.close()
        conn.close()
        
        by_profile = {}
        for r in reports:
            pid = r['profile_id']
            if pid not in by_profile:
                by_profile[pid] = {
                    "profile_id": pid,
                    "marketplace": r['marketplace'] or 'US',
                    "reports": [],
                    "summary": {"pending": 0, "completed": 0, "failed": 0, "parsed": 0, "total": 0}
                }
            
            by_profile[pid]["summary"]["total"] += 1
            status = r['status']
            if status == 'PENDING':
                by_profile[pid]["summary"]["pending"] += 1
            elif status == 'COMPLETED':
                by_profile[pid]["summary"]["completed"] += 1
            elif status == 'PARSED':
                by_profile[pid]["summary"]["parsed"] += 1
            elif status == 'FAILED':
                by_profile[pid]["summary"]["failed"] += 1
            
            period_days = (r['end_date'] - r['start_date']).days + 1 if r['start_date'] and r['end_date'] else 14
            
            by_profile[pid]["reports"].append({
                "report_id": r['report_id'],
                "ad_product": r.get('ad_product', 'SP'),
                "type": r['report_type'],
                "period_days": period_days,
                "status": status,
                "has_data": bool(r.get('has_data')),
                "created_at": r['created_at'].isoformat() if r['created_at'] else None,
                "completed_at": r['completed_at'].isoformat() if r['completed_at'] else None,
            })
        
        return {
            "account_id": account_id,
            "profiles": list(by_profile.values()),
            "total_reports": len(reports)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/reports/{report_id}/download")
async def download_report(account_id: int, report_id: str):
    """Download report data as JSON file. Requires account ownership verification."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    from fastapi.responses import JSONResponse
    import json
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT report_id, report_type, profile_id, start_date, end_date, 
                   status, report_data, account_id
            FROM amazon_reports 
            WHERE report_id = %s AND account_id = %s
        """, (report_id, account_id))
        
        report = cur.fetchone()
        cur.close()
        conn.close()
        
        if not report:
            raise HTTPException(status_code=404, detail="Report not found or access denied")
        
        if not report.get('report_data'):
            raise HTTPException(status_code=404, detail="Report data not available. Report may still be pending or failed.")
        
        report_data = report['report_data']
        if isinstance(report_data, str):
            report_data = json.loads(report_data)
        if isinstance(report_data, list) and len(report_data) > 0 and isinstance(report_data[0], list):
            report_data = report_data[0]
        
        filename = f"report_{report['profile_id']}_{report['start_date']}_{report['end_date']}.json"
        
        return JSONResponse(
            content={
                "report_id": report['report_id'],
                "report_type": report['report_type'],
                "profile_id": report['profile_id'],
                "start_date": str(report['start_date']),
                "end_date": str(report['end_date']),
                "status": report['status'],
                "rows_count": len(report_data) if isinstance(report_data, list) else 0,
                "data": report_data
            },
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/{account_id}/poll-reports")
async def poll_pending_reports(account_id: int):
    """Poll all PENDING reports for an account - checks status ONCE per report (non-blocking)."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    from backend.app.services.autopilot_sync_service import get_access_token, get_profile_api_url, update_report_status
    from backend.app.services.amazon_ads.report import check_report_status_once, download_report_gzip_json
    import logging
    import sys
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(message)s')
    logger = logging.getLogger("autopilot.poll")
    logger.setLevel(logging.INFO)
    
    try:
        access_token = get_access_token(account_id)
        logger.info(f"[POLL] Account {account_id}: Got access token: {bool(access_token)}")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token for account")
        
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT report_id, profile_id, ad_product 
            FROM amazon_reports 
            WHERE account_id = %s AND status = 'PENDING'
            ORDER BY created_at ASC
        """, (account_id,))
        
        pending_reports = cur.fetchall()
        cur.close()
        conn.close()
        
        logger.info(f"[POLL] Account {account_id}: Found {len(pending_reports)} pending reports")
        
        results = []
        for report in pending_reports:
            report_id = report['report_id']
            profile_id = report['profile_id']
            ad_product = report.get('ad_product', 'SP')
            api_url = get_profile_api_url(profile_id)
            
            logger.info(f"[POLL] Checking {ad_product} report {report_id[:12]}... profile={profile_id}, api_url={api_url}")
            
            try:
                data = check_report_status_once(access_token, profile_id, report_id, api_url)
                amazon_status = data.get("status")
                logger.info(f"[POLL] {ad_product} report {report_id[:12]}... Amazon response: status={amazon_status}, url={bool(data.get('url'))}")
                
                if amazon_status in ("SUCCESS", "COMPLETED"):
                    location = data.get("url")
                    if location:
                        logger.info(f"[POLL] {ad_product} report {report_id[:12]}... Downloading from URL")
                        rows = download_report_gzip_json(location)
                        update_report_status(report_id, 'COMPLETED', rows)
                        logger.info(f"[POLL] {ad_product} report {report_id[:12]}... COMPLETED with {len(rows) if rows else 0} rows")
                        results.append({
                            "report_id": report_id,
                            "profile_id": profile_id,
                            "ad_product": ad_product,
                            "status": "COMPLETED",
                            "rows_count": len(rows) if rows else 0
                        })
                    else:
                        results.append({
                            "report_id": report_id,
                            "profile_id": profile_id,
                            "ad_product": ad_product,
                            "status": "PENDING",
                            "message": "SUCCESS but no URL yet"
                        })
                elif amazon_status in ("FAILURE", "CANCELLED"):
                    update_report_status(report_id, 'FAILED')
                    logger.warning(f"[POLL] {ad_product} report {report_id[:12]}... FAILED: {amazon_status}")
                    results.append({
                        "report_id": report_id,
                        "profile_id": profile_id,
                        "ad_product": ad_product,
                        "status": "FAILED",
                        "message": f"Amazon status: {amazon_status}"
                    })
                else:
                    results.append({
                        "report_id": report_id,
                        "profile_id": profile_id,
                        "ad_product": ad_product,
                        "status": "PENDING",
                        "message": f"Still processing: {amazon_status}"
                    })
            except Exception as e:
                logger.error(f"[POLL] {ad_product} report {report_id[:12]}... ERROR: {str(e)}")
                results.append({
                    "report_id": report_id,
                    "profile_id": profile_id,
                    "ad_product": ad_product,
                    "status": "ERROR",
                    "error": str(e)
                })
        
        return {
            "polled_count": len(pending_reports),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Planned Actions
# ============================================

@router.get("/actions/{profile_id}")
async def get_planned_actions(profile_id: str, status: str = None):
    """Get planned actions for a profile."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT * FROM planned_actions WHERE profile_id = %s"
        params = [profile_id]
        
        if status:
            query += " AND status = %s"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        cur.execute(query, params)
        actions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        summary = {
            'total': len(actions),
            'planned': len([a for a in actions if a['status'] == 'PLANNED']),
            'executed': len([a for a in actions if a['status'] == 'EXECUTED']),
            'failed': len([a for a in actions if a['status'] == 'FAILED']),
            'increases': len([a for a in actions if (a.get('delta_bid') or 0) > 0]),
            'decreases': len([a for a in actions if (a.get('delta_bid') or 0) < 0]),
        }
        
        return {
            "profile_id": profile_id,
            "actions": [dict(a) for a in actions],
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/account/{account_id}")
async def get_account_actions(account_id: int, status: str = 'PLANNED', limit: int = 100, offset: int = 0, ad_product: str = None, sort_by: str = None, sort_dir: str = 'asc', filter_campaign: str = None, filter_target_type: str = None, filter_reason: str = None, filter_ad_product: str = None):
    """Get planned actions for an account with pagination and server-side sorting."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    ALLOWED_SORT_COLUMNS = {
        'keyword': 'pa.keyword',
        'campaign_name': 'pa.campaign_name',
        'target_type': 'pa.target_type',
        'current_bid': 'pa.current_bid',
        'delta_bid': 'pa.delta_bid',
        'new_bid': 'pa.new_bid',
        'acos_30d': 'pa.acos_30d',
        'acos_be': 'pa.acos_be',
        'impressions_30d': 'pa.impressions_30d',
        'clicks': 'pa.clicks',
        'purchases_30d': 'pa.purchases_30d',
        'reason': 'pa.reason',
        'ad_product': 'pa.ad_product',
        'created_at': 'pa.created_at',
    }
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        where_clauses = ["pa.account_id = %s", "pa.status = %s"]
        params = [account_id, status]
        
        effective_ad_product = filter_ad_product or ad_product
        if effective_ad_product:
            where_clauses.append("pa.ad_product = %s")
            params.append(effective_ad_product)
        
        if filter_campaign:
            where_clauses.append("pa.campaign_name = %s")
            params.append(filter_campaign)
        
        if filter_target_type:
            where_clauses.append("pa.target_type = %s")
            params.append(filter_target_type)
        
        if filter_reason:
            where_clauses.append("pa.reason = %s")
            params.append(filter_reason)
        
        where_sql = " AND ".join(where_clauses)
        
        cur.execute(f"SELECT COUNT(*) AS total_count FROM planned_actions pa WHERE {where_sql}", params)
        count_row = cur.fetchone()
        total_count = count_row['total_count'] if count_row else 0
        
        sort_column = ALLOWED_SORT_COLUMNS.get(sort_by, 'pa.created_at')
        sort_direction = 'DESC' if sort_dir.lower() == 'desc' else 'ASC'
        
        query = f"""
            SELECT pa.*, cp.country_code AS marketplace, ca.client_name AS account_name
            FROM planned_actions pa
            LEFT JOIN client_profiles cp ON pa.profile_id = cp.profile_id AND pa.account_id = cp.client_account_id
            LEFT JOIN client_accounts ca ON pa.account_id = ca.id
            WHERE {where_sql}
            ORDER BY {sort_column} {sort_direction} NULLS LAST
            LIMIT %s OFFSET %s
        """
        query_params = params + [limit, offset]
        
        cur.execute(query, query_params)
        actions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        by_profile = {}
        for action in actions:
            pid = action['profile_id']
            if pid not in by_profile:
                by_profile[pid] = []
            by_profile[pid].append(dict(action))
        
        return {
            "account_id": account_id,
            "total_actions": total_count,
            "returned_count": len(actions),
            "offset": offset,
            "limit": limit,
            "has_more": (offset + len(actions)) < total_count,
            "by_profile": by_profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/account/{account_id}/filters")
async def get_actions_filters(account_id: int, status: str = 'PLANNED'):
    """Get unique filter values for actions (campaigns, target types, ad products)."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT DISTINCT campaign_name FROM planned_actions pa
            WHERE pa.account_id = %s AND pa.status = %s
            AND campaign_name IS NOT NULL AND campaign_name != ''
            ORDER BY campaign_name
        """, (account_id, status))
        campaigns = [row['campaign_name'] for row in cur.fetchall()]
        
        cur.execute("""
            SELECT DISTINCT target_type FROM planned_actions pa
            WHERE pa.account_id = %s AND pa.status = %s
            AND target_type IS NOT NULL AND target_type != ''
            ORDER BY target_type
        """, (account_id, status))
        target_types = [row['target_type'] for row in cur.fetchall()]
        
        cur.execute("""
            SELECT DISTINCT ad_product FROM planned_actions pa
            WHERE pa.account_id = %s AND pa.status = %s
            AND ad_product IS NOT NULL
            ORDER BY ad_product
        """, (account_id, status))
        ad_products = [row['ad_product'] for row in cur.fetchall()]
        
        cur.execute("""
            SELECT DISTINCT reason FROM planned_actions pa
            WHERE pa.account_id = %s AND pa.status = %s
            AND reason IS NOT NULL AND reason != ''
            ORDER BY reason
        """, (account_id, status))
        reasons = [row['reason'] for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return {
            "campaigns": campaigns,
            "target_types": target_types,
            "ad_products": ad_products,
            "reasons": reasons
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/actions/account/{account_id}")
async def clear_planned_actions(account_id: int):
    """Clear all PLANNED actions for an account."""
    from db.accounts_db import get_connection
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM planned_actions 
            WHERE account_id = %s AND status = 'PLANNED'
        """, (account_id,))
        
        deleted_count = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Cancellate {deleted_count} azioni pianificate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/accounts/{account_id}/reports")
async def delete_account_reports(account_id: int):
    """Delete all reports for an account."""
    from db.accounts_db import delete_reports_for_account
    
    try:
        deleted_count = delete_reports_for_account(account_id)
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Eliminati {deleted_count} report"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions/account/{account_id}/export-xlsx")
async def export_actions_xlsx(account_id: int, status: str = None):
    """Export actions for an account as XLSX file.
    
    Args:
        account_id: Account ID
        status: Filter by status (PLANNED, EXECUTED, FAILED, or None for all)
    """
    from fastapi.responses import StreamingResponse
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    import pandas as pd
    import io
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                pa.id,
                pa.profile_id,
                pa.ad_product,
                pa.campaign_name,
                pa.keyword,
                pa.asin,
                pa.target_type,
                pa.current_bid,
                pa.new_bid,
                pa.delta_bid,
                pa.acos_30d,
                pa.acos_be,
                pa.reason,
                pa.status,
                pa.created_at,
                pa.executed_at,
                pa.error_message,
                pa.spend,
                pa.sales,
                pa.clicks,
                pa.orders,
                pa.impressions_30d,
                pa.marketplace
            FROM planned_actions pa
            WHERE pa.account_id = %s
        """
        params = [account_id]
        
        if status:
            query += " AND pa.status = %s"
            params.append(status)
        
        query += " ORDER BY pa.executed_at DESC NULLS LAST, pa.created_at DESC"
        
        cur.execute(query, params)
        actions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        if not actions:
            raise HTTPException(status_code=404, detail="Nessuna azione trovata")
        
        df = pd.DataFrame([dict(a) for a in actions])
        
        column_order = [
            'id', 'profile_id', 'ad_product', 'marketplace', 'campaign_name', 
            'keyword', 'asin', 'target_type', 'current_bid', 'new_bid', 'delta_bid',
            'acos_30d', 'acos_be', 'spend', 'sales', 'clicks', 'orders', 
            'impressions_30d', 'reason', 'status', 'created_at', 'executed_at', 'error_message'
        ]
        existing_cols = [c for c in column_order if c in df.columns]
        df = df[existing_cols]
        
        column_names = {
            'id': 'ID',
            'profile_id': 'Profile ID',
            'ad_product': 'Tipo (SP/SB)',
            'marketplace': 'Marketplace',
            'campaign_name': 'Campagna',
            'keyword': 'Keyword/Target',
            'asin': 'ASIN',
            'target_type': 'Tipo Target',
            'current_bid': 'Bid Attuale',
            'new_bid': 'Nuovo Bid',
            'delta_bid': 'Delta',
            'acos_30d': 'ACOS 30D',
            'acos_be': 'ACOS BE',
            'spend': 'Spesa',
            'sales': 'Vendite',
            'clicks': 'Click',
            'orders': 'Ordini',
            'impressions_30d': 'Impressioni 30D',
            'reason': 'Motivo',
            'status': 'Stato',
            'created_at': 'Data Creazione',
            'executed_at': 'Data Esecuzione',
            'error_message': 'Errore'
        }
        df.rename(columns=column_names, inplace=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Azioni')
        output.seek(0)
        
        status_suffix = f"_{status}" if status else ""
        filename = f"azioni_account_{account_id}{status_suffix}.xlsx"
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/big-bang-jobs/{job_id}/export-xlsx")
async def export_job_xlsx(job_id: int, export_type: str = "PLANNED"):
    """Export planned or executed actions for a specific big bang job as XLSX.
    
    Actions are matched by account_id and created_at within job's time window.
    Results are cached in job_exports table for permanent access.
    """
    from fastapi.responses import StreamingResponse
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    import pandas as pd
    import io
    
    if export_type not in ('PLANNED', 'EXECUTED'):
        raise HTTPException(status_code=400, detail="export_type must be PLANNED or EXECUTED")
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT * FROM job_exports WHERE big_bang_job_id = %s AND export_type = %s ORDER BY created_at DESC LIMIT 1", (job_id, export_type))
        cached = cur.fetchone()
        if cached:
            cur.close()
            conn.close()
            output = io.BytesIO(bytes(cached['file_data']))
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={cached['filename']}"}
            )
        
        cur.execute("SELECT * FROM big_bang_jobs WHERE id = %s", (job_id,))
        job = cur.fetchone()
        if not job:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Job non trovato")
        
        account_id = job['account_id']
        created_at = job['created_at']
        completed_at = job.get('last_completed_at') or job.get('updated_at') or job.get('executed_at')
        
        if not completed_at:
            from datetime import datetime, timedelta
            completed_at = datetime.utcnow()
        
        status_filter = 'PLANNED' if export_type == 'PLANNED' else 'EXECUTED'
        
        query = """
            SELECT 
                pa.id, pa.profile_id, pa.ad_product, pa.marketplace,
                pa.campaign_name, pa.keyword, pa.asin, pa.target_type,
                pa.current_bid, pa.new_bid, pa.delta_bid,
                pa.acos_30d, pa.acos_be, pa.spend, pa.sales,
                pa.clicks, pa.orders, pa.impressions_30d,
                pa.reason, pa.status, pa.created_at, pa.executed_at, pa.error_message
            FROM planned_actions pa
            WHERE pa.account_id = %s 
              AND pa.status = %s
              AND pa.created_at >= %s
              AND pa.created_at <= %s
            ORDER BY pa.created_at DESC
        """
        cur.execute(query, [account_id, status_filter, created_at, completed_at])
        actions = cur.fetchall()
        
        if not actions:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"Nessuna azione {export_type} trovata per questo job")
        
        df = pd.DataFrame([dict(a) for a in actions])
        
        column_names = {
            'id': 'ID', 'profile_id': 'Profile ID', 'ad_product': 'Tipo',
            'marketplace': 'Marketplace', 'campaign_name': 'Campagna',
            'keyword': 'Keyword/Target', 'asin': 'ASIN', 'target_type': 'Tipo Target',
            'current_bid': 'Bid Attuale', 'new_bid': 'Nuovo Bid', 'delta_bid': 'Delta',
            'acos_30d': 'ACOS 30D', 'acos_be': 'ACOS BE', 'spend': 'Spesa',
            'sales': 'Vendite', 'clicks': 'Click', 'orders': 'Ordini',
            'impressions_30d': 'Impressioni 30D', 'reason': 'Motivo',
            'status': 'Stato', 'created_at': 'Data Creazione',
            'executed_at': 'Data Esecuzione', 'error_message': 'Errore'
        }
        df.rename(columns=column_names, inplace=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Azioni')
        output.seek(0)
        file_bytes = output.getvalue()
        
        ad_prod = job.get('ad_product', 'ALL')
        job_date = created_at.strftime('%Y%m%d_%H%M') if created_at else 'unknown'
        filename = f"job_{job_id}_{ad_prod}_{export_type}_{job_date}.xlsx"
        
        cur.execute(
            "INSERT INTO job_exports (big_bang_job_id, account_id, export_type, file_data, filename, rows_count) VALUES (%s, %s, %s, %s, %s, %s)",
            (job_id, account_id, export_type, file_bytes, filename, len(actions))
        )
        conn.commit()
        cur.close()
        conn.close()
        
        output = io.BytesIO(file_bytes)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[EXPORT XLSX ERROR] job_id={job_id}, export_type={export_type}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/big-bang-jobs/{job_id}/export-info")
async def get_job_export_info(job_id: int):
    """Check what exports are available for a job."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT export_type, rows_count, filename, created_at 
            FROM job_exports 
            WHERE big_bang_job_id = %s 
            ORDER BY export_type
        """, (job_id,))
        exports = cur.fetchall()
        
        cur.execute("SELECT * FROM big_bang_jobs WHERE id = %s", (job_id,))
        job = cur.fetchone()
        
        planned_count = 0
        executed_count = 0
        if job:
            account_id = job['account_id']
            created_at = job['created_at']
            completed_at = job.get('last_completed_at') or job.get('updated_at') or job.get('executed_at')
            if created_at:
                from datetime import datetime
                if not completed_at:
                    completed_at = datetime.utcnow()
                cur.execute("SELECT COUNT(*) as cnt FROM planned_actions WHERE account_id = %s AND status = 'PLANNED' AND created_at >= %s AND created_at <= %s", (account_id, created_at, completed_at))
                planned_count = cur.fetchone()['cnt']
                cur.execute("SELECT COUNT(*) as cnt FROM planned_actions WHERE account_id = %s AND status = 'EXECUTED' AND created_at >= %s AND created_at <= %s", (account_id, created_at, completed_at))
                executed_count = cur.fetchone()['cnt']
        
        cur.close()
        conn.close()
        
        return {
            "job_id": job_id,
            "cached_exports": [dict(e) for e in exports],
            "planned_count": planned_count,
            "executed_count": executed_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/export-campaigns")
async def export_campaigns_csv(account_id: int):
    """Export all campaigns and ad groups for an account as CSV."""
    from fastapi.responses import StreamingResponse
    from backend.app.services.amazon import get_valid_access_token, AmazonAdsService
    from db.accounts_db import get_client_account, get_client_profiles
    import csv
    import io
    
    try:
        account = get_client_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account non trovato")
        
        account_name = account.get('client_name', f'Account {account_id}')
        
        from db.accounts_db import get_client_tokens
        
        tokens = get_client_tokens(account_id)
        if not tokens or not tokens.get('access_token'):
            raise HTTPException(status_code=400, detail='Token non disponibile')
        
        access_token = tokens['access_token']
        refresh_token = tokens.get('refresh_token', '')
        
        profiles = get_client_profiles(account_id)
        profiles = [p for p in profiles if p.get('country_code') in ('US', 'UK', 'IT')]
        
        service = AmazonAdsService(access_token, refresh_token, account_id)
        
        rows = []
        
        for profile in profiles:
            profile_id = str(profile.get('profile_id'))
            country_code = profile.get('country_code', '')
            marketplace = profile.get('marketplace_string') or country_code
            api_url = profile.get('api_url', 'https://advertising-api.amazon.com')
            
            for ad_product in ['SP', 'SB']:
                try:
                    if ad_product == 'SP':
                        campaigns = fetch_sp_campaigns_all_states(service, profile_id, api_url)
                        ad_groups = fetch_sp_ad_groups_all(service, profile_id, api_url)
                    else:
                        campaigns = fetch_sb_campaigns_all_states(service, profile_id, api_url)
                        ad_groups = fetch_sb_ad_groups_all(service, profile_id, api_url)
                    
                    campaign_map = {c['campaignId']: c for c in campaigns}
                    
                    for ag in ad_groups:
                        campaign_id = str(ag.get('campaignId', ''))
                        campaign = campaign_map.get(campaign_id, {})
                        
                        rows.append({
                            'account_id': account_id,
                            'account_name': account_name,
                            'profile_id': profile_id,
                            'marketplace': marketplace,
                            'campaign_id': campaign_id,
                            'campaign_name': campaign.get('name', ''),
                            'campaign_state': campaign.get('state', ''),
                            'ad_group_id': str(ag.get('adGroupId', '')),
                            'ad_group_name': ag.get('name', ''),
                            'ad_group_state': ag.get('state', ''),
                            'ad_product': ad_product,
                        })
                    
                    for c in campaigns:
                        campaign_id = str(c.get('campaignId', ''))
                        has_ad_groups = any(str(ag.get('campaignId', '')) == campaign_id for ag in ad_groups)
                        if not has_ad_groups:
                            rows.append({
                                'account_id': account_id,
                                'account_name': account_name,
                                'profile_id': profile_id,
                                'marketplace': marketplace,
                                'campaign_id': campaign_id,
                                'campaign_name': c.get('name', ''),
                                'campaign_state': c.get('state', ''),
                                'ad_group_id': '',
                                'ad_group_name': '',
                                'ad_group_state': '',
                                'ad_product': ad_product,
                            })
                except Exception as e:
                    print(f"[EXPORT] Error fetching {ad_product} for profile {profile_id}: {e}")
                    continue
        
        import json
        output = json.dumps(rows, indent=2, ensure_ascii=False)
        
        return StreamingResponse(
            iter([output]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=campaigns_account_{account_id}.json"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def fetch_sp_campaigns_all_states(service: 'AmazonAdsService', profile_id: str, api_url: str) -> list:
    """Fetch all SP campaigns with all states."""
    import os
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = f"{api_url}/sp/campaigns/list"
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/vnd.spcampaign.v3+json",
        "Content-Type": "application/vnd.spcampaign.v3+json",
    }
    payload = {"maxResults": 1000}
    
    try:
        response = service._make_request(url, headers, method="POST", json_data=payload)
        return response.json().get("campaigns", [])
    except Exception as e:
        print(f"[EXPORT] SP campaigns error: {e}")
        return []


def fetch_sp_ad_groups_all(service: 'AmazonAdsService', profile_id: str, api_url: str) -> list:
    """Fetch all SP ad groups."""
    import os
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = f"{api_url}/sp/adGroups/list"
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/vnd.spAdGroup.v3+json",
        "Content-Type": "application/vnd.spAdGroup.v3+json",
    }
    payload = {"maxResults": 1000}
    
    try:
        response = service._make_request(url, headers, method="POST", json_data=payload)
        return response.json().get("adGroups", [])
    except Exception as e:
        print(f"[EXPORT] SP ad groups error: {e}")
        return []


def fetch_sb_campaigns_all_states(service: 'AmazonAdsService', profile_id: str, api_url: str) -> list:
    """Fetch all SB campaigns with all states (with pagination)."""
    import os
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = f"{api_url}/sb/v4/campaigns/list"
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/vnd.sbcampaignresource.v4+json",
        "Content-Type": "application/vnd.sbcampaignresource.v4+json",
    }
    
    all_campaigns = []
    next_token = None
    
    while True:
        payload = {"maxResults": 100}
        if next_token:
            payload["nextToken"] = next_token
        
        try:
            response = service._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            all_campaigns.extend(data.get("campaigns", []))
            next_token = data.get("nextToken")
            if not next_token:
                break
        except Exception as e:
            print(f"[EXPORT] SB campaigns error: {e}")
            break
    
    return all_campaigns


def fetch_sb_ad_groups_all(service: 'AmazonAdsService', profile_id: str, api_url: str) -> list:
    """Fetch all SB ad groups (with pagination)."""
    import os
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = f"{api_url}/sb/v4/adGroups/list"
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/vnd.sbadgroupresource.v4+json",
        "Content-Type": "application/vnd.sbadgroupresource.v4+json",
    }
    
    all_ad_groups = []
    next_token = None
    
    while True:
        payload = {"maxResults": 100}
        if next_token:
            payload["nextToken"] = next_token
        
        try:
            response = service._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            all_ad_groups.extend(data.get("adGroups", []))
            next_token = data.get("nextToken")
            if not next_token:
                break
        except Exception as e:
            print(f"[EXPORT] SB ad groups error: {e}")
            break
    
    return all_ad_groups


def fetch_sp_keywords_all(service: 'AmazonAdsService', profile_id: str, api_url: str) -> list:
    """Fetch all SP keywords with all states."""
    import os
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = f"{api_url}/sp/keywords/list"
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/vnd.spKeyword.v3+json",
        "Content-Type": "application/vnd.spKeyword.v3+json",
    }
    
    all_keywords = []
    next_token = None
    
    while True:
        payload = {"maxResults": 1000}
        if next_token:
            payload["nextToken"] = next_token
        
        try:
            response = service._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            all_keywords.extend(data.get("keywords", []))
            next_token = data.get("nextToken")
            if not next_token:
                break
        except Exception as e:
            print(f"[EXPORT] SP keywords error: {e}")
            break
    
    return all_keywords


def fetch_sp_targets_all(service: 'AmazonAdsService', profile_id: str, api_url: str) -> list:
    """Fetch all SP targets with all states."""
    import os
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = f"{api_url}/sp/targets/list"
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/vnd.spTargetingClause.v3+json",
        "Content-Type": "application/vnd.spTargetingClause.v3+json",
    }
    
    all_targets = []
    next_token = None
    
    while True:
        payload = {"maxResults": 1000}
        if next_token:
            payload["nextToken"] = next_token
        
        try:
            response = service._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            all_targets.extend(data.get("targetingClauses", []))
            next_token = data.get("nextToken")
            if not next_token:
                break
        except Exception as e:
            print(f"[EXPORT] SP targets error: {e}")
            break
    
    return all_targets


def fetch_sb_keywords_all(service: 'AmazonAdsService', profile_id: str, api_url: str) -> list:
    """Fetch all SB keywords with all states."""
    import os
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = f"{api_url}/sb/keywords"
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/vnd.sbkeyword.v3.2+json",
    }
    
    try:
        response = service._make_request(url, headers, method="GET")
        return response.json() if isinstance(response.json(), list) else []
    except Exception as e:
        print(f"[EXPORT] SB keywords error: {e}")
        return []


def fetch_sb_targets_all(service: 'AmazonAdsService', profile_id: str, api_url: str) -> list:
    """Fetch all SB targets with all states (with pagination)."""
    import os
    client_id = os.getenv("AMAZON_ADS_CLIENT_ID")
    url = f"{api_url}/sb/targets/list"
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": client_id,
        "Accept": "application/vnd.sblisttargetsresponse.v3.2+json",
        "Content-Type": "application/json",
    }
    
    all_targets = []
    next_token = None
    
    while True:
        payload = {"maxResults": 100}
        if next_token:
            payload["nextToken"] = next_token
        
        try:
            response = service._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            targets = data.get("targets", []) if isinstance(data, dict) else []
            all_targets.extend(targets)
            next_token = data.get("nextToken")
            if not next_token:
                break
        except Exception as e:
            print(f"[EXPORT] SB targets error: {e}")
            break
    
    return all_targets


@router.get("/accounts/{account_id}/export-targets")
async def export_targets_json(account_id: int):
    """Export all targets (keywords + product targets) for an account as JSON."""
    from fastapi.responses import StreamingResponse
    from backend.app.services.amazon import AmazonAdsService
    from db.accounts_db import get_client_account, get_client_profiles, get_client_tokens
    import json
    
    try:
        account = get_client_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account non trovato")
        
        account_name = account.get('client_name', f'Account {account_id}')
        
        tokens = get_client_tokens(account_id)
        if not tokens or not tokens.get('access_token'):
            raise HTTPException(status_code=400, detail='Token non disponibile')
        
        access_token = tokens['access_token']
        refresh_token = tokens.get('refresh_token', '')
        
        profiles = get_client_profiles(account_id)
        profiles = [p for p in profiles if p.get('country_code') in ('US', 'UK', 'IT')]
        
        service = AmazonAdsService(access_token, refresh_token, account_id)
        
        campaigns_data = []
        
        for profile in profiles:
            profile_id = str(profile.get('profile_id'))
            country_code = profile.get('country_code', '')
            marketplace = profile.get('marketplace_string') or country_code
            api_url = profile.get('api_url', 'https://advertising-api.amazon.com')
            
            for ad_product in ['SP', 'SB']:
                try:
                    if ad_product == 'SP':
                        campaigns = fetch_sp_campaigns_all_states(service, profile_id, api_url)
                        keywords = fetch_sp_keywords_all(service, profile_id, api_url)
                        targets = fetch_sp_targets_all(service, profile_id, api_url)
                    else:
                        campaigns = fetch_sb_campaigns_all_states(service, profile_id, api_url)
                        keywords = fetch_sb_keywords_all(service, profile_id, api_url)
                        targets = fetch_sb_targets_all(service, profile_id, api_url)
                    
                    for campaign in campaigns:
                        campaign_id = str(campaign.get('campaignId', ''))
                        campaign_name = campaign.get('name', '')
                        campaign_state = campaign.get('state', '')
                        
                        campaign_keywords = [k for k in keywords if str(k.get('campaignId', '')) == campaign_id]
                        campaign_targets = [t for t in targets if str(t.get('campaignId', '')) == campaign_id]
                        
                        all_targets = []
                        
                        for kw in campaign_keywords:
                            state = kw.get('state', '')
                            all_targets.append({
                                'type': 'keyword',
                                'id': str(kw.get('keywordId', '')),
                                'text': kw.get('keywordText', ''),
                                'match_type': kw.get('matchType', ''),
                                'bid': kw.get('bid', 0),
                                'state': state,
                                'ad_group_id': str(kw.get('adGroupId', '')),
                            })
                        
                        for tgt in campaign_targets:
                            state = tgt.get('state', '')
                            expression = tgt.get('expression', [])
                            expr_str = ''
                            if expression and len(expression) > 0:
                                expr_str = expression[0].get('value', '') if isinstance(expression[0], dict) else str(expression[0])
                            
                            all_targets.append({
                                'type': 'target',
                                'id': str(tgt.get('targetId', '')),
                                'expression': expr_str,
                                'resolved_expression': tgt.get('resolvedExpression', []),
                                'bid': tgt.get('bid', 0),
                                'state': state,
                                'ad_group_id': str(tgt.get('adGroupId', '')),
                            })
                        
                        enabled_count = sum(1 for t in all_targets if t['state'] == 'ENABLED')
                        paused_count = sum(1 for t in all_targets if t['state'] == 'PAUSED')
                        archived_count = sum(1 for t in all_targets if t['state'] == 'ARCHIVED')
                        
                        campaigns_data.append({
                            'account_id': account_id,
                            'account_name': account_name,
                            'profile_id': profile_id,
                            'marketplace': marketplace,
                            'ad_product': ad_product,
                            'campaign_id': campaign_id,
                            'campaign_name': campaign_name,
                            'campaign_state': campaign_state,
                            'summary': {
                                'total': len(all_targets),
                                'enabled': enabled_count,
                                'paused': paused_count,
                                'archived': archived_count,
                            },
                            'targets': all_targets,
                        })
                        
                except Exception as e:
                    print(f"[EXPORT-TARGETS] Error fetching {ad_product} for profile {profile_id}: {e}")
                    continue
        
        output = json.dumps(campaigns_data, indent=2, ensure_ascii=False)
        
        return StreamingResponse(
            iter([output]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=targets_account_{account_id}.json"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}/export-search-terms")
async def export_search_terms_xlsx(
    request: Request,
    account_id: int,
    start_date: str = None,
    end_date: str = None,
):
    """
    Genera e scarica il report SP Search Term per un account, per tutti i profili attivi.
    Restituisce un file Excel (.xlsx) con le metriche per ogni termine di ricerca per ad group.
    
    Query params:
        start_date: YYYY-MM-DD (default: 30 giorni fa)
        end_date:   YYYY-MM-DD (default: ieri)
    """
    from fastapi.responses import StreamingResponse
    from db.accounts_db import get_client_account, get_client_profiles
    from backend.app.services.amazon_ads.report import create_sp_search_term_report, wait_for_report, download_report_gzip_json
    from backend.app.services.amazon import get_api_url_for_country, get_valid_access_token
    import io
    from datetime import date, timedelta

    user_id = _get_user_id_from_request(request)

    try:
        from datetime import datetime as _dt
        today = date.today()
        if end_date:
            try:
                end = _dt.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="end_date non valido, formato atteso: YYYY-MM-DD")
        else:
            end = today - timedelta(days=1)
        if start_date:
            try:
                start = _dt.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="start_date non valido, formato atteso: YYYY-MM-DD")
        else:
            start = end - timedelta(days=29)

        if start > end:
            raise HTTPException(status_code=400, detail="start_date deve essere precedente a end_date")

        account = get_client_account(account_id, user_id=user_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account non trovato")

        access_token, token_error = get_valid_access_token(account_id)
        if token_error:
            code = token_error.get("code", "")
            if code == "AUTH_FAILED":
                raise HTTPException(status_code=401, detail="Token Amazon scaduto — riconnetti l'account dalla pagina Account.")
            raise HTTPException(status_code=400, detail=token_error.get("error", "Token non disponibile"))
        if not access_token:
            raise HTTPException(status_code=400, detail="Token non disponibile")

        profiles = get_client_profiles(account_id)
        active_profiles = [p for p in profiles if p.get("country_code") in ("US", "UK", "IT", "DE", "FR", "ES", "CA")]
        if not active_profiles:
            active_profiles = profiles

        from backend.app.services.amazon_ads.report import split_date_range
        date_chunks = split_date_range(start, end, max_days=31)
        print(f"[SEARCH-TERM] {len(date_chunks)} chunk(s) per {len(active_profiles)} profili")

        # --- Fase 1: submit tutti i report (profilo × chunk) in parallelo ---
        pending = []
        for profile in active_profiles:
            profile_id = str(profile.get("profile_id"))
            country_code = profile.get("country_code", "")
            marketplace = profile.get("marketplace_string") or country_code
            api_url = profile.get("api_url") or get_api_url_for_country(country_code)
            for chunk_start, chunk_end in date_chunks:
                try:
                    report_id = create_sp_search_term_report(
                        access_token=access_token,
                        profile_id=profile_id,
                        start_date=chunk_start,
                        end_date=chunk_end,
                        api_url=api_url,
                    )
                    pending.append({
                        "profile_id": profile_id,
                        "marketplace": marketplace,
                        "api_url": api_url,
                        "report_id": report_id,
                    })
                    print(f"[SEARCH-TERM] Sottomesso {profile_id} {chunk_start}→{chunk_end} → {report_id}")
                except Exception as e:
                    print(f"[SEARCH-TERM] Errore submit {profile_id} {chunk_start}→{chunk_end}: {e}")

        if not pending:
            raise HTTPException(status_code=400, detail="Nessun report creato. Verifica i token e i profili dell'account.")

        # --- Fase 2: poll tutti in parallelo fino a completamento ---
        import time as _time
        from backend.app.services.amazon_ads.report import check_report_status_once

        deadline = _time.time() + 300  # 5 minuti totali
        completed = {}  # report_id → meta

        while pending and _time.time() < deadline:
            still_pending = []
            for item in pending:
                rid = item["report_id"]
                try:
                    meta = check_report_status_once(
                        access_token=access_token,
                        profile_id=item["profile_id"],
                        report_id=rid,
                        api_url=item["api_url"],
                    )
                    status = meta.get("status")
                    if status == "SUCCESS":
                        completed[rid] = {**item, "meta": meta}
                    elif status in ("FAILURE", "CANCELLED"):
                        print(f"[SEARCH-TERM] Report {rid} fallito: {meta}")
                    else:
                        still_pending.append(item)
                except Exception as e:
                    print(f"[SEARCH-TERM] Errore poll {rid}: {e}")
                    still_pending.append(item)
            pending = still_pending
            if pending:
                _time.sleep(5)

        if not completed:
            raise HTTPException(status_code=504, detail="Nessun report completato entro 5 minuti. Riprova.")

        # --- Fase 3: download e aggregazione ---
        all_rows = []
        for rid, item in completed.items():
            meta = item["meta"]
            location = meta.get("location") or meta.get("url")
            if not location:
                print(f"[SEARCH-TERM] Nessuna location per report {rid}")
                continue
            try:
                rows = download_report_gzip_json(location)
            except Exception as e:
                print(f"[SEARCH-TERM] Errore download {rid}: {e}")
                continue

            for row in rows:
                impressions = int(row.get("impressions") or 0)
                clicks = int(row.get("clicks") or 0)
                cost = float(row.get("cost") or 0.0)
                purchases = int(row.get("purchases14d") or 0)
                sales = float(row.get("sales14d") or 0.0)
                units = int(row.get("unitsSoldClicks14d") or 0)

                raw_acos = row.get("acosClicks14d")
                raw_roas = row.get("roasClicks14d")
                raw_cpc = row.get("costPerClick")
                raw_ctr = row.get("clickThroughRate")
                raw_kenp = row.get("kindleEditionNormalizedPagesRead14d")
                raw_kenp_roy = row.get("kindleEditionNormalizedPagesRoyalties14d")

                all_rows.append({
                    "date": str(row.get("date") or ""),
                    "marketplace": item["marketplace"],
                    "profile_id": item["profile_id"],
                    "campaign_id": str(row.get("campaignId") or ""),
                    "campaign_name": str(row.get("campaignName") or ""),
                    "ad_group_id": str(row.get("adGroupId") or ""),
                    "ad_group_name": str(row.get("adGroupName") or ""),
                    "keyword_id": str(row.get("keywordId") or ""),
                    "keyword": str(row.get("keyword") or ""),
                    "targeting": str(row.get("targeting") or ""),
                    "match_type": str(row.get("matchType") or ""),
                    "search_term": str(row.get("searchTerm") or ""),
                    "impressions": impressions,
                    "clicks": clicks,
                    "cost": cost,
                    "cost_per_click": float(raw_cpc) if raw_cpc is not None else None,
                    "ctr": float(raw_ctr) if raw_ctr is not None else None,
                    "purchases14d": purchases,
                    "sales14d": sales,
                    "units14d": units,
                    "acos14d": float(raw_acos) if raw_acos is not None else None,
                    "roas14d": float(raw_roas) if raw_roas is not None else None,
                    "kenp_read14d": int(raw_kenp) if raw_kenp is not None else None,
                    "kenp_royalties14d": float(raw_kenp_roy) if raw_kenp_roy is not None else None,
                })

        import json as _json
        payload = {
            "account_id": account_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "rows": all_rows,
        }
        json_bytes = _json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        buf = io.BytesIO(json_bytes)

        filename = f"search_term_report_{account_id}_{start.isoformat()}_{end.isoformat()}.json"
        return StreamingResponse(
            buf,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Search Term Report — Endpoint asincroni ────────────────────────────────

class StrJobRequest(BaseModel):
    profile_ids: List[str]
    start_date: str
    end_date: str


@router.post("/accounts/{account_id}/search-term-jobs")
async def start_search_term_job(
    request: Request,
    account_id: int,
    body: StrJobRequest,
):
    """
    Sottomette i report SP Search Term ad Amazon per i profili selezionati.
    Restituisce immediatamente un job_id e la lista degli Amazon report_id.
    Il polling avviene in background; usare GET /search-term-jobs/{job_id} per controllare lo stato.
    """
    from db.accounts_db import get_client_account, get_client_profiles
    from backend.app.services.amazon_ads.report import create_sp_search_term_report, split_date_range
    from backend.app.services.amazon import get_api_url_for_country, get_valid_access_token
    from datetime import date as _date
    from datetime import datetime as _dt

    user_id = _get_user_id_from_request(request)
    account = get_client_account(account_id, user_id=user_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account non trovato")

    try:
        start = _dt.strptime(body.start_date, "%Y-%m-%d").date()
        end = _dt.strptime(body.end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Date non valide (YYYY-MM-DD)")

    if start > end:
        raise HTTPException(status_code=400, detail="start_date deve essere precedente a end_date")

    access_token, token_error = get_valid_access_token(account_id)
    if not access_token:
        raise HTTPException(status_code=400, detail="Token Amazon non disponibile")

    all_profiles = get_client_profiles(account_id)
    selected_ids = set(body.profile_ids)
    profiles = [p for p in all_profiles if str(p.get("profile_id")) in selected_ids]
    if not profiles:
        raise HTTPException(status_code=400, detail="Nessun profilo trovato tra quelli selezionati")

    date_chunks = split_date_range(start, end, max_days=31)

    items = []
    for profile in profiles:
        profile_id = str(profile.get("profile_id"))
        country_code = profile.get("country_code", "")
        marketplace = profile.get("marketplace_string") or country_code
        api_url = profile.get("api_url") or get_api_url_for_country(country_code)
        for chunk_start, chunk_end in date_chunks:
            try:
                report_id = create_sp_search_term_report(
                    access_token=access_token,
                    profile_id=profile_id,
                    start_date=chunk_start,
                    end_date=chunk_end,
                    api_url=api_url,
                )
                items.append({
                    "profile_id": profile_id,
                    "marketplace": marketplace,
                    "country_code": country_code,
                    "api_url": api_url,
                    "report_id": report_id,
                    "chunk_start": chunk_start.isoformat(),
                    "chunk_end": chunk_end.isoformat(),
                    "status": "PENDING",
                    "amazon_status": None,
                    "location": None,
                })
                print(f"[STR-JOB] Sottomesso {profile_id} {chunk_start}→{chunk_end} → {report_id}")
            except Exception as e:
                print(f"[STR-JOB] Errore submit {profile_id} {chunk_start}→{chunk_end}: {e}")
                items.append({
                    "profile_id": profile_id,
                    "marketplace": marketplace,
                    "country_code": country_code,
                    "api_url": api_url,
                    "report_id": None,
                    "chunk_start": chunk_start.isoformat(),
                    "chunk_end": chunk_end.isoformat(),
                    "status": "FAILED",
                    "amazon_status": None,
                    "location": None,
                    "error": str(e),
                })

    submitted = [i for i in items if i["status"] == "PENDING"]
    if not submitted:
        raise HTTPException(status_code=400, detail="Nessun report sottomesso. Verifica i token e i profili.")

    job_id = str(_uuid.uuid4())
    with _str_jobs_lock:
        _str_jobs[job_id] = {
            "job_id": job_id,
            "account_id": account_id,
            "status": "RUNNING",
            "items": items,
            "rows": None,
            "total_rows": None,
            "created_at": datetime.utcnow().isoformat(),
        }

    t = _threading.Thread(target=_str_poll_thread, args=(job_id, account_id), daemon=True)
    t.start()

    return {
        "job_id": job_id,
        "status": "RUNNING",
        "items": items,
        "submitted": len(submitted),
        "total": len(items),
    }


@router.get("/accounts/{account_id}/search-term-jobs/{job_id}")
async def get_search_term_job(
    request: Request,
    account_id: int,
    job_id: str,
):
    """Restituisce lo stato del job di generazione Search Term report."""
    user_id = _get_user_id_from_request(request)
    with _str_jobs_lock:
        job = _str_jobs.get(job_id)
    if not job or job.get("account_id") != account_id:
        raise HTTPException(status_code=404, detail="Job non trovato")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "items": job["items"],
        "total_rows": job.get("total_rows"),
        "created_at": job.get("created_at"),
    }


@router.get("/accounts/{account_id}/search-term-jobs/{job_id}/download")
async def download_search_term_job(
    request: Request,
    account_id: int,
    job_id: str,
):
    """Scarica il JSON risultato del job quando status == DONE."""
    import json as _json
    import io

    user_id = _get_user_id_from_request(request)
    with _str_jobs_lock:
        job = _str_jobs.get(job_id)
    if not job or job.get("account_id") != account_id:
        raise HTTPException(status_code=404, detail="Job non trovato")
    if job["status"] == "RUNNING":
        raise HTTPException(status_code=202, detail="Report ancora in generazione")
    if job["status"] == "TIMEOUT":
        raise HTTPException(status_code=504, detail="Timeout — Amazon non ha completato i report entro 10 minuti")
    if job["status"] != "DONE":
        raise HTTPException(status_code=500, detail=f"Job in stato: {job['status']}")

    rows = job.get("rows") or []
    payload = {
        "job_id": job_id,
        "account_id": account_id,
        "total_rows": len(rows),
        "rows": rows,
    }
    json_bytes = _json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    buf = io.BytesIO(json_bytes)
    filename = f"search_term_{account_id}_{job_id[:8]}.json"
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/cache")
async def clear_cache():
    """Clear all cached live bids data."""
    stats_before = get_cache_stats()
    clear_live_bids_cache()
    return {
        "success": True,
        "cleared_keys": stats_before["total_keys"],
        "message": f"Cache svuotata: {stats_before['total_keys']} chiavi rimosse"
    }


@router.delete("/accounts/{account_id}/asin-cache")
async def clear_asin_cache(account_id: int):
    """Clear ASIN economics cache for an account."""
    from db.accounts_db import get_connection
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Get profile IDs for this account
        cur.execute("""
            SELECT profile_id FROM client_profiles WHERE client_account_id = %s
        """, (account_id,))
        profile_ids = [row[0] for row in cur.fetchall()]
        
        if not profile_ids:
            return {"success": True, "deleted_count": 0, "message": "Nessun profilo trovato per questo account"}
        
        # Delete from book_economics_cache for ASINs linked to this account's profiles
        cur.execute("""
            DELETE FROM book_economics_cache 
            WHERE (asin, marketplace) IN (
                SELECT pb.asin, pb.marketplace 
                FROM profile_books pb 
                WHERE pb.profile_id = ANY(%s)
            )
        """, (profile_ids,))
        deleted_economics = cur.rowcount
        
        # Also delete from profile_books to clear the ASIN associations
        cur.execute("""
            DELETE FROM profile_books WHERE profile_id = ANY(%s)
        """, (profile_ids,))
        deleted_books = cur.rowcount
        
        conn.commit()
        
        return {
            "success": True,
            "deleted_count": deleted_economics + deleted_books,
            "message": f"Cache ASIN svuotata: {deleted_economics} economics + {deleted_books} associazioni ASIN rimosse"
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


@router.delete("/cache/{profile_id}")
async def clear_cache_for_profile(profile_id: str):
    """Clear cached live bids data for a specific profile."""
    stats_before = get_cache_stats()
    keys_before = [k for k in stats_before["keys"] if k.startswith(f"{profile_id}_")]
    clear_live_bids_cache(profile_id)
    return {
        "success": True,
        "cleared_keys": len(keys_before),
        "message": f"Cache svuotata per profilo {profile_id}: {len(keys_before)} chiavi rimosse"
    }


@router.get("/cache/stats")
async def get_cache_statistics():
    """Get cache statistics."""
    return get_cache_stats()


@router.post("/actions/execute/{profile_id}")
async def execute_actions(profile_id: str):
    """Execute planned actions for a profile (update bids or pause targets on Amazon)."""
    from db.accounts_db import get_connection, get_account_for_profile
    from psycopg2.extras import RealDictCursor
    from backend.app.services.amazon_ads.update_bids import update_target_bids, update_keyword_bids, pause_sp_targets, pause_sb_targets, pause_sp_keywords, pause_sb_keywords
    from backend.app.services.amazon import get_valid_access_token
    
    try:
        profile_info = get_account_for_profile(profile_id)
        if not profile_info:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        account_id = profile_info.get('client_account_id')
        country_code = profile_info.get('country_code', 'US')
        
        access_token, token_error = get_valid_access_token(account_id)
        if not access_token:
            error_msg = token_error.get('error', 'Token non disponibile') if token_error else 'Token non disponibile'
            raise HTTPException(status_code=400, detail=error_msg)
        
        print(f"[EXECUTE-PROFILE] Token prefix: {access_token[:20]}... len={len(access_token)}")
        
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT pa.* FROM planned_actions pa
            WHERE pa.profile_id = %s AND pa.status = 'PLANNED'
        """, (profile_id,))
        actions = cur.fetchall()
        
        if not actions:
            cur.close()
            conn.close()
            return {"message": "No planned actions to execute", "executed": 0}
        
        api_url = "https://advertising-api.amazon.com" if country_code == 'US' else "https://advertising-api-eu.amazon.com"
        
        targets = []
        keywords = []
        pause_actions_by_type = {"sp_kw": [], "sp_tgt": [], "sb_kw": [], "sb_tgt": []}
        pause_action_ids = {"sp_kw": [], "sp_tgt": [], "sb_kw": [], "sb_tgt": []}
        
        for action in actions:
            keyword_id = action.get('keyword_id')
            reason = action.get('reason', '')
            ad_product = action.get('ad_product', 'SP')
            target_type = action.get('target_type', 'keyword')
            
            if keyword_id is None:
                continue
            
            is_pause = reason == 'PAUSE_HIGH_CLICKS_NO_SALES' or (isinstance(reason, str) and reason.startswith('PAUSA'))
            if is_pause:
                is_keyword = target_type == 'keyword'
                if ad_product == 'SB':
                    key = "sb_kw" if is_keyword else "sb_tgt"
                else:
                    key = "sp_kw" if is_keyword else "sp_tgt"
                pause_actions_by_type[key].append(action)
                pause_action_ids[key].append(action['id'])
                continue
            
            new_bid = action.get('new_bid')
            target_type = action.get('target_type', 'keyword')
            
            if new_bid is None:
                continue
            
            if target_type == 'target':
                targets.append({"targetId": str(keyword_id), "bid": float(new_bid), "action_id": action['id']})
            else:
                keywords.append({"keywordId": str(keyword_id), "bid": float(new_bid), "action_id": action['id']})
        
        executed = 0
        failed = 0
        paused = 0
        
        def _run_pause(pause_acts, act_ids, pause_fn, label, use_actions=False):
            nonlocal paused, failed
            if not pause_acts:
                return
            print(f"[EXECUTE-PROFILE] Pausing {len(pause_acts)} {label}")
            if use_actions:
                result = pause_fn(access_token, profile_id, api_url=api_url, actions=pause_acts)
            else:
                entity_ids = [str(a.get('keyword_id', '')) for a in pause_acts if a.get('keyword_id')]
                result = pause_fn(access_token, profile_id, entity_ids, api_url=api_url)
            p_success = result.get("success", 0)
            p_fail = result.get("failed", 0)
            paused += p_success
            failed += p_fail
            if p_fail == 0:
                for aid in act_ids:
                    cur.execute("UPDATE planned_actions SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP WHERE id = %s", (aid,))
            else:
                error_msg = str(result.get("results", []))[:500]
                for aid in act_ids:
                    cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", (error_msg, aid))
        
        _run_pause(pause_actions_by_type["sp_kw"], pause_action_ids["sp_kw"], pause_sp_keywords, "SP keywords")
        _run_pause(pause_actions_by_type["sp_tgt"], pause_action_ids["sp_tgt"], pause_sp_targets, "SP targets")
        _run_pause(pause_actions_by_type["sb_kw"], pause_action_ids["sb_kw"], pause_sb_keywords, "SB keywords", use_actions=True)
        _run_pause(pause_actions_by_type["sb_tgt"], pause_action_ids["sb_tgt"], pause_sb_targets, "SB targets", use_actions=True)
        
        if targets:
            result = update_target_bids(access_token, profile_id, targets, api_url=api_url)
            success_count = result.get("success", 0)
            fail_count = result.get("failed", 0)
            executed += success_count
            failed += fail_count
            for t in targets:
                if fail_count == len(targets):
                    error_msg = str(result.get("results", []))[:500]
                    cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", (error_msg, t["action_id"]))
                else:
                    cur.execute("UPDATE planned_actions SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP WHERE id = %s", (t["action_id"],))
        
        if keywords:
            result = update_keyword_bids(access_token, profile_id, keywords, api_url=api_url)
            success_count = result.get("success", 0)
            fail_count = result.get("failed", 0)
            executed += success_count
            failed += fail_count
            for k in keywords:
                if fail_count == len(keywords):
                    error_msg = str(result.get("results", []))[:500]
                    cur.execute("UPDATE planned_actions SET status = 'FAILED', error_message = %s WHERE id = %s", (error_msg, k["action_id"]))
                else:
                    cur.execute("UPDATE planned_actions SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP WHERE id = %s", (k["action_id"],))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "profile_id": profile_id,
            "executed": executed,
            "paused": paused,
            "failed": failed,
            "message": f"Executed {executed} bid updates, {paused} targets paused, {failed} failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/execute-single/{action_id}")
async def execute_single_action(action_id: int):
    """Execute a single planned action by fetching live bid from Amazon and applying delta."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    from backend.app.services.amazon_ads.update_bids import update_target_bids, update_keyword_bids
    from backend.app.services.amazon_ads.targets import get_targets_for_campaign, get_keywords_for_campaign
    from backend.app.services.amazon import get_valid_access_token
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT pa.*, cp.country_code
            FROM planned_actions pa
            LEFT JOIN client_profiles cp ON pa.profile_id = cp.profile_id
            WHERE pa.id = %s AND pa.status = 'PLANNED'
        """, (action_id,))
        action = cur.fetchone()
        
        if not action:
            cur.close()
            conn.close()
            return {"success": False, "error": "Azione non trovata o già eseguita"}
        
        account_id = action.get('account_id')
        access_token, token_error = get_valid_access_token(account_id)
        
        if not access_token:
            cur.close()
            conn.close()
            error_msg = token_error.get('error', 'Token non disponibile') if token_error else 'Token non disponibile'
            return {"success": False, "error": error_msg}
        
        keyword_id = action.get('keyword_id')
        campaign_id = action.get('campaign_id')
        ad_group_id = action.get('ad_group_id')
        delta_bid = action.get('delta_bid', 0)
        target_type = action.get('target_type', 'keyword')
        profile_id = action.get('profile_id')
        country_code = action.get('country_code', 'US')
        action_keyword = action.get('keyword') or ''
        ad_product = action.get('ad_product', 'SP')
        api_url = "https://advertising-api.amazon.com" if country_code == 'US' else "https://advertising-api-eu.amazon.com"
        
        reason = action.get('reason', '')
        is_pause = reason == 'PAUSE_HIGH_CLICKS_NO_SALES' or (isinstance(reason, str) and reason.startswith('PAUSA'))
        
        if is_pause:
            from backend.app.services.amazon_ads.update_bids import pause_sp_targets, pause_sb_targets, pause_sp_keywords, pause_sb_keywords
            is_keyword = target_type == 'keyword'
            print(f"[EXECUTE-SINGLE] PAUSE action for {ad_product} {'keyword' if is_keyword else 'target'} {keyword_id}")
            try:
                if ad_product == 'SB':
                    action_data = [action]
                    if is_keyword:
                        result = pause_sb_keywords(access_token, profile_id, api_url=api_url, actions=action_data)
                    else:
                        result = pause_sb_targets(access_token, profile_id, api_url=api_url, actions=action_data)
                else:
                    if is_keyword:
                        result = pause_sp_keywords(access_token, profile_id, [str(keyword_id)], api_url=api_url)
                    else:
                        result = pause_sp_targets(access_token, profile_id, [str(keyword_id)], api_url=api_url)
                
                success_count = result.get("success", 0)
                if success_count > 0:
                    cur.execute("""
                        UPDATE planned_actions 
                        SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (action_id,))
                    conn.commit()
                    cur.close()
                    conn.close()
                    return {
                        "success": True,
                        "message": f"Target {keyword_id} messo in PAUSA ({ad_product})",
                        "action_id": action_id,
                        "keyword": action_keyword,
                        "action_type": "PAUSE"
                    }
                else:
                    error_details = str(result.get("results", []))[:500]
                    cur.execute("""
                        UPDATE planned_actions 
                        SET status = 'FAILED', error_message = %s
                        WHERE id = %s
                    """, (error_details, action_id))
                    conn.commit()
                    cur.close()
                    conn.close()
                    return {"success": False, "error": error_details}
            except Exception as pause_err:
                cur.execute("""
                    UPDATE planned_actions 
                    SET status = 'FAILED', error_message = %s
                    WHERE id = %s
                """, (str(pause_err), action_id))
                conn.commit()
                cur.close()
                conn.close()
                return {"success": False, "error": f"Errore pausa: {str(pause_err)}"}
        
        if campaign_id is None:
            cur.close()
            conn.close()
            return {"success": False, "error": "Dati azione incompleti: campaign_id mancante"}
        
        print(f"[EXECUTE-SINGLE] Fetching live bids for campaign {campaign_id}, target_type={target_type}, keyword_id={keyword_id}, keyword={action_keyword}, ad_product={ad_product}...")
        
        live_bid = None
        real_entity_id = None
        matched_ad_group_id = None
        is_keyword_type = (target_type == 'keyword')
        is_sb = (ad_product == 'SB')
        is_sb_keyword_entity = False
        
        sb_service = None
        try:
            if is_sb:
                cached = get_cached_live_bids(str(profile_id), "SB")
                if cached:
                    sb_targets = cached.get("sb_targets", [])
                    print(f"[EXECUTE-SINGLE] SB: Using CACHED {len(sb_targets)} targets for profile {profile_id}")
                else:
                    from backend.app.services.amazon import AmazonAdsService
                    from db.accounts_db import get_client_tokens
                    token_data = get_client_tokens(account_id)
                    refresh_token = token_data.get("refresh_token", "") if token_data else ""
                    sb_service = AmazonAdsService(access_token, refresh_token, account_id)
                    sb_service.profile_id = profile_id
                    sb_targets = sb_service.get_sb_targets(profile_id, api_url)
                    set_cached_live_bids(str(profile_id), "SB", {"sb_targets": sb_targets})
                    print(f"[EXECUTE-SINGLE] SB: Fetched and CACHED {len(sb_targets)} targets for profile {profile_id}")
                
                for t in sb_targets:
                    is_sb_keyword = 'keywordId' in t
                    tid = str(t.get('keywordId', '') if is_sb_keyword else t.get('targetId', ''))
                    t_campaign = str(t.get('campaignId', ''))
                    
                    if t_campaign != str(campaign_id):
                        continue
                    
                    bid_obj = t.get('bid')
                    current_bid = None
                    if isinstance(bid_obj, dict):
                        current_bid = bid_obj.get('bid')
                    elif bid_obj is not None:
                        current_bid = float(bid_obj)
                    
                    matched = False
                    
                    if keyword_id and tid == str(keyword_id):
                        matched = True
                        print(f"[EXECUTE-SINGLE] SB matched by ID! {'keywordId' if is_sb_keyword else 'targetId'}={tid}")
                    elif is_keyword_type and is_sb_keyword:
                        kw_text = t.get('keywordText', '')
                        if kw_text and kw_text.lower() == action_keyword.lower():
                            matched = True
                            print(f"[EXECUTE-SINGLE] SB matched keyword by text! keywordText={kw_text}")
                    else:
                        expressions = t.get('expressions', []) or []
                        for expr in expressions:
                            if isinstance(expr, dict):
                                expr_type = expr.get('type', '')
                                expr_value = expr.get('value', '')
                                if expr_type == 'asinSameAs' and expr_value:
                                    action_asin = action_keyword.replace('asin="', '').replace('"', '').strip()
                                    if expr_value == action_asin:
                                        matched = True
                                        break
                    
                    if matched:
                        live_bid = current_bid
                        real_entity_id = tid
                        is_sb_keyword_entity = is_sb_keyword
                        matched_ad_group_id = t.get('adGroupId')
                        print(f"[EXECUTE-SINGLE] SB matched! {'keywordId' if is_sb_keyword else 'targetId'}={tid}, bid={current_bid}, adGroupId={matched_ad_group_id}")
                        break
            elif is_keyword_type:
                cache_key_kw = f"SP_KW_{campaign_id}"
                cached_kw = get_cached_live_bids(str(profile_id), cache_key_kw)
                if cached_kw:
                    keywords = cached_kw.get("keywords", [])
                    print(f"[EXECUTE-SINGLE] SP: Using CACHED {len(keywords)} keywords for campaign {campaign_id}")
                else:
                    keywords = get_keywords_for_campaign(access_token, profile_id, campaign_id, api_url=api_url)
                    set_cached_live_bids(str(profile_id), cache_key_kw, {"keywords": keywords})
                    print(f"[EXECUTE-SINGLE] SP: Fetched and CACHED {len(keywords)} keywords for campaign {campaign_id}")
                for kw in keywords:
                    kw_id = str(kw.get('keywordId', ''))
                    if keyword_id and kw_id == str(keyword_id):
                        live_bid = kw.get('bid')
                        real_entity_id = kw.get('keywordId')
                        print(f"[EXECUTE-SINGLE] Matched SP keyword by ID! keywordId={real_entity_id}, bid={live_bid}")
                        break
            else:
                cache_key_tg = f"SP_TG_{campaign_id}"
                cached_tg = get_cached_live_bids(str(profile_id), cache_key_tg)
                if cached_tg:
                    targets = cached_tg.get("targets", [])
                    print(f"[EXECUTE-SINGLE] SP: Using CACHED {len(targets)} targets for campaign {campaign_id}")
                else:
                    targets = get_targets_for_campaign(access_token, profile_id, campaign_id, api_url=api_url)
                    set_cached_live_bids(str(profile_id), cache_key_tg, {"targets": targets})
                    print(f"[EXECUTE-SINGLE] SP: Fetched and CACHED {len(targets)} targets for campaign {campaign_id}")
                
                auto_map = {
                    "queryHighRelMatches": "close-match",
                    "queryBroadRelMatches": "loose-match",
                    "asinSubstituteRelated": "substitutes",
                    "asinAccessoryRelated": "complements"
                }
                theme_map = {
                    "KEYWORDS_CLOSE_MATCH": "close-match",
                    "KEYWORDS_LOOSE_MATCH": "loose-match",
                    "PRODUCT_SUBSTITUTES": "substitutes",
                    "PRODUCT_COMPLEMENTS": "complements"
                }
                
                action_keyword_normalized = action_keyword.strip()
                if action_keyword_normalized.lower().startswith('asin=') or action_keyword_normalized.lower().startswith('category='):
                    action_composite_key = f"{campaign_id}_{ad_group_id}_{action_keyword_normalized}"
                elif action_keyword_normalized.lower() in ('close-match', 'loose-match', 'substitutes', 'complements'):
                    action_composite_key = f"{campaign_id}_{ad_group_id}_{action_keyword_normalized}"
                elif len(action_keyword_normalized) == 10 and action_keyword_normalized.isalnum():
                    action_composite_key = f"{campaign_id}_{ad_group_id}_asin={action_keyword_normalized.upper()}"
                else:
                    action_composite_key = f"{campaign_id}_{ad_group_id}_{action_keyword_normalized}"
                print(f"[EXECUTE-SINGLE] SP target: Looking for composite key '{action_composite_key}' in {len(targets)} targets...")
                
                for t in targets:
                    tid = t.get('targetId')
                    t_ad_group_id = str(t.get('adGroupId', ''))
                    td = t.get('targetDetails', {}) or {}
                    bid_obj = t.get('bid', {})
                    current_bid = bid_obj.get('bid') if isinstance(bid_obj, dict) else bid_obj
                    
                    api_composite_key = None
                    
                    if 'productTarget' in td:
                        product_target = td.get('productTarget') or {}
                        product = product_target.get('product') or {}
                        api_asin = product.get('productId', '')
                        if api_asin:
                            api_composite_key = f"{campaign_id}_{t_ad_group_id}_asin={api_asin}"
                    elif 'autoTarget' in td:
                        auto_target = td.get('autoTarget') or {}
                        expr_list = auto_target.get('expression', [])
                        if expr_list:
                            first_expr = expr_list[0] if isinstance(expr_list, list) else {}
                            expr_type = first_expr.get('type', '') if isinstance(first_expr, dict) else str(first_expr)
                            api_auto_type = auto_map.get(expr_type, expr_type.lower())
                            api_composite_key = f"{campaign_id}_{t_ad_group_id}_{api_auto_type}"
                    elif 'themeTarget' in td:
                        theme_target = td.get('themeTarget') or {}
                        match_type = theme_target.get('matchType', '')
                        api_theme_type = theme_map.get(match_type, match_type.lower())
                        api_composite_key = f"{campaign_id}_{t_ad_group_id}_{api_theme_type}"
                    elif 'categoryTarget' in td:
                        category_target = td.get('categoryTarget') or {}
                        api_category_name = category_target.get('categoryName', '')
                        if api_category_name:
                            api_composite_key = f"{campaign_id}_{t_ad_group_id}_category={api_category_name}"
                    
                    if api_composite_key and api_composite_key == action_composite_key:
                        live_bid = current_bid
                        real_entity_id = tid
                        print(f"[EXECUTE-SINGLE] Matched SP target by composite key! targetId={tid}, bid={current_bid}, key={api_composite_key}")
                        break
                    
        except Exception as fetch_err:
            cur.close()
            conn.close()
            return {"success": False, "error": f"Errore recupero bid live: {str(fetch_err)}"}
        
        if live_bid is None or real_entity_id is None:
            if not is_keyword_type:
                print(f"[EXECUTE-SINGLE] NO MATCH FOUND for '{action_keyword}' in campaign {campaign_id}")
                print(f"[EXECUTE-SINGLE] Target types found: {[list((t.get('targetDetails') or {}).keys()) for t in targets[:10]]}")
            cur.close()
            conn.close()
            entity_type = "Keyword" if is_keyword_type else "Target"
            return {"success": False, "error": f"{entity_type} '{action_keyword}' non trovato nella campagna {campaign_id}"}
        
        new_bid = max(0.02, round(float(live_bid) + float(delta_bid or 0), 2))
        
        print(f"[EXECUTE-SINGLE] Live bid: {live_bid}, delta: {delta_bid}, new_bid: {new_bid}")
        
        try:
            if is_sb:
                if sb_service is None:
                    from backend.app.services.amazon import AmazonAdsService
                    from db.accounts_db import get_client_tokens
                    token_data = get_client_tokens(account_id)
                    refresh_token = token_data.get("refresh_token", "") if token_data else ""
                    sb_service = AmazonAdsService(access_token, refresh_token, account_id)
                    sb_service.profile_id = profile_id
                if is_sb_keyword_entity:
                    result = sb_service.update_sb_keyword_bid(str(real_entity_id), new_bid, ad_group_id=str(matched_ad_group_id) if matched_ad_group_id else None, api_url=api_url)
                    print(f"[EXECUTE-SINGLE] SB keyword update result: {result}")
                else:
                    result = sb_service.update_sb_target_bid(str(real_entity_id), new_bid, ad_group_id=str(matched_ad_group_id) if matched_ad_group_id else None, api_url=api_url)
                    print(f"[EXECUTE-SINGLE] SB target update result: {result}")
                success_count = 1 if result.get("success") else 0
                amazon_response = result.get("amazon_response")
            elif is_keyword_type:
                result = update_keyword_bids(access_token, profile_id, [{"keywordId": str(real_entity_id), "bid": new_bid}], api_url=api_url)
                success_count = result.get("success", 0)
            else:
                result = update_target_bids(access_token, profile_id, [{"targetId": str(real_entity_id), "bid": new_bid}], api_url=api_url)
                success_count = result.get("success", 0)
            
            if success_count > 0:
                cur.execute("""
                    UPDATE planned_actions 
                    SET status = 'EXECUTED', executed_at = CURRENT_TIMESTAMP, new_bid = %s, current_bid = %s
                    WHERE id = %s
                """, (new_bid, live_bid, action_id))
                conn.commit()
                cur.close()
                conn.close()
                
                return {
                    "success": True,
                    "message": f"Bid aggiornato: {live_bid:.2f} -> {new_bid:.2f} (delta: {delta_bid:+.2f})",
                    "action_id": action_id,
                    "keyword": action.get('keyword'),
                    "old_bid": live_bid,
                    "new_bid": new_bid,
                    "delta": delta_bid
                }
            else:
                error_details = result.get("error", str(result.get("results", [])))[:500]
                amazon_resp = result.get("amazon_response") if is_sb else result
                cur.execute("""
                    UPDATE planned_actions 
                    SET status = 'FAILED', error_message = %s
                    WHERE id = %s
                """, (error_details, action_id))
                conn.commit()
                cur.close()
                conn.close()
                return {"success": False, "error": error_details, "amazon_response": amazon_resp}
                
        except Exception as api_err:
            cur.execute("""
                UPDATE planned_actions 
                SET status = 'FAILED', error_message = %s
                WHERE id = %s
            """, (str(api_err), action_id))
            conn.commit()
            cur.close()
            conn.close()
            return {"success": False, "error": f"Errore API Amazon: {str(api_err)}"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Runs & Actions
# ============================================

@router.get("/runs")
async def get_runs(account_id: int = None, profile_id: str = None, limit: int = 50):
    """Get autopilot runs."""
    try:
        from db.accounts_db import get_connection
        from psycopg2.extras import RealDictCursor
        
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT * FROM autopilot_runs WHERE 1=1"
        params = []
        
        if account_id:
            query += " AND account_id = %s"
            params.append(account_id)
        if profile_id:
            query += " AND profile_id = %s"
            params.append(profile_id)
        
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        
        cur.execute(query, params)
        runs = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {"runs": [dict(r) for r in runs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}")
async def get_run_detail(run_id: int):
    """Get run detail with actions."""
    try:
        from db.accounts_db import get_connection
        from psycopg2.extras import RealDictCursor
        
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT * FROM autopilot_runs WHERE id = %s", (run_id,))
        run = cur.fetchone()
        
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        cur.execute("""
            SELECT * FROM planned_actions 
            WHERE run_id = %s 
            ORDER BY id
        """, (run_id,))
        actions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "run": dict(run),
            "actions": [dict(a) for a in actions],
            "actions_count": len(actions)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}/execution-report")
async def get_execution_report(run_id: int):
    """Get execution report for a run."""
    try:
        from db.accounts_db import get_connection
        from psycopg2.extras import RealDictCursor
        
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT * FROM autopilot_runs WHERE id = %s", (run_id,))
        run = cur.fetchone()
        
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        cur.execute("""
            SELECT status, COUNT(*) as count 
            FROM planned_actions 
            WHERE run_id = %s 
            GROUP BY status
        """, (run_id,))
        status_counts = cur.fetchall()
        
        cur.execute("""
            SELECT * FROM planned_actions 
            WHERE run_id = %s 
            ORDER BY id
        """, (run_id,))
        actions = cur.fetchall()
        
        cur.close()
        conn.close()
        
        summary = {s['status']: s['count'] for s in status_counts}
        
        return {
            "run_id": run_id,
            "status": run['status'],
            "created_at": run['created_at'],
            "completed_at": run.get('completed_at'),
            "summary": {
                "total": sum(summary.values()),
                "executed": summary.get('EXECUTED', 0),
                "failed": summary.get('FAILED', 0),
                "planned": summary.get('PLANNED', 0),
            },
            "actions": [dict(a) for a in actions]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Scheduler Status
# ============================================

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get profiles due for autopilot run."""
    try:
        due_profiles = get_enabled_autopilot_profiles_due()
        return {
            "profiles_due": len(due_profiles),
            "profiles": due_profiles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Actions Management
# ============================================

@router.get("/actions/{profile_id}")
async def get_actions_for_profile(profile_id: str, status: str = None):
    """Get planned actions for a profile."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if status:
            cur.execute("""
                SELECT * FROM planned_actions 
                WHERE profile_id = %s AND status = %s
                ORDER BY created_at DESC
                LIMIT 200
            """, (profile_id, status))
        else:
            cur.execute("""
                SELECT * FROM planned_actions 
                WHERE profile_id = %s
                ORDER BY created_at DESC
                LIMIT 200
            """, (profile_id,))
        
        actions = cur.fetchall()
        
        increases = sum(1 for a in actions if a.get('delta_bid', 0) > 0)
        decreases = sum(1 for a in actions if a.get('delta_bid', 0) < 0)
        planned = sum(1 for a in actions if a.get('status') == 'PLANNED')
        
        cur.close()
        conn.close()
        
        return {
            "profile_id": profile_id,
            "actions": [dict(a) for a in actions],
            "summary": {
                "total": len(actions),
                "planned": planned,
                "increases": increases,
                "decreases": decreases
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/execute/{profile_id}")
async def execute_profile_actions(profile_id: str):
    """Execute all PLANNED actions for a profile."""
    from db.accounts_db import get_connection, get_actions_by_status, mark_actions_status
    from psycopg2.extras import RealDictCursor
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM planned_actions 
            WHERE profile_id = %s AND status = 'PLANNED'
            ORDER BY id
            LIMIT 100
        """, (profile_id,))
        
        actions = [dict(a) for a in cur.fetchall()]
        cur.close()
        conn.close()
        
        if not actions:
            return {
                "profile_id": profile_id,
                "executed": 0,
                "failed": 0,
                "total": 0,
                "message": "No PLANNED actions to execute"
            }
        
        from backend.app.services.action_executor import execute_actions_once
        
        action_ids = [a["id"] for a in actions]
        mark_actions_status(action_ids, "EXECUTING")
        
        result = execute_actions_once(batch_size=len(actions))
        
        return {
            "profile_id": profile_id,
            "executed": result.get("executed", 0),
            "failed": result.get("failed", 0),
            "total": len(actions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Step-by-Step Autopilot Operations
# ============================================

@router.post("/step/fetch-asins/{account_id}")
async def step_fetch_asins(account_id: int):
    """Step 1: Fetch ASINs from campaigns and get economics from Oxylabs.
    
    Clears existing profile_books and book_economics_cache for the account's
    autopilot profiles FIRST, then re-fetches fresh data. This prevents stale
    partial data from persisting after clear ASIN + re-enable automation.
    """
    from db.accounts_db import get_profiles_for_account, get_connection
    from psycopg2.extras import RealDictCursor
    from backend.app.services.autopilot_sync_service import (
        get_access_token,
        fetch_asins_from_amazon_api,
        get_profile_api_url,
        fetch_oxylabs_economics,
        save_book_economics,
        ensure_profile_book,
        calculate_economics,
        ALLOWED_COUNTRIES
    )
    
    try:
        profiles = get_profiles_for_account(account_id)
        profiles = [p for p in profiles if p.get('country_code') in ALLOWED_COUNTRIES]
        
        if not profiles:
            return {"error": "Nessun profilo US/UK/IT trovato", "total_asins": 0}
        
        access_token = get_access_token(account_id)
        if not access_token:
            return {"error": "Token di accesso non disponibile", "total_asins": 0}
        
        profile_ids = [str(p.get('profile_id')) for p in profiles]
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                DELETE FROM book_economics_cache 
                WHERE (asin, marketplace) IN (
                    SELECT pb.asin, pb.marketplace 
                    FROM profile_books pb 
                    WHERE pb.profile_id = ANY(%s)
                )
            """, (profile_ids,))
            deleted_economics = cur.rowcount
            
            cur.execute("""
                DELETE FROM profile_books WHERE profile_id = ANY(%s)
            """, (profile_ids,))
            deleted_books = cur.rowcount
            
            conn.commit()
            print(f"[FETCH-ASINS] Cleared stale data for account {account_id}: {deleted_economics} economics + {deleted_books} profile_books")
        except Exception as clear_err:
            conn.rollback()
            print(f"[FETCH-ASINS] Warning: Failed to clear stale data: {clear_err}")
        finally:
            cur.close()
            conn.close()
        
        total_asins = 0
        profile_results = []
        
        for profile in profiles:
            profile_id = str(profile.get('profile_id'))
            country_code = profile.get('country_code', 'US')
            api_url = get_profile_api_url(profile_id)
            
            asins = fetch_asins_from_amazon_api(access_token, profile_id, api_url)
            
            for asin in asins:
                ensure_profile_book(profile_id, asin, country_code)
                oxylabs_data = fetch_oxylabs_economics(asin, country_code)
                if oxylabs_data:
                    economics = calculate_economics(oxylabs_data)
                    save_book_economics(asin, country_code, oxylabs_data, economics)
            
            total_asins += len(asins)
            profile_results.append({
                "profile_id": profile_id,
                "country_code": country_code,
                "asins_found": len(asins),
                "asins": list(asins)[:10]
            })
        
        return {
            "status": "completed",
            "total_asins": total_asins,
            "profiles": profile_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step/request-reports/{account_id}")
async def step_request_reports(account_id: int):
    """Step 2: Request reports from Amazon for all profiles.
    
    Only requests reports for campaign types that exist in each profile:
    - If profile has SP campaigns -> request SP reports
    - If profile has SB campaigns -> request SB reports
    - Skip reports for campaign types that don't exist
    """
    from db.accounts_db import get_profiles_for_account
    from backend.app.services.autopilot_sync_service import (
        get_access_token,
        request_amazon_report,
        ALLOWED_COUNTRIES
    )
    from backend.app.services.amazon import AmazonAdsService
    
    try:
        profiles = get_profiles_for_account(account_id)
        profiles = [p for p in profiles if p.get('country_code') in ALLOWED_COUNTRIES]
        
        if not profiles:
            return {"error": "Nessun profilo trovato", "reports_requested": 0}
        
        from db.accounts_db import get_connection
        from psycopg2.extras import RealDictCursor
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT profile_id FROM autopilot_profiles WHERE account_id = %s AND enabled = TRUE", (account_id,))
        enabled_profile_ids = {str(row['profile_id']) for row in cur.fetchall()}
        cur.close()
        conn.close()
        
        profiles = [p for p in profiles if str(p.get('profile_id')) in enabled_profile_ids]
        
        if not profiles:
            return {"error": "Nessun profilo con Autopilot attivo", "reports_requested": 0}
        
        access_token = get_access_token(account_id)
        if not access_token:
            return {"error": "Token di accesso non disponibile", "reports_requested": 0}
        
        reports_requested = 0
        reports_cached = 0
        reports_failed = 0
        profile_results = []
        
        for profile in profiles:
            profile_id = profile.get('profile_id')
            country_code = profile.get('country_code', 'US')
            api_url = f"https://advertising-api.amazon.com" if country_code == 'US' else f"https://advertising-api-eu.amazon.com"
            
            print(f"[REQUEST-REPORTS] Profile {profile_id}: Requesting SP and SB 30D reports only")
            
            import time
            sp_report_30 = request_amazon_report(access_token, profile_id, 30, api_url, account_id, ad_product='SP')
            time.sleep(2)
            sb_report_30 = request_amazon_report(access_token, profile_id, 30, api_url, account_id, ad_product='SB')
            
            result = {
                "profile_id": profile_id,
                "country_code": country_code,
                "sp_report_30d": sp_report_30,
                "sb_report_30d": sb_report_30
            }
            profile_results.append(result)
            
            for label, rpt in [("SP", sp_report_30), ("SB", sb_report_30)]:
                if rpt:
                    reports_requested += 1
                    if rpt.get('is_cached'):
                        reports_cached += 1
                else:
                    reports_failed += 1
                    print(f"[REQUEST-REPORTS] FAILED: {label} report for profile {profile_id} returned None")
        
        if reports_requested == 0 and reports_failed > 0:
            error_msg = f"Tutti i report hanno fallito ({reports_failed} errori). Verificare token Amazon."
            print(f"[REQUEST-REPORTS] ERROR: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        if reports_failed > 0:
            print(f"[REQUEST-REPORTS] WARNING: {reports_failed} report falliti, {reports_requested} riusciti")
        
        all_cached = reports_requested > 0 and reports_cached == reports_requested
        
        return {
            "status": "completed",
            "reports_requested": reports_requested,
            "reports_cached": reports_cached,
            "reports_failed": reports_failed,
            "all_cached": all_cached,
            "profiles": profile_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PlanActionsRequest(BaseModel):
    target_scope: Optional[str] = None


@router.post("/step/plan-actions/{account_id}")
async def step_plan_actions(account_id: int, request: PlanActionsRequest = None):
    """Step 3: Analyze reports and create planned actions for all profiles registered in autopilot_profiles.
    
    Args:
        target_scope: Optional filter:
            - 'AUTO': Only SP auto-targeting (close-match, loose-match, substitutes, complements)
            - 'SP_MANUAL': SP keywords + product/category targets (excludes auto)
            - 'SB': All SB actions (keywords + targets)
            - None: All actions (default)
    """
    from db.accounts_db import get_profiles_for_account, get_connection
    from psycopg2.extras import RealDictCursor
    from backend.app.services.autopilot_sync_service import (
        analyze_and_plan_actions,
        ALLOWED_COUNTRIES
    )
    
    target_scope = request.target_scope if request else None
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT profile_id FROM autopilot_profiles 
            WHERE account_id = %s
        """, (account_id,))
        registered_profiles = {row['profile_id'] for row in cur.fetchall()}
        cur.close()
        conn.close()
        
        profiles = get_profiles_for_account(account_id)
        profiles = [p for p in profiles if p.get('country_code') in ALLOWED_COUNTRIES and p.get('profile_id') in registered_profiles]
        
        if not profiles:
            return {"error": "Nessun profilo US/UK/IT registrato in autopilot", "actions_planned": 0}
        
        total_actions = 0
        profile_results = []
        
        for profile in profiles:
            profile_id = profile.get('profile_id')
            country_code = profile.get('country_code', 'US')
            
            sp_actions = []
            sb_actions = []
            
            if target_scope in (None, 'AUTO', 'SP_MANUAL'):
                sp_scope = target_scope if target_scope in ('AUTO', 'SP_MANUAL') else None
                sp_actions = analyze_and_plan_actions(account_id, profile_id, ad_product='SP', target_scope=sp_scope)
            
            if target_scope in (None, 'SB'):
                sb_actions = analyze_and_plan_actions(account_id, profile_id, ad_product='SB', target_scope='SB' if target_scope == 'SB' else None)
            
            total_actions += len(sp_actions) + len(sb_actions)
            profile_results.append({
                "profile_id": profile_id,
                "country_code": country_code,
                "sp_actions": len(sp_actions),
                "sb_actions": len(sb_actions),
                "actions_planned": len(sp_actions) + len(sb_actions)
            })
        
        return {
            "status": "completed",
            "target_scope": target_scope,
            "total_actions": total_actions,
            "profiles": profile_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step/fetch-sp-inventory/{account_id}")
async def step_fetch_sp_inventory(account_id: int):
    """Download SP keywords and targets from Amazon API and save to sp_inventory table.
    
    This is the source of truth for which entities exist. The report only provides metrics.
    """
    from backend.app.services.amazon import get_valid_access_token, AmazonAdsService
    from backend.app.services.autopilot_sync_service import save_sp_inventory, get_profile_api_url
    
    try:
        access_token, token_error = get_valid_access_token(account_id)
        if not access_token:
            error_msg = token_error.get('error', 'Token non disponibile') if token_error else 'Token non disponibile'
            return {"status": "error", "message": error_msg, "total_entities": 0}
        
        profiles = get_autopilot_profiles_for_account(account_id)
        if not profiles:
            return {"status": "completed", "message": "Nessun profilo autopilot abilitato", "total_entities": 0}
        
        total_keywords = 0
        total_targets = 0
        profile_results = []
        
        for profile in profiles:
            profile_id = profile.get('profile_id')
            country_code = profile.get('country_code', 'US')
            api_url = get_profile_api_url(profile_id)
            
            try:
                service = AmazonAdsService(access_token, "", account_id)
                
                keywords = service.get_keywords(profile_id, api_url)
                targets = service.get_targets(profile_id, api_url)
                
                campaigns = service.get_campaigns(profile_id, api_url, include_paused=True)
                campaign_states = {str(c.get('campaignId', '')): (c.get('state') or 'ENABLED').upper() for c in campaigns}
                
                saved = save_sp_inventory(account_id, profile_id, keywords, targets, campaign_states)
                
                total_keywords += len(keywords)
                total_targets += len(targets)
                
                profile_results.append({
                    "profile_id": profile_id,
                    "country_code": country_code,
                    "keywords": len(keywords),
                    "targets": len(targets),
                    "saved": saved
                })
                
                print(f"[FETCH-SP-INVENTORY] Profile {profile_id}: {len(keywords)} keywords, {len(targets)} targets")
                
            except Exception as e:
                print(f"[FETCH-SP-INVENTORY] Error for profile {profile_id}: {e}")
                profile_results.append({
                    "profile_id": profile_id,
                    "country_code": country_code,
                    "error": str(e)
                })
        
        return {
            "status": "completed",
            "total_keywords": total_keywords,
            "total_targets": total_targets,
            "total_entities": total_keywords + total_targets,
            "profiles": profile_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step/fetch-sb-inventory/{account_id}")
async def step_fetch_sb_inventory(account_id: int):
    """Download SB targets from Amazon API and save to sb_inventory table."""
    from backend.app.services.amazon import get_valid_access_token, AmazonAdsService
    from backend.app.services.autopilot_sync_service import save_sb_inventory, get_profile_api_url
    
    try:
        access_token, token_error = get_valid_access_token(account_id)
        if not access_token:
            error_msg = token_error.get('error', 'Token non disponibile') if token_error else 'Token non disponibile'
            return {"status": "error", "message": error_msg, "total_entities": 0}
        
        profiles = get_autopilot_profiles_for_account(account_id)
        if not profiles:
            return {"status": "completed", "message": "Nessun profilo autopilot abilitato", "total_entities": 0}
        
        total_targets = 0
        profile_results = []
        
        for profile in profiles:
            profile_id = profile.get('profile_id')
            country_code = profile.get('country_code', 'US')
            api_url = get_profile_api_url(profile_id)
            
            try:
                service = AmazonAdsService(access_token, "", account_id)
                
                sb_targets = service.get_sb_targets(profile_id, api_url)
                
                campaign_ids = list(set(str(t.get('campaignId', '')) for t in sb_targets if t.get('campaignId')))
                print(f"[FETCH-SB-INVENTORY] Profile {profile_id}: extracted {len(campaign_ids)} unique campaignIds from targets")
                
                sb_campaigns = service.get_sb_campaigns(profile_id, api_url, include_paused=True, target_campaign_ids=campaign_ids)
                campaign_states = {str(c.get('campaignId', '')): (c.get('state') or 'ENABLED').upper() for c in sb_campaigns}
                
                saved = save_sb_inventory(account_id, profile_id, sb_targets, campaign_states)
                
                total_targets += len(sb_targets)
                
                profile_results.append({
                    "profile_id": profile_id,
                    "country_code": country_code,
                    "targets": len(sb_targets),
                    "campaigns": len(sb_campaigns),
                    "saved": saved
                })
                
                print(f"[FETCH-SB-INVENTORY] Profile {profile_id}: {len(sb_targets)} targets, {len(sb_campaigns)} campaigns")
                
            except Exception as e:
                print(f"[FETCH-SB-INVENTORY] Error for profile {profile_id}: {e}")
                profile_results.append({
                    "profile_id": profile_id,
                    "country_code": country_code,
                    "error": str(e)
                })
        
        return {
            "status": "completed",
            "total_targets": total_targets,
            "total_entities": total_targets,
            "profiles": profile_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step/plan-auto/{account_id}")
async def step_plan_auto(account_id: int):
    """Pianifica solo le AUTOMATICHE SP (close-match, loose-match, substitutes, complements)."""
    request = PlanActionsRequest(target_scope='AUTO')
    return await step_plan_actions(account_id, request)


@router.post("/step/plan-sp-manual/{account_id}")
async def step_plan_sp_manual(account_id: int):
    """Pianifica solo SP ASIN+Categorie e SP Keywords (esclude automatiche)."""
    request = PlanActionsRequest(target_scope='SP_MANUAL')
    return await step_plan_actions(account_id, request)


@router.post("/step/plan-sb/{account_id}")
async def step_plan_sb(account_id: int):
    """Pianifica solo SB ASIN+Categorie e SB Keywords."""
    request = PlanActionsRequest(target_scope='SB')
    return await step_plan_actions(account_id, request)


async def _execute_sb_actions(cur, sb_actions: list, access_token: str) -> tuple:
    """Execute SB actions using direct IDs (keyword_id, ad_group_id).
    
    SB actions have keyword_id and ad_group_id already stored in planned_actions,
    so we can call the SB API directly without expression matching.
    
    Returns (executed_count, failed_count)
    """
    from backend.app.services.amazon_ads.update_bids import update_sb_keyword_bids, update_sb_target_bids
    from collections import defaultdict
    
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


@router.post("/step/execute-actions/{account_id}")
async def step_execute_actions(account_id: int):
    """Step 4: Execute all planned actions.
    
    Delegates to the shared bid_executor service for actual execution.
    For SP actions: Uses expression matching (keyword text or ASIN) to find the real targetId/keywordId.
    For SB actions: Uses direct IDs (keyword_id, ad_group_id) already stored in planned_actions.
    """
    from backend.app.services.bid_executor import execute_all_bids
    
    try:
        return execute_all_bids(account_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AutopilotSettingsModel(BaseModel):
    delta_excellent: float = 0.05
    delta_good: float = 0.02
    delta_above_be: float = -0.02
    delta_high: float = -0.05
    delta_low_impressions: float = 0.01
    delta_no_sales: float = -0.02
    low_impressions_threshold: int = 100
    min_spend_for_decrement: float = 1.00
    max_clicks_no_sales: int = 10
    max_clicks_for_low_impressions: int = 0
    pause_on_clicks_enabled: bool = True


@router.get("/settings/{account_id}")
async def get_autopilot_settings(account_id: int):
    """Get autopilot settings for an account."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
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
            "min_spend_for_decrement": float(row["min_spend_for_decrement"]),
            "max_clicks_no_sales": int(row.get("max_clicks_no_sales", 20) or 20),
            "max_clicks_for_low_impressions": int(row.get("max_clicks_for_low_impressions", 0) or 0),
            "pause_on_clicks_enabled": bool(row.get("pause_on_clicks_enabled", True) if row.get("pause_on_clicks_enabled") is not None else True)
        }
    else:
        return AutopilotSettingsModel().model_dump()


@router.post("/settings/{account_id}")
async def save_autopilot_settings(account_id: int, settings: AutopilotSettingsModel):
    """Save autopilot settings for an account."""
    from db.accounts_db import get_connection
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO autopilot_settings (account_id, delta_excellent, delta_good, delta_above_be, 
            delta_high, delta_low_impressions, delta_no_sales, low_impressions_threshold, 
            min_spend_for_decrement, max_clicks_no_sales, max_clicks_for_low_impressions,
            pause_on_clicks_enabled, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (account_id) DO UPDATE SET
            delta_excellent = EXCLUDED.delta_excellent,
            delta_good = EXCLUDED.delta_good,
            delta_above_be = EXCLUDED.delta_above_be,
            delta_high = EXCLUDED.delta_high,
            delta_low_impressions = EXCLUDED.delta_low_impressions,
            delta_no_sales = EXCLUDED.delta_no_sales,
            low_impressions_threshold = EXCLUDED.low_impressions_threshold,
            min_spend_for_decrement = EXCLUDED.min_spend_for_decrement,
            max_clicks_no_sales = EXCLUDED.max_clicks_no_sales,
            max_clicks_for_low_impressions = EXCLUDED.max_clicks_for_low_impressions,
            pause_on_clicks_enabled = EXCLUDED.pause_on_clicks_enabled,
            updated_at = CURRENT_TIMESTAMP
    """, (account_id, settings.delta_excellent, settings.delta_good, settings.delta_above_be,
          settings.delta_high, settings.delta_low_impressions, settings.delta_no_sales,
          settings.low_impressions_threshold, settings.min_spend_for_decrement,
          settings.max_clicks_no_sales, settings.max_clicks_for_low_impressions,
          settings.pause_on_clicks_enabled))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return {"status": "saved", "settings": settings.model_dump()}


class SettingsProfileModel(BaseModel):
    name: str
    description: Optional[str] = None
    delta_excellent: float = 0.05
    delta_good: float = 0.02
    delta_above_be: float = -0.02
    delta_high: float = -0.05
    delta_low_impressions: float = 0.01
    delta_no_sales: float = -0.02
    low_impressions_threshold: int = 100
    min_spend_for_decrement: float = 1.00
    max_clicks_no_sales: int = 10
    max_clicks_for_low_impressions: int = 0
    pause_on_clicks_enabled: bool = True
    is_default: bool = False


@router.get("/settings-profiles/{account_id}")
async def get_settings_profiles(account_id: int, request: Request):
    """Get all settings profiles for the authenticated user."""
    import logging
    logger = logging.getLogger(__name__)
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    user_id = _get_user_id_from_request(request)
    
    conn = get_connection()
    try:
        _ensure_default_profiles(conn, user_id)
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, description, delta_excellent, delta_good, delta_above_be,
                   delta_high, delta_low_impressions, delta_no_sales, low_impressions_threshold,
                   min_spend_for_decrement, max_clicks_no_sales, max_clicks_for_low_impressions,
                   pause_on_clicks_enabled, is_default, is_system, created_at, updated_at
            FROM autopilot_settings_profiles 
            WHERE user_id = %s
            ORDER BY is_system DESC, is_default DESC, name ASC
        """, (user_id,))
        
        rows = cur.fetchall()
        cur.close()
    except Exception as e:
        logger.error(f"DB error in get_settings_profiles for user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    
    profiles = []
    for row in rows:
        profiles.append({
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "delta_excellent": float(row["delta_excellent"]),
            "delta_good": float(row["delta_good"]),
            "delta_above_be": float(row["delta_above_be"]),
            "delta_high": float(row["delta_high"]),
            "delta_low_impressions": float(row["delta_low_impressions"]),
            "delta_no_sales": float(row["delta_no_sales"]),
            "low_impressions_threshold": int(row["low_impressions_threshold"]),
            "min_spend_for_decrement": float(row["min_spend_for_decrement"]),
            "max_clicks_no_sales": int(row["max_clicks_no_sales"]) if row.get("max_clicks_no_sales") is not None else 20,
            "is_default": row["is_default"],
            "is_system": row.get("is_system", False),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
        })
    
    return {"profiles": profiles}


@router.post("/settings-profiles/{account_id}")
async def create_settings_profile(account_id: int, profile: SettingsProfileModel, request: Request):
    """Create a new settings profile for the authenticated user."""
    import logging
    logger = logging.getLogger(__name__)
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    user_id = _get_user_id_from_request(request)
    
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if profile.is_default:
            cur.execute("UPDATE autopilot_settings_profiles SET is_default = FALSE WHERE user_id = %s", (user_id,))
        
        cur.execute("""
            INSERT INTO autopilot_settings_profiles 
            (user_id, name, description, delta_excellent, delta_good, delta_above_be,
             delta_high, delta_low_impressions, delta_no_sales, low_impressions_threshold,
             min_spend_for_decrement, max_clicks_no_sales, max_clicks_for_low_impressions,
             pause_on_clicks_enabled, is_default, is_system)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)
            RETURNING id
        """, (user_id, profile.name, profile.description, profile.delta_excellent,
              profile.delta_good, profile.delta_above_be, profile.delta_high,
              profile.delta_low_impressions, profile.delta_no_sales,
              profile.low_impressions_threshold, profile.min_spend_for_decrement,
              profile.max_clicks_no_sales, profile.max_clicks_for_low_impressions,
              profile.pause_on_clicks_enabled, profile.is_default))
        
        new_id = cur.fetchone()["id"]
        conn.commit()
        cur.close()
    except Exception as e:
        logger.error(f"DB error in create_settings_profile for user_id={user_id}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    
    return {"status": "created", "id": new_id, "profile": profile.model_dump()}


@router.put("/settings-profiles/{account_id}/{profile_id}")
async def update_settings_profile(account_id: int, profile_id: int, profile: SettingsProfileModel, request: Request):
    """Update an existing settings profile for the authenticated user."""
    from db.accounts_db import get_connection
    
    user_id = _get_user_id_from_request(request)
    
    conn = get_connection()
    cur = conn.cursor()
    
    if profile.is_default:
        cur.execute("UPDATE autopilot_settings_profiles SET is_default = FALSE WHERE user_id = %s", (user_id,))
    
    cur.execute("""
        UPDATE autopilot_settings_profiles SET
            name = %s, description = %s, delta_excellent = %s, delta_good = %s,
            delta_above_be = %s, delta_high = %s, delta_low_impressions = %s,
            delta_no_sales = %s, low_impressions_threshold = %s,
            min_spend_for_decrement = %s, max_clicks_no_sales = %s,
            max_clicks_for_low_impressions = %s, pause_on_clicks_enabled = %s,
            is_default = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND user_id = %s
    """, (profile.name, profile.description, profile.delta_excellent, profile.delta_good,
          profile.delta_above_be, profile.delta_high, profile.delta_low_impressions,
          profile.delta_no_sales, profile.low_impressions_threshold,
          profile.min_spend_for_decrement, profile.max_clicks_no_sales,
          profile.max_clicks_for_low_impressions, profile.pause_on_clicks_enabled,
          profile.is_default, profile_id, user_id))
    
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    if updated == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"status": "updated", "profile": profile.model_dump()}


@router.delete("/settings-profiles/{account_id}/{profile_id}")
async def delete_settings_profile(account_id: int, profile_id: int, request: Request):
    """Delete a settings profile for the authenticated user. System profiles cannot be deleted."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    user_id = _get_user_id_from_request(request)
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT is_system FROM autopilot_settings_profiles WHERE id = %s AND user_id = %s", (profile_id, user_id))
    row = cur.fetchone()
    if row and row.get("is_system"):
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="I profili di sistema (Default, Conservative) non possono essere eliminati")
    
    cur.execute("UPDATE autopilot_profiles SET settings_profile_id = NULL WHERE settings_profile_id = %s", (profile_id,))
    
    cur.execute("DELETE FROM autopilot_settings_profiles WHERE id = %s AND user_id = %s", (profile_id, user_id))
    deleted = cur.rowcount
    
    conn.commit()
    cur.close()
    conn.close()
    
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"status": "deleted", "id": profile_id}


@router.post("/autopilot-profile/{profile_id}/assign-settings/{settings_profile_id}")
async def assign_settings_to_profile(profile_id: str, settings_profile_id: int):
    """Assign a settings profile to an Amazon autopilot profile."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("UPDATE autopilot_profiles SET settings_profile_id = %s WHERE profile_id = %s", 
                (settings_profile_id, profile_id))
    
    updated = cur.rowcount
    
    if updated == 0:
        cur.execute("""
            SELECT cp.client_account_id 
            FROM client_profiles cp 
            WHERE cp.profile_id = %s 
            LIMIT 1
        """, (profile_id,))
        cp_row = cur.fetchone()
        if not cp_row:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Profile not found")
        
        account_id = cp_row['client_account_id']
        cur.execute("""
            INSERT INTO autopilot_profiles (account_id, profile_id, enabled, cadence, settings_profile_id)
            VALUES (%s, %s, FALSE, 'daily', %s)
            ON CONFLICT (account_id, profile_id) DO UPDATE SET settings_profile_id = %s
        """, (account_id, profile_id, settings_profile_id, settings_profile_id))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return {"status": "assigned", "profile_id": profile_id, "settings_profile_id": settings_profile_id}


@router.delete("/autopilot-profile/{profile_id}/assign-settings")
async def unassign_settings_from_profile(profile_id: str):
    """Remove the settings profile assignment from an Amazon autopilot profile."""
    from db.accounts_db import get_connection
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("UPDATE autopilot_profiles SET settings_profile_id = NULL WHERE profile_id = %s", 
                (profile_id,))
    
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    if updated == 0:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"status": "unassigned", "profile_id": profile_id}


@router.get("/autopilot-profile/{profile_id}/settings")
async def get_profile_settings(profile_id: str):
    """Get the settings profile assigned to an Amazon autopilot profile."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT sp.* FROM autopilot_settings_profiles sp
        JOIN autopilot_profiles ap ON ap.settings_profile_id = sp.id
        WHERE ap.profile_id = %s
    """, (profile_id,))
    
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    if row:
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "delta_excellent": float(row["delta_excellent"]),
            "delta_good": float(row["delta_good"]),
            "delta_above_be": float(row["delta_above_be"]),
            "delta_high": float(row["delta_high"]),
            "delta_low_impressions": float(row["delta_low_impressions"]),
            "delta_no_sales": float(row["delta_no_sales"]),
            "low_impressions_threshold": int(row["low_impressions_threshold"]),
            "min_spend_for_decrement": float(row["min_spend_for_decrement"]),
            "is_default": row["is_default"]
        }
    else:
        return AutopilotSettingsModel().model_dump()


class ScheduleActionsRequest(BaseModel):
    hours: int


@router.post("/schedule-actions/{account_id}")
async def schedule_actions(account_id: int, request: ScheduleActionsRequest):
    """Schedule all PLANNED actions to be executed in X hours."""
    from db.accounts_db import get_connection
    
    if request.hours not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Hours must be 1, 2, or 3")
    
    planned_for = datetime.now() + timedelta(hours=request.hours)
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE planned_actions 
        SET planned_for = %s 
        WHERE account_id = %s AND status = 'PLANNED'
    """, (planned_for, account_id))
    
    updated = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    
    return {
        "status": "scheduled",
        "actions_scheduled": updated,
        "planned_for": planned_for.isoformat(),
        "hours": request.hours
    }


@router.get("/due-actions/{account_id}")
async def get_due_actions(account_id: int):
    """Get actions that are due for execution (planned_for <= now)."""
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM planned_actions 
        WHERE account_id = %s AND status = 'PLANNED' AND planned_for <= CURRENT_TIMESTAMP
        ORDER BY planned_for
    """, (account_id,))
    
    actions = cur.fetchall()
    cur.close()
    conn.close()
    
    return {"due_actions": [dict(a) for a in actions], "count": len(actions)}


class BigBangRequest(BaseModel):
    delay_minutes: int = 15
    ad_product: str = "ALL"  # SP, SB, or ALL
    recurring_mode: str = "recurring_1h"  # recurring_1h, recurring_3h, recurring_1d, recurring_3d, recurring_5d


@router.post("/big-bang/{account_id}")
async def start_big_bang(account_id: int, request: BigBangRequest, background_tasks: BackgroundTasks):
    """BIG BANG: Execute steps 1-5 in sequence, then schedule step 6 after delay_minutes."""
    from db.accounts_db import (
        create_big_bang_job, update_big_bang_job, get_active_big_bang_job
    )
    
    if request.delay_minutes not in [15, 30, 60, 120, 180]:
        raise HTTPException(status_code=400, detail="delay_minutes must be 15, 30, 60, 120, or 180")
    
    if request.ad_product not in ["SP", "SB", "ALL"]:
        raise HTTPException(status_code=400, detail="ad_product must be SP, SB, or ALL")
    
    valid_recurring_modes = ["recurring_1h", "recurring_3h", "recurring_1d", "recurring_3d", "recurring_5d"]
    if request.recurring_mode not in valid_recurring_modes:
        raise HTTPException(status_code=400, detail=f"recurring_mode must be one of: {valid_recurring_modes}")
    
    # Map recurring mode to interval (in hours for 1h, days for others)
    # We store interval_days as: 0 = 1 hour (special case), 1 = 1 day, 3 = 3 days, 5 = 5 days
    recurring_interval_map = {
        "recurring_1h": 0,   # 1 hour
        "recurring_3h": -3,  # 3 hours (negative = hours)
        "recurring_1d": 1,   # 1 day
        "recurring_3d": 3,   # 3 days
        "recurring_5d": 5    # 5 days
    }
    recurring_interval_days = recurring_interval_map[request.recurring_mode]
    
    active_job = get_active_big_bang_job(account_id)
    if active_job:
        raise HTTPException(status_code=400, detail=f"Job Nexus già attivo (id={active_job['id']}, status={active_job['status']})")
    
    job = create_big_bang_job(account_id, request.delay_minutes, request.ad_product, request.recurring_mode, recurring_interval_days)
    job_id = job['id']
    ad_product = request.ad_product
    
    def run_big_bang_sync():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_big_bang_async(job_id, account_id, recurring_interval_days, ad_product))
        finally:
            loop.close()
    
    background_tasks.add_task(run_big_bang_sync)
    
    label = "SP" if ad_product == "SP" else "SB" if ad_product == "SB" else "SP+SB"
    recurring_labels = {
        "recurring_1h": " (ogni ora)",
        "recurring_3h": " (ogni 3 ore)",
        "recurring_1d": " (ogni giorno)",
        "recurring_3d": " (ogni 3 giorni)",
        "recurring_5d": " (ogni 5 giorni)"
    }
    recurring_msg = recurring_labels.get(request.recurring_mode, "")
    delay_display = "1 ora" if recurring_interval_days == 0 else "3 ore" if recurring_interval_days == -3 else f"{recurring_interval_days} giorni"
    
    return {
        "job_id": job_id,
        "status": "started",
        "recurring_interval_days": recurring_interval_days,
        "ad_product": request.ad_product,
        "recurring_mode": request.recurring_mode,
        "message": f"Nexus {label} avviato{recurring_msg}. Esecuzione tra {delay_display}."
    }


async def run_big_bang_async(job_id: int, account_id: int, recurring_interval_days: int, ad_product: str = "ALL"):
    """Execute BIG BANG steps asynchronously based on ad_product (SP, SB, or ALL)."""
    from db.accounts_db import update_big_bang_job, get_recent_reports_status
    import asyncio
    
    is_sp = ad_product in ["SP", "ALL"]
    is_sb = ad_product in ["SB", "ALL"]
    label = "SP" if ad_product == "SP" else "SB" if ad_product == "SB" else "SP+SB"
    
    delay_minutes = 60
    
    total_steps = 2
    if is_sp: total_steps += 3
    if is_sb: total_steps += 1
    total_steps += 1
    completed_steps = 0
    
    def pct():
        return min(99, int((completed_steps / total_steps) * 100))
    
    try:
        update_big_bang_job(job_id, current_phase=1, phase_status='running', phase_message='Fase 1 - Raccolta dati...', progress_pct=pct())
        result1 = await step_fetch_asins(account_id)
        completed_steps += 1
        update_big_bang_job(job_id, current_phase=1, phase_status='completed', phase_message='Fase 1 completata', progress_pct=pct())
        
        update_big_bang_job(job_id, current_phase=2, phase_status='running', phase_message='Fase 2 - Analisi performance...', progress_pct=pct())
        result2 = await step_request_reports(account_id)
        reports_requested = result2.get('reports_requested', 0)
        reports_cached = result2.get('reports_cached', 0)
        all_cached = result2.get('all_cached', False)
        
        if all_cached:
            completed_steps += 1
            update_big_bang_job(job_id, current_phase=2, phase_status='completed', 
                               phase_message='Fase 2 completata', progress_pct=pct())
        elif reports_requested > 0:
            update_big_bang_job(job_id, current_phase=2, phase_status='completed', phase_message='Fase 2 - Elaborazione in corso...', progress_pct=pct())
            
            max_wait_minutes = 45
            poll_interval_seconds = 30
            waited_seconds = 0
            
            while waited_seconds < max_wait_minutes * 60:
                report_status = get_recent_reports_status(account_id, minutes=720)
                pending = report_status.get('pending', 0)
                parsed = report_status.get('parsed', 0)
                
                if report_status.get('all_parsed', False):
                    completed_steps += 1
                    update_big_bang_job(job_id, current_phase=2, phase_status='completed', 
                                       phase_message='Fase 2 completata', progress_pct=pct())
                    break
                
                elapsed_min = waited_seconds // 60
                update_big_bang_job(job_id, current_phase=2, phase_status='waiting', 
                                   phase_message=f'Fase 2 - Elaborazione in corso... ({elapsed_min} min)', progress_pct=pct())
                
                await asyncio.sleep(poll_interval_seconds)
                waited_seconds += poll_interval_seconds
            else:
                report_status = get_recent_reports_status(account_id, minutes=720)
                if report_status.get('pending', 0) > 0:
                    raise Exception(f"Timeout elaborazione dopo {max_wait_minutes} min.")
        else:
            completed_steps += 1
            update_big_bang_job(job_id, current_phase=2, phase_status='completed', phase_message='Fase 2 completata', progress_pct=pct())
        
        current_phase = 3
        
        if is_sp:
            update_big_bang_job(job_id, current_phase=current_phase, phase_status='running', phase_message=f'Fase {current_phase} - Analisi campagne SP...', progress_pct=pct())
            result_inv = await step_fetch_sp_inventory(account_id)
            completed_steps += 1
            update_big_bang_job(job_id, current_phase=current_phase, phase_status='completed', 
                               phase_message=f'Fase {current_phase} completata', progress_pct=pct())
            current_phase += 1
            
            update_big_bang_job(job_id, current_phase=current_phase, phase_status='running', phase_message=f'Fase {current_phase} - Pianificazione azioni SP...', progress_pct=pct())
            result4 = await step_plan_auto(account_id)
            result5 = await step_plan_sp_manual(account_id)
            completed_steps += 2
            total_sp_actions = result4.get('total_actions', 0) + result5.get('total_actions', 0)
            update_big_bang_job(job_id, current_phase=current_phase, phase_status='completed', phase_message=f'Fase {current_phase} completata - {total_sp_actions} azioni', progress_pct=pct())
            current_phase += 1
        
        if is_sb:
            update_big_bang_job(job_id, current_phase=current_phase, phase_status='running', phase_message=f'Fase {current_phase} - Analisi campagne SB...', progress_pct=pct())
            try:
                result_sb_inv = await step_fetch_sb_inventory(account_id)
                sb_inventory_count = result_sb_inv.get('total_targets', 0) or result_sb_inv.get('total_entities', 0) or 0
                result6 = await step_plan_sb(account_id)
                total_sb_actions = result6.get('total_actions', 0)
                
                if sb_inventory_count == 0 and total_sb_actions == 0:
                    update_big_bang_job(job_id, current_phase=current_phase, phase_status='completed',
                                       phase_message=f'Fase {current_phase} completata - Nessuna campagna SB', progress_pct=pct())
                else:
                    update_big_bang_job(job_id, current_phase=current_phase, phase_status='completed',
                                       phase_message=f'Fase {current_phase} completata - {total_sb_actions} azioni SB', progress_pct=pct())
            except Exception as sb_err:
                update_big_bang_job(job_id, current_phase=current_phase, phase_status='completed',
                                   phase_message=f'Fase {current_phase} - SB saltato', progress_pct=pct())
            completed_steps += 1
            current_phase += 1
        
        execute_at = datetime.now() + timedelta(minutes=delay_minutes)
        update_big_bang_job(
            job_id, 
            status='SCHEDULED', 
            current_phase=current_phase, 
            phase_status='scheduled',
            phase_message=f"Esecuzione bid tra {delay_minutes} min ({execute_at.strftime('%H:%M')})",
            execute_at=execute_at,
            progress_pct=pct()
        )
        
    except Exception as e:
        update_big_bang_job(
            job_id, 
            status='FAILED', 
            phase_status='failed',
            error_message=str(e)
        )


@router.get("/big-bang/active/{account_id}")
async def get_active_big_bang(account_id: int):
    """Get active BIG BANG job for account."""
    from db.accounts_db import get_active_big_bang_job
    
    job = get_active_big_bang_job(account_id)
    return {"job": job}


@router.get("/big-bang/history/{account_id}")
async def get_big_bang_history(account_id: int):
    """Get BIG BANG job history for account."""
    from db.accounts_db import get_big_bang_jobs_for_account
    
    jobs = get_big_bang_jobs_for_account(account_id)
    return {"jobs": jobs}


@router.get("/big-bang/{job_id}/status")
async def get_big_bang_status(job_id: int):
    """Get BIG BANG job status."""
    from db.accounts_db import get_big_bang_job
    
    job = get_big_bang_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job non trovato")
    
    return job


@router.post("/big-bang/{job_id}/cancel")
async def cancel_big_bang(job_id: int):
    """Cancel a running, scheduled or waiting BIG BANG job."""
    from db.accounts_db import get_big_bang_job, update_big_bang_job
    
    job = get_big_bang_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job non trovato")
    
    if job['status'] not in ['RUNNING', 'SCHEDULED', 'WAITING', 'EXECUTING']:
        raise HTTPException(status_code=400, detail="Job non annullabile (stato: {})".format(job['status']))
    
    update_big_bang_job(
        job_id,
        status='CANCELLED',
        phase_status='cancelled',
        phase_message='Annullato dall\'utente'
    )
    
    return {"success": True, "message": "Nexus annullato"}
