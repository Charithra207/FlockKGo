"""
websocket_manager.py — WebSocket connection manager.

Tracks all active WebSocket connections per trip.
When the ML pipeline status changes, the Celery task calls
`notify_trip_status()` to broadcast the update to all
connected clients for that trip.

Architecture:
  Client connects to /ws/trips/{id}/status
      ↓
  ConnectionManager.connect() — adds to pool
      ↓
  Immediately sends current status (so late joiners catch up)
      ↓
  Celery task calls notify_trip_status() on state change
      ↓
  ConnectionManager.broadcast() — pushes JSON to all clients
      ↓
  On disconnect / error → ConnectionManager.disconnect()

Why this is better than polling:
  - Frontend gets update in <100ms vs waiting up to 3s
  - No wasted DB queries every 3 seconds per client
  - Scales cleanly — one broadcast serves all connected clients
"""

import asyncio
import json
from collections import defaultdict
from typing import Dict, List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # trip_id (str) → list of active WebSocket connections
        self._connections: Dict[str, List[WebSocket]] = defaultdict(list)

    async def connect(self, trip_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[trip_id].append(websocket)

    def disconnect(self, trip_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(trip_id, [])
        if websocket in connections:
            connections.remove(websocket)
        # Clean up empty lists
        if not connections:
            self._connections.pop(trip_id, None)

    async def broadcast(self, trip_id: str, message: dict) -> None:
        """Send a JSON message to all clients watching this trip."""
        connections = list(self._connections.get(trip_id, []))
        if not connections:
            return

        dead = []
        for ws in connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)

        # Remove disconnected clients
        for ws in dead:
            self.disconnect(trip_id, ws)

    def active_connections(self, trip_id: str) -> int:
        return len(self._connections.get(trip_id, []))

    def total_connections(self) -> int:
        return sum(len(v) for v in self._connections.values())


# Module-level singleton — shared across all requests in the same process
manager = ConnectionManager()


def notify_trip_status(trip_id: str, status: str, extra: dict = None) -> None:
    """
    Synchronous helper called from Celery tasks and background threads.
    Schedules a broadcast on the running event loop if one exists,
    otherwise silently skips (no clients connected).

    Args:
        trip_id: Trip UUID as string.
        status:  Trip status string (running_ml, voting, collecting_preferences, etc.)
        extra:   Optional additional fields merged into the message.
    """
    message = {"type": "status_update", "trip_id": trip_id, "status": status}
    if extra:
        message.update(extra)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(manager.broadcast(trip_id, message))
    except RuntimeError:
        # No event loop in this thread (Celery worker) — use run_coroutine_threadsafe
        try:
            import threading
            # Find the main thread's event loop
            for thread in threading.enumerate():
                if hasattr(thread, "_target") and hasattr(thread, "_loop"):
                    loop = thread._loop
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            manager.broadcast(trip_id, message), loop
                        )
                        return
        except Exception:
            pass  # Silently skip if no loop is reachable from this worker
