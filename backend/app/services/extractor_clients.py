import os
import httpx
import base64
from typing import Optional, List, Any, Dict
import asyncio
import time
import json
from sqlalchemy.orm import Session

OXYLABS_ENDPOINT = "https://realtime.oxylabs.io/v1/queries"
CANOPY_ENDPOINT = "https://graphql.canopyapi.co/"


def _write_api_log(db: Session, job_id: str, log_type: str, endpoint: str, source: str,
                   request_data: dict, response_data: Any, status_code: Optional[int], duration_ms: int):
    from backend.app.models.extractor import ExtractorApiLog
    try:
        req_str = json.dumps(request_data, default=str)
        resp_str = json.dumps(response_data, default=str) if response_data else "{}"
        if len(resp_str) > 50000:
            resp_str = resp_str[:50000] + "...[truncated]"

        entry = ExtractorApiLog(
            job_id=job_id,
            log_type=log_type,
            endpoint=endpoint,
            request_data=req_str,
            response_data=resp_str,
            source=source,
            status_code=status_code,
            duration_ms=duration_ms
        )
        db.add(entry)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


async def amazon_autocomplete(
    keyword: str,
    marketplace: str = "com",
    job_id: Optional[str] = None,
    db: Optional[Session] = None
) -> List[str]:
    url = f"https://completion.amazon.{marketplace}/api/2017/suggestions"
    params = {
        "alias": "aps",
        "prefix": keyword,
        "nb": 10,
        "plain": "1",
    }
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url, params=params)
            duration_ms = int((time.time() - start) * 1000)
            data = r.json()
            suggestions = [s["value"] for s in data.get("suggestions", []) if s.get("value")]
            if job_id and db:
                _write_api_log(
                    db, job_id, "search", url, "autocomplete",
                    {"keyword": keyword, "marketplace": marketplace},
                    {"suggestions_count": len(suggestions), "suggestions": suggestions[:5]},
                    r.status_code, duration_ms
                )
            return suggestions
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        if job_id and db:
            _write_api_log(
                db, job_id, "search", url, "autocomplete",
                {"keyword": keyword, "marketplace": marketplace},
                {"error": str(e)}, 500, duration_ms
            )
        return []


