"""
Harvest Service - search-term harvesting AUTOMATICO (SP + SB) per il backend SaaS.

Porta la logica dello script operativo dentro lo stack:
  - token per-account (get_valid_access_token) invece di .env
  - region routing per-profile (api_url)
  - stato/piano/esiti persistiti su Postgres (harvest_jobs / harvest_actions)
  - eseguibile come job in background (vedi backend/routers/harvest.py)

Flusso (run_harvest_job):
  1. Scarica i Search Term report SP + SB (ultimi N giorni).
  2. Aggrega per termine, tiene solo chi ha >= min_purchases vendite.
  3. Classifica ASIN vs keyword.
  4. Rileva AUTOMATICAMENTE le destinazioni ispezionando l'account
     (SP/SB, match type, tipo di target). Nessun ID hardcoded.
  5. Deduplica contro cio' che esiste gia' (= "nuovo").
  6. Costruisce il piano:
       KEYWORD -> SP broad@0.5 + exact@0.55, SB broad@0.5 + exact@0.55,
                  negativeExact nella AUTO SP di origine
       ASIN    -> SP ASIN@0.5 + SB ASIN@0.5, negative ASIN nella AUTO SP di origine
  7. Esegue tutto (se non dry_run) in modo resiliente, tracciando ogni azione.
"""

import re
import gzip
import json
import time
from datetime import date, datetime, timedelta

import requests
from psycopg2.extras import RealDictCursor

from backend.app.services.amazon_ads.config import CLIENT_ID
from db.accounts_db import get_connection
from backend.app.services.amazon import get_valid_access_token
from db.harvest_db import (
    update_harvest_job, insert_harvest_actions, update_action_result,
)

# ---- Bid fissi richiesti ----
BID_BROAD = 0.5
BID_EXACT = 0.55
BID_ASIN = 0.5

ASIN_RE = re.compile(r"^(B0[A-Z0-9]{8}|\d{9}[\dX])$", re.IGNORECASE)

DEFAULT_API_URL = "https://advertising-api.amazon.com"


def _log(job_id, msg, phase=None, message=None):
    print(f"[HARVEST job={job_id}] {msg}")
    if phase is not None or message is not None:
        fields = {}
        if phase is not None:
            fields["phase"] = phase
        if message is not None:
            fields["message"] = message
        try:
            update_harvest_job(job_id, **fields)
        except Exception:
            pass


def clean(v):
    return "" if v is None else str(v).strip()


def safe_float(v):
    try:
        if v is None or v == "":
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def get_profile_api_url(profile_id: str) -> str:
    """Region routing: legge api_url dal profilo (fallback NA)."""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT api_url FROM client_profiles WHERE profile_id = %s", (profile_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row.get("api_url"):
            return row["api_url"]
    except Exception:
        pass
    return DEFAULT_API_URL


# ============================================================
# HTTP helpers (parametrizzati per api_url + profile scope)
# ============================================================

def _headers(access_token, profile_id, accept="application/json", content_type="application/json"):
    return {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Accept": accept,
        "Content-Type": content_type,
        "Prefer": "return=representation",
    }


def _post_list(access_token, api_url, profile_id, path, result_key, media,
               extra_payload=None, sb_fallback=False):
    url = f"{api_url}{path}"
    h = _headers(access_token, profile_id, accept=media, content_type=media)
    items, next_token, page = [], None, 1
    while True:
        payload = {"stateFilter": {"include": ["ENABLED", "PAUSED", "ARCHIVED"]}, "maxResults": 100}
        if extra_payload:
            payload.update(extra_payload)
        if next_token:
            payload["nextToken"] = next_token
        r = requests.post(url, headers=h, json=payload, timeout=60)
        if sb_fallback and r.status_code in (406, 415):
            h2 = _headers(access_token, profile_id, accept="*/*", content_type="application/json")
            r = requests.post(url, headers=h2, json=payload, timeout=60)
        if r.status_code >= 400:
            raise Exception(f"LIST {path} -> {r.status_code}: {r.text[:300]}")
        data = r.json()
        items.extend(data.get(result_key, []))
        next_token = data.get("nextToken")
        if not next_token:
            break
        page += 1
        time.sleep(0.2)
    return items


