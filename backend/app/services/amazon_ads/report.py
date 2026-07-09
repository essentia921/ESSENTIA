# amazon_api/reports.py

import time
import json
import gzip
from io import BytesIO
from datetime import date, timedelta

import requests

from backend.app.services.amazon_ads.config import API_BASE_URL, CLIENT_ID


# Intervalli di polling per la generazione del report
REPORT_POLL_INTERVAL = 5       # secondi
REPORT_POLL_TIMEOUT = 300      # secondi


def _common_headers(access_token: str, profile_id: str) -> dict:
    """
    Header standard per le chiamate Amazon Ads (reporting v3).
    """
    return {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def create_sp_targeting_report(
    access_token: str,
    profile_id: str,
    start_date: date,
    end_date: date,
    campaign_ids=None,
    api_url: str = None,
) -> str:
    """
    Richiede la creazione di un report Targeting Sponsored Products (versione 3).
    Usa colonne appropriate basate sul periodo del report.
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/reporting/reports"

    headers = _common_headers(access_token, profile_id)

    start_str = start_date.isoformat()
    end_str = end_date.isoformat()
    
    days_diff = (end_date - start_date).days + 1
    if days_diff <= 14:
        sales_col = "sales14d"
        purchases_col = "purchases14d"
    else:
        sales_col = "sales30d"
        purchases_col = "purchases30d"

    configuration = {
        "adProduct": "SPONSORED_PRODUCTS",
        "reportTypeId": "spTargeting",
        "timeUnit": "SUMMARY",
        "format": "GZIP_JSON",
        "columns": [
            "campaignId",
            "adGroupId",
            "targeting",
            "impressions",
            "clicks",
            "cost",
            purchases_col,
            sales_col,
        ],
        "groupBy": ["targeting"],
    }

    filters = []
    if campaign_ids:
        # Sintassi tipica dei filtri v3; se da errore, controlla la doc v3.
        filters.append(
            {
                "field": "campaignId",
                "values": [str(cid) for cid in campaign_ids],
            }
        )

    if filters:
        configuration["filters"] = filters

    payload = {
        "name": "AgentSP SP Targeting report",
        "startDate": start_str,
        "endDate": end_str,
        "configuration": configuration,
    }

    resp = requests.post(url, headers=headers, json=payload)
    print("=== CREATE REPORT SP TARGETING ===")
    print(resp.status_code, resp.text)
    print("==================================\n")
    resp.raise_for_status()

    data = resp.json()
    report_id = data.get("reportId")
    if not report_id:
        raise RuntimeError(f"ReportId non presente nella risposta: {data}")

    return report_id


def check_report_status_once(
    access_token: str,
    profile_id: str,
    report_id: str,
    api_url: str = None,
) -> dict:
    """
    Controlla lo stato del report UNA SOLA VOLTA senza loop.
    Restituisce il dict con status, url, etc.
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/reporting/reports/{report_id}"
    headers = _common_headers(access_token, profile_id)

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def wait_for_report(
    access_token: str,
    profile_id: str,
    report_id: str,
    timeout: int = REPORT_POLL_TIMEOUT,
    poll_interval: int = REPORT_POLL_INTERVAL,
    api_url: str = None,
) -> dict:
    """
    Polling su GET /reporting/reports/{reportId} finché il report non è pronto.
    """
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/reporting/reports/{report_id}"
    headers = _common_headers(access_token, profile_id)

    start_ts = time.time()

    while True:
        resp = requests.get(url, headers=headers)
        print("=== GET REPORT STATUS ===")
        print(resp.status_code, resp.text[:400])
        print("=========================\n")
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status")
        if status == "SUCCESS":
            return data
        if status in ("FAILURE", "CANCELLED"):
            raise RuntimeError(f"Report {report_id} fallito con status={status}")

        if time.time() - start_ts > timeout:
            raise TimeoutError(
                f"Timeout in attesa del report {report_id}, ultimo status={status}"
            )

        time.sleep(poll_interval)


def download_report_gzip_json(location_url: str) -> list:
    """
    Scarica il file da location_url (GZIP + JSON).
    Gestisce sia JSON array [{},...] che JSON lines (una riga per record).
    """
    resp = requests.get(location_url)
    resp.raise_for_status()

    with gzip.GzipFile(fileobj=BytesIO(resp.content)) as gz:
        raw = gz.read().decode("utf-8").strip()

    if not raw:
        return []

    # Prova prima come JSON array
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    # Fallback: JSON lines (una riga per record)
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def split_date_range(start: date, end: date, max_days: int = 31):
    """
    Divide un intervallo di date in chunk di max_days giorni.
    Restituisce una lista di tuple (chunk_start, chunk_end).
    """
    chunks = []
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=max_days - 1), end)
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)
    return chunks