class OxylabsClient:
    def __init__(self):
        self.user = os.getenv("OXYLABS_USER")
        self.password = os.getenv("OXYLABS_PASS")

    def is_configured(self) -> bool:
        return bool(self.user and self.password)

    def _get_auth_header(self) -> str:
        credentials = f"{self.user}:{self.password}"
        return "Basic " + base64.b64encode(credentials.encode()).decode()

    async def query(
        self, payload: dict, timeout_seconds: int = 120,
        job_id: Optional[str] = None, db: Optional[Session] = None,
        endpoint_label: str = "query"
    ) -> dict:
        if not self.is_configured():
            raise ValueError("Oxylabs credentials not configured")

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    OXYLABS_ENDPOINT,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": self._get_auth_header()
                    }
                )

                duration_ms = int((time.time() - start) * 1000)

                if job_id and db:
                    resp_summary = {"status_code": response.status_code}
                    try:
                        resp_json = response.json()
                        results = resp_json.get("results", [])
                        if results:
                            organic = results[0].get("content", {}).get("results", {}).get("organic", [])
                            resp_summary["organic_count"] = len(organic)
                        resp_summary["results_count"] = len(results)
                    except Exception:
                        resp_summary["raw_length"] = len(response.text)
                    _write_api_log(db, job_id, "search", endpoint_label, "oxylabs",
                                   payload, resp_summary, response.status_code, duration_ms)

                if response.status_code != 200:
                    raise Exception(f"Oxylabs API error: {response.status_code} - {response.text}")

                return response.json()
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            if job_id and db:
                _write_api_log(db, job_id, "search", endpoint_label, "oxylabs",
                               payload, {"error": str(e)}, 500, duration_ms)
            raise

    async def amazon_product_by_asin(
        self, asin: str, geo_location: str = "90210",
        job_id: Optional[str] = None, db: Optional[Session] = None
    ) -> dict:
        return await self.query(
            {"source": "amazon_product", "query": asin, "geo_location": geo_location, "parse": True},
            job_id=job_id, db=db, endpoint_label="amazon_product"
        )

    async def amazon_search(
        self, keyword: str, geo_location: str = "90210",
        category_id: Optional[str] = None,
        job_id: Optional[str] = None, db: Optional[Session] = None
    ) -> dict:
        payload: Dict[str, Any] = {
            "source": "amazon_search",
            "query": keyword,
            "geo_location": geo_location,
            "parse": True
        }
        if category_id:
            payload["context"] = [{"key": "category_id", "value": category_id}]

        return await self.query(payload, job_id=job_id, db=db, endpoint_label="amazon_search")

    async def amazon_search_single_page(
        self, keyword: str, page: int = 1, geo_location: str = "90210",
        category_id: Optional[str] = None,
        job_id: Optional[str] = None, db: Optional[Session] = None
    ) -> Optional[dict]:
        payload: Dict[str, Any] = {
            "source": "amazon_search",
            "query": keyword,
            "geo_location": geo_location,
            "parse": True,
            "start_page": page
        }
        if category_id:
            payload["context"] = [{"key": "category_id", "value": category_id}]
        try:
            return await self.query(payload, job_id=job_id, db=db,
                                     endpoint_label=f"amazon_search_p{page}")
        except Exception as e:
            print(f"[Oxylabs] Error fetching page {page} for '{keyword}': {e}")
            return None

    async def amazon_search_paginated(
        self,
        keyword: str,
        pages: int = 3,
        geo_location: str = "90210",
        category_id: Optional[str] = None,
        job_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> List[dict]:
        sem = asyncio.Semaphore(2)

        async def fetch_page(page: int) -> Optional[dict]:
            async with sem:
                return await self.amazon_search_single_page(
                    keyword, page, geo_location, category_id, job_id, db
                )

        tasks = [fetch_page(i + 1) for i in range(pages)]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def check_connection(self) -> dict:
        try:
            await self.amazon_product_by_asin("B07FZ8S74R")
            return {"status": "connected"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class CanopyClient:
    def __init__(self):
        self.api_key = os.getenv("CANOPY_API_KEY")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def gql(
        self, query: str, variables: Optional[dict] = None,
        timeout_seconds: int = 60,
        job_id: Optional[str] = None, db: Optional[Session] = None,
        endpoint_label: str = "canopy_gql"
    ) -> dict:
        if not self.is_configured():
            raise ValueError("Canopy API key not configured")

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    CANOPY_ENDPOINT,
                    json={"query": query, "variables": variables or {}},
                    headers={
                        "Content-Type": "application/json",
                        "API-KEY": self.api_key
                    }
                )

                duration_ms = int((time.time() - start) * 1000)

                if job_id and db:
                    _write_api_log(db, job_id, "search", endpoint_label, "canopy",
                                   {"query_length": len(query), "variables": variables},
                                   {"status_code": response.status_code}, response.status_code, duration_ms)

                if response.status_code != 200:
                    raise Exception(f"Canopy API error: {response.status_code} - {response.text}")

                return response.json()
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            if job_id and db:
                _write_api_log(db, job_id, "search", endpoint_label, "canopy",
                               {"query_length": len(query), "variables": variables},
                               {"error": str(e)}, 500, duration_ms)
            raise

    async def amazon_product(self, asin: str, job_id: Optional[str] = None, db: Optional[Session] = None) -> dict:
        query = """
            query AmazonProduct($asin: String!) {
                amazonProduct(input: { asinLookup: { asin: $asin } }) {
                    asin
                    title
                    brand
                    rating
                    ratingsTotal
                    mainImageUrl
                    price { display }
                    customersAlsoBought { asin title mainImageUrl }
                    customersAlsoViewed { asin title mainImageUrl }
                }
            }
        """
        return await self.gql(query, {"asin": asin}, job_id=job_id, db=db, endpoint_label="amazon_product")

    async def amazon_search(self, search_term: str, department: Optional[str] = None,
                            job_id: Optional[str] = None, db: Optional[Session] = None) -> dict:
        if department:
            query = """
                query AmazonSearch($term: String!, $dept: String!) {
                    amazonProductSearchResults(input: { searchTerm: $term, department: $dept }) {
                        productResults {
                            asin
                            title
                        }
                    }
                }
            """
            variables = {"term": search_term, "dept": department}
        else:
            query = """
                query AmazonSearch($term: String!) {
                    amazonProductSearchResults(input: { searchTerm: $term }) {
                        productResults {
                            asin
                            title
                        }
                    }
                }
            """
            variables = {"term": search_term}

        return await self.gql(query, variables, job_id=job_id, db=db, endpoint_label="amazon_search")

    async def amazon_autocomplete(self, search_term: str) -> dict:
        query = """
            query Auto($term: String!) {
                amazonSearchAutocompleteResults(input: { searchTerm: $term }) {
                    suggestion
                }
            }
        """
        return await self.gql(query, {"term": search_term})

    async def check_connection(self) -> dict:
        try:
            result = await self.amazon_search("test")
            if "errors" in result and result["errors"]:
                return {"status": "error", "message": result["errors"][0].get("message", "Unknown error")}
            return {"status": "connected"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


oxylabs_client = OxylabsClient()
canopy_client = CanopyClient()
