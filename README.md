# PackVote+

**Collaborative group travel consensus engine** — uses a hybrid ML/LLM pipeline to solve the hardest problem in group travel: getting 6 people with different budgets, vibes, and schedules to agree on a destination.

> Live API: `https://packvote-api.onrender.com`
> API Docs: `https://packvote-api.onrender.com/docs`

---

## What makes this different

Most "AI trip planners" send a user prompt to ChatGPT and print the response. PackVote+ does not do that.

The ML pipeline does the actual work:
1. Survey responses are converted into 16-dimensional preference vectors
2. KMeans clustering finds preference groups within the party
3. Destinations are scored using cosine similarity (semantic embeddings when available, hand-crafted vectors as fallback)
4. The top destinations go to GPT-4o — which **only writes descriptions**, it does not choose anything
5. Participants vote using Instant Runoff Voting with ML scores as tiebreakers
6. A linear programming budget optimizer (PuLP) produces a fair per-person spending plan

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         React Frontend                          │
│                    (Vite + Tailwind, Vercel)                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP + WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│                   (Python 3.11, Render)                         │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  REST API   │  │  WebSocket   │  │   Prometheus /metrics │  │
│  │  /v1/...    │  │  /ws/...     │  │   + structlog JSON    │  │
│  └──────┬──────┘  └──────┬───────┘  └───────────────────────┘  │
│         │                │                                       │
│         ▼                ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Service Layer                         │    │
│  │  trip_service  survey_service  voting_service  cache    │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│              ┌──────────────┼──────────────┐                    │
│              ▼              ▼              ▼                    │
│   ┌──────────────┐  ┌────────────┐  ┌──────────────┐           │
│   │  ML Pipeline │  │LLM Gateway │  │Budget Optim. │           │
│   │  (scikit-learn│  │(OpenAI +  │  │(PuLP LP model│           │
│   │   + PuLP)    │  │ circuit    │  │ 6 categories)│           │
│   └──────┬───────┘  │ breaker)  │  └──────────────┘           │
│          │          └────────────┘                              │
│          ▼                                                       │
│   ┌──────────────┐                                              │
│   │  Celery Task │  ← dispatched async, retries on failure      │
│   │  Queue       │                                              │
│   └──────────────┘                                              │
└──────────┬──────────────────────────────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌───────┐    ┌───────┐
│  PG   │    │ Redis │
│  DB   │    │broker │
└───────┘    └───────┘
```

---

## ML Pipeline Detail

```
Survey Responses
      │
      ▼
Feature Engineering (16-d vectors)
  • budget_midpoint / 10000
  • budget_range_size
  • 8 vibe one-hot (beach, adventure, cultural...)
  • 3 climate one-hot (warm, cold, any)
  • activity_level (0.0 / 0.5 / 1.0)
  • date_flexibility
  • exclusion_strictness
      │
      ▼
KMeans Clustering (k=2..4, best silhouette score)
  • Finds dominant preference group
  • Identifies minority preferences
      │
      ▼
Destination Scoring
  • Semantic mode: OpenAI text-embedding-3-small cosine similarity
  • Feature mode:  hand-crafted vector L2 distance (offline fallback)
  • Score = 50% dominant cluster + 30% group mean + 20% minority
      │
      ▼
LLM Polish (GPT-4o)
  • Receives top 5 ML-scored destinations
  • Writes descriptions only — does NOT choose
  • A/B tested prompts (v1: expert consultant, v2: mediator)
  • Quality scored 0–1 by LLMEvaluator
      │
      ▼
Instant Runoff Voting
  • Participants rank destinations
  • Elimination rounds until >50% majority
  • ML scores used as tiebreakers
      │
      ▼
Budget Optimizer (PuLP)
  • Linear programme: minimise variance in budget utilisation
  • Constraints: per-person budget range + optional category caps
  • Returns itemized plan: flights 35%, accommodation 30%, food 15%...
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.104, Python 3.11 |
| ML | scikit-learn (KMeans), numpy, scipy |
| LLM | OpenAI GPT-4o / text-embedding-3-small |
| Optimization | PuLP 2.7 (CBC solver) |
| Task Queue | Celery 5.3 + Redis |
| Database | PostgreSQL (prod) / SQLite (dev) |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic |
| Caching | Redis (recommendation cache, 1h TTL) |
| Logging | structlog (JSON in prod, colored in dev) |
| Metrics | Prometheus + custom gauges/histograms |
| Auth | SHA-256 hashed API keys |
| Deploy | Render (API + worker + PostgreSQL + Redis) |
| Frontend | React + Vite + Tailwind (Vercel) |

