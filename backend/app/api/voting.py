import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.participant import Participant
from app.models.recommendation import Recommendation
from app.models.trip import Trip
from app.models.vote import Vote
from app.monitoring.metrics import votes_submitted_total
from app.schemas.vote import VoteCreate

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(tags=["voting"])


@router.post("/trips/{trip_id}/votes")
@limiter.limit("10/minute")
def submit_vote(request: Request, trip_id: uuid.UUID, payload: VoteCreate, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.status != "voting":
        raise HTTPException(status_code=400, detail="Trip is not in voting status")

    if db.query(Vote).filter(Vote.trip_id == trip_id, Vote.participant_id == payload.participant_id).first():
        raise HTTPException(status_code=400, detail="Participant has already voted")

    participant = db.query(Participant).filter(Participant.id == payload.participant_id, Participant.trip_id == trip_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    vote = Vote(
        trip_id=trip_id,
        participant_id=payload.participant_id,
        ranked_choices=[item.model_dump(mode="json") for item in payload.ranked_choices],
    )
    db.add(vote)
    db.commit()
    votes_submitted_total.inc()
    return {"success": True, "message": "Vote submitted"}


@router.get("/trips/{trip_id}/votes/status")
@limiter.limit("60/minute")
def vote_status(request: Request, trip_id: uuid.UUID, db: Session = Depends(get_db)):
    participants = db.query(Participant).filter(Participant.trip_id == trip_id).all()
    votes = db.query(Vote).filter(Vote.trip_id == trip_id).all()
    voted_ids = {v.participant_id for v in votes}
    status = [{"id": str(p.id), "name": p.name, "has_voted": p.id in voted_ids} for p in participants]
    return {"participants": status, "voted_count": len(votes), "total_count": len(participants)}
