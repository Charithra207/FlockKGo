"""
seed.py — Demo data for PackVote+

Creates a complete trip end-to-end:
  1 trip → 5 participants → 5 survey responses → ML pipeline → votes

Usage:
    python seed.py                  # uses DATABASE_URL from .env / environment
    python seed.py --reset          # drops all existing demo data first

The script is idempotent: running it twice with --reset gives a clean slate.
"""

import argparse
import sys
import uuid
from datetime import date

from sqlalchemy.orm import Session

# ── bootstrap path so this runs from backend/ ────────────────────────────────
sys.path.insert(0, ".")

from app.db.database import SessionLocal, engine
from app.ml.feature_engineering import build_feature_vector
from app.ml.pipeline import MLPipeline
from app.models.participant import Participant
from app.models.recommendation import Recommendation
from app.models.survey_response import SurveyResponse
from app.models.trip import Trip
from app.models.vote import Vote
from app.models.ml_result import MLRunResult

# ── Demo data ─────────────────────────────────────────────────────────────────

DEMO_TRIP = {
    "name": "Europe Summer 2025",
    "organizer_name": "Aryan",
    "organizer_email": "aryan@demo.com",
    "trip_month": "June",
    "duration_days": 7,
}

DEMO_PARTICIPANTS = [
    {"name": "Aryan",   "email": "aryan@demo.com",   "phone": "+1111111111"},
    {"name": "Priya",   "email": "priya@demo.com",   "phone": "+2222222222"},
    {"name": "Carlos",  "email": "carlos@demo.com",  "phone": "+3333333333"},
    {"name": "Mei",     "email": "mei@demo.com",     "phone": "+4444444444"},
    {"name": "Jordan",  "email": "jordan@demo.com",  "phone": "+5555555555"},
]

