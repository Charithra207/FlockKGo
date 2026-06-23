# Architecture & Design Decisions

Every significant technical decision in PackVote+ is documented here with the reasoning and tradeoffs considered. This is the document I use to prepare for architecture questions in interviews.

---

## 1. Why KMeans for preference clustering?

**Decision:** Use KMeans clustering on participant preference vectors.

**Why KMeans:**
- Interpretable — each cluster has a centroid that represents the "average" preference of that group
- Fast — O(n·k·i) where n=participants, k=clusters, i=iterations. For groups of 2–20 people this is <10ms
- Silhouette score gives a clean quality metric for picking k automatically

**Why not DBSCAN or hierarchical clustering:**
- DBSCAN requires tuning ε and min_samples, which doesn't generalize well across different group sizes
- Hierarchical clustering doesn't scale and requires manually cutting the dendrogram
- For groups of 2–20 people, KMeans with automatic k selection (k=2..4) is the right tradeoff

**The k selection strategy:**
Try k=2, 3, 4. Pick the k with the highest silhouette score. This means the algorithm finds the natural groupings in the data rather than forcing a fixed number.

**Tradeoff accepted:**
KMeans assumes spherical clusters and is sensitive to outliers. For travel preference data (mostly binary features + continuous budget), this is acceptable. A future improvement would be to use a Gaussian Mixture Model for softer cluster boundaries.

---

## 2. Why a hybrid ML + LLM architecture instead of just asking ChatGPT?

**Decision:** ML pipeline does the scoring, LLM only writes descriptions.

**The problem with pure LLM:**
- LLMs hallucinate destinations that don't fit the group's actual budget
- Every run costs money ($0.02–0.05 per call for GPT-4o)
- Non-deterministic — the same group gets different destinations on different runs
- No mathematical basis — "I think Bali suits you" with no scoring

**Our approach:**
- ML scores all 20 destinations mathematically against group preference vectors
- LLM receives only the top 5 ML-scored destinations and writes descriptions
- LLM token usage drops by ~70% compared to asking it to choose destinations
- Results are reproducible — same survey data → same top destinations

**Resume line this earns:**
"Reduced LLM token costs by ~70% by using ML pre-filtering before LLM generation"

---

## 3. Why Instant Runoff Voting instead of simple majority vote?

**Decision:** IRV (ranked choice) rather than first-past-the-post voting.

**The problem with majority vote:**
If 6 people vote for 3 destinations and the split is 3/2/1, the winner gets only 50% of votes. The other 50% are ignored. This leads to arguments.

**Why IRV:**
- Every vote eventually counts — losing votes transfer to next preferences
- A destination can only win with an absolute majority (>50%)
- Handles 3+ options fairly, which is exactly our use case (5 recommendations)
- Well-studied algorithm — used in real elections (Australia, Ireland, ranked choice referendums)

**ML score tiebreaker:**
When the lowest-vote candidate has a tie for elimination, we eliminate the one with the lower ML score. This prevents a mathematically poor destination from surviving due to vote splitting.

**Tradeoff accepted:**
IRV can produce a "wrong" winner in edge cases (Condorcet paradox). For a group travel app with 2–10 voters and 5 options, this is theoretical and not worth the complexity of Condorcet methods.

---

## 4. Why PuLP for budget optimization instead of just averaging?

**Decision:** Linear programming with PuLP rather than taking the average or median budget.

**The problem with averaging:**
If Alice has a budget of $800–1000 and Bob has $1500–3000, the average is $1400 — which is $400 above Alice's maximum. She simply cannot go. Averaging ignores hard constraints.

**The LP model:**
- Decision variables: `spend_i` for each participant
- Constraints: `budget_min_i ≤ spend_i ≤ budget_max_i`
- Objective: minimise variance in *budget utilisation* (spend / budget_max) across all participants
- Result: everyone uses approximately the same fraction of their budget — fairness, not equality

**Why minimise utilisation variance and not just total cost:**
Minimising total cost would push everyone to their minimum. Minimising utilisation variance means a flexible person (large budget range) absorbs more of the slack, while a constrained person stays near their minimum. This is intuitively fair.

**Fallback:**
If PuLP is unavailable or constraints conflict, we fall back to 75% of each person's max budget — still better than averaging.

---

## 5. Why Celery + Redis instead of FastAPI BackgroundTasks?

**Decision:** ML pipeline runs as a Celery task, not a FastAPI background thread.

**The problem with BackgroundTasks:**
- Runs in the same process as the API server
- CPU-heavy ML work (KMeans, numpy) blocks the Python GIL and degrades API responsiveness
- No retry logic — if the task fails, it's gone
- No visibility — you can't see what's running or failed

