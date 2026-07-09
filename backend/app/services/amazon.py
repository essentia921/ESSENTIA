import os
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

CLIENT_ID = os.getenv("AMAZON_ADS_CLIENT_ID")
CLIENT_SECRET = os.getenv("AMAZON_ADS_CLIENT_SECRET")
TOKEN_URL = "https://api.amazon.com/auth/o2/token"

API_REGIONS = {
    "NA": {
        "url": "https://advertising-api.amazon.com",
        "name": "North America",
        "countries": ["US", "CA", "MX", "BR"],
    },
    "EU": {
        "url": "https://advertising-api-eu.amazon.com",
        "name": "Europe",
        "countries": ["UK", "GB", "DE", "FR", "IT", "ES", "NL", "SE", "PL", "BE", "AE", "SA", "EG", "TR", "IN"],
    },
    "FE": {
        "url": "https://advertising-api-fe.amazon.com",
        "name": "Far East",
        "countries": ["JP", "AU", "SG"],
    },
}


def get_api_url_for_country(country_code: str) -> str:
    country_upper = country_code.upper() if country_code else ""
    for region_info in API_REGIONS.values():
        if country_upper in region_info["countries"]:
            return region_info["url"]
    return API_REGIONS["EU"]["url"]


class AmazonAuthError(Exception):
    pass


