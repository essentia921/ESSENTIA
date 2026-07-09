import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.app.core.database import get_db
from backend.app.services.amazon import (
    get_amazon_profiles, 
    get_amazon_campaigns,
    get_api_url_for_country,
    AmazonAdsService,
    get_amazon_keywords_and_targets
)
from backend.app.services.amazon_reports import (
    get_date_range,
    create_report as amazon_create_report,
    read_report_content
)
from db.accounts_db import (
    get_all_client_accounts, 
    get_client_profiles, 
    get_profile_info, 
    get_client_tokens, 
    save_client_tokens,
    create_report as db_create_report,
    get_reports_for_profile,
    get_all_reports,
    get_report_by_id,
    delete_all_reports as db_delete_all_reports,
    delete_reports_by_ids as db_delete_reports_by_ids,
    save_planned_bid_action,
    get_planned_actions,
    clear_planned_actions,
    get_completed_reports_for_analysis,
    mark_actions_executed,
    get_planned_actions_by_ids,
    delete_planned_actions_by_ids,
    ensure_target_type_column,
    get_profiles_with_completed_reports,
    get_profiles_without_reports
)
from backend.app.services.bid_analyzer import analyze_targets
from backend.app.services.amazon_ads.update_bids import get_all_target_bids
import requests
import os

AMAZON_CLIENT_ID = os.getenv("AMAZON_ADS_CLIENT_ID")

logger = logging.getLogger(__name__)

router = APIRouter()


class ProfileWithAccount(BaseModel):
    accountId: int
    accountName: str
    profileId: str
    countryCode: str
    marketplace: Optional[str] = None
    region: Optional[str] = None


class CampaignWithProduct(BaseModel):
    campaignId: str
    campaignName: str
    state: str
    budget: Optional[float] = None
    asin: Optional[str] = None
    productTitle: Optional[str] = None


def get_current_user_from_token(authorization: str, db: Session):
    from backend.app.core.security import decode_access_token
    from backend.app.models.user import User
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == int(user_id)).first()
    return user


