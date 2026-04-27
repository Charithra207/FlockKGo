import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_db
from app.models.participant import Participant
from app.models.trip import Trip
from app.schemas.participant import ParticipantCreate

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(tags=["participants"])


@router.post("/trips/{trip_id}/participants")
@limiter.limit("10/minute")
def add_participant(request: Request, trip_id: uuid.UUID, payload: ParticipantCreate, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    token = uuid.uuid4().hex[:16]
    participant = Participant(trip_id=trip_id, survey_token=token, **payload.model_dump())
    db.add(participant)
    db.commit()
    db.refresh(participant)
    base = get_settings().frontend_base_url
    return {
        "id": str(participant.id),
        "name": participant.name,
        "survey_token": token,
        "survey_link": f"{base}/survey/{token}",
    }


@router.get("/trips/{trip_id}/participants")
@limiter.limit("60/minute")
def list_participants(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    rows = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    return [{"id": str(p.id), "name": p.name, "email": p.email, "phone": p.phone, "survey_token": p.survey_token} for p in rows]


@router.delete("/trips/{trip_id}/participants/{participant_id}")
@limiter.limit("10/minute")
def delete_participant(request: Request, trip_id: uuid.UUID, participant_id: uuid.UUID, db: Session = Depends(get_db)):
    row = db.query(Participant).filter(Participant.trip_id == trip_id, Participant.id == participant_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Participant not found")
    db.delete(row)
    db.commit()
    return {"success": True}