**Why Celery:**
- Runs in a separate worker process — API stays responsive during ML execution
- Built-in retry with exponential backoff (`max_retries=2, default_retry_delay=30`)
- Flower dashboard shows task history, success/failure rates, worker status
- Tasks survive API restarts — queued tasks are in Redis

**Graceful fallback:**
If Redis is unavailable (local dev without Docker), the code falls back to BackgroundTasks automatically. The app always works.

**Tradeoff accepted:**
Celery adds operational complexity — you need Redis running and a separate worker process. For a portfolio project this is the right complexity to add because it's a real engineering skill that appears in job descriptions.

---

## 6. Why SHA-256 for API key storage?

**Decision:** Store only the SHA-256 hash of API keys, never the plaintext.

**Why not bcrypt/argon2 like passwords:**
- API keys are long (256 bits of entropy) — they don't need the slow hashing that passwords need to defeat brute force
- SHA-256 is fast enough for lookup on every request (no rate limiting concern)
- bcrypt produces different hashes for the same input (salted) — you can't look up a key by hash

**Why SHA-256 over storing plaintext:**
If the database is breached, attackers get hashes. A 256-bit random key has 2^256 possible values — SHA-256 preimage attacks are computationally infeasible.

**The key format:** `flockgo_<64-hex-chars>`
The prefix makes leaked keys identifiable (useful for GitHub secret scanning alerts).

---

## 7. Why structlog instead of Python's stdlib logging?

**Decision:** structlog with JSON output in production.

**The problem with print() and stdlib logging:**
```
[ML] starting pipeline for trip=abc123 k=2 duration=1.2s
```
This is a string. You cannot query it. You cannot filter by trip_id. You cannot aggregate durations.

**With structlog:**
```json
{"timestamp": "2025-01-01T12:00:00Z", "level": "info", "event": "ml_pipeline_complete",
 "request_id": "uuid", "trip_id": "uuid", "clusters": 2, "duration_ms": 1240}
```
This is structured data. A log aggregator (Datadog, CloudWatch, Loki) can:
- Group all logs for a single request by `request_id`
- Alert when `level == "error"`
- Dashboard average `duration_ms` over time
- Trace a user action from API → Celery → LLM

**Correlation IDs:**
Every HTTP request gets a `request_id`. structlog's context variables automatically include it in every log line emitted during that request — including logs from the ML pipeline called from that request.

---

## 8. Why WebSocket for ML status instead of polling?

**Decision:** WebSocket push instead of HTTP polling.

**The problem with polling:**
The frontend was polling `GET /trips/{id}/analysis` every 3 seconds. For 100 concurrent users waiting for their ML results, that's 100 requests × 20/sec = 2000 DB queries per minute of pure overhead.

**With WebSocket:**
- One persistent connection per waiting user
- Server pushes when status changes — zero wasted queries
- Client gets update in <100ms instead of waiting up to 3s

**The polling fallback still exists** in the frontend (via `useAnalysisPoller` hook) — if WebSocket fails, the frontend degrades to polling. Resilience is more important than elegance.

---

## 9. Why SQLite for development, PostgreSQL for production?

**Decision:** SQLite locally, PostgreSQL on Render.

**Why SQLite locally:**
- Zero setup — no Docker required to run the backend
- Alembic migrations work identically on both
- 99% of application logic is database-agnostic (SQLAlchemy ORM abstracts the dialect)

**The one catch:**
SQLAlchemy's UUID type behaves differently on SQLite vs PostgreSQL. We use `Uuid` (capital U) from `sqlalchemy` which handles both. The `check_same_thread=False` connect arg is needed for SQLite in a threaded FastAPI context.

**URL normalisation:**
Render provides `postgres://` URLs. SQLAlchemy requires `postgresql+psycopg2://`. We normalise silently in `database.py` and `alembic/env.py`.

---

## 10. Why A/B test prompt versions?

**Decision:** Two prompt variants, persistent DB assignment, auto-exploitation.

**v1 — Expert consultant framing:**
Positions the LLM as an authority making recommendations. Tends to produce more confident, opinionated descriptions.

**v2 — Collaborative mediator framing:**
Positions the LLM as helping the group find compromise. Tends to acknowledge tradeoffs and competing preferences.

**The feedback loop:**
- Exploration phase (<5 trips per version): balanced alternating assignment
- Exploitation phase (≥5 trips, >5% quality gap): always assign the statistically better version
- Quality is measured by `LLMEvaluator`: correct field count, budget format validity, activity completeness

**Why this matters:**
Most projects do random A/B assignment and never analyse the results. Ours closes the feedback loop. The system gets better over time.