def create_sp_search_term_report(
    access_token: str,
    profile_id: str,
    start_date: date,
    end_date: date,
    api_url: str = None,
) -> str:
    """
    Richiede la creazione di un report Search Term Sponsored Products (v3).
    reportTypeId: spSearchTerm — mostra le query reali dei clienti per ad group.

    Gestisce HTTP 425 (duplicate): Amazon restituisce l'ID del report esistente
    nel campo detail, che viene estratto e usato direttamente.
    """
    import re
    base_url = api_url or API_BASE_URL
    url = f"{base_url}/reporting/reports"

    headers = _common_headers(access_token, profile_id)

    payload = {
        "name": f"SP Search Term {start_date.isoformat()} {end_date.isoformat()}",
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "configuration": {
            "adProduct": "SPONSORED_PRODUCTS",
            "reportTypeId": "spSearchTerm",
            "timeUnit": "DAILY",
            "format": "GZIP_JSON",
            "groupBy": ["searchTerm"],
            "columns": [
                "date",
                "campaignId",
                "campaignName",
                "adGroupId",
                "adGroupName",
                "keywordId",
                "keyword",
                "targeting",
                "matchType",
                "searchTerm",
                "impressions",
                "clicks",
                "cost",
                "costPerClick",
                "clickThroughRate",
                "purchases14d",
                "sales14d",
                "unitsSoldClicks14d",
                "acosClicks14d",
                "roasClicks14d",
                "kindleEditionNormalizedPagesRead14d",
                "kindleEditionNormalizedPagesRoyalties14d",
            ],
        },
    }

    resp = requests.post(url, headers=headers, json=payload)
    print("=== CREATE REPORT SP SEARCH TERM ===")
    print(resp.status_code, resp.text[:500])
    print("=====================================\n")

    # 425 = report duplicato — Amazon include l'ID esistente nel detail
    if resp.status_code == 425:
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            detail = resp.text
        # formato: "The Request is a duplicate of : <reportId>"
        match = re.search(r"duplicate of\s*:\s*([\w-]+)", detail, re.IGNORECASE)
        if match:
            existing_id = match.group(1).strip()
            print(f"[SEARCH-TERM] 425 duplicate — riuso report esistente: {existing_id}")
            return existing_id
        raise RuntimeError(f"425 duplicate ma ID non trovato nel detail: {detail}")

    resp.raise_for_status()

    data = resp.json()
    report_id = data.get("reportId")
    if not report_id:
        raise RuntimeError(f"ReportId non presente nella risposta: {data}")

    return report_id


def get_sp_targeting_metrics(
    access_token: str,
    profile_id: str,
    campaign_ids,
    timeframe_days: int,
) -> dict:
    """
    Wrapper alto livello:
    - calcola start/end date in base al timeframe richiesto
    - crea il report SP Targeting
    - attende la generazione
    - scarica e parsifica il GZIP JSON
    - restituisce un dict {targetId: metriche}

    Returns:
        {
          targetId (int o string): {
              "impressions": int,
              "clicks": int,
              "cost": float,
              "orders": int,
              "sales": float,
              "acos": float o None,
          },
          ...
        }
    """

    # Per sicurezza usiamo dati fino a ieri, non includiamo oggi (ritardi attribution)
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=timeframe_days - 1)

    report_id = create_sp_targeting_report(
        access_token=access_token,
        profile_id=profile_id,
        start_date=start,
        end_date=end,
        campaign_ids=campaign_ids,
    )

    meta = wait_for_report(access_token, profile_id, report_id)
    location = meta.get("location")
    if not location:
        raise RuntimeError(f"Nessuna 'location' nel meta report: {meta}")

    rows = download_report_gzip_json(location)

    metrics_by_target = {}

    for row in rows:
        tid = row.get("targetId")
        if tid is None:
            continue

        impressions = int(row.get("impressions", 0) or 0)
        clicks = int(row.get("clicks", 0) or 0)
        cost = float(row.get("cost", 0.0) or 0.0)

        # Nomina ordini tipica: purchases14d (v3) oppure attributedConversions14d (v2)
        orders = (
            row.get("purchases14d")
            or row.get("attributedConversions14d")
            or 0
        )
        orders = int(orders or 0)

        # Nomina vendite tipica: sales14d (v3) oppure attributedSales14d (v2)
        sales = (
            row.get("sales14d")
            or row.get("attributedSales14d")
            or 0.0
        )
        sales = float(sales or 0.0)

        acos = None
        if sales > 0 and cost > 0:
            acos = (cost / sales) * 100.0

        metrics_by_target[str(tid)] = {
            "impressions": impressions,
            "clicks": clicks,
            "cost": cost,
            "orders": orders,
            "sales": sales,
            "acos": acos,
        }

    return metrics_by_target
