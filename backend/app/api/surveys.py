"""
surveys.py — Survey submission and status endpoints.

ANTI-DICTATOR BLINDING PROTOCOL
---------------------------------
All routes that return survey or preference data are scoped strictly to the
calling participant's own token.  No route in this file allows one participant
to query another participant's budget, feature vector, vibes, or any other
preference metric while the trip is in an active collection state.

Blinding rules enforced here:
  1. GET /survey/{token}        — returns ONLY the calling participant's trip name
                                  and submission status. Never returns peer data.
  2. POST /survey/{token}/submit — writes ONLY the calling participant's response.
  3. GET /trips/{id}/survey-status — returns aggregate counts (submitted vs total)
                                      and per-participant submitted/not-submitted flags.
                                      Does NOT return budget ranges, vibes, or any
                                      preference payload from other participants.
"""

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

# Trip statuses where preference data is still being actively collected.
# During these states the blinding is fully in effect.
_ACTIVE_COLLECTION_STATUSES = {"collecting_preferences", "running_ml"}


@router.get("/survey/{token}")
@limiter.limit("60/minute")
def survey_details(request: Request, token: str, db: Session = Depends(get_db)):
    """
    Return the survey form context for the participant identified by *token*.

    BLINDING: Returns only this participant's own name, the trip name, and
    whether they have already submitted.  No peer preference data is included
    regardless of trip status.
    """
    participant = (
        db.query(Participant)
        .filter(Participant.survey_token == token)
        .first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Survey token not found")

    trip = db.query(Trip).filter(Trip.id == participant.trip_id).first()
    already_submitted = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.participant_id == participant.id)
        .first()
    ) is not None

    return {
        "participant_name": participant.name,
        "trip_name": trip.name,
        "trip_id": str(participant.trip_id),
        "already_submitted": already_submitted,
        # Intentionally omitted: other participants' budgets, vibes, vectors.
    }


@router.post("/survey/{token}/submit")
@limiter.limit("5/minute")
def submit_survey(
    request: Request,
    token: str,
    payload: SurveySubmit,
    db: Session = Depends(get_db),
):
    """
    Accept a survey submission from the participant identified by *token*.

    Builds the 16-d feature vector from the submitted payload and saves it.
    If the participant already submitted, updates their response and stores
    the old feature_vector in previous_vector for drift detection.

    BLINDING: This route writes ONLY to the calling participant's own row.
    No other participant's data is read or mutated.
    """
    participant = (
        db.query(Participant)
        .filter(Participant.survey_token == token)
        .first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Survey token not found")

    data = payload.model_dump()
    # Build a temporary object that satisfies build_feature_vector's attribute access
    temp_obj = type("_R", (), data)()
    vector = build_feature_vector(temp_obj)

    existing = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.participant_id == participant.id)
        .first()
    )
    if existing:
        existing.previous_vector = existing.feature_vector or []
        for key, value in data.items():
            setattr(existing, key, value)
        existing.feature_vector = vector
        is_update = True
    else:
        existing = SurveyResponse(
            participant_id=participant.id,
            trip_id=participant.trip_id,
            feature_vector=vector,
            previous_vector=[],
            **data,
        )
        db.add(existing)
        is_update = False

    db.commit()
    surveys_submitted_total.inc()
    return {"success": True, "message": "Survey submitted", "is_update": is_update}


@router.get("/trips/{trip_id}/survey-status")
@limiter.limit("60/minute")
def survey_status(
    request: Request,
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Return aggregate survey completion status for the trip organiser dashboard.

    Returns per-participant submitted/not-submitted flags and aggregate counts.

    BLINDING: Does NOT include budget ranges, vibes, climate preferences, or
    any other preference payload.  Only submission status (boolean) is exposed.
    The blinding is unconditional — it applies in all trip states, not just
    during active collection, because preference data belongs to the participant
    and should never be leaked to peers through this endpoint.
    """
    # get_survey_status already returns only {submitted: bool, participant_name, id}
    # per participant — no preference payload.
    return get_survey_status(db, trip_id)
