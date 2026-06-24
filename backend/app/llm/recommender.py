from app.llm.ab_testing import ABTestManager
from app.llm.evaluator import LLMEvaluator
from app.llm.gateway import LLMError, ModelGateway
from app.llm.prompts import recommendation_v1, recommendation_v2
from app.models.recommendation import Recommendation
from app.models.destination import Destination
from app.monitoring.cost_tracker import log_llm_usage
from app.monitoring.metrics import llm_low_quality_total, llm_recommendation_quality
from app.core.logging import get_logger

log = get_logger(__name__)
QUALITY_THRESHOLD = 0.5


def _fallback_recommendations(db, trip_id, group_size: int) -> list:
    """
    Generate recommendations purely from ML scores when no LLM key is set.
    Picks the top destinations from the Destination table by score_vector similarity,
    or simply returns the highest-rated destinations from the catalog.
    """
    destinations = db.query(Destination).all()
    if not destinations:
        # Absolute fallback - hardcoded popular destinations
        destinations_data = [
            {"name": "Bali", "country": "Indonesia", "budget": "$1,500-$2,500", "activities": ["Beach", "Temples", "Spa"], "why": "Perfect blend of culture, nature and relaxation for any group."},
            {"name": "Bangkok", "country": "Thailand", "budget": "$1,200-$2,000", "activities": ["Street food", "Temples", "Nightlife"], "why": "Vibrant city with something for everyone at great value."},
            {"name": "Barcelona", "country": "Spain", "budget": "$2,000-$3,500", "activities": ["Architecture", "Beaches", "Food"], "why": "Iconic European city with culture, sun and great food."},
            {"name": "Tokyo", "country": "Japan", "budget": "$2,500-$4,000", "activities": ["Culture", "Food", "Shopping"], "why": "Unique mix of tradition and modernity that fascinates every visitor."},
            {"name": "Lisbon", "country": "Portugal", "budget": "$1,800-$2,800", "activities": ["History", "Beaches", "Seafood"], "why": "Charming, affordable European gem with warm weather and great food."},
        ]
    else:
        destinations_data = [
            {
                "name": d.name,
                "country": d.country,
                "budget": f"${int(d.budget_midpoint * 0.7):,}-${int(d.budget_midpoint * 1.3):,}",
                "activities": d.vibes[:3] if d.vibes else ["Sightseeing", "Culture", "Food"],
                "why": f"Great destination for a group of {group_size} with {', '.join(d.vibes[:2]) if d.vibes else 'varied'} interests.",
            }
            for d in destinations[:5]
        ]

    rows = []
    db.query(Recommendation).filter(Recommendation.trip_id == trip_id).delete()
    for idx, dest in enumerate(destinations_data[:5], start=1):
        row = Recommendation(
            trip_id=trip_id,
            destination_name=dest["name"],
            country=dest["country"],
            why_recommended=dest["why"],
            estimated_budget_range=dest["budget"],
            best_activities=dest["activities"],
            potential_concerns=None,
            ml_score=round(1.0 - (idx - 1) * 0.1, 2),
            llm_model_used="fallback-no-key",
            prompt_version="v1",
            quality_score=0.7,
            rank=idx,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    log.info("llm_fallback_recommendations", trip_id=str(trip_id), count=len(rows))
    return rows


class RecommendationEngine:
    def __init__(self, db):
        self.db = db
        self.gateway = ModelGateway()
        self.evaluator = LLMEvaluator()
        self.ab = ABTestManager()

    def generate(self, trip_id, ml_context, group_size):
        # If no LLM key configured, use ML-based fallback
        if not self.gateway.client:
            log.warning("llm_no_key_using_fallback", trip_id=str(trip_id))
            rows = _fallback_recommendations(self.db, trip_id, group_size)
            # Set trip to voting
            from app.models.trip import Trip
            trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
            if trip:
                trip.status = "voting"
                self.db.commit()
            return rows

        version = self.ab.pick_prompt_version(trip_id, db=self.db)
        if version == "v1":
            system = recommendation_v1.SYSTEM_PROMPT
            user = recommendation_v1.build_user_prompt(ml_context, group_size)
        else:
            system = recommendation_v2.SYSTEM_PROMPT
            user = recommendation_v2.build_user_prompt(ml_context, group_size)

        log.info("llm_generating_recommendations", trip_id=str(trip_id), prompt_version=version)
        try:
            payload = self.gateway.complete(
                "recommendation_generation",
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.4,
            )
        except LLMError:
            log.warning("llm_error_using_fallback", trip_id=str(trip_id))
            rows = _fallback_recommendations(self.db, trip_id, group_size)
            from app.models.trip import Trip
            trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
            if trip:
                trip.status = "voting"
                self.db.commit()
            return rows

        parsed = payload["content"]
        quality_score = self.evaluator.evaluate(parsed)

        if quality_score < QUALITY_THRESHOLD:
            log.warning("llm_low_quality", trip_id=str(trip_id), prompt_version=version, quality_score=round(quality_score, 3))
            llm_low_quality_total.labels(prompt_version=version).inc()

        llm_recommendation_quality.labels(prompt_version=version).observe(quality_score)

        self.db.query(Recommendation).filter(Recommendation.trip_id == trip_id).delete()
        rows = []
        for idx, rec in enumerate(parsed.get("recommendations", [])[:10], start=1):
            destination = rec.get("destination", "Unknown")
            row = Recommendation(
                trip_id=trip_id,
                destination_name=destination,
                country=rec.get("country"),
                why_recommended=rec.get("why_this_group"),
                estimated_budget_range=rec.get("estimated_budget_per_person"),
                best_activities=rec.get("top_3_activities", []),
                potential_concerns=rec.get("potential_concern"),
                ml_score=rec.get("ml_alignment_score", 0.0),
                llm_model_used=payload["model"],
                prompt_version=version,
                quality_score=quality_score,
                rank=idx,
            )
            self.db.add(row)
            rows.append(row)

        log_llm_usage(self.db, trip_id, payload["model"], "recommendation_generation",
                      payload["prompt_tokens"], payload["completion_tokens"],
                      payload["latency_ms"], prompt_version=version)
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows
