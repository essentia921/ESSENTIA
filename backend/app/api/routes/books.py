import logging
import os
import re
from typing import List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.services.amazon import AmazonAdsService, get_api_url_for_country
from db.accounts_db import get_all_client_accounts, get_client_profiles, get_client_tokens, save_client_tokens
from backend.app.services.kdp_calculator import (
    calculate_printing_cost,
    calculate_hardcover_printing_cost,
    calculate_acos_values,
    get_trim_category,
    ACOS_RATIO,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/books", tags=["books"])

OXYLABS_USER = os.environ.get("OXYLABS_USER", "")
OXYLABS_PASS = os.environ.get("OXYLABS_PASS", "")


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


OXYLABS_URL = "https://realtime.oxylabs.io/v1/queries"


def get_db_connection():
    return psycopg2.connect(settings.DATABASE_URL)


class BookResponse(BaseModel):
    id: int
    asin: str
    profile_id: Optional[str]
    marketplace: Optional[str]
    title: Optional[str]
    subtitle: Optional[str]
    link: Optional[str]
    format: Optional[str]
    pages: Optional[int]
    width_inches: Optional[float]
    height_inches: Optional[float]
    trim_size: Optional[str]
    ink_type: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    c_print: Optional[float]
    royalty_rate: Optional[float]
    r_net: Optional[float]
    acos_be: Optional[float]
    acos_opt: Optional[float]
    synced_at: Optional[datetime]


class SyncRequest(BaseModel):
    asin: str
    marketplace: str = "US"


class BulkSyncRequest(BaseModel):
    marketplace: str = "US"


@router.get("/asins")
async def get_unique_asins():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT report_data, profile_id 
            FROM amazon_reports 
            WHERE status = 'COMPLETED' AND report_data IS NOT NULL
        """)
        reports = cur.fetchall()
        
        asins = set()
        for report in reports:
            report_data = report.get("report_data")
            if report_data:
                if isinstance(report_data, dict):
                    rows = report_data.get("rows", report_data.get("data", []))
                elif isinstance(report_data, list):
                    rows = report_data
                else:
                    continue
                
                for row in rows:
                    asin = row.get("advertisedAsin") or row.get("asin")
                    if asin and len(asin) == 10 and asin.startswith("B"):
                        asins.add(asin)
        
        cur.execute("SELECT asin FROM books")
        existing = {r["asin"] for r in cur.fetchall()}
        
        return {
            "total_asins": len(asins),
            "new_asins": len(asins - existing),
            "existing_asins": len(asins & existing),
            "asins": sorted(list(asins)),
        }
    finally:
        cur.close()
        conn.close()


@router.post("/import-asins")
async def import_asins_from_reports():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT report_data, profile_id 
            FROM amazon_reports 
            WHERE status = 'COMPLETED' AND report_data IS NOT NULL
        """)
        reports = cur.fetchall()
        
        asins = set()
        for report in reports:
            report_data = report.get("report_data")
            if report_data:
                if isinstance(report_data, dict):
                    rows = report_data.get("rows", report_data.get("data", []))
                elif isinstance(report_data, list):
                    rows = report_data
                else:
                    continue
                
                for row in rows:
                    asin = row.get("advertisedAsin") or row.get("asin")
                    if asin and len(asin) == 10 and asin.startswith("B"):
                        asins.add(asin)
        
        imported = 0
        for asin in asins:
            cur.execute("""
                INSERT INTO books (asin) 
                VALUES (%s) 
                ON CONFLICT (asin) DO NOTHING
            """, (asin,))
            if cur.rowcount > 0:
                imported += 1
        
        conn.commit()
        return {"imported": imported, "total": len(asins)}
    finally:
        cur.close()
        conn.close()


AMAZON_CLIENT_ID = os.getenv("AMAZON_ADS_CLIENT_ID")


