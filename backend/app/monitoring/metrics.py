from prometheus_client import Counter, Histogram

trips_created_total = Counter("trips_created_total", "Total trips created")
surveys_submitted_total = Counter("surveys_submitted_total", "Total surveys submitted")
ml_pipeline_duration_seconds = Histogram("ml_pipeline_duration_seconds", "ML pipeline duration seconds")
llm_request_duration_seconds = Histogram("llm_request_duration_seconds", "LLM latency", ["model"])
llm_cost_total = Counter("llm_cost_total", "LLM cost", ["model"])
votes_submitted_total = Counter("votes_submitted_total", "Votes submitted")
llm_low_quality_total = Counter("llm_low_quality_total", "LLM responses below quality threshold", ["prompt_version"])
