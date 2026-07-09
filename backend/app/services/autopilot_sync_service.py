"""
Autopilot Sync Service - Complete data refresh flow

This service orchestrates:
1. Fetching ASINs from active campaigns for all US/UK/IT profiles
2. Calling Oxylabs to get book economics (price, royalty, ACOS BE/Opt)
3. Requesting Amazon Ads reports (30d)
4. Downloading and parsing reports
5. Aggregating metrics by ASIN
"""

import os
import threading
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import requests
import gzip
import json
from io import BytesIO

from db.accounts_db import get_connection, get_profiles_for_account
from psycopg2.extras import RealDictCursor

OXYLABS_USER = os.environ.get("OXYLABS_USER", "")
OXYLABS_PASS = os.environ.get("OXYLABS_PASS", "")
OXYLABS_URL = "https://realtime.oxylabs.io/v1/queries"

ALLOWED_COUNTRIES = ('US', 'CA', 'MX', 'BR', 'UK', 'GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'SE', 'PL', 'BE', 'AE', 'SA', 'EG', 'TR', 'IN', 'JP', 'AU', 'SG')


def create_sync_job(account_id: int) -> int:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        INSERT INTO autopilot_sync_jobs (account_id, status, phase, message, started_at)
        VALUES (%s, 'STARTING', 'INIT', 'Inizializzazione sync...', CURRENT_TIMESTAMP)
        RETURNING id
    """, (account_id,))
    
    job = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    
    return job['id']


def update_sync_job(job_id: int, **kwargs):
    conn = get_connection()
    cur = conn.cursor()
    
    updates = []
    values = []
    for key, value in kwargs.items():
        updates.append(f"{key} = %s")
        values.append(value)
    
    if updates:
        values.append(job_id)
        cur.execute(f"""
            UPDATE autopilot_sync_jobs 
            SET {', '.join(updates)}
            WHERE id = %s
        """, values)
        conn.commit()
    
    cur.close()
    conn.close()


def get_sync_job_status(job_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM autopilot_sync_jobs WHERE id = %s", (job_id,))
    job = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(job) if job else None


def get_latest_sync_job(account_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM autopilot_sync_jobs 
        WHERE account_id = %s 
        ORDER BY started_at DESC 
        LIMIT 1
    """, (account_id,))
    job = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return dict(job) if job else None


def get_profile_api_url(profile_id: str) -> str:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT api_url FROM client_profiles WHERE profile_id = %s", (profile_id,))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if result and result.get('api_url'):
        return result['api_url']
    return "https://advertising-api.amazon.com"


def fetch_asins_from_amazon_api(access_token: str, profile_id: str, api_url: str = None) -> List[str]:
    from backend.app.services.amazon_ads.config import CLIENT_ID
    
    base_url = api_url or "https://advertising-api.amazon.com"
    asins = set()
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Content-Type": "application/vnd.spproductad.v3+json",
        "Accept": "application/vnd.spproductad.v3+json",
    }
    
    try:
        url = f"{base_url}/sp/productAds/list"
        payload = {"maxResults": 1000}
        
        resp = requests.post(url, headers=headers, json=payload)
        print(f"=== PRODUCT ADS for profile {profile_id} ===")
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            product_ads = data.get("productAds", [])
            print(f"Found {len(product_ads)} product ads")
            
            for ad in product_ads:
                asin = ad.get("asin")
                if not asin:
                    print(f"  Ad missing ASIN: {ad}")
                    continue
                asins.add(asin)
                print(f"  Added ASIN: {asin}")
        else:
            print(f"Error: {resp.text[:500]}")
            
    except Exception as e:
        print(f"Error fetching product ads: {e}")
    
    print(f"Total ASINs found: {len(asins)}")
    return list(asins)


def get_asins_from_campaigns(account_id: int, profile_id: str) -> List[str]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    asins = set()
    
    cur.execute("""
        SELECT DISTINCT asin FROM launched_campaigns 
        WHERE account_id = %s AND profile_id = %s AND asin IS NOT NULL
    """, (account_id, profile_id))
    
    for row in cur.fetchall():
        if row['asin']:
            asins.add(row['asin'])
    
    cur.execute("""
        SELECT report_data FROM amazon_reports 
        WHERE account_id = %s AND profile_id = %s 
        AND status = 'COMPLETED' AND report_data IS NOT NULL
        ORDER BY created_at DESC LIMIT 5
    """, (account_id, profile_id))
    
    for row in cur.fetchall():
        report_data = row.get('report_data')
        if report_data:
            if isinstance(report_data, dict):
                rows = report_data.get('rows', report_data.get('data', []))
            elif isinstance(report_data, list):
                if len(report_data) > 0 and isinstance(report_data[0], list):
                    rows = report_data[0]
                else:
                    rows = report_data
            else:
                continue
            
            for r in rows:
                asin = r.get('advertisedAsin') or r.get('asin')
                if asin:
                    asins.add(asin)
    
    cur.close()
    conn.close()
    
    return list(asins)


