from sqlalchemy import func

from app.models.recommendation import LLMUsageLog

PRICES = {
    "gpt-4o": {"in": 2.50 / 1_000_000, "out": 10.00 / 1_000_000},
    "gpt-4o-mini": {"in": 0.15 / 1_000_000, "out": 0.60 / 1_000_000},
}


def log_llm_usage(db, trip_id, model, task, prompt_tokens, completion_tokens, latency_ms, prompt_version=None):
    p = PRICES.get(model, PRICES["gpt-4o-mini"])
    cost_usd = prompt_tokens * p["in"] + completion_tokens * p["out"]
    row = LLMUsageLog(
        trip_id=trip_id,
        model_name=model,
        task_type=task,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        prompt_version=prompt_version,
    )
    db.add(row)
    db.commit()
    return row


def get_total_cost_for_trip(db, trip_id):
    value = db.query(func.coalesce(func.sum(LLMUsageLog.cost_usd), 0.0)).filter(LLMUsageLog.trip_id == trip_id).scalar()
    return float(value)


def get_usage_summary(db):
    rows = db.query(LLMUsageLog.model_name, func.count(LLMUsageLog.id), func.avg(LLMUsageLog.latency_ms), func.sum(LLMUsageLog.cost_usd)).group_by(LLMUsageLog.model_name).all()
    return {
        "total_llm_cost": float(sum((r[3] or 0.0) for r in rows)),
        "calls_by_model": {r[0]: int(r[1]) for r in rows},
        "average_latency_ms": float(sum((r[2] or 0.0) for r in rows) / len(rows)) if rows else 0.0,
    }
