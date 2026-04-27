def notify_participant(channel: str, destination: str, message: str) -> dict:
    return {"channel": channel, "destination": destination, "status": "queued", "message": message}
