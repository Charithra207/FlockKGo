from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class TripCreate(BaseModel):
    name: str
    organizer_name: str
    organizer_email: str
    trip_month: str
    duration_days: int = Field(ge=1, le=30)


class ParticipantCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class SurveySubmit(BaseModel):
    budget_min: int
    budget_max: int
    vibes: List[str] = []
    climate: str = "either"
    activity_level: str = "moderate"
    available_dates: List[Optional[str]] = []
    exclusions: List[str] = []
    visited: List[str] = []


class VoteSubmit(BaseModel):
    participant_id: str
    ranking: List[str]


app = FastAPI(title="FlockGo API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRIPS: Dict[str, Dict] = {}
PARTICIPANTS: Dict[str, List[Dict]] = {}
SURVEYS: Dict[str, Dict] = {}
SURVEY_TOKENS: Dict[str, Dict] = {}
ANALYSIS: Dict[str, Dict] = {}
RECOMMENDATIONS: Dict[str, List[Dict]] = {}
VOTES: Dict[str, Dict[str, List[str]]] = {}


def _sample_recommendations() -> List[Dict]:
    return [
        {
            "id": "rec-bali",
            "name": "Bali",
            "country_flag": "ID",
            "why": "Great balance of beaches, food, and relaxation for mixed groups.",
            "budget_min": 900,
            "budget_max": 1700,
            "activities": ["Beach", "Food", "Nature"],
            "ml_score": 92,
            "concern": "",
        },
        {
            "id": "rec-tokyo",
            "name": "Tokyo",
            "country_flag": "JP",
            "why": "Strong fit for city explorers, culture lovers, and foodies.",
            "budget_min": 1400,
            "budget_max": 2600,
            "activities": ["City", "Culture", "Nightlife"],
            "ml_score": 86,
            "concern": "Slightly higher budget than group average.",
        },
        {
            "id": "rec-lisbon",
            "name": "Lisbon",
            "country_flag": "PT",
            "why": "Budget-friendly with beaches, walkable neighborhoods, and nightlife.",
            "budget_min": 1000,
            "budget_max": 1900,
            "activities": ["Beach", "Food", "Nightlife"],
            "ml_score": 84,
            "concern": "",
        },
    ]


def _get_trip_or_404(trip_id: str) -> Dict:
    trip = TRIPS.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.get("/")
async def root() -> Dict:
    return {"message": "FlockGo API", "docs": "/docs"}


@app.get("/health")
async def health() -> Dict:
    return {"ok": True}


@app.post("/v1/trips")
async def create_trip(payload: TripCreate) -> Dict:
    trip_id = str(uuid4())
    trip = {
        "id": trip_id,
        "name": payload.name,
        "organizer_name": payload.organizer_name,
        "organizer_email": payload.organizer_email,
        "trip_month": payload.trip_month,
        "duration_days": payload.duration_days,
        "status": "collecting_preferences",
        "created_at": datetime.utcnow().isoformat(),
    }
    TRIPS[trip_id] = trip
    PARTICIPANTS[trip_id] = []
    VOTES[trip_id] = {}
    return trip


@app.get("/v1/trips/{trip_id}")
async def get_trip(trip_id: str) -> Dict:
    return _get_trip_or_404(trip_id)


@app.get("/v1/trips/{trip_id}/summary")
async def get_trip_summary(trip_id: str) -> Dict:
    return _get_trip_or_404(trip_id)


@app.post("/v1/trips/{trip_id}/participants")
async def add_participant(trip_id: str, payload: ParticipantCreate) -> Dict:
    _get_trip_or_404(trip_id)
    participant_id = str(uuid4())
    token = str(uuid4())
    participant = {
        "id": participant_id,
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "survey_submitted": False,
        "survey_link": f"/survey/{token}",
    }
    PARTICIPANTS[trip_id].append(participant)
    SURVEY_TOKENS[token] = {
        "trip_id": trip_id,
        "participant_id": participant_id,
        "participant_name": payload.name,
    }
    return participant


@app.get("/v1/trips/{trip_id}/participants")
async def get_participants(trip_id: str) -> List[Dict]:
    _get_trip_or_404(trip_id)
    return PARTICIPANTS.get(trip_id, [])


@app.get("/v1/survey/{token}")
async def get_survey_info(token: str) -> Dict:
    token_data = SURVEY_TOKENS.get(token)
    if not token_data:
        raise HTTPException(status_code=404, detail="Survey token not found")
    return {
        "participant_name": token_data["participant_name"],
        "submitted": token in SURVEYS,
    }


@app.post("/v1/survey/{token}/submit")
async def submit_survey(token: str, payload: SurveySubmit) -> Dict:
    token_data = SURVEY_TOKENS.get(token)
    if not token_data:
        raise HTTPException(status_code=404, detail="Survey token not found")
    SURVEYS[token] = payload.model_dump()
    trip_id = token_data["trip_id"]
    participant_id = token_data["participant_id"]
    for participant in PARTICIPANTS.get(trip_id, []):
        if participant["id"] == participant_id:
            participant["survey_submitted"] = True
            break
    return {"success": True}


@app.get("/v1/trips/{trip_id}/survey-status")
async def get_survey_status(trip_id: str) -> Dict:
    _get_trip_or_404(trip_id)
    participants = PARTICIPANTS.get(trip_id, [])
    submitted = len([p for p in participants if p["survey_submitted"]])
    return {"submitted_count": submitted, "total_count": len(participants)}


@app.post("/v1/trips/{trip_id}/run-analysis")
async def run_analysis(trip_id: str) -> Dict:
    trip = _get_trip_or_404(trip_id)
    participants = PARTICIPANTS.get(trip_id, [])
    if len(participants) < 2:
        raise HTTPException(status_code=400, detail="Add at least 2 participants before analysis")
    if not all(p["survey_submitted"] for p in participants):
        raise HTTPException(status_code=400, detail="Not all participants have submitted surveys")

    trip["status"] = "running_ml"
    ANALYSIS[trip_id] = {"status": "complete", "ran_at": datetime.utcnow().isoformat(), "cluster_count": 2}
    RECOMMENDATIONS[trip_id] = _sample_recommendations()
    trip["status"] = "voting"
    return {"status": "processing"}


@app.get("/v1/trips/{trip_id}/analysis")
async def analysis_status(trip_id: str) -> Dict:
    _get_trip_or_404(trip_id)
    return ANALYSIS.get(trip_id, {"status": "not_started"})


@app.get("/v1/trips/{trip_id}/recommendations")
async def get_recommendations(trip_id: str) -> List[Dict]:
    _get_trip_or_404(trip_id)
    return RECOMMENDATIONS.get(trip_id, [])


@app.post("/v1/trips/{trip_id}/votes")
async def submit_vote(trip_id: str, payload: VoteSubmit) -> Dict:
    _get_trip_or_404(trip_id)
    votes_for_trip = VOTES.setdefault(trip_id, {})
    votes_for_trip[payload.participant_id] = payload.ranking
    participants = PARTICIPANTS.get(trip_id, [])
    if len(votes_for_trip) == len(participants) and len(participants) > 0:
        TRIPS[trip_id]["status"] = "completed"
    return {"success": True}


@app.get("/v1/trips/{trip_id}/votes/status")
async def vote_status(trip_id: str) -> Dict:
    _get_trip_or_404(trip_id)
    votes_for_trip = VOTES.get(trip_id, {})
    participants = PARTICIPANTS.get(trip_id, [])
    return {
        "voted_count": len(votes_for_trip),
        "total_count": len(participants),
        "voters": list(votes_for_trip.keys()),
    }


@app.get("/v1/trips/{trip_id}/results")
async def get_results(trip_id: str) -> Dict:
    _get_trip_or_404(trip_id)
    recs = RECOMMENDATIONS.get(trip_id, _sample_recommendations())
    votes_for_trip = VOTES.get(trip_id, {})
    winner = recs[0]["name"] if recs else "TBD"
    if votes_for_trip:
        first_choices: Dict[str, int] = {}
        for ranking in votes_for_trip.values():
            if ranking:
                first_choices[ranking[0]] = first_choices.get(ranking[0], 0) + 1
        if first_choices:
            winner_id = max(first_choices, key=first_choices.get)
            matched = [r for r in recs if r["id"] == winner_id]
            if matched:
                winner = matched[0]["name"]
    return {
        "winner": winner,
        "total_voters": len(votes_for_trip),
        "rounds_taken": 1,
        "ai_agreement": True,
        "rounds": [
            {"round": 1, "eliminated": "N/A", "votes": votes_for_trip},
        ],
    }
