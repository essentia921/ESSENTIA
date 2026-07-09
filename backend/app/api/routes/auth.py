from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import timedelta, datetime, timezone
import httpx
import secrets
import urllib.parse
import os
import logging

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import (
    verify_password, 
    get_password_hash, 
    create_access_token,
    decode_access_token
)
from backend.app.models.user import User, UserRole
from backend.app.models.email_verification import EmailVerificationToken
from backend.app.models.password_reset import PasswordResetToken
from backend.app.services.email_service import send_verification_email, send_password_reset_email

logger = logging.getLogger(__name__)
router = APIRouter()

oauth_states: dict[str, bool] = {}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    subscription_status: str
    has_password: bool = False
    
    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    message: str
    email: str


@router.post("/register", response_model=RegisterResponse)
async def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        if not existing_user.is_verified:
            db.query(EmailVerificationToken).filter(
                EmailVerificationToken.user_id == existing_user.id
            ).delete()
            db.delete(existing_user)
            db.commit()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=UserRole.USER.value,
        is_verified=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    verification_token = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(verification_token)
    db.commit()
    
    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        base_url = str(request.base_url).rstrip("/")
    
    verification_link = f"{base_url}/verify-email?token={token}"
    
    email_sent = send_verification_email(
        to_email=user.email,
        verification_link=verification_link,
        user_name=user.full_name
    )
    
    if not email_sent:
        logger.warning(f"Failed to send verification email to {user.email}")
    
    return {
        "message": "Registrazione completata. Controlla la tua email per verificare l'account.",
        "email": user.email
    }


@router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    verification = db.query(EmailVerificationToken).filter(
        EmailVerificationToken.token == token
    ).first()
    
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token di verifica non valido"
        )
    
    if verification.expires_at < datetime.now(timezone.utc):
        db.delete(verification)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token di verifica scaduto. Registrati di nuovo."
        )
    
    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato"
        )
    
    user.is_verified = True
    db.delete(verification)
    db.commit()
    
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    return RedirectResponse(url=f"/auth/callback?token={access_token}")


@router.post("/resend-verification")
async def resend_verification(email: EmailStr, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        return {"message": "Se l'email esiste, riceverai un link di verifica."}
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email già verificata. Effettua il login."
        )
    
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id
    ).delete()
    
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    verification_token = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at
    )
    db.add(verification_token)
    db.commit()
    
    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not base_url:
        base_url = str(request.base_url).rstrip("/")
    
    verification_link = f"{base_url}/verify-email?token={token}"
    
    send_verification_email(
        to_email=user.email,
        verification_link=verification_link,
        user_name=user.full_name
    )
    
    return {"message": "Se l'email esiste, riceverai un link di verifica."}


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide"
        )
    
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide"
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email non verificata. Controlla la tua casella di posta."
        )
    
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "subscription_status": user.subscription_status
        }
    }


@router.get("/google")
async def google_login():
    state = secrets.token_urlsafe(32)
    oauth_states[state] = True
    
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "consent"
    }
    
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(
    code: str, 
    state: Optional[str] = None,
    db: Session = Depends(get_db)
):
    if not state or state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid OAuth state - possible CSRF attack")
    
    del oauth_states[state]
    
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Google token")
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        
        user_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Google user info")
        
        google_user = user_response.json()
    
    user = db.query(User).filter(User.google_id == google_user["id"]).first()
    
    if not user:
        user = db.query(User).filter(User.email == google_user["email"]).first()
        if user:
            user.google_id = google_user["id"]
            user.picture = google_user.get("picture")
            db.commit()
        else:
            user = User(
                email=google_user["email"],
                full_name=google_user.get("name"),
                picture=google_user.get("picture"),
                google_id=google_user["id"],
                is_verified=True,
                role=UserRole.USER.value
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    
    jwt_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    redirect_url = f"{settings.FRONTEND_URL}/auth/callback?token={jwt_token}"
    return RedirectResponse(url=redirect_url)


@router.get("/me", response_model=UserResponse)
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        subscription_status=user.subscription_status,
        has_password=bool(user.hashed_password)
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
    password: str


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    
    if user and user.hashed_password:
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id
        ).delete()
        
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires_at
        )
        db.add(reset_token)
        db.commit()
        
        base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        if not base_url:
            base_url = str(request.base_url).rstrip("/")
        
        reset_link = f"{base_url}/reset-password?token={token}"
        
        email_sent = send_password_reset_email(
            to_email=user.email,
            reset_link=reset_link,
            user_name=user.full_name
        )
        
        if not email_sent:
            logger.warning(f"Failed to send password reset email to {user.email}")
    
    return {"message": "Se l'email esiste, riceverai un link per reimpostare la password."}


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == data.token
    ).first()
    
    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token non valido o scaduto"
        )
    
    if reset_token.expires_at < datetime.now(timezone.utc):
        db.delete(reset_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token scaduto. Richiedi un nuovo link."
        )
    
    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente non trovato"
        )
    
    user.hashed_password = get_password_hash(data.new_password)
    db.delete(reset_token)
    db.commit()
    
    return {"message": "Password reimpostata con successo"}


def get_current_user_from_request(request: Request, db: Session) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Non autenticato")
    
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Token non valido")
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    
    return user


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest, 
    request: Request, 
    db: Session = Depends(get_db)
):
    user = get_current_user_from_request(request, db)
    
    if not user.hashed_password:
        raise HTTPException(
            status_code=400, 
            detail="Account Google. Usa la funzione 'Password dimenticata' per impostare una password."
        )
    
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(
            status_code=400, 
            detail="Password attuale non corretta"
        )
    
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail="La nuova password deve avere almeno 6 caratteri"
        )
    
    user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    
    return {"message": "Password aggiornata con successo"}


@router.put("/profile")
async def update_profile(
    data: UpdateProfileRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_request(request, db)
    
    if data.full_name is not None:
        user.full_name = data.full_name
    
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "subscription_status": user.subscription_status
    }


@router.post("/change-email")
async def change_email(
    data: ChangeEmailRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_request(request, db)
    
    if not user.hashed_password:
        raise HTTPException(
            status_code=400,
            detail="Account Google non può cambiare email"
        )
    
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=400,
            detail="Password non corretta"
        )
    
    existing = db.query(User).filter(User.email == data.new_email).first()
    if existing and existing.id != user.id:
        raise HTTPException(
            status_code=400,
            detail="Email già in uso"
        )
    
    user.email = data.new_email
    db.commit()
    
    new_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    return {
        "message": "Email aggiornata con successo",
        "access_token": new_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "subscription_status": user.subscription_status
        }
    }


@router.delete("/account")
async def delete_account(
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_request(request, db)
    
    db.query(EmailVerificationToken).filter(
        EmailVerificationToken.user_id == user.id
    ).delete()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id
    ).delete()
    
    db.delete(user)
    db.commit()
    
    return {"message": "Account eliminato con successo"}