def get_campaign_asins(service: AmazonAdsService, profile_id: str, campaign_id: str, api_url: str) -> List[str]:
    try:
        ad_groups_url = f"{api_url}/sp/adGroups/list"
        headers = {
            "Authorization": f"Bearer {service.access_token}",
            "Amazon-Advertising-API-ClientId": AMAZON_CLIENT_ID,
            "Amazon-Advertising-API-Scope": profile_id,
            "Content-Type": "application/vnd.spAdGroup.v3+json",
            "Accept": "application/vnd.spAdGroup.v3+json",
        }
        payload = {"campaignIdFilter": {"include": [campaign_id]}}
        
        response = service._make_request(ad_groups_url, headers, method="POST", json_data=payload)
        ad_groups = response.json().get("adGroups", [])
        
        if not ad_groups:
            return []
        
        asins = []
        for ad_group in ad_groups:
            ad_group_id = ad_group.get("adGroupId")
            if not ad_group_id:
                continue
            
            product_ads_url = f"{api_url}/sp/productAds/list"
            headers["Content-Type"] = "application/vnd.spProductAd.v3+json"
            headers["Accept"] = "application/vnd.spProductAd.v3+json"
            payload = {"adGroupIdFilter": {"include": [ad_group_id]}}
            
            response = service._make_request(product_ads_url, headers, method="POST", json_data=payload)
            product_ads = response.json().get("productAds", [])
            
            for ad in product_ads:
                asin = ad.get("asin")
                if asin and len(asin) == 10 and asin.startswith("B"):
                    asins.append(asin)
        
        return asins
    except Exception as e:
        logger.warning(f"Error getting ASINs for campaign {campaign_id}: {e}")
        return []


