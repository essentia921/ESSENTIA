import os
import json
import requests
import logging
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

CLIENT_ID = os.getenv("AMAZON_ADS_CLIENT_ID")
CLIENT_SECRET = os.getenv("AMAZON_ADS_CLIENT_SECRET")
TOKEN_URL = "https://api.amazon.com/auth/o2/token"

VENDOR_TYPES = {
    "campaigns": "application/vnd.spCampaign.v3+json",
    "adGroups": "application/vnd.spAdGroup.v3+json",
    "productAds": "application/vnd.spProductAd.v3+json",
    "keywords": "application/vnd.spKeyword.v3+json",
    "targets": "application/vnd.spTargetingClause.v3+json",
}

API_REGIONS = {
    "NA": "https://advertising-api.amazon.com",
    "EU": "https://advertising-api-eu.amazon.com",
    "FE": "https://advertising-api-fe.amazon.com",
}


class CampaignLauncherError(Exception):
    def __init__(self, message: str, amazon_response: dict = None):
        super().__init__(message)
        self.amazon_response = amazon_response


def get_api_url_for_region(region: str) -> str:
    return API_REGIONS.get(region.upper(), API_REGIONS["EU"])


def refresh_token(refresh_token_value: str) -> Tuple[str, str]:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_value,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    return data["access_token"], data.get("refresh_token", refresh_token_value)


def extract_id(resp, keys: List[str]) -> str:
    if isinstance(resp, list):
        for item in resp:
            if isinstance(item, dict):
                for k in keys:
                    if k in item:
                        return str(item[k])
                index_obj = item.get("index", None)
                if index_obj is not None:
                    for k in keys:
                        if k in item:
                            return str(item[k])

    if isinstance(resp, dict):
        for k in keys:
            if isinstance(resp.get(k), (int, str)):
                return str(resp[k])

        for container in ["campaigns", "adGroups", "productAds", "keywords", "targets"]:
            block = resp.get(container)
            if isinstance(block, dict):
                success = block.get("success")
                if isinstance(success, list):
                    for item in success:
                        for k in keys:
                            if k in item:
                                return str(item[k])

        for container in ["results", "success"]:
            items = resp.get(container)
            if isinstance(items, list):
                for item in items:
                    for k in keys:
                        if k in item:
                            return str(item[k])

    raise CampaignLauncherError(f"Could not extract ID from response", resp if isinstance(resp, dict) else {"response": resp})