class AmazonAPIError(Exception):
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class AmazonAdsService:
    def __init__(self, access_token: str, refresh_token: str, account_id: int):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.account_id = account_id
        self.token_refreshed = False
        self.expires_at = None
    
    def refresh_access_token(self) -> Tuple[str, str, datetime]:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
        
        try:
            response = requests.post(TOKEN_URL, data=payload)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise AmazonAuthError(f"Token refresh failed: {e}")
        
        data = response.json()
        
        new_access_token = data["access_token"]
        new_refresh_token = data.get("refresh_token", self.refresh_token)
        expires_in = data.get("expires_in", 3600)
        self.expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        self.access_token = new_access_token
        self.refresh_token = new_refresh_token
        self.token_refreshed = True
        
        return new_access_token, new_refresh_token, self.expires_at
    
    def _make_request(self, url: str, headers: dict, method: str = "GET", json_data: dict = None, retry_on_401: bool = True) -> requests.Response:
        if method == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=json_data)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=json_data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 401 and retry_on_401:
            self.refresh_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            if method == "POST":
                response = requests.post(url, headers=headers, json=json_data)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=json_data)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=json_data)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                response = requests.get(url, headers=headers)
        
        if response.status_code == 401:
            raise AmazonAuthError("Authentication failed after token refresh")
        
        if response.status_code >= 400:
            raise AmazonAPIError(f"Amazon API error: {response.status_code} - {response.text}", response.status_code)
        
        return response
    
    def get_profiles(self) -> Tuple[list[dict], list[str]]:
        all_profiles = []
        errors = []
        
        for region_code, region_info in API_REGIONS.items():
            url = f"{region_info['url']}/v2/profiles"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Amazon-Advertising-API-ClientId": CLIENT_ID,
            }
            
            try:
                response = self._make_request(url, headers)
                profiles = response.json()
                for profile in profiles:
                    profile["_region"] = region_code
                    profile["_api_url"] = region_info["url"]
                all_profiles.extend(profiles)
            except AmazonAuthError:
                raise
            except AmazonAPIError as e:
                errors.append(f"{region_code}: {str(e)}")
            except Exception as e:
                errors.append(f"{region_code}: {str(e)}")
        
        if not all_profiles and errors:
            raise AmazonAPIError(f"All regions failed: {'; '.join(errors)}")
        
        return all_profiles, errors
    
    def get_campaigns(self, profile_id: str, api_url: str = None, include_paused: bool = False) -> list[dict]:
        """Get SP campaigns with pagination support."""
        base_url = api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sp/campaigns/list"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Accept": "application/vnd.spcampaign.v3+json",
            "Content-Type": "application/vnd.spcampaign.v3+json",
        }
        
        state_filter = ["ENABLED", "PAUSED"] if include_paused else ["ENABLED"]
        
        all_campaigns = []
        next_token = None
        page = 0
        
        while True:
            payload = {
                "campaignFilter": {
                    "campaignTypes": ["SPONSORED_PRODUCTS"],
                    "stateFilter": state_filter,
                },
                "maxResults": 1000,
            }
            if next_token:
                payload["nextToken"] = next_token
            
            response = self._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            
            campaigns = data.get("campaigns", [])
            all_campaigns.extend(campaigns)
            page += 1
            
            next_token = data.get("nextToken")
            if not next_token:
                break
        
        print(f"[SP CAMPAIGNS] Profile {profile_id}: fetched {len(all_campaigns)} campaigns in {page} pages (include_paused={include_paused})")
        return all_campaigns
    
    def get_keywords(self, profile_id: str, api_url: str = None) -> list[dict]:
        """Get all SP keywords with their bids (with pagination)."""
        base_url = api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sp/keywords/list"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Accept": "application/vnd.spKeyword.v3+json",
            "Content-Type": "application/vnd.spKeyword.v3+json",
        }
        
        all_keywords = []
        next_token = None
        page = 0
        
        while True:
            payload = {
                "stateFilter": {"include": ["ENABLED"]},
                "maxResults": 1000,
            }
            if next_token:
                payload["nextToken"] = next_token
            
            response = self._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            
            keywords = data.get("keywords", [])
            all_keywords.extend(keywords)
            page += 1
            
            next_token = data.get("nextToken")
            if not next_token:
                break
                
        print(f"[SP KEYWORDS] Profile {profile_id}: fetched {len(all_keywords)} keywords in {page} pages")
        return all_keywords
    
    def get_targets(self, profile_id: str, api_url: str = None) -> list[dict]:
        """Get all SP targets (product/category targeting) with their bids (with pagination)."""
        base_url = api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sp/targets/list"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Accept": "application/vnd.spTargetingClause.v3+json",
            "Content-Type": "application/vnd.spTargetingClause.v3+json",
        }
        
        all_targets = []
        next_token = None
        page = 0
        
        while True:
            payload = {
                "stateFilter": {"include": ["ENABLED"]},
                "maxResults": 1000,
            }
            if next_token:
                payload["nextToken"] = next_token
            
            response = self._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            
            targets = data.get("targetingClauses", [])
            all_targets.extend(targets)
            page += 1
            
            next_token = data.get("nextToken")
            if not next_token:
                break
                
        print(f"[SP TARGETS] Profile {profile_id}: fetched {len(all_targets)} targets in {page} pages")
        return all_targets
    
    def get_product_targets_query(self, profile_id: str, api_url: str = None, target_types: list = None) -> list[dict]:
        """
        Get SP targets using the query endpoint.
        This endpoint returns all targets with full targetDetails (ASIN, category, auto).
        
        Args:
            target_types: List of target types to fetch. Default: ["PRODUCT", "CATEGORY"]
        """
        base_url = api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/adsApi/v1/query/targets"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Ads-CustomerId": str(profile_id),
            "Amazon-Ads-ClientId": CLIENT_ID,
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        target_types = target_types or ["PRODUCT", "PRODUCT_CATEGORY"]
        
        payload = {
            "adProductFilter": {"include": ["SPONSORED_PRODUCTS"]},
            "targetTypeFilter": {"include": target_types},
            "stateFilter": {"include": ["ENABLED"]},
            "maxResults": 1000,
        }
        
        all_targets = []
        next_token = None
        page = 0
        
        while True:
            if next_token:
                payload["nextToken"] = next_token
            
            response = self._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            
            targets = data.get("targets", [])
            all_targets.extend(targets)
            page += 1
            
            next_token = data.get("nextToken")
            if not next_token:
                break
        
        print(f"[SP PRODUCT TARGETS QUERY] Profile {profile_id}: fetched {len(all_targets)} product targets in {page} pages")
        return all_targets
    
    def update_keyword_bid(self, keyword_id: str, new_bid: float, api_url: str = None) -> dict:
        """Update the bid for a single keyword."""
        base_url = api_url or self.api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sp/keywords"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(self.profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Accept": "application/vnd.spKeyword.v3+json",
            "Content-Type": "application/vnd.spKeyword.v3+json",
        }
        payload = {
            "keywords": [
                {"keywordId": str(keyword_id), "bid": new_bid}
            ]
        }
        
        response = self._make_request(url, headers, method="PUT", json_data=payload)
        return response.json()
    
    def update_target_bid(self, target_id: str, new_bid: float, api_url: str = None) -> dict:
        """Update the bid for a single target."""
        base_url = api_url or self.api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sp/targets"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(self.profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Accept": "application/vnd.spTargetingClause.v3+json",
            "Content-Type": "application/vnd.spTargetingClause.v3+json",
        }
        payload = {
            "targetingClauses": [
                {"targetId": str(target_id), "bid": new_bid}
            ]
        }
        
        response = self._make_request(url, headers, method="PUT", json_data=payload)
        return response.json()
    
    def get_sb_targets(self, profile_id: str, api_url: str = None) -> list[dict]:
        """Get all SB targets (keywords and product targeting) with their bids.
        
        For keywords: Try GET /sb/keywords (works on all marketplaces)
        For targets: Use POST /sb/targets/list
        
        Uses retry logic: JSON -> V3 -> */* fallback.
        """
        base_url = api_url or API_REGIONS["EU"]["url"]
        all_targets = []
        
        common_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
        }
        
        def try_sb_keywords_request(url, accept_header):
            headers = {**common_headers, "Accept": accept_header}
            print(f"[SB_REQ] GET {url}")
            print(f"[SB_REQ] Accept: {accept_header}")
            response = self._make_request(url, headers, method="GET")
            print(f"[SB_RESP] Status: {response.status_code}")
            return response
        
        try:
            start_index = 0
            page_size = 1000
            keyword_count = 0
            working_accept = None
            
            while True:
                url = f"{base_url}/sb/keywords?startIndex={start_index}&count={page_size}&stateFilter=enabled"
                
                if working_accept:
                    response = try_sb_keywords_request(url, working_accept)
                    keywords = response.json()
                else:
                    for accept in ["application/vnd.sbkeywordresource.v3+json", "*/*"]:
                        try:
                            response = try_sb_keywords_request(url, accept)
                            keywords = response.json()
                            working_accept = accept
                            print(f"[SB KEYWORDS] Success with Accept: {accept}")
                            break
                        except AmazonAPIError as e:
                            print(f"[SB KEYWORDS] Failed with Accept {accept}: {e}")
                            if accept == "*/*":
                                raise
                            continue
                
                if not keywords:
                    break
                for kw in keywords:
                    kw["_sb_type"] = "keyword"
                all_targets.extend(keywords)
                keyword_count += len(keywords)
                if len(keywords) < page_size:
                    break
                start_index += page_size
            print(f"[SB KEYWORDS] Profile {profile_id}: fetched {keyword_count} keywords via GET /sb/keywords")
        except AmazonAPIError as e:
            logger.warning(f"Failed to get SB keywords for profile {profile_id}: {e}")
        
        def try_sb_targets_request(url, accept_header, content_type, payload):
            headers = {**common_headers, "Accept": accept_header, "Content-Type": content_type}
            print(f"[SB_REQ] POST {url}")
            print(f"[SB_REQ] Accept: {accept_header}, Content-Type: {content_type}")
            response = self._make_request(url, headers, method="POST", json_data=payload)
            print(f"[SB_RESP] Status: {response.status_code}")
            return response
        
        try:
            url = f"{base_url}/sb/targets/list"
            next_token = None
            product_count = 0
            working_headers = None
            
            while True:
                payload = {"maxResults": 1000}
                if next_token:
                    payload["nextToken"] = next_token
                
                if working_headers:
                    response = try_sb_targets_request(url, working_headers[0], working_headers[1], payload)
                    data = response.json()
                else:
                    headers_options = [
                        ("application/vnd.sbtargetingclause.v3+json", "application/json"),
                        ("application/vnd.sbtargetingclause.v3+json", "application/vnd.sbtargetingclause.v3+json"),
                        ("*/*", "application/json"),
                    ]
                    for accept, content_type in headers_options:
                        try:
                            response = try_sb_targets_request(url, accept, content_type, payload)
                            data = response.json()
                            working_headers = (accept, content_type)
                            print(f"[SB TARGETS] Success with Accept: {accept}, Content-Type: {content_type}")
                            break
                        except AmazonAPIError as e:
                            print(f"[SB TARGETS] Failed with Accept {accept}, CT {content_type}: {e}")
                            if accept == "*/*":
                                raise
                            continue
                
                targets = data.get("targets", [])
                enabled_targets = [t for t in targets if t.get("state", "").upper() == "ENABLED"]
                for t in enabled_targets:
                    t["_sb_type"] = "product_target"
                all_targets.extend(enabled_targets)
                product_count += len(enabled_targets)
                next_token = data.get("nextToken")
                if not next_token:
                    break
            print(f"[SB PRODUCT TARGETS] Profile {profile_id}: fetched {product_count} product targets via POST /sb/targets/list")
        except AmazonAPIError as e:
            logger.warning(f"Failed to get SB product targets for profile {profile_id}: {e}")
        
        print(f"[SB TARGETS TOTAL] Profile {profile_id}: {len(all_targets)} total (keywords + product targets)")
        return all_targets
    
    def get_sb_campaign_by_id(self, campaign_id: str, profile_id: str, api_url: str = None) -> dict:
        """Get a single SB campaign by ID using GET /sb/v4/campaigns/{campaignId}."""
        base_url = api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sb/v4/campaigns/{campaign_id}"
        
        common_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
        }
        
        accept_options = ["*/*", "application/json", "application/vnd.sbcampaignresource.v4+json"]
        
        last_error = None
        for accept in accept_options:
            headers = {**common_headers, "Accept": accept}
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    print(f"[SB_CAMPAIGN_BY_ID] {campaign_id} success with Accept: {accept}")
                    return response.json()
                last_error = f"status={response.status_code} body={response.text[:200] if response.text else ''}"
            except Exception as e:
                last_error = str(e)
                continue
        
        logger.warning(f"SB campaign by id failed for {campaign_id}. Last error: {last_error}")
        return None
    
    def get_sb_campaigns_by_ids(self, campaign_ids: list, profile_id: str, api_url: str = None) -> dict:
        """Get multiple SB campaigns by IDs. Returns dict campaignId -> campaign data."""
        import time
        campaign_map = {}
        unique_ids = list(set(campaign_ids))
        
        print(f"[SB_CAMPAIGNS_BY_ID] Fetching {len(unique_ids)} unique campaigns for profile {profile_id}")
        
        for i, cid in enumerate(unique_ids):
            campaign = self.get_sb_campaign_by_id(str(cid), profile_id, api_url)
            if campaign:
                state = campaign.get("state", "UNKNOWN").upper()
                campaign_map[str(cid)] = state
            else:
                campaign_map[str(cid)] = "UNKNOWN"
            
            if (i + 1) % 50 == 0:
                print(f"[SB_CAMPAIGNS_BY_ID] Progress: {i+1}/{len(unique_ids)}")
                time.sleep(0.1)
        
        states_summary = {}
        for state in campaign_map.values():
            states_summary[state] = states_summary.get(state, 0) + 1
        print(f"[SB_CAMPAIGNS_BY_ID] States: {states_summary}")
        
        return campaign_map
    
    def get_sb_campaigns(self, profile_id: str, api_url: str = None, include_paused: bool = False, target_campaign_ids: list = None) -> list[dict]:
        """Get SB campaigns using POST /sb/v4/campaigns/list endpoint.
        
        Returns list of campaign dicts with campaignId, state, name.
        Falls back to per-ID lookup if list endpoint fails.
        """
        base_url = api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sb/v4/campaigns/list"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Accept": "application/vnd.sbcampaignresource.v4+json",
            "Content-Type": "application/vnd.sbcampaignresource.v4+json",
        }
        
        state_filter = {"include": ["ENABLED", "PAUSED"]} if include_paused else {"include": ["ENABLED"]}
        
        all_campaigns = []
        next_token = None
        max_pages = 20
        
        for page in range(max_pages):
            body = {
                "maxResults": 100,
                "stateFilter": state_filter,
            }
            if next_token:
                body["nextToken"] = next_token
            
            try:
                response = requests.post(url, headers=headers, json=body)
                if response.status_code == 200:
                    data = response.json()
                    campaigns = data.get("campaigns", [])
                    all_campaigns.extend(campaigns)
                    next_token = data.get("nextToken")
                    if not next_token:
                        break
                elif response.status_code in (406, 415):
                    headers_retry = {**headers, "Accept": "*/*", "Content-Type": "application/json"}
                    response2 = requests.post(url, headers=headers_retry, json=body)
                    if response2.status_code == 200:
                        data = response2.json()
                        campaigns = data.get("campaigns", [])
                        all_campaigns.extend(campaigns)
                        next_token = data.get("nextToken")
                        if not next_token:
                            break
                    else:
                        print(f"[SB CAMPAIGNS LIST] Retry failed: {response2.status_code} - {response2.text[:200]}")
                        break
                else:
                    print(f"[SB CAMPAIGNS LIST] Failed: {response.status_code} - {response.text[:200]}")
                    break
            except Exception as e:
                print(f"[SB CAMPAIGNS LIST] Error: {e}")
                break
        
        if all_campaigns:
            result = []
            for c in all_campaigns:
                cid = str(c.get("campaignId", ""))
                state = (c.get("state") or "ENABLED").upper()
                name = c.get("name", "")
                result.append({"campaignId": cid, "state": state, "name": name})
            
            states_summary = {}
            for c in result:
                s = c["state"]
                states_summary[s] = states_summary.get(s, 0) + 1
            print(f"[SB CAMPAIGNS LIST] Profile {profile_id}: {len(result)} campaigns - states: {states_summary}")
            return result
        
        if target_campaign_ids:
            print(f"[SB CAMPAIGNS] List endpoint returned 0 results, falling back to per-ID lookup for {len(target_campaign_ids)} campaigns")
            campaign_map = self.get_sb_campaigns_by_ids(target_campaign_ids, profile_id, api_url)
            campaigns = [{"campaignId": cid, "state": state} for cid, state in campaign_map.items()]
            print(f"[SB CAMPAIGNS] Profile {profile_id}: fetched {len(campaigns)} campaigns via per-ID fallback")
            return campaigns
        
        print(f"[SB CAMPAIGNS] Profile {profile_id}: no campaigns found")
        return []
    
    def update_sb_target_bid(self, target_id: str, new_bid: float, ad_group_id: str = None, api_url: str = None) -> dict:
        """Update the bid for a single SB product target (NOT keywords).
        
        Uses Accept: */* which works for all SB endpoints.
        SB targets require adGroupId in payload.
        """
        if not target_id or str(target_id).strip() == '':
            return {"success": False, "error": "target_id vuoto o mancante", "amazon_response": None}
        
        import json
        base_url = api_url or self.api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sb/targets"
        
        target_obj = {"targetId": int(target_id), "bid": round(new_bid, 2)}
        if ad_group_id:
            target_obj["adGroupId"] = int(ad_group_id)
        
        payload = {"targets": [target_obj]}
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(self.profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Accept": "*/*",
            "Content-Type": "application/json",
        }
        
        print(f"[SB_UPDATE_TARGET] PUT {url}")
        print(f"[SB_UPDATE_TARGET] Headers: Accept=*/*, Content-Type=application/json")
        print(f"[SB_UPDATE_TARGET] Payload: {payload}")
        
        try:
            response = requests.put(url, headers=headers, data=json.dumps(payload))
            print(f"[SB_UPDATE_TARGET] Response status: {response.status_code}")
            print(f"[SB_UPDATE_TARGET] Response: {response.text[:1000]}")
            
            if response.status_code >= 400:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}", "amazon_response": response.text}
            
            data = response.json()
            
            if isinstance(data, list):
                success_count = sum(1 for item in data if item.get("code") == "SUCCESS")
                error_items = [item for item in data if item.get("errors") or (item.get("code") and item.get("code") != "SUCCESS")]
                if error_items:
                    return {"success": False, "error": json.dumps(error_items), "amazon_response": data}
                if success_count > 0:
                    return {"success": True, "results": data, "amazon_response": data}
                return {"success": True, "results": data, "amazon_response": data}
            
            success_list = data.get("updateTargetSuccessResults", [])
            error_list = data.get("updateTargetErrorResults", [])
            
            if error_list:
                return {"success": False, "error": json.dumps(error_list), "amazon_response": data}
            if success_list:
                return {"success": True, "results": success_list, "amazon_response": data}
            return {"success": True, "results": data, "amazon_response": data}
        except Exception as e:
            logger.error(f"Failed to update SB target bid: {e}")
            return {"success": False, "error": str(e), "amazon_response": None}
    
    def update_sb_keyword_bid(self, keyword_id: str, new_bid: float, ad_group_id: str = None, api_url: str = None) -> dict:
        """Update the bid for a single SB keyword.
        
        Uses Accept: */* which works for all SB endpoints.
        SB keywords require adGroupId in payload.
        """
        if not keyword_id or str(keyword_id).strip() == '':
            return {"success": False, "error": "keyword_id vuoto o mancante", "amazon_response": None}
        
        import json
        base_url = api_url or self.api_url or API_REGIONS["EU"]["url"]
        url = f"{base_url}/sb/keywords"
        
        keyword_obj = {"keywordId": int(keyword_id), "bid": round(new_bid, 2)}
        if ad_group_id:
            keyword_obj["adGroupId"] = int(ad_group_id)
        
        payload = [keyword_obj]
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Amazon-Advertising-API-Scope": str(self.profile_id),
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Accept": "*/*",
            "Content-Type": "application/json",
        }
        
        print(f"[SB_UPDATE_KEYWORD] PUT {url}")
        print(f"[SB_UPDATE_KEYWORD] Headers: Accept=*/*, Content-Type=application/json")
        print(f"[SB_UPDATE_KEYWORD] Payload: {payload}")
        
        try:
            response = requests.put(url, headers=headers, data=json.dumps(payload))
            print(f"[SB_UPDATE_KEYWORD] Response status: {response.status_code}")
            print(f"[SB_UPDATE_KEYWORD] Response: {response.text[:1000]}")
            
            if response.status_code >= 400:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}", "amazon_response": response.text}
            
            data = response.json()
            
            if isinstance(data, list):
                success_count = sum(1 for item in data if item.get("code") == "SUCCESS")
                error_items = [item for item in data if item.get("errors") or (item.get("code") and item.get("code") != "SUCCESS")]
                if error_items:
                    return {"success": False, "error": json.dumps(error_items), "amazon_response": data}
                if success_count > 0:
                    return {"success": True, "results": data, "amazon_response": data}
                return {"success": True, "results": data, "amazon_response": data}
            
            success_list = data.get("updateKeywordSuccessResults", [])
            error_list = data.get("updateKeywordErrorResults", [])
            
            if error_list:
                return {"success": False, "error": json.dumps(error_list), "amazon_response": data}
            if success_list:
                return {"success": True, "results": success_list, "amazon_response": data}
            return {"success": True, "results": data, "amazon_response": data}
        except Exception as e:
            logger.error(f"Failed to update SB keyword bid: {e}")
            return {"success": False, "error": str(e), "amazon_response": None}
    
    def get_updated_tokens(self) -> Optional[Tuple[str, str, datetime]]:
        if self.token_refreshed and self.expires_at:
            return self.access_token, self.refresh_token, self.expires_at
        return None


