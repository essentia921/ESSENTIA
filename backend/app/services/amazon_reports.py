import os
import gzip
import requests
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from backend.app.services.amazon import API_REGIONS, get_api_url_for_country

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 10

CLIENT_ID = os.getenv("AMAZON_ADS_CLIENT_ID")
CLIENT_SECRET = os.getenv("AMAZON_ADS_CLIENT_SECRET")
REPORTS_DIR = "reports_data"

os.makedirs(REPORTS_DIR, exist_ok=True)


def get_date_range(days: int) -> Tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    end_date = today - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def create_report(
    access_token: str,
    profile_id: str,
    api_url: str,
    report_type: str,
    start_date: str,
    end_date: str,
    ad_product: str = "SP"
) -> str:
    """
    Create an Amazon Ads report for SP (Sponsored Products) or SB (Sponsored Brands).
    
    ad_product: 'SP' for Sponsored Products, 'SB' for Sponsored Brands
    """
    if ad_product == "SB":
        if report_type == "SB_TARGETING_14D":
            columns = [
                "campaignId",
                "campaignName",
                "adGroupId",
                "keywordId",
                "targetingId",
                "keywordText",
                "targetingExpression",
                "matchType",
                "keywordBid",
                "impressions",
                "clicks",
                "cost",
                "sales",
                "purchases"
            ]
            name = "SB_TARGETING_14D"
        else:
            columns = [
                "campaignId",
                "campaignName",
                "adGroupId",
                "keywordId",
                "targetingId",
                "keywordText",
                "targetingExpression",
                "matchType",
                "keywordBid",
                "impressions",
                "clicks",
                "cost",
                "sales",
                "purchases"
            ]
            name = "SB_TARGETING_30D"
        
        payload = {
            "name": name,
            "startDate": start_date,
            "endDate": end_date,
            "configuration": {
                "adProduct": "SPONSORED_BRANDS",
                "reportTypeId": "sbTargeting",
                "groupBy": ["targeting"],
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON",
                "columns": columns
            }
        }
    else:
        if report_type == "SP_TARGETING_14D":
            columns = [
                "campaignId",
                "campaignName",
                "adGroupId",
                "keywordId",
                "targetId",
                "keyword",
                "targeting",
                "matchType",
                "keywordBid",
                "advertisedAsin",
                "impressions",
                "clicks",
                "cost",
                "sales14d",
                "purchases14d"
            ]
            name = "SP_TARGETING_14D"
        else:
            columns = [
                "campaignId",
                "campaignName",
                "adGroupId",
                "keywordId",
                "targetId",
                "keyword",
                "targeting",
                "matchType",
                "keywordBid",
                "advertisedAsin",
                "impressions",
                "clicks",
                "cost",
                "sales30d",
                "purchases30d"
            ]
            name = "SP_TARGETING_30D"
        
        payload = {
            "name": name,
            "startDate": start_date,
            "endDate": end_date,
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "reportTypeId": "spTargeting",
                "groupBy": ["targeting"],
                "timeUnit": "SUMMARY",
                "format": "GZIP_JSON",
                "columns": columns
            }
        }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": profile_id,
        "Content-Type": "application/json",
    }
    
    logger.info(f"Creating report: {api_url}/reporting/reports")
    logger.info(f"Payload: {payload}")
    
    response = None
    for attempt in range(MAX_RETRIES):
        response = requests.post(
            f"{api_url}/reporting/reports",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 429:
            wait_time = RETRY_DELAY_SECONDS * (2 ** attempt)
            logger.warning(f"Got 429 throttled, waiting {wait_time}s before retry {attempt + 1}/{MAX_RETRIES}")
            time.sleep(wait_time)
            continue
        else:
            break
    
    if response is None or response.status_code == 429:
        logger.error(f"Report creation failed after {MAX_RETRIES} retries due to throttling")
        raise requests.exceptions.HTTPError(f"429 throttled after {MAX_RETRIES} retries")
    
    if response.status_code == 425:
        import re
        text = response.text
        match = re.search(r'duplicate of\s*:\s*([a-f0-9-]+)', text, re.IGNORECASE)
        if match:
            duplicate_id = match.group(1)
            logger.info(f"Report is duplicate, using existing: {duplicate_id}")
            return duplicate_id
        logger.error(f"Report creation failed with 425 but no duplicate ID found: {text}")
        response.raise_for_status()
    
    if response.status_code != 200:
        logger.error(f"Report creation failed: {response.status_code}")
        logger.error(f"Response: {response.text}")
    
    response.raise_for_status()
    
    data = response.json()
    return data["reportId"]


def check_report_status(
    access_token: str,
    profile_id: str,
    api_url: str,
    report_id: str
) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": profile_id,
    }
    
    response = requests.get(
        f"{api_url}/reporting/reports/{report_id}",
        headers=headers,
        timeout=15
    )
    response.raise_for_status()
    
    data = response.json()
    return {
        "status": data.get("status"),
        "url": data.get("url"),
        "failureReason": data.get("failureReason")
    }


def download_report(download_url: str, report_id: str, profile_id: str, report_type: str) -> str:
    response = requests.get(download_url, timeout=60)
    response.raise_for_status()
    
    raw = gzip.decompress(response.content)
    
    filename = f"{report_type.lower()}_{profile_id}_{report_id}.json"
    file_path = os.path.join(REPORTS_DIR, filename)
    
    with open(file_path, "wb") as f:
        f.write(raw)
    
    logger.info(f"Report saved: {file_path}")
    return file_path


def read_report_content(file_path: str) -> Optional[str]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Report file not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading report: {e}")
        return None


def check_report_status_with_service(service, profile_id: str, api_url: str, report_id: str) -> dict:
    headers = {
        "Authorization": f"Bearer {service.access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": profile_id,
    }
    
    url = f"{api_url}/reporting/reports/{report_id}"
    response = service._make_request(url, headers)
    
    data = response.json()
    return {
        "status": data.get("status"),
        "url": data.get("url"),
        "failureReason": data.get("failureReason")
    }


def download_report_with_service(service, download_url: str) -> dict:
    import json
    
    response = requests.get(download_url, timeout=60)
    response.raise_for_status()
    
    raw = gzip.decompress(response.content)
    return json.loads(raw.decode('utf-8'))


def download_and_parse(download_url: str) -> dict:
    """
    Download report from URL, decompress gzip and parse JSON.
    This is the single place for gzip decompression and JSON parsing.
    
    Args:
        download_url: The URL to download the report from
        
    Returns:
        Parsed JSON data as dict
    """
    import json
    
    response = requests.get(download_url, timeout=60)
    response.raise_for_status()
    
    raw = gzip.decompress(response.content)
    return json.loads(raw.decode('utf-8'))
