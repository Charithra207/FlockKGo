import json
import time

from openai import OpenAI

from app.config import get_settings


class LLMError(Exception):
    pass


class ModelGateway:
    task_models = {
        "recommendation_generation": "gpt-4o",
        "recommendation_evaluation": "gpt-4o-mini",
        "preference_summary": "gpt-4o-mini",
    }
    prices = {
        "gpt-4o": {"in": 2.50 / 1_000_000, "out": 10.00 / 1_000_000},
        "gpt-4o-mini": {"in": 0.15 / 1_000_000, "out": 0.60 / 1_000_000},
    }

    def __init__(self):
        api_key = get_settings().openai_api_key
        self.client = OpenAI(api_key=api_key) if api_key else None

    def _cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        p = self.prices.get(model, self.prices["gpt-4o-mini"])
        return prompt_tokens * p["in"] + completion_tokens * p["out"]

    def complete(self, task, messages, temperature=0.3, override_model=None) -> dict:
        if not self.client:
            raise LLMError("OpenAI API key not configured")

        primary = override_model or self.task_models.get(task, "gpt-4o-mini")
        for model in [primary, "gpt-4o-mini"]:
            try:
                print(f"[LLM] model={model} task={task}")
                start = time.perf_counter()
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
                latency_ms = int((time.perf_counter() - start) * 1000)
                usage = response.usage
                content = json.loads(response.choices[0].message.content)
                return {
                    "model": model,
                    "content": content,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "latency_ms": latency_ms,
                    "cost_usd": self._cost(model, usage.prompt_tokens, usage.completion_tokens),
                }
            except Exception as e:
                if model == "gpt-4o-mini":
                    raise LLMError(str(e))
        raise LLMError("Model call failed")