def get_amazon_profiles(account_id: int) -> Tuple[list[dict], Optional[dict]]:
    from db.accounts_db import get_client_tokens, save_client_tokens
    
    token_data = get_client_tokens(account_id)
    if not token_data:
        return [], {"error": "Account not connected to Amazon Ads", "code": "NO_TOKENS"}
    
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    if not access_token or not refresh_token:
        return [], {"error": "Invalid token data", "code": "INVALID_TOKENS"}
    
    service = AmazonAdsService(access_token, refresh_token, account_id)
    
    try:
        profiles, partial_errors = service.get_profiles()
        
        updated_tokens = service.get_updated_tokens()
        if updated_tokens:
            new_access, new_refresh, expires_at = updated_tokens
            save_client_tokens(account_id, new_access, new_refresh, expires_at)
        
        warning = None
        if partial_errors:
            warning = {"warning": f"Some regions failed: {'; '.join(partial_errors)}", "code": "PARTIAL_SUCCESS"}
        
        return profiles, warning
    except AmazonAuthError as e:
        return [], {"error": f"Amazon authentication failed: {str(e)}. Please reconnect the account.", "code": "AUTH_FAILED"}
    except AmazonAPIError as e:
        return [], {"error": f"Amazon API error: {str(e)}", "code": "API_ERROR"}
    except requests.exceptions.RequestException as e:
        return [], {"error": f"Network error: {str(e)}", "code": "NETWORK_ERROR"}
    except Exception as e:
        return [], {"error": f"Unexpected error: {str(e)}", "code": "UNKNOWN_ERROR"}


