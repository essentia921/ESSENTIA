from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.core.security import decode_access_token
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import secrets

router = APIRouter()

ADMIN_EMAIL = "erba.francesco.mp@gmail.com"


async def require_admin(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Non autenticato")

    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token non valido")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Accesso non autorizzato")

    return user


@router.get("/users")
async def get_all_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "subscription_status": u.subscription_status,
            "subscription_id": u.subscription_id,
            "subscription_ends_at": u.subscription_ends_at.isoformat() if u.subscription_ends_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "has_password": bool(u.hashed_password),
            "google_id": bool(u.google_id),
        })
    return {"users": result, "total": len(result)}


@router.get("/users/{user_id}/details")
async def get_user_details(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT id, client_name, created_at FROM client_accounts 
        WHERE user_id = %s ORDER BY created_at DESC
    """, (user_id,))
    accounts = cur.fetchall()

    cur.execute("""
        SELECT DISTINCT ON (pb.asin, pb.marketplace)
               pb.asin, pb.marketplace, pb.profile_id,
               COALESCE(bec.title, pb.title) as title,
               bec.author, bec.image_url,
               bec.price, bec.print_cost as c_print, bec.royalty_net as r_net,
               bec.pages, bec.format, bec.acos_be, bec.acos_opt,
               ca.id as account_id, ca.client_name as account_name
        FROM profile_books pb
        JOIN client_profiles cp ON pb.profile_id = cp.profile_id
        JOIN client_accounts ca ON cp.client_account_id = ca.id
        LEFT JOIN book_economics_cache bec ON pb.asin = bec.asin AND pb.marketplace = bec.marketplace
        WHERE ca.user_id = %s
        ORDER BY pb.asin, pb.marketplace, bec.fetched_at DESC NULLS LAST
    """, (user_id,))
    books = cur.fetchall()

    cur.execute("""
        SELECT id, name, is_default, is_system,
               delta_excellent, delta_good, delta_above_be, delta_high,
               delta_low_impressions, delta_no_sales,
               low_impressions_threshold, max_clicks_no_sales, pause_on_clicks_enabled
        FROM autopilot_settings_profiles
        WHERE user_id = %s
        ORDER BY is_default DESC, name ASC
    """, (user_id,))
    settings_profiles = cur.fetchall()

    cur.close()
    conn.close()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "subscription_status": user.subscription_status,
            "subscription_ends_at": user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "accounts": [dict(a) for a in accounts],
        "books": [dict(b) for b in books],
        "settings_profiles": [dict(s) for s in settings_profiles],
    }


@router.get("/users/{user_id}/jobs")
async def get_user_jobs(user_id: int, admin: User = Depends(require_admin)):
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        WITH job_windows AS (
            SELECT j.id, j.account_id, j.created_at,
                   LEAD(j.created_at) OVER (PARTITION BY j.account_id ORDER BY j.created_at) as next_job_created
            FROM big_bang_jobs j
            JOIN client_accounts ca ON j.account_id = ca.id
            WHERE ca.user_id = %s
        )
        SELECT j.id, j.account_id, j.ad_product, j.status, j.current_phase, j.phase_status, j.phase_message,
               j.recurring_mode, j.recurring_interval_days, j.delay_hours,
               j.execute_at, j.executed_at, j.error_message, j.created_at, j.updated_at,
               j.next_run_at, j.last_completed_at, j.progress_pct,
               ca.client_name as account_name,
               COALESCE((SELECT COUNT(*) FROM planned_actions pa
                    WHERE pa.account_id = j.account_id
                    AND pa.created_at >= jw.created_at
                    AND (jw.next_job_created IS NULL OR pa.created_at < jw.next_job_created)
                    AND pa.status = 'PLANNED'), 0) as planned_count,
               COALESCE((SELECT COUNT(*) FROM planned_actions pa
                    WHERE pa.account_id = j.account_id
                    AND pa.created_at >= jw.created_at
                    AND (jw.next_job_created IS NULL OR pa.created_at < jw.next_job_created)
                    AND pa.status = 'EXECUTED'), 0) as executed_count,
               COALESCE((SELECT COUNT(*) FROM planned_actions pa
                    WHERE pa.account_id = j.account_id
                    AND pa.created_at >= jw.created_at
                    AND (jw.next_job_created IS NULL OR pa.created_at < jw.next_job_created)
                    AND pa.status = 'FAILED'), 0) as failed_count
        FROM big_bang_jobs j
        JOIN client_accounts ca ON j.account_id = ca.id
        JOIN job_windows jw ON jw.id = j.id
        WHERE ca.user_id = %s
        ORDER BY j.created_at DESC
        LIMIT 100
    """, (user_id, user_id))
    jobs = cur.fetchall()

    cur.close()
    conn.close()

    return {"jobs": [dict(j) for j in jobs], "total": len(jobs)}


