"""
pipeline.py — Sync orchestration for the India Destination Sync.

Phase 5, Task 5.2.

UPSERT CONTRACT
---------------
- Primary matching key: osm_source_id (NEVER name).
- Upserts are idempotent: running the same sync twice produces identical state.
- Existing rows are UPDATE-d only when mutable fields actually changed.
- created_at is NEVER updated.
- Existing recommendation IDs (destination.id) are NEVER recreated.
- Feature vector and embedding regeneration only happen when data changes.
- Soft delete only: destinations absent from current OSM results get
  is_active=False. Rows are NEVER physically deleted.

BATCH OPERATIONS
----------------
- All DB reads are bulk (query IN / query all).
- Inserts are batched (add_all + single commit per batch).
- Updates collect dirty rows and commit once per batch window.
- If a batch fails, only that transaction is rolled back.

COUNTS RETURNED
---------------
  inserted   — new destinations created
  updated    — existing destinations with at least one field change
  unchanged  — existing destinations with no field change
  deactivated — destinations soft-deleted this run
  skipped    — medium-quality candidates rejected due to catalog cap
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.logging import get_logger
from app.ml.scoring import VIBES_ORDER, ACTIVITY, _feature_vec_from_destination
from app.models.destination import Destination
from app.sync.dna_mapper import DNAResult, compute_dna, dna_to_feature_compatible
from app.sync.embedding_updater import run_embedding_update
from app.sync.geometry_filter import filter_candidates
from app.sync.opentripmap_enricher import OTMInfo, enrich_opentripmap
from app.sync.osm_fetcher import CandidateRecord, fetch_india_destinations
from app.sync.quality_scorer import QualityTier, ScoredCandidate, score_candidates
from app.sync.wikidata_enricher import WikidataInfo, enrich_wikidata

log = get_logger(__name__)

# Maximum rows per insert batch
_INSERT_BATCH_SIZE = 200


# ---------------------------------------------------------------------------
# Feature vector builder — mirrors _feature_vec_from_destination logic
# but builds from individual fields rather than an ORM row.
# ---------------------------------------------------------------------------

def _build_feature_vector_from_fields(
    budget_midpoint: int,
    budget_flexibility: float,
    vibes: list[str],
    climate: str,
    activity_level: str,
) -> list[float]:
    """
    Build a 16-d feature vector directly from destination fields.

    Matches the logic in scoring._feature_vec_from_destination so that
    newly synced destinations score correctly in the existing ML pipeline.
    """
    import numpy as np

    vec = [
        budget_midpoint / 10000.0,
        0.5,                                      # budget_range_size placeholder
        *[1.0 if v in (vibes or []) else 0.0 for v in VIBES_ORDER],
        *[1.0 if climate == c else 0.0 for c in ["warm", "cold", "any"]],
        ACTIVITY.get(activity_level, 0.5),
        1.0,                                      # date_flexibility placeholder
        0.0,                                      # exclusion_strictness placeholder
    ]
    return [max(0.0, min(1.0, float(v))) for v in vec]


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def _fields_changed(existing: Destination, new_fields: dict) -> bool:
    """Return True if any mutable field differs between the DB row and new data."""
    for field_name, new_val in new_fields.items():
        old_val = getattr(existing, field_name, None)
        # Normalise list comparison (JSON round-trip may reorder vibes)
        if isinstance(new_val, list) and isinstance(old_val, list):
            if sorted(str(x) for x in old_val) != sorted(str(x) for x in new_val):
                return True
        elif old_val != new_val:
            return True
    return False


def _make_destination_fields(
    candidate: CandidateRecord,
    dna: DNAResult,
    wikidata: WikidataInfo,
) -> dict:
    """
    Build the full dict of mutable fields for a Destination row from a
    ScoredCandidate + DNAResult.  Does NOT include id or created_at.
    """
    compat = dna_to_feature_compatible(dna)
    feature_vector = _build_feature_vector_from_fields(
        budget_midpoint=compat["budget_midpoint"],
        budget_flexibility=compat["budget_flexibility"],
        vibes=compat["vibes"],
        climate=compat["climate"],
        activity_level=compat["activity_level"],
    )
    return {
        "name": candidate.name,
        "country": "India",
        "budget_midpoint": compat["budget_midpoint"],
        "budget_flexibility": compat["budget_flexibility"],
        "vibes": compat["vibes"],
        "climate": compat["climate"],
        "activity_level": compat["activity_level"],
        "feature_vector": feature_vector,
        "is_active": True,
        "osm_source_id": candidate.osm_source_id,
        "travel_dna": dna.travel_dna,
        "tourism_metadata": {
            "wikidata_id": wikidata.wikidata_id,
            "wikipedia_url": wikidata.wikipedia_url,
            "image_url": wikidata.image_url,
            "is_unesco": wikidata.is_unesco,
        },
    }


# ---------------------------------------------------------------------------
# Core upsert function
# ---------------------------------------------------------------------------

def upsert_destinations(
    scored_candidates: list[ScoredCandidate],
    dna_results: dict[str, DNAResult],   # keyed by osm_source_id
    db: Session,
) -> dict:
    """
    Idempotently upsert scored candidates into the destinations table.

    Matching is by osm_source_id exclusively (never by name).
    created_at is never touched.
    Embeddings are only nullified when content fields actually change.
    Soft-deletes destinations no longer present in the current OSM results.

    Returns
    -------
    dict with keys:
        inserted, updated, unchanged, deactivated, skipped,
        upserted_changes (list[dict] for embedding_updater)
    """
    settings = get_settings()

    # -----------------------------------------------------------------------
    # Step 1: Bulk-load all existing destinations keyed by osm_source_id
    # -----------------------------------------------------------------------
    existing_by_osm: dict[str, Destination] = {
        d.osm_source_id: d
        for d in db.query(Destination).filter(
            Destination.osm_source_id.isnot(None)
        ).all()
    }

    # -----------------------------------------------------------------------
    # Step 2: Count active destinations (for catalog cap check on medium tier)
    # -----------------------------------------------------------------------
    active_count = db.query(Destination).filter(Destination.is_active == True).count()

    # -----------------------------------------------------------------------
    # Step 3: Process each scored candidate
    # -----------------------------------------------------------------------
    inserted = 0
    updated = 0
    unchanged = 0
    skipped = 0
    upserted_changes: list[dict] = []  # for embedding_updater

    rows_to_insert: list[Destination] = []
    osm_ids_in_current_run: set[str] = set()

    for scored in scored_candidates:
        osm_id = scored.candidate.osm_source_id
        osm_ids_in_current_run.add(osm_id)

        dna = dna_results.get(osm_id)
        if dna is None:
            log.warning("upsert_missing_dna", osm_source_id=osm_id)
            continue

        new_fields = _make_destination_fields(scored.candidate, dna, scored.wikidata)

        if osm_id in existing_by_osm:
            # ── UPDATE path ──────────────────────────────────────────────
            existing = existing_by_osm[osm_id]

            # Mutable fields we compare (exclude created_at, id, embedding*)
            mutable_keys = [
                "name", "country", "budget_midpoint", "budget_flexibility",
                "vibes", "climate", "activity_level", "feature_vector",
                "is_active", "travel_dna", "tourism_metadata",
            ]
            comparable = {k: new_fields[k] for k in mutable_keys if k in new_fields}

            if _fields_changed(existing, comparable):
                # Collect change record for embedding nullification
                upserted_changes.append({
                    "destination_id": existing.id,
                    "old_name": existing.name,
                    "new_name": new_fields["name"],
                    "old_vibes": existing.vibes,
                    "new_vibes": new_fields["vibes"],
                    "old_climate": existing.climate,
                    "new_climate": new_fields["climate"],
                    "old_activity_level": existing.activity_level,
                    "new_activity_level": new_fields["activity_level"],
                })
                for k, v in new_fields.items():
                    if k not in ("id", "created_at"):
                        setattr(existing, k, v)
                updated += 1
            else:
                unchanged += 1
                # Ensure is_active is True even if unchanged otherwise
                if not existing.is_active:
                    existing.is_active = True
                    updated += 1
                    unchanged -= 1

        else:
            # ── INSERT path ──────────────────────────────────────────────
            # Catalog cap: only medium-tier destinations are capped
            if scored.tier == QualityTier.MEDIUM:
                projected_active = active_count + len(rows_to_insert)
                if projected_active >= settings.catalog_max_active:
                    log.warning(
                        "catalog_cap_reached",
                        tier=scored.tier.value,
                        osm_source_id=osm_id,
                        active_count=projected_active,
                    )
                    skipped += 1
                    continue

            new_dest = Destination(
                id=uuid.uuid4(),
                **new_fields,
            )
            rows_to_insert.append(new_dest)
            inserted += 1

    # -----------------------------------------------------------------------
    # Step 4: Flush inserts in batches
    # -----------------------------------------------------------------------
    if rows_to_insert:
        try:
            for i in range(0, len(rows_to_insert), _INSERT_BATCH_SIZE):
                batch = rows_to_insert[i: i + _INSERT_BATCH_SIZE]
                db.add_all(batch)
                db.commit()
                log.info(
                    "upsert_insert_batch",
                    batch_start=i,
                    batch_size=len(batch),
                )
        except Exception:
            db.rollback()
            log.error("upsert_insert_batch_failed", batch_start=i)
            raise

    # -----------------------------------------------------------------------
    # Step 5: Flush updates
    # -----------------------------------------------------------------------
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.error("upsert_update_commit_failed")
        raise

    # -----------------------------------------------------------------------
    # Step 6: Soft-delete destinations absent from this run
    # -----------------------------------------------------------------------
    deactivated = 0
    if osm_ids_in_current_run:
        # Only soft-delete OSM-sourced destinations not in current run
        to_deactivate = (
            db.query(Destination)
            .filter(
                Destination.osm_source_id.isnot(None),
                Destination.is_active == True,
                ~Destination.osm_source_id.in_(osm_ids_in_current_run),
            )
            .all()
        )
        for dest in to_deactivate:
            dest.is_active = False
            deactivated += 1

        if deactivated:
            try:
                db.commit()
                log.info("upsert_soft_delete", count=deactivated)
            except Exception:
                db.rollback()
                log.error("upsert_soft_delete_failed")
                raise

    log.info(
        "upsert_complete",
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        deactivated=deactivated,
        skipped=skipped,
    )

    return {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "deactivated": deactivated,
        "skipped": skipped,
        "upserted_changes": upserted_changes,
    }


# ---------------------------------------------------------------------------
# Full pipeline orchestration
# ---------------------------------------------------------------------------

def run_sync_pipeline(db: Session) -> dict:
    """
    Orchestrate all sync components in sequence:

      1. fetch_india_destinations   (Overpass API)
      2. filter_candidates          (Geometry filter)
      3. enrich_wikidata / enrich_opentripmap  (per candidate)
      4. score_candidates           (Quality scorer)
      5. compute_dna                (DNA mapper)
      6. upsert_destinations        (DB upsert)
      7. run_embedding_update       (Incremental embeddings)

    Emits structlog entries at each stage with processed/accepted/rejected counts.
    Emits WARNING if rejected > 80% of processed at any stage.
    Returns stage counts dict compatible with SyncRun.stage_counts.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.

    Returns
    -------
    dict
        Keys: inserted, updated, unchanged, deactivated, skipped,
              fetched, stage_counts
    """
    settings = get_settings()
    stage_counts: dict[str, dict] = {}

    # -----------------------------------------------------------------------
    # Stage 1 — OSM Fetch
    # -----------------------------------------------------------------------
    raw_candidates = fetch_india_destinations(
        overpass_url=settings.overpass_api_url,
        batch_size=settings.osm_batch_size,
    )
    fetched = len(raw_candidates)
    _log_stage(stage_counts, "osm_fetch", processed=fetched, accepted=fetched, rejected=0)

    # -----------------------------------------------------------------------
    # Stage 2 — Geometry Filter
    # -----------------------------------------------------------------------
    filter_result = filter_candidates(raw_candidates)
    accepted_geo = filter_result.accepted
    rejected_geo = len(filter_result.rejected)
    _log_stage(
        stage_counts, "geometry_filter",
        processed=fetched,
        accepted=len(accepted_geo),
        rejected=rejected_geo,
    )

    # -----------------------------------------------------------------------
    # Stage 3 — Enrichment (Wikidata + OpenTripMap per candidate)
    # -----------------------------------------------------------------------
    wikidata_map: dict[str, WikidataInfo] = {}
    otm_map: dict[str, OTMInfo] = {}

    for candidate in accepted_geo:
        wikidata_map[candidate.osm_source_id] = enrich_wikidata(candidate)
        if settings.opentripmap_api_key:
            otm_map[candidate.osm_source_id] = enrich_opentripmap(
                candidate,
                api_key=settings.opentripmap_api_key,
            )
        else:
            otm_map[candidate.osm_source_id] = OTMInfo()

    _log_stage(
        stage_counts, "enrichment",
        processed=len(accepted_geo),
        accepted=len(accepted_geo),
        rejected=0,
    )

    # -----------------------------------------------------------------------
    # Stage 4 — Quality Scoring
    # -----------------------------------------------------------------------
    scored = score_candidates(
        accepted_geo,
        wikidata_map,
        otm_map,
        threshold_high=settings.quality_threshold_high,
        threshold_medium=settings.quality_threshold_medium,
    )
    rejected_quality = len(accepted_geo) - len(scored)
    _log_stage(
        stage_counts, "quality_scorer",
        processed=len(accepted_geo),
        accepted=len(scored),
        rejected=rejected_quality,
    )

    # -----------------------------------------------------------------------
    # Stage 5 — DNA Computation
    # -----------------------------------------------------------------------
    dna_results: dict[str, DNAResult] = {}
    for s in scored:
        dna_results[s.candidate.osm_source_id] = compute_dna(s)

    _log_stage(
        stage_counts, "dna_mapper",
        processed=len(scored),
        accepted=len(dna_results),
        rejected=0,
    )

    # -----------------------------------------------------------------------
    # Stage 6 — Upsert
    # -----------------------------------------------------------------------
    upsert_result = upsert_destinations(scored, dna_results, db)
    _log_stage(
        stage_counts, "upsert",
        processed=len(scored),
        accepted=upsert_result["inserted"] + upsert_result["updated"] + upsert_result["unchanged"],
        rejected=upsert_result["skipped"],
    )

    # -----------------------------------------------------------------------
    # Stage 7 — Embedding Update
    # -----------------------------------------------------------------------
    embedding_result = run_embedding_update(upsert_result["upserted_changes"], db)
    _log_stage(
        stage_counts, "embedding_update",
        processed=len(upsert_result["upserted_changes"]),
        accepted=embedding_result.embedded,
        rejected=0,
    )

    result = {
        "fetched": fetched,
        "inserted": upsert_result["inserted"],
        "updated": upsert_result["updated"],
        "unchanged": upsert_result["unchanged"],
        "deactivated": upsert_result["deactivated"],
        "skipped": upsert_result["skipped"],
        "stage_counts": stage_counts,
    }

    log.info(
        "sync_pipeline_complete",
        fetched=fetched,
        inserted=upsert_result["inserted"],
        updated=upsert_result["updated"],
        unchanged=upsert_result["unchanged"],
        deactivated=upsert_result["deactivated"],
        skipped=upsert_result["skipped"],
    )
    return result


# ---------------------------------------------------------------------------
# Stage logging helper
# ---------------------------------------------------------------------------

def _log_stage(
    stage_counts: dict,
    stage: str,
    processed: int,
    accepted: int,
    rejected: int,
) -> None:
    """Emit a structlog entry for a pipeline stage and check rejection rate."""
    stage_counts[stage] = {
        "processed": processed,
        "accepted": accepted,
        "rejected": rejected,
    }
    log.info(
        "sync_stage_complete",
        stage=stage,
        processed=processed,
        accepted=accepted,
        rejected=rejected,
    )
    if processed > 0 and rejected > 0.8 * processed:
        log.warning(
            "high_rejection_rate",
            stage=stage,
            processed=processed,
            rejected=rejected,
        )
