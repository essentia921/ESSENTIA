"""
Bid Analyzer - Pure analysis functions for generating bid actions

This module is PURE: no database queries, no Amazon API calls.
All data must be passed in as parameters.

BUSINESS RULES:
1. LOW_IMPRESSIONS (priority): Targets with impressions < threshold receive bid increases
   to gain visibility, REGARDLESS of ACOS/ACOS_BE data. These targets lack sufficient
   data for meaningful ACOS analysis.
   
2. GHOST TARGETS: Targets in live_bids but absent from reports (0 impressions) also
   receive LOW_IMPRESSIONS treatment to become visible.
   
3. ACOS-BASED (standard): Targets with sufficient impressions are evaluated based on
   ACOS vs ACOS_BE thresholds. Requires both ACOS (calculated from sales) and ACOS_BE
   (from book association) to generate actions.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

AUTO_TOKENS = {"close-match", "loose-match", "substitutes", "complements"}


def normalize_display_keyword(expr: str, target_type: str = None) -> str:
    """
    Normalize keyword/targeting expression for consistent UI display.
    For ASIN targets: strips 'asin=' prefix and quotes, returns just the ASIN code.
    For categories: keeps 'category=' prefix for clarity.
    For keywords: returns as-is.
    """
    if not expr:
        return ""
    s = expr.strip()
    
    # Remove quotes
    s = s.replace('"', '').replace("'", '').strip()
    
    # For ASIN targets, strip the 'asin=' prefix
    if target_type in ('product_target',) or s.lower().startswith('asin='):
        m = re.search(r'asin\s*=\s*([A-Za-z0-9]{10})', s, flags=re.IGNORECASE)
        if m:
            return m.group(1).upper()
    
    return s


def normalize_expr(expr: str) -> str:
    """
    Normalize targeting expression for consistent matching.
    Handles quotes, spaces, case variations.
    """
    if not expr:
        return ""
    s = expr.strip()

    # Uniforma virgolette e backslash
    s = s.replace('\\"', '"').replace(""", '"').replace(""", '"').replace("'", "'")
    s = re.sub(r"\s+", " ", s)

    # asin="B0..." oppure asin='B0...' oppure asin=B0...
    m = re.search(r'asin\s*=\s*["\']?([A-Za-z0-9]{8,20})["\']?', s, flags=re.IGNORECASE)
    if m:
        return f"asin={m.group(1).upper()}"

    # category="Nome..."
    m = re.search(r'category\s*=\s*["\']?(.+?)["\']?$', s, flags=re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        name = re.sub(r'\s+', ' ', name)
        return f"category={name}"

    # auto/theme tokens
    low = s.lower().strip()
    if low in AUTO_TOKENS:
        return low

    # keyword / phrase normale
    return re.sub(r"\s+", " ", s.strip()).lower()

ACOS_LOW_THRESHOLD = Decimal("0.20")
ACOS_HIGH_THRESHOLD = Decimal("0.50")
DELTA_BID = Decimal("0.01")
LOW_CLICKS_THRESHOLD = 5
LOW_IMPRESSIONS_THRESHOLD = 100


def get_acos_be_from_map(asin: str, asin_to_acos_be_map: Dict[str, float]) -> Optional[Decimal]:
    """Get ACOS BE from pre-loaded map. Returns Decimal or None."""
    if not asin or not asin_to_acos_be_map:
        return None
    
    acos_be = asin_to_acos_be_map.get(asin)
    if acos_be is not None:
        return Decimal(str(acos_be))
    return None


def get_book_acos_be(asin: str, profile_id: str = None) -> Optional[Decimal]:
    """Legacy function - queries DB. Use get_acos_be_from_map for pure analysis."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from backend.app.core.config import settings
        
        conn = psycopg2.connect(settings.DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        if profile_id:
            cur.execute("SELECT acos_be FROM books WHERE asin = %s AND profile_id = %s", (asin, profile_id))
        else:
            cur.execute("SELECT acos_be FROM books WHERE asin = %s", (asin,))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result and result.get("acos_be"):
            return Decimal(str(result["acos_be"])) / Decimal("100")
        return None
    except Exception as e:
        logger.warning(f"Could not get ACOS BE for ASIN {asin}: {e}")
        return None


DEFAULT_DELTA_CONFIG = {
    "delta_excellent": 0.05,
    "delta_good": 0.02,
    "delta_above_be": -0.02,
    "delta_high": -0.05,
    "delta_low_impressions": 0.01,
    "delta_no_sales": -0.02,
    "low_impressions_threshold": 100,
    "min_spend_for_decrement": 1.00,
    "max_clicks_no_sales": 10,
    "max_clicks_for_low_impressions": 0
}


def evaluate_target_with_book_acos(
    acos: Decimal,
    acos_be: Decimal,
    keyword_id: str,
    campaign_id: str,
    campaign_name: str,
    ad_group_id: str,
    keyword: str,
    asin: Optional[str],
    current_bid: Optional[Decimal],
    target_type: str,
    acos_30d: Optional[float],
    impressions_30d: int = 0,
    purchases_30d: int = 0,
    clicks_30d: int = 0,
    cost_30d: float = 0,
    sales_30d_val: float = 0,
    delta_config: Optional[Dict] = None
) -> Optional[Dict]:
    config = delta_config or DEFAULT_DELTA_CONFIG
    delta_excellent = Decimal(str(config.get("delta_excellent", 0.05)))
    delta_good = Decimal(str(config.get("delta_good", 0.02)))
    delta_above_be = Decimal(str(config.get("delta_above_be", -0.02)))
    delta_high = Decimal(str(config.get("delta_high", -0.05)))
    
    be_div_3 = acos_be / Decimal("3")
    be_div_1_5 = acos_be / Decimal("1.5")
    be_div_0_75 = acos_be / Decimal("0.75")
    
    if acos <= be_div_3:
        delta = delta_excellent
        tipo = f"INCREMENTO +{float(delta):.2f} (ACOS {float(acos)*100:.1f}% <= BE/3 {float(be_div_3)*100:.1f}%)"
        reason_code = "ACOS_EXCELLENT"
    elif acos <= be_div_1_5:
        delta = delta_good
        tipo = f"INCREMENTO +{float(delta):.2f} (BE/3 < ACOS {float(acos)*100:.1f}% <= BE/1.5 {float(be_div_1_5)*100:.1f}%)"
        reason_code = "ACOS_GOOD"
    elif acos <= acos_be:
        return None
    elif acos <= be_div_0_75:
        delta = delta_above_be
        tipo = f"DECREMENTO {float(delta):.2f} (BE < ACOS {float(acos)*100:.1f}% <= BE/0.75 {float(be_div_0_75)*100:.1f}%)"
        reason_code = "ACOS_ABOVE_BE"
    else:
        delta = delta_high
        tipo = f"DECREMENTO {float(delta):.2f} (ACOS {float(acos)*100:.1f}% > BE/0.75 {float(be_div_0_75)*100:.1f}%)"
        reason_code = "ACOS_TOO_HIGH"
    
    return {
        "keyword_id": keyword_id,
        "entity_id": keyword_id,
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "ad_group_id": ad_group_id,
        "keyword": keyword,
        "asin": asin,
        "current_bid": float(current_bid) if current_bid else None,
        "delta_bid": float(delta),
        "tipo_azione": tipo,
        "target_type": target_type,
        "acos_30d": acos_30d,
        "impressions_30d": impressions_30d,
        "purchases_30d": purchases_30d,
        "clicks_30d": clicks_30d,
        "spend_30d": cost_30d,
        "sales_30d": sales_30d_val,
        "acos_be": float(acos_be) * 100,
        "reason": reason_code
    }


def analyze_targets(report_30d: List[Dict], discovery_data: Dict[str, Dict], live_bids: Optional[Dict[str, Dict]] = None, profile_id: Optional[str] = None, delta_config: Optional[Dict] = None, targets_map: Optional[Dict[str, Dict]] = None, campaign_states_map: Optional[Dict[str, str]] = None, keywords_map: Optional[Dict[str, Dict]] = None) -> List[Dict]:
    """
    Analyze targets from 30D report and generate bid actions.
    
    Args:
        report_30d: 30-day report data
        discovery_data: Campaign discovery info (names, ASINs)
        live_bids: Dict of live bid data from API {target_id: {"bid": float, "targetType": str}}
        profile_id: Profile ID for book-specific ACOS BE lookup
        delta_config: Optional dict with configurable delta values
        targets_map: Map of targetId -> target metadata (keywordText, expression, etc.)
        campaign_states_map: Map of campaign_id -> state (ENABLED/PAUSED/ARCHIVED)
        keywords_map: Map of keywordId -> keyword data from Amazon API (for ghost target processing)
    """
    actions = []
    live_bids = live_bids or {}
    targets_map = targets_map or {}
    campaign_states_map = campaign_states_map or {}
    keywords_map = keywords_map or {}
    
    data_30d_by_keyword = {}
    target_types_30d = {}
    skipped_non_dict_30d = 0
    for row in report_30d:
        if not isinstance(row, dict):
            skipped_non_dict_30d += 1
            continue
        kw_id = row.get("keywordId")
        tgt_id = row.get("targetId")
        keyword_id = kw_id or tgt_id
        if keyword_id:
            keyword_id_str = str(keyword_id)
            data_30d_by_keyword[keyword_id_str] = row
            target_types_30d[keyword_id_str] = "keyword" if kw_id else "target"
    
    if skipped_non_dict_30d > 0:
        print(f"[ANALYZE_TARGETS] Skipped {skipped_non_dict_30d} non-dict rows in 30D data")
    
    processed_keywords = set()
    
    for keyword_id, row_30d in data_30d_by_keyword.items():
        if keyword_id in processed_keywords:
            continue
        
        processed_keywords.add(keyword_id)
        
        campaign_id = row_30d.get("campaignId")
        
        campaign_name = row_30d.get("campaignName") or ""
        ad_group_id = row_30d.get("adGroupId")
        keyword = row_30d.get("keyword") or row_30d.get("keywordText") or row_30d.get("target") or row_30d.get("targeting") or row_30d.get("targetingExpression") or ""
        
        clicks_30d = int(row_30d.get("clicks", 0) or 0)
        cost_30d = Decimal(str(row_30d.get("cost", 0) or 0))
        sales_30d = Decimal(str(row_30d.get("sales30d", 0) or row_30d.get("sales", 0) or 0))
        purchases_30d = int(row_30d.get("purchases30d", 0) or row_30d.get("purchases", 0) or 0)
        impressions_30d = int(row_30d.get("impressions", 0) or 0)
        
        discovery_info = discovery_data.get(str(campaign_id), {})
        discovered_campaign_name = discovery_info.get("campaign_name") or campaign_name
        asin = row_30d.get("advertisedAsin") or discovery_info.get("asin")
        
        live_bid_info = live_bids.get(str(keyword_id), {})
        current_bid = live_bid_info.get("bid") if live_bid_info else None
        if current_bid is not None:
            current_bid = Decimal(str(current_bid))
        
        target_type = target_types_30d.get(keyword_id, "keyword")
        
        action = evaluate_target(
            keyword_id=keyword_id,
            campaign_id=campaign_id,
            campaign_name=discovered_campaign_name,
            ad_group_id=ad_group_id,
            keyword=keyword,
            asin=asin,
            current_bid=current_bid,
            clicks_30d=clicks_30d,
            cost_30d=cost_30d,
            sales_30d=sales_30d,
            purchases_30d=purchases_30d,
            impressions_30d=impressions_30d,
            target_type=target_type,
            profile_id=profile_id,
            delta_config=delta_config
        )
        
        if action:
            actions.append(action)
    
    config = delta_config or DEFAULT_DELTA_CONFIG
    delta_low_impressions = Decimal(str(config.get("delta_low_impressions", 0.01)))
    ghost_count = 0
    
    for target_id, kw_info in keywords_map.items():
        if target_id in processed_keywords:
            continue
        
        if not target_id.isdigit():
            continue
        
        kw_state = kw_info.get("state", "").upper()
        if kw_state and kw_state != "ENABLED":
            continue
        
        current_bid = kw_info.get("bid")
        if current_bid is None:
            continue
        current_bid = Decimal(str(current_bid))
        
        target_meta = targets_map.get(target_id, {})
        keyword = kw_info.get("keyword") or target_meta.get("keywordText") or target_meta.get("expression") or target_meta.get("report_targeting") or ""
        campaign_id = kw_info.get("campaignId") or target_meta.get("campaignId") or ""
        ad_group_id = kw_info.get("adGroupId") or target_meta.get("adGroupId") or ""
        asin = target_meta.get("asin") or ""
        target_type = kw_info.get("entity_type", "keyword")
        
        target_ad_product = kw_info.get("ad_product", "SP")
        campaign_state = campaign_states_map.get(str(campaign_id), "").upper()
        if target_ad_product == "SP" and campaign_state != "ENABLED":
            continue
        
        discovery_info = discovery_data.get(str(campaign_id), {})
        campaign_name = discovery_info.get("campaign_name") or ""
        
        action = {
            "keyword_id": target_id,
            "entity_id": target_id,
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "ad_group_id": ad_group_id,
            "keyword": keyword,
            "asin": asin,
            "current_bid": float(current_bid),
            "delta_bid": float(delta_low_impressions),
            "tipo_azione": f"INCREMENTO +{float(delta_low_impressions):.2f} (0 impressioni - target non in report)",
            "target_type": target_type,
            "acos_30d": None,
            "impressions_30d": 0,
            "purchases_30d": 0,
            "clicks_30d": 0,
            "spend_30d": 0,
            "sales_30d": 0,
            "acos_be": None,
            "reason": "LOW_IMPRESSIONS"
        }
        actions.append(action)
        ghost_count += 1
    
    if ghost_count > 0:
        print(f"[ANALYZE_TARGETS DEBUG] Ghost targets: {ghost_count} actions created")
    
    return actions


def evaluate_target(
    keyword_id: str,
    campaign_id: str,
    campaign_name: str,
    ad_group_id: str,
    keyword: str,
    asin: Optional[str],
    current_bid: Optional[Decimal],
    clicks_30d: int,
    cost_30d: Decimal,
    sales_30d: Decimal,
    purchases_30d: int,
    impressions_30d: int = 0,
    target_type: str = "keyword",
    profile_id: Optional[str] = None,
    delta_config: Optional[Dict] = None
) -> Optional[Dict]:
    """
    Evaluate a target using 30D data and generate a bid action.
    
    REGOLE (in ordine di priorità):
    1. Se current_bid è None (non presente in live_bids), nessuna azione
    2. Se ci sono vendite (ACOS calcolabile), valuta per ACOS (ACOS ha priorità su impressioni)
    3. Se impressioni < soglia E no vendite → LOW_IMPRESSIONS (delta_low_impressions)
    4. Se no ACOS_BE (no libro associato), nessuna azione
    """
    if current_bid is None:
        return None
    
    config = delta_config or DEFAULT_DELTA_CONFIG
    low_impressions_threshold = int(config.get("low_impressions_threshold", 100))
    delta_low_impressions = Decimal(str(config.get("delta_low_impressions", 0.01)))
    max_clicks_no_sales = int(config.get("max_clicks_no_sales", 10))
    max_clicks_for_low_impressions = int(config.get("max_clicks_for_low_impressions", 0))
    pause_on_clicks_enabled = bool(config.get("pause_on_clicks_enabled", True))
    
    acos_30 = None
    
    if sales_30d > 0:
        acos_30 = cost_30d / sales_30d
    
    acos = acos_30
    
    if acos is None:
        if pause_on_clicks_enabled and max_clicks_no_sales > 0 and clicks_30d >= max_clicks_no_sales and purchases_30d == 0:
            return {
                "keyword_id": keyword_id,
                "entity_id": keyword_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "ad_group_id": ad_group_id,
                "keyword": keyword,
                "asin": asin,
                "current_bid": float(current_bid),
                "delta_bid": 0.0,
                "tipo_azione": f"PAUSA (clicks {clicks_30d} >= soglia {max_clicks_no_sales}, 0 vendite in 30D)",
                "target_type": target_type,
                "acos_30d": None,
                "acos_be": None,
                "impressions_30d": impressions_30d,
                "purchases_30d": purchases_30d,
                "clicks_30d": clicks_30d,
                "spend_30d": float(cost_30d),
                "sales_30d": float(sales_30d),
                "reason": "PAUSE_HIGH_CLICKS_NO_SALES"
            }
        if impressions_30d < low_impressions_threshold:
            clicks_ok = max_clicks_for_low_impressions == 0 or clicks_30d < max_clicks_for_low_impressions
            if clicks_ok:
                clicks_info = f", clicks {clicks_30d} < {max_clicks_for_low_impressions}" if max_clicks_for_low_impressions > 0 else ""
                return {
                    "keyword_id": keyword_id,
                    "entity_id": keyword_id,
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "ad_group_id": ad_group_id,
                    "keyword": keyword,
                    "asin": asin,
                    "current_bid": float(current_bid),
                    "delta_bid": float(delta_low_impressions),
                    "tipo_azione": f"INCREMENTO +{float(delta_low_impressions):.2f} (impressioni {impressions_30d} < soglia {low_impressions_threshold}{clicks_info})",
                    "target_type": target_type,
                    "acos_30d": None,
                    "acos_be": None,
                    "impressions_30d": impressions_30d,
                    "purchases_30d": purchases_30d,
                    "clicks_30d": clicks_30d,
                    "spend_30d": float(cost_30d),
                    "sales_30d": float(sales_30d),
                    "reason": "LOW_IMPRESSIONS"
                }
        delta_no_sales = Decimal(str(config.get("delta_no_sales", -0.02)))
        min_spend_for_decrement = Decimal(str(config.get("min_spend_for_decrement", 1.0)))
        if cost_30d >= min_spend_for_decrement and sales_30d == 0:
            return {
                "keyword_id": keyword_id,
                "entity_id": keyword_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "ad_group_id": ad_group_id,
                "keyword": keyword,
                "asin": asin,
                "current_bid": float(current_bid),
                "delta_bid": float(delta_no_sales),
                "tipo_azione": f"DECREMENTO {float(delta_no_sales):+.2f} (spesa {float(cost_30d):.2f} senza vendite, {impressions_30d} imp, {clicks_30d} clicks)",
                "target_type": target_type,
                "acos_30d": None,
                "acos_be": None,
                "impressions_30d": impressions_30d,
                "purchases_30d": purchases_30d,
                "clicks_30d": clicks_30d,
                "spend_30d": float(cost_30d),
                "sales_30d": float(sales_30d),
                "reason": "NO_SALES_HIGH_SPEND"
            }
        return None
    
    acos_be = None
    if asin:
        acos_be = get_book_acos_be(asin, profile_id)
    
    if acos_be is None:
        return None
    
    return evaluate_target_with_book_acos(
        acos=acos,
        acos_be=acos_be,
        keyword_id=keyword_id,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        ad_group_id=ad_group_id,
        keyword=keyword,
        asin=asin,
        current_bid=current_bid,
        target_type=target_type,
        acos_30d=float(acos_30) if acos_30 is not None else None,
        impressions_30d=impressions_30d,
        purchases_30d=purchases_30d,
        clicks_30d=clicks_30d,
        cost_30d=float(cost_30d),
        sales_30d_val=float(sales_30d),
        delta_config=delta_config
    )


def _resolve_target_id(
    row: Dict, 
    campaign_id: str, 
    ad_group_id: str, 
    targeting_to_id_map: Dict[str, str],
    ad_product: str = "SP",
    targets_map: Dict[str, Dict] = None
) -> Tuple[Optional[str], str]:
    """
    Resolve targeting expression to targetId.
    
    CRITERI SP:
    - KEYWORD: usa keywordId diretto dal report SOLO se appartiene alla campagna corretta
    - ASIN: chiave composita campaign_adgroup_asin=B...
    - CATEGORY: chiave composita campaign_adgroup_category=Nome
    - AUTO: chiave composita campaign_adgroup_matchtype (close-match, etc)
    
    CRITERI SB:
    - KEYWORD/ASIN: usa targetingId direttamente dal report
    - CATEGORY: usa match descrittivo dalla mappa
    
    Returns:
        (resolved_id, target_type) tuple
    """
    kw_id = row.get("keywordId")
    tgt_id = row.get("targetId")
    targeting_id = row.get("targetingId")
    targeting_raw = row.get("targeting", "") or row.get("targetingExpression", "")
    targets_map = targets_map or {}
    
    # ========== SP ==========
    if ad_product == "SP":
        target_type = _classify_target_type(targeting_raw, row)
        
        # Only use keywordId if it's actually a keyword, NOT a product target
        # Amazon reports sometimes have keywordId on product targets - ignore it
        # IMPORTANTE: verificare che keywordId appartenga alla campagna corretta
        # NON fidarsi di keywordId se non è validabile tramite targets_map
        if kw_id and target_type == "keyword":
            kw_id_str = str(kw_id)
            if kw_id_str in targets_map:
                target_campaign_id = str(targets_map[kw_id_str].get("campaignId", ""))
                if target_campaign_id == campaign_id:
                    return kw_id_str, "keyword"
                else:
                    print(f"[RESOLVE_DEBUG] keywordId {kw_id_str} belongs to campaign {target_campaign_id}, not {campaign_id}. Using composite key fallback.")
                    # NON return qui - fallback alla chiave composita sotto
            else:
                print(f"[RESOLVE_DEBUG] keywordId {kw_id_str} not found in targets_map. Using composite key fallback.")
                # NON return qui - fallback alla chiave composita sotto
        
        if tgt_id:
            return str(tgt_id), target_type
        
        if not targeting_raw:
            return None, "unknown"
        
        # KEYWORD SP: se non c'è keywordId, cerca nella mappa con chiave composita poi fallback semplice
        if target_type == "keyword":
            kw_text_lower = targeting_raw.lower().strip()
            composite_key = f"{campaign_id}_{ad_group_id}_kw={kw_text_lower}"
            if composite_key in targeting_to_id_map:
                return targeting_to_id_map[composite_key], "keyword"
            # FALLBACK: usa chiave semplice SOLO se il keyword_id risolto appartiene alla campagna corrente
            if kw_text_lower in targeting_to_id_map:
                candidate_id = targeting_to_id_map[kw_text_lower]
                if str(candidate_id) in targets_map:
                    candidate_campaign = str(targets_map[str(candidate_id)].get("campaignId", ""))
                    if candidate_campaign == campaign_id:
                        return candidate_id, "keyword"
                    # Se la campagna non corrisponde, NON usare questo ID - logga e skip
                    # Non stampare per evitare spam, la riga verrà saltata
                else:
                    # Se non è in targets_map, non possiamo verificare - skip per sicurezza
                    pass
        
        targeting_lower = targeting_raw.lower().strip()
        
        if targeting_lower in AUTO_TOKENS:
            composite_key = f"{campaign_id}_{ad_group_id}_{targeting_lower}"
            if composite_key in targeting_to_id_map:
                return targeting_to_id_map[composite_key], "auto_target"
            else:
                available_auto_keys = [k for k in targeting_to_id_map.keys() if k.startswith(f"{campaign_id}_{ad_group_id}_") and not k.startswith(f"{campaign_id}_{ad_group_id}_asin=") and not k.startswith(f"{campaign_id}_{ad_group_id}_kw=") and not k.startswith(f"{campaign_id}_{ad_group_id}_category=")][:5]
                print(f"[SP_RESOLVE_DEBUG] AUTO not found: key='{composite_key}', available_auto_keys={available_auto_keys}")
        
        if 'asin="' in targeting_lower or 'asin="' in targeting_raw:
            import re
            asin_match = re.search(r'asin=["\']?([A-Z0-9]{10})["\']?', targeting_raw, re.IGNORECASE)
            if asin_match:
                asin = asin_match.group(1).upper()
                composite_key = f"{campaign_id}_{ad_group_id}_asin={asin}"
                if composite_key in targeting_to_id_map:
                    return targeting_to_id_map[composite_key], "product_target"
                else:
                    matching_keys = [k for k in targeting_to_id_map.keys() if k.startswith(f"{campaign_id}_{ad_group_id}_asin=")][:3]
                    print(f"[SP_RESOLVE_DEBUG] ASIN not found: key='{composite_key}', available_asin_keys={matching_keys}")
        
        # Bare ASIN/ISBN detection: B0/B1 prefix OR 10-char alphanumeric (for numeric ISBNs)
        targeting_stripped = targeting_raw.strip()
        if len(targeting_stripped) == 10 and targeting_stripped.isalnum():
            asin = targeting_stripped.upper()
            composite_key = f"{campaign_id}_{ad_group_id}_asin={asin}"
            if composite_key in targeting_to_id_map:
                return targeting_to_id_map[composite_key], "product_target"
        
        if 'category="' in targeting_lower or 'category="' in targeting_raw:
            import re
            cat_match = re.search(r'category=["\']?([^"\']+)["\']?', targeting_raw, re.IGNORECASE)
            if cat_match:
                category_name = cat_match.group(1).strip()
                category_normalized = ' '.join(category_name.split()).lower()
                composite_key = f"{campaign_id}_{ad_group_id}_category={category_normalized}"
                if composite_key in targeting_to_id_map:
                    return targeting_to_id_map[composite_key], "category_target"
                else:
                    matching_keys = [k for k in targeting_to_id_map.keys() if k.startswith(f"{campaign_id}_{ad_group_id}_category=")][:5]
                    print(f"[SP_RESOLVE_DEBUG] CATEGORY not found: key='{composite_key}', available_category_keys={matching_keys}")
        
        if target_type not in ("keyword", "unknown"):
            print(f"[SP_RESOLVE_DEBUG] Unresolved SP target: type={target_type}, targeting='{targeting_raw[:50]}', cid={campaign_id}, agid={ad_group_id}")
        
        return None, target_type
    
    # ========== SB ==========
    if ad_product == "SB":
        target_type = _classify_target_type(targeting_raw, row)
        
        if kw_id:
            return str(kw_id), "keyword"
        
        if targeting_id:
            return str(targeting_id), target_type if target_type != "unknown" else "product_target"
        
        if tgt_id:
            return str(tgt_id), target_type if target_type != "unknown" else "product_target"
        
        keyword_text = row.get("keywordText", "") or row.get("keyword", "")
        match_type = row.get("matchType", "")
        if target_type == "keyword" and keyword_text and match_type:
            composite_key = f"{campaign_id}:{ad_group_id}:kw:{keyword_text.lower().strip()}:{match_type.lower()}"
            if composite_key in targeting_to_id_map:
                return targeting_to_id_map[composite_key], "keyword"
        
        if target_type in ("product_target", "category_target") and targeting_raw:
            normalized = normalize_expr(targeting_raw).lower() if targeting_raw else ""
            composite_key = f"{campaign_id}:{ad_group_id}:target:{normalized}"
            if composite_key in targeting_to_id_map:
                return targeting_to_id_map[composite_key], target_type
            print(f"[SB_RESOLVE_DEBUG] Composite key NOT found: '{composite_key}', targeting_raw='{targeting_raw}'")
        
        return None, target_type
    
    return None, "unknown"


def _classify_target_type(targeting: str, row: Dict = None) -> str:
    """
    Classify targeting expression into target_type.
    
    Logic:
    - AUTO tokens (close-match, loose-match, etc.) -> auto_target
    - asin=... or starts with B0/B1 -> product_target
    - category=... -> category_target
    - Pure text (like "clinical pathophysiology") -> keyword (if row has matchType or no special patterns)
    """
    if not targeting:
        if row and row.get("matchType"):
            return "keyword"
        return "product_target"
    
    targeting_lower = targeting.lower().strip()
    
    if targeting_lower in AUTO_TOKENS:
        return "auto_target"
    
    if "asin=" in targeting_lower or targeting_lower.startswith("asin"):
        return "product_target"
    
    # Bare ASIN/ISBN: B0/B1 prefix OR any 10-char alphanumeric (for numeric ISBNs like 1264278489)
    targeting_stripped = targeting.strip()
    if len(targeting_stripped) == 10 and targeting_stripped.isalnum():
        return "product_target"
    
    if "category=" in targeting_lower or targeting_lower.startswith("category"):
        return "category_target"
    
    if row and row.get("matchType"):
        return "keyword"
    
    if not any(c in targeting for c in ['=', '"', '(', ')']):
        return "keyword"
    
    return "product_target"


def analyze(
    profile_id: str,
    report_30_data: List[Dict],
    asin_to_acos_be_map: Dict[str, float],
    discovery_data: Dict[str, Dict] = None,
    live_bids: Dict[str, Dict] = None,
    targeting_to_id_map: Dict[str, str] = None,
    ad_product: str = "SP",
    targets_map: Dict[str, Dict] = None,
    delta_config: Dict = None,
    campaign_states_map: Dict[str, str] = None
) -> List[Dict]:
    """
    PURE analysis function - no DB queries, no API calls.
    All analysis based exclusively on 30-day report data.
    
    Args:
        profile_id: Profile ID for the run
        report_30_data: 30-day report data rows
        asin_to_acos_be_map: Pre-loaded map of ASIN -> ACOS BE (as decimal, e.g. 0.35)
        discovery_data: Optional campaign discovery info {campaign_id: {campaign_name, asin}}
        live_bids: Optional dict of live bid data {target_id: {"bid": float, "targetType": str}}
        targeting_to_id_map: Map of targeting expressions to targetIds for resolution
        ad_product: "SP" or "SB" - determines ID resolution priority
        targets_map: Map of targetId -> target metadata (report_targeting, expression, etc.)
        campaign_states_map: Map of campaign_id -> state (ENABLED/PAUSED/ARCHIVED), skip PAUSED campaigns
    
    Returns:
        List of action dicts ready to be inserted as planned_actions
    """
    actions = []
    discovery_data = discovery_data or {}
    live_bids = live_bids or {}
    targeting_to_id_map = targeting_to_id_map or {}
    targets_map = targets_map or {}
    campaign_states_map = campaign_states_map or {}
    
    stats = {
        "total_targets": 0,
        "no_acos": 0,
        "with_acos_be": 0,
        "acos_in_optimal_band": 0,
        "low_impressions": 0,
        "actions_generated": 0,
        "unresolved": 0
    }
    
    print(f"[ANALYZE_DEBUG] targeting_to_id_map has {len(targeting_to_id_map)} keys")
    print(f"[ANALYZE_DEBUG] live_bids has {len(live_bids)} entries")
    print(f"[ANALYZE_DEBUG] targets_map has {len(targets_map)} entries")
    
    data_30d_by_keyword = {}
    target_types_30d = {}
    resolved_30d_counts = {"keyword": 0, "product_target": 0, "auto_target": 0, "category_target": 0, "unknown": 0}
    unresolved_30d_counts = {"keyword": 0, "product_target": 0, "auto_target": 0, "category_target": 0, "unknown": 0}
    unresolved_30d_samples = []
    
    auto_30d_raw_samples = []
    skipped_non_dict_rows = 0
    for row in report_30_data:
        # Skip non-dict rows (defensive check for malformed data)
        if not isinstance(row, dict):
            skipped_non_dict_rows += 1
            continue
        campaign_id = str(row.get("campaignId", ""))
        ad_group_id = str(row.get("adGroupId", ""))
        targeting_raw = row.get("targeting", "") or row.get("targetingExpression", "")
        
        if targeting_raw and targeting_raw.lower().strip() in AUTO_TOKENS and len(auto_30d_raw_samples) < 5:
            auto_30d_raw_samples.append({
                "targeting_raw": targeting_raw,
                "cid": campaign_id,
                "agid": ad_group_id,
                "purchases30d": row.get("purchases30d"),
                "sales30d": row.get("sales30d")
            })
        
        keyword_id, target_type = _resolve_target_id(row, campaign_id, ad_group_id, targeting_to_id_map, ad_product, targets_map)
        if keyword_id:
            keyword_id_str = str(keyword_id)
            data_30d_by_keyword[keyword_id_str] = row
            target_types_30d[keyword_id_str] = target_type
            resolved_30d_counts[target_type] = resolved_30d_counts.get(target_type, 0) + 1
        else:
            unresolved_30d_counts[target_type] = unresolved_30d_counts.get(target_type, 0) + 1
            if target_type in ("auto_target", "category_target") and len(unresolved_30d_samples) < 10:
                unresolved_30d_samples.append({
                    "type": target_type,
                    "targeting": targeting_raw[:60] if targeting_raw else "",
                    "cid": campaign_id,
                    "agid": ad_group_id
                })
    
    if auto_30d_raw_samples:
        print(f"[30D_AUTO_RAW] Sample AUTO rows from 30D report: {auto_30d_raw_samples}")
    
    print(f"[30D_RESOLVE] Resolved: {resolved_30d_counts}")
    print(f"[30D_RESOLVE] Unresolved: {unresolved_30d_counts}")
    if skipped_non_dict_rows > 0:
        print(f"[30D_WARN] Skipped {skipped_non_dict_rows} non-dict rows in 30D data")
    if unresolved_30d_samples:
        print(f"[30D_RESOLVE] Unresolved AUTO/CATEGORY samples: {unresolved_30d_samples[:5]}")
        for sample in unresolved_30d_samples[:3]:
            expected_key = f"{sample['cid']}_{sample['agid']}_{sample['targeting'].lower().strip()}"
            key_exists = expected_key in targeting_to_id_map
            print(f"[30D_DEBUG] Sample: targeting='{sample['targeting']}' -> expected_key='{expected_key}' -> exists={key_exists}")
    
    processed_keywords = set()
    skipped_paused_campaigns = 0

    for keyword_id, row_30d in data_30d_by_keyword.items():
        if keyword_id in processed_keywords:
            continue
        
        processed_keywords.add(keyword_id)
        
        if keyword_id and str(keyword_id) in targets_map:
            target_meta = targets_map[str(keyword_id)]
            campaign_id = str(target_meta.get("campaignId", row_30d.get("campaignId", "")))
            ad_group_id = str(target_meta.get("adGroupId", row_30d.get("adGroupId", "")))
            discovery_info_corrected = discovery_data.get(campaign_id, {})
            campaign_name = discovery_info_corrected.get("campaign_name") or row_30d.get("campaignName") or ""
        else:
            campaign_id = str(row_30d.get("campaignId", ""))
            campaign_name = row_30d.get("campaignName") or ""
            ad_group_id = row_30d.get("adGroupId")
        
        campaign_state = campaign_states_map.get(campaign_id, "").upper()
        if campaign_state and campaign_state != "ENABLED":
            skipped_paused_campaigns += 1
            continue
        
        live_bid_info = live_bids.get(str(keyword_id), {})
        if not live_bid_info:
            stats["unresolved"] = stats.get("unresolved", 0) + 1
            continue
        
        current_bid = live_bid_info.get("bid")
        if current_bid is not None:
            current_bid = Decimal(str(current_bid))
        
        raw_keyword = row_30d.get("keyword") or row_30d.get("keywordText") or row_30d.get("target") or row_30d.get("targeting") or row_30d.get("targetingExpression") or ""
        
        if (not raw_keyword or raw_keyword.isdigit()) and keyword_id and keyword_id in targets_map:
            target_meta = targets_map[keyword_id]
            raw_keyword = target_meta.get("report_targeting") or target_meta.get("expression") or target_meta.get("keywordText") or raw_keyword
        
        target_type = target_types_30d.get(keyword_id, "keyword")
        
        if target_type == "keyword":
            keyword = raw_keyword
        else:
            keyword = normalize_display_keyword(raw_keyword, target_type)
        
        clicks_30d = int(row_30d.get("clicks", 0) or 0)
        cost_30d = Decimal(str(row_30d.get("cost", 0) or 0))
        sales_30d = Decimal(str(row_30d.get("sales30d", 0) or row_30d.get("sales", 0) or 0))
        purchases_30d = int(row_30d.get("purchases30d", 0) or row_30d.get("purchases", 0) or 0)
        impressions_30d = int(row_30d.get("impressions", 0) or 0)
        
        discovery_info = discovery_data.get(str(campaign_id), {})
        discovered_campaign_name = discovery_info.get("campaign_name") or campaign_name
        asin = row_30d.get("advertisedAsin") or discovery_info.get("asin")
        
        action = _evaluate_target_pure(
            keyword_id=keyword_id,
            campaign_id=campaign_id,
            campaign_name=discovered_campaign_name,
            ad_group_id=ad_group_id,
            keyword=keyword,
            asin=asin,
            current_bid=current_bid,
            clicks_30d=clicks_30d,
            cost_30d=cost_30d,
            sales_30d=sales_30d,
            purchases_30d=purchases_30d,
            impressions_30d=impressions_30d,
            target_type=target_type,
            asin_to_acos_be_map=asin_to_acos_be_map,
            delta_config=delta_config
        )
        
        if action:
            actions.append(action)
    
    if skipped_paused_campaigns > 0:
        print(f"[ANALYZER] Skipped {skipped_paused_campaigns} targets from PAUSED/ARCHIVED campaigns")
    
    keyword_actions = len([a for a in actions if a.get('target_type') == 'keyword'])
    product_actions = len([a for a in actions if a.get('target_type') == 'product_target'])
    auto_actions = len([a for a in actions if a.get('target_type') == 'auto_target'])
    print(f"[ANALYZER] Actions from 30D data: {keyword_actions} keywords, {product_actions} product_targets, {auto_actions} auto_targets")
    
    print(f"[ANALYZE DEBUG] Profile {profile_id}: total_targets={len(processed_keywords)}, report_30d={len(report_30_data)}, actions={len(actions)}")
    if len(report_30_data) > 0:
        sample = report_30_data[0]
        if isinstance(sample, dict):
            print(f"[ANALYZE DEBUG] Sample 30D row keys: {list(sample.keys())[:10]}")
            print(f"[ANALYZE DEBUG] Sample impressions: {sample.get('impressions')}")
        else:
            print(f"[ANALYZE DEBUG] Sample 30D row is not a dict, type: {type(sample)}")
    
    # GHOST TARGETS: Target attivi (in live_bids) ma non presenti nei report (0 impressioni)
    # Filtra solo ID numerici reali (non chiavi stringa ausiliarie come keyword text)
    ghost_count = 0
    ghost_skipped = 0
    for target_id, live_info in live_bids.items():
        # Skip se già processato
        if target_id in processed_keywords:
            continue
        
        # Skip chiavi stringa ausiliarie (keyword text, espressioni, etc.)
        # I veri target ID sono numeri o stringhe numeriche
        if not target_id.isdigit():
            continue
        
        current_bid = live_info.get("bid")
        if current_bid is None:
            continue
        current_bid = Decimal(str(current_bid))
        
        # Skip if this target belongs to a different ad_product
        target_ad_product = live_info.get("ad_product", "SP")
        if target_ad_product != ad_product:
            continue
        
        # Determina target_type dalla live_info se disponibile
        target_type = live_info.get("targetType", "keyword")
        if target_type not in ["keyword", "product_target", "auto_target", "category_target"]:
            target_type = "keyword"
        
        # Recupera info dalla mappa targets se disponibile, o da live_info per keyword
        target_meta = targets_map.get(target_id, {})
        keyword = live_info.get("keywordText") or target_meta.get("keywordText") or target_meta.get("expression") or target_meta.get("report_targeting") or ""
        campaign_id = target_meta.get("campaignId") or live_info.get("campaignId") or ""
        ad_group_id = target_meta.get("adGroupId") or live_info.get("adGroupId") or ""
        asin = target_meta.get("asin") or ""
        
        campaign_state = campaign_states_map.get(str(campaign_id), "").upper()
        if campaign_state and campaign_state != "ENABLED":
            ghost_skipped += 1
            continue
        
        # Recupera campaign_name dal discovery
        discovery_info = discovery_data.get(str(campaign_id), {})
        campaign_name = discovery_info.get("campaign_name") or ""
        
        # Usa delta_config se disponibile
        config = delta_config or DEFAULT_DELTA_CONFIG
        delta_low_impressions = Decimal(str(config.get("delta_low_impressions", 0.01)))
        
        action = {
            "keyword_id": target_id,
            "entity_id": target_id,
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "ad_group_id": ad_group_id,
            "keyword": keyword,
            "asin": asin,
            "current_bid": float(current_bid),
            "delta_bid": float(delta_low_impressions),
            "tipo_azione": f"INCREMENTO +{float(delta_low_impressions):.2f} (0 impressioni - target non in report)",
            "target_type": target_type,
            "acos_30d": None,
            "impressions_30d": 0,
            "purchases_30d": 0,
            "clicks_30d": 0,
            "spend_30d": 0,
            "sales_30d": 0,
            "acos_be": None,
            "reason": "LOW_IMPRESSIONS"
        }
        actions.append(action)
        ghost_count += 1
    
    ghost_no_campaign = sum(1 for a in actions[-ghost_count:] if not a.get("campaign_id")) if ghost_count > 0 else 0
    ghost_no_adgroup = sum(1 for a in actions[-ghost_count:] if not a.get("ad_group_id")) if ghost_count > 0 else 0
    ghost_no_name = sum(1 for a in actions[-ghost_count:] if not a.get("campaign_name")) if ghost_count > 0 else 0
    
    if ghost_count > 0 or ghost_skipped > 0:
        print(f"[ANALYZE DEBUG] Ghost targets: {ghost_count} actions created, {ghost_skipped} skipped (non-ENABLED)")
        if ghost_count > 0:
            print(f"[ANALYZE DEBUG] Ghost data quality: {ghost_no_campaign} missing campaign_id, {ghost_no_adgroup} missing ad_group_id, {ghost_no_name} missing campaign_name")
            sample_ghost = actions[-1]
            print(f"[ANALYZE DEBUG] Sample ghost: id={sample_ghost.get('keyword_id')}, campaign_id={sample_ghost.get('campaign_id')}, ad_group_id={sample_ghost.get('ad_group_id')}, campaign_name={sample_ghost.get('campaign_name')}, target_type={sample_ghost.get('target_type')}")
    
    return actions


def _evaluate_target_pure(
    keyword_id: str,
    campaign_id: str,
    campaign_name: str,
    ad_group_id: str,
    keyword: str,
    asin: Optional[str],
    current_bid: Optional[Decimal],
    clicks_30d: int,
    cost_30d: Decimal,
    sales_30d: Decimal,
    purchases_30d: int,
    impressions_30d: int,
    target_type: str,
    asin_to_acos_be_map: Dict[str, float],
    delta_config: Dict = None
) -> Optional[Dict]:
    """
    Pure evaluation based exclusively on 30D data.
    
    GERARCHIA REGOLE:
    1. Se ci sono vendite (ACOS calcolabile), valuta per ACOS
    2. Se NON ci sono vendite E clicks >= soglia → PAUSA (priorità su LOW_IMPRESSIONS)
    3. Se NON ci sono vendite E impressioni < soglia → LOW_IMPRESSIONS
    4. Con ACOS_BE: valuta fasce BE/3, BE/1.5, BE, BE/0.75
    5. Senza ACOS_BE: soglie fisse ACOS_LOW/HIGH
    """
    config = delta_config or DEFAULT_DELTA_CONFIG
    low_impressions_threshold = int(config.get("low_impressions_threshold", 100))
    delta_low_impressions = Decimal(str(config.get("delta_low_impressions", 0.01)))
    delta_excellent = Decimal(str(config.get("delta_excellent", 0.05)))
    delta_good = Decimal(str(config.get("delta_good", 0.02)))
    delta_above_be = Decimal(str(config.get("delta_above_be", -0.02)))
    delta_high = Decimal(str(config.get("delta_high", -0.05)))
    delta_no_sales = Decimal(str(config.get("delta_no_sales", -0.02)))
    min_spend_for_decrement = Decimal(str(config.get("min_spend_for_decrement", 1.0)))
    
    acos_30 = None
    if sales_30d > 0:
        acos_30 = cost_30d / sales_30d
    
    acos_be = get_acos_be_from_map(asin, asin_to_acos_be_map) if asin else None
    
    max_clicks_no_sales = int(config.get("max_clicks_no_sales", 10))
    max_clicks_for_low_impressions = int(config.get("max_clicks_for_low_impressions", 0))
    pause_on_clicks_enabled = bool(config.get("pause_on_clicks_enabled", True))
    
    if acos_30 is None:
        if pause_on_clicks_enabled and max_clicks_no_sales > 0 and clicks_30d >= max_clicks_no_sales and purchases_30d == 0:
            return {
                "keyword_id": keyword_id,
                "entity_id": keyword_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "ad_group_id": ad_group_id,
                "keyword": keyword,
                "asin": asin,
                "current_bid": float(current_bid) if current_bid else None,
                "delta_bid": 0.0,
                "tipo_azione": f"PAUSA (clicks {clicks_30d} >= soglia {max_clicks_no_sales}, 0 vendite in 30D)",
                "target_type": target_type,
                "acos_30d": None,
                "impressions_30d": impressions_30d,
                "purchases_30d": purchases_30d,
                "clicks_30d": clicks_30d,
                "spend_30d": float(cost_30d),
                "sales_30d": float(sales_30d),
                "acos_be": float(acos_be) * 100 if acos_be is not None else None,
                "reason": "PAUSE_HIGH_CLICKS_NO_SALES"
            }
        if impressions_30d < low_impressions_threshold:
            clicks_ok = max_clicks_for_low_impressions == 0 or clicks_30d < max_clicks_for_low_impressions
            if clicks_ok:
                clicks_info = f", clicks {clicks_30d} < {max_clicks_for_low_impressions}" if max_clicks_for_low_impressions > 0 else ""
                return {
                    "keyword_id": keyword_id,
                    "entity_id": keyword_id,
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                    "ad_group_id": ad_group_id,
                    "keyword": keyword,
                    "asin": asin,
                    "current_bid": float(current_bid) if current_bid else None,
                    "delta_bid": float(delta_low_impressions),
                    "tipo_azione": f"INCREMENTO +{float(delta_low_impressions):.2f} (impressioni {impressions_30d} < soglia {low_impressions_threshold}{clicks_info})",
                    "target_type": target_type,
                    "acos_30d": None,
                    "impressions_30d": impressions_30d,
                    "purchases_30d": purchases_30d,
                    "clicks_30d": clicks_30d,
                    "spend_30d": float(cost_30d),
                    "sales_30d": float(sales_30d),
                    "acos_be": float(acos_be) * 100 if acos_be is not None else None,
                    "reason": "LOW_IMPRESSIONS"
                }
        if cost_30d >= min_spend_for_decrement and sales_30d == 0:
            return {
                "keyword_id": keyword_id,
                "entity_id": keyword_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "ad_group_id": ad_group_id,
                "keyword": keyword,
                "asin": asin,
                "current_bid": float(current_bid) if current_bid else None,
                "delta_bid": float(delta_no_sales),
                "tipo_azione": f"DECREMENTO {float(delta_no_sales):+.2f} (spesa {float(cost_30d):.2f} senza vendite, {impressions_30d} imp, {clicks_30d} clicks)",
                "target_type": target_type,
                "acos_30d": None,
                "impressions_30d": impressions_30d,
                "purchases_30d": purchases_30d,
                "clicks_30d": clicks_30d,
                "spend_30d": float(cost_30d),
                "sales_30d": float(sales_30d),
                "acos_be": float(acos_be) * 100 if acos_be is not None else None,
                "reason": "NO_SALES_HIGH_SPEND"
            }
        return None
    
    if acos_be is None:
        if cost_30d >= min_spend_for_decrement and sales_30d == 0:
            return {
                "keyword_id": keyword_id,
                "entity_id": keyword_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "ad_group_id": ad_group_id,
                "keyword": keyword,
                "asin": asin,
                "current_bid": float(current_bid) if current_bid else None,
                "delta_bid": float(delta_no_sales),
                "tipo_azione": f"DECREMENTO {float(delta_no_sales):+.2f} (spesa ${float(cost_30d):.2f} senza vendite)",
                "target_type": target_type,
                "acos_30d": float(acos_30) if acos_30 is not None else None,
                "impressions_30d": impressions_30d,
                "purchases_30d": purchases_30d,
                "clicks_30d": clicks_30d,
                "spend_30d": float(cost_30d),
                "sales_30d": float(sales_30d),
                "acos_be": None,
                "reason": "NO_SALES_HIGH_SPEND"
            }
        
        high_acos_threshold = Decimal("0.50")
        if acos_30 is not None and acos_30 > high_acos_threshold:
            return {
                "keyword_id": keyword_id,
                "entity_id": keyword_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "ad_group_id": ad_group_id,
                "keyword": keyword,
                "asin": asin,
                "current_bid": float(current_bid) if current_bid else None,
                "delta_bid": float(delta_high),
                "tipo_azione": f"DECREMENTO {float(delta_high):+.2f} (ACOS {float(acos_30)*100:.1f}% > 50%)",
                "target_type": target_type,
                "acos_30d": float(acos_30),
                "impressions_30d": impressions_30d,
                "purchases_30d": purchases_30d,
                "clicks_30d": clicks_30d,
                "spend_30d": float(cost_30d),
                "sales_30d": float(sales_30d),
                "acos_be": None,
                "reason": "ACOS_HIGH_NO_BE"
            }
    
    if acos_be is not None:
        delta, tipo_azione, reason_code = _evaluate_with_acos_be_30d(acos_30, acos_be, delta_excellent, delta_good, delta_above_be, delta_high)
    else:
        delta, tipo_azione, reason_code = _evaluate_without_acos_be_30d(acos_30, delta_good, delta_above_be)
    
    if delta is None or delta == 0 or tipo_azione is None:
        return None
    
    return {
        "keyword_id": keyword_id,
        "entity_id": keyword_id,
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "ad_group_id": ad_group_id,
        "keyword": keyword,
        "asin": asin,
        "current_bid": float(current_bid) if current_bid else None,
        "delta_bid": float(delta),
        "tipo_azione": tipo_azione,
        "target_type": target_type,
        "acos_30d": float(acos_30) if acos_30 is not None else None,
        "impressions_30d": impressions_30d,
        "purchases_30d": purchases_30d,
        "clicks_30d": clicks_30d,
        "spend_30d": float(cost_30d),
        "sales_30d": float(sales_30d),
        "acos_be": float(acos_be) * 100 if acos_be is not None else None,
        "reason": reason_code
    }


def _evaluate_with_acos_be_30d(acos_val, acos_be, delta_excellent, delta_good, delta_above_be, delta_high):
    if acos_val is None or acos_be is None:
        return None, None, None
    be_div_3 = acos_be / Decimal("3")
    be_div_1_5 = acos_be / Decimal("1.5")
    be_div_0_75 = acos_be / Decimal("0.75")
    
    if acos_val <= be_div_3:
        return delta_excellent, f"INCREMENTO {float(delta_excellent):+.2f} 30D (ACOS {float(acos_val)*100:.1f}% <= BE/3)", "ACOS_EXCELLENT"
    elif acos_val <= be_div_1_5:
        return delta_good, f"INCREMENTO {float(delta_good):+.2f} 30D (ACOS {float(acos_val)*100:.1f}% <= BE/1.5)", "ACOS_GOOD"
    elif acos_val <= acos_be:
        return Decimal("0"), None, None
    elif acos_val <= be_div_0_75:
        return delta_above_be, f"DECREMENTO {float(delta_above_be):+.2f} 30D (ACOS {float(acos_val)*100:.1f}% > BE)", "ACOS_ABOVE_BE"
    else:
        return delta_high, f"DECREMENTO {float(delta_high):+.2f} 30D (ACOS {float(acos_val)*100:.1f}% > BE/0.75)", "ACOS_TOO_HIGH"


def _evaluate_without_acos_be_30d(acos_val, delta_good, delta_above_be):
    if acos_val is None:
        return None, None, None
    if acos_val < ACOS_LOW_THRESHOLD:
        return delta_good, f"INCREMENTO {float(delta_good):+.2f} 30D (ACOS {float(acos_val)*100:.1f}% < {float(ACOS_LOW_THRESHOLD)*100}%)", "ACOS_LOW_NO_BE"
    elif acos_val > ACOS_HIGH_THRESHOLD:
        return delta_above_be, f"DECREMENTO {float(delta_above_be):+.2f} 30D (ACOS {float(acos_val)*100:.1f}% > {float(ACOS_HIGH_THRESHOLD)*100}%)", "ACOS_HIGH_NO_BE"
    else:
        return Decimal("0"), None, None
