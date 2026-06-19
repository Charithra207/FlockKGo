"""
metrics.py — Prometheus metrics for PackVote+.

All metrics are module-level singletons — Prometheus requires this.
Import and increment from anywhere in the app.

Metrics exposed at GET /metrics (Prometheus scrape endpoint).

Categories
----------
  Business metrics  — trips, surveys, votes (what the app does)
  ML metrics        — pipeline duration, cluster count, quality scores
  LLM metrics       — cost, latency, quality, circuit breaker state
  System metrics    — WebSocket connections, budget optimizer calls
"""

from prometheus_client import Counter, Gauge, Histogram

# ── Business metrics ──────────────────────────────────────────────────────────

trips_created_total = Counter(
    "packvote_trips_created_total",
    "Total trips created",
)
surveys_submitted_total = Counter(
    "packvote_surveys_submitted_total",
    "Total survey responses submitted",
)
votes_submitted_total = Counter(
    "packvote_votes_submitted_total",
    "Total votes submitted",
)

# ── ML metrics ────────────────────────────────────────────────────────────────

ml_pipeline_duration_seconds = Histogram(
    "packvote_ml_pipeline_duration_seconds",
    "End-to-end ML pipeline duration (feature engineering → scoring)",
    buckets=[1, 2, 5, 10, 30, 60, 120],
)
ml_cluster_count = Histogram(
    "packvote_ml_cluster_count",
    "Number of preference clusters found per trip",
    buckets=[1, 2, 3, 4, 5],
)
ml_silhouette_score = Histogram(
    "packvote_ml_silhouette_score",
    "KMeans silhouette score (0=random, 1=perfect)",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── LLM metrics ───────────────────────────────────────────────────────────────

llm_request_duration_seconds = Histogram(
    "packvote_llm_request_duration_seconds",
    "LLM API call latency in seconds",
    ["model"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30],
)
llm_cost_total = Counter(
    "packvote_llm_cost_usd_total",
    "Cumulative LLM spend in USD",
    ["model"],
)
llm_low_quality_total = Counter(
    "packvote_llm_low_quality_total",
    "LLM responses below quality threshold (score < 0.5)",
    ["prompt_version"],
)
llm_recommendation_quality = Histogram(
    "packvote_llm_recommendation_quality_score",
    "LLMEvaluator quality score per generation (0–1)",
    ["prompt_version"],
    buckets=[0.0, 0.25, 0.5, 0.75, 1.0],
)
llm_circuit_breaker_state = Gauge(
    "packvote_llm_circuit_breaker_state",
    "OpenAI circuit breaker state (0=closed, 1=half_open, 2=open)",
)

# ── System metrics ────────────────────────────────────────────────────────────

ws_active_connections = Gauge(
    "packvote_ws_active_connections",
    "Number of active WebSocket connections",
)
budget_optimizer_calls_total = Counter(
    "packvote_budget_optimizer_calls_total",
    "Total budget optimization runs",
    ["status"],  # optimal | feasible | fallback | infeasible
)
api_key_auth_total = Counter(
    "packvote_api_key_auth_total",
    "API key authentication attempts",
    ["result"],  # success | failure | skipped
)
