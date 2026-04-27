SYSTEM_PROMPT = """You are a collaborative travel mediator helping groups reach compromise and consensus. Use ML findings and always return valid JSON."""


def build_user_prompt(ml_context: str, group_size: int) -> str:
    return f"""
Here is ML insight for a travel group of {group_size} people:
{ml_context}
Generate compromise-friendly destination recommendations and explain tradeoffs.
Return JSON with the same schema as v1 and include exactly 5 recommendations.
""".strip()