@router.post("/sync-from-amazon")
async def sync_asins_from_amazon(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    accounts = get_all_client_accounts(user_id=user.id)
    
    if not accounts:
        raise HTTPException(status_code=404, detail="Nessun account Amazon collegato")
    
    all_asins = []
    processed_profiles = 0
    errors = []
    
    for account in accounts:
        account_id = account.get("id")
        account_name = account.get("client_name", f"Account {account_id}")
        
        tokens = get_client_tokens(account_id)
        if not tokens:
            errors.append(f"{account_name}: Token non trovati")
            continue
        
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        
        if not access_token or not refresh_token:
            errors.append(f"{account_name}: Token non validi")
            continue
        
        service = AmazonAdsService(access_token, refresh_token, account_id)
        
        profiles = get_client_profiles(account_id)
        if not profiles:
            try:
                profiles_data, _ = service.get_profiles()
                profiles = profiles_data
            except Exception as e:
                errors.append(f"{account_name}: Errore recupero profili: {str(e)}")
                continue
        
        for profile in profiles:
            try:
                profile_data = profile.get("profile_data", profile) if isinstance(profile, dict) else profile
                profile_id = str(profile_data.get("profileId") or profile_data.get("profile_id", ""))
                country_code = profile_data.get("countryCode") or profile_data.get("country_code", "")
                api_url = profile_data.get("_api_url") or profile_data.get("api_url") or get_api_url_for_country(country_code)
                
                if not profile_id:
                    continue
                
                campaigns = service.get_campaigns(profile_id, api_url)
                processed_profiles += 1
                
                marketplace = country_code.upper() if country_code else "US"
                
                enabled_campaigns = [c for c in campaigns if c.get("state") == "ENABLED"]
                
                def fetch_asins(campaign_id):
                    return get_campaign_asins(service, profile_id, campaign_id, api_url)
                
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = []
                    for campaign in enabled_campaigns:
                        campaign_id = str(campaign.get("campaignId"))
                        if campaign_id:
                            futures.append(executor.submit(fetch_asins, campaign_id))
                    
                    for future in as_completed(futures):
                        try:
                            asins = future.result()
                            for asin in asins:
                                all_asins.append({"asin": asin, "marketplace": marketplace, "profile_id": profile_id})
                        except Exception as e:
                            logger.warning(f"Error fetching ASINs: {e}")
                
            except Exception as e:
                errors.append(f"{account_name}/{profile_id}: {str(e)}")
        
        updated_tokens = service.get_updated_tokens()
        if updated_tokens:
            new_access, new_refresh, expires_at = updated_tokens
            save_client_tokens(account_id, new_access, new_refresh, expires_at)
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT asin, profile_id FROM books")
        existing_pairs = {(r["asin"], r["profile_id"]) for r in cur.fetchall()}
        
        unique_asins = {}
        for item in all_asins:
            key = (item["asin"], item["profile_id"])
            if key not in unique_asins:
                unique_asins[key] = item["marketplace"]
        
        imported = 0
        new_asin_list = []
        for (asin, pid), mkt in unique_asins.items():
            if (asin, pid) in existing_pairs:
                continue
            cur.execute("""
                INSERT INTO books (asin, marketplace, profile_id) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (asin, profile_id) DO NOTHING
            """, (asin, mkt, pid))
            if cur.rowcount > 0:
                imported += 1
                new_asin_list.append((asin, mkt, pid))
        
        conn.commit()
        
    finally:
        cur.close()
        conn.close()
    
    sync_results = {"synced": 0, "failed": 0, "filtered": 0, "sync_errors": []}
    VALID_FORMATS = ["paperback", "hardcover", "hardback", "copertina flessibile", "copertina rigida", "tapa blanda", "tapa dura", "broché", "relié", "taschenbuch", "gebundene ausgabe"]
    
    for asin, mkt, pid in new_asin_list:
        try:
            result = await sync_single_book(asin, marketplace=mkt, profile_id=pid)
            book_format = (result.get("book", {}).get("format") or "").lower()
            
            is_valid_format = any(valid in book_format for valid in VALID_FORMATS)
            if not is_valid_format and book_format:
                conn2 = get_db_connection()
                cur2 = conn2.cursor()
                cur2.execute("DELETE FROM books WHERE asin = %s AND profile_id = %s", (asin, pid))
                conn2.commit()
                cur2.close()
                conn2.close()
                sync_results["filtered"] += 1
                logger.info(f"Filtered out {asin} (profile {pid}): format '{book_format}' is not Paperback/Hardcover")
            else:
                sync_results["synced"] += 1
        except Exception as e:
            sync_results["failed"] += 1
            sync_results["sync_errors"].append({"asin": asin, "marketplace": mkt, "profile_id": pid, "error": str(e)})
            logger.warning(f"Failed to sync book {asin} ({mkt}, profile {pid}): {e}")
    
    return {
        "success": True,
        "total_asins_found": len(all_asins),
        "unique_asin_profile_pairs": len(unique_asins),
        "new_asins_imported": imported,
        "already_existing": len(existing_pairs & set(unique_asins.keys())),
        "note": "Books are now managed per profile",
        "profiles_processed": processed_profiles,
        "oxylabs_synced": sync_results["synced"],
        "oxylabs_failed": sync_results["failed"],
        "filtered_out": sync_results["filtered"],
        "errors": errors if errors else None,
        "sync_errors": sync_results["sync_errors"] if sync_results["sync_errors"] else None
    }


@router.get("/profiles")
async def get_book_profiles():
    """Get all profiles with account info (including those without books)"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT 
                cp.profile_id,
                cp.country_code,
                cp.marketplace_string,
                ca.id as account_id,
                ca.client_name as account_name,
                (SELECT COUNT(*) FROM books b WHERE b.profile_id = cp.profile_id) as book_count
            FROM client_profiles cp
            JOIN client_accounts ca ON cp.client_account_id = ca.id
            ORDER BY ca.client_name, cp.country_code
        """)
        profiles = cur.fetchall()
        return {"profiles": profiles}
    finally:
        cur.close()
        conn.close()


class CombinedBookResponse(BookResponse):
    author: Optional[str] = None
    image_url: Optional[str] = None
    print_cost: Optional[float] = None