# ============================================================
# REPORTS
# ============================================================

def _split_range(start_date, end_date, chunk_days=30):
    chunks, cur = [], start_date
    while cur <= end_date:
        end = min(cur + timedelta(days=chunk_days - 1), end_date)
        chunks.append((cur, end))
        cur = end + timedelta(days=1)
    return chunks


def _create_report(access_token, api_url, profile_id, name, start_date, end_date, configuration):
    url = f"{api_url}/reporting/reports"
    h = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Content-Type": "application/json",
    }
    payload = {
        "name": name,
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "configuration": configuration,
    }
    r = requests.post(url, headers=h, json=payload, timeout=60)
    if r.status_code >= 400:
        raise Exception(f"CREATE REPORT -> {r.status_code}: {r.text[:400]}")
    return r.json()["reportId"]


def _poll_report(access_token, api_url, profile_id, report_id, max_attempts=90,
                 sleep_seconds=20, job_id=None, hb_label=""):
    url = f"{api_url}/reporting/reports/{report_id}"
    h = {
        "Authorization": f"Bearer {access_token}",
        "Amazon-Advertising-API-ClientId": CLIENT_ID,
        "Amazon-Advertising-API-Scope": str(profile_id),
        "Accept": "application/json",
    }
    for attempt in range(1, max_attempts + 1):
        r = requests.get(url, headers=h, timeout=60)
        if r.status_code >= 400:
            raise Exception(f"POLL REPORT -> {r.status_code}: {r.text[:300]}")
        data = r.json()
        status = data.get("status")
        if status in ("COMPLETED", "SUCCESS"):
            return data.get("url") or data.get("location")
        if status in ("FAILED", "FAILURE", "CANCELLED"):
            raise Exception(f"Report fallito: {status}")
        if job_id:  # heartbeat: tiene vivo updated_at durante l'attesa del report
            try:
                update_harvest_job(job_id, message=f"Attendo report {hb_label} ({attempt}/{max_attempts})...")
            except Exception:
                pass
        time.sleep(sleep_seconds)
    raise TimeoutError("Report non completato in tempo.")


def _download_gzip_json(url):
    r = requests.get(url, timeout=120)
    if r.status_code >= 400:
        raise Exception(f"DOWNLOAD -> {r.status_code}")
    return json.loads(gzip.decompress(r.content).decode("utf-8"))


def download_search_terms(access_token, api_url, profile_id, ad_product, days, job_id=None):
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)

    if ad_product == "SPONSORED_PRODUCTS":
        report_type_id = "spSearchTerm"
        columns = ["campaignId", "campaignName", "adGroupId", "adGroupName",
                   "keyword", "matchType", "targeting", "searchTerm",
                   "impressions", "clicks", "cost",
                   "purchases7d", "sales7d", "purchases14d", "sales14d"]
        purchases_field = "purchases14d"
    else:
        report_type_id = "sbSearchTerm"
        columns = ["campaignId", "campaignName", "adGroupId", "adGroupName",
                   "keywordText", "matchType", "searchTerm",
                   "impressions", "clicks", "cost", "purchases", "sales"]
        purchases_field = "purchases"

    all_rows = []
    for s, e in _split_range(start_date, end_date, 30):
        cfg = {
            "adProduct": ad_product,
            "groupBy": ["searchTerm"],
            "columns": columns,
            "reportTypeId": report_type_id,
            "timeUnit": "SUMMARY",
            "format": "GZIP_JSON",
        }
        report_id = _create_report(access_token, api_url, profile_id,
                                   f"harvest-{report_type_id}-{s}-{e}", s, e, cfg)
        url = _poll_report(access_token, api_url, profile_id, report_id,
                           job_id=job_id, hb_label=f"{report_type_id} {s}->{e}")
        rows = _download_gzip_json(url)
        for row in rows:
            row["_adProduct"] = ad_product
            row["_purchases"] = safe_float(row.get(purchases_field))
            row["_cost"] = safe_float(row.get("cost"))
        all_rows.extend(rows)
        time.sleep(0.5)
    return all_rows


