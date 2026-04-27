from app.llm.prompts import recommendation_v1, recommendation_v2


def get_prompt_template(version: str):
    if version == "v2":
        return recommendation_v2.SYSTEM_PROMPT, recommendation_v2.build_user_prompt
    return recommendation_v1.SYSTEM_PROMPT, recommendation_v1.build_user_prompt