@router.get("/users/{user_id}/jobs/{job_id}/actions")
async def get_job_actions(user_id: int, job_id: int, admin: User = Depends(require_admin)):
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT j.account_id, j.created_at,
               LEAD(j.created_at) OVER (PARTITION BY j.account_id ORDER BY j.created_at) as next_job_created
        FROM big_bang_jobs j
        JOIN client_accounts ca ON j.account_id = ca.id
        WHERE ca.user_id = %s
    """, (user_id,))
    windows = {r['account_id']: r for r in cur.fetchall() if True}
    
    cur.execute("SELECT account_id, created_at FROM big_bang_jobs WHERE id = %s", (job_id,))
    job_row = cur.fetchone()
    if not job_row:
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Job non trovato")

    cur.execute("""
        WITH job_window AS (
            SELECT j.created_at as job_start,
                   LEAD(j.created_at) OVER (PARTITION BY j.account_id ORDER BY j.created_at) as job_end
            FROM big_bang_jobs j
            WHERE j.account_id = %s
        )
        SELECT pa.id, pa.profile_id, pa.ad_product, pa.marketplace, pa.asin, pa.entity_type,
               pa.target_type, pa.keyword, pa.action_type, pa.current_bid, pa.proposed_bid,
               pa.bid_change_pct, pa.acos_target, pa.acos_actual, pa.spend, pa.sales,
               pa.clicks, pa.orders, pa.rationale, pa.status, pa.executed_at, pa.execution_error, pa.created_at
        FROM planned_actions pa
        WHERE pa.account_id = %s
          AND pa.created_at >= (SELECT job_start FROM job_window WHERE job_start = %s LIMIT 1)
          AND (pa.created_at < COALESCE((SELECT job_end FROM job_window WHERE job_start = %s LIMIT 1), NOW() + INTERVAL '100 years'))
        ORDER BY pa.created_at DESC
        LIMIT 500
    """, (job_row['account_id'], job_row['account_id'], job_row['created_at'], job_row['created_at']))
    actions = cur.fetchall()

    cur.close()
    conn.close()

    return {"actions": [dict(a) for a in actions], "total": len(actions)}


@router.get("/users/{user_id}/actions")
async def get_user_actions(user_id: int, admin: User = Depends(require_admin)):
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT pa.id, pa.profile_id, pa.ad_product, pa.marketplace, pa.asin, pa.entity_type,
               pa.target_type, pa.keyword, pa.action_type, pa.current_bid, pa.proposed_bid,
               pa.bid_change_pct, pa.acos_target, pa.acos_actual, pa.spend, pa.sales,
               pa.clicks, pa.orders, pa.rationale, pa.status, pa.executed_at, pa.execution_error, pa.created_at
        FROM planned_actions pa
        JOIN client_accounts ca ON pa.account_id = ca.id
        WHERE ca.user_id = %s
        ORDER BY pa.created_at DESC
        LIMIT 500
    """, (user_id,))
    actions = cur.fetchall()

    cur.close()
    conn.close()

    return {"actions": [dict(a) for a in actions], "total": len(actions)}


class SubscriptionAction(BaseModel):
    action: str


