import asyncio
import re
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional, Set, Dict, Any, Tuple
from sqlalchemy.orm import Session
from backend.app.models.extractor import ExtractionJob, ExtractedAsin, ExtractedKeyword, ExtractorApiLog
from backend.app.services.extractor_clients import oxylabs_client, canopy_client, amazon_autocomplete

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "it", "its", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "what", "which", "who", "whom", "whose",
    "when", "where", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "also",
    "pack", "count", "oz", "lb", "lbs", "mg", "g", "kg", "ml", "fl",
    "size", "new", "free", "amazon", "prime",
}

MAX_OXY_SERP_CALLS = 24
MAX_OXY_PRODUCT_CALLS = 12
TARGET_MIN = 500
TARGET_MAX = 1000
MAX_SERP_PAGE = 2

MAX_AUTOCOMPLETE_L1 = 10
MAX_AUTOCOMPLETE_L2 = 50

cancelled_jobs: Set[str] = set()


def cancel_extraction(job_id: str):
    cancelled_jobs.add(job_id)


def is_cancelled(job_id: str) -> bool:
    return job_id in cancelled_jobs


def clear_cancellation(job_id: str):
    cancelled_jobs.discard(job_id)


def detect_format(title: str, binding: Optional[str] = None) -> Optional[str]:
    lower_title = title.lower()
    lower_binding = (binding or "").lower()

    if "paperback" in lower_binding or "paperback" in lower_title:
        return "paperback"
    if "hardcover" in lower_binding or "hardcover" in lower_title:
        return "hardcover"
    if "kindle" in lower_binding or "kindle" in lower_title:
        return "kindle"
    if "audiobook" in lower_binding or "audiobook" in lower_title or "audible" in lower_title:
        return "audiobook"
    return None


async def _serp_round_robin(
    seed_keywords: List[str],
    category_id: Optional[str],
    include_merch: bool,
    job_id: str,
    db: Session,
    job: ExtractionJob,
    write_progress: bool = True,
    progress_start: int = 0,
    progress_end: int = 50,
) -> Tuple[Dict[str, dict], List[str]]:
    """
    Oxylabs SERP round-robin for ASIN extraction.
    progress_start/progress_end define the range used when writing progress.
    In keywords mode, pass progress_start=40, progress_end=60 so the bar
    advances during the SERP phase without conflicting with autocomplete.
    """
    asins_found: Dict[str, dict] = {}
    titles_collected: List[str] = []
    serp_calls = 0
    progress_range = progress_end - progress_start

    for page in range(1, MAX_SERP_PAGE + 1):
        for seed_keyword in seed_keywords:
            if is_cancelled(job_id):
                return asins_found, titles_collected

            if serp_calls >= MAX_OXY_SERP_CALLS:
                break
            if len(asins_found) >= TARGET_MAX:
                break

            try:
                response = await oxylabs_client.amazon_search_single_page(
                    seed_keyword, page=page, category_id=category_id,
                    job_id=job_id, db=db
                )
                serp_calls += 1

                if response:
                    results = response.get("results", [])
                    for result in results:
                        content = result.get("content", {})
                        organic = content.get("results", {}).get("organic", [])

                        for product in organic:
                            asin = product.get("asin")
                            if not asin or asin in asins_found:
                                continue

                            title = product.get("title", "")
                            if not include_merch and "merch" in title.lower():
                                continue

                            asin_data = {
                                "asin": asin,
                                "title": title,
                                "brand": product.get("brand"),
                                "price": product.get("price"),
                                "rating": product.get("rating"),
                                "ratings_total": product.get("reviews_count"),
                                "bsr": product.get("sales_rank"),
                                "image_url": product.get("url_image") or product.get("image"),
                                "format": detect_format(title),
                                "source": "search",
                                "seed_keyword": seed_keyword,
                            }
                            asins_found[asin] = asin_data
                            titles_collected.append(title)

            except Exception as e:
                print(f"[Extractor] SERP error for '{seed_keyword}' page {page}: {e}")

            if write_progress:
                pct = progress_start + min(
                    progress_range,
                    int((serp_calls / MAX_OXY_SERP_CALLS) * progress_range)
                )
                job.progress = pct
                job.asins_found = len(asins_found)
                db.commit()

        if serp_calls >= MAX_OXY_SERP_CALLS or len(asins_found) >= TARGET_MAX:
            break

    if len(asins_found) < TARGET_MIN and serp_calls < MAX_OXY_SERP_CALLS:
        for seed_keyword in seed_keywords:
            if serp_calls >= MAX_OXY_SERP_CALLS or len(asins_found) >= TARGET_MIN:
                break
            try:
                response = await oxylabs_client.amazon_search_single_page(
                    seed_keyword, page=3, category_id=category_id,
                    job_id=job_id, db=db
                )
                serp_calls += 1
                if response:
                    results = response.get("results", [])
                    for result in results:
                        content = result.get("content", {})
                        organic = content.get("results", {}).get("organic", [])
                        for product in organic:
                            asin = product.get("asin")
                            if not asin or asin in asins_found:
                                continue
                            title = product.get("title", "")
                            if not include_merch and "merch" in title.lower():
                                continue
                            asins_found[asin] = {
                                "asin": asin, "title": title,
                                "brand": product.get("brand"), "price": product.get("price"),
                                "rating": product.get("rating"), "ratings_total": product.get("reviews_count"),
                                "bsr": product.get("sales_rank"),
                                "image_url": product.get("url_image") or product.get("image"),
                                "format": detect_format(title), "source": "search",
                                "seed_keyword": seed_keyword,
                            }
                            titles_collected.append(title)
            except Exception as e:
                print(f"[Extractor] SERP page 3 error for '{seed_keyword}': {e}")

    return asins_found, titles_collected


