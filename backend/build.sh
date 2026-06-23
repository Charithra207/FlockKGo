#!/usr/bin/env bash
# build.sh — Runs on every Render deploy before the server starts.
# Handles schema migrations and initial data seeding.
set -e

echo "=== PackVote+ deploy script ==="
echo "Environment: ${ENVIRONMENT:-development}"
echo "Database URL prefix: ${DATABASE_URL:0:20}..."

# ── 1. Run Alembic migrations ──────────────────────────────────────────────
echo ""
echo "--- Running database migrations ---"
alembic upgrade head
echo "Migrations complete."

# ── 2. Seed destination catalog ────────────────────────────────────────────
# Idempotent — skips destinations that already exist.
# Generates OpenAI embeddings if OPENAI_API_KEY is set.
echo ""
echo "--- Seeding destinations ---"
python seed_destinations.py
echo "Destinations seeded."

echo ""
echo "=== Deploy script complete. Starting server... ==="
