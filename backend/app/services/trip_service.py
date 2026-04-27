import uuid

from sqlalchemy.orm import Session

from app.models.participant import Participant
from app.models.survey_response import SurveyResponse
from app.models.trip import Trip


def get_trip_summary(db: Session, trip_id: uuid.UUID) -> dict:
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        return {}

    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    rows = []
    for p in participants:
        submitted = db.query(SurveyResponse).filter(SurveyResponse.participant_id == p.id).first() is not None
        rows.append({"id": str(p.id), "name": p.name, "survey_submitted": submitted})

    return {
        "trip": {
            "id": str(trip.id),
            "name": trip.name,
            "status": trip.status,
            "organizer_name": trip.organizer_name,
            "organizer_email": trip.organizer_email,
        },
        "participants": rows,
    }
