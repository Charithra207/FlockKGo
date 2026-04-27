import re


class LLMEvaluator:
    def evaluate(self, recommendations_json) -> float:
        recommendations = recommendations_json.get("recommendations", [])
        score = 0.0

        if len(recommendations) == 5:
            score += 0.25

        required_fields = {
            "destination",
            "country",
            "why_this_group",
            "estimated_budget_per_person",
            "best_months_to_visit",
            "top_3_activities",
            "potential_concern",
            "ml_alignment_score",
        }
        if recommendations and all(required_fields.issubset(r.keys()) for r in recommendations):
            score += 0.25

        budget_ok = True
        for rec in recommendations:
            numbers = [int(x) for x in re.findall(r"\d+", rec.get("estimated_budget_per_person", ""))]
            if len(numbers) < 2 or min(numbers) < 100 or max(numbers) > 50000:
                budget_ok = False
                break
        if recommendations and budget_ok:
            score += 0.25

        if recommendations and all(len(rec.get("top_3_activities", [])) > 0 for rec in recommendations):
            score += 0.25

        return max(0.0, min(1.0, score))
