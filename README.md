# FlockGo

**Group trips around Karnataka, decided together, plus the hidden spots only locals know.**

**Live:** https://flock-k-go.vercel.app  ·  **API:** https://packvote-api-nmz2.onrender.com/docs  ·  **Deploy guide:** [DEPLOY.md](DEPLOY.md)

FlockGo does two things:

1. **Plans a group trip without the group-chat chaos.** Everyone fills a short survey. The app groups people by taste, ranks Karnataka destinations for the whole group, everyone votes, and a fair per-person budget comes out the other end.
2. **Maps Karnataka's hidden spots, by locals.** Quiet waterfalls, hilltops, viewpoints and the cafe only the town knows. To see someone else's hidden spot, you share one of your own.

---

## Give a spot, get a spot

| Action | Credits |
|---|---|
| Sign up | +1 free unlock |
| Share a **hidden** spot (once an admin approves it) | +3 |
| Share a **public** spot (once approved) | +1 |
| Unlock a hidden spot (exact location, directions, photos) | −1 |
| Vouch "I've been here" | 0 (ranks spots, can't be farmed) |

- Locked spots are hidden **on the server**: the API returns only the district and an approximate area (shown as a dashed circle), never the real coordinates.
- New submissions go to an admin review queue at `/admin/spots`. Duplicates (same kind of place within 150 m) are rejected, and each user can have at most 5 waiting for review.
- Photos are resized in the browser and stored in the database.

## What's on the map at launch

619 spots across all 31 districts, from open data (no scraping):

| | Count | Source |
|---|---|---|
| Hidden gems (locked) | 100 across 26 districts | OpenStreetMap + Wikidata |
| Public waterfalls, peaks, viewpoints, lakes, temples | ~290 | OpenStreetMap + Wikidata |
| Independent cafes | 230 | OpenStreetMap |

Famous places (Jog, Abbey, Hebbe, Nandi Hills, …) are public; lesser-known ones far from the main tourist hubs are hidden. Descriptions contain only facts from the source data. Every place's district was confirmed by reverse geocoding, and anything outside Karnataka was dropped.

The real value comes from locals adding places that aren't on any map. That's what "Share a spot" is for.

## Other features

- **ಕನ್ನಡ / English** switch (the trip-planning screens are English only for now).
- **Trip companion** (`/trip/:id/plan`): packing list, shared expenses with "who pays whom", day-by-day itinerary, how to get there (KSRTC / IRCTC / redBus links), and SOS with the nearest hospitals and police stations from OpenStreetMap.
- **65 destination hubs** across Karnataka, each with coordinates and district.

---

## How the group decision works

The ML pipeline makes the choice; the language model (optional) only writes descriptions.

1. Survey answers become 16-number preference vectors (budget in ₹, vibe, climate, activity level, flexibility).
2. KMeans clustering finds the taste groups inside the party.
3. Destinations are scored: 50% dominant group, 30% whole-group average, 20% minority group, so nobody is ignored.
4. Optional: GPT-4o writes descriptions for the top 5. It doesn't choose anything. Without an `OPENAI_API_KEY`, the app still works and uses plain descriptions.
5. Everyone ranks the shortlist; **Instant Runoff Voting** picks the winner, with ML scores as tiebreakers.
6. A linear-programming optimiser (PuLP) splits the budget fairly across travel, stay, food and activities.

---

## Architecture

```
  Browser ──► React + Vite + Tailwind + Leaflet (Vercel)
                    │  HTTPS, X-API-Key + Bearer token
                    ▼
            FastAPI (Render, free web service)
            ├── /v1/trips, surveys, votes, budget    ─► ML pipeline (scikit-learn, PuLP)
            ├── /v1/spots, /v1/auth, /v1/photos       ─► give-to-get credits
            └── background analysis runs in-process (USE_CELERY=false)
                    │
                    ▼
            PostgreSQL (Neon, free)
```

Redis and Celery are supported but optional. They're switched off on the free deploy, and the cache fails gracefully without Redis.

| Layer | Tech |
|---|---|
| Frontend | React 18, Vite, Tailwind, zustand, react-leaflet + OpenStreetMap tiles |
| API | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, slowapi rate limits |
| Auth | scrypt password hashes + signed bearer tokens (users); SHA-256 hashed API keys (site) |
| ML | scikit-learn KMeans, numpy, PuLP |
| LLM (optional) | OpenAI GPT-4o, text-embedding-3-small |
| Data | OpenStreetMap (ODbL), Wikidata (CC0), Nominatim geocoding |
| Hosting | Vercel + Render + Neon, all free tier |

---

## Project structure

```
FlockGo/
├── render.yaml                 # Render blueprint (API only, free plan)
├── DEPLOY.md                   # step-by-step deploy guide
├── .github/workflows/
│   └── keep-api-awake.yml      # pings the API every 10 min so it doesn't sleep
├── backend/
│   ├── app/
│   │   ├── api/                # routes: trips, surveys, voting, budget, spots, accounts, photos, admin…
│   │   ├── core/karnataka.py   # districts, bounding box, distance helpers
│   │   ├── ml/                 # features, clustering, scoring, budget optimiser
│   │   ├── models/             # SQLAlchemy models (Trip, Spot, User, Photo…)
│   │   └── services/           # auth, cache, SOS, travel options…
│   ├── alembic/                # migrations
│   ├── data/                   # OSM/Wikidata spot snapshots loaded on deploy
│   ├── build.sh                # runs on every Render start: migrate → seed → load spots
│   ├── db_bootstrap.py         # creates tables on a fresh DB, upgrades an old one
│   ├── seed_destinations.py    # the 65 Karnataka hubs
│   ├── import_osm_spots.py     # fetch/refresh spots from OSM + Wikidata, load into DB
│   ├── make_admin.py           # python make_admin.py you@example.com
│   └── tests/                  # 300+ tests
└── frontend/
    └── src/
        ├── pages/              # Home, Explore, SpotDetail, ShareSpot, TripCompanion, AdminSpots…
        ├── components/spots/   # SpotMap, SpotCard
        ├── services/           # api.js, spotsService.js, companionService.js
        └── i18n.js             # English + Kannada strings
```

---

## Running locally

**Backend** (SQLite, no Docker needed):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env              # OPENAI_API_KEY is optional

python db_bootstrap.py            # create tables
python seed_destinations.py       # 65 Karnataka hubs
python import_osm_spots.py load   # 619 spots
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /v1 to :8000)
```

Make yourself an admin: put your email in `ADMIN_EMAILS` (or run `python make_admin.py you@example.com`), then sign up or log in.

**Tests:**

```bash
cd backend
pytest
```

If you have an old `flockgo_demo.db` from before the spots feature, delete it and rerun the setup. It only holds demo data.

---

## Key API endpoints

| Method | Endpoint | What it does |
|---|---|---|
| POST | `/v1/auth/register`, `/v1/auth/login` | Accounts (returns a bearer token) |
| GET | `/v1/spots?district=&category=&lat=&lng=&radius_km=` | Search spots (locked ones redacted) |
| POST | `/v1/spots` | Share a spot (goes to review) |
| POST | `/v1/spots/{id}/unlock` | Spend 1 credit (402 if you have none) |
| POST | `/v1/spots/{id}/vouch` | "I've been here" |
| GET/POST | `/v1/admin/spots/pending`, `/v1/admin/spots/{id}/review` | Admin queue |
| POST | `/v1/photos` | Upload a photo (JPEG/PNG/WebP, ≤ 1.5 MB) |
| POST | `/v1/trips` | Create a trip |
| POST | `/v1/survey/{token}/submit` | Submit a survey |
| POST | `/v1/trips/{id}/run-analysis` | Run the ML pipeline |
| POST | `/v1/trips/{id}/votes` | Ranked-choice ballot |
| GET | `/v1/trips/{id}/results` | Voting results |
| POST | `/v1/trips/{id}/budget-plan` | Fair budget split |
| GET | `/health` | Liveness (no DB) |

Full interactive docs: `/docs` on the API.

---

## Environment variables

**Backend** (Render, or `backend/.env` locally):

| Variable | Needed | What it's for |
|---|---|---|
| `DATABASE_URL` | yes | Postgres (Neon) in production, SQLite locally |
| `API_SECRET_KEY` | production | Admin secret for creating site API keys; turns on API-key checks |
| `AUTH_TOKEN_SECRET` | production | Signs user login tokens (Render generates it) |
| `FRONTEND_BASE_URL` | production | Your Vercel URL, for CORS |
| `ADMIN_EMAILS` | production | Your login email(s), comma-separated; these accounts become admin |
| `ENVIRONMENT` | production | `production` |
| `USE_CELERY` | no | Keep `false` unless you run a Celery worker + Redis |
| `OPENAI_API_KEY` | no | Nicer descriptions and semantic scoring |
| `REDIS_URL` | no | Cache / Celery broker |
| `TRAWEX_API_URL`, `TRAWEX_API_KEY` | no | Live bus prices (without them the app shows official booking links) |
| `WIKIMEDIA_CONTACT` | no | Contact string, only needed to refresh spots from Wikidata |

**Frontend** (Vercel):

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://<your-api>.onrender.com/v1` |
| `VITE_API_KEY` | key from `POST /v1/admin/api-keys` (see DEPLOY.md) |

---

## Known limitations

- **Free hosting sleeps.** Render's free server sleeps after 15 min idle and takes ~50 s to wake. The keep-awake GitHub Action and a wake-up ping on page load hide this most of the time.
- **Cafe coverage follows OpenStreetMap,** which is dense in Bengaluru and thin elsewhere. Locals sharing spots fills the gaps.
- **Kannada translations need a native speaker's review.**
- **Live bus and hotel prices** need a booking API account; until then the app links to KSRTC, IRCTC and redBus.
- **The site API key (`VITE_API_KEY`) is visible in the browser.** It only stops casual scripting; rate limits and user accounts protect the real actions.

## Data & credits

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), available under the ODbL. Place data from [Wikidata](https://www.wikidata.org) (CC0). Geocoding by [Nominatim](https://nominatim.org). See [backend/data/README.md](backend/data/README.md).