def get_cached_economics(asin: str, marketplace: str) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT price, print_cost, royalty_net, format, pages, acos_be, acos_opt
        FROM book_economics_cache 
        WHERE asin = %s AND marketplace = %s
    """, (asin, marketplace))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if result and result.get('price'):
        return {
            'asin': asin,
            'marketplace': marketplace,
            'price': float(result['price']) if result['price'] else None,
            'pages': result.get('pages'),
            'format': result.get('format'),
        }
    return None


def fetch_oxylabs_economics(asin: str, marketplace: str) -> Optional[dict]:
    if not OXYLABS_USER or not OXYLABS_PASS:
        return get_cached_economics(asin, marketplace)
    
    domain_map = {'US': 'com', 'UK': 'co.uk', 'GB': 'co.uk', 'IT': 'it'}
    
    domain = domain_map.get(marketplace.upper(), 'com')
    
    payload = {
        "source": "amazon_product",
        "query": asin,
        "domain": domain,
        "parse": True,
    }
    
    if marketplace.upper() == 'US':
        payload["geo_location"] = "10001"
    
    try:
        response = requests.post(
            OXYLABS_URL,
            auth=(OXYLABS_USER, OXYLABS_PASS),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        
        results = data.get('results', [{}])
        if not results:
            return None
        
        content = results[0].get('content', {})
        
        price_str = content.get('price_upper_value') or content.get('price')
        price = None
        if price_str:
            try:
                price = float(str(price_str).replace('$', '').replace('£', '').replace('€', '').replace(',', '.').strip())
            except:
                pass
        
        pages = content.get('page_count')
        if isinstance(pages, str):
            try:
                pages = int(pages.split()[0])
            except:
                pages = None
        
        dimensions = content.get('dimensions')
        width, height = None, None
        if dimensions:
            parts = dimensions.replace('x', ' ').split()
            try:
                nums = [float(p) for p in parts if p.replace('.', '').isdigit()]
                if len(nums) >= 2:
                    width, height = min(nums[:2]), max(nums[:2])
            except:
                pass
        
        format_type = 'paperback'
        if 'hardcover' in str(content.get('title', '')).lower():
            format_type = 'hardcover'
        
        images = content.get('images', [])
        image_url = None
        if images:
            first_img = images[0]
            if isinstance(first_img, dict):
                image_url = first_img.get('link') or first_img.get('url')
            elif isinstance(first_img, str):
                image_url = first_img
        
        author = content.get('manufacturer') or content.get('brand')
        if not author:
            by_info = content.get('product_details', {})
            if isinstance(by_info, dict):
                author = by_info.get('Author') or by_info.get('Publisher')
        
        return {
            'asin': asin,
            'marketplace': marketplace,
            'title': content.get('title'),
            'author': author,
            'image_url': image_url,
            'price': price,
            'pages': pages,
            'format': format_type,
            'width': width,
            'height': height,
        }
    except Exception as e:
        print(f"Oxylabs error for {asin}: {e}")
        return None


def calculate_economics(data: dict) -> dict:
    from backend.app.services.kdp_calculator import (
        calculate_printing_cost,
        calculate_hardcover_printing_cost,
        calculate_acos_values,
        ACOS_RATIO,
    )

    price = data.get('price') or 0
    pages = data.get('pages') or 200
    marketplace = data.get('marketplace', 'US')
    format_type = str(data.get('format') or 'paperback').lower()
    width = data.get('width')
    height = data.get('height')
    ink_type = data.get('ink_type', 'black')

    is_hardcover = 'hardcover' in format_type

    c_print_float = None
    try:
        if is_hardcover:
            result = calculate_hardcover_printing_cost(
                pages=pages,
                marketplace=marketplace,
                ink_type=ink_type,
                width_inches=width,
                height_inches=height,
            )
        else:
            result = calculate_printing_cost(
                pages=pages,
                marketplace=marketplace,
                ink_type=ink_type,
                width_inches=width,
                height_inches=height,
            )
        if result is not None:
            c_print_float = float(result[0])
    except Exception:
        result = None

    if c_print_float is None:
        base_cost = 1.00 if marketplace.upper() in ('US', 'CA', 'AU') else 0.75
        per_page_cost = 0.012 if marketplace.upper() in ('US', 'CA', 'AU') else 0.012
        c_print_float = round(base_cost + (pages * per_page_cost), 2)

    royalty_rate = 0.60
    r_net, acos_be, acos_opt = calculate_acos_values(
        price=price,
        c_print=c_print_float,
        royalty_rate=royalty_rate,
        k=float(ACOS_RATIO),
    )

    return {
        'print_cost': round(c_print_float, 2),
        'royalty_net': round(r_net, 2),
        'acos_be': round(acos_be, 2),
        'acos_opt': round(acos_opt, 2),
    }


def save_book_economics(asin: str, marketplace: str, oxylabs_data: dict, economics: dict):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO book_economics_cache 
        (asin, marketplace, price, print_cost, royalty_net, format, pages, acos_be, acos_opt, title, author, image_url, fetched_at, source)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, 'oxylabs')
        ON CONFLICT (asin, marketplace) 
        DO UPDATE SET 
            price = EXCLUDED.price,
            print_cost = EXCLUDED.print_cost,
            royalty_net = EXCLUDED.royalty_net,
            format = EXCLUDED.format,
            pages = EXCLUDED.pages,
            acos_be = EXCLUDED.acos_be,
            acos_opt = EXCLUDED.acos_opt,
            title = COALESCE(EXCLUDED.title, book_economics_cache.title),
            author = COALESCE(EXCLUDED.author, book_economics_cache.author),
            image_url = COALESCE(EXCLUDED.image_url, book_economics_cache.image_url),
            fetched_at = CURRENT_TIMESTAMP
    """, (
        asin, marketplace,
        oxylabs_data.get('price'),
        economics.get('print_cost'),
        economics.get('royalty_net'),
        oxylabs_data.get('format'),
        oxylabs_data.get('pages'),
        economics.get('acos_be'),
        economics.get('acos_opt'),
        oxylabs_data.get('title'),
        oxylabs_data.get('author'),
        oxylabs_data.get('image_url'),
    ))
    
    conn.commit()
    cur.close()
    conn.close()


def ensure_profile_book(profile_id: str, asin: str, marketplace: str):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO profile_books (profile_id, asin, marketplace)
        VALUES (%s, %s, %s)
        ON CONFLICT (profile_id, asin) DO NOTHING
    """, (profile_id, asin, marketplace))
    
    conn.commit()
    cur.close()
    conn.close()


def get_access_token(account_id: int) -> Optional[str]:
    """Get a valid access token, refreshing if needed."""
    from backend.app.services.amazon import get_valid_access_token
    
    access_token, error = get_valid_access_token(account_id)
    if error:
        print(f"Token refresh failed for account {account_id}: {error}")
        return None
    
    return access_token


def save_report_to_db(account_id: int, profile_id: str, report_id: str, period_days: int, status: str = 'PENDING', ad_product: str = 'SP'):
    conn = get_connection()
    cur = conn.cursor()
    
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=period_days - 1)
    
    report_type = f'{ad_product}_TARGETING'
    
    cur.execute("""
        INSERT INTO amazon_reports (account_id, profile_id, report_id, report_type, ad_product, start_date, end_date, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (report_id) DO UPDATE SET status = EXCLUDED.status
    """, (account_id, profile_id, report_id, report_type, ad_product, start_date, end_date, status))
    
    conn.commit()
    cur.close()
    conn.close()


def update_report_status(report_id: str, status: str, report_data: dict = None):
    conn = get_connection()
    cur = conn.cursor()
    
    if report_data:
        import json
        cur.execute("""
            UPDATE amazon_reports 
            SET status = %s, report_data = %s, completed_at = CURRENT_TIMESTAMP
            WHERE report_id = %s
        """, (status, json.dumps(report_data), report_id))
    else:
        cur.execute("""
            UPDATE amazon_reports SET status = %s WHERE report_id = %s
        """, (status, report_id))
    
    conn.commit()
    cur.close()
    conn.close()


def get_recent_report(profile_id: str, period_days: int, max_age_hours: int = 24, ad_product: str = 'SP') -> Optional[dict]:
    """Check if a usable report was already requested in the last N hours.
    Excludes FAILED reports from cache to allow retry.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    report_type = f'{ad_product}_TARGETING'
    
    cur.execute("""
        SELECT report_id, status, created_at, completed_at, report_data
        FROM amazon_reports 
        WHERE profile_id = %s 
          AND report_type = %s
          AND end_date = (CURRENT_DATE - INTERVAL '1 day')::date
          AND (end_date - start_date) IN (%s - 1, %s)
          AND created_at > NOW() - INTERVAL '%s hours'
          AND status != 'FAILED'
        ORDER BY created_at DESC
        LIMIT 1
    """, (profile_id, report_type, period_days, period_days, max_age_hours))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return dict(result) if result else None


def request_amazon_report(access_token: str, profile_id: str, period_days: int, api_url: str = None, account_id: int = None, force_new: bool = False, ad_product: str = 'SP') -> dict:
    """Request or reuse an Amazon report.
    
    Returns:
        dict with 'report_id' and 'is_cached' (True if reusing existing PARSED report)
    """
    from backend.app.services.amazon_ads.report import create_sp_targeting_report
    from backend.app.services.amazon_reports import create_report, get_date_range
    
    if not force_new:
        recent = get_recent_report(profile_id, period_days, max_age_hours=12, ad_product=ad_product)
        if recent:
            print(f"Using cached {ad_product} report {recent['report_id']} for profile {profile_id} ({period_days}D) - status: {recent['status']}")
            return {'report_id': recent['report_id'], 'is_cached': recent['status'] == 'PARSED'}
    
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=period_days - 1)
    
    try:
        if ad_product == 'SB':
            report_type = f'SB_TARGETING_{period_days}D'
            report_id = create_report(
                access_token=access_token,
                profile_id=profile_id,
                api_url=api_url or "https://advertising-api.amazon.com",
                report_type=report_type,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                ad_product='SB'
            )
        else:
            report_id = create_sp_targeting_report(
                access_token=access_token,
                profile_id=profile_id,
                start_date=start_date,
                end_date=end_date,
                api_url=api_url,
            )
        if report_id and account_id:
            save_report_to_db(account_id, profile_id, report_id, period_days, 'PENDING', ad_product=ad_product)
        print(f"Created new {ad_product} report {report_id} for profile {profile_id} ({period_days}D)")
        return {'report_id': report_id, 'is_cached': False}
    except Exception as e:
        print(f"Error requesting {ad_product} report: {e}")
        return None


