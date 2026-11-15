#!/usr/bin/env bash
# build.sh — Runs on every Render deploy before the server starts.
# Handles schema migrations and initial data seeding.
set -e

echo "=== PackVote+ deploy script ==="
echo "Environment: ${ENVIRONMENT:-development}"
echo "Database URL prefix: ${DATABASE_URL:0:20}..."

# ── 1. Schema ──────────────────────────────────────────────────────────────
# db_bootstrap.py creates all tables on a fresh DB (the Alembic history can't
# build the base tables from scratch) and runs migrations on existing ones.
echo ""
echo "--- Preparing database schema ---"
python db_bootstrap.py
echo "Schema ready."

# ── 2. Seed Karnataka destination catalog ────────────────────────────────────────────
# Idempotent — skips destinations that already exist.
# Generates OpenAI embeddings if OPENAI_API_KEY is set.
echo ""
echo "--- Seeding destinations ---"
python seed_destinations.py
echo "Destinations seeded."

echo ""
echo "=== Deploy script complete. Starting server... ==="