def get_valid_access_token(account_id: int) -> Tuple[Optional[str], Optional[dict]]:
    """Get a valid access token for the account, always refreshing to ensure validity."""
    from db.accounts_db import get_client_tokens, save_client_tokens
    
    token_data = get_client_tokens(account_id)
    if not token_data:
        return None, {"error": "Account not connected to Amazon Ads", "code": "NO_TOKENS"}
    
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    if not access_token or not refresh_token:
        return None, {"error": "Invalid token data", "code": "INVALID_TOKENS"}
    
    service = AmazonAdsService(access_token, refresh_token, account_id)
    
    try:
        new_access, new_refresh, expires_at = service.refresh_access_token()
        save_client_tokens(account_id, new_access, new_refresh, expires_at)
        return new_access, None
    except AmazonAuthError as e:
        return None, {"error": f"Amazon authentication failed: {str(e)}. Please reconnect the account.", "code": "AUTH_FAILED"}
    except Exception as e:
        return None, {"error": f"Unexpected error: {str(e)}", "code": "UNKNOWN_ERROR"}


def get_amazon_campaigns(account_id: int, profile_id: str, api_url: str = None) -> Tuple[list[dict], Optional[dict]]:
    from db.accounts_db import get_client_tokens, save_client_tokens
    
    token_data = get_client_tokens(account_id)
    if not token_data:
        return [], {"error": "Account not connected to Amazon Ads", "code": "NO_TOKENS"}
    
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    if not access_token or not refresh_token:
        return [], {"error": "Invalid token data", "code": "INVALID_TOKENS"}
    
    service = AmazonAdsService(access_token, refresh_token, account_id)
    
    try:
        campaigns = service.get_campaigns(profile_id, api_url)
        
        updated_tokens = service.get_updated_tokens()
        if updated_tokens:
            new_access, new_refresh, expires_at = updated_tokens
            save_client_tokens(account_id, new_access, new_refresh, expires_at)
        
        return campaigns, None
    except AmazonAuthError as e:
        return [], {"error": f"Amazon authentication failed: {str(e)}. Please reconnect the account.", "code": "AUTH_FAILED"}
    except AmazonAPIError as e:
        return [], {"error": f"Amazon API error: {str(e)}", "code": "API_ERROR"}
    except requests.exceptions.RequestException as e:
        return [], {"error": f"Network error: {str(e)}", "code": "NETWORK_ERROR"}
    except Exception as e:
        return [], {"error": f"Unexpected error: {str(e)}", "code": "UNKNOWN_ERROR"}


