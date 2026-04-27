SYSTEM_PROMPT = """You are an expert travel consultant that uses ML data to generate personalized group recommendations. Always return valid JSON."""


def build_user_prompt(ml_context: str, group_size: int) -> str:
    return f"""
Use this ML context:
{ml_context}

Group size: {group_size}
Return JSON in this exact shape:
{{
  "recommendations": [
    {{
      "destination": "City, Country",
      "country": "Country",
      "why_this_group": "specific ML-based reason",
      "estimated_budget_per_person": "$X - $Y USD",
      "best_months_to_visit": ["Month1", "Month2"],
      "top_3_activities": ["act1", "act2", "act3"],
      "potential_concern": "any conflict",
      "ml_alignment_score": 0.00
    }}
  ],
  "group_insight": "observation about group compatibility",
  "budget_recommendation": "which tier fits this group"
}}
Provide exactly 5 recommendations.
""".strip()
