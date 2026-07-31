"""
checklist.py — Collaborative Packing Hub endpoints.

All routes require X-API-Key authentication.

Endpoints:
  GET    /trips/{id}/checklist               — list all items for a trip
  POST   /trips/{id}/checklist               — add a custom item
  POST   /trips/{id}/checklist/suggest       — run Smart Suggestion engine
  PATCH  /trips/{id}/checklist/{item_id}     — update item (packed, assign, rename)
  DELETE /trips/{id}/checklist/{item_id}     — remove an item

WebSocket broadcast:
  After any mutation (add/update/delete), a WS broadcast is sent to all
  clients subscribed to trip_{trip_id} so everyone sees real-time sync.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.checklist import ChecklistItem
from app.models.destination import Destination
from app.models.participant import Participant
from app.models.recommendation import Recommendation
from app.models.trip import Trip
from app.services.auth import get_current_api_key
from app.services.smart_suggestions import generate_suggestions

limiter = Limiter(key_func=lambda request: request.client.host if request.client else "unknown")
router = APIRouter(tags=["checklist"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class AddItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="misc", max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    assigned_to_participant_id: str | None = None
    sort_order: int = 0


class PatchItemRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    is_packed: bool | None = None
    assigned_to_participant_id: str | None = None  # Pass empty string "" to unassign
    sort_order: int | None = None
    packed_by_participant_id: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _item_to_dict(item: ChecklistItem) -> dict:
    return {
        "id": str(item.id),
        "trip_id": str(item.trip_id),
        "name": item.name,
        "category": item.category,
        "suggested_by": item.suggested_by,
        "notes": item.notes,
        "assigned_to_participant_id": str(item.assigned_to_participant_id) if item.assigned_to_participant_id else None,
        "is_packed": item.is_packed,
        "packed_at": item.packed_at.isoformat() if item.packed_at else None,
        "packed_by_participant_id": str(item.packed_by_participant_id) if item.packed_by_participant_id else None,
        "sort_order": item.sort_order,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


async def _broadcast(trip_id: str, event: str, payload: dict) -> None:
    """Fire-and-forget WS broadcast to all clients of this trip."""
    try:
        from app.services.websocket_manager import manager
        await manager.broadcast(
            trip_id,
            {"event": event, "data": payload},
        )
    except Exception:
        pass   # WS broadcast is best-effort; never block the HTTP response


# ── GET /trips/{id}/checklist ─────────────────────────────────────────────────

@router.get("/trips/{trip_id}/checklist")
@limiter.limit("60/minute")
def get_checklist(
    request: Request,
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """Return all checklist items for a trip, grouped by category."""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    items = (
        db.query(ChecklistItem)
        .filter(ChecklistItem.trip_id == trip_id)
        .order_by(ChecklistItem.category, ChecklistItem.sort_order, ChecklistItem.created_at)
        .all()
    )

    # Group by category
    grouped: dict[str, list] = {}
    for item in items:
        grouped.setdefault(item.category, []).append(_item_to_dict(item))

    total = len(items)
    packed = sum(1 for i in items if i.is_packed)

    return {
        "trip_id": str(trip_id),
        "total_items": total,
        "packed_items": packed,
        "completion_pct": round(packed / total * 100, 1) if total else 0.0,
        "categories": grouped,
    }


# ── POST /trips/{id}/checklist/suggest ────────────────────────────────────────

@router.post("/trips/{trip_id}/checklist/suggest")
@limiter.limit("5/minute")
def generate_checklist(
    request: Request,
    trip_id: uuid.UUID,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """
    Run the Smart Suggestion engine and bulk-insert a baseline packing list.

    Reads the trip's winning recommendation to extract climate, vibes, and
    quick_info. Skips items that already exist (by name) to avoid duplicates.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Pull destination metadata from the top-ranked recommendation
    top_rec = (
        db.query(Recommendation)
        .filter(Recommendation.trip_id == trip_id)
        .order_by(Recommendation.rank.asc())
        .first()
    )

    # Try to look up the Destination row for richer metadata
    dest: Destination | None = None
    if top_rec:
        dest = (
            db.query(Destination)
            .filter(Destination.name == top_rec.destination_name)
            .first()
        )

    climate = dest.climate if dest else None
    activity_level = dest.activity_level if dest else None
    vibes = dest.vibes if dest else []
    quick_info = dest.quick_info if dest else (top_rec.destination_name if top_rec else trip.name)

    suggestions = generate_suggestions(
        trip_id=str(trip_id),
        quick_info=quick_info,
        climate=climate,
        activity_level=activity_level,
        vibes=vibes,
        duration_days=trip.duration_days,
    )

    # Load existing item names to skip duplicates
    existing_names = {
        name.lower().strip()
        for (name,) in db.query(ChecklistItem.name)
        .filter(ChecklistItem.trip_id == trip_id)
        .all()
    }

    new_items: list[ChecklistItem] = []
    for s in suggestions:
        if s["name"].lower().strip() not in existing_names:
            new_items.append(ChecklistItem(
                id=uuid.UUID(s["id"]),
                trip_id=trip_id,
                name=s["name"],
                category=s["category"],
                sort_order=s["sort_order"],
                suggested_by="system",
            ))

    if new_items:
        db.add_all(new_items)
        db.commit()

    return {
        "trip_id": str(trip_id),
        "generated": len(new_items),
        "skipped_duplicates": len(suggestions) - len(new_items),
        "destination": top_rec.destination_name if top_rec else None,
        "climate_used": climate,
        "vibes_used": vibes,
    }