async def _enrich_asins_with_products(
    asins_found: Dict[str, dict],
    job_id: str,
    db: Session,
    job: ExtractionJob
):
    if len(asins_found) >= TARGET_MIN:
        return

    product_calls = 0
    top_asins = list(asins_found.keys())[:MAX_OXY_PRODUCT_CALLS * 2]

    for asin in top_asins:
        if product_calls >= MAX_OXY_PRODUCT_CALLS or len(asins_found) >= TARGET_MIN:
            break

        try:
            response = await oxylabs_client.amazon_product_by_asin(
                asin, job_id=job_id, db=db
            )
            product_calls += 1

            results = response.get("results", [])
            for result in results:
                content = result.get("content", {})
                related = content.get("related_items", {})
                also_bought = related.get("also_bought", []) if related else []
                also_viewed = related.get("also_viewed", []) if related else []

                for item in (also_bought + also_viewed):
                    new_asin = item.get("asin")
                    if new_asin and new_asin not in asins_found:
                        asins_found[new_asin] = {
                            "asin": new_asin,
                            "title": item.get("title", ""),
                            "brand": None,
                            "price": item.get("price"),
                            "rating": None,
                            "ratings_total": None,
                            "bsr": None,
                            "image_url": item.get("image"),
                            "format": detect_format(item.get("title", "")),
                            "source": "product_related",
                            "seed_keyword": asins_found[asin].get("seed_keyword", ""),
                        }

            job.asins_found = len(asins_found)
            job.progress = min(70, 50 + int((product_calls / MAX_OXY_PRODUCT_CALLS) * 20))
            db.commit()

        except Exception as e:
            print(f"[Extractor] Product enrichment error for {asin}: {e}")


