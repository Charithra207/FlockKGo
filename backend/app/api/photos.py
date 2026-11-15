"""
photos.py — Upload and serve spot photos.

POST /v1/photos          multipart "file" (JPEG/PNG/WebP, <= 1.5 MB) -> {id, url}
GET  /v1/photos/{id}     the image bytes (cached for a year; ids never change)
"""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.trips import limiter
from app.dependencies import get_db
from app.models.photo import Photo
from app.models.user import User
from app.services.user_auth import get_current_user

router = APIRouter(tags=["photos"])

MAX_BYTES = 1_500_000
MAX_PHOTOS_PER_USER = 200


def sniff_image_type(head: bytes) -> str | None:
    """Trust the bytes, not the filename or the client's Content-Type."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.post("/photos", status_code=201)
@limiter.limit("30/hour")
async def upload_photo(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Photo is too big (max 1.5 MB)")
    content_type = sniff_image_type(data[:16])
    if not content_type:
        raise HTTPException(status_code=415, detail="Please upload a JPEG, PNG or WebP image")
    count = db.query(func.count(Photo.id)).filter(Photo.user_id == user.id).scalar()
    if count >= MAX_PHOTOS_PER_USER and not user.is_admin:
        raise HTTPException(status_code=429, detail="Photo limit reached")
    photo = Photo(user_id=user.id, content_type=content_type, size_bytes=len(data), data=data)
    db.add(photo)
    db.commit()
    return {"id": str(photo.id), "url": f"/v1/photos/{photo.id}"}


@router.get("/photos/{photo_id}")
def get_photo(photo_id: uuid.UUID, db: Session = Depends(get_db)):
    photo = db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return Response(
        content=photo.data,
        media_type=photo.content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
