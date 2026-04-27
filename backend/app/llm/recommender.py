from app.llm.ab_testing import ABTestManager
from app.llm.evaluator import LLMEvaluator
from app.llm.gateway import LLMError, ModelGateway
from app.llm.prompts import recommendation_v1, recommendation_v2
from app.models.recommendation import Recommendation
from app.monitoring.cost_tracker import log_llm_usage


class RecommendationEngine:
    def __init__(self, db):
        self.db = db
        self.gateway = ModelGateway()
        self.evaluator = LLMEvaluator()
        self.ab = ABTestManager()

    def generate(self, trip_id, ml_context, group_size):
        version = self.ab.pick_prompt_version(trip_id)
        if version == "v1":
            system = recommendation_v1.SYSTEM_PROMPT
            user = recommendation_v1.build_user_prompt(ml_context, group_size)
        else:
            system = recommendation_v2.SYSTEM_PROMPT
            user = recommendation_v2.build_user_prompt(ml_context, group_size)

        print(f"[LLM] generating recommendations for trip={trip_id} version={version}")
        payload = self.gateway.complete(
            "recommendation_generation",
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.4,
        )
        parsed = payload["content"]
        _quality = self.evaluator.evaluate(parsed)

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
                rank=idx,
            )
            self.db.add(row)
            rows.append(row)

        log_llm_usage(
            self.db,
            trip_id,
            payload["model"],
            "recommendation_generation",
            payload["prompt_tokens"],
            payload["completion_tokens"],
            payload["latency_ms"],
            prompt_version=version,
        )
        self.db.commit()
        for row in rows:
            self.db.refresh(row)
        return rows
