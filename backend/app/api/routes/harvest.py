"""
Harvest Router - search-term harvesting automatico (SP + SB).

Endpoint:
  POST /api/harvest/run            -> crea un job e lo lancia in background (per account+profile)
  GET  /api/harvest/jobs           -> lista job dell'account
  GET  /api/harvest/jobs/{job_id}  -> stato job + azioni pianificate/eseguite
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.app.core.security import decode_access_token
from db.accounts_db import verify_account_ownership
from db.harvest_db import (
    init_harvest_db, create_harvest_job, get_harvest_job,
    get_harvest_actions, list_harvest_jobs,
)

router = APIRouter()


class HarvestRunRequest(BaseModel):
    account_id: int
    profile_id: str
    days: int = 60
    min_purchases: int = 1
    dry_run: bool = False


def _user_id(request: Request) -> int:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(auth.split(" ")[1])
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(payload.get("sub"))


@router.post("/run")
def run(req: HarvestRunRequest, request: Request):
    user_id = _user_id(request)
    if not verify_account_ownership(user_id, req.account_id):
        raise HTTPException(status_code=403, detail="Account non autorizzato")

    if req.days < 1 or req.days > 90:
        raise HTTPException(status_code=400, detail="days deve essere tra 1 e 90")
    if req.min_purchases < 1:
        raise HTTPException(status_code=400, detail="min_purchases deve essere >= 1")

    init_harvest_db()
    job_id = create_harvest_job(req.account_id, req.profile_id, req.days,
                                req.min_purchases, req.dry_run)

    # Il job resta QUEUED: lo prende ed esegue il worker (backend.app.services.big_bang_worker),
    # cosi' e' robusto ai riavvii del processo web.
    return {"job_id": job_id, "status": "QUEUED", "dry_run": req.dry_run}


@router.get("/jobs")
def jobs(account_id: int, request: Request):
    user_id = _user_id(request)
    if not verify_account_ownership(user_id, account_id):
        raise HTTPException(status_code=403, detail="Account non autorizzato")
    return {"jobs": list_harvest_jobs(account_id)}


@router.get("/jobs/{job_id}")
def job_detail(job_id: int, request: Request):
    user_id = _user_id(request)
    job = get_harvest_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job non trovato")
    if not verify_account_ownership(user_id, job["account_id"]):
        raise HTTPException(status_code=403, detail="Account non autorizzato")
    return {"job": job, "actions": get_harvest_actions(job_id)}