REPORTS_DIR = "reports_data"
os.makedirs(REPORTS_DIR, exist_ok=True)


def poll_and_download_report(access_token: str, profile_id: str, report_id: str, api_url: str = None, 
                             ad_product: str = 'SP', period_days: int = 14, marketplace: str = 'US') -> Optional[List[dict]]:
    """Check report status ONCE (non-blocking). Returns data if ready, None otherwise.
    Also saves the report to disk with descriptive filename: {AD_PRODUCT}_{PERIOD}D_{COUNTRY}_{report_id}.json
    """
    from backend.app.services.amazon_ads.report import check_report_status_once, download_report_gzip_json
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT status, report_data FROM amazon_reports WHERE report_id = %s", (report_id,))
    existing = cur.fetchone()
    cur.close()
    conn.close()
    
    if existing and existing['status'] in ('PARSED', 'COMPLETED') and existing.get('report_data'):
        data = existing['report_data']
        if isinstance(data, str):
            data = json.loads(data)
        print(f"Report {report_id} already {existing['status']}, using cached data ({len(data)} rows)")
        return data
    
    try:
        meta = check_report_status_once(access_token, profile_id, report_id, api_url)
        amazon_status = meta.get('status')
        
        if amazon_status == 'SUCCESS':
            location = meta.get('url')
            if location:
                rows = download_report_gzip_json(location)
                update_report_status(report_id, 'COMPLETED', rows)
                
                filename = f"{ad_product}_{period_days}D_{marketplace}_{report_id}.json"
                file_path = os.path.join(REPORTS_DIR, filename)
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(rows, f, indent=2)
                print(f"Report {report_id} downloaded: {len(rows)} rows -> {filename}")
                return rows
            else:
                print(f"Report {report_id} SUCCESS but no URL")
                return None
        elif amazon_status in ('FAILURE', 'CANCELLED'):
            update_report_status(report_id, 'FAILED')
            print(f"Report {report_id} failed: {amazon_status}")
            return None
        else:
            print(f"Report {report_id} still processing: {amazon_status}")
            return None
    except Exception as e:
        print(f"Error polling report {report_id}: {e}")
        return None


def aggregate_report_by_asin(report_rows: List[dict]) -> Dict[str, dict]:
    asin_metrics = {}
    
    for row in report_rows:
        asin = row.get('advertisedAsin') or row.get('asin')
        if not asin:
            continue
        
        if asin not in asin_metrics:
            asin_metrics[asin] = {
                'spend': 0,
                'sales': 0,
                'orders': 0,
                'clicks': 0,
                'impressions': 0,
            }
        
        asin_metrics[asin]['spend'] += float(row.get('cost', 0) or 0)
        asin_metrics[asin]['sales'] += float(row.get('sales14d', 0) or row.get('attributedSales14d', 0) or 0)
        asin_metrics[asin]['orders'] += int(row.get('purchases14d', 0) or row.get('attributedConversions14d', 0) or 0)
        asin_metrics[asin]['clicks'] += int(row.get('clicks', 0) or 0)
        asin_metrics[asin]['impressions'] += int(row.get('impressions', 0) or 0)
    
    for asin, m in asin_metrics.items():
        if m['sales'] > 0:
            m['acos'] = round((m['spend'] / m['sales']) * 100, 2)
        else:
            m['acos'] = None
    
    return asin_metrics