@router.get("/profiles")
async def get_all_profiles(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    accounts = get_all_client_accounts(user_id=user.id)
    
    all_profiles = []
    
    for account in accounts:
        account_id = account.get("id")
        account_name = account.get("client_name", f"Account {account_id}")
        
        cached_profiles = get_client_profiles(account_id)
        
        if cached_profiles:
            for profile in cached_profiles:
                profile_data = profile.get("profile_data", profile) if isinstance(profile, dict) else profile
                all_profiles.append({
                    "accountId": account_id,
                    "accountName": account_name,
                    "profileId": str(profile_data.get("profileId") or profile_data.get("profile_id", "")),
                    "countryCode": profile_data.get("countryCode") or profile_data.get("country_code", ""),
                    "marketplace": profile_data.get("marketplace") or profile_data.get("marketplaceString") or profile_data.get("marketplace_string", ""),
                    "region": profile_data.get("region") or profile_data.get("_region", ""),
                })
        else:
            profiles, status = get_amazon_profiles(account_id)
            if profiles:
                for profile in profiles:
                    all_profiles.append({
                        "accountId": account_id,
                        "accountName": account_name,
                        "profileId": str(profile.get("profileId", "")),
                        "countryCode": profile.get("countryCode", ""),
                        "marketplace": profile.get("marketplace") or profile.get("marketplaceString", ""),
                        "region": profile.get("region", ""),
                    })
    
    return all_profiles


@router.get("/campaigns")
async def get_campaigns_with_products(
    account_id: int,
    profile_id: str,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    profile_info = get_profile_info(account_id, profile_id)
    api_url = None
    if profile_info:
        api_url = profile_info.get('api_url')
        if not api_url and profile_info.get('country_code'):
            api_url = get_api_url_for_country(profile_info['country_code'])
    
    if not api_url:
        api_url = "https://advertising-api-eu.amazon.com"
    
    campaigns, status = get_amazon_campaigns(account_id, profile_id, api_url)
    
    if status:
        status_code = status.get("code", "UNKNOWN")
        if status_code == "NO_TOKENS":
            raise HTTPException(status_code=424, detail="Account not connected to Amazon Ads")
        elif status_code == "AUTH_FAILED":
            raise HTTPException(status_code=424, detail="Amazon authentication expired")
        elif status_code == "API_ERROR":
            raise HTTPException(status_code=502, detail=f"Amazon API error: {status.get('error', 'Unknown error')}")
    
    tokens = get_client_tokens(account_id)
    if not tokens:
        raise HTTPException(status_code=424, detail="No tokens available")
    
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    
    if not access_token or not refresh_token:
        raise HTTPException(status_code=424, detail="Invalid tokens")
    
    service = AmazonAdsService(access_token, refresh_token, account_id)
    
    campaign_data = []
    for campaign in campaigns:
        campaign_id = campaign.get("campaignId")
        campaign_name = campaign.get("name", "")
        state = campaign.get("state", "")
        budget = campaign.get("budget", {})
        budget_value = budget.get("budget") if isinstance(budget, dict) else budget
        campaign_data.append({
            "campaignId": str(campaign_id),
            "campaignName": campaign_name,
            "state": state,
            "budget": budget_value,
            "asin": None,
        })
    
    def fetch_asin(idx, campaign_id):
        try:
            return idx, get_campaign_asin(service, profile_id, campaign_id, api_url)
        except Exception as e:
            logger.warning(f"Could not get ASIN for campaign {campaign_id}: {e}")
            return idx, None
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for idx, campaign in enumerate(campaign_data):
            futures.append(executor.submit(fetch_asin, idx, campaign["campaignId"]))
        
        for future in as_completed(futures):
            idx, asin = future.result()
            campaign_data[idx]["asin"] = asin
    
    updated_tokens = service.get_updated_tokens()
    if updated_tokens:
        new_access, new_refresh, expires_at = updated_tokens
        save_client_tokens(account_id, new_access, new_refresh, expires_at)
    
    return campaign_data


def get_campaign_asin(service: AmazonAdsService, profile_id: str, campaign_id: str, api_url: str) -> Optional[str]:
    try:
        ad_groups_url = f"{api_url}/sp/adGroups/list"
        headers = {
            "Authorization": f"Bearer {service.access_token}",
            "Amazon-Advertising-API-ClientId": AMAZON_CLIENT_ID,
            "Amazon-Advertising-API-Scope": profile_id,
            "Content-Type": "application/vnd.spAdGroup.v3+json",
            "Accept": "application/vnd.spAdGroup.v3+json",
        }
        payload = {
            "campaignIdFilter": {
                "include": [campaign_id]
            }
        }
        
        response = service._make_request(ad_groups_url, headers, method="POST", json_data=payload)
        data = response.json()
        
        ad_groups = data.get("adGroups", [])
        
        if not ad_groups:
            return None
        
        ad_group_id = ad_groups[0].get("adGroupId")
        
        product_ads_url = f"{api_url}/sp/productAds/list"
        headers["Content-Type"] = "application/vnd.spProductAd.v3+json"
        headers["Accept"] = "application/vnd.spProductAd.v3+json"
        payload = {
            "adGroupIdFilter": {
                "include": [ad_group_id]
            }
        }
        
        response = service._make_request(product_ads_url, headers, method="POST", json_data=payload)
        data = response.json()
        
        product_ads = data.get("productAds", [])
        
        if product_ads:
            return product_ads[0].get("asin")
        
        return None
        
    except Exception as e:
        logger.warning(f"Error getting ASIN for campaign {campaign_id}: {e}")
        return None


class GenerateReportRequest(BaseModel):
    account_id: int
    profile_id: str
    report_type: str


class ReportResponse(BaseModel):
    id: int
    report_id: str
    report_type: str
    profile_id: str
    start_date: str
    end_date: str
    status: str
    created_at: str
    completed_at: Optional[str] = None


@router.post("/reports/generate")
async def generate_report(
    request: GenerateReportRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if request.report_type not in ["14D", "30D"]:
        raise HTTPException(status_code=400, detail="Invalid report type. Use '14D' or '30D'")
    
    days = 14 if request.report_type == "14D" else 30
    report_type = f"SP_TARGETING_{request.report_type}"
    start_date, end_date = get_date_range(days)
    
    profile_info = get_profile_info(request.account_id, request.profile_id)
    api_url = None
    if profile_info:
        api_url = profile_info.get('api_url')
        if not api_url and profile_info.get('country_code'):
            api_url = get_api_url_for_country(profile_info['country_code'])
    
    if not api_url:
        api_url = "https://advertising-api-eu.amazon.com"
    
    tokens = get_client_tokens(request.account_id)
    if not tokens:
        raise HTTPException(status_code=424, detail="Account not connected to Amazon Ads")
    
    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=424, detail="Invalid tokens")
    
    try:
        report_id = amazon_create_report(
            access_token=access_token,
            profile_id=request.profile_id,
            api_url=api_url,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date
        )
        
        db_report = db_create_report(
            account_id=request.account_id,
            profile_id=request.profile_id,
            report_id=report_id,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "success": True,
            "report_id": report_id,
            "report_type": report_type,
            "start_date": start_date,
            "end_date": end_date,
            "status": "PENDING"
        }
    except Exception as e:
        logger.error(f"Error creating report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create report: {str(e)}")


@router.post("/reports/generate-all")
async def generate_reports_for_all_profiles(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Generate 14D and 30D reports for all profiles across all accounts."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    accounts = get_all_client_accounts(user_id=user.id)
    
    total_reports_created = 0
    total_profiles = 0
    errors = []
    results = []
    
    for acc in accounts:
        acc_id = acc.get("id")
        acc_name = acc.get("client_name", f"Account {acc_id}")
        
        tokens = get_client_tokens(acc_id)
        if not tokens or not tokens.get("access_token"):
            errors.append({"account": acc_name, "error": "Account not connected"})
            continue
        
        access_token = tokens.get("access_token")
        
        profiles, status = get_amazon_profiles(acc_id)
        if not profiles:
            errors.append({"account": acc_name, "error": f"Could not fetch profiles: {status}"})
            continue
        
        for profile in profiles:
            profile_id = profile.get("profileId") or profile.get("profile_id")
            if not profile_id:
                logger.warning(f"Skipping profile with no profile_id in account {acc_name}")
                continue
            
            profile_id = str(profile_id)
            country_code = profile.get("countryCode") or profile.get("country_code", "")
            
            allowed_countries = {"US", "GB", "UK", "IT"}
            if country_code not in allowed_countries:
                logger.info(f"Skipping profile {profile_id} - country {country_code} not in {allowed_countries}")
                continue
            
            api_url = get_api_url_for_country(country_code) or "https://advertising-api-eu.amazon.com"
            
            total_profiles += 1
            profile_reports = {"profile_id": profile_id, "country_code": country_code, "reports": []}
            
            for report_type_suffix in ["14D", "30D"]:
                days = 14 if report_type_suffix == "14D" else 30
                report_type = f"SP_TARGETING_{report_type_suffix}"
                start_date, end_date = get_date_range(days)
                
                try:
                    report_id = amazon_create_report(
                        access_token=access_token,
                        profile_id=profile_id,
                        api_url=api_url,
                        report_type=report_type,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    db_create_report(
                        account_id=acc_id,
                        profile_id=profile_id,
                        report_id=report_id,
                        report_type=report_type,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    total_reports_created += 1
                    profile_reports["reports"].append({
                        "type": report_type_suffix,
                        "report_id": report_id,
                        "status": "PENDING"
                    })
                    logger.info(f"Created {report_type_suffix} report for profile {profile_id} ({country_code})")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error creating {report_type_suffix} report for profile {profile_id}: {error_msg}")
                    profile_reports["reports"].append({
                        "type": report_type_suffix,
                        "error": error_msg
                    })
            
            if profile_reports["reports"]:
                results.append(profile_reports)
    
    return {
        "success": total_reports_created > 0,
        "total_profiles": total_profiles,
        "total_reports_created": total_reports_created,
        "results": results,
        "errors": errors
    }


@router.get("/reports")
async def get_reports(
    profile_id: Optional[str] = None,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    reports = get_reports_for_profile(profile_id) if profile_id else get_all_reports()
    
    result = []
    for r in reports:
        result.append({
            "id": r.get("id"),
            "report_id": r.get("report_id"),
            "report_type": r.get("report_type"),
            "profile_id": r.get("profile_id"),
            "start_date": str(r.get("start_date")) if r.get("start_date") else None,
            "end_date": str(r.get("end_date")) if r.get("end_date") else None,
            "status": r.get("status"),
            "created_at": str(r.get("created_at")) if r.get("created_at") else None,
            "completed_at": str(r.get("completed_at")) if r.get("completed_at") else None,
        })
    
    return result


@router.delete("/reports")
async def delete_all_reports_endpoint(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Delete all reports from database."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        deleted_count = db_delete_all_reports()
        logger.info(f"Deleted {deleted_count} reports")
        return {
            "success": True,
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error deleting reports: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete reports: {str(e)}")




class DeleteReportsRequest(BaseModel):
    report_ids: List[int]


@router.post("/reports/delete-selected")
async def delete_selected_reports(
    request: DeleteReportsRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Delete selected reports by IDs."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        deleted_count = db_delete_reports_by_ids(request.report_ids)
        logger.info(f"Deleted {deleted_count} selected reports")
        return {
            "success": True,
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Error deleting selected reports: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete reports: {str(e)}")


@router.get("/reports/{report_id}/content")
async def get_report_content(
    report_id: str,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    report = get_report_by_id(report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if report.get("status") != "COMPLETED":
        raise HTTPException(status_code=400, detail="Report not completed yet")
    
    report_data = report.get("report_data")
    if report_data:
        if isinstance(report_data, str):
            try:
                return json.loads(report_data)
            except json.JSONDecodeError:
                return {"raw": report_data}
        return report_data
    
    raise HTTPException(status_code=404, detail="Report data not found")


class AnalyzeRequest(BaseModel):
    profile_id: str
    account_id: int


@router.post("/analyze-reports")
async def analyze_reports(
    request: AnalyzeRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    report_14d, report_30d = get_completed_reports_for_analysis(request.profile_id)
    
    if not report_14d and not report_30d:
        raise HTTPException(status_code=400, detail="No completed reports found for this profile. Generate 14D and 30D reports first.")
    
    data_14d = report_14d.get("report_data", []) if report_14d else []
    data_30d = report_30d.get("report_data", []) if report_30d else []
    
    if isinstance(data_14d, dict):
        data_14d = data_14d.get("rows", data_14d.get("data", []))
    if isinstance(data_30d, dict):
        data_30d = data_30d.get("rows", data_30d.get("data", []))
    
    profile_info = get_profile_info(request.account_id, request.profile_id)
    api_url = None
    if profile_info:
        api_url = profile_info.get('api_url')
        if not api_url and profile_info.get('country_code'):
            api_url = get_api_url_for_country(profile_info['country_code'])
    if not api_url:
        api_url = "https://advertising-api-eu.amazon.com"
    
    tokens = get_client_tokens(request.account_id)
    discovery_data = {}
    
    if tokens and tokens.get("access_token") and tokens.get("refresh_token"):
        try:
            service = AmazonAdsService(tokens["access_token"], tokens["refresh_token"], request.account_id)
            
            campaigns, _ = get_amazon_campaigns(request.account_id, request.profile_id, api_url)
            
            if campaigns:
                for campaign in campaigns:
                    campaign_id = str(campaign.get("campaignId", ""))
                    campaign_name = campaign.get("name", "")
                    
                    asin = None
                    try:
                        asin = get_campaign_asin(service, request.profile_id, campaign_id, api_url)
                    except Exception as e:
                        logger.warning(f"Could not get ASIN for campaign {campaign_id}: {e}")
                    
                    discovery_data[campaign_id] = {
                        "campaign_name": campaign_name,
                        "asin": asin
                    }
                
                updated_tokens = service.get_updated_tokens()
                if updated_tokens:
                    new_access, new_refresh, expires_at = updated_tokens
                    save_client_tokens(request.account_id, new_access, new_refresh, expires_at)
        except Exception as e:
            logger.warning(f"Could not load campaign discovery data: {e}")
    
    all_target_ids = set()
    for row in data_14d:
        kw_id = row.get("keywordId")
        tgt_id = row.get("targetId")
        if kw_id:
            all_target_ids.add(str(kw_id))
        if tgt_id:
            all_target_ids.add(str(tgt_id))
    for row in data_30d:
        kw_id = row.get("keywordId")
        tgt_id = row.get("targetId")
        if kw_id:
            all_target_ids.add(str(kw_id))
        if tgt_id:
            all_target_ids.add(str(tgt_id))
    
    fresh_tokens = get_client_tokens(request.account_id)
    access_token = fresh_tokens.get("access_token") if fresh_tokens else None
    
    live_bids = {}
    targets_map = {}
    campaign_states_map = {}
    if all_target_ids and access_token:
        try:
            logger.info(f"Fetching live bids for {len(all_target_ids)} targets from profile {request.profile_id}")
            live_bids = get_all_target_bids(
                access_token,
                request.profile_id,
                list(all_target_ids),
                api_url
            )
            logger.info(f"Got {len(live_bids)} live bids")
        except Exception as e:
            logger.warning(f"Could not fetch live bids: {e}")
    
    keywords_map = {}
    if access_token:
        try:
            keywords_map, targets_map, error = get_amazon_keywords_and_targets(
                request.account_id, request.profile_id, api_url
            )
            if error:
                logger.warning(f"Error fetching keywords/targets: {error}")
            campaign_states_map = keywords_map.pop("_campaign_states", {})
            logger.info(f"Got {len(keywords_map)} keywords, {len(targets_map)} targets, {len(campaign_states_map)} campaign states")
        except Exception as e:
            logger.warning(f"Could not fetch keywords/targets: {e}")
    
    actions = analyze_targets(data_14d, data_30d, discovery_data, live_bids, profile_id=request.profile_id, targets_map=targets_map, campaign_states_map=campaign_states_map, keywords_map=keywords_map)
    
    clear_planned_actions(request.profile_id)
    
    ensure_target_type_column()
    
    saved_count = 0
    for action in actions:
        save_planned_bid_action(
            profile_id=request.profile_id,
            account_id=request.account_id,
            campaign_id=action.get("campaign_id", ""),
            campaign_name=action.get("campaign_name", ""),
            ad_group_id=action.get("ad_group_id", ""),
            keyword_id=action.get("keyword_id", ""),
            asin=action.get("asin", ""),
            target_keyword=action.get("keyword", ""),
            current_bid=action.get("current_bid"),
            delta_bid=action.get("delta_bid", 0),
            tipo_azione=action.get("tipo_azione", ""),
            report_14d_id=report_14d.get("report_id") if report_14d else None,
            report_30d_id=report_30d.get("report_id") if report_30d else None,
            target_type=action.get("target_type", "keyword"),
            acos_14d=action.get("acos_14d"),
            acos_30d=action.get("acos_30d")
        )
        saved_count += 1
    
    return {
        "success": True,
        "actions_count": saved_count,
        "report_14d_used": report_14d.get("report_id") if report_14d else None,
        "report_30d_used": report_30d.get("report_id") if report_30d else None
    }


@router.post("/analyze-all")
async def analyze_all_profiles(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Analyze ACOS for ALL profiles that have completed reports."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    profiles_with_reports = get_profiles_with_completed_reports()
    
    if not profiles_with_reports:
        raise HTTPException(status_code=400, detail="Nessun profilo con report completati trovato")
    
    results = []
    total_actions = 0
    
    for profile in profiles_with_reports:
        profile_id = profile.get("profile_id")
        account_id = profile.get("account_id")
        country_code = profile.get("country_code")
        account_name = profile.get("account_name", "")
        
        try:
            report_14d, report_30d = get_completed_reports_for_analysis(profile_id)
            
            if not report_14d and not report_30d:
                continue
            
            data_14d = report_14d.get("report_data", []) if report_14d else []
            data_30d = report_30d.get("report_data", []) if report_30d else []
            
            if isinstance(data_14d, dict):
                data_14d = data_14d.get("rows", data_14d.get("data", []))
            if isinstance(data_30d, dict):
                data_30d = data_30d.get("rows", data_30d.get("data", []))
            
            profile_info = get_profile_info(account_id, profile_id)
            api_url = None
            if profile_info:
                api_url = profile_info.get('api_url')
                if not api_url and profile_info.get('country_code'):
                    api_url = get_api_url_for_country(profile_info['country_code'])
            if not api_url:
                api_url = "https://advertising-api-eu.amazon.com"
            
            tokens = get_client_tokens(account_id)
            discovery_data = {}
            
            if tokens and tokens.get("access_token") and tokens.get("refresh_token"):
                try:
                    service = AmazonAdsService(tokens["access_token"], tokens["refresh_token"], account_id)
                    
                    campaigns, _ = get_amazon_campaigns(account_id, profile_id, api_url)
                    
                    if campaigns:
                        for campaign in campaigns:
                            campaign_id = str(campaign.get("campaignId", ""))
                            campaign_name = campaign.get("name", "")
                            
                            asin = None
                            try:
                                asin = get_campaign_asin(service, profile_id, campaign_id, api_url)
                            except Exception as e:
                                logger.warning(f"Could not get ASIN for campaign {campaign_id}: {e}")
                            
                            discovery_data[campaign_id] = {
                                "campaign_name": campaign_name,
                                "asin": asin
                            }
                        
                        updated_tokens = service.get_updated_tokens()
                        if updated_tokens:
                            new_access, new_refresh, expires_at = updated_tokens
                            save_client_tokens(account_id, new_access, new_refresh, expires_at)
                except Exception as e:
                    logger.warning(f"Could not load campaign discovery data for profile {profile_id}: {e}")
            
            all_target_ids = set()
            for row in data_14d:
                kw_id = row.get("keywordId")
                tgt_id = row.get("targetId")
                if kw_id:
                    all_target_ids.add(str(kw_id))
                if tgt_id:
                    all_target_ids.add(str(tgt_id))
            for row in data_30d:
                kw_id = row.get("keywordId")
                tgt_id = row.get("targetId")
                if kw_id:
                    all_target_ids.add(str(kw_id))
                if tgt_id:
                    all_target_ids.add(str(tgt_id))
            
            fresh_tokens = get_client_tokens(account_id)
            access_token = fresh_tokens.get("access_token") if fresh_tokens else None
            
            live_bids = {}
            targets_map = {}
            campaign_states_map = {}
            if all_target_ids and access_token:
                try:
                    logger.info(f"Fetching live bids for {len(all_target_ids)} targets from profile {profile_id}")
                    live_bids = get_all_target_bids(
                        access_token,
                        profile_id,
                        list(all_target_ids),
                        api_url
                    )
                    logger.info(f"Got {len(live_bids)} live bids for profile {profile_id}")
                except Exception as e:
                    logger.warning(f"Could not fetch live bids for profile {profile_id}: {e}")
            
            keywords_map = {}
            if access_token:
                try:
                    keywords_map, targets_map, error = get_amazon_keywords_and_targets(
                        account_id, profile_id, api_url
                    )
                    if error:
                        logger.warning(f"Error fetching keywords/targets for profile {profile_id}: {error}")
                    campaign_states_map = keywords_map.pop("_campaign_states", {})
                    logger.info(f"Got {len(keywords_map)} keywords, {len(targets_map)} targets, {len(campaign_states_map)} campaign states for profile {profile_id}")
                except Exception as e:
                    logger.warning(f"Could not fetch keywords/targets for profile {profile_id}: {e}")
            
            actions = analyze_targets(data_14d, data_30d, discovery_data, live_bids, profile_id=profile_id, targets_map=targets_map, campaign_states_map=campaign_states_map, keywords_map=keywords_map)
            
            clear_planned_actions(profile_id)
            
            ensure_target_type_column()
            
            saved_count = 0
            for action in actions:
                save_planned_bid_action(
                    profile_id=profile_id,
                    account_id=account_id,
                    campaign_id=action.get("campaign_id", ""),
                    campaign_name=action.get("campaign_name", ""),
                    ad_group_id=action.get("ad_group_id", ""),
                    keyword_id=action.get("keyword_id", ""),
                    asin=action.get("asin", ""),
                    target_keyword=action.get("keyword", ""),
                    current_bid=action.get("current_bid"),
                    delta_bid=action.get("delta_bid", 0),
                    tipo_azione=action.get("tipo_azione", ""),
                    report_14d_id=report_14d.get("report_id") if report_14d else None,
                    report_30d_id=report_30d.get("report_id") if report_30d else None,
                    target_type=action.get("target_type", "keyword"),
                    acos_14d=action.get("acos_14d"),
                    acos_30d=action.get("acos_30d")
                )
                saved_count += 1
            
            total_actions += saved_count
            results.append({
                "profile_id": profile_id,
                "account_name": account_name,
                "country_code": country_code,
                "actions_count": saved_count,
                "success": True
            })
            
        except Exception as e:
            logger.error(f"Error analyzing profile {profile_id}: {e}")
            results.append({
                "profile_id": profile_id,
                "account_name": account_name,
                "country_code": country_code,
                "actions_count": 0,
                "success": False,
                "error": str(e)
            })
    
    return {
        "success": True,
        "profiles_analyzed": len(results),
        "total_actions": total_actions,
        "details": results
    }


@router.get("/profiles-without-reports")
async def get_profiles_missing_reports(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Get profiles that have NO completed reports (need report generation)."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    profiles = get_profiles_without_reports()
    
    return profiles


@router.get("/planned-actions")
async def get_planned_bid_actions(
    profile_id: Optional[str] = None,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    actions = get_planned_actions(profile_id=profile_id, executed=False)
    
    accounts = get_all_client_accounts(user_id=user.id)
    account_map = {acc.get("id"): acc.get("client_name", f"Account {acc.get('id')}") for acc in accounts}
    
    profile_cache = {}
    for acc in accounts:
        acc_id = acc.get("id")
        cached_profiles = get_client_profiles(acc_id)
        for p in cached_profiles:
            profile_cache[str(p.get("profile_id"))] = {
                "account_id": acc_id,
                "account_name": account_map.get(acc_id, f"Account {acc_id}"),
                "country_code": p.get("country_code", ""),
                "marketplace": p.get("marketplace_id", "")
            }
    
    result = []
    for a in actions:
        pid = str(a.get("profile_id"))
        profile_info = profile_cache.get(pid, {})
        result.append({
            "id": a.get("id"),
            "profile_id": pid,
            "account_id": a.get("account_id") or profile_info.get("account_id"),
            "account_name": profile_info.get("account_name", ""),
            "country_code": profile_info.get("country_code", ""),
            "campaign_id": a.get("campaign_id"),
            "campaign_name": a.get("campaign_name") or "",
            "keyword_id": a.get("keyword_id"),
            "asin": a.get("asin"),
            "target": a.get("target_keyword"),
            "current_bid": float(a.get("current_bid")) if a.get("current_bid") else None,
            "delta_bid": float(a.get("delta_bid")) if a.get("delta_bid") else 0,
            "tipo_azione": a.get("tipo_azione"),
            "acos_14d": float(a.get("acos_14d")) if a.get("acos_14d") else None,
            "acos_30d": float(a.get("acos_30d")) if a.get("acos_30d") else None,
            "created_at": str(a.get("created_at")) if a.get("created_at") else None,
        })
    
    return result


class DeleteActionsRequest(BaseModel):
    action_ids: List[int]


@router.delete("/planned-actions")
async def delete_planned_bid_actions(
    request: DeleteActionsRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if not request.action_ids:
        raise HTTPException(status_code=400, detail="No actions selected")
    
    deleted_count = delete_planned_actions_by_ids(request.action_ids)
    
    return {"success": True, "deleted_count": deleted_count}


class ExecuteActionsRequest(BaseModel):
    action_ids: List[int]


@router.post("/execute-actions")
async def execute_planned_actions(
    request: ExecuteActionsRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Execute planned bid actions via Amazon Ads API - supports multiple profiles."""
    from backend.app.services.amazon_ads.update_bids import update_keyword_bids, update_target_bids, get_all_target_bids
    from backend.app.services.amazon import get_valid_access_token
    from collections import defaultdict
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if not request.action_ids:
        raise HTTPException(status_code=400, detail="No actions selected")
    
    actions = get_planned_actions_by_ids(request.action_ids)
    
    if not actions:
        raise HTTPException(status_code=404, detail="Actions not found")
    
    for action in actions:
        if action.get("executed"):
            raise HTTPException(status_code=400, detail=f"Action {action.get('id')} already executed")
    
    accounts = get_all_client_accounts(user_id=user.id)
    account_map = {acc.get("id"): acc for acc in accounts}
    
    profile_info_cache = {}
    for acc in accounts:
        acc_id = acc.get("id")
        cached_profiles = get_client_profiles(acc_id)
        for p in cached_profiles:
            pid = str(p.get("profile_id") or "")
            if pid:
                profile_info_cache[pid] = {
                    "account_id": acc_id,
                    "country_code": p.get("country_code", ""),
                }
    
    logger.info(f"Profile cache built with {len(profile_info_cache)} profiles from {len(accounts)} accounts")
    
    actions_by_profile = defaultdict(list)
    for action in actions:
        profile_id = str(action.get("profile_id"))
        actions_by_profile[profile_id].append(action)
    
    total_success = 0
    total_failed = 0
    all_results = []
    profiles_processed = 0
    
    for profile_id, profile_actions in actions_by_profile.items():
        profile_info = profile_info_cache.get(profile_id)
        if not profile_info:
            logger.warning(f"Profile {profile_id} not found in cache, skipping")
            total_failed += len(profile_actions)
            continue
        
        account_id = profile_info.get("account_id")
        country_code = profile_info.get("country_code", "")
        
        access_token, error = get_valid_access_token(account_id)
        if error or not access_token:
            error_msg = error.get("error", "Account not connected") if error else "Account not connected"
            logger.error(f"Token error for account {account_id}: {error_msg}")
            total_failed += len(profile_actions)
            all_results.append({"profile_id": profile_id, "error": error_msg})
            continue
        
        api_url = get_api_url_for_country(country_code) if country_code else "https://advertising-api-eu.amazon.com"
        
        all_target_ids = []
        for action in profile_actions:
            keyword_id = action.get("keyword_id")
            if keyword_id:
                all_target_ids.append(str(keyword_id))
        
        if not all_target_ids:
            logger.warning(f"No valid target IDs for profile {profile_id}")
            continue
        
        current_bids_data = get_all_target_bids(access_token, profile_id, all_target_ids, api_url=api_url)
        logger.info(f"Profile {profile_id}: Fetched bids for {len(current_bids_data)} targets")
        
        keyword_updates = []
        target_updates = []
        keyword_action_ids = []
        target_action_ids = []
        
        for action in profile_actions:
            action_id = action.get("id")
            target_id = str(action.get("keyword_id"))
            delta_bid = float(action.get("delta_bid") or 0)
            
            bid_info = current_bids_data.get(target_id)
            if bid_info is None:
                logger.warning(f"No current bid found for target {target_id}, skipping")
                total_failed += 1
                continue
            
            current_bid = bid_info.get("bid")
            api_target_type = bid_info.get("targetType", "KEYWORD")
            
            new_bid = max(0.02, round(current_bid + delta_bid, 2))
            
            if api_target_type == "KEYWORD":
                keyword_updates.append({
                    "keywordId": target_id,
                    "bid": new_bid
                })
                keyword_action_ids.append(action_id)
            else:
                target_updates.append({
                    "targetId": target_id,
                    "bid": new_bid
                })
                target_action_ids.append(action_id)
        
        if not keyword_updates and not target_updates:
            logger.warning(f"Profile {profile_id}: No valid updates")
            continue
        
        logger.info(f"Profile {profile_id}: {len(keyword_updates)} keywords, {len(target_updates)} targets")
        
        try:
            if keyword_updates:
                kw_result = update_keyword_bids(access_token, profile_id, keyword_updates, api_url=api_url)
                kw_success = kw_result.get("success", 0)
                total_success += kw_success
                total_failed += kw_result.get("failed", 0)
                all_results.append({"profile_id": profile_id, "type": "keywords", "result": kw_result})
                
                if kw_success > 0 and keyword_action_ids:
                    mark_actions_executed(keyword_action_ids)
            
            if target_updates:
                tgt_result = update_target_bids(access_token, profile_id, target_updates, api_url=api_url)
                tgt_success = tgt_result.get("success", 0)
                total_success += tgt_success
                total_failed += tgt_result.get("failed", 0)
                all_results.append({"profile_id": profile_id, "type": "targets", "result": tgt_result})
                
                if tgt_success > 0 and target_action_ids:
                    mark_actions_executed(target_action_ids)
            
            profiles_processed += 1
        except Exception as e:
            logger.error(f"Error executing actions for profile {profile_id}: {e}")
            total_failed += len(keyword_updates) + len(target_updates)
            all_results.append({"profile_id": profile_id, "error": str(e)})
    
    return {
        "success": total_success > 0,
        "executed_count": total_success,
        "failed_count": total_failed,
        "profiles_processed": profiles_processed,
        "total_profiles": len(actions_by_profile),
        "details": {"results": all_results}
    }


@router.get("/executed-actions")
async def get_executed_actions(
    profile_id: Optional[str] = None,
    limit: int = 50,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Get executed bid actions history."""
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    actions = get_planned_actions(profile_id=profile_id, executed=True)
    
    result = []
    for a in actions[:limit]:
        result.append({
            "id": a.get("id"),
            "profile_id": a.get("profile_id"),
            "campaign_id": a.get("campaign_id"),
            "campaign_name": a.get("campaign_name") or "",
            "keyword_id": a.get("keyword_id"),
            "asin": a.get("asin"),
            "target": a.get("target_keyword"),
            "current_bid": float(a.get("current_bid")) if a.get("current_bid") else None,
            "delta_bid": float(a.get("delta_bid")) if a.get("delta_bid") else 0,
            "tipo_azione": a.get("tipo_azione"),
            "created_at": str(a.get("created_at")) if a.get("created_at") else None,
        })
    
    return result


@router.get("/autopilot/status")
async def get_autopilot_status(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Get autopilot status for all profiles."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from backend.app.core.config import settings
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT * FROM autopilot_settings ORDER BY profile_id")
        settings_list = cur.fetchall()
        
        return [
            {
                "profile_id": s["profile_id"],
                "account_id": s.get("account_id"),
                "enabled": s["enabled"],
                "last_run": str(s["last_run"]) if s.get("last_run") else None,
                "next_run": str(s["next_run"]) if s.get("next_run") else None,
                "interval_hours": s.get("interval_hours", 72),
                "mode": s.get("mode", "3d"),
                "is_running": s.get("is_running", False),
            }
            for s in settings_list
        ]
    finally:
        cur.close()
        conn.close()


class AutopilotToggleRequest(BaseModel):
    profile_id: Optional[str] = None
    account_id: Optional[int] = None
    enabled: bool
    mode: str = "3d"  # "test" (2h), "3d" (3 days), "5d" (5 days)


@router.post("/autopilot/toggle")
async def toggle_autopilot(
    request: AutopilotToggleRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Enable or disable autopilot for a profile or all profiles in an account."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from backend.app.core.config import settings
    from datetime import datetime, timedelta
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        mode_intervals = {
            "test": timedelta(hours=2),
            "3d": timedelta(days=3),
            "5d": timedelta(days=5),
        }
        interval = mode_intervals.get(request.mode, timedelta(days=3))
        interval_hours = int(interval.total_seconds() / 3600)
        next_run = datetime.now() + interval if request.enabled else None
        
        profiles_to_update = []
        
        if request.account_id and not request.profile_id:
            cur.execute("""
                SELECT profile_id FROM client_profiles WHERE client_account_id = %s
            """, (request.account_id,))
            profiles_to_update = [r["profile_id"] for r in cur.fetchall()]
        elif request.profile_id:
            profiles_to_update = [request.profile_id]
        
        if not profiles_to_update:
            raise HTTPException(status_code=400, detail="No profile_id or account_id provided")
        
        results = []
        for pid in profiles_to_update:
            cur.execute("""
                INSERT INTO autopilot_settings (profile_id, account_id, enabled, next_run, interval_hours, mode, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (profile_id) DO UPDATE SET
                    account_id = EXCLUDED.account_id,
                    enabled = EXCLUDED.enabled,
                    next_run = EXCLUDED.next_run,
                    interval_hours = EXCLUDED.interval_hours,
                    mode = EXCLUDED.mode,
                    updated_at = NOW()
                RETURNING *
            """, (pid, request.account_id, request.enabled, next_run, interval_hours, request.mode))
            result = cur.fetchone()
            results.append({
                "profile_id": result["profile_id"],
                "enabled": result["enabled"],
                "mode": result.get("mode"),
                "next_run": str(result["next_run"]) if result.get("next_run") else None,
            })
        
        conn.commit()
        
        return {
            "success": True,
            "profiles_updated": len(results),
            "results": results,
        }
    finally:
        cur.close()
        conn.close()


@router.post("/autopilot/run")
async def run_autopilot(
    profile_id: Optional[str] = None,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Trigger autopilot: creates report requests and starts the async flow.
    Returns immediately with run IDs - use /autopilot/poll to check progress.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from backend.app.core.config import settings as app_settings
    from db.accounts_db import (
        get_account_for_profile, get_client_tokens, 
        create_autopilot_run, update_autopilot_run, save_report_to_db
    )
    from backend.app.services.amazon_reports import create_report as amazon_create_report, get_date_range
    from backend.app.services.amazon import get_valid_access_token
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = psycopg2.connect(app_settings.DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if profile_id:
            cur.execute("SELECT * FROM autopilot_settings WHERE profile_id = %s AND enabled = TRUE", (profile_id,))
        else:
            cur.execute("SELECT * FROM autopilot_settings WHERE enabled = TRUE")
        
        profiles_to_run = cur.fetchall()
        
        if not profiles_to_run:
            return {"success": False, "message": "No profiles with autopilot enabled"}
        
        results = []
        
        for profile_setting in profiles_to_run:
            pid = profile_setting["profile_id"]
            mode = profile_setting.get("mode", "normal")
            
            try:
                profile_info = get_account_for_profile(pid)
                if not profile_info:
                    logger.warning(f"Autopilot: Profile {pid} not found in database")
                    results.append({"profile_id": pid, "success": False, "error": "Profile not found"})
                    continue
                
                account_id = profile_info.get("client_account_id")
                api_url = profile_info.get("api_url") or "https://advertising-api-eu.amazon.com"
                
                access_token, token_info = get_valid_access_token(account_id)
                if not access_token:
                    logger.warning(f"Autopilot: No valid tokens for account {account_id}")
                    results.append({"profile_id": pid, "success": False, "error": "No valid access tokens"})
                    continue
                
                autopilot_run = create_autopilot_run(pid, account_id, mode)
                if not autopilot_run:
                    results.append({"profile_id": pid, "success": False, "error": "Failed to create run"})
                    continue
                
                run_id = autopilot_run["id"]
                logger.info(f"Autopilot: Created run {run_id} for profile {pid}")
                
                start_14d, end_14d = get_date_range(14)
                start_30d, end_30d = get_date_range(30)
                
                report_14d_id = None
                report_30d_id = None
                
                try:
                    report_14d_id = amazon_create_report(
                        access_token, pid, api_url, "SP_TARGETING_14D", start_14d, end_14d
                    )
                    logger.info(f"Autopilot: Created 14D report {report_14d_id} for profile {pid}")
                    save_report_to_db(pid, account_id, report_14d_id, "SP_TARGETING_14D", 
                                     start_14d, end_14d, run_id)
                except Exception as e:
                    logger.error(f"Autopilot: Failed to create 14D report for {pid}: {e}")
                
                try:
                    report_30d_id = amazon_create_report(
                        access_token, pid, api_url, "SP_TARGETING_30D", start_30d, end_30d
                    )
                    logger.info(f"Autopilot: Created 30D report {report_30d_id} for profile {pid}")
                    save_report_to_db(pid, account_id, report_30d_id, "SP_TARGETING_30D",
                                     start_30d, end_30d, run_id)
                except Exception as e:
                    logger.error(f"Autopilot: Failed to create 30D report for {pid}: {e}")
                
                if not report_14d_id and not report_30d_id:
                    update_autopilot_run(run_id, status="FAILED", 
                                        error_message="Failed to create any reports")
                    results.append({"profile_id": pid, "success": False, "error": "Failed to create reports"})
                    continue
                
                update_autopilot_run(
                    run_id,
                    status="GENERATING_REPORTS",
                    report_14d_id=report_14d_id,
                    report_30d_id=report_30d_id,
                    reports_requested_at="NOW()"
                )
                
                results.append({
                    "profile_id": pid,
                    "success": True,
                    "run_id": run_id,
                    "status": "GENERATING_REPORTS",
                    "report_14d_id": report_14d_id,
                    "report_30d_id": report_30d_id
                })
                
            except Exception as e:
                logger.error(f"Autopilot error for profile {pid}: {e}")
                results.append({
                    "profile_id": pid,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "message": "Reports requested. Use /autopilot/poll to check progress.",
            "profiles_processed": len(results),
            "results": results
        }
    finally:
        cur.close()
        conn.close()


@router.post("/autopilot/poll")
async def poll_autopilot(
    run_id: Optional[int] = None,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Poll autopilot runs to check report status and trigger analysis when ready.
    Can poll a specific run_id or all pending runs.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from backend.app.core.config import settings as app_settings
    from db.accounts_db import (
        get_autopilot_run, get_pending_autopilot_runs, update_autopilot_run,
        update_report_status, get_account_for_profile, get_client_tokens,
        get_latest_discovery_report
    )
    from backend.app.services.amazon_reports import (
        check_report_status as amazon_check_status,
        download_report_with_service
    )
    from backend.app.services.amazon import get_valid_access_token
    import json
    import gzip
    import requests
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = psycopg2.connect(app_settings.DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if run_id:
            autopilot_run = get_autopilot_run(run_id)
            if not autopilot_run:
                raise HTTPException(status_code=404, detail="Autopilot run not found")
            pending_runs = [autopilot_run]
        else:
            pending_runs = get_pending_autopilot_runs()
        
        if not pending_runs:
            return {"success": True, "message": "No pending autopilot runs", "results": []}
        
        results = []
        
        for run in pending_runs:
            run_id = run["id"]
            pid = run["profile_id"]
            account_id = run.get("account_id")
            report_14d_id = run.get("report_14d_id")
            report_30d_id = run.get("report_30d_id")
            
            try:
                profile_info = get_account_for_profile(pid)
                if not profile_info:
                    update_autopilot_run(run_id, status="FAILED", error_message="Profile not found")
                    results.append({"run_id": run_id, "status": "FAILED", "error": "Profile not found"})
                    continue
                
                api_url = profile_info.get("api_url") or "https://advertising-api-eu.amazon.com"
                account_id = profile_info.get("client_account_id")
                
                access_token, token_info = get_valid_access_token(account_id)
                if not access_token:
                    update_autopilot_run(run_id, status="FAILED", error_message="No valid tokens")
                    results.append({"run_id": run_id, "status": "FAILED", "error": "No valid tokens"})
                    continue
                
                report_14d_ready = False
                report_30d_ready = False
                data_14d = []
                data_30d = []
                
                if report_14d_id:
                    try:
                        status_14d = amazon_check_status(access_token, pid, api_url, report_14d_id)
                        if status_14d["status"] == "COMPLETED" and status_14d.get("url"):
                            resp = requests.get(status_14d["url"], timeout=60)
                            resp.raise_for_status()
                            data_14d = json.loads(gzip.decompress(resp.content).decode('utf-8'))
                            update_report_status(report_14d_id, "COMPLETED", download_url=status_14d["url"], report_data=data_14d)
                            report_14d_ready = True
                            logger.info(f"Poll: 14D report ready for run {run_id}")
                        elif status_14d["status"] == "FAILURE":
                            update_report_status(report_14d_id, "FAILED", failure_reason=status_14d.get("failureReason"))
                            logger.warning(f"Poll: 14D report failed for run {run_id}")
                    except Exception as e:
                        logger.error(f"Poll: Error checking 14D report for run {run_id}: {e}")
                
                if report_30d_id:
                    try:
                        status_30d = amazon_check_status(access_token, pid, api_url, report_30d_id)
                        if status_30d["status"] == "COMPLETED" and status_30d.get("url"):
                            resp = requests.get(status_30d["url"], timeout=60)
                            resp.raise_for_status()
                            data_30d = json.loads(gzip.decompress(resp.content).decode('utf-8'))
                            update_report_status(report_30d_id, "COMPLETED", download_url=status_30d["url"], report_data=data_30d)
                            report_30d_ready = True
                            logger.info(f"Poll: 30D report ready for run {run_id}")
                        elif status_30d["status"] == "FAILURE":
                            update_report_status(report_30d_id, "FAILED", failure_reason=status_30d.get("failureReason"))
                            logger.warning(f"Poll: 30D report failed for run {run_id}")
                    except Exception as e:
                        logger.error(f"Poll: Error checking 30D report for run {run_id}: {e}")
                
                if report_14d_ready or report_30d_ready:
                    update_autopilot_run(run_id, status="ANALYZING")
                    logger.info(f"Poll: Starting analysis for run {run_id}")
                    
                    discovery_data = {}
                    discovery_report = get_latest_discovery_report(pid)
                    if discovery_report:
                        disc_data = discovery_report.get("report_data", [])
                        if isinstance(disc_data, dict):
                            disc_data = disc_data.get("rows", disc_data.get("data", []))
                        for row in disc_data:
                            campaign_id = row.get("campaignId")
                            ad_group_id = row.get("adGroupId")
                            if campaign_id and ad_group_id:
                                discovery_data[(str(campaign_id), str(ad_group_id))] = {
                                    "campaign_name": row.get("campaignName", ""),
                                    "campaign_id": str(campaign_id),
                                    "ad_group_id": str(ad_group_id),
                                    "asin": row.get("asin", row.get("advertisedAsin", ""))
                                }
                    
                    all_target_ids = set()
                    for row in data_14d:
                        kw_id = row.get("keywordId")
                        tgt_id = row.get("targetId")
                        if kw_id:
                            all_target_ids.add(str(kw_id))
                        if tgt_id:
                            all_target_ids.add(str(tgt_id))
                    for row in data_30d:
                        kw_id = row.get("keywordId")
                        tgt_id = row.get("targetId")
                        if kw_id:
                            all_target_ids.add(str(kw_id))
                        if tgt_id:
                            all_target_ids.add(str(tgt_id))
                    
                    live_bids = {}
                    targets_map = {}
                    campaign_states_map = {}
                    if all_target_ids and access_token:
                        try:
                            live_bids = get_all_target_bids(access_token, pid, list(all_target_ids), api_url)
                            logger.info(f"Poll: Fetched {len(live_bids)} live bids for run {run_id}")
                        except Exception as e:
                            logger.warning(f"Poll: Could not fetch live bids for run {run_id}: {e}")
                    
                    keywords_map = {}
                    if access_token:
                        try:
                            keywords_map, targets_map, error = get_amazon_keywords_and_targets(
                                account_id, pid, api_url
                            )
                            if error:
                                logger.warning(f"Poll: Error fetching keywords/targets for run {run_id}: {error}")
                            campaign_states_map = keywords_map.pop("_campaign_states", {})
                            logger.info(f"Poll: Got {len(keywords_map)} keywords, {len(targets_map)} targets, {len(campaign_states_map)} campaign states for run {run_id}")
                        except Exception as e:
                            logger.warning(f"Poll: Could not fetch keywords/targets for run {run_id}: {e}")
                    
                    actions = analyze_targets(data_14d, data_30d, discovery_data, live_bids, profile_id=pid, targets_map=targets_map, campaign_states_map=campaign_states_map, keywords_map=keywords_map)
                    
                    clear_planned_actions(pid)
                    
                    saved_count = 0
                    for action in actions:
                        save_planned_bid_action(
                            profile_id=pid,
                            account_id=account_id,
                            campaign_id=action.get("campaign_id", ""),
                            campaign_name=action.get("campaign_name", ""),
                            ad_group_id=action.get("ad_group_id", ""),
                            keyword_id=action.get("keyword_id", ""),
                            asin=action.get("asin", ""),
                            target_keyword=action.get("keyword", ""),
                            current_bid=action.get("current_bid"),
                            delta_bid=action.get("delta_bid", 0),
                            tipo_azione=action.get("tipo_azione", ""),
                            report_14d_id=report_14d_id,
                            report_30d_id=report_30d_id,
                            target_type=action.get("target_type", "keyword"),
                            acos_14d=action.get("acos_14d"),
                            acos_30d=action.get("acos_30d")
                        )
                        saved_count += 1
                    
                    update_autopilot_run(
                        run_id,
                        status="COMPLETED",
                        actions_count=saved_count,
                        analysis_completed_at="NOW()"
                    )
                    
                    cur.execute("""
                        UPDATE autopilot_settings 
                        SET last_run = NOW(), next_run = NOW() + INTERVAL '3 days', updated_at = NOW()
                        WHERE profile_id = %s
                    """, (pid,))
                    conn.commit()
                    
                    results.append({
                        "run_id": run_id,
                        "profile_id": pid,
                        "status": "COMPLETED",
                        "actions_planned": saved_count
                    })
                    
                else:
                    update_autopilot_run(run_id, status="WAITING_REPORTS")
                    results.append({
                        "run_id": run_id,
                        "profile_id": pid,
                        "status": "WAITING_REPORTS",
                        "report_14d_ready": report_14d_ready,
                        "report_30d_ready": report_30d_ready
                    })
                    
            except Exception as e:
                logger.error(f"Poll error for run {run_id}: {e}")
                update_autopilot_run(run_id, status="FAILED", error_message=str(e))
                results.append({"run_id": run_id, "status": "FAILED", "error": str(e)})
        
        return {
            "success": True,
            "runs_polled": len(results),
            "results": results
        }
    finally:
        cur.close()
        conn.close()


@router.get("/autopilot/runs")
async def get_autopilot_runs(
    profile_id: Optional[str] = None,
    limit: int = 20,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Get autopilot run history."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from backend.app.core.config import settings as app_settings
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    conn = psycopg2.connect(app_settings.DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if profile_id:
            cur.execute("""
                SELECT ar.*, cp.country_code, ca.client_name as account_name
                FROM autopilot_runs ar
                LEFT JOIN client_profiles cp ON ar.profile_id = cp.profile_id
                LEFT JOIN client_accounts ca ON ar.account_id = ca.id
                WHERE ar.profile_id = %s
                ORDER BY ar.created_at DESC
                LIMIT %s
            """, (profile_id, limit))
        else:
            cur.execute("""
                SELECT ar.*, cp.country_code, ca.client_name as account_name
                FROM autopilot_runs ar
                LEFT JOIN client_profiles cp ON ar.profile_id = cp.profile_id
                LEFT JOIN client_accounts ca ON ar.account_id = ca.id
                ORDER BY ar.created_at DESC
                LIMIT %s
            """, (limit,))
        
        runs = cur.fetchall()
        
        return {
            "success": True,
            "runs": [dict(r) for r in runs]
        }
    finally:
        cur.close()
        conn.close()


# ============================================================
# NEW SIMPLIFIED AUTOPILOT ENDPOINTS (Refactored Architecture)
# ============================================================

@router.post("/autopilot/v2/run")
async def run_autopilot_v2(
    profile_id: str,
    account_id: int,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    V2 Autopilot: Create a run and trigger the orchestrator.
    
    Creates run with status CREATED, then calls orchestrator.process_run()
    which transitions it to REPORTS_PENDING.
    """
    from db.accounts_db import create_autopilot_run, set_run_status, get_account_for_profile
    from backend.app.services.autopilot_orchestrator import process_run
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    profile_info = get_account_for_profile(profile_id)
    if not profile_info:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if profile_info.get("client_account_id") != account_id:
        raise HTTPException(
            status_code=400, 
            detail=f"Profile {profile_id} does not belong to account {account_id}"
        )
    
    try:
        autopilot_run = create_autopilot_run(profile_id, account_id, mode="normal")
        if not autopilot_run:
            raise HTTPException(status_code=500, detail="Failed to create autopilot run")
        
        run_id = autopilot_run["id"]
        
        set_run_status(run_id, "CREATED")
        
        result = process_run(run_id)
        
        return {
            "success": True,
            "run_id": run_id,
            "status": result.get("status", "REPORTS_PENDING"),
            "report_14d_id": result.get("report_14d_id"),
            "report_30d_id": result.get("report_30d_id"),
            "message": "Run created and reports requested. Use /autopilot/v2/poll to check progress."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Autopilot V2 run error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autopilot/v2/poll")
async def poll_autopilot_v2(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    V2 Autopilot Poll: Check report status and advance runs to REPORTS_READY.
    
    Only handles:
    - Polls PENDING reports (transitions to COMPLETED/PARSED)
    - Marks runs as REPORTS_READY when their reports are PARSED
    
    Does NOT trigger analysis - use /autopilot/v2/analyze for that.
    """
    from backend.app.services.report_scheduler import poll_reports_once, mark_runs_ready_once
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        poll_result = poll_reports_once()
        
        ready_result = mark_runs_ready_once()
        
        return {
            "success": True,
            "reports_polled": poll_result.get("polled", 0),
            "reports_parsed": poll_result.get("parsed", 0),
            "runs_marked_ready": ready_result.get("marked_ready", 0)
        }
    except Exception as e:
        logger.error(f"Autopilot V2 poll error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autopilot/v2/analyze")
async def analyze_autopilot_v2(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    V2 Autopilot Analyze: Process runs that are REPORTS_READY.
    
    - Gets runs with status REPORTS_READY
    - Calls orchestrator.process_run() for each to transition to ACTIONS_PLANNED
    """
    from backend.app.services.autopilot_orchestrator import process_run
    from db.accounts_db import get_runs_by_status
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        runs_ready = get_runs_by_status(["REPORTS_READY"])
        analysis_results = []
        
        for run in runs_ready[:5]:
            run_id = run.get("id")
            result = process_run(run_id)
            analysis_results.append({
                "run_id": run_id,
                "status": result.get("status"),
                "actions_count": result.get("actions_count", 0)
            })
        
        return {
            "success": True,
            "runs_analyzed": len(analysis_results),
            "results": analysis_results
        }
    except Exception as e:
        logger.error(f"Autopilot V2 analyze error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autopilot/v2/execute")
async def execute_autopilot_v2(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    V2 Autopilot Execute: Execute planned actions in batch.
    
    - Executes up to 100 PLANNED actions
    - Finalizes completed runs to DONE
    """
    from backend.app.services.action_executor import execute_actions_once, finalize_runs_once
    
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        execute_result = execute_actions_once()
        
        finalize_result = finalize_runs_once()
        
        return {
            "success": True,
            "actions_executed": execute_result.get("executed", 0),
            "actions_failed": execute_result.get("failed", 0),
            "profiles_processed": execute_result.get("profiles_processed", 0),
            "runs_finalized": finalize_result.get("finalized", 0),
            "details": execute_result.get("results", [])
        }
    except Exception as e:
        logger.error(f"Autopilot V2 execute error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