# ── POST /trips/{id}/checklist ────────────────────────────────────────────────

@router.post("/trips/{trip_id}/checklist")
@limiter.limit("30/minute")
async def add_item(
    request: Request,
    trip_id: uuid.UUID,
    payload: AddItemRequest,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """Add a custom item to the trip checklist."""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Validate participant assignment if provided
    assigned_pid = None
    if payload.assigned_to_participant_id:
        try:
            assigned_pid = uuid.UUID(payload.assigned_to_participant_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid participant UUID")
        p = db.query(Participant).filter(
            Participant.id == assigned_pid,
            Participant.trip_id == trip_id,
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="Participant not found in this trip")

    item = ChecklistItem(
        trip_id=trip_id,
        name=payload.name,
        category=payload.category,
        notes=payload.notes,
        assigned_to_participant_id=assigned_pid,
        sort_order=payload.sort_order,
        suggested_by="user",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    data = _item_to_dict(item)
    await _broadcast(str(trip_id), "checklist_item_added", data)
    return data


# ── PATCH /trips/{id}/checklist/{item_id} ────────────────────────────────────

@router.patch("/trips/{trip_id}/checklist/{item_id}")
@limiter.limit("60/minute")
async def update_item(
    request: Request,
    trip_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: PatchItemRequest,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """
    Update a checklist item.

    Key use cases:
      - Mark as packed:      PATCH with is_packed=true (+ packed_by_participant_id)
      - Assign (Divvy Up):   PATCH with assigned_to_participant_id=<uuid>
      - Unassign:            PATCH with assigned_to_participant_id="" (empty string)
      - Rename / add notes:  PATCH with name / notes
    """
    item = db.query(ChecklistItem).filter(
        ChecklistItem.id == item_id,
        ChecklistItem.trip_id == trip_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    if payload.name is not None:
        item.name = payload.name
    if payload.category is not None:
        item.category = payload.category
    if payload.notes is not None:
        item.notes = payload.notes
    if payload.sort_order is not None:
        item.sort_order = payload.sort_order

    # Handle pack / unpack
    if payload.is_packed is not None:
        item.is_packed = payload.is_packed
        item.packed_at = datetime.now(timezone.utc) if payload.is_packed else None
        if payload.packed_by_participant_id:
            try:
                item.packed_by_participant_id = uuid.UUID(payload.packed_by_participant_id)
            except ValueError:
                pass
        elif not payload.is_packed:
            item.packed_by_participant_id = None

    # Handle assignment / unassignment
    if payload.assigned_to_participant_id is not None:
        if payload.assigned_to_participant_id == "":
            item.assigned_to_participant_id = None   # unassign
        else:
            try:
                apid = uuid.UUID(payload.assigned_to_participant_id)
                item.assigned_to_participant_id = apid
            except ValueError:
                raise HTTPException(status_code=422, detail="Invalid participant UUID")

    db.commit()
    db.refresh(item)

    data = _item_to_dict(item)
    event = "checklist_item_packed" if (payload.is_packed is True) else "checklist_item_updated"
    await _broadcast(str(trip_id), event, data)
    return data


# ── DELETE /trips/{id}/checklist/{item_id} ────────────────────────────────────

@router.delete("/trips/{trip_id}/checklist/{item_id}")
@limiter.limit("30/minute")
async def delete_item(
    request: Request,
    trip_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    _api_key=Depends(get_current_api_key),
):
    """Remove a checklist item."""
    item = db.query(ChecklistItem).filter(
        ChecklistItem.id == item_id,
        ChecklistItem.trip_id == trip_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    db.delete(item)
    db.commit()

    await _broadcast(str(trip_id), "checklist_item_deleted", {"id": str(item_id)})
    return {"deleted": True, "id": str(item_id)}
