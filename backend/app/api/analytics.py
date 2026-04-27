from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.monitoring.cost_tracker import get_usage_summary

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/usage")
@limiter.limit("60/minute")
def usage(request: Request, db: Session = Depends(get_db)):
    return get_usage_summary(db)