async def _autocomplete_expand(
    seeds: List[str],
    marketplace: str,
    job_id: str,
    db: Session,
    job: ExtractionJob
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """
    2-level Amazon Autocomplete expansion.
    L1: autocomplete on each seed (max 10 seeds) → real user search suggestions.
    L2: autocomplete on each L1 result (max 50 calls) → deeper long-tail coverage.
    Returns (l1_pairs, l2_pairs) as lists of (keyword, source) tuples.
    Owns progress 5→20% (L1) and 20→40% (L2).
    """
    sem = asyncio.Semaphore(5)

    async def fetch(kw: str) -> List[str]:
        async with sem:
            return await amazon_autocomplete(kw, marketplace, job_id, db)

    seeds_lower: Set[str] = {s.lower().strip() for s in seeds}

    l1_inputs = seeds[:MAX_AUTOCOMPLETE_L1]
    l1_results_raw = await asyncio.gather(*[fetch(s) for s in l1_inputs])

    l1_seen: Set[str] = set()
    l1_pairs: List[Tuple[str, str]] = []
    for suggestions in l1_results_raw:
        for s in suggestions:
            norm = s.lower().strip()
            if norm and norm not in seeds_lower and norm not in l1_seen:
                l1_seen.add(norm)
                l1_pairs.append((norm, "autocomplete_l1"))

    job.progress = 20
    job.keywords_found = len(l1_pairs)
    db.commit()

    l2_inputs = [kw for kw, _ in l1_pairs[:MAX_AUTOCOMPLETE_L2]]
    l2_results_raw = await asyncio.gather(*[fetch(kw) for kw in l2_inputs])

    all_seen = seeds_lower | l1_seen
    l2_seen: Set[str] = set()
    l2_pairs: List[Tuple[str, str]] = []
    for suggestions in l2_results_raw:
        for s in suggestions:
            norm = s.lower().strip()
            if norm and norm not in all_seen and norm not in l2_seen:
                l2_seen.add(norm)
                l2_pairs.append((norm, "autocomplete_l2"))

    job.progress = 40
    job.keywords_found = len(l1_pairs) + len(l2_pairs)
    db.commit()

    return l1_pairs, l2_pairs


def _extract_serp_phrases(titles: List[str], seen: Set[str]) -> List[Tuple[str, str]]:
    """
    Extract 2-3 word phrases from SERP titles as a secondary signal.
    Only keeps phrases appearing in at least 2 distinct titles.
    """
    phrase_freq: Counter = Counter()
    for title in titles:
        cleaned = re.sub(r'[^\w\s]', ' ', title.lower())
        words = [w for w in cleaned.split() if len(w) > 2 and w not in STOP_WORDS and not w.isdigit()]
        phrase_set: Set[str] = set()
        for i in range(len(words) - 1):
            phrase_set.add(f"{words[i]} {words[i+1]}")
        for i in range(len(words) - 2):
            phrase_set.add(f"{words[i]} {words[i+1]} {words[i+2]}")
        for p in phrase_set:
            phrase_freq[p] += 1

    results: List[Tuple[str, str]] = []
    for phrase, freq in phrase_freq.most_common(300):
        if freq >= 2 and phrase not in seen:
            results.append((phrase, "serp_title"))
    return results




async def run_extraction(
    db: Session,
    job_id: str,
    user_id: int,
    extraction_type: str = "asins",
    category_mode: str = "books",
    max_asins: int = 1000,
    max_keywords: int = 1000,
    include_merch: bool = False
):
    job = db.query(ExtractionJob).filter(ExtractionJob.id == job_id).first()
    if not job:
        return

    try:
        job.status = "processing"
        db.commit()

        seed_keywords = job.seed_keywords or []
        category_id = "283155" if category_mode == "books" else None

        if extraction_type == "asins":
            asins_found, _ = await _serp_round_robin(
                seed_keywords, category_id, include_merch, job_id, db, job,
                write_progress=True
            )

            if is_cancelled(job_id):
                job.status = "error"
                job.error = "Estrazione annullata dall'utente"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                clear_cancellation(job_id)
                return

            job.progress = 55
            db.commit()

            await _enrich_asins_with_products(asins_found, job_id, db, job)

            job.progress = 80
            db.commit()

            for asin_code, data in asins_found.items():
                db_asin = ExtractedAsin(user_id=user_id, job_id=job_id, **data)
                db.add(db_asin)

            job.status = "completed"
            job.progress = 100
            job.asins_found = len(asins_found)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

        elif extraction_type == "keywords":
            marketplace = "com"

            job.progress = 5
            db.commit()

            # Phase 1+2: Run autocomplete expansion and SERP round-robin concurrently.
            # Autocomplete owns 5→40% (L1: 5→20%, L2: 20→40%).
            # SERP writes 40→60% so the bar keeps moving during Oxylabs calls.
            # Since autocomplete finishes first, there is no conflict: SERP picks up
            # at 40% and advances from there while the user waits.
            (l1_pairs, l2_pairs), (serp_asins, titles_collected) = await asyncio.gather(
                _autocomplete_expand(seed_keywords, marketplace, job_id, db, job),
                _serp_round_robin(
                    seed_keywords, category_id, include_merch, job_id, db, job,
                    write_progress=True, progress_start=40, progress_end=60,
                )
            )
            job.asins_found = len(serp_asins)

            if is_cancelled(job_id):
                job.status = "error"
                job.error = "Estrazione annullata dall'utente"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                clear_cancellation(job_id)
                return

            job.progress = 60
            db.commit()

            # Phase 3: Extract secondary phrases from SERP titles.
            autocomplete_seen: Set[str] = {s.lower().strip() for s in seed_keywords}
            for kw, _ in l1_pairs:
                autocomplete_seen.add(kw)
            for kw, _ in l2_pairs:
                autocomplete_seen.add(kw)

            serp_phrases = _extract_serp_phrases(titles_collected, autocomplete_seen)

            # Phase 4: Build full merged pool (seeds first, then L1, L2, serp_phrases).
            # Bounded by max_keywords. All sources included; seeds get priority.
            merged_pool: List[Tuple[str, str]] = []
            merged_seen: Set[str] = set()

            for seed in seed_keywords:
                norm = seed.lower().strip()
                if norm and norm not in merged_seen:
                    merged_seen.add(norm)
                    merged_pool.append((norm, "seed"))

            for kw, source in (l1_pairs + l2_pairs + serp_phrases):
                if kw not in merged_seen:
                    merged_seen.add(kw)
                    merged_pool.append((kw, source))
                if len(merged_pool) >= max_keywords:
                    break

            job.progress = 65
            job.keywords_found = len(merged_pool)
            db.commit()

            # Phase 5: Persist keywords directly — no AI scoring.
            # category and relevance_score remain NULL.
            job.progress = 90
            db.commit()

            for kw, source in merged_pool:
                db_keyword = ExtractedKeyword(
                    user_id=user_id,
                    job_id=job_id,
                    keyword=kw,
                    source=source,
                    source_asin=None,
                    is_seed=(source == "seed"),
                    category=None,
                    relevance_score=None,
                )
                db.add(db_keyword)

            job.status = "completed"
            job.progress = 100
            job.keywords_found = len(merged_pool)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

    except Exception as e:
        job.status = "error"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        clear_cancellation(job_id)


def get_dashboard_data(db: Session, user_id: int) -> dict:
    total_asins = db.query(ExtractedAsin).filter(ExtractedAsin.user_id == user_id).count()
    total_keywords = db.query(ExtractedKeyword).filter(ExtractedKeyword.user_id == user_id).count()
    total_jobs = db.query(ExtractionJob).filter(ExtractionJob.user_id == user_id).count()

    latest_job = db.query(ExtractionJob).filter(
        ExtractionJob.user_id == user_id
    ).order_by(ExtractionJob.started_at.desc()).first()

    recent_asins = db.query(ExtractedAsin).filter(
        ExtractedAsin.user_id == user_id
    ).order_by(ExtractedAsin.extracted_at.desc()).limit(5).all()

    recent_keywords = db.query(ExtractedKeyword).filter(
        ExtractedKeyword.user_id == user_id
    ).order_by(ExtractedKeyword.extracted_at.desc()).limit(15).all()

    recent_jobs = db.query(ExtractionJob).filter(
        ExtractionJob.user_id == user_id
    ).order_by(ExtractionJob.started_at.desc()).limit(5).all()

    return {
        "total_asins": total_asins,
        "total_keywords": total_keywords,
        "total_jobs": total_jobs,
        "latest_job": {
            "id": latest_job.id,
            "status": latest_job.status,
            "started_at": latest_job.started_at.isoformat() if latest_job.started_at else None,
            "completed_at": latest_job.completed_at.isoformat() if latest_job.completed_at else None,
        } if latest_job else None,
        "recent_asins": [
            {"asin": a.asin, "title": a.title}
            for a in recent_asins
        ],
        "recent_keywords": [k.keyword for k in recent_keywords],
        "recent_jobs": [
            {
                "id": j.id,
                "seed_keywords": j.seed_keywords or [],
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "status": j.status,
                "asins_found": j.asins_found or 0,
                "keywords_found": j.keywords_found or 0
            }
            for j in recent_jobs
        ]
    }


def get_current_job(db: Session, user_id: int) -> Optional[dict]:
    job = db.query(ExtractionJob).filter(
        ExtractionJob.user_id == user_id,
        ExtractionJob.status == "processing"
    ).first()

    if not job:
        return None

    if job.started_at:
        elapsed = (datetime.now(timezone.utc) - job.started_at).total_seconds()
        if elapsed > 900:
            job.status = "error"
            job.error = "Timeout: estrazione bloccata da più di 15 minuti"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return None

    return {
        "id": job.id,
        "seed_keywords": job.seed_keywords,
        "extraction_type": job.extraction_type,
        "category_mode": job.category_mode,
        "status": job.status,
        "progress": job.progress,
        "asins_found": job.asins_found,
        "keywords_found": job.keywords_found,
        "started_at": job.started_at.isoformat() if job.started_at else None,
    }
