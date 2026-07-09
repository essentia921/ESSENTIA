from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles as StarletteStaticFiles
from contextlib import asynccontextmanager
from backend.app.core.config import settings
from backend.app.api.routes import auth, accounts, profiles, bids, subscriptions, amazon_auth, tokens, campaign_launcher, flash_agent, books, autopilot_v2, extractor, admin, blog, affiliates, harvest
from backend.app.services.report_scheduler import start_report_poller, stop_report_poller
import os
from typing import Optional

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}

class NoCacheStaticFiles(StarletteStaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response is not None:
            for key, value in NO_CACHE_HEADERS.items():
                response.headers[key] = value
        return response


def migrate_orphan_profile_books():
    """Link profile_ids in profile_books that are missing from client_profiles.

    Strategy:
    1. Try to link via planned_actions/sp_inventory/sb_inventory where account EXISTS.
    2. For still-orphaned profiles (planned_actions references deleted accounts):
       link to the first account of the admin/owner user (user_id with the lowest id
       that has at least one client_account).
    3. Fix accounts with NULL user_id by assigning them to the admin user
       if their profile_ids appear alongside known admin profile_ids.
    """
    try:
        from db.accounts_db import get_connection
        conn = get_connection()
        cur = conn.cursor()

        # Step 1: Link via activity tables where the referenced account still exists
        cur.execute("""
            INSERT INTO client_profiles (profile_id, client_account_id)
            SELECT DISTINCT pb.profile_id, pa.account_id
            FROM profile_books pb
            LEFT JOIN client_profiles cp ON pb.profile_id = cp.profile_id
            JOIN (
                SELECT DISTINCT profile_id, account_id FROM planned_actions WHERE account_id IS NOT NULL
                UNION
                SELECT DISTINCT profile_id, account_id FROM sp_inventory WHERE account_id IS NOT NULL
                UNION
                SELECT DISTINCT profile_id, account_id FROM sb_inventory WHERE account_id IS NOT NULL
            ) pa ON pa.profile_id = pb.profile_id
            JOIN client_accounts ca ON ca.id = pa.account_id
            WHERE cp.profile_id IS NULL
            ON CONFLICT (client_account_id, profile_id) DO NOTHING
        """)
        step1 = cur.rowcount

        # Step 2: For still-orphaned profiles (activity refs deleted accounts),
        # assign to the owner of the account with the lowest id (admin).
        cur.execute("""
            INSERT INTO client_profiles (profile_id, client_account_id)
            SELECT DISTINCT pb.profile_id,
                   (SELECT ca2.id FROM client_accounts ca2
                    WHERE ca2.user_id IS NOT NULL
                    ORDER BY ca2.user_id, ca2.id
                    LIMIT 1)
            FROM profile_books pb
            LEFT JOIN client_profiles cp ON pb.profile_id = cp.profile_id
            WHERE cp.profile_id IS NULL
            ON CONFLICT (client_account_id, profile_id) DO NOTHING
        """)
        step2 = cur.rowcount

        conn.commit()
        cur.close()
        conn.close()
        total = step1 + step2
        if total:
            print(f"[migration] Linked {total} orphan profile(s): {step1} via activity tables, {step2} via fallback owner")
    except Exception as e:
        print(f"[migration] migrate_orphan_profile_books warning: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from db.accounts_db import init_autopilot_v2_tables
    from db.blog_db import init_blog_tables
    from backend.app.models.affiliate import init_affiliate_tables
    try:
        init_autopilot_v2_tables()
    except Exception as e:
        print(f"DB init warning: {e}")
    try:
        init_blog_tables()
    except Exception as e:
        print(f"Blog DB init warning: {e}")
    try:
        init_affiliate_tables()
    except Exception as e:
        print(f"Affiliate DB init warning: {e}")
    try:
        from db.harvest_db import init_harvest_db
        init_harvest_db()
    except Exception as e:
        print(f"Harvest DB init warning: {e}")
    migrate_orphan_profile_books()
    try:
        from backend.app.api.routes.blog import check_object_storage_available, migrate_local_blog_images_to_object_storage
        if check_object_storage_available():
            migrate_local_blog_images_to_object_storage()
    except Exception as e:
        print(f"Blog image storage warning: {e}")
    start_report_poller()
    yield
    stop_report_poller()


app = FastAPI(
    title=settings.APP_NAME,
    description="Amazon Ads Manager API",
    version="1.0.0",
    redirect_slashes=True,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_cache_control(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(amazon_auth.router, prefix="/api/auth", tags=["Amazon OAuth"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Accounts"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["Profiles"])
app.include_router(bids.router, prefix="/api/bids", tags=["Bids"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["Subscriptions"])
app.include_router(subscriptions.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(tokens.router, prefix="/api/tokens", tags=["Tokens"])
app.include_router(campaign_launcher.router, prefix="/api/campaign-launcher", tags=["Campaign Launcher"])
app.include_router(flash_agent.router, prefix="/api/flash-agent", tags=["Flash Agent"])
app.include_router(books.router, prefix="/api", tags=["Books"])
app.include_router(autopilot_v2.router, prefix="/api/autopilot", tags=["Autopilot V2"])
app.include_router(extractor.router, prefix="/api", tags=["Extractor"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(blog.router, prefix="/api/blog", tags=["Blog"])
app.include_router(affiliates.router, prefix="/api/affiliates", tags=["Affiliates"])
app.include_router(harvest.router, prefix="/api/harvest", tags=["Harvest"])

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

FRONTEND_ROUTES = [
    "/dashboard",
    "/accounts", "/profiles", "/books", "/campaign-launcher", 
    "/autopilot", "/flash-agent", "/bids", "/tokens", "/settings", 
    "/pricing", "/login", "/register", "/auth/callback", "/onboarding",
    "/verify-email", "/forgot-password", "/reset-password",
    "/extractor", "/extractor/dashboard", "/extractor/new", "/extractor/asins",
    "/extractor/keywords", "/extractor/history", "/extractor/logs", "/extractor/status",
    "/admin", "/adminblog",
    "/blog", "/author",
    "/purchase-success",
    "/tool",
    "/acos-calculator",
    "/campaign-analyzer",
]

@app.get("/health")
async def health():
    return {"status": "healthy"}


PRODUCTION_BASE_URL = "https://essentia-ads.io"

@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    from db.blog_db import get_all_posts
    from datetime import datetime
    posts = get_all_posts(include_drafts=False)
    now = datetime.utcnow().strftime("%Y-%m-%d")

    static_pages = [
        {"loc": f"{PRODUCTION_BASE_URL}/", "priority": "1.0", "changefreq": "weekly"},
        {"loc": f"{PRODUCTION_BASE_URL}/blog", "priority": "0.9", "changefreq": "daily"},
        {"loc": f"{PRODUCTION_BASE_URL}/author", "priority": "0.7", "changefreq": "monthly"},
    ]

    urls = []
    for page in static_pages:
        urls.append(
            f"  <url>\n"
            f"    <loc>{page['loc']}</loc>\n"
            f"    <changefreq>{page['changefreq']}</changefreq>\n"
            f"    <priority>{page['priority']}</priority>\n"
            f"    <lastmod>{now}</lastmod>\n"
            f"  </url>"
        )

    for post in posts:
        lastmod = post.get("updated_at") or post.get("published_at")
        if lastmod and hasattr(lastmod, "strftime"):
            lastmod = lastmod.strftime("%Y-%m-%d")
        elif isinstance(lastmod, str):
            lastmod = lastmod[:10]
        else:
            lastmod = now
        slug = post.get("slug", "")
        urls.append(
            f"  <url>\n"
            f"    <loc>{PRODUCTION_BASE_URL}/blog/{slug}</loc>\n"
            f"    <changefreq>monthly</changefreq>\n"
            f"    <priority>0.8</priority>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin\n"
        "Disallow: /adminblog\n"
        "\n"
        f"Sitemap: {PRODUCTION_BASE_URL}/sitemap.xml\n"
    )
    return Response(content=content, media_type="text/plain")


LLMS_TXT_CONTENT = """\
# Essentia Suite

> Essentia Suite is an Amazon Advertising automation platform for KDP (Kindle Direct Publishing) authors and publishers. We help self-publishers dominate Amazon US with automated bid optimization, ACOS analytics, and keyword research tools.

## Topics
- Amazon KDP advertising and bid optimization
- Self-publishing on Amazon
- Book marketing and ACOS management
- Amazon Sponsored Products campaigns
- Keyword research for Amazon books

## Key URLs
- Homepage: https://essentia-ads.io
- Blog: https://essentia-ads.io/blog
- About the author: https://essentia-ads.io/author

## Author
Francesco Erba — Amazon Ads specialist and KDP publisher. Founder of Essentia Suite.

## Contact
hello@essentia-ads.io
"""


@app.get("/llms.txt", include_in_schema=False)
async def llms_txt():
    return Response(content=LLMS_TXT_CONTENT, media_type="text/plain")


async def serve_spa():
    """Serve the SPA index.html for frontend routes."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers=NO_CACHE_HEADERS)
    return {"error": "Frontend not found"}


for route in FRONTEND_ROUTES:
    app.get(route)(serve_spa)

@app.get("/blog/{slug}")
async def serve_blog_post(slug: str):
    return await serve_spa()



@app.get("/")
async def root_handler(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    scope: Optional[str] = Query(None)
):
    if code and state:
        redirect_url = f"/api/auth/amazon/callback?code={code}&state={state}"
        if scope:
            redirect_url += f"&scope={scope}"
        return RedirectResponse(url=redirect_url)
    
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, headers=NO_CACHE_HEADERS)
    
    return {"message": "Amazon Ads Manager API", "version": "1.0.0"}


@app.get("/uploads/blog/{filename}", include_in_schema=False)
async def redirect_legacy_blog_image(filename: str):
    return RedirectResponse(url=f"/api/blog/images/{filename}", status_code=301)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

if os.path.exists(FRONTEND_DIR):
    app.mount("/", NoCacheStaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
