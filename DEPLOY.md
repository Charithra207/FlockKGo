# Deploying (free tier)

| Piece    | Where              | Cost |
|----------|--------------------|------|
| Frontend | Vercel             | free |
| API      | Render web service | free (sleeps after 15 min idle, ~50 s cold start) |
| Database | Neon Postgres      | free, doesn't expire |

The ML analysis runs inside the API (`USE_CELERY=false`), so you don't need Redis or a worker.

## 1. Database (Neon)
1. Create a project at neon.tech and pick the Singapore or Mumbai region (closest to Karnataka).
2. Copy the connection string (`postgresql://...`).

## 2. API (Render)
1. In Render, choose **New → Blueprint** and pick this repo. It reads `render.yaml`.
2. Set these environment variables:
   - `DATABASE_URL`: the Neon string
   - `FRONTEND_BASE_URL`: your Vercel URL (fill this in after step 3)
   - `API_SECRET_KEY`: the output of `openssl rand -hex 32`
   - `OPENAI_API_KEY`: optional
   - `AUTH_TOKEN_SECRET`: generated automatically by Render
3. Deploy. On every start, `build.sh` runs `db_bootstrap.py`, which creates or upgrades the tables, then seeds the 65 Karnataka destinations.
4. Check that `https://<your-service>.onrender.com/health` returns OK.

## 3. Frontend (Vercel)
1. Import the repo and set **Root directory** to `frontend`.
2. Set these environment variables:
   - `VITE_API_URL=https://<your-service>.onrender.com/v1`
   - `VITE_API_KEY`: required because `ENVIRONMENT=production` enforces `X-API-Key` on the trip endpoints. Create one with:
     ```
     curl -X POST https://<api>/v1/admin/api-keys -H "X-Admin-Secret: $API_SECRET_KEY" \
          -H "Content-Type: application/json" -d '{"name":"web"}'
     ```
3. Deploy, then put the Vercel URL into Render's `FRONTEND_BASE_URL`.

## 4. Make yourself an admin and load cafes
1. Sign up on the live site.
2. In the Render **Shell** tab, run:
   ```
   python make_admin.py you@example.com
   python import_osm_cafes.py            # all 31 districts; retries if Overpass is busy
   ```
3. Open `/admin/spots` to review submissions.

## Local development
```
cd backend
python db_bootstrap.py && python seed_destinations.py
uvicorn app.main:app --reload
cd ../frontend && npm install && npm run dev
```
If you have an old `flockgo_demo.db` from before the spots feature, delete it and run `db_bootstrap.py` again. It is demo data only.
