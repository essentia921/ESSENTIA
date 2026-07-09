from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json
import io
from datetime import datetime

from backend.app.core.database import get_db
from backend.app.api.routes.auth import get_current_user
from backend.app.models.user import User
from backend.app.models.extractor import ExtractionJob, ExtractedAsin, ExtractedKeyword, ExtractorApiLog
from backend.app.services.extractor_service import (
    run_extraction, cancel_extraction, get_dashboard_data, get_current_job
)
from backend.app.services.extractor_clients import oxylabs_client, canopy_client

router = APIRouter(prefix="/extractor", tags=["extractor"])


class StartExtractionRequest(BaseModel):
    extraction_type: str = "asins"
    category_mode: str = "books"
    seed_keywords: List[str]
    max_asins: int = 1000
    max_keywords: int = 1000
    include_merch: bool = False


class JobResponse(BaseModel):
    id: str
    seed_keywords: List[str]
    extraction_type: str
    category_mode: str
    status: str
    progress: int
    asins_found: int
    keywords_found: int
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[str]

    class Config:
        from_attributes = True


@router.get("/dashboard")
async def get_extractor_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_dashboard_data(db, current_user.id)


@router.get("/current")
async def get_current_extraction(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_current_job(db, current_user.id)


@router.post("/start")
async def start_extraction(
    request: StartExtractionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current = get_current_job(db, current_user.id)
    if current:
        raise HTTPException(status_code=400, detail="Un'estrazione è già in corso")
    
    if not request.seed_keywords or len(request.seed_keywords) == 0:
        raise HTTPException(status_code=400, detail="Almeno una keyword seed è richiesta")
    
    if len(request.seed_keywords) > 15:
        raise HTTPException(status_code=400, detail="Massimo 15 keyword seed consentite")
    
    job_id = str(uuid.uuid4())
    job = ExtractionJob(
        id=job_id,
        user_id=current_user.id,
        seed_keywords=request.seed_keywords,
        extraction_type=request.extraction_type,
        category_mode=request.category_mode,
        max_asins=request.max_asins,
        max_keywords=request.max_keywords,
        include_merch=request.include_merch,
        status="pending"
    )
    db.add(job)
    db.commit()
    
    background_tasks.add_task(
        run_extraction,
        db,
        job_id,
        current_user.id,
        request.extraction_type,
        request.category_mode,
        request.max_asins,
        request.max_keywords,
        request.include_merch
    )
    
    return {
        "id": job_id,
        "status": "pending",
        "message": "Estrazione avviata"
    }


@router.post("/stop")
async def stop_extraction(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current = get_current_job(db, current_user.id)
    if not current:
        raise HTTPException(status_code=400, detail="Nessuna estrazione in corso")
    
    cancel_extraction(current["id"])
    
    job = db.query(ExtractionJob).filter(ExtractionJob.id == current["id"]).first()
    if job:
        job.status = "error"
        job.error = "Estrazione annullata dall'utente"
        job.completed_at = datetime.utcnow()
        db.commit()
    
    return {"success": True, "message": "Estrazione fermata"}


@router.get("/asins")
async def get_asins(
    job_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ExtractedAsin).filter(ExtractedAsin.user_id == current_user.id)
    
    if job_id:
        query = query.filter(ExtractedAsin.job_id == job_id)
    
    total = query.count()
    asins = query.order_by(ExtractedAsin.extracted_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "items": [
            {
                "id": a.id,
                "asin": a.asin,
                "title": a.title,
                "brand": a.brand,
                "price": a.price,
                "rating": a.rating,
                "ratings_total": a.ratings_total,
                "bsr": a.bsr,
                "image_url": a.image_url,
                "format": a.format,
                "source": a.source,
                "seed_keyword": a.seed_keyword,
                "extracted_at": a.extracted_at.isoformat() if a.extracted_at else None
            }
            for a in asins
        ]
    }


@router.get("/keywords")
async def get_keywords(
    job_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ExtractedKeyword).filter(ExtractedKeyword.user_id == current_user.id)
    
    if job_id:
        query = query.filter(ExtractedKeyword.job_id == job_id)
    
    total = query.count()
    keywords = query.order_by(ExtractedKeyword.extracted_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "items": [
            {
                "id": k.id,
                "keyword": k.keyword,
                "source": k.source,
                "source_asin": k.source_asin,
                "category": k.category,
                "relevance_score": k.relevance_score,
                "is_seed": k.is_seed,
                "extracted_at": k.extracted_at.isoformat() if k.extracted_at else None
            }
            for k in keywords
        ]
    }


@router.get("/jobs")
async def get_jobs(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ExtractionJob).filter(ExtractionJob.user_id == current_user.id)
    total = query.count()
    jobs = query.order_by(ExtractionJob.started_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "items": [
            {
                "id": j.id,
                "seed_keywords": j.seed_keywords,
                "extraction_type": j.extraction_type,
                "category_mode": j.category_mode,
                "status": j.status,
                "progress": j.progress,
                "asins_found": j.asins_found,
                "keywords_found": j.keywords_found,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "error": j.error
            }
            for j in jobs
        ]
    }


@router.get("/logs")
async def get_api_logs(
    job_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ExtractorApiLog).join(
        ExtractionJob, ExtractorApiLog.job_id == ExtractionJob.id
    ).filter(ExtractionJob.user_id == current_user.id)
    
    if job_id:
        query = query.filter(ExtractorApiLog.job_id == job_id)
    
    total = query.count()
    logs = query.order_by(ExtractorApiLog.timestamp.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "items": [
            {
                "id": log.id,
                "job_id": log.job_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "log_type": log.log_type,
                "endpoint": log.endpoint,
                "source": log.source,
                "status_code": log.status_code,
                "duration_ms": log.duration_ms,
                "request_data": log.request_data,
                "response_data": log.response_data
            }
            for log in logs
        ]
    }


@router.get("/jobs/{job_id}/logs/download")
async def download_job_logs(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ExtractionJob).filter(
        ExtractionJob.id == job_id,
        ExtractionJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job non trovato")

    logs = db.query(ExtractorApiLog).filter(
        ExtractorApiLog.job_id == job_id
    ).order_by(ExtractorApiLog.timestamp.asc()).all()

    lines = []
    for log in logs:
        entry = {
            "id": log.id,
            "job_id": log.job_id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "log_type": log.log_type,
            "endpoint": log.endpoint,
            "source": log.source,
            "status_code": log.status_code,
            "duration_ms": log.duration_ms,
            "request_data": log.request_data,
            "response_data": log.response_data
        }
        lines.append(json.dumps(entry, default=str))

    content = "\n".join(lines)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f"attachment; filename=logs_{job_id}.jsonl"}
    )


@router.get("/status")
async def get_api_status(
    current_user: User = Depends(get_current_user)
):
    oxylabs_status = {"status": "not_configured"}
    canopy_status = {"status": "not_configured"}
    
    if oxylabs_client.is_configured():
        try:
            oxylabs_status = await oxylabs_client.check_connection()
        except Exception as e:
            oxylabs_status = {"status": "error", "message": str(e)}
    
    if canopy_client.is_configured():
        try:
            canopy_status = await canopy_client.check_connection()
        except Exception as e:
            canopy_status = {"status": "error", "message": str(e)}
    
    return {
        "oxylabs": oxylabs_status,
        "canopy": canopy_status
    }


@router.delete("/asins")
async def delete_all_asins(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    count = db.query(ExtractedAsin).filter(ExtractedAsin.user_id == current_user.id).delete()
    db.commit()
    return {"deleted": count}


@router.delete("/keywords")
async def delete_all_keywords(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    count = db.query(ExtractedKeyword).filter(ExtractedKeyword.user_id == current_user.id).delete()
    db.commit()
    return {"deleted": count}


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ExtractionJob).filter(
        ExtractionJob.id == job_id,
        ExtractionJob.user_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job non trovato")
    
    db.query(ExtractedAsin).filter(ExtractedAsin.job_id == job_id).delete()
    db.query(ExtractedKeyword).filter(ExtractedKeyword.job_id == job_id).delete()
    db.query(ExtractorApiLog).filter(ExtractorApiLog.job_id == job_id).delete()
    db.delete(job)
    db.commit()
    
    return {"deleted": True}
