# amazon_api/targets.py

import json
import requests
from backend.app.services.amazon_ads.config import API_BASE_URL, CLIENT_ID


def get_keywords_for_campaign(access_token, profile_id, campaign_id, api_url=None):
    """
    Restituisce tutte le keyword SP per una campagna con i loro bid.
    Usa l'endpoint /sp/keywords/list della API v3.
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/sp/keywords/list"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Accept": "application/vnd.spKeyword.v3+json",
        "Content-Type": "application/vnd.spKeyword.v3+json",
    }
    
    payload = {
        "campaignIdFilter": {"include": [str(campaign_id)]},
        "stateFilter": {"include": ["ENABLED", "PAUSED"]},
        "maxResults": 10000,
    }
    
    print(f"[GET_KEYWORDS] Fetching keywords for campaign {campaign_id}...")
    
    resp = requests.post(url, headers=headers, json=payload)
    
    print(f"[GET_KEYWORDS] Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"[GET_KEYWORDS] Error: {resp.text[:500]}")
        resp.raise_for_status()
    
    data = resp.json()
    keywords = data.get("keywords", [])
    
    print(f"[GET_KEYWORDS] Found {len(keywords)} keywords for campaign {campaign_id}")
    
    for kw in keywords[:5]:
        print(f"  - {kw.get('keywordId')}: {kw.get('keywordText')} bid={kw.get('bid')}")
    
    if len(keywords) > 5:
        print(f"  ... and {len(keywords) - 5} more")
    
    return keywords


def get_targets_for_campaign(access_token, profile_id, campaign_id, api_url=None):
    """
    Restituisce tutti i target (keyword, product, auto, ecc.) per una campagna SP.

    Nota importante:
    - Questo endpoint è principalmente "configurativo".
    - Le metriche di performance per timeframe (impressions, clicks, ordini, ACOS)
      NON sono garantite qui e vanno prese tramite i REPORT ufficiali di Amazon Ads.
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/adsApi/v1/query/targets"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Ads-CustomerId": str(profile_id),
        "Amazon-Ads-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Non filtriamo piu solo targetType = KEYWORD.
    # Così vediamo:
    # - keyword target
    # - product target
    # - auto target
    payload = {
        "adProductFilter": {"include": ["SPONSORED_PRODUCTS"]},
        "campaignIdFilter": {"include": [str(campaign_id)]},
        # "targetTypeFilter": {"include": ["KEYWORD"]},  # rimosso per includere tutto
        "stateFilter": {"include": ["ENABLED", "PAUSED"]},
        "maxResults": 1000,
    }

    resp = requests.post(url, headers=headers, json=payload)

    print("============================")
    print("=== QUERY TARGETS RESULT ===")
    print(resp.status_code, resp.text)
    print("============================\n")

    resp.raise_for_status()
    data = resp.json()

    targets = data.get("targets", [])
    print(f"Trovati {len(targets)} target.\n")

    # Log base per capire cosa arriva
    for t in targets:
        tid = t.get("targetId")
        target_type = t.get("targetType")
        td = t.get("targetDetails", {}) or {}
        bid = (t.get("bid") or {}).get("bid")

        # Estrai identificatore in base al tipo di target
        expression = None
        info = "unknown"
        
        if "keywordTarget" in td:
            # Keyword: targetDetails.keywordTarget.keyword
            kw_data = td.get("keywordTarget") or {}
            expression = kw_data.get("keyword")
            mt = kw_data.get("matchType", "")
            info = f"keyword:{expression} ({mt})"
        elif "productTarget" in td:
            # Product: targetDetails.productTarget.product.productId
            pt = td.get("productTarget") or {}
            product = pt.get("product") or {}
            expression = product.get("productId")
            match_type = pt.get("matchType", "PRODUCT_EXACT")
            info = f"product:{expression} ({match_type})"
        elif "autoTarget" in td:
            # Auto: targetDetails.autoTarget.expression[0].type
            at = td.get("autoTarget") or {}
            expressions = at.get("expression") or []
            if expressions:
                expression = expressions[0].get("type")
            info = f"auto:{expression}"
        elif "asinCategoryTarget" in td:
            info = "asinCategoryTarget"
        elif "asinBrandTarget" in td:
            info = "asinBrandTarget"

        print(f"- {tid} | type={target_type} | {info} | bid={bid}")

    return targets
