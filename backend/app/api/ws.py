"""
ws.py — WebSocket endpoints for real-time trip status updates.

Endpoint:
  WS /ws/trips/{trip_id}/status

Protocol:
  1. Client connects.
  2. Server immediately sends current trip status (catch-up message).
  3. Server sends a ping every 30s to keep the connection alive.
  4. When the ML pipeline status changes, server pushes a status_update message.
  5. Client can send {"type": "ping"} — server replies {"type": "pong"}.
  6. On error or trip reaching terminal state (voting / failed), server
     sends a final message and closes cleanly.

Message shapes (server → client):
  {"type": "status_update", "trip_id": "...", "status": "running_ml",  "task_status": "running"}
  {"type": "status_update", "trip_id": "...", "status": "voting",      "task_status": "complete", "top_destination": "Bali"}
  {"type": "status_update", "trip_id": "...", "status": "collecting_preferences", "task_status": "failed", "error": "..."}
  {"type": "ping"}
  {"type": "connection_established", "trip_id": "...", "current_status": "..."}
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.ml_result import MLRunResult
from app.models.recommendation import Recommendation
from app.models.task_run import TaskRun
from app.models.trip import Trip
from app.services.websocket_manager import manager

router = APIRouter(tags=["websocket"])

PING_INTERVAL = 30       # seconds between server-side keepalive pings
TERMINAL_STATUSES = {"voting", "collecting_preferences"}  # close after these


def _get_current_status(db: Session, trip_id: uuid.UUID) -> dict:
    """Build the current status payload for a trip."""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        return {"status": "not_found"}

    task_run = (
        db.query(TaskRun)
        .filter(TaskRun.trip_id == trip_id)
        .order_by(TaskRun.created_at.desc())
        .first()
    )

    top = (
        db.query(Recommendation)
        .filter(Recommendation.trip_id == trip_id)
        .order_by(Recommendation.rank.asc())
        .first()
    )

    ml_run = (
        db.query(MLRunResult)
        .filter(MLRunResult.trip_id == trip_id)
        .order_by(MLRunResult.ran_at.desc())
        .first()
    )

    payload = {
        "trip_id": str(trip_id),
        "status": trip.status,
        "task_status": task_run.status if task_run else None,
        "top_destination": top.destination_name if top else None,
        "clusters_found": ml_run.cluster_count if ml_run else None,
    }

    if task_run and task_run.status == "failed":
        payload["error"] = task_run.error_message

    return payload


@router.websocket("/ws/trips/{trip_id}/status")
async def trip_status_ws(websocket: WebSocket, trip_id: uuid.UUID):
    """
    WebSocket endpoint for real-time ML pipeline status updates.

    Connect from the frontend:
      const ws = new WebSocket(`ws://localhost:8000/ws/trips/${tripId}/status`)
      ws.onmessage = (e) => console.log(JSON.parse(e.data))
    """
    trip_id_str = str(trip_id)
    await manager.connect(trip_id_str, websocket)

    db = SessionLocal()
    try:
        # 1. Send current status immediately so the client doesn't wait
        current = _get_current_status(db, trip_id)
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            **current,
        }))

        # If already in a terminal state, close cleanly
        if current.get("status") in TERMINAL_STATUSES:
            await websocket.send_text(json.dumps({
                "type": "status_update",
                "trip_id": trip_id_str,
                "status": current["status"],
                "message": "Analysis complete — closing connection",
            }))
            return

        # 2. Poll DB + send updates until terminal state or disconnect
        last_status = current.get("status")
        last_task_status = current.get("task_status")

        while True:
            # Wait — listen for client messages or timeout for ping
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=PING_INTERVAL)
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    continue
            except asyncio.TimeoutError:
                # No message from client — send keepalive ping
                await websocket.send_text(json.dumps({"type": "ping"}))

            # Check for status change
            db.expire_all()  # refresh ORM cache
            updated = _get_current_status(db, trip_id)
            new_status = updated.get("status")
            new_task_status = updated.get("task_status")

            if new_status != last_status or new_task_status != last_task_status:
                await websocket.send_text(json.dumps({
                    "type": "status_update",
                    **updated,
                }))
                last_status = new_status
                last_task_status = new_task_status

            # Close on terminal state
            if new_status in TERMINAL_STATUSES:
                await websocket.send_text(json.dumps({
                    "type": "status_update",
                    "trip_id": trip_id_str,
                    "status": new_status,
                    "message": "Analysis complete — closing connection",
                    "top_destination": updated.get("top_destination"),
                    "clusters_found": updated.get("clusters_found"),
                }))
                break

    except WebSocketDisconnect:
        pass  # Client closed connection — normal
    except Exception as e:
        # Send error message before closing
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        except Exception:
            pass
    finally:
        manager.disconnect(trip_id_str, websocket)
        db.close()