def save_asin_metrics(profile_id: str, asin: str, period_days: int, metrics: dict):
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        DELETE FROM ads_agg_book_metrics 
        WHERE profile_id = %s AND asin = %s AND period_days = %s AND run_id IS NULL
    """, (profile_id, asin, period_days))
    
    cur.execute("""
        INSERT INTO ads_agg_book_metrics 
        (profile_id, asin, period_days, spend, sales, orders, clicks, impressions, acos, calculated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """, (
        profile_id, asin, period_days,
        metrics.get('spend', 0),
        metrics.get('sales', 0),
        metrics.get('orders', 0),
        metrics.get('clicks', 0),
        metrics.get('impressions', 0),
        metrics.get('acos'),
    ))
    
    conn.commit()
    cur.close()
    conn.close()


def analyze_and_plan_actions(account_id: int, profile_id: str, ad_product: str = 'SP', target_scope: str = None) -> List[dict]:
    """Analyze reports and create planned bid actions for a profile.
    
    Args:
        account_id: The account ID
        profile_id: The profile ID
        ad_product: 'SP' for Sponsored Products, 'SB' for Sponsored Brands
        target_scope: Optional filter for action types:
            - 'AUTO': Only SP auto-targeting (close-match, loose-match, substitutes, complements)
            - 'SP_MANUAL': SP keywords + product/category targets (excludes auto)
            - 'SB': All SB actions (keywords + targets)
            - None: All actions (default)
    """
    from backend.app.services.bid_analyzer import analyze
    from backend.app.services.amazon import get_campaign_names_map, get_amazon_keywords_and_targets, get_api_url_for_country, get_campaign_to_asin_map, get_sb_campaign_names_map
    import json
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT country_code FROM client_profiles WHERE profile_id = %s LIMIT 1
    """, (profile_id,))
    profile_row = cur.fetchone()
    country_code = profile_row.get('country_code') if profile_row else 'US'
    if not country_code:
        country_code = 'US'
    api_url = get_api_url_for_country(country_code)
    
    report_type = f'{ad_product}_TARGETING'
    
    cur.execute("""
        SELECT report_id, report_data, created_at FROM amazon_reports 
        WHERE profile_id = %s AND status IN ('COMPLETED', 'PARSED') AND report_data IS NOT NULL
        AND report_type = %s
        AND (end_date - start_date) IN (29, 30)
        ORDER BY created_at DESC LIMIT 1
    """, (profile_id, report_type))
    report_30 = cur.fetchone()
    
    if report_30 and report_30.get('created_at'):
        from datetime import datetime, timezone, timedelta
        report_age = datetime.now(timezone.utc) - report_30['created_at'].replace(tzinfo=timezone.utc) if report_30['created_at'].tzinfo is None else datetime.now(timezone.utc) - report_30['created_at']
        if report_age > timedelta(hours=24):
            stale_report_id = report_30['report_id']
            print(f"[REPORT FRESHNESS] Report {stale_report_id} for profile {profile_id} ({ad_product}) is {report_age.total_seconds()/3600:.1f}h old (>24h). Deleting stale report.")
            cur.execute("DELETE FROM amazon_reports WHERE report_id = %s", (stale_report_id,))
            conn.commit()
            report_30 = None
    
    cur.execute("""
        SELECT pb.asin, bec.acos_be 
        FROM profile_books pb 
        JOIN book_economics_cache bec ON pb.asin = bec.asin AND pb.marketplace = bec.marketplace
        WHERE pb.profile_id = %s AND bec.acos_be IS NOT NULL
    """, (profile_id,))
    books = cur.fetchall()
    
    cur.execute("""
        SELECT campaign_id, campaign_name, asin, default_bid 
        FROM launched_campaigns 
        WHERE profile_id = %s
    """, (profile_id,))
    launched_campaigns = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not report_30:
        print(f"No 30D report found for profile {profile_id}")
        return []
    
    print(f"Fetching campaign names from Amazon API for profile {profile_id}...")
    campaign_names_map, err = get_campaign_names_map(account_id, profile_id, api_url)
    if err:
        print(f"Warning: Failed to get campaign names: {err}")
        campaign_names_map = {}
    
    if ad_product == 'SB':
        print(f"Fetching SB campaign names from Amazon API for profile {profile_id}...")
        sb_names_map, sb_err = get_sb_campaign_names_map(account_id, profile_id, api_url)
        if sb_err:
            print(f"Warning: Failed to get SB campaign names: {sb_err}")
        else:
            campaign_names_map.update(sb_names_map)
            print(f"Merged {len(sb_names_map)} SB campaign names into campaign_names_map (total: {len(campaign_names_map)})")
    
    print(f"Fetching campaign -> ASIN mapping from Amazon API for profile {profile_id}...")
    campaign_to_asin_map, err = get_campaign_to_asin_map(account_id, profile_id, api_url)
    if err:
        print(f"Warning: Failed to get campaign->ASIN map: {err}")
        campaign_to_asin_map = {}
    
    if ad_product == 'SP':
        inventory = get_sp_inventory_for_profile(profile_id)
    elif ad_product == 'SB':
        inventory = get_sb_inventory_for_profile(profile_id)
    else:
        inventory = []
    
    if inventory and len(inventory) > 0:
        print(f"[INVENTORY-DRIVEN] Using {ad_product.lower()}_inventory for profile {profile_id}: {len(inventory)} entities")
        keywords_map = {}
        targets_map = {}
        targeting_to_id_map = {}
        campaign_states_map = {}
        
        for row in inventory:
            entity_id = row.get('entity_id')
            entity_type = row.get('entity_type')
            expression = row.get('expression', '')
            expression_type = row.get('expression_type', '')
            bid = float(row.get('current_bid')) if row.get('current_bid') else None
            campaign_id = str(row.get('campaign_id', ''))
            ad_group_id = str(row.get('ad_group_id', ''))
            state = row.get('state', 'ENABLED')
            
            if state != 'ENABLED':
                continue
            
            if entity_type == 'keyword':
                keywords_map[entity_id] = {
                    "bid": bid,
                    "keyword": expression,
                    "keywordText": expression,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id
                }
                # IMPORTANTE: Aggiungere keyword anche a targets_map per consistenza con il fallback API flow
                # Questo permette al bid_analyzer di usare i metadata corretti da targets_map
                targets_map[entity_id] = {
                    "bid": bid,
                    "expression": expression,
                    "keywordText": expression,
                    "report_targeting": expression,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "targetType": "keyword"
                }
                if expression:
                    # Chiave semplice (per fallback)
                    targeting_to_id_map[expression.lower()] = entity_id
                    # Chiave composita (per risoluzione precisa per campagna)
                    composite_key = f"{campaign_id}_{ad_group_id}_kw={expression.lower()}"
                    targeting_to_id_map[composite_key] = entity_id
                campaign_states_map[campaign_id] = row.get('campaign_state', 'ENABLED') or "ENABLED"
            else:
                target_type_map = {
                    'asin': 'product_target',
                    'category': 'category_target',
                    'auto': 'auto_target',
                    'ASIN_SAME_AS': 'product_target',
                    'ASIN_CATEGORY_SAME_AS': 'category_target',
                    'QUERY_BROAD_REL_MATCHES': 'auto_target',
                    'QUERY_HIGH_REL_MATCHES': 'auto_target',
                    'ASIN_SUBSTITUTE_RELATED': 'auto_target',
                    'ASIN_ACCESSORY_RELATED': 'auto_target',
                }
                resolved_target_type = target_type_map.get(expression_type, 'product_target')
                
                normalized_expr_type = 'auto' if expression_type in (
                    'QUERY_BROAD_REL_MATCHES', 'QUERY_HIGH_REL_MATCHES',
                    'ASIN_SUBSTITUTE_RELATED', 'ASIN_ACCESSORY_RELATED', 'auto'
                ) else 'asin' if expression_type in ('ASIN_SAME_AS', 'asin') else 'category' if expression_type in ('ASIN_CATEGORY_SAME_AS', 'category') else expression_type
                
                auto_token_map = {
                    "query_high_rel_matches": "close-match",
                    "query_broad_rel_matches": "loose-match",
                    "asin_substitute_related": "substitutes",
                    "asin_accessory_related": "complements",
                    "close_match": "close-match",
                    "loose_match": "loose-match",
                    "close-match": "close-match",
                    "loose-match": "loose-match",
                    "substitutes": "substitutes",
                    "complements": "complements",
                }
                
                report_targeting = expression
                if normalized_expr_type == 'auto' and expression:
                    expr_lower = expression.lower().strip()
                    report_targeting = auto_token_map.get(expr_lower, expr_lower.replace("_", "-"))
                elif normalized_expr_type == 'asin' and expression:
                    report_targeting = f'asin="{expression.upper()}"'
                elif normalized_expr_type == 'category' and expression:
                    report_targeting = f'category="{expression}"'
                
                targets_map[entity_id] = {
                    "bid": bid,
                    "expression": expression,
                    "report_targeting": report_targeting,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "targetType": resolved_target_type
                }
                if expression:
                    expr_lower = expression.lower().strip()
                    
                    if normalized_expr_type == 'auto':
                        token = auto_token_map.get(expr_lower, expr_lower.replace("_", "-"))
                        key = f"{campaign_id}_{ad_group_id}_{token}"
                        targeting_to_id_map[key] = entity_id
                        targeting_to_id_map[token] = entity_id
                    elif normalized_expr_type == 'asin':
                        asin_upper = expression.upper()
                        key = f"{campaign_id}_{ad_group_id}_asin={asin_upper}"
                        targeting_to_id_map[key] = entity_id
                        targeting_to_id_map[asin_upper] = entity_id
                        targeting_to_id_map[asin_upper.lower()] = entity_id
                        targeting_to_id_map[f'asin="{asin_upper}"'] = entity_id
                        targeting_to_id_map[f"asin='{asin_upper}'"] = entity_id
                        targeting_to_id_map[f'asin="{asin_upper}"'.lower()] = entity_id
                    elif normalized_expr_type == 'category':
                        cat_normalized = ' '.join(expression.split()).lower()
                        key = f"{campaign_id}_{ad_group_id}_category={cat_normalized}"
                        targeting_to_id_map[key] = entity_id
                        targeting_to_id_map[f'category="{expression}"'] = entity_id
                        targeting_to_id_map[f'category="{expression}"'.lower()] = entity_id
                        targeting_to_id_map[cat_normalized] = entity_id
                    else:
                        key = f"{campaign_id}_{ad_group_id}_{expr_lower}"
                        targeting_to_id_map[key] = entity_id
                        targeting_to_id_map[expr_lower] = entity_id
            
            campaign_states_map[campaign_id] = row.get('campaign_state', 'ENABLED') or "ENABLED"
        
        print(f"[INVENTORY-DRIVEN] Built from inventory: {len(keywords_map)} keywords, {len(targets_map)} targets")
        print(f"[INVENTORY-DRIVEN] targeting_to_id_map has {len(targeting_to_id_map)} keys")
        sample_keys = list(targeting_to_id_map.keys())[:10]
        print(f"[INVENTORY-DRIVEN] Sample keys: {sample_keys}")
    else:
        print(f"[FALLBACK] Using live API for profile {profile_id} (no inventory)")
        print(f"Fetching keyword/target bids from Amazon API for profile {profile_id}...")
        keywords_map, targets_map, err = get_amazon_keywords_and_targets(account_id, profile_id, api_url)
        if err:
            print(f"Warning: Failed to get keyword/target bids: {err}")
            keywords_map = {}
            targets_map = {}
        
        targeting_to_id_map = keywords_map.pop("_targeting_to_id", {})
        campaign_states_map = keywords_map.pop("_campaign_states", {})
    
    live_bids = {}
    for kw_id, kw_data in keywords_map.items():
        live_bids[kw_id] = {
            "bid": kw_data.get("bid"), 
            "targetType": "keyword",
            "campaignId": kw_data.get("campaignId"),
            "adGroupId": kw_data.get("adGroupId"),
            "keywordText": kw_data.get("keyword"),
            "ad_product": ad_product
        }
        if kw_data.get("keyword"):
            live_bids[kw_data["keyword"].lower()] = {
                "bid": kw_data.get("bid"), 
                "targetType": "keyword",
                "campaignId": kw_data.get("campaignId"),
                "adGroupId": kw_data.get("adGroupId"),
                "keywordText": kw_data.get("keyword"),
                "ad_product": ad_product
            }
    for tgt_id, tgt_data in targets_map.items():
        target_type = tgt_data.get("targetType", "product_target")
        bid_info = {"bid": tgt_data.get("bid"), "targetType": target_type, "campaignId": tgt_data.get("campaignId"), "adGroupId": tgt_data.get("adGroupId"), "ad_product": ad_product}
        live_bids[tgt_id] = bid_info
        if tgt_data.get("report_targeting"):
            live_bids[tgt_data["report_targeting"]] = bid_info
            live_bids[tgt_data["report_targeting"].lower()] = bid_info
    
    discovery_data = {}
    for cid, cname in campaign_names_map.items():
        asin_from_api = campaign_to_asin_map.get(cid)
        discovery_data[cid] = {"campaign_name": cname, "asin": asin_from_api, "default_bid": None}
    
    for lc in launched_campaigns:
        cid = str(lc.get('campaign_id'))
        if cid in discovery_data:
            if not discovery_data[cid]['asin']:
                discovery_data[cid]['asin'] = lc.get('asin')
            discovery_data[cid]['default_bid'] = float(lc.get('default_bid')) if lc.get('default_bid') else None
        else:
            asin_from_api = campaign_to_asin_map.get(cid) or lc.get('asin')
            discovery_data[cid] = {
                'campaign_name': lc.get('campaign_name'),
                'asin': asin_from_api,
                'default_bid': float(lc.get('default_bid')) if lc.get('default_bid') else None
            }
    
    campaigns_with_asin = sum(1 for d in discovery_data.values() if d.get('asin'))
    print(f"[DISCOVERY_DATA] {len(discovery_data)} campaigns, {campaigns_with_asin} with ASIN mapped")
    
    report_30_data = []
    
    def _extract_report_rows(data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return []
        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], list):
                print(f"[REPORT_FLATTEN] Flattened nested report data: outer={len(data)}, inner={len(data[0])}")
                return data[0]
            return data
        if isinstance(data, dict):
            return data.get("rows", data.get("data", []))
        return []
    
    if report_30 and report_30.get('report_data'):
        report_30_data = _extract_report_rows(report_30['report_data'])
    
    asin_to_acos_be = {}
    for book in books:
        if book.get('asin') and book.get('acos_be'):
            asin_to_acos_be[book['asin']] = float(book['acos_be']) / 100
    
    print(f"Profile {profile_id} ({ad_product}): {len(report_30_data)} rows 30D, {len(asin_to_acos_be)} books with ACOS BE, {len(campaign_names_map)} campaigns, {len(live_bids)} live bids")
    
    # Load delta_config from autopilot_settings_profiles (if profile has assigned settings)
    # Falls back to autopilot_settings (account-level) if no profile settings assigned
    delta_config = None
    try:
        conn2 = get_connection()
        cur2 = conn2.cursor(cursor_factory=RealDictCursor)
        
        # First try to load from profile-specific settings
        cur2.execute("""
            SELECT sp.* FROM autopilot_settings_profiles sp
            JOIN autopilot_profiles ap ON ap.settings_profile_id = sp.id
            WHERE ap.profile_id = %s
        """, (profile_id,))
        settings_row = cur2.fetchone()
        
        if settings_row:
            delta_config = {
                "delta_excellent": float(settings_row["delta_excellent"]),
                "delta_good": float(settings_row["delta_good"]),
                "delta_above_be": float(settings_row["delta_above_be"]),
                "delta_high": float(settings_row["delta_high"]),
                "delta_low_impressions": float(settings_row["delta_low_impressions"]),
                "delta_no_sales": float(settings_row["delta_no_sales"]),
                "low_impressions_threshold": int(settings_row["low_impressions_threshold"]),
                "min_spend_for_decrement": float(settings_row["min_spend_for_decrement"]),
                "max_clicks_no_sales": int(settings_row.get("max_clicks_no_sales") or 10),
                "pause_on_clicks_enabled": bool(settings_row.get("pause_on_clicks_enabled", True) if settings_row.get("pause_on_clicks_enabled") is not None else True),
                "max_clicks_for_low_impressions": int(settings_row.get("max_clicks_for_low_impressions") or 3)
            }
            print(f"[SETTINGS] Loaded delta_config from profile '{settings_row['name']}' for {profile_id} (pause_on_clicks_enabled={delta_config['pause_on_clicks_enabled']})")
        else:
            # Fallback to account-level settings
            cur2.execute("SELECT * FROM autopilot_settings WHERE account_id = %s", (account_id,))
            settings_row = cur2.fetchone()
            if settings_row:
                delta_config = {
                    "delta_excellent": float(settings_row["delta_excellent"]),
                    "delta_good": float(settings_row["delta_good"]),
                    "delta_above_be": float(settings_row["delta_above_be"]),
                    "delta_high": float(settings_row["delta_high"]),
                    "delta_low_impressions": float(settings_row["delta_low_impressions"]),
                    "delta_no_sales": float(settings_row["delta_no_sales"]),
                    "low_impressions_threshold": int(settings_row["low_impressions_threshold"]),
                    "min_spend_for_decrement": float(settings_row["min_spend_for_decrement"]),
                    "max_clicks_no_sales": int(settings_row.get("max_clicks_no_sales") or 10),
                    "pause_on_clicks_enabled": bool(settings_row.get("pause_on_clicks_enabled", True) if settings_row.get("pause_on_clicks_enabled") is not None else True),
                    "max_clicks_for_low_impressions": int(settings_row.get("max_clicks_for_low_impressions") or 3)
                }
                print(f"[SETTINGS] Loaded delta_config from account {account_id} (fallback)")
        
        cur2.close()
        conn2.close()
    except Exception as e:
        print(f"Warning: Could not load autopilot_settings: {e}")
    
    actions = analyze(
        profile_id=profile_id,
        report_30_data=report_30_data,
        asin_to_acos_be_map=asin_to_acos_be,
        discovery_data=discovery_data,
        live_bids=live_bids,
        targeting_to_id_map=targeting_to_id_map,
        ad_product=ad_product,
        targets_map=targets_map,
        delta_config=delta_config,
        campaign_states_map=campaign_states_map
    )
    
    AUTO_TOKENS = {"close-match", "loose-match", "substitutes", "complements"}
    
    if target_scope:
        filtered_actions = []
        for action in actions:
            target_type = action.get('target_type', '')
            keyword = (action.get('keyword') or '').lower().strip()
            
            if target_scope == 'AUTO':
                if target_type == 'auto_target' or keyword in AUTO_TOKENS:
                    filtered_actions.append(action)
            elif target_scope == 'SP_MANUAL':
                if target_type in ('keyword', 'product_target', 'category_target'):
                    if keyword not in AUTO_TOKENS:
                        filtered_actions.append(action)
            elif target_scope == 'SB':
                # Per SB, includiamo solo se l'azione viene dai dati SB
                # Il target_type deve essere uno dei tipi SB validi
                if target_type in ('keyword', 'product_target', 'category_target'):
                    filtered_actions.append(action)
        
        actions = filtered_actions
        print(f"Profile {profile_id} ({ad_product}): filtered to {len(actions)} actions with scope={target_scope}")
    
    if actions:
        save_planned_actions(account_id, profile_id, actions, ad_product=ad_product, target_scope=target_scope)
    
    print(f"Profile {profile_id} ({ad_product}): {len(actions)} bid actions planned")
    return actions


