"""
Amazon Ads OAuth Router
Handles OAuth flow for connecting Amazon Ads accounts, including:
- Direct connection (admin connects their own accounts)
- Client onboarding (shareable links for clients to connect their accounts)

OAuth state is stored in the DB so it survives server restarts and works
correctly across multiple workers/processes and between dev/prod environments.
"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
import httpx

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter()


def get_amazon_auth_url(region: str = "eu") -> str:
    """Get the Amazon authorization URL based on region."""
    region_urls = {
        "na": "https://www.amazon.com/ap/oa",
        "eu": "https://eu.account.amazon.com/ap/oa",
        "fe": "https://apac.account.amazon.com/ap/oa"
    }
    return region_urls.get(region, region_urls["eu"])


def get_amazon_token_url(region: str = "eu") -> str:
    """Get the Amazon token URL based on region."""
    region_urls = {
        "na": "https://api.amazon.com/auth/o2/token",
        "eu": "https://api.amazon.co.uk/auth/o2/token",
        "fe": "https://api.amazon.co.jp/auth/o2/token"
    }
    return region_urls.get(region, region_urls["eu"])


def verify_user_from_request(request: Request, token_param: Optional[str] = None) -> int:
    """
    Verify user authentication from request and return user_id.
    Supports: Authorization header, cookie, or query parameter (for OAuth redirects).
    """
    token = None

    auth_header = request.headers.get("Authorization") if request else None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif token_param:
        token = token_param
    elif request:
        token = request.cookies.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return int(payload.get("sub"))


@router.post("/amazon/init")
async def amazon_init(
    account_id: int = Query(..., description="Client account ID to connect"),
    region: str = Query("eu", description="Amazon region (na, eu, fe)"),
    request: Request = None
):
    """
    Initialize Amazon OAuth flow - creates a one-time redirect token stored in DB.
    Returns a temporary token that can be used once to start the OAuth flow.
    """
    from db.accounts_db import get_client_account, create_oauth_pending

    user_id = verify_user_from_request(request)

    account = get_client_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.get("user_id") and account.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to connect this account")

    temp_token = secrets.token_urlsafe(32)
    create_oauth_pending(temp_token, account_id, region, user_id)

    return {"redirect_token": temp_token}


@router.get("/amazon")
async def amazon_login(
    redirect_token: str = Query(..., description="One-time redirect token from /amazon/init")
):
    """
    Start Amazon OAuth flow using a one-time redirect token (read from DB).
    """
    from db.accounts_db import get_and_delete_oauth_pending, create_oauth_state

    token_data = get_and_delete_oauth_pending(redirect_token)
    if not token_data:
        raise HTTPException(status_code=400, detail="Invalid or expired redirect token")

    account_id = token_data["account_id"]
    region = token_data["region"]

    state = secrets.token_urlsafe(32)
    create_oauth_state(state, account_id, region, flow_type='direct')

    # On dev (replit), the callback is always received by production (essentia-ads.io)
    # because Amazon only allows registered redirect URIs. State is shared via DB.
    redirect_uri = settings.AMAZON_ADS_REDIRECT_URI

    import urllib.parse
    params = {
        "client_id": settings.AMAZON_ADS_CLIENT_ID,
        "scope": "advertising::campaign_management",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state
    }

    auth_url = f"{get_amazon_auth_url(region)}?{urllib.parse.urlencode(params)}"

    logger.info(f"Starting Amazon OAuth for account {account_id}, region {region}")
    return RedirectResponse(url=auth_url)


@router.get("/amazon/callback")
async def amazon_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Handle Amazon OAuth callback.
    Exchanges authorization code for access/refresh tokens.
    State is read from DB so it works across any server instance.
    """
    from db.accounts_db import save_client_tokens, get_onboarding_token, mark_onboarding_used, get_and_delete_oauth_state

    state_data = get_and_delete_oauth_state(state)
    if not state_data:
        logger.error(f"Invalid or expired OAuth state: {state[:20]}...")
        raise HTTPException(status_code=400, detail="Invalid OAuth state - session expired or invalid")

    account_id = state_data.get("account_id")
    region = state_data.get("region", "eu")
    flow_type = state_data.get("flow_type", "direct")
    onboarding_token = state_data.get("onboarding_token")

    redirect_uri = settings.AMAZON_ADS_REDIRECT_URI

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            get_amazon_token_url(region),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.AMAZON_ADS_CLIENT_ID,
                "client_secret": settings.AMAZON_ADS_CLIENT_SECRET
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if token_response.status_code != 200:
            logger.error(f"Amazon token exchange failed: {token_response.text}")
            error_redirect = f"{settings.FRONTEND_URL}/accounts?error=amazon_auth_failed"
            return RedirectResponse(url=error_redirect)

        tokens = token_response.json()

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    expires_at = datetime.now() + timedelta(seconds=expires_in)

    save_client_tokens(account_id, access_token, refresh_token, expires_at)

    logger.info(f"Amazon OAuth successful for account {account_id}")

    if flow_type == "onboarding" and onboarding_token:
        mark_onboarding_used(onboarding_token, account_id)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/onboarding/success")

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/accounts?connected={account_id}")


