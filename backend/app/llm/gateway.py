"""
gateway.py — OpenAI LLM gateway with circuit breaker.

Circuit breaker pattern:
  CLOSED  → normal operation, calls go through
  OPEN    → too many failures, calls are blocked immediately (fast fail)
  HALF_OPEN → after cooldown, one trial call is allowed to test recovery

Why this matters for interviews:
  "When OpenAI has an outage, the circuit breaker prevents the app from
   hammering a dead endpoint, consuming tokens on timeout fees, and
   blocking the Celery worker for 6 minutes. It fails fast and lets the
   task retry after the cooldown period."
"""

import json
import time
from enum import Enum
from threading import Lock

from openai import OpenAI

from app.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


class LLMError(Exception):
    pass


class CircuitState(Enum):
    CLOSED = "closed"       # normal — calls allowed
    OPEN = "open"           # too many failures — calls blocked
    HALF_OPEN = "half_open" # testing recovery — one call allowed


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,    # failures before opening
        cooldown_seconds: int = 60,    # how long to stay open
        success_threshold: int = 1,    # successes to close from half-open
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.cooldown_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
            return self._state

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    log.warning("circuit_breaker_closed", reason="OpenAI recovered")

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    log.error(
                        "circuit_breaker_open",
                        failure_count=self._failure_count,
                        cooldown_seconds=self.cooldown_seconds,
                    )
                self._state = CircuitState.OPEN

    def is_allowed(self) -> bool:
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)


# Module-level circuit breaker — shared across all gateway instances
_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    cooldown_seconds=60,
)


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

    @property
    def circuit_status(self) -> str:
        return _circuit_breaker.state.value

    def complete(self, task, messages, temperature=0.3, override_model=None) -> dict:
        if not self.client:
            raise LLMError("OpenAI API key not configured")

        # Circuit breaker check — fail fast if OpenAI is having issues
        if not _circuit_breaker.is_allowed():
            raise LLMError(
                f"OpenAI circuit breaker is OPEN — too many recent failures. "
                f"Retry after {_circuit_breaker.cooldown_seconds}s cooldown."
            )

        primary = override_model or self.task_models.get(task, "gpt-4o-mini")

        # Try primary model, fall back to gpt-4o-mini
        for model in [primary, "gpt-4o-mini"]:
            try:
                log.info("llm_call_start", model=model, task=task, circuit=_circuit_breaker.state.value)
                start = time.perf_counter()
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    timeout=30,
                )
                latency_ms = int((time.perf_counter() - start) * 1000)
                usage = response.usage
                content = json.loads(response.choices[0].message.content)

                _circuit_breaker.record_success()
                log.info(
                    "llm_call_complete",
                    model=model,
                    task=task,
                    latency_ms=latency_ms,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                )

                return {
                    "model": model,
                    "content": content,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "latency_ms": latency_ms,
                    "cost_usd": self._cost(model, usage.prompt_tokens, usage.completion_tokens),
                }

            except LLMError:
                raise

            except Exception as e:
                _circuit_breaker.record_failure()
                log.error("llm_call_failed", model=model, task=task, error=str(e))
                if model == "gpt-4o-mini":
                    raise LLMError(str(e))

        raise LLMError("All models failed")
