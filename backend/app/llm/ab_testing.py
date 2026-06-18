"""
ab_testing.py — Persistent A/B test manager with auto-selection.

Phases
------
EXPLORATION  (< MIN_SAMPLES per version)
  Balanced assignment — alternate v1/v2 to build up enough data.
  Same as before.

EXPLOITATION (>= MIN_SAMPLES per version)
  Compare avg quality scores. If one version is clearly better
  (margin > QUALITY_MARGIN), always assign that version.
  Otherwise keep alternating (versions are equivalent).

Why this matters for interviews
---------------------------------
  "The A/B test has a feedback loop. Once I have enough quality data,
   the system stops randomly assigning and starts exploiting the better
   prompt. This is a simplified epsilon-greedy bandit strategy."
"""

import random
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.prompt_version import PromptVersionAssignment

# Minimum trips per version before switching to exploitation
MIN_SAMPLES = 5

# Quality score margin to declare a winner (0.05 = 5 percentage points)
QUALITY_MARGIN = 0.05


class ABTestManager:
    VERSIONS = ["v1", "v2"]

    # ── Public API ────────────────────────────────────────────────────────────

    def pick_prompt_version(self, trip_id, db: Session = None) -> str:
        """
        Return the prompt version for this trip.
        Persists the assignment so the same trip always gets the same version.
        Falls back to random if db is None.
        """
        if db is None:
            return random.choice(self.VERSIONS)

        # Return existing assignment (idempotent)
        existing = (
            db.query(PromptVersionAssignment)
            .filter(PromptVersionAssignment.trip_id == trip_id)
            .first()
        )
        if existing:
            return existing.version

        # New trip — decide which version to assign
        version = self._select_version(db)

        assignment = PromptVersionAssignment(trip_id=trip_id, version=version)
        db.add(assignment)
        db.commit()

        return version

    def get_current_strategy(self, db: Session) -> dict:
        """
        Returns the current selection strategy and quality stats.
        Exposed via GET /analytics/ab-test for transparency.
        """
        stats = self._quality_stats(db)
        phase, winner = self._evaluate_phase(stats)

        return {
            "phase": phase,
            "winner": winner,
            "min_samples_required": MIN_SAMPLES,
            "quality_margin_threshold": QUALITY_MARGIN,
            "version_stats": stats,
        }

    # ── Internal logic ────────────────────────────────────────────────────────

    def _select_version(self, db: Session) -> str:
        """Pick which version to assign to a new trip."""
        stats = self._quality_stats(db)
        phase, winner = self._evaluate_phase(stats)

        if phase == "exploitation" and winner:
            return winner

        # Exploration phase — keep balanced
        v1_count = stats.get("v1", {}).get("trips", 0)
        v2_count = stats.get("v2", {}).get("trips", 0)
        return "v1" if v1_count <= v2_count else "v2"

    def _quality_stats(self, db: Session) -> dict:
        """
        Pull avg quality score and trip count per version from the DB.
        Joins PromptVersionAssignment → Recommendation (via trip_id).
        """
        from app.models.recommendation import Recommendation

        rows = (
            db.query(
                PromptVersionAssignment.version,
                func.count(func.distinct(PromptVersionAssignment.trip_id)).label("trips"),
                func.avg(Recommendation.quality_score).label("avg_quality"),
            )
            .join(
                Recommendation,
                Recommendation.trip_id == PromptVersionAssignment.trip_id,
            )
            .filter(Recommendation.quality_score.isnot(None))
            .group_by(PromptVersionAssignment.version)
            .all()
        )

        stats = {}
        for row in rows:
            stats[row.version] = {
                "trips": int(row.trips),
                "avg_quality": round(float(row.avg_quality or 0.0), 4),
            }
        return stats

    def _evaluate_phase(self, stats: dict) -> tuple[str, str | None]:
        """
        Returns (phase, winner_version | None).

        phase = "exploration" | "exploitation"
        winner = "v1" | "v2" | None (None means tie or not enough data)
        """
        v1 = stats.get("v1", {})
        v2 = stats.get("v2", {})

        v1_trips = v1.get("trips", 0)
        v2_trips = v2.get("trips", 0)

        # Not enough data yet
        if v1_trips < MIN_SAMPLES or v2_trips < MIN_SAMPLES:
            return "exploration", None

        v1_q = v1.get("avg_quality", 0.0)
        v2_q = v2.get("avg_quality", 0.0)
        diff = abs(v1_q - v2_q)

        if diff < QUALITY_MARGIN:
            # Too close to call — keep exploring
            return "exploration", None

        winner = "v1" if v1_q > v2_q else "v2"
        return "exploitation", winner