@router.post("/onboarding/create")
async def create_onboarding_link(
    client_name: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Create a shareable onboarding link for a client.
    """
    from db.accounts_db import create_onboarding_token

    auth_header = request.headers.get("Authorization") if request else None
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = int(payload.get("sub"))

    onboarding_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=7)

    create_onboarding_token(onboarding_token, user_id, client_name, expires_at)

    base_url = settings.FRONTEND_URL
    onboarding_url = f"{base_url}/onboarding/{onboarding_token}"

    logger.info(f"Created onboarding link for client '{client_name}' by user {user_id}")

    return {
        "token": onboarding_token,
        "url": onboarding_url,
        "expires_at": expires_at.isoformat(),
        "client_name": client_name
    }


@router.get("/onboarding/{token}")
async def get_onboarding_info(token: str):
    """
    Get information about an onboarding token.
    """
    from db.accounts_db import get_onboarding_token

    onboarding = get_onboarding_token(token)

    if not onboarding:
        raise HTTPException(status_code=404, detail="Link non valido o scaduto")

    if onboarding.get("used_at"):
        raise HTTPException(status_code=400, detail="Questo link è già stato utilizzato")

    if datetime.now() > onboarding.get("expires_at"):
        raise HTTPException(status_code=400, detail="Questo link è scaduto")

    return {
        "client_name": onboarding.get("client_name"),
        "expires_at": onboarding.get("expires_at").isoformat() if onboarding.get("expires_at") else None
    }


@router.get("/onboarding/{token}/start")
async def start_onboarding_oauth(
    token: str,
    region: str = Query("eu")
):
    """
    Start Amazon OAuth from an onboarding link.
    """
    from db.accounts_db import get_onboarding_token, create_client_account, create_oauth_state

    onboarding = get_onboarding_token(token)

    if not onboarding:
        raise HTTPException(status_code=404, detail="Link non valido o scaduto")

    if onboarding.get("used_at"):
        raise HTTPException(status_code=400, detail="Questo link è già stato utilizzato")

    if datetime.now() > onboarding.get("expires_at"):
        raise HTTPException(status_code=400, detail="Questo link è scaduto")

    user_id = onboarding.get("user_id")
    client_name = onboarding.get("client_name")

    account_id = create_client_account(user_id, client_name)

    state = secrets.token_urlsafe(32)
    create_oauth_state(state, account_id, region, flow_type='onboarding', onboarding_token=token)

    redirect_uri = settings.AMAZON_ADS_REDIRECT_URI

    import urllib.parse
    params = {
        "client_id": settings.AMAZON_ADS_CLIENT_ID,
        "scope": "advertising::campaign_management",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state
    }

    auth_url = f"{get_amazon_auth_url(region)}?{urllib.parse.urlencode(params)}"

    logger.info(f"Starting onboarding OAuth for client '{client_name}', account {account_id}")
    return RedirectResponse(url=auth_url)


@router.get("/onboarding/list")
async def list_onboarding_links(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    List all onboarding links created by the current user.
    """
    from db.accounts_db import get_user_onboarding_tokens

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = int(payload.get("sub"))

    tokens = get_user_onboarding_tokens(user_id)

    return [{
        "token": t["token"],
        "client_name": t["client_name"],
        "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
        "expires_at": t["expires_at"].isoformat() if t.get("expires_at") else None,
        "used_at": t["used_at"].isoformat() if t.get("used_at") else None,
        "is_used": t.get("used_at") is not None,
        "is_expired": datetime.now() > t["expires_at"] if t.get("expires_at") else False,
        "url": f"{settings.FRONTEND_URL}/onboarding/{t['token']}"
    } for t in tokens]
