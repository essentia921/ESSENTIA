from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from db.blog_db import (
    get_all_posts, get_post_by_slug, get_post_by_id,
    create_post, update_post, publish_post, unpublish_post, delete_post,
)
from backend.app.services.email_service import get_resend_credentials
import resend
import re
import os
import uuid
import logging
from backend.app.services.supabase_storage import SupabaseStorage

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Blog Admin credentials (separate from main app auth) ─────────────────────
BLOG_ADMIN_USERNAME = "admin"
BLOG_ADMIN_PASSWORD = "EssentiaB!og2025"
BLOG_ADMIN_SECRET   = "blog-admin-essentia-suite-secret-2025"
BLOG_ADMIN_EMAIL    = "erba.francesco.mp@gmail.com"
BLOG_TOKEN_EXPIRE_DAYS = 30


def create_blog_token() -> str:
    payload = {
        "sub": BLOG_ADMIN_USERNAME,
        "type": "blog_admin",
        "exp": datetime.utcnow() + timedelta(days=BLOG_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, BLOG_ADMIN_SECRET, algorithm="HS256")


def verify_blog_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, BLOG_ADMIN_SECRET, algorithms=["HS256"])
        return payload.get("type") == "blog_admin"
    except JWTError:
        return False


def require_blog_admin(request: Request):
    token = request.headers.get("X-Blog-Admin-Token", "")
    if not token or not verify_blog_token(token):
        raise HTTPException(status_code=401, detail="Accesso non autorizzato al blog admin")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def serialize_post(post: dict) -> dict:
    for field in ['created_at', 'updated_at', 'published_at']:
        if post.get(field) and isinstance(post[field], datetime):
            post[field] = post[field].isoformat()
    return post


