from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import stripe
import logging
import secrets
from datetime import datetime, timezone, timedelta
from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import decode_access_token, get_password_hash
from backend.app.models.user import User, SubscriptionStatus
from backend.app.models.password_reset import PasswordResetToken

logger = logging.getLogger(__name__)

router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY


class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str
    affiliate_code: Optional[str] = None


class SubscriptionResponse(BaseModel):
    status: str
    current_period_end: Optional[str]
    cancel_at_period_end: bool


def get_current_user_from_token(authorization: str = Header(...), db: Session = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name,
            metadata={"user_id": str(user.id)}
        )
        user.stripe_customer_id = customer.id
        db.commit()
    
    session_metadata: dict = {"user_id": str(user.id)}
    if request.affiliate_code:
        session_metadata["affiliate_code"] = request.affiliate_code.upper().strip()

    checkout_session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{
            "price": settings.STRIPE_PRICE_ID,
            "quantity": 1,
        }],
        mode="subscription",
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        metadata=session_metadata
    )
    
    return {"checkout_url": checkout_session.url}


@router.get("/status", response_model=SubscriptionResponse)
async def get_subscription_status(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    
    return {
        "status": user.subscription_status,
        "current_period_end": str(user.subscription_ends_at) if user.subscription_ends_at else None,
        "cancel_at_period_end": False
    }


async def handle_stripe_webhook(request: Request, db: Session):
    """Core webhook handler logic"""
    logger.info("=== STRIPE WEBHOOK RECEIVED ===")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    logger.info(f"Signature header present: {bool(sig_header)}")
    logger.info(f"Payload size: {len(payload)} bytes")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        logger.info(f"Event verified successfully: {event['type']}")
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event["type"]
    logger.info(f"Processing event type: {event_type}")
    
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        affiliate_code = metadata.get("affiliate_code")
        subscription_id = session.get("subscription")
        customer_id = session.get("customer")
        stripe_session_id = session.get("id")
        amount_total_cents = session.get("amount_total") or 0
        # customer_email may be in different fields depending on Stripe session mode
        customer_email = (
            session.get("customer_email")
            or (session.get("customer_details") or {}).get("email")
        )
        # Final fallback: retrieve Stripe customer object if we have an ID
        if not customer_email and customer_id:
            try:
                stripe_customer = stripe.Customer.retrieve(customer_id)
                customer_email = stripe_customer.get("email")
            except Exception as _ce:
                logger.warning(f"Could not retrieve Stripe customer {customer_id}: {_ce}")

        logger.info(f"Checkout completed - user_id: {user_id}, email: {customer_email}, subscription_id: {subscription_id}, customer_id: {customer_id}, affiliate_code: {affiliate_code}")

        activated_user: User = None

        if user_id:
            # Standard flow: authenticated user checkout
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                user.subscription_status = SubscriptionStatus.ACTIVE.value
                user.subscription_id = subscription_id
                user.stripe_customer_id = customer_id
                db.commit()
                logger.info(f"User {user_id} subscription activated!")
                activated_user = user
            else:
                logger.error(f"User {user_id} not found in database")
        else:
            # Affiliate direct-checkout flow: no pre-existing user session
            if customer_email:
                existing_user = db.query(User).filter(User.email == customer_email).first()
                if existing_user:
                    # User already has an account — just activate subscription
                    existing_user.subscription_status = SubscriptionStatus.ACTIVE.value
                    existing_user.subscription_id = subscription_id
                    existing_user.stripe_customer_id = customer_id
                    db.commit()
                    logger.info(f"Existing user {customer_email} subscription activated via affiliate checkout")
                    activated_user = existing_user
                else:
                    # New user: create account and send activation email
                    try:
                        temp_password = secrets.token_urlsafe(32)
                        new_user = User(
                            email=customer_email,
                            hashed_password=get_password_hash(temp_password),
                            is_verified=True,
                            is_active=True,
                            subscription_status=SubscriptionStatus.ACTIVE.value,
                            subscription_id=subscription_id,
                            stripe_customer_id=customer_id,
                        )
                        db.add(new_user)
                        db.commit()
                        db.refresh(new_user)
                        activated_user = new_user
                        logger.info(f"New user {customer_email} created via affiliate checkout (id={new_user.id})")

                        # Create a 48-hour password-set token and send activation email
                        token = secrets.token_urlsafe(32)
                        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
                        reset_token = PasswordResetToken(
                            user_id=new_user.id,
                            token=token,
                            expires_at=expires_at,
                        )
                        db.add(reset_token)
                        db.commit()

                        from backend.app.services.email_service import send_password_reset_email
                        activate_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
                        send_password_reset_email(
                            to_email=customer_email,
                            reset_link=activate_link,
                        )
                        logger.info(f"Activation email sent to {customer_email}")
                    except Exception as e:
                        logger.error(f"Error creating user from affiliate checkout: {e}")
            else:
                logger.error("No user_id and no customer_email in checkout session")

        if affiliate_code:
            try:
                from backend.app.models.affiliate import Affiliate, Referral, TIER_COMMISSION
                from backend.app.services.email_service import send_affiliate_referral_notification

                aff = db.query(Affiliate).filter(
                    Affiliate.code == affiliate_code.upper(),
                    Affiliate.is_active == True
                ).first()

                if aff:
                    amount_paid = amount_total_cents / 100.0
                    commission_rate = TIER_COMMISSION.get(aff.tier, 0.10)
                    commission = round(amount_paid * commission_rate, 2)

                    existing = db.query(Referral).filter(Referral.stripe_session_id == stripe_session_id).first()
                    if not existing:
                        referral = Referral(
                            affiliate_id=aff.id,
                            referred_user_id=activated_user.id if activated_user else None,
                            stripe_session_id=stripe_session_id,
                            amount_paid=amount_paid,
                            commission=commission,
                            status="pending",
                        )
                        db.add(referral)
                        aff.balance_pending = round(aff.balance_pending + commission, 2)
                        aff.total_earned = round(aff.total_earned + commission, 2)
                        db.commit()
                        logger.info(f"Affiliate referral created: code={affiliate_code}, commission=${commission}")

                        aff_user = db.query(User).filter(User.id == aff.user_id).first()
                        send_affiliate_referral_notification(
                            affiliate_email=aff_user.email if aff_user else affiliate_code,
                            affiliate_code=affiliate_code,
                            commission=commission,
                            amount_paid=amount_paid,
                            tier=aff.tier,
                        )
                else:
                    logger.warning(f"Affiliate code {affiliate_code} not found or inactive")
            except Exception as e:
                logger.error(f"Error processing affiliate referral: {e}")
    
    elif event_type == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        
        logger.info(f"Subscription updated - customer: {customer_id}, status: {status}")
        
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            if status == "active":
                user.subscription_status = SubscriptionStatus.ACTIVE.value
            elif status == "past_due":
                user.subscription_status = SubscriptionStatus.PAST_DUE.value
            elif status == "canceled":
                user.subscription_status = SubscriptionStatus.CANCELED.value
            db.commit()
            logger.info(f"User subscription status updated to: {status}")
    
    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription.get("customer")
        
        logger.info(f"Subscription deleted - customer: {customer_id}")
        
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.subscription_status = SubscriptionStatus.NONE.value
            user.subscription_id = None
            db.commit()
            logger.info("User subscription canceled")
    
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        
        logger.info(f"Payment failed - customer: {customer_id}")
        
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.subscription_status = SubscriptionStatus.PAST_DUE.value
            db.commit()
            logger.info("User marked as past due")
    
    else:
        logger.info(f"Unhandled event type: {event_type}")
    
    return {"received": True}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook endpoint at /api/subscriptions/webhook"""
    return await handle_stripe_webhook(request, db)


@router.post("/stripe")
async def stripe_webhook_alt(request: Request, db: Session = Depends(get_db)):
    """Webhook endpoint at /api/webhooks/stripe"""
    return await handle_stripe_webhook(request, db)


@router.post("/cancel")
async def cancel_subscription(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    
    if not user.subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription")
    
    stripe.Subscription.modify(
        user.subscription_id,
        cancel_at_period_end=True
    )
    
    return {"message": "Subscription will be canceled at the end of the billing period"}


class PortalRequest(BaseModel):
    return_url: str


@router.post("/customer-portal")
async def create_customer_portal_session(
    request: PortalRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Nessun account Stripe associato")
    
    portal_session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=request.return_url
    )
    
    return {"portal_url": portal_session.url}


@router.get("/details")
async def get_subscription_details(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_token(authorization, db)
    
    subscription_data = {
        "status": user.subscription_status,
        "current_period_end": None,
        "cancel_at_period_end": False,
        "plan_name": None,
        "amount": None,
        "currency": None,
        "interval": None
    }
    
    if user.subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(user.subscription_id)
            subscription_data["current_period_end"] = subscription.current_period_end
            subscription_data["cancel_at_period_end"] = subscription.cancel_at_period_end
            
            if subscription.items.data:
                price = subscription.items.data[0].price
                subscription_data["plan_name"] = price.nickname or "Piano Pro"
                subscription_data["amount"] = price.unit_amount / 100 if price.unit_amount else None
                subscription_data["currency"] = price.currency.upper()
                subscription_data["interval"] = price.recurring.interval if price.recurring else None
        except Exception as e:
            logger.error(f"Error fetching subscription from Stripe: {e}")
    
    return subscription_data


@router.get("/invoices")
async def get_invoices(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
    limit: int = 10
):
    user = get_current_user_from_token(authorization, db)
    
    if not user.stripe_customer_id:
        return {"invoices": []}
    
    try:
        invoices = stripe.Invoice.list(
            customer=user.stripe_customer_id,
            limit=limit
        )
        
        invoice_list = []
        for inv in invoices.data:
            invoice_list.append({
                "id": inv.id,
                "number": inv.number,
                "amount": inv.amount_paid / 100 if inv.amount_paid else 0,
                "currency": inv.currency.upper() if inv.currency else "EUR",
                "status": inv.status,
                "created": inv.created,
                "invoice_pdf": inv.invoice_pdf,
                "hosted_invoice_url": inv.hosted_invoice_url
            })
        
        return {"invoices": invoice_list}
    except Exception as e:
        logger.error(f"Error fetching invoices: {e}")
        return {"invoices": []}
