from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from backend.app.core.database import get_db
from backend.app.api.routes.auth import get_current_user
from backend.app.models.user import User

router = APIRouter()


class AccountCreate(BaseModel):
    name: str


class AccountRename(BaseModel):
    name: str


class AccountResponse(BaseModel):
    id: int
    name: str
    has_token: bool
    
    class Config:
        from_attributes = True


@router.get("/", response_model=List[AccountResponse])
async def get_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from db.accounts_db import get_all_client_accounts, get_client_tokens
    accounts = get_all_client_accounts(user_id=current_user.id)
    
    result = []
    for acc in accounts:
        token_data = get_client_tokens(acc["id"])
        result.append({
            "id": acc["id"],
            "name": acc.get("client_name", acc.get("name", "")),
            "has_token": token_data is not None
        })
    
    return result


@router.post("/", response_model=AccountResponse)
async def create_account(
    account: AccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from db.accounts_db import create_client_account
    new_account = create_client_account(account.name, user_id=current_user.id)
    
    if not new_account:
        raise HTTPException(status_code=400, detail="Failed to create account")
    
    return {
        "id": new_account.get("id"),
        "name": new_account.get("client_name", account.name),
        "has_token": False
    }


@router.put("/{account_id}", response_model=AccountResponse)
async def rename_account(
    account_id: int,
    account: AccountRename,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from db.accounts_db import rename_client_account, get_client_tokens
    
    if not account.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    
    updated = rename_client_account(account_id, account.name.strip(), user_id=current_user.id)
    
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found or not authorized")
    
    token_data = get_client_tokens(account_id)
    
    return {
        "id": updated["id"],
        "name": updated.get("client_name", account.name),
        "has_token": token_data is not None
    }


@router.delete("/{account_id}")
async def delete_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from db.accounts_db import delete_client_account
    success = delete_client_account(account_id, user_id=current_user.id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Account not found or not authorized")
    
    return {"message": "Account deleted"}