class CampaignLauncherService:
    def __init__(self, access_token: str, refresh_token_value: str, profile_id: str, api_url: str):
        self.access_token = access_token
        self.refresh_token_value = refresh_token_value
        self.profile_id = str(profile_id)
        self.api_url = api_url
        self.token_refreshed = False

    def _headers(self, vendor_type: str) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Amazon-Advertising-API-Scope": self.profile_id,
            "Content-Type": VENDOR_TYPES[vendor_type],
            "Accept": VENDOR_TYPES[vendor_type],
        }

    def _post(self, path: str, payload, vendor_type: str, retry_on_401: bool = True):
        url = f"{self.api_url}{path}"
        headers = self._headers(vendor_type)

        logger.info(f"=== Amazon API Request ===")
        logger.info(f"URL: {url}")
        logger.info(f"Content-Type: {headers.get('Content-Type')}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        logger.info(f"Response Status: {response.status_code}")
        logger.info(f"Response Body: {response.text[:2000]}")

        if response.status_code == 401 and retry_on_401:
            logger.info("Token expired, refreshing...")
            self.access_token, self.refresh_token_value = refresh_token(self.refresh_token_value)
            self.token_refreshed = True
            headers = self._headers(vendor_type)
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            logger.info(f"Retry Response Status: {response.status_code}")
            logger.info(f"Retry Response Body: {response.text[:2000]}")

        if response.status_code not in (200, 207):
            raise CampaignLauncherError(
                f"Amazon API error: {response.status_code}",
                amazon_response={"status": response.status_code, "body": response.text}
            )

        return response.json()

    def create_campaign(self, name: str, targeting_type: str, daily_budget: float, start_date: str, bidding_strategy: str = "DOWN_ONLY") -> str:
        strategy_map = {
            "DOWN_ONLY": "LEGACY_FOR_SALES",
            "UP_AND_DOWN": "AUTO_FOR_SALES",
            "FIXED": "MANUAL",
            "LEGACY_FOR_SALES": "LEGACY_FOR_SALES",
            "AUTO_FOR_SALES": "AUTO_FOR_SALES",
            "MANUAL": "MANUAL",
        }
        strategy_value = strategy_map.get(bidding_strategy, "LEGACY_FOR_SALES")

        payload = {
            "campaigns": [
                {
                    "name": name,
                    "campaignType": "SPONSORED_PRODUCTS",
                    "targetingType": targeting_type,
                    "state": "ENABLED",
                    "startDate": start_date,
                    "budget": {
                        "budgetType": "DAILY",
                        "budget": daily_budget
                    },
                    "dynamicBidding": {
                        "strategy": strategy_value
                    }
                }
            ]
        }
        resp = self._post("/sp/campaigns", payload, "campaigns")
        return extract_id(resp, ["campaignId"])

    def create_ad_group(self, campaign_id: str, name: str, default_bid: float) -> str:
        payload = {
            "adGroups": [
                {
                    "campaignId": campaign_id,
                    "name": name,
                    "defaultBid": default_bid,
                    "state": "ENABLED"
                }
            ]
        }
        resp = self._post("/sp/adGroups", payload, "adGroups")
        return extract_id(resp, ["adGroupId"])

    def create_product_ad(self, campaign_id: str, ad_group_id: str, asin: str) -> dict:
        payload = {
            "productAds": [
                {
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "asin": asin,
                    "state": "ENABLED"
                }
            ]
        }
        return self._post("/sp/productAds", payload, "productAds")

    def create_keywords(self, campaign_id: str, ad_group_id: str, keywords: List[Dict]) -> dict:
        payload = {
            "keywords": [
                {
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "keywordText": kw["keyword"],
                    "matchType": kw.get("match_type", "EXACT").upper(),
                    "bid": float(kw.get("bid", 0.2)),
                    "state": "ENABLED"
                } for kw in keywords
            ]
        }
        return self._post("/sp/keywords", payload, "keywords")

    def create_targets(self, campaign_id: str, ad_group_id: str, targets: List[Dict], expression_type: str = "exact") -> dict:
        if expression_type == "expanded":
            target_type = "ASIN_EXPANDED_FROM"
        else:
            target_type = "ASIN_SAME_AS"

        payload = {
            "targetingClauses": [
                {
                    "campaignId": str(campaign_id),
                    "adGroupId": str(ad_group_id),
                    "expressionType": "MANUAL",
                    "expression": [{"type": target_type, "value": t["asin"]}],
                    "bid": float(t.get("bid", 0.2)),
                    "state": "ENABLED"
                } for t in targets
            ]
        }
        return self._post("/sp/targets", payload, "targets")

    def get_updated_tokens(self) -> Optional[Tuple[str, str]]:
        if self.token_refreshed:
            return self.access_token, self.refresh_token_value
        return None


def launch_campaign(
    account_id: int,
    profile_id: str,
    api_url: str,
    campaign_type: str,
    campaign_name: str,
    ad_group_name: str,
    asin: str,
    daily_budget: float,
    default_bid: float,
    targets: List[Dict] = None,
    start_date: str = None,
    bidding_strategy: str = "DOWN_ONLY"
) -> Dict[str, Any]:
    from db.accounts_db import get_client_tokens, save_client_tokens

    token_data = get_client_tokens(account_id)
    if not token_data:
        raise CampaignLauncherError("Account not connected to Amazon Ads")

    access_token = token_data.get("access_token")
    refresh_token_val = token_data.get("refresh_token")

    if not access_token or not refresh_token_val:
        raise CampaignLauncherError("Invalid token data")

    if not start_date:
        start_date = datetime.now().strftime("%Y-%m-%d")

    targeting_type = "AUTO" if campaign_type == "automatica" else "MANUAL"

    service = CampaignLauncherService(access_token, refresh_token_val, profile_id, api_url)

    try:
        campaign_id = service.create_campaign(campaign_name, targeting_type, daily_budget, start_date, bidding_strategy)
        logger.info(f"[LAUNCH] Campaign created: {campaign_id}")
        ad_group_id = service.create_ad_group(campaign_id, ad_group_name, default_bid)
        logger.info(f"[LAUNCH] Ad Group created: {ad_group_id}")
        product_ad_resp = service.create_product_ad(campaign_id, ad_group_id, asin)
        logger.info(f"[LAUNCH] Product Ad response: {json.dumps(product_ad_resp)[:500]}")

        if campaign_type == "keywords" and targets:
            service.create_keywords(campaign_id, ad_group_id, targets)
        elif campaign_type == "product_exact" and targets:
            service.create_targets(campaign_id, ad_group_id, targets, expression_type="exact")
        elif campaign_type == "product_expanded" and targets:
            service.create_targets(campaign_id, ad_group_id, targets, expression_type="expanded")

        updated_tokens = service.get_updated_tokens()
        if updated_tokens:
            new_access, new_refresh = updated_tokens
            save_client_tokens(account_id, new_access, new_refresh)

        logger.info(f"[LAUNCH COMPLETE] campaign_id={campaign_id}, ad_group_id={ad_group_id}, asin={asin}, type={campaign_type}")

        return {
            "success": True,
            "campaign_id": campaign_id,
            "ad_group_id": ad_group_id,
            "campaign_name": campaign_name,
            "targeting_type": targeting_type,
        }

    except CampaignLauncherError:
        raise
    except Exception as e:
        raise CampaignLauncherError(f"Unexpected error: {str(e)}")