# ============================================================
# STRUTTURA ACCOUNT (routing automatico)
# ============================================================

def _get_sp_campaigns(t, u, p):
    out = {}
    for c in _post_list(t, u, p, "/sp/campaigns/list", "campaigns",
                        "application/vnd.spCampaign.v3+json"):
        cid = clean(c.get("campaignId"))
        if cid:
            out[cid] = {"campaignId": cid, "name": clean(c.get("name")),
                        "state": clean(c.get("state")).upper(),
                        "targetingType": clean(c.get("targetingType")).upper()}
    return out


def _get_sp_adgroups(t, u, p):
    out = {}
    for a in _post_list(t, u, p, "/sp/adGroups/list", "adGroups",
                        "application/vnd.spAdGroup.v3+json"):
        agid = clean(a.get("adGroupId"))
        if agid:
            out[agid] = {"adGroupId": agid, "campaignId": clean(a.get("campaignId")),
                         "name": clean(a.get("name")), "state": clean(a.get("state")).upper()}
    return out


def _get_sp_keywords(t, u, p):
    return _post_list(t, u, p, "/sp/keywords/list", "keywords",
                      "application/vnd.spKeyword.v3+json")


def _get_sp_targets(t, u, p):
    return _post_list(t, u, p, "/sp/targets/list", "targetingClauses",
                      "application/vnd.spTargetingClause.v3+json")


def _get_sp_neg_keywords(t, u, p):
    try:
        return _post_list(t, u, p, "/sp/negativeKeywords/list", "negativeKeywords",
                          "application/vnd.spNegativeKeyword.v3+json")
    except Exception:
        return []


def _get_sp_neg_targets(t, u, p):
    try:
        return _post_list(t, u, p, "/sp/negativeTargets/list", "negativeTargetingClauses",
                          "application/vnd.spNegativeTargetingClause.v3+json")
    except Exception:
        return []


def _get_sb_campaigns(t, u, p):
    out = {}
    for c in _post_list(t, u, p, "/sb/v4/campaigns/list", "campaigns",
                        "application/vnd.sbcampaignresource.v4+json", sb_fallback=True):
        cid = clean(c.get("campaignId"))
        if cid:
            out[cid] = {"campaignId": cid, "name": clean(c.get("name") or c.get("campaignName")),
                        "state": clean(c.get("state")).upper()}
    return out


def _get_sb_adgroups(t, u, p):
    out = {}
    try:
        raw = _post_list(t, u, p, "/sb/v4/adGroups/list", "adGroups",
                         "application/vnd.sbadgroupresource.v4+json", sb_fallback=True)
    except Exception:
        return out
    for a in raw:
        agid = clean(a.get("adGroupId"))
        if agid:
            out[agid] = {"adGroupId": agid, "campaignId": clean(a.get("campaignId")),
                         "name": clean(a.get("name") or a.get("adGroupName")),
                         "state": clean(a.get("state")).upper()}
    return out


def _get_sb_keywords(t, u, p):
    all_kw, start_index, count = [], 0, 1000
    while True:
        url = (f"{u}/sb/keywords?startIndex={start_index}"
               f"&count={count}&stateFilter=enabled,paused,archived")
        h = _headers(t, p, accept="application/vnd.sbkeywordresource.v3+json",
                     content_type="application/json")
        r = requests.get(url, headers=h, timeout=60)
        if r.status_code >= 400:
            h = _headers(t, p, accept="*/*", content_type="application/json")
            r = requests.get(url, headers=h, timeout=60)
        if r.status_code >= 400:
            break
        batch = r.json()
        if not batch:
            break
        all_kw.extend(batch)
        if len(batch) < count:
            break
        start_index += count
        time.sleep(0.2)
    return all_kw


