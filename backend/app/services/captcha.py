"""Optional Cloudflare Turnstile check + a honeypot field for bots."""

from typing import Optional

import httpx
from fastapi import HTTPException

from app.config import get_settings


def check_human(captcha_token: Optional[str], honeypot: Optional[str], ip: Optional[str] = None) -> None:
    # Hidden "website" field: people never see it, simple bots fill it in.
    if honeypot:
        raise HTTPException(status_code=400, detail="Something went wrong. Please try again.")
    secret = get_settings().turnstile_secret
    if not secret:
        return
    if not captcha_token:
        raise HTTPException(status_code=400, detail="Please complete the 'I'm human' check")
    try:
        r = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": captcha_token, **({"remoteip": ip} if ip else {})},
            timeout=10,
        )
        ok = r.json().get("success") is True
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status_code=400, detail="The 'I'm human' check failed. Please try again.")