---

## Project Structure

```
packvote/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI route handlers
│   │   │   ├── trips.py       # trip CRUD + ML dispatch + results
│   │   │   ├── surveys.py     # survey submission + token lookup
│   │   │   ├── recommendations.py  # cached recommendations
│   │   │   ├── voting.py      # ranked choice ballot submission
│   │   │   ├── budget.py      # LP budget optimizer endpoint
│   │   │   ├── analytics.py   # A/B test results + cost dashboard
│   │   │   ├── admin.py       # API key management
│   │   │   ├── health.py      # liveness + readiness probes
│   │   │   └── ws.py          # WebSocket status updates
│   │   ├── ml/            # Machine learning pipeline
│   │   │   ├── feature_engineering.py  # 16-d preference vectors
│   │   │   ├── clustering.py           # KMeans with silhouette selection
│   │   │   ├── scoring.py              # destination scoring (semantic + feature)
│   │   │   ├── similarity.py           # cosine similarity matrix
│   │   │   ├── drift_detection.py      # preference change detection
│   │   │   ├── embeddings.py           # OpenAI embedding cache
│   │   │   ├── pipeline.py             # orchestrator
│   │   │   └── budget_optimizer.py     # PuLP LP model
│   │   ├── llm/           # LLM integration
│   │   │   ├── gateway.py      # OpenAI client + circuit breaker
│   │   │   ├── recommender.py  # generation + quality evaluation
│   │   │   ├── ab_testing.py   # persistent A/B test manager
│   │   │   └── prompts/        # versioned prompt templates
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic v2 request/response schemas
│   │   ├── services/      # Business logic layer
│   │   │   ├── auth.py              # API key auth
│   │   │   ├── cache.py             # Redis cache helpers
│   │   │   └── websocket_manager.py # WebSocket connection pool
│   │   ├── workers/       # Celery task definitions
│   │   ├── monitoring/    # Prometheus metrics + cost tracking
│   │   └── core/          # Logging + middleware
│   ├── alembic/           # Database migration scripts
│   ├── tests/             # Integration + unit tests
│   ├── seed.py            # Demo data generator
│   ├── seed_destinations.py  # Destination catalog + embeddings
│   └── build.sh           # Render deploy script
└── frontend/              # React frontend (friend's work)
```

---

## Running Locally

### Option A — SQLite (no Docker, instant)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env: add OPENAI_API_KEY if you want LLM features

alembic upgrade head
python seed_destinations.py
python seed.py

uvicorn app.main:app --reload
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

### Option B — Docker (PostgreSQL + Redis + Celery)

```bash
cd backend
cp .env.example .env
# Edit .env: add OPENAI_API_KEY

docker-compose up --build
```

Services:
- API: http://localhost:8000
- Flower (Celery monitor): http://localhost:5555
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/trips` | Create a trip |
| POST | `/v1/trips/{id}/participants` | Add participant, get survey link |
| POST | `/v1/survey/{token}/submit` | Submit survey response |
| GET | `/v1/trips/{id}/summary` | Dashboard — who submitted |
| POST | `/v1/trips/{id}/run-analysis` | Trigger ML + LLM pipeline |
| GET | `/v1/trips/{id}/analysis` | Poll pipeline status |
| WS | `/ws/trips/{id}/status` | Real-time pipeline status |
| GET | `/v1/trips/{id}/ml-insights` | Full ML breakdown |
| GET | `/v1/trips/{id}/recommendations` | LLM recommendations |
| POST | `/v1/trips/{id}/votes` | Submit ranked choice ballot |
| GET | `/v1/trips/{id}/results` | IRV election results |
| POST | `/v1/trips/{id}/budget-plan` | LP budget optimization |
| GET | `/v1/analytics/ab-test` | Prompt A/B test results |
| GET | `/v1/analytics/cost-dashboard` | LLM spend breakdown |
| GET | `/health/detailed` | DB + Redis + OpenAI status |

Full interactive docs: `/docs`

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL or SQLite URL |
| `REDIS_URL` | No | Redis URL (Celery + cache) |
| `OPENAI_API_KEY` | No | Enables LLM + embeddings |
| `FRONTEND_BASE_URL` | No | CORS origin for frontend |
| `ENVIRONMENT` | No | `development` or `production` |
| `API_SECRET_KEY` | No | Enables API key auth (prod) |