def _register_key(targeting_map: dict, key: str, target_id: str):
    """
    Register a simple descriptive key in the targeting map.
    Registers key, key.lower(), and normalize_expr(key) for flexible matching.
    """
    from backend.app.services.bid_analyzer import normalize_expr
    
    if not key or not target_id:
        return
    targeting_map[key] = target_id
    if key.lower() != key:
        targeting_map[key.lower()] = target_id
    
    normalized = normalize_expr(key)
    if normalized and normalized != key and normalized != key.lower():
        targeting_map[normalized] = target_id


def get_amazon_keywords_and_targets(account_id: int, profile_id: str, api_url: str = None) -> Tuple[dict, dict, Optional[dict]]:
    """
    Get keywords and targets with their bids for a profile (SP + SB).
    
    Builds targeting_to_id_map using ONLY simple descriptive keys:
    
    SP KEYWORD: keywordText -> keywordId
    SP PRODUCT: asin="B..." -> targetId  
    SP CATEGORY: category="Nome" -> targetId
    SP AUTO/THEME: "close-match" -> targetId
    
    SB CATEGORY: category="Nome" -> targetId (SB KWS/ASIN use targetingId directly)
    
    Returns:
        Tuple of (keywords_map, targets_map, error)
        - keywords_map includes "_targeting_to_id" key with the lookup map
    """
    from db.accounts_db import get_client_tokens, save_client_tokens
    
    token_data = get_client_tokens(account_id)
    if not token_data:
        return {}, {}, {"error": "Account not connected to Amazon Ads", "code": "NO_TOKENS"}
    
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    if not access_token or not refresh_token:
        return {}, {}, {"error": "Invalid token data", "code": "INVALID_TOKENS"}
    
    service = AmazonAdsService(access_token, refresh_token, account_id)
    
    try:
        sp_keywords = service.get_keywords(profile_id, api_url)
        sp_product_targets = service.get_product_targets_query(profile_id, api_url, target_types=["PRODUCT", "PRODUCT_CATEGORY", "THEME"])
        sp_auto_targets = service.get_targets(profile_id, api_url)
        sp_targets = sp_product_targets + sp_auto_targets
        sb_targets = service.get_sb_targets(profile_id, api_url)
        
        sp_campaigns = service.get_campaigns(profile_id, api_url, include_paused=True)
        
        campaign_states_map = {}
        for camp in sp_campaigns:
            camp_id = str(camp.get("campaignId", ""))
            camp_state = (camp.get("state") or "ENABLED").upper()
            if camp_id:
                campaign_states_map[camp_id] = camp_state
        
        # SB campaigns: API endpoint is deprecated (403).
        # We cannot reliably determine SB campaign state.
        # SB targets are tagged with ad_product="SB" and analyze() skips campaign state check for SB.
        # SB actions are generated assuming all SB campaigns are ENABLED (since targets are fetched with stateFilter=enabled).
        
        state_counts = {}
        for s in campaign_states_map.values():
            state_counts[s] = state_counts.get(s, 0) + 1
        print(f"[CAMPAIGN STATES] Profile {profile_id}: {len(campaign_states_map)} SP campaigns - states: {state_counts}")
        
        updated_tokens = service.get_updated_tokens()
        if updated_tokens:
            new_access, new_refresh, expires_at = updated_tokens
            save_client_tokens(account_id, new_access, new_refresh, expires_at)
        
        keywords_map = {}
        targeting_to_id_map = {}
        targets_map = {}
        
        for kw in sp_keywords:
            kw_id = str(kw.get("keywordId", ""))
            if not kw_id:
                continue
            
            keyword_text = kw.get("keywordText", "")
            match_type = kw.get("matchType", "")
            campaign_id = str(kw.get("campaignId", ""))
            ad_group_id = str(kw.get("adGroupId", ""))
            
            keywords_map[kw_id] = {
                "bid": float(kw.get("bid", 0)) if kw.get("bid") else None,
                "keyword": keyword_text,
                "matchType": match_type,
                "campaignId": campaign_id,
                "adGroupId": ad_group_id,
                "state": kw.get("state", ""),
                "ad_product": "SP",
                "entity_type": "keyword",
            }
            
            targets_map[kw_id] = {
                "bid": float(kw.get("bid", 0)) if kw.get("bid") else None,
                "keywordText": keyword_text,
                "expression": keyword_text,
                "report_targeting": keyword_text,
                "targetType": "keyword",
                "campaignId": campaign_id,
                "adGroupId": ad_group_id,
                "state": kw.get("state", ""),
                "ad_product": "SP",
                "entity_type": "keyword",
            }
            
            if keyword_text:
                kw_normalized = keyword_text.lower().strip()
                composite_key = f"{campaign_id}_{ad_group_id}_kw={kw_normalized}"
                targeting_to_id_map[composite_key] = kw_id
                _register_key(targeting_to_id_map, keyword_text, kw_id)
        
        auto_map = {
            "queryHighRelMatches": "close-match",
            "queryBroadRelMatches": "loose-match",
            "asinSubstituteRelated": "substitutes",
            "asinAccessoryRelated": "complements",
            "QUERY_HIGH_REL_MATCHES": "close-match",
            "QUERY_BROAD_REL_MATCHES": "loose-match",
            "ASIN_SUBSTITUTE_RELATED": "substitutes",
            "ASIN_ACCESSORY_RELATED": "complements",
            "KEYWORDS_CLOSE_MATCH": "close-match",
            "KEYWORDS_LOOSE_MATCH": "loose-match",
            "PRODUCT_SUBSTITUTES": "substitutes",
            "PRODUCT_COMPLEMENTS": "complements",
            "CLOSE_MATCH": "close-match",
            "LOOSE_MATCH": "loose-match",
            "SUBSTITUTES": "substitutes",
            "COMPLEMENTS": "complements",
        }
        
        for tgt in sp_targets:
            tgt_id = str(tgt.get("targetId", ""))
            if not tgt_id:
                continue
                
            campaign_id = str(tgt.get("campaignId", ""))
            ad_group_id = str(tgt.get("adGroupId", ""))
            target_type = tgt.get("targetType", "")
            target_details = tgt.get("targetDetails", {})
            
            expression_value = ""
            report_targeting = ""
            
            bid_value = None
            bid_obj = tgt.get("bid")
            if isinstance(bid_obj, dict):
                bid_value = float(bid_obj.get("bid", 0)) if bid_obj.get("bid") else None
            elif bid_obj is not None:
                bid_value = float(bid_obj)
            
            if target_type == "PRODUCT":
                product_target = target_details.get("productTarget", {})
                product = product_target.get("product", {})
                asin = product.get("productId", "")
                if asin:
                    asin_upper = asin.upper()
                    expression_value = asin_upper
                    report_targeting = f'asin="{asin_upper}"'
                    composite_key = f"{campaign_id}_{ad_group_id}_asin={asin_upper}"
                    targeting_to_id_map[composite_key] = tgt_id
            
            elif target_type == "AUTO":
                auto_target = target_details.get("autoTarget", {})
                expr_list = auto_target.get("expression", [])
                
                for expr_item in expr_list:
                    expr_type = expr_item.get("type", "") if isinstance(expr_item, dict) else str(expr_item)
                    token = auto_map.get(expr_type)
                    if token:
                        expression_value = expr_type
                        report_targeting = token
                        composite_key = f"{campaign_id}_{ad_group_id}_{token}"
                        targeting_to_id_map[composite_key] = tgt_id
            
            elif target_type == "THEME":
                theme_target = target_details.get("themeTarget", {})
                match_type = theme_target.get("matchType", "")
                expression_value = match_type
                token = auto_map.get(match_type, match_type.lower() if match_type else "")
                report_targeting = token
                if token:
                    composite_key = f"{campaign_id}_{ad_group_id}_{token}"
                    targeting_to_id_map[composite_key] = tgt_id
            
            elif target_type == "CATEGORY":
                category_target = target_details.get("categoryTarget", {})
                category_name = category_target.get("categoryName", "") or tgt.get("categoryName", "")
                
                if category_name:
                    category_normalized = ' '.join(category_name.strip().split()).lower()
                    expression_value = category_name
                    report_targeting = f'category="{category_name}"'
                    composite_key = f"{campaign_id}_{ad_group_id}_category={category_normalized}"
                    targeting_to_id_map[composite_key] = tgt_id
            
            else:
                expr_list = tgt.get("expression", [])
                if expr_list and len(expr_list) > 0:
                    first_expr = expr_list[0]
                    if isinstance(first_expr, dict):
                        expr_type = first_expr.get("type", "")
                        expr_value = first_expr.get("value", "")
                        expression_value = expr_value or expr_type
                        if expr_type == "asinSameAs" and expr_value:
                            asin_upper = expr_value.upper()
                            report_targeting = f'asin="{asin_upper}"'
                            composite_key = f"{campaign_id}_{ad_group_id}_asin={asin_upper}"
                            targeting_to_id_map[composite_key] = tgt_id
            
            targets_map[tgt_id] = {
                "bid": bid_value,
                "expression": expression_value,
                "report_targeting": report_targeting,
                "targetType": target_type,
                "campaignId": campaign_id,
                "adGroupId": ad_group_id,
                "state": tgt.get("state", ""),
                "ad_product": "SP",
                "entity_type": "target",
            }
            
            keywords_map[tgt_id] = {
                "bid": bid_value,
                "keyword": report_targeting or expression_value,
                "matchType": "",
                "campaignId": campaign_id,
                "adGroupId": ad_group_id,
                "state": tgt.get("state", ""),
                "ad_product": "SP",
                "entity_type": "target",
            }
        
        for tgt in sb_targets:
            sb_type = tgt.get("_sb_type", "")
            campaign_id = str(tgt.get("campaignId", ""))
            ad_group_id = str(tgt.get("adGroupId", ""))
            
            bid_value = None
            bid_obj = tgt.get("bid")
            if isinstance(bid_obj, dict):
                bid_value = float(bid_obj.get("bid", 0)) if bid_obj.get("bid") else None
            elif bid_obj is not None:
                bid_value = float(bid_obj)
            
            if sb_type == "keyword":
                kw_id = str(tgt.get("keywordId", ""))
                if not kw_id:
                    continue
                keyword_text = tgt.get("keywordText", "")
                match_type = tgt.get("matchType", "")
                
                keywords_map[kw_id] = {
                    "bid": bid_value,
                    "keyword": keyword_text,
                    "matchType": match_type,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": tgt.get("state", ""),
                    "ad_product": "SB",
                    "entity_type": "keyword",
                }
                
                if keyword_text:
                    composite_key = f"{campaign_id}:{ad_group_id}:kw:{keyword_text.lower().strip()}:{match_type.lower()}"
                    targeting_to_id_map[composite_key] = kw_id
                    _register_key(targeting_to_id_map, keyword_text, kw_id)
                continue
            
            tgt_id = str(tgt.get("targetId", ""))
            if not tgt_id:
                continue
            
            target_type = tgt.get("targetType", "")
            expression_value = ""
            report_targeting = ""
            
            if target_type in ("PRODUCT", "ASIN"):
                product_target = tgt.get("productTarget", {})
                product = product_target.get("product", {})
                asin = product.get("productId", "") or tgt.get("asin", "")
                if asin:
                    expression_value = asin
                    report_targeting = f'asin="{asin}"'
                    from backend.app.services.bid_analyzer import normalize_expr
                    normalized_target = normalize_expr(report_targeting).lower()
                    composite_key = f"{campaign_id}:{ad_group_id}:target:{normalized_target}"
                    targeting_to_id_map[composite_key] = tgt_id
                    _register_key(targeting_to_id_map, f'asin="{asin}"', tgt_id)
                
                targets_map[tgt_id] = {
                    "bid": bid_value,
                    "expression": expression_value,
                    "report_targeting": report_targeting,
                    "targetType": target_type,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": tgt.get("state", ""),
                    "ad_product": "SB",
                    "entity_type": "target",
                }
                
                keywords_map[tgt_id] = {
                    "bid": bid_value,
                    "keyword": report_targeting or expression_value,
                    "matchType": "",
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": tgt.get("state", ""),
                    "ad_product": "SB",
                    "entity_type": "target",
                }
            
            elif target_type == "CATEGORY":
                category_target = tgt.get("productTarget", {}).get("category", {})
                category_name = category_target.get("categoryName", "") or tgt.get("categoryName", "")
                
                if category_name:
                    expression_value = category_name
                    report_targeting = f'category="{category_name}"'
                    from backend.app.services.bid_analyzer import normalize_expr
                    normalized_target = normalize_expr(report_targeting).lower()
                    composite_key = f"{campaign_id}:{ad_group_id}:target:{normalized_target}"
                    targeting_to_id_map[composite_key] = tgt_id
                    _register_key(targeting_to_id_map, f'category="{category_name}"', tgt_id)
                
                targets_map[tgt_id] = {
                    "bid": bid_value,
                    "expression": expression_value,
                    "report_targeting": report_targeting,
                    "targetType": target_type,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": tgt.get("state", ""),
                    "ad_product": "SB",
                    "entity_type": "target",
                }
                
                keywords_map[tgt_id] = {
                    "bid": bid_value,
                    "keyword": report_targeting or expression_value,
                    "matchType": "",
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": tgt.get("state", ""),
                    "ad_product": "SB",
                    "entity_type": "target",
                }
            
            else:
                targets_map[tgt_id] = {
                    "bid": bid_value,
                    "expression": "",
                    "report_targeting": "",
                    "targetType": target_type,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": tgt.get("state", ""),
                    "ad_product": "SB",
                    "entity_type": "target",
                }
                
                keywords_map[tgt_id] = {
                    "bid": bid_value,
                    "keyword": "",
                    "matchType": "",
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": tgt.get("state", ""),
                    "ad_product": "SB",
                    "entity_type": "target",
                }
        
        keywords_map["_targeting_to_id"] = targeting_to_id_map
        keywords_map["_campaign_states"] = campaign_states_map
        
        sp_target_types = {}
        for tgt in sp_targets:
            tt = tgt.get("targetType", "UNKNOWN")
            sp_target_types[tt] = sp_target_types.get(tt, 0) + 1
        
        logger.info(f"[targeting_to_id_map] Built map with {len(targeting_to_id_map)} keys for profile {profile_id}")
        logger.info(f"[targeting_to_id_map] SP keywords: {len(sp_keywords)}, SP targets: {len(sp_targets)}, SB targets: {len(sb_targets)}")
        logger.info(f"[targeting_to_id_map] SP target types breakdown: {sp_target_types}")
        sample_keys = list(targeting_to_id_map.keys())[:20]
        logger.info(f"[targeting_to_id_map] Sample keys: {sample_keys}")
        
        asin_keys = [k for k in targeting_to_id_map.keys() if 'asin=' in k.lower()][:5]
        auto_keys = [k for k in targeting_to_id_map.keys() if k in ('close-match', 'loose-match', 'substitutes', 'complements')]
        logger.info(f"[targeting_to_id_map] ASIN keys sample: {asin_keys}")
        logger.info(f"[targeting_to_id_map] AUTO keys: {auto_keys}")
        
        return keywords_map, targets_map, None
    except AmazonAuthError as e:
        return {}, {}, {"error": f"Amazon authentication failed: {str(e)}. Please reconnect the account.", "code": "AUTH_FAILED"}
    except AmazonAPIError as e:
        return {}, {}, {"error": f"Amazon API error: {str(e)}", "code": "API_ERROR"}
    except requests.exceptions.RequestException as e:
        return {}, {}, {"error": f"Network error: {str(e)}", "code": "NETWORK_ERROR"}
    except Exception as e:
        return {}, {}, {"error": f"Unexpected error: {str(e)}", "code": "UNKNOWN_ERROR"}