def _sp_target_asin(target):
    for expr in target.get("expression", []) or []:
        if clean(expr.get("type")).upper() == "ASIN_SAME_AS":
            return clean(expr.get("value")).upper()
    return ""


def _sp_negtarget_asin(neg):
    for expr in neg.get("expression", []) or []:
        if clean(expr.get("type")).upper() == "ASIN_SAME_AS":
            return clean(expr.get("value")).upper()
    return ""


def _pick_best_adgroup(counter, adgroups):
    if not counter:
        return None
    def score(item):
        agid, cnt = item
        ag = adgroups.get(agid, {})
        return (cnt, 1 if ag.get("state") == "ENABLED" else 0)
    best_id = sorted(counter.items(), key=score, reverse=True)[0][0]
    return adgroups.get(best_id)


def _classify_sp(campaigns, adgroups, keywords, targets):
    manual_ags = {agid for agid, a in adgroups.items()
                  if campaigns.get(a["campaignId"], {}).get("targetingType") == "MANUAL"}
    broad_c, exact_c, asin_c = {}, {}, {}
    for kw in keywords:
        agid = clean(kw.get("adGroupId"))
        if agid not in manual_ags:
            continue
        mt = clean(kw.get("matchType")).upper()
        if mt == "BROAD":
            broad_c[agid] = broad_c.get(agid, 0) + 1
        elif mt == "EXACT":
            exact_c[agid] = exact_c.get(agid, 0) + 1
    for tg in targets:
        agid = clean(tg.get("adGroupId"))
        if agid in manual_ags and _sp_target_asin(tg):
            asin_c[agid] = asin_c.get(agid, 0) + 1
    return {
        "broad": _pick_best_adgroup(broad_c, adgroups),
        "exact": _pick_best_adgroup(exact_c, adgroups),
        "asin": _pick_best_adgroup(asin_c, adgroups),
        "auto_campaign_ids": {cid for cid, c in campaigns.items() if c["targetingType"] == "AUTO"},
    }


def _classify_sb(campaigns, adgroups, keywords):
    broad_c, exact_c, ag_with_kw = {}, {}, set()
    for kw in keywords:
        agid = clean(kw.get("adGroupId"))
        if not agid:
            continue
        ag_with_kw.add(agid)
        mt = clean(kw.get("matchType")).upper()
        if mt == "BROAD":
            broad_c[agid] = broad_c.get(agid, 0) + 1
        elif mt == "EXACT":
            exact_c[agid] = exact_c.get(agid, 0) + 1
    asin_candidates = {agid: 1 for agid, ag in adgroups.items()
                       if agid not in ag_with_kw and ag.get("state") != "ARCHIVED"}
    return {
        "broad": _pick_best_adgroup(broad_c, adgroups),
        "exact": _pick_best_adgroup(exact_c, adgroups),
        "asin": _pick_best_adgroup(asin_candidates, adgroups),
    }


# ============================================================
# TERMINI QUALIFICATI + PIANO
# ============================================================

def _build_qualifying(sp_rows, sb_rows, sp_auto_ids, min_purchases):
    terms = {}
    def touch(term):
        key = term.lower()
        if key not in terms:
            terms[key] = {"term": term, "is_asin": bool(ASIN_RE.match(term)),
                          "purchases": 0.0, "cost": 0.0, "sp_auto_origins": set()}
        return terms[key]
    for r in sp_rows:
        term = clean(r.get("searchTerm"))
        if not term or term == "*":
            continue
        t = touch(term)
        t["purchases"] += safe_float(r.get("_purchases"))
        t["cost"] += safe_float(r.get("_cost"))
        cid, agid = clean(r.get("campaignId")), clean(r.get("adGroupId"))
        if cid in sp_auto_ids and agid:
            t["sp_auto_origins"].add((cid, agid))
    for r in sb_rows:
        term = clean(r.get("searchTerm"))
        if not term or term == "*":
            continue
        t = touch(term)
        t["purchases"] += safe_float(r.get("_purchases"))
        t["cost"] += safe_float(r.get("_cost"))
    q = [t for t in terms.values() if t["purchases"] >= min_purchases]
    q.sort(key=lambda x: x["purchases"], reverse=True)
    return q