def send_credentials_email():
    """Send blog admin credentials to the admin email via Resend."""
    try:
        api_key, _ = get_resend_credentials()
        if not api_key:
            import os
            api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            logger.error("No Resend API key available for blog credentials email")
            return False
        resend.api_key = api_key
        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; background: #f8feff; padding: 40px;">
          <div style="max-width: 480px; margin: 0 auto; background: white; border-radius: 16px; padding: 40px; border: 1px solid #e5e7eb;">
            <div style="text-align: center; margin-bottom: 24px;">
              <div style="width: 48px; height: 48px; background: #00D4FF; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 12px;">
                <span style="color: white; font-size: 24px;">⚡</span>
              </div>
              <h2 style="color: #0F1D32; margin: 0;">Essentia Suite — Blog Admin</h2>
            </div>
            <p style="color: #6b7280;">Hai richiesto il recupero delle credenziali di accesso al Blog Admin.</p>
            <div style="background: #f8feff; border: 1px solid #b3eeff; border-radius: 10px; padding: 20px; margin: 24px 0;">
              <p style="margin: 0 0 8px 0; color: #374151;"><strong>URL:</strong> <a href="https://essentia-ads.io/adminblog" style="color: #00D4FF;">essentia-ads.io/adminblog</a></p>
              <p style="margin: 0 0 8px 0; color: #374151;"><strong>Username:</strong> admin</p>
              <p style="margin: 0; color: #374151;"><strong>Password:</strong> EssentiaB!og2025</p>
            </div>
            <p style="color: #9ca3af; font-size: 12px; margin-top: 24px;">Essentia Suite • Blog Admin Panel</p>
          </div>
        </body>
        </html>
        """
        result = resend.Emails.send({
            "from": "Essentia Suite <noreply@anonimapublishing.online>",
            "to": [BLOG_ADMIN_EMAIL],
            "subject": "Blog Admin — Credenziali di Accesso",
            "html": html,
        })
        logger.info(f"Blog credentials email sent: {result}")
        return True
    except Exception as e:
        logger.error(f"Failed to send credentials email: {e}")
        return False


PRODUCTION_BASE_URL = "https://essentia-ads.io"

STATIC_PAGES = [
    {"url": PRODUCTION_BASE_URL + "/", "priority": "1.0", "type": "static"},
    {"url": PRODUCTION_BASE_URL + "/blog", "priority": "0.9", "type": "static"},
]


# ─── Pydantic models ──────────────────────────────────────────────────────────

class BlogLoginBody(BaseModel):
    username: str
    password: str


class PostBody(BaseModel):
    title: str
    slug: Optional[str] = None
    excerpt: Optional[str] = ""
    content: str = ""
    cover_image_url: Optional[str] = None
    author: Optional[str] = "Essentia Suite Team"
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    tags: Optional[str] = ""
    reading_time_min: Optional[int] = 5
    language: Optional[str] = 'en'


# ─── Blog Admin Auth endpoints ────────────────────────────────────────────────

@router.post("/admin/bloglogin")
async def blog_admin_login(body: BlogLoginBody):
    if body.username != BLOG_ADMIN_USERNAME or body.password != BLOG_ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    token = create_blog_token()
    return {"token": token, "username": BLOG_ADMIN_USERNAME}


@router.post("/admin/bloglogin/forgot")
async def blog_admin_forgot():
    ok = send_credentials_email()
    if not ok:
        raise HTTPException(status_code=500, detail="Errore invio email. Riprova.")
    return {"ok": True, "message": f"Credenziali inviate a {BLOG_ADMIN_EMAIL}"}


@router.get("/admin/bloglogin/verify")
async def blog_admin_verify(request: Request):
    token = request.headers.get("X-Blog-Admin-Token", "")
    if not token or not verify_blog_token(token):
        raise HTTPException(status_code=401, detail="Token non valido o scaduto")
    return {"ok": True, "username": BLOG_ADMIN_USERNAME}


# ─── Public endpoints ─────────────────────────────────────────────────────────

@router.get("/posts")
async def list_posts(lang: Optional[str] = None):
    posts = get_all_posts(include_drafts=False, lang=lang)
    return [serialize_post(p) for p in posts]


@router.get("/posts/slug/{slug}")
async def get_post(slug: str):
    post = get_post_by_slug(slug, include_drafts=False)
    if not post:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return serialize_post(post)


# ─── Admin endpoints (protected by blog token) ────────────────────────────────

@router.get("/admin/posts")
async def admin_list_posts(request: Request, lang: Optional[str] = None):
    require_blog_admin(request)
    posts = get_all_posts(include_drafts=True, lang=lang)
    return [serialize_post(p) for p in posts]


@router.get("/admin/posts/{post_id}")
async def admin_get_post(post_id: int, request: Request):
    require_blog_admin(request)
    post = get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return serialize_post(post)


@router.post("/admin/posts")
async def admin_create_post(body: PostBody, request: Request):
    require_blog_admin(request)
    slug = body.slug or slugify(body.title)
    if not slug:
        raise HTTPException(status_code=400, detail="Slug non valido")
    data = {
        'title': body.title, 'slug': slug, 'excerpt': body.excerpt or '',
        'content': body.content, 'cover_image_url': body.cover_image_url,
        'author': body.author or 'Essentia Suite Team', 'seo_title': body.seo_title,
        'seo_description': body.seo_description, 'tags': body.tags or '',
        'reading_time_min': body.reading_time_min or 5,
        'language': body.language or 'en',
    }
    try:
        return serialize_post(create_post(data))
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            raise HTTPException(status_code=409, detail="Slug già in uso — modificalo")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/posts/{post_id}")
async def admin_update_post(post_id: int, body: PostBody, request: Request):
    require_blog_admin(request)
    existing = get_post_by_id(post_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    slug = body.slug or slugify(body.title)
    data = {
        'title': body.title, 'slug': slug, 'excerpt': body.excerpt or '',
        'content': body.content, 'cover_image_url': body.cover_image_url,
        'author': body.author or 'Essentia Suite Team', 'seo_title': body.seo_title,
        'seo_description': body.seo_description, 'tags': body.tags or '',
        'reading_time_min': body.reading_time_min or 5,
        'language': body.language or 'en',
    }
    try:
        return serialize_post(update_post(post_id, data))
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            raise HTTPException(status_code=409, detail="Slug già in uso — modificalo")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/posts/{post_id}/publish")
async def admin_publish_post(post_id: int, request: Request):
    require_blog_admin(request)
    post = publish_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return serialize_post(post)


@router.post("/admin/posts/{post_id}/unpublish")
async def admin_unpublish_post(post_id: int, request: Request):
    require_blog_admin(request)
    post = unpublish_post(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    return serialize_post(post)


@router.delete("/admin/posts/{post_id}")
async def admin_delete_post(post_id: int, request: Request):
    require_blog_admin(request)
    if not get_post_by_id(post_id):
        raise HTTPException(status_code=404, detail="Articolo non trovato")
    delete_post(post_id)
    return {"ok": True}


@router.get("/admin/sitemap-preview")
async def admin_sitemap_preview(request: Request):
    """Return all sitemap URLs as JSON for the AdminBlog viewer."""
    require_blog_admin(request)
    posts = get_all_posts(include_drafts=False)
    entries = list(STATIC_PAGES)
    for p in posts:
        lastmod = p.get("updated_at") or p.get("published_at")
        if isinstance(lastmod, datetime):
            lastmod = lastmod.isoformat()
        entries.append({
            "url": PRODUCTION_BASE_URL + f"/blog/{p['slug']}",
            "priority": "0.8",
            "lastmod": lastmod,
            "type": "article",
            "title": p.get("title", ""),
            "status": p.get("status", ""),
        })
    return {"urls": entries, "sitemap_url": f"{PRODUCTION_BASE_URL}/sitemap.xml"}


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

LOCAL_UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "blog")

def _get_object_storage_client():
    return SupabaseStorage()

def check_object_storage_available() -> bool:
    """Verifica che Supabase Storage sia raggiungibile all'avvio.

    Ritorna True se il bucket e' accessibile, False altrimenti (con warning).
    """
    return SupabaseStorage().available()

def migrate_local_blog_images_to_object_storage():
    """Migrate any blog images still on the local filesystem into Object Storage.

    Called once at app startup so that images present on disk (e.g. from dev
    or a previous deployment that used the filesystem) are made available via
    the persistent Object Storage backend.
    """
    if not os.path.isdir(LOCAL_UPLOADS_DIR):
        return
    files = [f for f in os.listdir(LOCAL_UPLOADS_DIR)
             if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS]
    if not files:
        return
    try:
        client = _get_object_storage_client()
        for filename in files:
            object_name = f"blog/{filename}"
            try:
                if client.exists(object_name):
                    continue
                with open(os.path.join(LOCAL_UPLOADS_DIR, filename), "rb") as fh:
                    data = fh.read()
                client.upload_from_bytes(object_name, data)
                logger.info(f"Migrated blog image to object storage: {filename}")
            except Exception as e:
                logger.warning(f"Could not migrate blog image {filename}: {e}")
    except Exception as e:
        logger.warning(f"Blog image migration skipped (object storage unavailable): {e}")

@router.post("/admin/upload-image")
async def admin_upload_image(request: Request, file: UploadFile = File(...)):
    require_blog_admin(request)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Formato non supportato. Usa: {', '.join(ALLOWED_EXTENSIONS)}")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File troppo grande (max 10 MB)")
    filename = f"{uuid.uuid4().hex}{ext}"
    object_name = f"blog/{filename}"
    try:
        client = _get_object_storage_client()
        client.upload_from_bytes(object_name, content)
    except Exception as e:
        logger.error(f"Object storage upload failed: {e}")
        raise HTTPException(status_code=500, detail="Errore nel caricamento dell'immagine")
    url = f"/api/blog/images/{filename}"
    return {"url": url, "filename": filename}

@router.get("/images/{filename}")
async def serve_blog_image(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Tipo file non supportato")
    object_name = f"blog/{filename}"
    data = None
    try:
        client = _get_object_storage_client()
        data = client.download_as_bytes(object_name)
    except Exception as e:
        logger.warning(f"Image not in object storage: {object_name} — {e}")
    if data is None:
        local_path = os.path.join(LOCAL_UPLOADS_DIR, filename)
        if os.path.isfile(local_path):
            with open(local_path, "rb") as fh:
                data = fh.read()
    if data is None:
        raise HTTPException(status_code=404, detail="Immagine non trovata")
    content_type = CONTENT_TYPE_MAP.get(ext, "application/octet-stream")
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=31536000"})