def get_campaign_names_map(account_id: int, profile_id: str, api_url: str = None) -> Tuple[dict, Optional[dict]]:
    """
    Get a map of campaign_id -> campaign_name for a profile.
    """
    campaigns, error = get_amazon_campaigns(account_id, profile_id, api_url)
    if error:
        return {}, error
    
    campaign_map = {}
    for c in campaigns:
        cid = str(c.get("campaignId", ""))
        if cid:
            campaign_map[cid] = c.get("name", "")
    
    return campaign_map, None


def get_sb_campaign_names_map(account_id: int, profile_id: str, api_url: str = None) -> Tuple[dict, Optional[dict]]:
    """
    Get a map of campaign_id -> campaign_name for SB campaigns.
    """
    from db.accounts_db import get_client_tokens, save_client_tokens
    
    token_data = get_client_tokens(account_id)
    if not token_data:
        return {}, {"error": "Account not connected to Amazon Ads", "code": "NO_TOKENS"}
    
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    if not access_token or not refresh_token:
        return {}, {"error": "Invalid token data", "code": "INVALID_TOKENS"}
    
    service = AmazonAdsService(access_token, refresh_token, account_id)
    
    try:
        sb_campaigns = service.get_sb_campaigns(profile_id, api_url, include_paused=True)
        
        updated_tokens = service.get_updated_tokens()
        if updated_tokens:
            new_access, new_refresh, expires_at = updated_tokens
            save_client_tokens(account_id, new_access, new_refresh, expires_at)
        
        campaign_map = {}
        for c in sb_campaigns:
            cid = str(c.get("campaignId", ""))
            if cid:
                campaign_map[cid] = c.get("name", "")
        
        return campaign_map, None
    except Exception as e:
        return {}, {"error": f"Failed to get SB campaigns: {str(e)}", "code": "API_ERROR"}


