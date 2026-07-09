"""
Supabase Storage - sostituto di Replit Object Storage per le immagini del blog.

Stessa interfaccia usata da blog.py (exists / upload_from_bytes / download_as_bytes),
implementata con l'API REST di Supabase Storage (nessun SDK aggiuntivo).

Env richiesti:
  SUPABASE_URL            es. https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY    service role key (lato server)
  SUPABASE_STORAGE_BUCKET nome bucket (default: "media")
"""

import os
import logging

import requests

logger = logging.getLogger(__name__)

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
)
DEFAULT_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "media")


class SupabaseStorage:
    def __init__(self, bucket: str = None):
        self.bucket = bucket or DEFAULT_BUCKET
        self.base = f"{SUPABASE_URL}/storage/v1"
        self.key = SUPABASE_SERVICE_KEY

    def _headers(self, extra: dict = None) -> dict:
        h = {"Authorization": f"Bearer {self.key}", "apikey": self.key or ""}
        if extra:
            h.update(extra)
        return h

    def available(self) -> bool:
        if not SUPABASE_URL or not self.key:
            logger.warning("Supabase Storage non configurato (SUPABASE_URL / SUPABASE_SERVICE_KEY mancanti)")
            return False
        try:
            r = requests.get(f"{self.base}/bucket/{self.bucket}", headers=self._headers(), timeout=5)
            if r.status_code == 200:
                logger.info(f"Supabase Storage disponibile (bucket: {self.bucket})")
                return True
            logger.warning(f"Supabase Storage: bucket '{self.bucket}' non accessibile ({r.status_code})")
            return False
        except Exception as e:
            logger.warning(f"Supabase Storage non raggiungibile: {e}")
            return False

    def exists(self, path: str) -> bool:
        try:
            r = requests.get(
                f"{self.base}/object/info/{self.bucket}/{path}",
                headers=self._headers(), timeout=10,
            )
            return r.status_code == 200
        except Exception:
            return False

    def upload_from_bytes(self, path: str, data: bytes, content_type: str = "application/octet-stream"):
        r = requests.post(
            f"{self.base}/object/{self.bucket}/{path}",
            headers=self._headers({"Content-Type": content_type, "x-upsert": "true"}),
            data=data, timeout=30,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Supabase upload fallito {r.status_code}: {r.text[:200]}")

    def download_as_bytes(self, path: str) -> bytes:
        r = requests.get(
            f"{self.base}/object/{self.bucket}/{path}",
            headers=self._headers(), timeout=30,
        )
        if r.status_code != 200:
            raise FileNotFoundError(f"Supabase download {r.status_code} per {path}")
        return r.content
