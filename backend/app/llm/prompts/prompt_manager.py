# prompt_manager.py
# Recommender imports v1/v2 directly — this file is kept for reference only.
# Use ab_testing.py to pick a version; import the module directly for prompts.

from app.llm.prompts import recommendation_v1, recommendation_v2


def get_prompt_template(version: str):
    """Return (system_prompt, build_user_prompt_fn) for the given version."""
    if version == "v2":
        return recommendation_v2.SYSTEM_PROMPT, recommendation_v2.build_user_prompt
    return recommendation_v1.SYSTEM_PROMPT, recommendation_v1.build_user_prompt
