from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional
import json
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from db.accounts_db import get_all_client_accounts, get_client_tokens

router = APIRouter()

SALT = b"amazon_ads_manager_v1"


class TokenExportRequest(BaseModel):
    password: str


class AccountTokenInfo(BaseModel):
    id: int
    name: str
    has_token: bool
    token_expires_at: Optional[str] = None


def derive_key(password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=100000,
    )
    key = kdf.derive(password.encode())
    return base64.urlsafe_b64encode(key)


@router.get("/accounts", response_model=List[AccountTokenInfo])
async def get_accounts_with_tokens():
    accounts = get_all_client_accounts()
    
    result = []
    for acc in accounts:
        token_data = get_client_tokens(acc["id"])
        expires_at = None
        if token_data and token_data.get("expires_at"):
            expires_at = str(token_data["expires_at"])
        
        result.append({
            "id": acc["id"],
            "name": acc.get("client_name", acc.get("name", "")),
            "has_token": token_data is not None,
            "token_expires_at": expires_at
        })
    
    return result


@router.post("/export")
async def export_tokens(request: TokenExportRequest):
    if len(request.password) < 4:
        raise HTTPException(status_code=400, detail="La password deve essere di almeno 4 caratteri")
    
    accounts = get_all_client_accounts()
    
    export_data = {
        "accounts": [],
        "exported_at": None
    }
    
    from datetime import datetime
    export_data["exported_at"] = datetime.now().isoformat()
    
    for acc in accounts:
        token_data = get_client_tokens(acc["id"])
        if token_data:
            account_export = {
                "account_id": acc["id"],
                "account_name": acc.get("client_name", acc.get("name", "")),
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_at": str(token_data.get("expires_at")) if token_data.get("expires_at") else None
            }
            export_data["accounts"].append(account_export)
    
    if not export_data["accounts"]:
        raise HTTPException(status_code=400, detail="Nessun account con token da esportare")
    
    json_data = json.dumps(export_data, indent=2)
    key = derive_key(request.password)
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(json_data.encode())
    
    return Response(
        content=encrypted_data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename=amazon_tokens_encrypted.bin"
        }
    )


