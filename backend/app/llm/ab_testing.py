"""
ab_testing.py — Persistent A/B test manager for prompt versions.

Old behaviour: random assignment stored in an in-memory dict.
               Lost on every server restart. Useless for analysis.

New behaviour: assignment stored in `prompt_version_assignments` table.
               Same trip always gets the same version.
               Assignments are evenly distributed (alternating) across new trips,
               falling back to random if the DB is unavailable.
"""

import random
from sqlalchemy.orm import Session

from app.models.prompt_version import PromptVersionAssignment


class ABTestManager:
    VERSIONS = ["v1", "v2"]

    def pick_prompt_version(self, trip_id, db: Session = None) -> str:
        """
        Return the prompt version for a trip, persisting the assignment
        if it doesn't exist yet.

        Falls back to random choice if db is None (e.g. during tests).
        """
        if db is None:
            return random.choice(self.VERSIONS)

        tid = str(trip_id)

        # Check for existing assignment
        existing = (
            db.query(PromptVersionAssignment)
            .filter(PromptVersionAssignment.trip_id == trip_id)
            .first()
        )
        if existing:
            return existing.version

        # New trip — assign version to keep distribution even
        # Count existing assignments per version
        from sqlalchemy import func
        counts = (
            db.query(
                PromptVersionAssignment.version,
                func.count(PromptVersionAssignment.id).label("n"),
            )
            .group_by(PromptVersionAssignment.version)
            .all()
        )
        count_map = {r.version: r.n for r in counts}
        v1_count = count_map.get("v1", 0)
        v2_count = count_map.get("v2", 0)

        # Assign whichever version has fewer assignments (balanced distribution)
        version = "v1" if v1_count <= v2_count else "v2"

        assignment = PromptVersionAssignment(trip_id=trip_id, version=version)
        db.add(assignment)
        db.commit()

        return version
