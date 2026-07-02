"""
sync_admin.py — Sync observability and availability admin router.

Phase 5, Task 5.1 (schemas) + Task 5.2 (admin routes).

Endpoints:
  POST /admin/destinations/{destination_id}/availability  — mark destination available/unavailable
  GET  /admin/sync/runs                                   — list last 20 SyncRun records
  GET  /admin/sync/runs/{run_id}                          — get full SyncRun detail
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.admin import _require_master_secret
from app.dependencies import get_db
from app.models.destination import Destination
from app.models.destination_availability import DestinationAvailability
from app.models.sync_run import SyncRun
from app.schemas.availability import AvailabilityRequest, AvailabilityResponse
from app.schemas.sync import SyncRunDetail, SyncRunSummary

router = APIRouter(prefix="/admin", tags=["sync-admin"])


# ---------------------------------------------------------------------------
# Destination Availability
# ---------------------------------------------------------------------------

@router.post(
    "/destinations/{destination_id}/availability",
    response_model=AvailabilityResponse,
)
def set_destination_availability(
    destination_id: uuid.UUID,
    payload: AvailabilityRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_master_secret),
):
    """
    Create or update a DestinationAvailability record for a destination.

    - 404 if destination_id does not exist.
    - 422 if reason > 200 chars (enforced by schema Field(max_length=200)).
    """
    destination = db.query(Destination).filter(Destination.id == destination_id).first()
    if not destination:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination not found")

    # Upsert: one record per destination — update if exists, create if not
    record = (
        db.query(DestinationAvailability)
        .filter(DestinationAvailability.destination_id == destination_id)
        .first()
    )

    if record:
        record.is_available = payload.is_available
        record.reason = payload.reason
        record.expires_at = payload.expires_at
    else:
        record = DestinationAvailability(
            id=uuid.uuid4(),
            destination_id=destination_id,
            is_available=payload.is_available,
            reason=payload.reason,
            expires_at=payload.expires_at,
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    return AvailabilityResponse(
        id=record.id,
        destination_id=record.destination_id,
        destination_name=destination.name,
        is_available=record.is_available,
        reason=record.reason,
        expires_at=record.expires_at,
        created_at=record.created_at,
    )


# ---------------------------------------------------------------------------
# Sync Run Observability
# ---------------------------------------------------------------------------

@router.get("/sync/runs", response_model=list[SyncRunSummary])
def list_sync_runs(
    db: Session = Depends(get_db),
    _: None = Depends(_require_master_secret),
):
    """
    Return the last 20 SyncRun records ordered by started_at DESC.
    Returns [] (HTTP 200) when no records exist.
    """
    runs = (
        db.query(SyncRun)
        .order_by(SyncRun.started_at.desc())
        .limit(20)
        .all()
    )
    return runs


@router.get("/sync/runs/{run_id}", response_model=SyncRunDetail)
def get_sync_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: None = Depends(_require_master_secret),
):
    """
    Return full SyncRun detail including stage_counts.
    Returns 404 if run_id not found.
    """
    run = db.query(SyncRun).filter(SyncRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SyncRun not found")
    return run