@router.get("/combined")
async def list_books_combined(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """Return all books from profile_books + book_economics_cache for the authenticated user only."""
    user = get_current_user_from_token(authorization or "", db)
    if not user:
        raise HTTPException(status_code=401, detail="Non autenticato")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT DISTINCT ON (pb.asin, pb.marketplace)
                pb.id,
                pb.asin,
                pb.profile_id,
                pb.marketplace,
                COALESCE(bec.title, pb.title)   AS title,
                NULL::text                       AS subtitle,
                NULL::text                       AS link,
                bec.format,
                bec.pages,
                NULL::float                      AS width_inches,
                NULL::float                      AS height_inches,
                bec.trim                         AS trim_size,
                bec.ink                          AS ink_type,
                bec.price,
                NULL::text                       AS currency,
                bec.print_cost                   AS c_print,
                NULL::float                      AS royalty_rate,
                bec.royalty_net                  AS r_net,
                bec.acos_be,
                bec.acos_opt,
                bec.fetched_at                   AS synced_at,
                bec.author,
                bec.image_url,
                bec.print_cost
            FROM profile_books pb
            JOIN book_economics_cache bec
                   ON pb.asin = bec.asin
                  AND pb.marketplace = bec.marketplace
            JOIN client_profiles cp ON pb.profile_id = cp.profile_id
            JOIN client_accounts ca ON cp.client_account_id = ca.id
            WHERE ca.user_id = %s
            ORDER BY pb.asin, pb.marketplace, bec.fetched_at DESC NULLS LAST
        """, (user.id,))
        rows = cur.fetchall()
        return [CombinedBookResponse(**dict(r)) for r in rows]
    finally:
        cur.close()
        conn.close()


@router.get("/", response_model=List[BookResponse])
async def list_books(profile_id: Optional[str] = None, account_id: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if profile_id:
            cur.execute("""
                SELECT * FROM books WHERE profile_id = %s ORDER BY asin
            """, (profile_id,))
        elif account_id:
            cur.execute("""
                SELECT b.* FROM books b
                JOIN client_profiles cp ON b.profile_id = cp.profile_id
                WHERE cp.client_account_id = %s
                ORDER BY b.asin
            """, (int(account_id),))
        else:
            cur.execute("""
                SELECT * FROM books ORDER BY asin
            """)
        books = cur.fetchall()
        return [BookResponse(**b) for b in books]
    finally:
        cur.close()
        conn.close()


def parse_dimensions(dimensions_str: str) -> Tuple[Optional[float], Optional[float]]:
    if not dimensions_str:
        return None, None
    
    is_cm = "cm" in dimensions_str.lower() or "centimeter" in dimensions_str.lower()
    is_mm = "mm" in dimensions_str.lower() or "millimeter" in dimensions_str.lower()
    
    numbers = re.findall(r'(\d+\.?\d*)', dimensions_str)
    if len(numbers) < 2:
        return None, None
    
    dims = [float(n) for n in numbers[:3]]
    
    if is_cm:
        dims = [d / 2.54 for d in dims]
    elif is_mm:
        dims = [d / 25.4 for d in dims]
    
    if len(dims) == 3:
        dims_sorted = sorted(dims, reverse=True)
        height = dims_sorted[0]
        width = dims_sorted[1]
    else:
        width = min(dims[0], dims[1])
        height = max(dims[0], dims[1])
    
    return round(width, 2), round(height, 2)


def fetch_oxylabs_product(asin: str, marketplace: str = "US") -> dict:
    geo_location = {
        "US": "90210",
        "UK": "SW1A 1AA",
        "GB": "SW1A 1AA",
        "DE": "10115",
        "FR": "75001",
        "IT": "00100",
        "ES": "28001",
        "CA": "M5V 2A8",
        "JP": "100-0001",
        "AU": "2000",
    }.get(marketplace.upper(), "90210")
    
    domain = {
        "US": "com",
        "UK": "co.uk",
        "GB": "co.uk",
        "DE": "de",
        "FR": "fr",
        "IT": "it",
        "ES": "es",
        "CA": "ca",
        "JP": "co.jp",
        "AU": "com.au",
    }.get(marketplace.upper(), "com")
    
    payload = {
        "source": "amazon_product",
        "query": asin,
        "domain": domain,
        "geo_location": geo_location,
        "parse": True,
    }
    
    response = requests.post(
        OXYLABS_URL,
        auth=(OXYLABS_USER, OXYLABS_PASS),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


@router.post("/sync/{asin}")
async def sync_single_book(asin: str, marketplace: str = "US", price: Optional[float] = None, ink_type: str = "black", royalty_rate: float = 0.6, profile_id: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if profile_id:
            cur.execute("SELECT * FROM books WHERE asin = %s AND profile_id = %s", (asin, profile_id))
        else:
            cur.execute("SELECT * FROM books WHERE asin = %s", (asin,))
        book = cur.fetchone()
        
        if not book:
            if profile_id:
                cur.execute("INSERT INTO books (asin, profile_id) VALUES (%s, %s) RETURNING *", (asin, profile_id))
            else:
                cur.execute("INSERT INTO books (asin) VALUES (%s) RETURNING *", (asin,))
            book = cur.fetchone()
            conn.commit()
        
        try:
            oxylabs_data = fetch_oxylabs_product(asin, marketplace)
        except Exception as e:
            logger.error(f"Oxylabs fetch failed for {asin}: {e}")
            raise HTTPException(status_code=502, detail=f"Failed to fetch from Oxylabs: {str(e)}")
        
        results = oxylabs_data.get("results", [])
        if not results:
            raise HTTPException(status_code=404, detail="No product data found")
        
        content = results[0].get("content", {})
        product_details = content.get("product_details", {})
        
        title = content.get("title", "") or content.get("product_name", "")
        subtitle = content.get("subtitle", "")
        link = content.get("url", "")
        
        product_format = ""
        variations = content.get("variation", [])
        for var in variations:
            if var.get("selected"):
                var_dims = var.get("dimensions", {})
                product_format = var_dims.get("Format", "")
                break
        if not product_format:
            product_format = content.get("format", content.get("binding", ""))
        
        pages = None
        page_info = product_details.get("print_length") or content.get("page_count") or content.get("print_length")
        if page_info:
            if isinstance(page_info, int):
                pages = page_info
            else:
                page_match = re.search(r'(\d+)', str(page_info))
                if page_match:
                    pages = int(page_match.group(1))
        
        dimensions = product_details.get("dimensions") or content.get("dimensions", content.get("product_dimensions", ""))
        width_inches, height_inches = parse_dimensions(dimensions)
        
        if price is None:
            price_info = content.get("price", content.get("price_upper"))
            if price_info:
                if isinstance(price_info, (int, float)):
                    price = float(price_info)
                else:
                    price_match = re.search(r'[\d,.]+', str(price_info))
                    if price_match:
                        price = float(price_match.group().replace(",", "."))
        
        currency = content.get("currency", "USD")
        trim_size = get_trim_category(width_inches, height_inches)
        
        c_print = None
        r_net = None
        acos_be = None
        acos_opt = None
        
        is_hardcover = any(hc in product_format.lower() for hc in ["hardcover", "hardback", "copertina rigida", "tapa dura", "relié", "gebundene"])
        
        if pages and price:
            if is_hardcover:
                cost_result = calculate_hardcover_printing_cost(
                    pages=pages,
                    marketplace=marketplace,
                    ink_type=ink_type,
                    width_inches=width_inches,
                    height_inches=height_inches,
                )
            else:
                cost_result = calculate_printing_cost(
                    pages=pages,
                    marketplace=marketplace,
                    ink_type=ink_type,
                    width_inches=width_inches,
                    height_inches=height_inches,
                )
            if cost_result:
                c_print, cost_currency = cost_result
                c_print = float(c_print)
                
                r_net, acos_be, acos_opt = calculate_acos_values(
                    price=price,
                    c_print=c_print,
                    royalty_rate=royalty_rate,
                    k=float(ACOS_RATIO),
                )
        
        if profile_id:
            cur.execute("""
                UPDATE books SET
                    marketplace = %s,
                    title = %s,
                    subtitle = %s,
                    link = %s,
                    format = %s,
                    pages = %s,
                    width_inches = %s,
                    height_inches = %s,
                    trim_size = %s,
                    ink_type = %s,
                    price = %s,
                    currency = %s,
                    c_print = %s,
                    royalty_rate = %s,
                    r_net = %s,
                    acos_be = %s,
                    acos_opt = %s,
                    synced_at = NOW(),
                    updated_at = NOW()
                WHERE asin = %s AND profile_id = %s
                RETURNING *
            """, (
                marketplace, title, subtitle, link, product_format, pages,
                width_inches, height_inches, trim_size, ink_type, price, currency,
                c_print, royalty_rate, r_net, acos_be, acos_opt, asin, profile_id
            ))
        else:
            cur.execute("""
                UPDATE books SET
                    marketplace = %s,
                    title = %s,
                    subtitle = %s,
                    link = %s,
                    format = %s,
                    pages = %s,
                    width_inches = %s,
                    height_inches = %s,
                    trim_size = %s,
                    ink_type = %s,
                    price = %s,
                    currency = %s,
                    c_print = %s,
                    royalty_rate = %s,
                    r_net = %s,
                    acos_be = %s,
                    acos_opt = %s,
                    synced_at = NOW(),
                    updated_at = NOW()
                WHERE asin = %s
                RETURNING *
            """, (
                marketplace, title, subtitle, link, product_format, pages,
                width_inches, height_inches, trim_size, ink_type, price, currency,
                c_print, royalty_rate, r_net, acos_be, acos_opt, asin
            ))
        
        updated_book = cur.fetchone()
        conn.commit()
        
        return {
            "success": True,
            "book": dict(updated_book) if updated_book else None,
        }
    finally:
        cur.close()
        conn.close()


@router.post("/sync-all")
async def sync_all_books(request: BulkSyncRequest):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("SELECT asin FROM books WHERE synced_at IS NULL")
        books = cur.fetchall()
        
        results = {"synced": 0, "failed": 0, "errors": []}
        
        for book in books:
            asin = book["asin"]
            try:
                await sync_single_book(asin, request.marketplace)
                results["synced"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"asin": asin, "error": str(e)})
                logger.error(f"Failed to sync {asin}: {e}")
        
        return results
    finally:
        cur.close()
        conn.close()


@router.put("/{asin}")
async def update_book(asin: str, price: Optional[float] = None, ink_type: Optional[str] = None, royalty_rate: Optional[float] = None, marketplace: Optional[str] = None, profile_id: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        if profile_id:
            cur.execute("SELECT * FROM books WHERE asin = %s AND profile_id = %s", (asin, profile_id))
        else:
            cur.execute("SELECT * FROM books WHERE asin = %s", (asin,))
        book = cur.fetchone()
        
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        
        new_price = price if price is not None else book.get("price")
        new_ink = ink_type if ink_type is not None else book.get("ink_type", "black")
        new_royalty = royalty_rate if royalty_rate is not None else book.get("royalty_rate", 0.6)
        new_marketplace = marketplace if marketplace is not None else book.get("marketplace", "US")
        pages = book.get("pages")
        width_inches = book.get("width_inches")
        height_inches = book.get("height_inches")
        product_format = book.get("format", "")
        
        c_print = None
        r_net = None
        acos_be = None
        acos_opt = None
        
        is_hardcover = any(hc in (product_format or "").lower() for hc in ["hardcover", "hardback", "copertina rigida", "tapa dura", "relié", "gebundene"])
        
        if pages and new_price:
            if is_hardcover:
                cost_result = calculate_hardcover_printing_cost(
                    pages=pages,
                    marketplace=new_marketplace,
                    ink_type=new_ink,
                    width_inches=width_inches,
                    height_inches=height_inches,
                )
            else:
                cost_result = calculate_printing_cost(
                    pages=pages,
                    marketplace=new_marketplace,
                    ink_type=new_ink,
                    width_inches=width_inches,
                    height_inches=height_inches,
                )
            if cost_result:
                c_print, _ = cost_result
                c_print = float(c_print)
                
                r_net, acos_be, acos_opt = calculate_acos_values(
                    price=new_price,
                    c_print=c_print,
                    royalty_rate=new_royalty,
                    k=float(ACOS_RATIO),
                )
        
        if profile_id:
            cur.execute("""
                UPDATE books SET
                    price = %s,
                    ink_type = %s,
                    royalty_rate = %s,
                    marketplace = %s,
                    c_print = %s,
                    r_net = %s,
                    acos_be = %s,
                    acos_opt = %s,
                    updated_at = NOW()
                WHERE asin = %s AND profile_id = %s
                RETURNING *
            """, (new_price, new_ink, new_royalty, new_marketplace, c_print, r_net, acos_be, acos_opt, asin, profile_id))
        else:
            cur.execute("""
                UPDATE books SET
                    price = %s,
                    ink_type = %s,
                    royalty_rate = %s,
                    marketplace = %s,
                    c_print = %s,
                    r_net = %s,
                    acos_be = %s,
                    acos_opt = %s,
                    updated_at = NOW()
                WHERE asin = %s
                RETURNING *
            """, (new_price, new_ink, new_royalty, new_marketplace, c_print, r_net, acos_be, acos_opt, asin))
        
        updated = cur.fetchone()
        conn.commit()
        
        return {"success": True, "book": dict(updated)}
    finally:
        cur.close()
        conn.close()


@router.post("/recalculate-economics")
async def recalculate_all_economics(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Ricalcola print_cost, royalty_net, acos_be, acos_opt per tutti i libri in cache usando il KDP calculator."""
    from backend.app.services.autopilot_sync_service import calculate_economics
    from db.accounts_db import get_connection as get_raw_conn
    from psycopg2.extras import RealDictCursor

    user = get_current_user_from_token(authorization or "", db)
    if not user:
        raise HTTPException(status_code=401, detail="Non autenticato")

    conn = get_raw_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT
                bec.asin, bec.marketplace, bec.price, bec.format,
                COALESCE(bec.pages, b.pages)              AS pages,
                COALESCE(b.width_inches)                  AS width,
                COALESCE(b.height_inches)                 AS height,
                COALESCE(b.ink_type, 'black')             AS ink_type
            FROM book_economics_cache bec
            LEFT JOIN books b ON bec.asin = b.asin
                AND (b.marketplace = bec.marketplace OR b.marketplace IS NULL)
            WHERE bec.price IS NOT NULL AND bec.price > 0
        """)
        rows = cur.fetchall()

        updated = 0
        errors = 0
        for row in rows:
            try:
                econ = calculate_economics({
                    'price': float(row['price']),
                    'pages': row['pages'] or 200,
                    'marketplace': row['marketplace'],
                    'format': row['format'] or 'paperback',
                    'width': row['width'],
                    'height': row['height'],
                    'ink_type': row['ink_type'] or 'black',
                })
                cur.execute("""
                    UPDATE book_economics_cache
                    SET print_cost = %s,
                        royalty_net = %s,
                        acos_be = %s,
                        acos_opt = %s
                    WHERE asin = %s AND marketplace = %s
                """, (
                    econ['print_cost'],
                    econ['royalty_net'],
                    econ['acos_be'],
                    econ['acos_opt'],
                    row['asin'],
                    row['marketplace'],
                ))
                updated += 1
            except Exception as e:
                logger.error(f"Recalc error for {row['asin']}/{row['marketplace']}: {e}")
                errors += 1

        conn.commit()
        return {"success": True, "updated": updated, "errors": errors, "total": len(rows)}
    finally:
        cur.close()
        conn.close()


@router.delete("/{asin}")
async def delete_book(asin: str, profile_id: Optional[str] = None):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if profile_id:
            cur.execute("DELETE FROM books WHERE asin = %s AND profile_id = %s", (asin, profile_id))
        else:
            cur.execute("DELETE FROM books WHERE asin = %s", (asin,))
        deleted = cur.rowcount
        conn.commit()
        
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Book not found")
        
        return {"success": True, "deleted": asin, "profile_id": profile_id}
    finally:
        cur.close()
        conn.close()
