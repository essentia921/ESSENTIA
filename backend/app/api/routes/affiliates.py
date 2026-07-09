from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import stripe

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.models.affiliate import Affiliate, Referral, TIER_COMMISSION
from backend.app.api.routes.admin import require_admin

router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreateAffiliateRequest(BaseModel):
    user_id: int
    code: str
    tier: str = "platinum"
    notes: Optional[str] = None


class UpdateAffiliateRequest(BaseModel):
    tier: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
async def list_affiliates(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    affiliates = db.query(Affiliate).order_by(Affiliate.created_at.desc()).all()
    result = []
    for aff in affiliates:
        user = db.query(User).filter(User.id == aff.user_id).first()
        referral_count = db.query(Referral).filter(Referral.affiliate_id == aff.id).count()
        result.append({
            "id": aff.id,
            "user_id": aff.user_id,
            "user_email": user.email if user else "-",
            "user_name": user.full_name if user else "-",
            "code": aff.code,
            "tier": aff.tier,
            "is_active": aff.is_active,
            "balance_pending": round(aff.balance_pending, 2),
            "total_earned": round(aff.total_earned, 2),
            "notes": aff.notes,
            "referral_count": referral_count,
            "created_at": aff.created_at.isoformat() if aff.created_at else None,
        })

    total_pending = sum(a["balance_pending"] for a in result)
    total_paid = sum(a["total_earned"] - a["balance_pending"] for a in result)
    active_count = sum(1 for a in result if a["is_active"])

    return {
        "affiliates": result,
        "stats": {
            "total": len(result),
            "active": active_count,
            "total_pending": round(total_pending, 2),
            "total_paid": round(total_paid, 2),
        }
    }


@router.post("")
async def create_affiliate(
    data: CreateAffiliateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    existing_code = db.query(Affiliate).filter(Affiliate.code == data.code.upper()).first()
    if existing_code:
        raise HTTPException(status_code=400, detail="Codice affiliato già in uso")

    existing_user = db.query(Affiliate).filter(Affiliate.user_id == data.user_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Questo utente è già un affiliato")

    if data.tier not in TIER_COMMISSION:
        raise HTTPException(status_code=400, detail="Tier non valido. Usa 'platinum' o 'diamond'")

    aff = Affiliate(
        user_id=data.user_id,
        code=data.code.upper(),
        tier=data.tier,
        notes=data.notes,
        is_active=True,
        balance_pending=0.0,
        total_earned=0.0,
    )
    db.add(aff)
    db.commit()
    db.refresh(aff)
    return {"message": f"Affiliato creato con codice {aff.code}", "id": aff.id, "code": aff.code}


@router.patch("/{affiliate_id}")
async def update_affiliate(
    affiliate_id: int,
    data: UpdateAffiliateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    aff = db.query(Affiliate).filter(Affiliate.id == affiliate_id).first()
    if not aff:
        raise HTTPException(status_code=404, detail="Affiliato non trovato")

    if data.tier is not None:
        if data.tier not in TIER_COMMISSION:
            raise HTTPException(status_code=400, detail="Tier non valido")
        aff.tier = data.tier
    if data.notes is not None:
        aff.notes = data.notes
    if data.is_active is not None:
        aff.is_active = data.is_active

    db.commit()
    return {"message": "Affiliato aggiornato"}


@router.get("/{affiliate_id}/referrals")
async def get_affiliate_referrals(
    affiliate_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    aff = db.query(Affiliate).filter(Affiliate.id == affiliate_id).first()
    if not aff:
        raise HTTPException(status_code=404, detail="Affiliato non trovato")

    referrals = db.query(Referral).filter(
        Referral.affiliate_id == affiliate_id
    ).order_by(Referral.created_at.desc()).all()

    result = []
    for ref in referrals:
        referred_user = db.query(User).filter(User.id == ref.referred_user_id).first() if ref.referred_user_id else None
        result.append({
            "id": ref.id,
            "referred_user_email": referred_user.email if referred_user else "-",
            "stripe_session_id": ref.stripe_session_id,
            "amount_paid": round(ref.amount_paid, 2),
            "commission": round(ref.commission, 2),
            "status": ref.status,
            "created_at": ref.created_at.isoformat() if ref.created_at else None,
            "paid_at": ref.paid_at.isoformat() if ref.paid_at else None,
        })

    return {"referrals": result, "total": len(result)}


@router.get("/checkout/{code}")
async def affiliate_checkout(code: str, db: Session = Depends(get_db)):
    """Public endpoint: redirects directly to Stripe Checkout for the given affiliate code."""
    aff = db.query(Affiliate).filter(
        Affiliate.code == code.upper(),
        Affiliate.is_active == True
    ).first()

    if not aff:
        raise HTTPException(status_code=404, detail="Codice affiliato non trovato o non attivo")

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price": settings.STRIPE_PRICE_ID,
            "quantity": 1,
        }],
        mode="subscription",
        success_url=f"{settings.FRONTEND_URL}/purchase-success",
        cancel_url=f"{settings.FRONTEND_URL}/",
        metadata={"affiliate_code": code.upper()},
    )

    return RedirectResponse(url=checkout_session.url, status_code=302)


@router.patch("/referrals/{referral_id}/mark-paid")
async def mark_referral_paid(
    referral_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ref = db.query(Referral).filter(Referral.id == referral_id).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Referral non trovato")

    if ref.status != "pending":
        raise HTTPException(status_code=400, detail=f"Referral non in stato 'pending' (stato attuale: {ref.status})")

    aff = db.query(Affiliate).filter(Affiliate.id == ref.affiliate_id).first()

    ref.status = "paid"
    ref.paid_at = datetime.now(timezone.utc)

    if aff:
        aff.balance_pending = max(0.0, round(aff.balance_pending - ref.commission, 2))

    db.commit()
    return {"message": f"Referral #{referral_id} segnato come pagato. Commissione: ${ref.commission:.2f}"}