# Diverse preferences so clustering produces interesting results
DEMO_SURVEYS = [
    {
        "budget_min": 800,
        "budget_max": 1400,
        "vibes": ["beach", "relaxation", "food"],
        "climate_pref": "warm",
        "activity_level": "moderate",
        "available_start": date(2025, 6, 1),
        "available_end": date(2025, 6, 15),
        "excluded_destinations": [],
        "already_visited": ["Bali"],
    },
    {
        "budget_min": 1200,
        "budget_max": 2000,
        "vibes": ["city", "cultural", "food"],
        "climate_pref": "any",
        "activity_level": "intense",
        "available_start": date(2025, 6, 5),
        "available_end": date(2025, 6, 20),
        "excluded_destinations": ["Vegas"],
        "already_visited": [],
    },
    {
        "budget_min": 600,
        "budget_max": 1100,
        "vibes": ["beach", "nature", "relaxation"],
        "climate_pref": "warm",
        "activity_level": "relaxed",
        "available_start": date(2025, 6, 1),
        "available_end": date(2025, 6, 30),
        "excluded_destinations": [],
        "already_visited": [],
    },
    {
        "budget_min": 1500,
        "budget_max": 2800,
        "vibes": ["adventure", "nature", "cultural"],
        "climate_pref": "cold",
        "activity_level": "intense",
        "available_start": date(2025, 6, 10),
        "available_end": date(2025, 6, 25),
        "excluded_destinations": ["Dubai"],
        "already_visited": ["Iceland"],
    },
    {
        "budget_min": 900,
        "budget_max": 1600,
        "vibes": ["food", "city", "nightlife"],
        "climate_pref": "warm",
        "activity_level": "moderate",
        "available_start": date(2025, 6, 1),
        "available_end": date(2025, 6, 15),
        "excluded_destinations": [],
        "already_visited": [],
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_survey_obj(data: dict) -> object:
    """Build a lightweight object that feature_engineering can read."""
    return type("Survey", (), data)()


def reset_demo_data(db: Session) -> None:
    """Remove any existing demo trip (matched by organizer email)."""
    trips = db.query(Trip).filter(Trip.organizer_email == "aryan@demo.com").all()
    for trip in trips:
        tid = trip.id
        db.query(Vote).filter(Vote.trip_id == tid).delete()
        db.query(Recommendation).filter(Recommendation.trip_id == tid).delete()
        db.query(MLRunResult).filter(MLRunResult.trip_id == tid).delete()

        participant_ids = [
            p.id for p in db.query(Participant).filter(Participant.trip_id == tid).all()
        ]
        for pid in participant_ids:
            db.query(SurveyResponse).filter(SurveyResponse.participant_id == pid).delete()

        db.query(Participant).filter(Participant.trip_id == tid).delete()
        db.delete(trip)

    db.commit()
    print("✓ Existing demo data cleared")


# ── Main seed logic ───────────────────────────────────────────────────────────

def seed(db: Session) -> None:
    # 1. Create trip
    trip = Trip(**DEMO_TRIP)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    print(f"✓ Trip created: {trip.name}  id={trip.id}")

    # 2. Create participants + survey responses
    participants = []
    for p_data, s_data in zip(DEMO_PARTICIPANTS, DEMO_SURVEYS):
        token = uuid.uuid4().hex[:16]
        participant = Participant(
            trip_id=trip.id,
            survey_token=token,
            **p_data,
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)
        participants.append(participant)

        survey_obj = _build_survey_obj(s_data)
        vector = build_feature_vector(survey_obj)

        response = SurveyResponse(
            participant_id=participant.id,
            trip_id=trip.id,
            feature_vector=vector,
            previous_vector=[],
            **s_data,
        )
        db.add(response)
        db.commit()
        print(f"  ✓ Participant + survey: {participant.name}  token={token}")

    # 3. Run ML pipeline (no LLM — seed works offline)
    print("\n⚙  Running ML pipeline...")
    try:
        pipeline = MLPipeline(db)
        ml_data, llm_context = pipeline.run(trip.id)
        clusters = ml_data["clusters"]
        top5 = ml_data["destination_scores"][:5]
        print(f"  ✓ Clusters found: {clusters['k']}  silhouette={clusters['silhouette_score']:.3f}")
        print(f"  ✓ Top destinations:")
        for d in top5:
            print(f"      {d['destination_name']:25s}  score={d['score']:.3f}")
    except Exception as e:
        print(f"  ✗ ML pipeline failed: {e}")
        print("    (This is OK for offline seeding — survey data is still saved)")
        db.rollback()
        trip.status = "collecting_preferences"
        db.commit()
        return

    # 4. Create placeholder recommendations so votes have something to reference
    #    (In production the LLM generates these — here we use ML scores directly)
    recs = []
    for idx, dest in enumerate(top5, start=1):
        rec = Recommendation(
            trip_id=trip.id,
            destination_name=dest["destination_name"],
            country=dest.get("country", ""),
            why_recommended=f"ML score: {dest['score']:.3f} — strong match for group preferences",
            estimated_budget_range="$800 - $2000",
            best_activities=["Sightseeing", "Local food", "Nature"],
            ml_score=dest["score"],
            prompt_version="seed",
            quality_score=1.0,
            rank=idx,
        )
        db.add(rec)
        recs.append(rec)

    trip.status = "voting"
    db.commit()
    for r in recs:
        db.refresh(r)
    print(f"\n✓ {len(recs)} recommendations saved")

    # 5. Submit votes — each participant ranks all 5 destinations
    #    Voting pattern designed so Bali wins in round 1 (clear majority)
    vote_patterns = [
        [0, 1, 2, 3, 4],  # Aryan:  1st→Bali
        [0, 2, 1, 4, 3],  # Priya:  1st→Bali
        [1, 0, 2, 3, 4],  # Carlos: 1st→2nd place
        [0, 1, 3, 2, 4],  # Mei:    1st→Bali
        [2, 0, 1, 3, 4],  # Jordan: 1st→3rd place
    ]

    for participant, pattern in zip(participants, vote_patterns):
        ranked_choices = [
            {"rank": rank + 1, "recommendation_id": str(recs[rec_idx].id)}
            for rank, rec_idx in enumerate(pattern)
        ]
        vote = Vote(
            trip_id=trip.id,
            participant_id=participant.id,
            ranked_choices=ranked_choices,
        )
        db.add(vote)

    db.commit()
    print(f"✓ {len(participants)} votes submitted")

    # 6. Summary
    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SEED COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Trip ID   : {trip.id}
  Status    : {trip.status}
  Participants : {len(participants)}
  Recommendations : {len(recs)}

  Test these endpoints:
  GET  /v1/trips/{trip.id}
  GET  /v1/trips/{trip.id}/summary
  GET  /v1/trips/{trip.id}/recommendations
  GET  /v1/trips/{trip.id}/results
  GET  /v1/trips/{trip.id}/metrics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed PackVote+ demo data")
    parser.add_argument("--reset", action="store_true", help="Clear existing demo data before seeding")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            reset_demo_data(db)
        seed(db)
    except Exception as e:
        print(f"\n✗ Seed failed: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