def save_planned_actions(account_id: int, profile_id: str, actions: List[dict], ad_product: str = 'SP', target_scope: str = None):
    """Save planned actions to database.
    
    Args:
        target_scope: If provided, only deletes actions matching this scope before inserting.
            - 'AUTO': Deletes only auto_target actions
            - 'SP_MANUAL': Deletes only non-auto SP actions (keywords, product/category targets)
            - 'SB': Deletes all SB actions
            - None: Deletes all actions for this ad_product (default behavior)
    """
    conn = get_connection()
    cur = conn.cursor()
    
    AUTO_TOKENS_DB = ('close-match', 'loose-match', 'substitutes', 'complements')
    
    try:
        if target_scope == 'AUTO':
            cur.execute("""
                DELETE FROM planned_actions 
                WHERE profile_id = %s AND status = 'PLANNED' AND ad_product = %s 
                AND (target_type = 'auto_target' OR LOWER(keyword) IN %s)
            """, (profile_id, ad_product, AUTO_TOKENS_DB))
            print(f"[SAVE_ACTIONS] Deleted old PLANNED {ad_product} AUTO actions for profile {profile_id}")
        elif target_scope == 'SP_MANUAL':
            cur.execute("""
                DELETE FROM planned_actions 
                WHERE profile_id = %s AND status = 'PLANNED' AND ad_product = %s 
                AND (target_type IN ('keyword', 'product_target', 'category_target', 'target') OR target_type IS NULL)
                AND (keyword IS NULL OR LOWER(keyword) NOT IN %s)
            """, (profile_id, ad_product, AUTO_TOKENS_DB))
            print(f"[SAVE_ACTIONS] Deleted old PLANNED {ad_product} MANUAL actions for profile {profile_id}")
        else:
            cur.execute("DELETE FROM planned_actions WHERE profile_id = %s AND status = 'PLANNED' AND ad_product = %s", (profile_id, ad_product))
            print(f"[SAVE_ACTIONS] Deleted old PLANNED {ad_product} actions for profile {profile_id}")
    except Exception as e:
        print(f"[SAVE_ACTIONS] Error deleting: {e}")
        conn.rollback()
        raise
    
    inserted = 0
    for action in actions:
        current_bid = action.get('current_bid')
        delta_bid = action.get('delta_bid', 0)
        new_bid = None
        if current_bid is not None:
            new_bid = max(0.02, current_bid + delta_bid)
        
        try:
            cur.execute("""
                INSERT INTO planned_actions 
                (profile_id, account_id, ad_product, keyword_id, entity_id, campaign_id, campaign_name, ad_group_id, 
                 keyword, asin, target_type, current_bid, delta_bid, new_bid, 
                 acos_14d, acos_30d, acos_be, impressions_14d, impressions_30d, purchases_14d, purchases_30d,
                 clicks, spend, sales, orders, reason, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PLANNED')
            """, (
                profile_id,
                account_id,
                ad_product,
                action.get('keyword_id'),
                action.get('entity_id') or action.get('keyword_id'),
                action.get('campaign_id'),
                action.get('campaign_name'),
                action.get('ad_group_id'),
                action.get('keyword'),
                action.get('asin'),
                action.get('target_type', 'keyword'),
                current_bid,
                delta_bid,
                new_bid,
                None,
                action.get('acos_30d'),
                action.get('acos_be'),
                None,
                action.get('impressions_30d'),
                None,
                action.get('purchases_30d'),
                action.get('clicks_30d'),
                action.get('spend_30d'),
                action.get('sales_30d'),
                action.get('purchases_30d'),
                action.get('reason') or action.get('tipo_azione')
            ))
            inserted += 1
        except Exception as e:
            print(f"[SAVE_ACTIONS] Error inserting action: {e}")
            continue
    
    try:
        conn.commit()
        print(f"[SAVE_ACTIONS] Committed {inserted} actions for profile {profile_id}")
    except Exception as e:
        print(f"[SAVE_ACTIONS] Error committing: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def save_sp_inventory(account_id: int, profile_id: str, keywords: List[dict], targets: List[dict], campaign_states: dict = None):
    """Save SP keywords and targets inventory to database.
    
    This creates the lookup table for inventory-driven bid updates.
    The inventory serves as the source of truth for which entities exist.
    
    Args:
        campaign_states: Dict mapping campaign_id -> state (ENABLED/PAUSED/ARCHIVED)
    """
    campaign_states = campaign_states or {}
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM sp_inventory WHERE profile_id = %s", (profile_id,))
        print(f"[SP_INVENTORY] Cleared old inventory for profile {profile_id}")
    except Exception as e:
        print(f"[SP_INVENTORY] Error clearing: {e}")
        conn.rollback()
    
    inserted = 0
    
    for kw in keywords:
        try:
            keyword_id = kw.get('keywordId')
            campaign_id = str(kw.get('campaignId', ''))
            ad_group_id = kw.get('adGroupId')
            keyword_text = kw.get('keywordText', '')
            match_type = kw.get('matchType', '')
            bid = kw.get('bid')
            state = kw.get('state', 'ENABLED')
            campaign_state = campaign_states.get(campaign_id, 'UNKNOWN')
            
            if not keyword_id or not campaign_id:
                continue
            
            cur.execute("""
                INSERT INTO sp_inventory 
                (account_id, profile_id, entity_type, entity_id, campaign_id, ad_group_id, 
                 expression, expression_type, match_type, current_bid, state, campaign_state)
                VALUES (%s, %s, 'keyword', %s, %s, %s, %s, 'keyword', %s, %s, %s, %s)
                ON CONFLICT (profile_id, entity_type, entity_id) 
                DO UPDATE SET 
                    campaign_id = EXCLUDED.campaign_id,
                    ad_group_id = EXCLUDED.ad_group_id,
                    expression = EXCLUDED.expression,
                    match_type = EXCLUDED.match_type,
                    current_bid = EXCLUDED.current_bid,
                    state = EXCLUDED.state,
                    campaign_state = EXCLUDED.campaign_state,
                    updated_at = CURRENT_TIMESTAMP
            """, (account_id, profile_id, keyword_id, campaign_id, ad_group_id, 
                  keyword_text, match_type, bid, state, campaign_state))
            inserted += 1
        except Exception as e:
            print(f"[SP_INVENTORY] Error inserting keyword: {e}")
            continue
    
    for t in targets:
        try:
            target_id = t.get('targetId')
            campaign_id = str(t.get('campaignId', ''))
            ad_group_id = t.get('adGroupId')
            bid = t.get('bid')
            state = t.get('state', 'ENABLED')
            campaign_state = campaign_states.get(campaign_id, 'UNKNOWN')
            
            if not target_id or not campaign_id:
                continue
            
            expression = None
            expression_type = None
            
            resolved_exp = t.get('resolvedExpression') or []
            if resolved_exp and len(resolved_exp) > 0:
                first_exp = resolved_exp[0]
                exp_type = first_exp.get('type', '')
                exp_value = first_exp.get('value', '')
                
                exp_normalized = exp_type.upper().replace(' ', '_').replace('-', '_') if exp_type else ''
                
                asin_types = {'ASIN_SAME_AS', 'ASINSAMEAS'}
                category_types = {'ASIN_CATEGORY_SAME_AS', 'ASINCATEGORYSAMEAS'}
                auto_types = {
                    'QUERY_BROAD_REL_MATCHES', 'QUERY_HIGH_REL_MATCHES',
                    'ASIN_SUBSTITUTE_RELATED', 'ASIN_ACCESSORY_RELATED',
                    'QUERYBROADRELMATCHES', 'QUERYHIGHRELMATCHES',
                    'ASINSUBSTITUTERELATED', 'ASINACCESSORYRELATED'
                }
                
                if exp_normalized in asin_types or exp_type == 'asinSameAs':
                    expression = exp_value
                    expression_type = 'asin'
                elif exp_normalized in category_types or exp_type == 'asinCategorySameAs':
                    expression = exp_value
                    expression_type = 'category'
                elif exp_normalized in auto_types or exp_type in ('queryBroadRelMatches', 'queryHighRelMatches', 
                                  'asinSubstituteRelated', 'asinAccessoryRelated'):
                    auto_map = {
                        'QUERY_BROAD_REL_MATCHES': 'loose-match',
                        'QUERY_HIGH_REL_MATCHES': 'close-match',
                        'ASIN_SUBSTITUTE_RELATED': 'substitutes',
                        'ASIN_ACCESSORY_RELATED': 'complements',
                        'queryBroadRelMatches': 'loose-match',
                        'queryHighRelMatches': 'close-match',
                        'asinSubstituteRelated': 'substitutes',
                        'asinAccessoryRelated': 'complements',
                    }
                    expression = auto_map.get(exp_normalized, auto_map.get(exp_type, exp_type))
                    expression_type = 'auto'
                else:
                    expression = exp_value or exp_type
                    expression_type = exp_type
            
            cur.execute("""
                INSERT INTO sp_inventory 
                (account_id, profile_id, entity_type, entity_id, campaign_id, ad_group_id, 
                 expression, expression_type, current_bid, state, campaign_state)
                VALUES (%s, %s, 'target', %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (profile_id, entity_type, entity_id) 
                DO UPDATE SET 
                    campaign_id = EXCLUDED.campaign_id,
                    ad_group_id = EXCLUDED.ad_group_id,
                    expression = EXCLUDED.expression,
                    expression_type = EXCLUDED.expression_type,
                    current_bid = EXCLUDED.current_bid,
                    state = EXCLUDED.state,
                    campaign_state = EXCLUDED.campaign_state,
                    updated_at = CURRENT_TIMESTAMP
            """, (account_id, profile_id, target_id, campaign_id, ad_group_id, 
                  expression, expression_type, bid, state, campaign_state))
            inserted += 1
        except Exception as e:
            print(f"[SP_INVENTORY] Error inserting target: {e}")
            continue
    
    try:
        conn.commit()
        print(f"[SP_INVENTORY] Saved {inserted} entities for profile {profile_id}")
    except Exception as e:
        print(f"[SP_INVENTORY] Error committing: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    
    return inserted


def get_sp_inventory_for_profile(profile_id: str, entity_type: str = None, only_enabled_campaigns: bool = True) -> List[dict]:
    """Get SP inventory for a profile, optionally filtered by entity type.
    
    Args:
        profile_id: Profile ID
        entity_type: Filter by 'keyword' or 'target'
        only_enabled_campaigns: If True, only return entities from ENABLED campaigns
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        campaign_filter = "AND campaign_state = 'ENABLED'" if only_enabled_campaigns else ""
        
        if entity_type:
            cur.execute(f"""
                SELECT * FROM sp_inventory 
                WHERE profile_id = %s AND entity_type = %s {campaign_filter}
                ORDER BY campaign_id, ad_group_id
            """, (profile_id, entity_type))
        else:
            cur.execute(f"""
                SELECT * FROM sp_inventory 
                WHERE profile_id = %s {campaign_filter}
                ORDER BY entity_type, campaign_id, ad_group_id
            """, (profile_id,))
        
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def save_sb_inventory(account_id: int, profile_id: str, targets: List[dict], campaign_states: dict = None):
    """Save SB keywords and targets inventory to database.
    
    Args:
        campaign_states: Dict mapping campaign_id -> state (ENABLED/PAUSED/ARCHIVED)
    """
    campaign_states = campaign_states or {}
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM sb_inventory WHERE profile_id = %s", (profile_id,))
        print(f"[SB_INVENTORY] Cleared old inventory for profile {profile_id}")
    except Exception as e:
        print(f"[SB_INVENTORY] Error clearing: {e}")
        conn.rollback()
    
    inserted = 0
    
    for t in targets:
        try:
            target_id = t.get('keywordId') or t.get('targetId')
            campaign_id = str(t.get('campaignId', ''))
            ad_group_id = t.get('adGroupId')
            bid = t.get('bid')
            state = (t.get('state') or 'ENABLED').upper()
            campaign_state = campaign_states.get(campaign_id, 'UNKNOWN')
            
            if not target_id or not campaign_id:
                continue
            
            entity_type = 'keyword' if t.get('keywordId') else 'target'
            expression = t.get('keywordText', '')
            match_type = t.get('matchType', '')
            
            if not expression and t.get('expressions'):
                expressions = t.get('expressions', [])
                if expressions:
                    first_exp = expressions[0]
                    expression = first_exp.get('value', '')
            
            cur.execute("""
                INSERT INTO sb_inventory 
                (account_id, profile_id, entity_type, entity_id, campaign_id, ad_group_id, 
                 expression, match_type, current_bid, state, campaign_state)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (profile_id, entity_type, entity_id) 
                DO UPDATE SET 
                    campaign_id = EXCLUDED.campaign_id,
                    ad_group_id = EXCLUDED.ad_group_id,
                    expression = EXCLUDED.expression,
                    match_type = EXCLUDED.match_type,
                    current_bid = EXCLUDED.current_bid,
                    state = EXCLUDED.state,
                    campaign_state = EXCLUDED.campaign_state,
                    updated_at = CURRENT_TIMESTAMP
            """, (account_id, profile_id, entity_type, target_id, campaign_id, ad_group_id, 
                  expression, match_type, bid, state, campaign_state))
            inserted += 1
        except Exception as e:
            print(f"[SB_INVENTORY] Error inserting target: {e}")
            continue
    
    try:
        conn.commit()
        print(f"[SB_INVENTORY] Saved {inserted} entities for profile {profile_id}")
    except Exception as e:
        print(f"[SB_INVENTORY] Error committing: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    
    return inserted


def get_sb_inventory_for_profile(profile_id: str, entity_type: str = None, only_enabled_campaigns: bool = True) -> List[dict]:
    """Get SB inventory for a profile, optionally filtered by entity type."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        campaign_filter = "AND campaign_state = 'ENABLED'" if only_enabled_campaigns else ""
        
        if entity_type:
            cur.execute(f"""
                SELECT * FROM sb_inventory 
                WHERE profile_id = %s AND entity_type = %s {campaign_filter}
                ORDER BY campaign_id, ad_group_id
            """, (profile_id, entity_type))
        else:
            cur.execute(f"""
                SELECT * FROM sb_inventory 
                WHERE profile_id = %s {campaign_filter}
                ORDER BY entity_type, campaign_id, ad_group_id
            """, (profile_id,))
        
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def build_inventory_lookup(inventory: List[dict]) -> dict:
    """Build lookup indices from inventory for matching report rows.
    
    Returns dict with multiple lookup strategies:
    - by_id: {entity_id: inventory_row}
    - by_campaign_adgroup_expression: {(campaign_id, ad_group_id, expression): inventory_row}
    """
    by_id = {}
    by_campaign_adgroup_expression = {}
    
    for row in inventory:
        entity_id = row.get('entity_id')
        campaign_id = str(row.get('campaign_id', ''))
        ad_group_id = str(row.get('ad_group_id', ''))
        expression = (row.get('expression') or '').lower().strip()
        
        if entity_id:
            by_id[entity_id] = row
        
        if campaign_id and ad_group_id and expression:
            key = (campaign_id, ad_group_id, expression)
            by_campaign_adgroup_expression[key] = row
    
    return {
        'by_id': by_id,
        'by_campaign_adgroup_expression': by_campaign_adgroup_expression
    }


def run_sync_job(job_id: int, account_id: int):
    try:
        profiles = get_profiles_for_account(account_id)
        profiles = [p for p in profiles if p.get('country_code') in ALLOWED_COUNTRIES]
        
        if not profiles:
            update_sync_job(job_id, status='COMPLETED', phase='DONE', message='Nessun profilo US/UK/IT trovato', progress_pct=100)
            return
        
        update_sync_job(
            job_id,
            status='RUNNING',
            phase='FETCHING_ASINS',
            message=f'Acquisizione dati libri...',
            total_profiles=len(profiles),
            progress_pct=5
        )
        
        access_token = get_access_token(account_id)
        if not access_token:
            update_sync_job(job_id, status='FAILED', phase='ERROR', message='Token Amazon non trovato', error='Missing access token')
            return
        
        all_asins = {}
        completed_profiles = 0
        for profile in profiles:
            profile_id = profile.get('profile_id')
            marketplace = profile.get('country_code', 'US')
            api_url = get_profile_api_url(profile_id)
            
            asins = fetch_asins_from_amazon_api(access_token, profile_id, api_url)
            print(f"Profile {profile_id} ({marketplace}): found {len(asins)} ASINs from Amazon API")
            
            for asin in asins:
                all_asins[(asin, marketplace)] = profile_id
            completed_profiles += 1
            update_sync_job(job_id, completed_profiles=completed_profiles)
        
        total_asins = len(all_asins)
        update_sync_job(
            job_id,
            phase='FETCHING_ECONOMICS',
            message=f'Elaborazione dati in corso...',
            total_asins=total_asins,
            progress_pct=10
        )
        
        completed_asins = 0
        for (asin, marketplace), profile_id in all_asins.items():
            ensure_profile_book(profile_id, asin, marketplace)
            
            oxylabs_data = fetch_oxylabs_economics(asin, marketplace)
            if oxylabs_data and oxylabs_data.get('price'):
                economics = calculate_economics(oxylabs_data)
                save_book_economics(asin, marketplace, oxylabs_data, economics)
            
            completed_asins += 1
            progress = 10 + int((completed_asins / max(total_asins, 1)) * 40)
            
            if completed_asins % 5 == 0 or completed_asins == total_asins:
                update_sync_job(
                    job_id,
                    message=f'Economics: {completed_asins}/{total_asins} ASIN completati',
                    completed_asins=completed_asins,
                    progress_pct=progress
                )
        
        update_sync_job(
            job_id,
            phase='REQUESTING_REPORTS',
            message='Richiesta report Amazon Ads (SP + SB)...',
            progress_pct=55
        )
        
        report_jobs = []
        for profile in profiles:
            profile_id = profile.get('profile_id')
            api_url = get_profile_api_url(profile_id)
            for ad_product in ['SP', 'SB']:
                for period in [14, 30]:
                    report_result = request_amazon_report(access_token, profile_id, period, api_url, account_id, ad_product=ad_product)
                    report_id = report_result.get('report_id') if report_result else None
                    if report_id:
                        report_jobs.append({
                            'profile_id': profile_id,
                            'report_id': report_id,
                            'period_days': period,
                            'marketplace': profile.get('country_code', 'US'),
                            'api_url': api_url,
                            'ad_product': ad_product
                        })
        
        total_reports = len(report_jobs)
        update_sync_job(
            job_id,
            phase='WAITING_REPORTS',
            message=f'In attesa di {total_reports} report Amazon...',
            total_reports=total_reports,
            progress_pct=60
        )
        
        completed_reports = 0
        for rj in report_jobs:
            update_sync_job(
                job_id,
                phase='DOWNLOADING_REPORTS',
                message=f'Download report {completed_reports + 1}/{total_reports}...',
                progress_pct=60 + int((completed_reports / max(total_reports, 1)) * 30)
            )
            
            rows = poll_and_download_report(
                access_token, rj['profile_id'], rj['report_id'], rj.get('api_url'),
                ad_product=rj['ad_product'], period_days=rj['period_days'], marketplace=rj['marketplace']
            )
            
            if rows:
                asin_metrics = aggregate_report_by_asin(rows)
                for asin, metrics in asin_metrics.items():
                    save_asin_metrics(rj['profile_id'], asin, rj['period_days'], metrics)
                    ensure_profile_book(rj['profile_id'], asin, rj['marketplace'])
            
            completed_reports += 1
            update_sync_job(job_id, completed_reports=completed_reports)
        
        update_sync_job(
            job_id,
            phase='ANALYZING',
            message='Analisi bid e pianificazione azioni (SP + SB)...',
            progress_pct=92
        )
        
        total_actions = 0
        for profile in profiles:
            profile_id = profile.get('profile_id')
            for ad_product in ['SP', 'SB']:
                actions = analyze_and_plan_actions(account_id, profile_id, ad_product=ad_product)
                total_actions += len(actions)
        
        update_sync_job(
            job_id,
            status='COMPLETED',
            phase='DONE',
            message=f'Completato! {total_asins} ASIN, {total_reports} report, {total_actions} azioni pianificate',
            progress_pct=100,
            completed_at=datetime.now()
        )
        
    except Exception as e:
        update_sync_job(
            job_id,
            status='FAILED',
            phase='ERROR',
            message=f'Errore: {str(e)}',
            error=str(e)
        )


def start_sync_job_async(account_id: int) -> int:
    job_id = create_sync_job(account_id)
    
    thread = threading.Thread(target=run_sync_job, args=(job_id, account_id))
    thread.daemon = True
    thread.start()
    
    return job_id