def get_campaign_to_asin_map(account_id: int, profile_id: str, api_url: str = None) -> Tuple[dict, Optional[dict]]:
    """
    Get a map of campaign_id -> asin by fetching productAds from Amazon API.
    This allows associating each campaign with its advertised product's ASIN.
    """
    from db.accounts_db import get_client_tokens, save_client_tokens
    
    token_data = get_client_tokens(account_id)
    if not token_data:
        return {}, {"error": "Account not connected to Amazon Ads", "code": "NO_TOKENS"}
    
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    
    if not access_token or not refresh_token:
        return {}, {"error": "Invalid token data", "code": "INVALID_TOKENS"}
    
    service = AmazonAdsService(access_token, refresh_token, account_id)
    
    if not api_url:
        api_url = "https://advertising-api.amazon.com"
    
    try:
        headers = {
            "Authorization": f"Bearer {service.access_token}",
            "Amazon-Advertising-API-ClientId": CLIENT_ID,
            "Amazon-Advertising-API-Scope": profile_id,
            "Content-Type": "application/vnd.spProductAd.v3+json",
            "Accept": "application/vnd.spProductAd.v3+json",
        }
        
        url = f"{api_url}/sp/productAds/list"
        campaign_to_asin = {}
        next_token = None
        
        while True:
            payload = {"maxResults": 1000}
            if next_token:
                payload["nextToken"] = next_token
            
            response = service._make_request(url, headers, method="POST", json_data=payload)
            data = response.json()
            
            product_ads = data.get("productAds", [])
            
            for ad in product_ads:
                campaign_id = ad.get("campaignId")
                asin = ad.get("asin")
                if campaign_id and asin:
                    campaign_to_asin[str(campaign_id)] = asin.upper()
            
            next_token = data.get("nextToken")
            if not next_token:
                break
        
        updated_tokens = service.get_updated_tokens()
        if updated_tokens:
            new_access, new_refresh, expires_at = updated_tokens
            save_client_tokens(account_id, new_access, new_refresh, expires_at)
        
        logger.info(f"[CAMPAIGN_ASIN_MAP] Profile {profile_id}: {len(campaign_to_asin)} campaigns mapped to ASINs")
        
        return campaign_to_asin, None
    except AmazonAuthError as e:
        return {}, {"error": f"Amazon authentication failed: {str(e)}. Please reconnect the account.", "code": "AUTH_FAILED"}
    except AmazonAPIError as e:
        return {}, {"error": f"Amazon API error: {str(e)}", "code": "API_ERROR"}
    except requests.exceptions.RequestException as e:
        return {}, {"error": f"Network error: {str(e)}", "code": "NETWORK_ERROR"}
    except Exception as e:
        return {}, {"error": f"Unexpected error: {str(e)}", "code": "UNKNOWN_ERROR"}