def _build_plan(qualifying, sp_dest, sb_dest,
                ex_sp_kw, ex_sp_tgt, ex_sp_negkw, ex_sp_negtgt, ex_sb_kw):
    actions = []
    def add(kind, product, dest, term, value, match_type, bid, note=""):
        actions.append({
            "kind": kind, "product": product,
            "campaignId": dest[0], "adGroupId": dest[1],
            "term": term, "value": value, "matchType": match_type, "bid": bid,
            "note": note, "status": "PLANNED", "response": "",
        })
    for t in qualifying:
        term = t["term"]
        if t["is_asin"]:
            asin = term.upper()
            if sp_dest["asin"]:
                d = (sp_dest["asin"]["campaignId"], sp_dest["asin"]["adGroupId"])
                if (d[1], asin) not in ex_sp_tgt:
                    add("asin_target", "SP", d, term, asin, "ASIN_SAME_AS", BID_ASIN)
            if sb_dest["asin"]:
                d = (sb_dest["asin"]["campaignId"], sb_dest["asin"]["adGroupId"])
                add("asin_target", "SB", d, term, asin, "asinSameAs", BID_ASIN,
                    note="SB ASIN dedup best-effort")
            for (cid, agid) in sorted(t["sp_auto_origins"]):
                if (agid, asin) not in ex_sp_negtgt:
                    add("neg_asin", "SP", (cid, agid), term, asin, "ASIN_SAME_AS", None,
                        note="negative ASIN in auto")
        else:
            for product, dm in (("SP", sp_dest), ("SB", sb_dest)):
                ex = ex_sp_kw if product == "SP" else ex_sb_kw
                if dm["broad"]:
                    d = (dm["broad"]["campaignId"], dm["broad"]["adGroupId"])
                    if (d[1], term.lower(), "BROAD") not in ex:
                        add("keyword", product, d, term, term, "BROAD", BID_BROAD)
                if dm["exact"]:
                    d = (dm["exact"]["campaignId"], dm["exact"]["adGroupId"])
                    if (d[1], term.lower(), "EXACT") not in ex:
                        add("keyword", product, d, term, term, "EXACT", BID_EXACT)
            for (cid, agid) in sorted(t["sp_auto_origins"]):
                if (agid, term.lower(), "NEGATIVE_EXACT") not in ex_sp_negkw:
                    add("neg_keyword", "SP", (cid, agid), term, term, "NEGATIVE_EXACT", None,
                        note="negativeExact in auto")
    return actions


# ============================================================
# ESECUZIONE
# ============================================================

def _chunk(items, size=100):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _post(access_token, api_url, profile_id, path, media, body):
    url = f"{api_url}{path}"
    h = _headers(access_token, profile_id, accept=media, content_type=media)
    r = requests.post(url, headers=h, json=body, timeout=60)
    if r.status_code in (406, 415):
        h2 = _headers(access_token, profile_id, accept="*/*", content_type="application/json")
        r = requests.post(url, headers=h2, json=body, timeout=60)
    return r


