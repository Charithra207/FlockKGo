import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.ml.feature_engineering import build_feature_vector
from app.models.participant import Participant
from app.models.survey_response import SurveyResponse
from app.models.trip import Trip
from app.monitoring.metrics import surveys_submitted_total
from app.schemas.survey import SurveySubmit
from app.services.survey_service import get_survey_status

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(tags=["surveys"])


@router.get("/survey/{token}")
@limiter.limit("60/minute")
def survey_details(request: Request, token: str, db: Session = Depends(get_db)):
    participant = db.query(Participant).filter(Participant.survey_token == token).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Survey token not found")
    trip = db.query(Trip).filter(Trip.id == participant.trip_id).first()
    already = db.query(SurveyResponse).filter(SurveyResponse.participant_id == participant.id).first() is not None
    return {
        "participant_name": participant.name,
        "trip_name": trip.name,
        "trip_id": str(participant.trip_id),
        "already_submitted": already,
    }


@router.post("/survey/{token}/submit")
@limiter.limit("5/minute")
def submit_survey(request: Request, token: str, payload: SurveySubmit, db: Session = Depends(get_db)):
    participant = db.query(Participant).filter(Participant.survey_token == token).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Survey token not found")

    data = payload.model_dump()
    temp = type("R", (), data)()
    vector = build_feature_vector(temp)

    existing = db.query(SurveyResponse).filter(SurveyResponse.participant_id == participant.id).first()
    if existing:
        existing.previous_vector = existing.feature_vector or []
        for key, value in data.items():
            setattr(existing, key, value)
        existing.feature_vector = vector
        updated = True
    else:
        existing = SurveyResponse(
            participant_id=participant.id,
            trip_id=participant.trip_id,
            feature_vector=vector,
            previous_vector=[],
            **data,
        )
        db.add(existing)
        updated = False

    db.commit()
    surveys_submitted_total.inc()
    return {"success": True, "message": "Survey submitted", "is_update": updated}


@router.get("/trips/{trip_id}/survey-status")
@limiter.limit("60/minute")
def survey_status(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_survey_status(db, trip_id)