@router.post("/users/{user_id}/subscription")
async def toggle_subscription(user_id: int, data: SubscriptionAction, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    if data.action == "activate":
        user.subscription_status = "active"
        user.role = "subscriber"
        if not user.subscription_ends_at or user.subscription_ends_at < datetime.now(timezone.utc):
            user.subscription_ends_at = datetime.now(timezone.utc) + timedelta(days=30)
    elif data.action == "deactivate":
        user.subscription_status = "none"
        user.role = "user"
    else:
        raise HTTPException(status_code=400, detail="Azione non valida. Usa 'activate' o 'deactivate'")

    db.commit()
    return {
        "message": f"Abbonamento {'attivato' if data.action == 'activate' else 'disattivato'} per {user.email}",
        "subscription_status": user.subscription_status
    }


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(user_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from backend.app.models.password_reset import PasswordResetToken
    from backend.app.services.email_service import send_password_reset_email
    import os

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    if not user.hashed_password:
        raise HTTPException(status_code=400, detail="Utente registrato con Google, non ha password da resettare")

    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    reset_token = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    db.add(reset_token)
    db.commit()

    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        base_url = str(request.base_url).rstrip("/")

    reset_link = f"{base_url}/reset-password?token={token}"

    send_password_reset_email(ADMIN_EMAIL, reset_link)

    return {"message": f"Link di reset password inviato a {ADMIN_EMAIL}", "user_email": user.email}


@router.get("/users/{user_id}/export")
async def export_user_data(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from db.accounts_db import get_connection
    from psycopg2.extras import RealDictCursor
    from fastapi.responses import JSONResponse
    import json

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id, client_name, created_at FROM client_accounts WHERE user_id = %s", (user_id,))
    accounts = cur.fetchall()
    account_ids = [a['id'] for a in accounts]

    cur.execute("""
        SELECT DISTINCT ON (pb.asin, pb.marketplace)
               pb.asin, pb.marketplace, pb.profile_id,
               COALESCE(bec.title, pb.title) as title,
               bec.author, bec.image_url,
               bec.price, bec.print_cost as c_print, bec.royalty_net as r_net,
               bec.pages, bec.format, bec.acos_be, bec.acos_opt, bec.fetched_at as created_at
        FROM profile_books pb
        JOIN client_profiles cp ON pb.profile_id = cp.profile_id
        JOIN client_accounts ca ON cp.client_account_id = ca.id
        LEFT JOIN book_economics_cache bec ON pb.asin = bec.asin AND pb.marketplace = bec.marketplace
        WHERE ca.user_id = %s
        ORDER BY pb.asin, pb.marketplace, bec.fetched_at DESC NULLS LAST
    """, (user_id,))
    books = cur.fetchall()

    cur.execute("""
        SELECT id, name, is_default, is_system,
               delta_excellent, delta_good, delta_above_be, delta_high,
               delta_low_impressions, delta_no_sales,
               low_impressions_threshold, max_clicks_no_sales, pause_on_clicks_enabled
        FROM autopilot_settings_profiles WHERE user_id = %s
    """, (user_id,))
    settings_profiles = cur.fetchall()

    jobs = []
    actions = []
    if account_ids:
        placeholders = ','.join(['%s'] * len(account_ids))
        cur.execute(f"""
            SELECT id, account_id, ad_product, status, current_phase, phase_status, phase_message,
                   recurring_mode, recurring_interval_days, delay_hours,
                   execute_at, executed_at, error_message, created_at, next_run_at, progress_pct
            FROM big_bang_jobs WHERE account_id IN ({placeholders})
            ORDER BY created_at DESC
        """, account_ids)
        jobs = cur.fetchall()

        cur.execute(f"""
            SELECT id, profile_id, ad_product, marketplace, asin, entity_type, target_type,
                   keyword, action_type, current_bid, proposed_bid, bid_change_pct,
                   acos_target, acos_actual, spend, sales, clicks, orders,
                   rationale, status, executed_at, created_at
            FROM planned_actions WHERE account_id IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT 2000
        """, account_ids)
        actions = cur.fetchall()

    cur.close()
    conn.close()

    def serialize(obj):
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        from decimal import Decimal
        if isinstance(obj, Decimal):
            return float(obj)
        return str(obj)

    export_data = {
        "export_date": datetime.now().isoformat(),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "subscription_status": user.subscription_status,
            "subscription_ends_at": user.subscription_ends_at.isoformat() if user.subscription_ends_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "accounts": [dict(a) for a in accounts],
        "books": [dict(b) for b in books],
        "settings_profiles": [dict(s) for s in settings_profiles],
        "jobs": [dict(j) for j in jobs],
        "actions": [dict(a) for a in actions],
    }

    content = json.dumps(export_data, default=serialize, indent=2, ensure_ascii=False)
    return JSONResponse(
        content=json.loads(content),
        headers={"Content-Disposition": f"attachment; filename=user_{user_id}_export.json"}
    )