def _execute(access_token, api_url, profile_id, actions):
    groups = {}
    for a in actions:
        groups.setdefault((a["kind"], a["product"]), []).append(a)

    counters = {"ok": 0, "err": 0}

    def run(group_actions, path, media, wrap, builder):
        for batch in _chunk(group_actions, 100):
            body = wrap([builder(a) for a in batch])
            try:
                r = _post(access_token, api_url, profile_id, path, media, body)
                ok = r.status_code < 400
                resp = f"{r.status_code} {r.text[:300]}"
                for a in batch:
                    a["status"] = "SENT_OK" if ok else "SENT_ERR"
                    a["response"] = resp
                    counters["ok" if ok else "err"] += 1
                    if a.get("db_id"):
                        update_action_result(a["db_id"], a["status"], resp)
            except Exception as e:
                for a in batch:
                    a["status"] = "EXCEPTION"
                    a["response"] = str(e)[:300]
                    counters["err"] += 1
                    if a.get("db_id"):
                        update_action_result(a["db_id"], "EXCEPTION", str(e)[:300])
            time.sleep(1)

    if ("keyword", "SP") in groups:
        run(groups[("keyword", "SP")], "/sp/keywords",
            "application/vnd.spKeyword.v3+json",
            lambda items: {"keywords": items},
            lambda a: {"campaignId": a["campaignId"], "adGroupId": a["adGroupId"],
                       "keywordText": a["value"], "matchType": a["matchType"],
                       "state": "ENABLED", "bid": a["bid"]})
    if ("asin_target", "SP") in groups:
        run(groups[("asin_target", "SP")], "/sp/targets",
            "application/vnd.spTargetingClause.v3+json",
            lambda items: {"targetingClauses": items},
            lambda a: {"campaignId": a["campaignId"], "adGroupId": a["adGroupId"],
                       "expressionType": "MANUAL",
                       "expression": [{"type": "ASIN_SAME_AS", "value": a["value"]}],
                       "state": "ENABLED", "bid": a["bid"]})
    if ("neg_keyword", "SP") in groups:
        run(groups[("neg_keyword", "SP")], "/sp/negativeKeywords",
            "application/vnd.spNegativeKeyword.v3+json",
            lambda items: {"negativeKeywords": items},
            lambda a: {"campaignId": a["campaignId"], "adGroupId": a["adGroupId"],
                       "keywordText": a["value"], "matchType": "NEGATIVE_EXACT",
                       "state": "ENABLED"})
    if ("neg_asin", "SP") in groups:
        run(groups[("neg_asin", "SP")], "/sp/negativeTargets",
            "application/vnd.spNegativeTargetingClause.v3+json",
            lambda items: {"negativeTargetingClauses": items},
            lambda a: {"campaignId": a["campaignId"], "adGroupId": a["adGroupId"],
                       "expression": [{"type": "ASIN_SAME_AS", "value": a["value"]}],
                       "state": "ENABLED"})
    if ("keyword", "SB") in groups:
        run(groups[("keyword", "SB")], "/sb/keywords", "application/json",
            lambda items: items,
            lambda a: {"campaignId": a["campaignId"], "adGroupId": a["adGroupId"],
                       "keywordText": a["value"], "matchType": a["matchType"].lower(),
                       "bid": a["bid"]})
    if ("asin_target", "SB") in groups:
        run(groups[("asin_target", "SB")], "/sb/targets", "application/json",
            lambda items: {"targets": items},
            lambda a: {"campaignId": a["campaignId"], "adGroupId": a["adGroupId"],
                       "expressions": [{"type": "asinSameAs", "value": a["value"]}],
                       "bid": a["bid"]})

    return counters


def _dest_summary(d):
    if not d:
        return None
    return {"adGroupId": d["adGroupId"], "campaignId": d["campaignId"], "name": d["name"]}


# ============================================================
# ORCHESTRATORE
# ============================================================

