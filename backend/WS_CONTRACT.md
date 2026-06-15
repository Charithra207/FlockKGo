# WebSocket Contract

## Endpoint
```
WS ws://localhost:8000/ws/trips/{trip_id}/status
```

## How to connect (React)
```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/trips/${tripId}/status`)

ws.onopen = () => console.log('Connected')

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data)

  switch (msg.type) {
    case 'connection_established':
      // Sent immediately on connect — gives you current state
      console.log('Current status:', msg.status)
      break

    case 'status_update':
      if (msg.status === 'running_ml') {
        // Show loading spinner
      }
      if (msg.status === 'voting') {
        // ML done — redirect to recommendations page
        // msg.top_destination — top ML pick
        // msg.clusters_found  — number of preference clusters
      }
      if (msg.status === 'collecting_preferences' && msg.task_status === 'failed') {
        // Show error: msg.error
      }
      break

    case 'ping':
      // Server keepalive — no action needed, connection is healthy
      break
  }
}

ws.onerror = (err) => console.error('WS error', err)
ws.onclose = () => console.log('Disconnected')
```

## Message shapes (server → client)

### On connect
```json
{
  "type": "connection_established",
  "trip_id": "uuid",
  "status": "running_ml",
  "task_status": "running",
  "top_destination": null,
  "clusters_found": null
}
```

### Status update (ML running)
```json
{
  "type": "status_update",
  "trip_id": "uuid",
  "status": "running_ml",
  "task_status": "running"
}
```

### Status update (ML complete)
```json
{
  "type": "status_update",
  "trip_id": "uuid",
  "status": "voting",
  "task_status": "complete",
  "top_destination": "Bali",
  "clusters_found": 2,
  "duration_seconds": 4.2,
  "message": "Analysis complete — closing connection"
}
```

### Status update (ML failed)
```json
{
  "type": "status_update",
  "trip_id": "uuid",
  "status": "collecting_preferences",
  "task_status": "failed",
  "error": "Need at least 2 survey responses"
}
```

### Keepalive ping (every 30s)
```json
{ "type": "ping" }
```
