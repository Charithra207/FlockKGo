from sqlalchemy.orm import Session

from app.models.participant import Participant
from app.models.survey_response import SurveyResponse


def get_survey_status(db: Session, trip_id):
    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    rows = []
    submitted = 0
    for p in participants:
        has = db.query(SurveyResponse).filter(SurveyResponse.participant_id == p.id).first() is not None
        submitted += int(has)
        rows.append({"id": str(p.id), "name": p.name, "submitted": has})

    total = len(participants)
    return {
        "participants": rows,
        "submitted_count": submitted,
        "total_count": total,
        "all_submitted": total > 0 and submitted == total,
    }