def run_harvest_job(job_id: int, account_id: int, profile_id: str,
                    days: int, min_purchases: int, dry_run: bool):
    """Esegue l'intero harvesting per (account, profile). Aggiorna harvest_jobs/actions."""
    try:
        update_harvest_job(job_id, status="RUNNING", phase="TOKEN", message="Recupero token...")
        access_token, err = get_valid_access_token(account_id)
        if not access_token:
            raise Exception(f"Token non valido: {err}")
        api_url = get_profile_api_url(profile_id)

        # 1. Report
        _log(job_id, "scarico SP search terms", phase="REPORT_SP", message="Scarico report SP...")
        sp_rows = download_search_terms(access_token, api_url, profile_id, "SPONSORED_PRODUCTS", days, job_id=job_id)
        _log(job_id, "scarico SB search terms", phase="REPORT_SB", message="Scarico report SB...")
        sb_rows = download_search_terms(access_token, api_url, profile_id, "SPONSORED_BRANDS", days, job_id=job_id)

        # 2. Struttura account
        _log(job_id, "ispeziono struttura account", phase="STRUCTURE",
             message="Ispeziono campagne/ad group per il routing...")
        sp_campaigns = _get_sp_campaigns(access_token, api_url, profile_id)
        sp_adgroups = _get_sp_adgroups(access_token, api_url, profile_id)
        sp_keywords = _get_sp_keywords(access_token, api_url, profile_id)
        sp_targets = _get_sp_targets(access_token, api_url, profile_id)
        sp_negkw = _get_sp_neg_keywords(access_token, api_url, profile_id)
        sp_negtgt = _get_sp_neg_targets(access_token, api_url, profile_id)
        sb_campaigns = _get_sb_campaigns(access_token, api_url, profile_id)
        sb_adgroups = _get_sb_adgroups(access_token, api_url, profile_id)
        sb_keywords = _get_sb_keywords(access_token, api_url, profile_id)

        sp_dest = _classify_sp(sp_campaigns, sp_adgroups, sp_keywords, sp_targets)
        sb_dest = _classify_sb(sb_campaigns, sb_adgroups, sb_keywords)

        # dedup sets
        ex_sp_kw = {(clean(k.get("adGroupId")), clean(k.get("keywordText")).lower(),
                     clean(k.get("matchType")).upper()) for k in sp_keywords}
        ex_sp_tgt = {(clean(t.get("adGroupId")), _sp_target_asin(t))
                     for t in sp_targets if _sp_target_asin(t)}
        ex_sp_negkw = {(clean(n.get("adGroupId")), clean(n.get("keywordText")).lower(),
                        clean(n.get("matchType")).upper()) for n in sp_negkw}
        ex_sp_negtgt = {(clean(n.get("adGroupId")), _sp_negtarget_asin(n))
                        for n in sp_negtgt if _sp_negtarget_asin(n)}
        ex_sb_kw = {(clean(k.get("adGroupId")), clean(k.get("keywordText")).lower(),
                     clean(k.get("matchType")).upper()) for k in sb_keywords}

        # 3. Qualifying
        _log(job_id, "filtro termini qualificati", phase="FILTER",
             message="Filtro termini con vendite...")
        qualifying = _build_qualifying(sp_rows, sb_rows, sp_dest["auto_campaign_ids"], min_purchases)

        # 4. Piano
        actions = _build_plan(qualifying, sp_dest, sb_dest,
                              ex_sp_kw, ex_sp_tgt, ex_sp_negkw, ex_sp_negtgt, ex_sb_kw)
        insert_harvest_actions(job_id, actions)

        update_harvest_job(
            job_id, phase="PLANNED",
            message=f"{len(qualifying)} termini, {len(actions)} azioni pianificate.",
            qualifying_terms=len(qualifying), planned_actions=len(actions),
            sp_dest={k: _dest_summary(v) for k, v in sp_dest.items() if k != "auto_campaign_ids"},
            sb_dest={k: _dest_summary(v) for k, v in sb_dest.items()},
        )

        # 5. Esecuzione
        if dry_run:
            update_harvest_job(job_id, status="DONE", phase="DONE_DRYRUN",
                               message="Dry-run: piano pronto, nessuna scrittura.",
                               finished_at=datetime.now())
            return

        _log(job_id, "esecuzione", phase="EXECUTE", message="Eseguo le azioni su Amazon...")
        counters = _execute(access_token, api_url, profile_id, actions)

        update_harvest_job(job_id, status="DONE", phase="DONE",
                           message=f"Completato. OK={counters['ok']} ERR={counters['err']}",
                           executed_ok=counters["ok"], executed_err=counters["err"],
                           finished_at=datetime.now())
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            update_harvest_job(job_id, status="FAILED", phase="ERROR",
                               message=f"Errore: {e}", error=str(e)[:1000],
                               finished_at=datetime.now())
        except Exception:
            pass
